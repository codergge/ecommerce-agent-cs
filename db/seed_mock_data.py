"""
生成「星辰商城」业务模拟数据库（SQLite）

三张表：
    orders     订单状态表   120 条
    shipments  快递物流表   110 条
    inventory  商品库存表   120 条

关联关键字：
    orders.product_sku  -> inventory.sku         商品维度关联
    orders.tracking_no  -> shipments.tracking_no  订单查物流
    shipments.order_no  -> orders.order_no        物流反查订单

用法：
    python scripts/init_mock_db.py            # 首次生成（已存在则跳过）
    python scripts/init_mock_db.py --rebuild  # 删库重建（改了数据逻辑时用）

生成产物：
    data/ecommerce.db      SQLite 数据库文件（已在 .gitignore 中忽略）
    data/seed_data.sql     纯 INSERT 语句，可用 Navicat / DB Browser 直接导入查看
"""
import argparse
import json
import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta

# 固定随机种子：保证每次生成的数据一致，方便演示和截图复现
SEED = 20261112
# 基准"今天"，用于生成相对时间
TODAY = datetime(2026, 11, 11, 20, 0, 0)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SCHEMA_PATH = os.path.join(DATA_DIR, "schema.sql")
DB_PATH = os.path.join(DATA_DIR, "ecommerce.db")
SEED_SQL_PATH = os.path.join(DATA_DIR, "seed_data.sql")


# ==================== 商品池：30 个商品 × 4 规格 = 120 个 SKU ====================
PRODUCT_POOL = [
    ("降噪耳机 Pro",   "数码配件", 299.00),
    ("智能手表 S2",    "智能穿戴", 1299.00),
    ("手机壳",         "数码配件", 89.90),
    ("快充充电器 65W", "数码配件", 129.00),
    ("蓝牙音箱 Mini",  "数码配件", 199.00),
    ("机械键盘 K87",   "数码配件", 399.00),
    ("无线鼠标 M3",    "数码配件", 99.00),
    ("移动电源 20000mAh", "数码配件", 159.00),
    ("数据线 Type-C",  "数码配件", 39.90),
    ("屏幕保护膜",     "数码配件", 29.90),
    ("笔记本支架",     "数码配件", 119.00),
    ("USB-C 扩展坞",   "数码配件", 259.00),
    ("智能台灯",       "家居生活", 189.00),
    ("电动牙刷",       "个护健康", 269.00),
    ("保温杯",         "家居生活", 129.00),
    ("双肩背包",       "家居生活", 239.00),
    ("瑜伽垫",         "家居生活", 89.00),
    ("运动水壶",       "家居生活", 69.00),
    ("空气净化器",     "家居生活", 899.00),
    ("扫地机器人",     "家居生活", 1899.00),
    ("电饭煲",         "家居生活", 399.00),
    ("咖啡机",         "家居生活", 699.00),
    ("吹风机",         "个护健康", 299.00),
    ("剃须刀",         "个护健康", 399.00),
    ("加湿器",         "家居生活", 199.00),
    ("电热毯",         "家居生活", 159.00),
    ("蓝牙耳机 Air",   "数码配件", 499.00),
    ("平板保护套",     "数码配件", 129.00),
    ("触控笔",         "数码配件", 199.00),
    ("摄像头 4K",      "数码配件", 399.00),
]

COLORS = [
    ("星空黑", "BK", 0.0),
    ("钛银",   "SV", 30.0),
    ("冰川白", "WH", 0.0),
    ("深空蓝", "BL", 50.0),
]

CATEGORY_CODE = {
    "数码配件": "DIG",
    "智能穿戴": "WEA",
    "家居生活": "HOM",
    "个护健康": "CAR",
}

CARRIERS = [
    ("顺丰速运", "SF"),
    ("圆通速递", "YTO"),
    ("中通快递", "ZTO"),
    ("京东物流", "JD"),
]

WAREHOUSES = ["长沙仓", "杭州仓", "深圳仓", "武汉仓"]

CITIES = ["长沙市", "杭州市", "深圳市", "上海市", "北京市", "广州市", "武汉市", "成都市"]

