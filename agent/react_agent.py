"""
ReAct Agent：基于 LangGraph create_react_agent，把 LLM + 工具 + 记忆组装起来。
Agent 会自主决定：思考(Thought) -> 调用工具(Action) -> 观察(Observation) -> 再思考 -> 最终回答。
"""
from typing import Dict, Any, Generator

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, AIMessageChunk
from langgraph.prebuilt import create_react_agent

from core.llm import get_chat_llm
from core.prompts import SYSTEM_PROMPT
from agent.tools import ALL_TOOLS
from agent.memory import get_checkpointer


def _build_react_agent(llm, checkpointer):
    """
    兼容构造 create_react_agent。
    系统提示词参数在不同 LangGraph 版本里叫法不同：
      新版 prompt -> 过渡版 state_modifier -> 旧版 messages_modifier
    这里按新到旧依次尝试，避免换版本就报 TypeError。
    """
    base = dict(model=llm, tools=ALL_TOOLS, checkpointer=checkpointer)

    for kw in ("prompt", "state_modifier", "messages_modifier"):
        try:
            return create_react_agent(**base, **{kw: SYSTEM_PROMPT})
        except TypeError:
            continue

    raise RuntimeError(
        "当前 langgraph 版本无法识别系统提示词参数，请升级：pip install -U langgraph"
    )


class CustomerServiceAgent:
    """电商智能客服 Agent 封装。"""

    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.llm = get_chat_llm(streaming=True)
        self.checkpointer = get_checkpointer()
        self.agent = _build_react_agent(self.llm, self.checkpointer)

    @property
    def config(self) -> Dict[str, Any]:
        return {"configurable": {"thread_id": self.thread_id}}

    def chat(self, user_message: str) -> str:
        """同步对话，返回完整回复。"""
        result = self.agent.invoke(
            {"messages": [HumanMessage(content=user_message)]},
            config=self.config,
        )
        return result["messages"][-1].content

    def chat_stream(self, user_message: str) -> Generator[str, None, None]:
        """
        流式对话：逐 token 产出。同时通过 stream_mode="updates" 捕获工具调用事件，
        便于前端展示"正在查询订单..."这类中间状态。
        """
        inputs = {"messages": [HumanMessage(content=user_message)]}
        final_text = ""

        for mode, chunk in self.agent.stream(inputs, config=self.config, stream_mode=["updates", "messages"]):
            if mode == "messages":
                # chunk 是 (message_chunk, metadata)
                msg_chunk, _meta = chunk
                # 只取模型自己产出的文本，过滤 ToolMessage，避免工具原始结果被展示给用户
                if isinstance(msg_chunk, AIMessageChunk) and msg_chunk.content:
                    final_text += msg_chunk.content
                    yield ("token", msg_chunk.content)
            elif mode == "updates":
                # 节点更新：可能是 tool 调用或 agent 最终回复
                for node_name, node_output in chunk.items():
                    if node_name == "tools":
                        tool_msgs = node_output.get("messages", [])
                        for tm in tool_msgs:
                            tool_name = getattr(tm, "name", None) or "工具"
                            yield ("tool_event", f"🔧 已调用工具: {tool_name}")
                    # agent 节点的最终消息在 messages stream 里已经逐 token 产出

        yield ("done", final_text)

    def get_history(self):
        """获取当前会话的消息历史（从 checkpointer 读）。"""
        state = self.agent.get_state(self.config)
        return state.messages if state else []
