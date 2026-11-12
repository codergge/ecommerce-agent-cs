"""
剔除 Qwen3 思考块（thinking）的过滤器。

为什么需要这一层：
    Qwen3 在部分 Ollama / langchain-ollama 版本下，不会把思考内容拆到 reasoning 字段，
    而是直接拼进 message.content。前端就会先看到一大段推理文字，最后才出现正式回答。
    即使已在模型侧尝试关闭 thinking，仍需输出层兜底，保证界面只呈现最终结果。

兼容三种收尾标记（不同版本/模板不一样，漏认任何一种都会把正文吞掉）：
    </think>
    <|end_of_thinking|>
    <｜end▁of▁thinking｜>   （Qwen3 原生特殊 token，带全角竖线）

开头探测（_PROBE_LEN）：
    个别模板会省略 <think> 开标签，直接输出推理文字。流式场景下如果边收边发，
    这些文字已经显示出去、收不回来。因此流开始时先缓冲最多 40 个字符：
      - 缓冲里出现 <think>        -> 正常进入思考模式（不产生额外延迟）
      - 缓冲里先出现 </think>     -> 判定为"隐式思考"，把标签前的内容整体丢弃
      - 缓冲超过 40 字符仍无标签  -> 判定为正常回答，一次性放出
    正常模型（带 <think> 开头）在第一个 chunk 就会判定，不受影响。

两种用法：
    ThinkStreamFilter  流式逐 token 过滤
    strip_think        一次性清洗整段文本，用于非流式回复
"""
import re

_OPENERS = ("<think>", "<|begin_of_thinking|>")
_CLOSERS = ("</think>", "<|end_of_thinking|>", "<｜end▁of▁thinking｜>")
_PROBE_LEN = 40          # 开头探测的缓冲长度（字符）
_PROBE_BYTES = 20        # 只探测英文/数字时更小的阈值，避免长英文回答被拖延

_THINK_BLOCK = re.compile(
    r"(?:<think\b[^>]*>|<\|begin_of_thinking\|>).*?"
    r"(?:</think\s*>|<\|end_of_thinking\|>|<｜end▁of▁thinking｜>)",
    re.IGNORECASE | re.DOTALL,
)


def _find_any(buf: str, tags, start: int):
    """在 buf 中从 start 开始找任意一个标记，返回 (位置, 长度)，找不到返回 (-1, 0)"""
    best_pos, best_len = -1, 0
    low = buf.lower()
    for tag in tags:
        p = low.find(tag.lower(), start)
        if p != -1 and (best_pos == -1 or p < best_pos):
            best_pos, best_len = p, len(tag)
    return best_pos, best_len


def _partial_suffix(buf: str, tags) -> int:
    """返回 buf 末尾与某个标记前缀匹配的最大长度（识别被切断的半个标签）"""
    limit = min(len(buf), max(len(t) for t in tags) - 1)
    for k in range(limit, 0, -1):
        tail = buf[-k:].lower()
        for tag in tags:
            if tail == tag.lower()[:k]:
                return k
    return 0


class ThinkStreamFilter:
    """
    流式过滤器示例：

        flt = ThinkStreamFilter()
        for token in stream:
            visible = flt.feed(token)
            if visible:
                print(visible, end="")
        tail = flt.flush()
    """

    def __init__(self):
        self._pending = ""      # 暂存的半个标签
        self._in_think = False  # 当前是否处于思考块内
        self._primed = False    # 是否已完成开头探测
        self._probe = ""        # 开头探测缓冲

    def _decide_probe(self) -> bool:
        """判断开头探测是否可以结束"""
        buf = self._probe
        open_pos, _ = _find_any(buf, _OPENERS, 0)
        close_pos, _ = _find_any(buf, _CLOSERS, 0)

        # 出现任意标签即可判定
        if open_pos != -1 or close_pos != -1:
            return True

        # 出现句读标点或换行：大概率是正常正文，立即放行（通常 1~2 个 token 就命中，几乎无延迟）
        if any(p in buf for p in "，。！？；：,.!?;:\n"):
            return True

        # 以 '<' 开头但标签还没凑齐，或一直没有任何标点：有限等待
        if buf.lstrip().startswith("<") or len(buf) >= _PROBE_LEN:
            return True
        return False

    def feed(self, text: str) -> str:
        """喂入一段文本，返回其中可以展示给用户的部分"""
        buf = self._pending + (text or "")
        self._pending = ""

        # ---------- 开头探测 ----------
        if not self._primed:
            self._probe += buf
            if not self._decide_probe():
                return ""
            buf = self._probe
            self._probe = ""
            self._primed = True

            # 隐式思考：没有开标签却先出现闭标签，丢弃闭标签之前的内容
            open_pos, _ = _find_any(buf, _OPENERS, 0)
            close_pos, close_len = _find_any(buf, _CLOSERS, 0)
            if close_pos != -1 and (open_pos == -1 or close_pos < open_pos):
                buf = buf[close_pos + close_len:]

        # ---------- 正常逐段处理 ----------
        out = []
        i = 0

        while i < len(buf):
            if self._in_think:
                end, end_len = _find_any(buf, _CLOSERS, i)
                if end == -1:
                    keep = _partial_suffix(buf[i:], _CLOSERS)
                    if keep:
                        self._pending = buf[-keep:]
                    return "".join(out)
                i = end + end_len
                self._in_think = False
                continue

            open_pos, open_len = _find_any(buf, _OPENERS, i)
            close_pos, close_len = _find_any(buf, _CLOSERS, i)

            if close_pos != -1 and (open_pos == -1 or close_pos < open_pos):
                i = close_pos + close_len
                continue

            if open_pos != -1:
                out.append(buf[i:open_pos])
                i = open_pos + open_len
                self._in_think = True
                continue

            keep = _partial_suffix(buf[i:], _OPENERS + _CLOSERS)
            if keep:
                out.append(buf[i:len(buf) - keep])
                self._pending = buf[-keep:]
            else:
                out.append(buf[i:])
            return "".join(out)

        return "".join(out)

    def flush(self) -> str:
        """流结束：吐出暂存内容；未闭合的思考块直接丢弃"""
        if not self._primed:
            rest = self._probe
            self._probe = ""
            self._primed = True
            return strip_think(rest)

        tail = self._pending
        self._pending = ""
        return "" if self._in_think else tail


def strip_think(text: str) -> str:
    """整段清洗：删除所有思考块及未闭合的残留思考内容"""
    if not text:
        return ""
    if not isinstance(text, str):
        text = str(text)

    # 1) 删除完整思考块
    prev = None
    while prev != text:
        prev, text = text, _THINK_BLOCK.sub("", text)

    low = text.lower()

    # 2) 只有开标签没有闭标签：丢弃开标签之后的内容
    pos = min(
        (low.find(t.lower()) for t in _OPENERS if low.find(t.lower()) != -1),
        default=-1,
    )
    if pos != -1:
        text = text[:pos]
        low = text.lower()

    # 3) 只有闭标签：保留最后一个闭标签之后的内容
    end_pos, end_len = -1, 0
    for t in _CLOSERS:
        p = low.rfind(t.lower())
        if p > end_pos:
            end_pos, end_len = p, len(t)
    if end_pos != -1:
        text = text[end_pos + end_len:]

    # 4) 压缩多余空行
    return re.sub(r"\n{3,}", "\n\n", text).strip()