# 每个城市对应的行政区，保证「市 + 区」搭配真实
DISTRICTS = {
    "长沙市": ["雨花区", "岳麓区", "芙蓉区", "天心区"],
    "杭州市": ["西湖区", "滨江区", "余杭区"],
    "深圳市": ["南山区", "福田区", "宝安区"],
    "上海市": ["浦东新区", "徐汇区", "静安区"],
    "北京市": ["朝阳区", "海淀区", "丰台区"],
    "广州市": ["天河区", "越秀区", "番禺区"],
    "武汉市": ["洪山区", "江汉区", "武昌区"],
    "成都市": ["武侯区", "锦江区", "高新区"],
}

# 物流单号前缀 -> 承运商，保证「单号前缀」与「承运商名称」一致
CARRIER_BY_PREFIX = {
    "SF": ("顺丰速运", "SF"),
    "YT": ("圆通速递", "YTO"),
    "ZT": ("中通快递", "ZTO"),
    "JD": ("京东物流", "JD"),
}

SURNAMES = ["张", "李", "王", "刘", "陈", "杨", "赵", "黄", "周", "吴", "徐", "孙", "马", "朱", "胡"]
GIVEN_NAMES = ["伟", "芳", "娜", "敏", "静", "磊", "洋", "艳", "勇", "军", "杰", "娟", "涛", "明", "超", "秀英"]

USER_IDS = [f"U{10001 + i}" for i in range(60)]


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _phone(rng: random.Random) -> str:
    return f"1{rng.choice(['3', '5', '7', '8'])}{rng.randint(0, 9)}****{rng.randint(1000, 9999)}"


# ==================== 1. 库存表 ====================
def build_inventory(rng: random.Random) -> list:
    rows = []
    seq = 0
    for name, category, base_price in PRODUCT_POOL:
        for color_name, color_code, extra in COLORS:
            seq += 1
            sku = f"SKU-{CATEGORY_CODE[category]}-{seq:04d}-{color_code}"
            price = round(base_price + extra, 2)

            # 约 15% 的 SKU 缺货，用于演示"无货"场景
            if rng.random() < 0.15:
                stock = 0
                eta = _fmt(TODAY + timedelta(days=rng.randint(2, 20)))[:10]
            else:
                stock = rng.randint(1, 500)
                eta = None

            rows.append({
                "sku": sku,
                "product_name": name,
                "category": category,
                "spec": color_name,
                "price": price,
                "stock": stock,
                "safety_stock": rng.choice([5, 10, 15, 20]),
                "warehouse": rng.choice(WAREHOUSES),
                "restock_eta": eta,
                "update_time": _fmt(TODAY - timedelta(hours=rng.randint(1, 72))),
            })
    return rows


# ==================== 2. 订单表 ====================
# 示意分布：已完成 45 / 待收货 25 / 运输中 20 / 已发货 20 / 待发货 5 / 待付款 3 / 已取消 1 / 退款中 1
STATUS_PLAN = (
    [("已完成", 45)] + [("待收货", 25)] + [("运输中", 20)] + [("已发货", 20)]
    + [("待发货", 5)] + [("待付款", 3)] + [("已取消", 1)] + [("退款中", 1)]
)

# 原来 demo 用的三个订单，保留下来，保证之前的演示脚本/面试话术仍可复用
FIXED_ORDERS = [
    {
        "order_no": "SO20261101001", "user_id": "U10001", "sku_keyword": "降噪耳机 Pro",
        "quantity": 1, "status": "已发货", "tracking_no": "SF1234567890",
        "receiver_name": "张伟", "create": datetime(2026, 11, 8, 9, 0, 0), "refund_status": "无",
    },
    {
        "order_no": "SO20261101002", "user_id": "U10002", "sku_keyword": "智能手表 S2",
        "quantity": 1, "status": "待收货", "tracking_no": "SF0987654321",
        "receiver_name": "李芳", "create": datetime(2026, 11, 7, 14, 20, 0), "refund_status": "无",
    },
    {
        "order_no": "SO20261101003", "user_id": "U10003", "sku_keyword": "手机壳",
        "quantity": 1, "status": "已完成", "tracking_no": "YT5555666677",
        "receiver_name": "王强", "create": datetime(2026, 10, 25, 20, 10, 0), "refund_status": "无",
    },
]


