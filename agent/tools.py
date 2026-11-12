"""
Agent 可调用的工具集：

- search_knowledge_base : RAG 知识库检索（退换货政策、运费规则、会员权益等静态规则）
- query_order           : 查询订单状态（SQLite orders 表）
- query_logistics       : 查询物流轨迹（SQLite shipments 表，支持传物流单号或订单号）
- apply_refund          : 提交退款申请（真实 UPDATE orders 表，非纯文本返回）
- check_product_stock   : 查询商品库存（SQLite inventory 表，按名称/SKU 模糊检索）

数据源说明：
    订单 / 物流 / 库存来自本地 SQLite 数据库 data/ecommerce.db，
    schema 见 data/schema.sql，造数脚本见 db/seed_mock_data.py。
    三表通过 order_no / tracking_no / sku 三个关键字关联。

为什么工具要从数据库而不是字典取数：
    字典是硬编码的，改一条数据要改代码；换成 SQLite 后，
    数据与代码解耦，且能演示参数化查询、多表 JOIN、写操作事务等真实数据访问路径。
"""
from langchain_core.tools import tool

from db.business_repo import (
    get_order_detail,
    get_shipment,
    get_shipment_by_order,
    search_inventory,
    submit_refund,
)
from rag.vector_store import similarity_search


# ==================== 工具定义 ====================

@tool
def search_knowledge_base(query: str) -> str:
    """
    搜索商城官方知识库，用于回答平台规则类问题：退换货政策、运费规则、保修政策、
    会员权益、发票规则等。凡涉及"政策""规则""多久能退""运费谁出"等问题，必须先调用此工具。

    Args:
        query: 用户的问题，用一句完整的话描述。
    """
    try:
        docs = similarity_search(query, k=4)
        if not docs:
            return "知识库中未找到相关内容。"
        blocks = []
        for i, d in enumerate(docs, 1):
            blocks.append(f"【片段{i}】来源: {d.metadata.get('source', '未知')}\n{d.page_content}")
        return "\n\n".join(blocks)
    except Exception as e:
        return f"知识库检索失败: {e}"


@tool
def query_order(order_id: str) -> str:
    """
    根据订单号查询订单状态、商品、金额、收货信息，并返回关联的物流单号与承运商。
    用户提到订单、买了什么、发货没、订单状态、订单金额时调用。订单号通常以 SO 开头。

    Args:
        order_id: 订单号，例如 SO20261101001
    """
    order_id = (order_id or "").strip().upper()
    if not order_id:
        return "请提供订单号（通常以 SO 开头）。"

    order = get_order_detail(order_id)
    if not order:
        return f"未找到订单 {order_id}，请核对订单号是否正确（通常以 SO 开头）。"

    lines = [
        f"订单号: {order['order_no']}",
        f"商品: {order['product_name']}（{order['spec'] or '默认规格'}）",
        f"数量: {order['quantity']}",
        f"金额: ¥{order['amount']:.2f}",
        f"订单状态: {order['status']}",
        f"退款状态: {order['refund_status'] or '无'}",
        f"下单时间: {order['create_time']}",
    ]
    if order.get("receiver_name"):
        lines.append(f"收货人: {order['receiver_name']} {order.get('receiver_phone') or ''}".strip())
    if order.get("receiver_addr"):
        lines.append(f"收货地址: {order['receiver_addr']}")

    if order.get("tracking_no"):
        lines.append(f"物流单号: {order['tracking_no']}")
        lines.append(f"承运商: {order.get('carrier') or '未知'}")
        lines.append(f"物流状态: {order.get('logistics_status') or '暂无'}")
        if order.get("current_city"):
            lines.append(f"当前位置: {order['current_city']}")
    else:
        lines.append("物流单号: 暂未发货")

    return "\n".join(lines)


