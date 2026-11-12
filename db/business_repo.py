"""
业务数据访问层（Repository）

所有 SQL 均使用参数化占位符，避免注入；查询结果统一转成 dict 供 tools 层格式化。

三张表的关键字关联：
    orders.product_sku   ->  inventory.sku
    orders.tracking_no   ->  shipments.tracking_no
    shipments.order_no   ->  orders.order_no
"""
import json
import threading
from datetime import datetime

from db.connection import get_business_conn

_WRITE_LOCK = threading.Lock()

# 有物流轨迹的订单状态
SHIPPED_STATUS = ("已发货", "运输中", "待收货", "已完成", "退款中")
# 不可申请退款的状态
NO_REFUND_STATUS = ("待付款", "待发货", "已取消")


def _row_to_dict(row):
    return dict(row) if row is not None else None


def get_order_detail(order_no: str):
    """
    查询订单详情，并通过 tracking_no 关联物流表、通过 product_sku 关联库存表。

    Returns:
        dict 或 None
    """
    sql = """
        SELECT o.order_no, o.user_id, o.product_sku, o.product_name, o.spec,
               o.quantity, o.amount, o.status, o.tracking_no, o.receiver_name,
               o.receiver_phone, o.receiver_addr, o.refund_status,
               o.create_time, o.pay_time, o.ship_time, o.finish_time, o.remark,
               s.carrier, s.carrier_code, s.status AS logistics_status,
               s.current_city, s.last_update AS logistics_update, s.sign_time,
               s.track_detail,
               i.stock, i.warehouse, i.restock_eta, i.price AS current_price
        FROM orders o
        LEFT JOIN shipments s ON o.tracking_no = s.tracking_no
        LEFT JOIN inventory i ON o.product_sku = i.sku
        WHERE o.order_no = ?
    """
    conn = get_business_conn()
    row = conn.execute(sql, (order_no,)).fetchone()
    return _row_to_dict(row)


def get_shipment(tracking_no: str):
    """根据物流单号查询物流信息（并反查所属订单）"""
    sql = """
        SELECT s.tracking_no, s.order_no, s.carrier, s.carrier_code, s.status,
               s.current_city, s.sender_city, s.receiver_city, s.track_detail,
               s.last_update, s.sign_time,
               o.product_name, o.status AS order_status, o.receiver_name, o.receiver_addr
        FROM shipments s
        LEFT JOIN orders o ON s.order_no = o.order_no
        WHERE s.tracking_no = ?
    """
    conn = get_business_conn()
    row = conn.execute(sql, (tracking_no,)).fetchone()
    return _row_to_dict(row)


def get_shipment_by_order(order_no: str):
    """根据订单号查询物流信息（物流表 order_no 关键字关联）"""
    sql = """
        SELECT s.tracking_no, s.order_no, s.carrier, s.status, s.current_city,
               s.track_detail, s.last_update, s.sign_time,
               o.product_name, o.status AS order_status
        FROM shipments s
        LEFT JOIN orders o ON s.order_no = o.order_no
        WHERE s.order_no = ?
    """
    conn = get_business_conn()
    row = conn.execute(sql, (order_no,)).fetchone()
    return _row_to_dict(row)


def search_inventory(keyword: str, limit: int = 3) -> list:
    """
    按商品名称 / SKU 模糊查询库存，有货的排在前面。

    Returns:
        list[dict]
    """
    like = f"%{keyword}%"
    sql = """
        SELECT sku, product_name, category, spec, price, stock,
               safety_stock, warehouse, restock_eta, update_time
        FROM inventory
        WHERE product_name LIKE ? OR sku LIKE ?
        ORDER BY CASE WHEN stock > 0 THEN 0 ELSE 1 END, price ASC
        LIMIT ?
    """
    conn = get_business_conn()
    rows = conn.execute(sql, (like, like, limit)).fetchall()
    return [dict(r) for r in rows]


def list_inventory_by_category(category: str, limit: int = 5) -> list:
    """按类目列商品（供「有哪些商品」类问题使用）"""
    conn = get_business_conn()
    rows = conn.execute(
        """SELECT sku, product_name, spec, price, stock
           FROM inventory WHERE category = ?
           ORDER BY stock DESC LIMIT ?""",
        (category, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def submit_refund(order_no: str, reason: str) -> dict:
    """
    提交退款申请：真实更新订单表（status / refund_status / remark）。

    业务规则：
        - 待付款 / 待发货 / 已取消  -> 不可退款
        - 退款中（已有申请）        -> 不重复提交
        - 已完成                    -> 走售后流程，订单状态不变
        - 已发货 / 运输中 / 待收货  -> 订单状态改为「退款中」，等待仓库拦截

    Returns:
        {"ok": bool, "message": str, ...}
    """
    order = get_order_detail(order_no)
    if not order:
        return {"ok": False, "message": f"未找到订单 {order_no}"}

    if order["refund_status"] == "审核中" or order["status"] == "退款中":
        return {"ok": False, "order_no": order_no,
                "message": f"订单 {order_no} 已有退款申请正在审核中，无需重复提交。"}

    if order["status"] in NO_REFUND_STATUS:
        return {"ok": False, "order_no": order_no,
                "message": f"订单 {order_no} 当前状态为「{order['status']}」，不支持申请退款。"}

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_before = order["status"]
    status_after = status_before if status_before == "已完成" else "退款中"
    remark = f"[{now}] 退款申请：{reason}"

    with _WRITE_LOCK:
        conn = get_business_conn()
        conn.execute(
            "UPDATE orders SET status = ?, refund_status = '审核中', remark = ? WHERE order_no = ?",
            (status_after, remark, order_no),
        )
        conn.commit()

    return {
        "ok": True,
        "order_no": order_no,
        "product_name": order["product_name"],
        "amount": order["amount"],
        "status_before": status_before,
        "status_after": status_after,
        "reason": reason,
        "eta": "1-3 个工作日",
        "is_aftersale": status_before == "已完成",
    }


def parse_tracks(track_detail) -> list:
    """把 track_detail 的 JSON 字符串解析成列表"""
    if not track_detail:
        return []
    try:
        return json.loads(track_detail)
    except (json.JSONDecodeError, TypeError):
        return []


def get_stats() -> dict:
    """三表数据量统计（侧边栏展示用）"""
    conn = get_business_conn()
    stats = {}
    for table in ("orders", "shipments", "inventory"):
        stats[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return stats