def _make_order(rng, order_no, status, inv, create_dt, refund_status, receiver=None, city=None):
    """按状态补全各时间节点，返回订单字典"""
    quantity = rng.choices([1, 1, 1, 2, 3], k=1)[0]
    amount = round(inv["price"] * quantity, 2)

    pay_dt = create_dt + timedelta(minutes=rng.randint(1, 30)) if status != "待付款" else None
    ship_dt = pay_dt + timedelta(hours=rng.randint(6, 30)) if status in (
        "已发货", "运输中", "待收货", "已完成", "退款中"
    ) else None
    finish_dt = ship_dt + timedelta(days=rng.randint(2, 5)) if status == "已完成" else None

    city = city or rng.choice(CITIES)
    name = receiver or (rng.choice(SURNAMES) + rng.choice(GIVEN_NAMES))

    return {
        "order_no": order_no,
        "user_id": rng.choice(USER_IDS),
        "product_sku": inv["sku"],
        "product_name": inv["product_name"],
        "spec": inv["spec"],
        "quantity": quantity,
        "amount": amount,
        "status": status,
        "tracking_no": None,          # 建物流时回填
        "receiver_name": name,
        "receiver_phone": _phone(rng),
        "receiver_addr": f"{city}{rng.choice(DISTRICTS.get(city, ['高新区']))}"
                         f"{rng.randint(1, 200)}号{rng.randint(1, 30)}栋{rng.randint(101, 2508)}室",
        "refund_status": refund_status,
        "create_time": _fmt(create_dt),
        "pay_time": _fmt(pay_dt) if pay_dt else None,
        "ship_time": _fmt(ship_dt) if ship_dt else None,
        "finish_time": _fmt(finish_dt) if finish_dt else None,
        "remark": None,
    }


def build_orders(rng: random.Random, inventory: list) -> list:
    by_name = {}
    for inv in inventory:
        by_name.setdefault(inv["product_name"], []).append(inv)

    orders = []

    # 1) 三个固定演示订单
    for fo in FIXED_ORDERS:
        inv_list = by_name[fo["sku_keyword"]]
        # 优先取「星空黑」规格，保证演示金额与最初版本一致（299 / 1299 / 89.90）
        inv = next((x for x in inv_list if x["spec"] == "星空黑"), inv_list[0])
        o = _make_order(rng, fo["order_no"], fo["status"], inv, fo["create"],
                        fo["refund_status"], receiver=fo["receiver_name"],
                        city="长沙市")
        o["quantity"] = fo["quantity"]
        o["amount"] = round(inv["price"] * fo["quantity"], 2)
        o["tracking_no"] = fo["tracking_no"]
        orders.append(o)

    # 2) 其余订单按状态分布随机生成
    # 记录每天的序号，保证订单号唯一；固定演示订单已占用 20261101 的 001~003
    counter = {"20261101": 3}
    need = 120 - len(orders)
    statuses = [s for s, n in STATUS_PLAN for _ in range(n)]
    # 固定订单已占了：已发货1、待收货1、已完成1
    for s in ("已发货", "待收货", "已完成"):
        if s in statuses:
            statuses.remove(s)
    statuses = statuses[:need]

    for i, status in enumerate(statuses, start=1):
        create_dt = TODAY - timedelta(
            days=rng.randint(0, 42), hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
        )
        dkey = create_dt.strftime("%Y%m%d")
        counter[dkey] = counter.get(dkey, 0) + 1
        order_no = f"SO{dkey}{counter[dkey]:03d}"

        inv = rng.choice(inventory)
        refund_status = "审核中" if status == "退款中" else "无"
        orders.append(_make_order(rng, order_no, status, inv, create_dt, refund_status))

    return orders


# ==================== 3. 物流表 ====================
TRACK_TEMPLATE = [
    ("发货城市", "商家已发货，包裹交由{}揽收"),
    ("转运中心", "快件已到达【{}转运中心】"),
    ("派送点",   "快件已到达【{}派送点】，准备派送"),
    ("派送中",   "快递员正在派送中，请保持电话畅通"),
    ("已签收",   "您的快件已签收，感谢使用{}，期待再次为您服务"),
]