@tool
def query_logistics(logistics_no: str) -> str:
    """
    查询物流轨迹。可以传物流单号（如 SF1234567890），也可以直接传订单号（如 SO20261101001），
    传订单号时会自动通过订单表关联到对应物流单。用户问"到哪了""什么时候送到"时调用。

    Args:
        logistics_no: 物流单号或订单号
    """
    key = (logistics_no or "").strip().upper()
    if not key:
        return "请提供物流单号或订单号。"

    if key.startswith("SO"):
        shipment = get_shipment_by_order(key)
    else:
        shipment = get_shipment(key)

    if not shipment:
        return f"未查询到 {key} 对应的物流信息，请确认物流单号或订单号是否正确。"

    header = [
        f"物流单号: {shipment['tracking_no']}",
        f"关联订单: {shipment['order_no']}（{shipment.get('product_name') or '未知商品'}）",
        f"承运商: {shipment.get('carrier') or '未知'}",
        f"物流状态: {shipment['status']}",
    ]
    if shipment.get("current_city"):
        header.append(f"当前位置: {shipment['current_city']}")

    tracks = shipment.get("track_detail")
    if isinstance(tracks, str):
        try:
            import json
            tracks = json.loads(tracks)
        except (json.JSONDecodeError, TypeError):
            tracks = []

    if not tracks:
        header.append("暂无轨迹明细。")
        return "\n".join(header)

    header.append(f"最新轨迹（共 {len(tracks)} 条，从新到旧）:")
    for i, t in enumerate(reversed(tracks), 1):
        header.append(f"  {i}. {t.get('time', '')}  {t.get('desc', '')}")

    return "\n".join(header)


@tool
def apply_refund(order_id: str, reason: str) -> str:
    """
    为指定订单提交退款申请（会真实写入订单表，改变订单状态）。
    用户明确要求"退货""退款""不想要了""申请售后"时调用。

    Args:
        order_id: 要退款的订单号，例如 SO20261101001
        reason: 退款原因，例如"七天无理由""商品质量问题"
    """
    order_id = (order_id or "").strip().upper()
    reason = (reason or "未说明原因").strip()
    if not order_id:
        return "请提供需要退款的订单号。"

    result = submit_refund(order_id, reason)

    if not result.get("ok"):
        return f"退款未提交：{result['message']}"

    if result.get("is_aftersale"):
        return (
            f"已为订单 {result['order_no']} 提交售后申请。\n"
            f"商品: {result['product_name']}\n"
            f"金额: ¥{result['amount']:.2f}\n"
            f"退款原因: {result['reason']}\n"
            f"说明: 该订单已完成，已转入售后流程，客服将在 {result['eta']}内联系您确认退回事宜。"
        )

    return (
        f"退款申请已提交成功。\n"
        f"订单号: {result['order_no']}\n"
        f"商品: {result['product_name']}\n"
        f"金额: ¥{result['amount']:.2f}\n"
        f"退款原因: {result['reason']}\n"
        f"订单状态: {result['status_before']} → {result['status_after']}\n"
        f"说明: 仓库拦截成功后将原路退款，预计 {result['eta']}到账。"
    )


@tool
def check_product_stock(product_name: str) -> str:
    """
    查询商品库存、价格、规格、所在仓库。用户问"有没有货""还有库存吗""多少钱""什么时候到货"时调用。
    支持模糊查询，传商品名或 SKU 都可以。

    Args:
        product_name: 商品名称或 SKU，例如"降噪耳机 Pro"、"SKU-DIG-0001-BK"
    """
    keyword = (product_name or "").strip()
    if not keyword:
        return "请提供商品名称。"

    items = search_inventory(keyword, limit=3)
    if not items:
        return f"未找到商品「{keyword}」，请确认商品名称或 SKU。"

    lines = [f"「{keyword}」共匹配到 {len(items)} 个 SKU："]
    for i, it in enumerate(items, 1):
        stock_text = f"库存 {it['stock']} 件"
        if it["stock"] == 0:
            stock_text += f"（缺货，预计 {it['restock_eta'] or '待定'} 到货）"
        elif it["stock"] <= it["safety_stock"]:
            stock_text += "（库存紧张）"
        lines.append(
            f"{i}. {it['sku']}｜{it['product_name']}｜{it['spec']}｜"
            f"¥{it['price']:.2f}｜{stock_text}｜{it['warehouse']}"
        )

    lines.append("如需下单请告知具体规格。")
    return "\n".join(lines)


# 工具列表，供 Agent 初始化时传入
ALL_TOOLS = [
    search_knowledge_base,
    query_order,
    query_logistics,
    apply_refund,
    check_product_stock,
]
