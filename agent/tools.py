"""
Agent 可调用的工具集：
- search_knowledge_base : RAG 知识库检索（退换货政策、运费规则等）
- query_order           : 查询订单状态（这里用模拟数据，实际可替换为真实订单 API）
- query_logistics       : 查询物流轨迹
- apply_refund          : 提交退款申请
- check_product_stock  : 查询商品库存
"""
from typing import Optional

from langchain_core.tools import tool

from rag.vector_store import similarity_search


# ==================== 模拟业务数据库（实际项目替换为真实 API / DB） ====================
_MOCK_ORDERS = {
    "SO20261101001": {"status": "已发货", "amount": 299.00, "product": "降噪耳机 Pro", "logistics_no": "SF1234567890"},
    "SO20261101002": {"status": "待收货", "amount": 1299.00, "product": "智能手表 S2", "logistics_no": "SF0987654321"},
    "SO20261101003": {"status": "已完成", "amount": 89.90, "product": "手机壳", "logistics_no": "YT5555666677"},
}

_MOCK_LOGISTICS = {
    "SF1234567890": [
        "2026-11-08 10:20  已从深圳转运中心发出",
        "2026-11-09 22:10  已到达长沙雨花区派送点",
        "2026-11-10 08:30  快递员正在派送中，请保持电话畅通",
    ],
    "SF0987654321": [
        "2026-11-09 14:00  已从杭州仓发出",
        "2026-11-10 06:50  已到达长沙转运中心",
    ],
}

_MOCK_STOCK = {
    "降噪耳机 Pro": {"color": "星空黑", "stock": 23, "price": 299.00},
    "智能手表 S2": {"color": "钛银", "stock": 0, "price": 1299.00, "note": "预计11月15日到货"},
    "手机壳": {"color": "透明", "stock": 356, "price": 89.90},
}


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
    根据订单号查询订单状态、金额、商品等信息。用户提到订单、买了什么、发货没、
    订单状态时调用。订单号通常以 SO 开头。

    Args:
        order_id: 订单号，例如 SO20261101001
    """
    order = _MOCK_ORDERS.get(order_id)
    if not order:
        return f"未找到订单 {order_id}，请核对订单号是否正确（通常以 SO 开头）。"
    return (
        f"订单号: {order_id}\n"
        f"商品: {order['product']}\n"
        f"金额: ¥{order['amount']:.2f}\n"
        f"状态: {order['status']}\n"
        f"物流单号: {order['logistics_no']}"
    )


@tool
def query_logistics(logistics_no: str) -> str:
    """
    根据物流单号查询最新物流轨迹。

    Args:
        logistics_no: 物流单号，例如 SF1234567890
    """
    tracks = _MOCK_LOGISTICS.get(logistics_no)
    if not tracks:
        return f"未查询到物流单号 {logistics_no} 的轨迹，请确认单号是否正确。"
    return f"物流单号 {logistics_no} 最新轨迹:\n" + "\n".join(tracks)


@tool
def apply_refund(order_id: str, reason: str) -> str:
    """
    为指定订单提交退款申请。用户明确要求"退货""退款""不想要了"时调用。

    Args:
        order_id: 要退款的订单号
        reason: 退款原因，例如"七天无理由""商品质量问题"
    """
    order = _MOCK_ORDERS.get(order_id)
    if not order:
        return f"退款失败：未找到订单 {order_id}。"
    if order["status"] == "已完成":
        return f"订单 {order_id} 已完成，可申请售后退款。原因: {reason}。已提交，预计1-3个工作日审核。"
    return f"已为订单 {order_id} 提交退款申请（原因: {reason}），仓库拦截后将原路退款。"


@tool
def check_product_stock(product_name: str) -> str:
    """
    查询某商品的库存、颜色、价格。用户问"有没有货""库存""多少钱"时调用。

    Args:
        product_name: 商品名称，例如"降噪耳机 Pro"
    """
    info = _MOCK_STOCK.get(product_name)
    if not info:
        return f"未找到商品「{product_name}」，请确认商品名称。"
    stock_text = f"库存: {info['stock']} 件" + (f"（{info['note']}）" if info.get("note") else "")
    return f"商品: {product_name}\n规格: {info['color']}\n价格: ¥{info['price']:.2f}\n{stock_text}"


# 工具列表，供 Agent 初始化时传入
ALL_TOOLS = [
    search_knowledge_base,
    query_order,
    query_logistics,
    apply_refund,
    check_product_stock,
]