LOGISTICS_STATUS_MAP = {
    "已发货": "已揽收",
    "运输中": "运输中",
    "待收货": "派送中",
    "已完成": "已签收",
    "退款中": "运输中",
}

# 固定演示单号直接指定物流状态，与轨迹内容保持一致
FIXED_SHIP_STATUS = {
    "SF1234567890": "派送中",
    "SF0987654321": "派送中",
    "YT5555666677": "已签收",
}


def build_shipments(rng: random.Random, orders: list) -> list:
    shipments = []
    fixed_tracks = {
        "SF1234567890": [
            ("2026-11-08 18:00:00", "【深圳市】顺丰速运 已收取快件"),
            ("2026-11-08 22:40:00", "快件已从【深圳转运中心】发出"),
            ("2026-11-09 22:10:00", "快件已到达【长沙雨花区派送点】"),
            ("2026-11-10 08:30:00", "快递员正在派送中，请保持电话畅通"),
        ],
        "SF0987654321": [
            ("2026-11-09 09:20:00", "【杭州市】顺丰速运 已收取快件"),
            ("2026-11-09 14:00:00", "快件已从【杭州仓】发出"),
            ("2026-11-10 06:50:00", "快件已到达【长沙转运中心】"),
            ("2026-11-10 15:10:00", "快件已到达【长沙雨花区派送点】"),
        ],
        "YT5555666677": [
            ("2026-10-26 10:00:00", "【杭州市】圆通速递 已收取快件"),
            ("2026-10-27 07:30:00", "快件已到达【杭州转运中心】"),
            ("2026-10-28 09:15:00", "快件已到达【长沙岳麓区派送点】"),
            ("2026-10-28 16:40:00", "您的快件已签收，感谢使用圆通速递"),
        ],
    }

    for order in orders:
        tracking_no = order["tracking_no"]

        lstatus = FIXED_SHIP_STATUS.get(tracking_no) if tracking_no else None
        lstatus = lstatus or LOGISTICS_STATUS_MAP.get(order["status"])
        if not lstatus:
            continue  # 待付款/待发货/已取消 没有物流

        if tracking_no:
            # 已有单号（固定演示订单）按前缀识别承运商，避免「圆通单号配顺丰」的矛盾
            carrier_name, carrier_code = CARRIER_BY_PREFIX.get(
                tracking_no[:2], rng.choice(CARRIERS)
            )
        else:
            carrier_name, carrier_code = rng.choice(CARRIERS)
            tracking_no = f"{carrier_code}{rng.randint(10 ** 11, 10 ** 12 - 1)}"
            order["tracking_no"] = tracking_no

        sender_city = rng.choice(["深圳市", "杭州市", "武汉市", "长沙市"])
        receiver_city = (order["receiver_addr"] or "长沙市")[:3]
        if receiver_city.startswith("长沙"):
            receiver_city = "长沙市"
        elif receiver_city.startswith("杭州"):
            receiver_city = "杭州市"

        # 轨迹明细
        if tracking_no in fixed_tracks:
            tracks = [{"time": t, "desc": d} for t, d in fixed_tracks[tracking_no]]
        else:
            ship_dt = datetime.strptime(order["ship_time"], "%Y-%m-%d %H:%M:%S")
            steps = {"已揽收": 1, "运输中": 2, "派送中": 3, "已签收": 4}[lstatus]
            tracks = []
            for i in range(steps):
                t = ship_dt + timedelta(hours=i * rng.randint(6, 14))
                desc = TRACK_TEMPLATE[i][1].format(
                    sender_city if i == 0 else (receiver_city if i >= 2 else rng.choice(CITIES))
                )
                if i == 4:
                    desc = desc.format(carrier_name)
                tracks.append({"time": _fmt(t), "desc": desc})
            if lstatus == "已签收":
                tracks.append({
                    "time": _fmt(ship_dt + timedelta(days=2)),
                    "desc": f"您的快件已签收，感谢使用{carrier_name}",
                })

        last_time = tracks[-1]["time"]
        sign_time = last_time if lstatus == "已签收" else None
        # 当前所在城市：已揽收=发货城市，派送中/已签收=收货城市，运输中=随机中转城市
        if lstatus == "已揽收":
            current_city = sender_city
        elif lstatus in ("派送中", "已签收"):
            current_city = receiver_city
        else:
            current_city = rng.choice(CITIES)

        shipments.append({
            "tracking_no": tracking_no,
            "order_no": order["order_no"],
            "carrier": carrier_name,
            "carrier_code": carrier_code,
            "status": lstatus,
            "current_city": current_city,
            "sender_city": sender_city,
            "receiver_city": receiver_city,
            "track_detail": json.dumps(tracks, ensure_ascii=False),
            "last_update": last_time,
            "sign_time": sign_time,
        })

    return shipments


