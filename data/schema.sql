-- ================================================================
-- 星辰商城 · 业务模拟数据库 Schema（SQLite）
-- ----------------------------------------------------------------
-- 三张核心表：订单状态 / 快递物流 / 商品库存
--
-- 关键字关联关系（面试时可重点讲）：
--   orders.product_sku   -->  inventory.sku          （商品维度）
--   orders.tracking_no   -->  shipments.tracking_no  （订单查物流）
--   shipments.order_no   -->  orders.order_no        （物流反查订单）
--   orders.order_no 为订单主键，shipments 通过 order_no 与订单一对一挂接
-- ================================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------
-- 表 1：订单状态表 orders
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no        TEXT    NOT NULL UNIQUE,           -- 订单号，主键标识，如 SO20261112001
    user_id         TEXT    NOT NULL,                  -- 下单用户 ID
    product_sku     TEXT    NOT NULL,                  -- 商品 SKU，关联 inventory.sku
    product_name    TEXT    NOT NULL,                  -- 商品名称（冗余字段，便于直接展示）
    spec            TEXT,                              -- 规格 / 颜色
    quantity        INTEGER NOT NULL DEFAULT 1,        -- 购买数量
    amount          REAL    NOT NULL,                  -- 订单实付金额（元）
    status          TEXT    NOT NULL,                  -- 订单状态：待付款/待发货/已发货/运输中/待收货/已完成/已取消/退款中
    tracking_no     TEXT,                              -- 物流单号，关联 shipments.tracking_no（未发货为空）
    receiver_name   TEXT,                              -- 收货人
    receiver_phone  TEXT,                              -- 收货电话（脱敏展示）
    receiver_addr   TEXT,                              -- 收货地址
    refund_status   TEXT    NOT NULL DEFAULT '无',      -- 退款状态：无/审核中/已退款（apply_refund 工具会更新）
    create_time     TEXT    NOT NULL,                  -- 下单时间
    pay_time        TEXT,                              -- 付款时间
    ship_time       TEXT,                              -- 发货时间
    finish_time     TEXT,                              -- 完成时间
    remark          TEXT                               -- 备注
);

CREATE INDEX IF NOT EXISTS idx_orders_sku        ON orders(product_sku);
CREATE INDEX IF NOT EXISTS idx_orders_status     ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_user       ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_tracking   ON orders(tracking_no);
CREATE INDEX IF NOT EXISTS idx_orders_create_time ON orders(create_time);

-- ----------------------------------------------------------------
-- 表 2：快递物流表 shipments
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shipments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tracking_no     TEXT    NOT NULL UNIQUE,           -- 物流单号，如 SF1234567890123
    order_no        TEXT    NOT NULL,                  -- 关联订单号，关联 orders.order_no
    carrier         TEXT    NOT NULL,                  -- 承运商：顺丰速运/圆通速递/中通快递/京东物流
    carrier_code    TEXT    NOT NULL,                  -- 承运商代码：SF/YTO/ZTO/JD
    status          TEXT    NOT NULL,                  -- 物流状态：已揽收/运输中/派送中/已签收
    current_city    TEXT,                              -- 当前所在城市
    sender_city     TEXT,                              -- 发货城市
    receiver_city   TEXT,                              -- 收货城市
    track_detail    TEXT,                              -- 轨迹明细（JSON 数组字符串：[{"time":"...","desc":"..."}]）
    last_update     TEXT,                              -- 最后更新时间
    sign_time       TEXT,                              -- 签收时间
    FOREIGN KEY (order_no) REFERENCES orders(order_no)
);

CREATE INDEX IF NOT EXISTS idx_shipments_order    ON shipments(order_no);
CREATE INDEX IF NOT EXISTS idx_shipments_carrier  ON shipments(carrier_code);
CREATE INDEX IF NOT EXISTS idx_shipments_status   ON shipments(status);

-- ----------------------------------------------------------------
-- 表 3：商品库存表 inventory
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inventory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sku             TEXT    NOT NULL UNIQUE,           -- 商品 SKU，关联 orders.product_sku
    product_name    TEXT    NOT NULL,                  -- 商品名称
    category        TEXT    NOT NULL,                  -- 类目：数码配件/智能穿戴/家居生活/个护健康
    spec            TEXT,                              -- 规格 / 颜色
    price           REAL    NOT NULL,                  -- 售价（元）
    stock           INTEGER NOT NULL DEFAULT 0,        -- 可用库存
    safety_stock    INTEGER NOT NULL DEFAULT 5,        -- 安全库存阈值
    warehouse       TEXT,                              -- 所在仓库
    restock_eta     TEXT,                              -- 补货预计到货时间（缺货时展示）
    update_time     TEXT                               -- 库存更新时间
);

CREATE INDEX IF NOT EXISTS idx_inventory_name     ON inventory(product_name);
CREATE INDEX IF NOT EXISTS idx_inventory_category ON inventory(category);
CREATE INDEX IF NOT EXISTS idx_inventory_stock    ON inventory(stock);
