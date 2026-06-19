import os
from datetime import date, timedelta

from app.data.db import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    tier TEXT NOT NULL DEFAULT 'standard',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    item_name TEXT NOT NULL,
    category TEXT NOT NULL,
    amount REAL NOT NULL,
    status TEXT NOT NULL,
    order_date TEXT NOT NULL,
    delivered_date TEXT,
    is_final_sale INTEGER NOT NULL DEFAULT 0,
    is_refunded INTEGER NOT NULL DEFAULT 0,
    refund_date TEXT
);
CREATE TABLE IF NOT EXISTS refunds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    amount REAL NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    customer_id INTEGER,
    customer_name TEXT,
    timestamp TEXT NOT NULL,
    user_message TEXT NOT NULL,
    decision TEXT,
    total_tokens_in INTEGER NOT NULL,
    total_tokens_out INTEGER NOT NULL,
    total_cost_usd REAL NOT NULL,
    total_latency_ms INTEGER NOT NULL,
    step_count INTEGER NOT NULL,
    steps_json TEXT NOT NULL
);
"""


def _ago(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


# 15 customers (id, name, email, tier)
CUSTOMERS = [
    (1, "Alice Tan", "alice@example.com", "standard"),
    (2, "Bob Reyes", "bob@example.com", "premium"),
    (3, "Carla Mendes", "carla@example.com", "standard"),
    (4, "Derek Owusu", "derek@example.com", "standard"),
    (5, "Elena Petrova", "elena@example.com", "premium"),
    (6, "Farid Haddad", "farid@example.com", "standard"),
    (7, "Grace Kim", "grace@example.com", "standard"),
    (8, "Hiro Tanaka", "hiro@example.com", "premium"),
    (9, "Ines Costa", "ines@example.com", "standard"),
    (10, "Jamal Brooks", "jamal@example.com", "standard"),
    (11, "Keiko Mori", "keiko@example.com", "standard"),
    (12, "Liam Walsh", "liam@example.com", "premium"),
    (13, "Mara Singh", "mara@example.com", "standard"),
    (14, "Noah Klein", "noah@example.com", "standard"),
    (15, "Olivia Park", "olivia@example.com", "standard"),
]

# orders: (id, customer_id, item_name, category, amount, status,
#          order_date, delivered_date, is_final_sale, is_refunded, refund_date)
# Branch coverage is engineered: clean / final-sale / over-$500 / outside-window /
# already-refunded / processing / shipped / cancelled.
ORDERS = [
    # Alice (1): clean refundable + final sale
    (1001, 1, "Wireless Earbuds", "electronics", 79.99, "delivered", _ago(14), _ago(10), 0, 0, None),
    (1002, 1, "Clearance Hoodie", "apparel", 24.99, "delivered", _ago(20), _ago(15), 1, 0, None),
    # Bob (2): over-threshold (escalate) + clean
    (1003, 2, "4K OLED TV", "electronics", 899.00, "delivered", _ago(12), _ago(8), 0, 0, None),
    (1004, 2, "HDMI Cable", "electronics", 14.50, "delivered", _ago(9), _ago(6), 0, 0, None),
    # Carla (3): outside window + already refunded
    (1005, 3, "Running Shoes", "apparel", 110.00, "delivered", _ago(70), _ago(60), 0, 0, None),
    (1006, 3, "Yoga Mat", "fitness", 39.00, "delivered", _ago(40), _ago(35), 0, 1, _ago(20)),
    # Derek (4): processing + clean
    (1007, 4, "Standing Desk", "furniture", 320.00, "processing", _ago(3), None, 0, 0, None),
    (1008, 4, "Desk Lamp", "furniture", 45.00, "delivered", _ago(11), _ago(7), 0, 0, None),
    # Elena (5): over-threshold + final sale
    (1009, 5, "Espresso Machine", "kitchen", 640.00, "delivered", _ago(13), _ago(9), 0, 0, None),
    (1010, 5, "Final-Sale Knife Set", "kitchen", 89.00, "delivered", _ago(18), _ago(12), 1, 0, None),
    # Farid (6): shipped (not delivered) + clean
    (1011, 6, "Bluetooth Speaker", "electronics", 59.00, "shipped", _ago(4), None, 0, 0, None),
    (1012, 6, "Phone Case", "electronics", 19.99, "delivered", _ago(16), _ago(12), 0, 0, None),
    # Grace (7): cancelled + clean
    (1013, 7, "Winter Coat", "apparel", 180.00, "cancelled", _ago(8), None, 0, 0, None),
    (1014, 7, "Wool Scarf", "apparel", 35.00, "delivered", _ago(10), _ago(6), 0, 0, None),
    # Hiro (8): clean + already refunded
    (1015, 8, "Gaming Laptop", "electronics", 1450.00, "delivered", _ago(15), _ago(11), 0, 0, None),
    (1016, 8, "Mechanical Keyboard", "electronics", 120.00, "delivered", _ago(30), _ago(25), 0, 1, _ago(12)),
    # Ines (9): clean + outside window
    (1017, 9, "Cookware Set", "kitchen", 210.00, "delivered", _ago(13), _ago(9), 0, 0, None),
    (1018, 9, "Blender", "kitchen", 75.00, "delivered", _ago(80), _ago(72), 0, 0, None),
    # Jamal (10): final sale + clean
    (1019, 10, "Clearance Sneakers", "apparel", 49.99, "delivered", _ago(17), _ago(13), 1, 0, None),
    (1020, 10, "Socks 5-Pack", "apparel", 12.00, "delivered", _ago(9), _ago(5), 0, 0, None),
    # Keiko (11): over-threshold + clean
    (1021, 11, "Road Bike", "fitness", 720.00, "delivered", _ago(14), _ago(10), 0, 0, None),
    (1022, 11, "Water Bottle", "fitness", 18.00, "delivered", _ago(8), _ago(4), 0, 0, None),
    # Liam (12): clean + processing
    (1023, 12, "Office Chair", "furniture", 260.00, "delivered", _ago(12), _ago(8), 0, 0, None),
    (1024, 12, "Monitor Arm", "furniture", 65.00, "processing", _ago(2), None, 0, 0, None),
    # Mara (13): outside window + final sale
    (1025, 13, "Sandals", "apparel", 42.00, "delivered", _ago(95), _ago(88), 0, 0, None),
    (1026, 13, "Final-Sale Dress", "apparel", 70.00, "delivered", _ago(15), _ago(11), 1, 0, None),
    # Noah (14): clean + already refunded
    (1027, 14, "Headphones", "electronics", 199.00, "delivered", _ago(11), _ago(7), 0, 0, None),
    (1028, 14, "USB-C Charger", "electronics", 29.00, "delivered", _ago(25), _ago(20), 0, 1, _ago(9)),
    # Olivia (15): clean + shipped
    (1029, 15, "Backpack", "apparel", 85.00, "delivered", _ago(10), _ago(6), 0, 0, None),
    (1030, 15, "Travel Pillow", "apparel", 22.00, "shipped", _ago(3), None, 0, 0, None),
]


def create_schema(conn) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def seed_data(conn) -> None:
    now = date.today().isoformat()
    conn.executemany(
        "INSERT INTO customers (id, name, email, tier, created_at) VALUES (?, ?, ?, ?, ?)",
        [(cid, name, email, tier, now) for (cid, name, email, tier) in CUSTOMERS],
    )
    conn.executemany(
        """INSERT INTO orders
           (id, customer_id, item_name, category, amount, status,
            order_date, delivered_date, is_final_sale, is_refunded, refund_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ORDERS,
    )
    conn.commit()


def ensure_seeded(db_path: str) -> None:
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = connect(db_path)
    create_schema(conn)
    already = conn.execute("SELECT COUNT(*) AS c FROM customers").fetchone()["c"]
    if already == 0:
        seed_data(conn)
    conn.close()