# ==================== 写库 ====================
def _insert(conn, table, rows):
    if not rows:
        return 0
    cols = list(rows[0].keys())
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})"
    conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
    return len(rows)


def _sql_literal(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def dump_seed_sql(tables: dict):
    """导出纯 INSERT 语句，方便用 Navicat / DB Browser 直接查看或导入"""
    lines = [
        "-- ============================================================",
        "-- 星辰商城业务模拟数据（由 scripts/init_mock_db.py 自动生成）",
        "-- 表：orders / shipments / inventory",
        "-- 用法：sqlite3 ecommerce.db < seed_data.sql  或导入任意 SQLite 客户端",
        "-- ============================================================",
        "",
        "BEGIN TRANSACTION;",
        "",
    ]
    for table, rows in tables.items():
        if not rows:
            continue
        cols = list(rows[0].keys())
        lines.append(f"-- ---------- {table}：{len(rows)} 条 ----------")
        for r in rows:
            vals = ", ".join(_sql_literal(r[c]) for c in cols)
            lines.append(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({vals});")
        lines.append("")

    lines.append("COMMIT;")
    with open(SEED_SQL_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def create_database(rebuild: bool = False, verbose: bool = True) -> dict:
    """
    创建业务模拟数据库（供 db/connection.py 首次运行自动调用，也可手动执行）。

    Args:
        rebuild: True 则删除已有数据库重建
        verbose: 是否打印统计信息

    Returns:
        {"inventory": n, "orders": n, "shipments": n, "created": bool}
    """
    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError(f"找不到建表脚本: {SCHEMA_PATH}")

    if os.path.exists(DB_PATH):
        if not rebuild:
            if verbose:
                print(f"[INFO] 数据库已存在，跳过生成: {DB_PATH}")
            return {"inventory": None, "orders": None, "shipments": None, "created": False}
        os.remove(DB_PATH)
        if verbose:
            print(f"[INFO] 已删除旧数据库: {DB_PATH}")

    rng = random.Random(SEED)

    inventory = build_inventory(rng)
    orders = build_orders(rng, inventory)
    shipments = build_shipments(rng, orders)

    conn = sqlite3.connect(DB_PATH)
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

        n_inv = _insert(conn, "inventory", inventory)
        n_ord = _insert(conn, "orders", orders)
        n_ship = _insert(conn, "shipments", shipments)

        conn.commit()
    finally:
        conn.close()

    dump_seed_sql({"inventory": inventory, "orders": orders, "shipments": shipments})

    stats = {"inventory": n_inv, "orders": n_ord, "shipments": n_ship, "created": True}

    if verbose:
        print("=" * 58)
        print("  业务模拟数据库生成完成")
        print("=" * 58)
        print(f"  数据库文件 : {DB_PATH}")
        print(f"  INSERT 脚本: {SEED_SQL_PATH}")
        print(f"  inventory  : {n_inv} 条")
        print(f"  orders     : {n_ord} 条")
        print(f"  shipments  : {n_ship} 条")
        print("-" * 58)
        print("  关联示例：")
        print("    orders.product_sku  -> inventory.sku")
        print("    orders.tracking_no  -> shipments.tracking_no")
        print("    shipments.order_no  -> orders.order_no")
        print("=" * 58)

    return stats


def main():
    parser = argparse.ArgumentParser(description="生成电商业务模拟数据库（订单/物流/库存）")
    parser.add_argument("--rebuild", action="store_true", help="删库重建")
    args = parser.parse_args()

    stats = create_database(rebuild=args.rebuild)
    if not stats["created"]:
        print("       如需重建请加 --rebuild")


if __name__ == "__main__":
    main()
