import sqlite3
import hashlib
import secrets
import pandas as pd
from datetime import datetime, timedelta

DB_NAME = "shelfmind.db"

LOW_STOCK_THRESHOLD = 5  # units — below this, an item is flagged "Low Stock"
SESSION_LIFETIME_DAYS = 30


def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _clean_phone(phone_number):
    return (phone_number or "").replace("+91", "").replace(" ", "").replace("-", "").strip()


def _hash_pin(phone_number, pin):
    """PIN hash salted with the store's own phone number (unique per store)."""
    clean_phone = _clean_phone(phone_number)
    return hashlib.sha256(f"{clean_phone}:{pin}".encode("utf-8")).hexdigest()


def init_db():
    """Initializes tables for Shopkeepers, Inventory, Udhar Ledger, and Sessions."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Shopkeeper Accounts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shopkeepers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_name TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            phone_number TEXT UNIQUE NOT NULL,
            upi_id TEXT NOT NULL,
            pin_hash TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # Migration safety net: older DBs won't have pin_hash yet.
    cursor.execute("PRAGMA table_info(shopkeepers)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if "pin_hash" not in existing_cols:
        cursor.execute("ALTER TABLE shopkeepers ADD COLUMN pin_hash TEXT")

    # 2. Store Inventory
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_phone TEXT NOT NULL,
            item_name TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            wholesale_rate REAL NOT NULL DEFAULT 0.0,
            last_restocked TEXT NOT NULL,
            status TEXT DEFAULT 'Active',
            UNIQUE(store_phone, item_name)
        )
    """)

    # 3. Udhar / Credit Ledger
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS udhar_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_phone TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            amount REAL NOT NULL,
            items_note TEXT,
            credit_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT DEFAULT 'Pending'
        )
    """)

    # 4. Login Sessions (so we never put phone numbers or PINs in the URL)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            store_phone TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# --- SHOPKEEPER CRUD & AUTH ---
def register_shopkeeper(shop_name, owner_name, phone_number, upi_id, pin):
    conn = get_connection()
    cursor = conn.cursor()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    clean_phone = _clean_phone(phone_number)
    pin_hash = _hash_pin(clean_phone, pin)
    try:
        cursor.execute("""
            INSERT INTO shopkeepers (shop_name, owner_name, phone_number, upi_id, pin_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (shop_name.strip(), owner_name.strip(), clean_phone, upi_id.strip(), pin_hash, created_at))
        conn.commit()
        success, err = True, ""
    except sqlite3.IntegrityError:
        success, err = False, "This mobile number is already registered. Please log in instead."
    conn.close()
    return success, err


def get_shopkeeper(phone_number):
    """Public profile only — never returns the PIN hash."""
    conn = get_connection()
    cursor = conn.cursor()
    clean_phone = _clean_phone(phone_number)
    cursor.execute("SELECT shop_name, owner_name, phone_number, upi_id FROM shopkeepers WHERE phone_number = ?", (clean_phone,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"shop_name": row[0], "owner_name": row[1], "phone_number": row[2], "upi_id": row[3]}
    return None


def verify_login(phone_number, pin):
    """Checks phone + PIN together. Returns (profile_dict_or_None, error_message)."""
    conn = get_connection()
    cursor = conn.cursor()
    clean_phone = _clean_phone(phone_number)
    cursor.execute("SELECT shop_name, owner_name, phone_number, upi_id, pin_hash FROM shopkeepers WHERE phone_number = ?", (clean_phone,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None, "No store found with this mobile number. Please register first."

    shop_name, owner_name, stored_phone, upi_id, pin_hash = row

    if not pin_hash:
        # Legacy account created before PIN protection existed.
        return None, "LEGACY_NO_PIN"

    if _hash_pin(clean_phone, pin) != pin_hash:
        return None, "Incorrect PIN. Please try again."

    return {"shop_name": shop_name, "owner_name": owner_name, "phone_number": stored_phone, "upi_id": upi_id}, ""


def set_pin(phone_number, new_pin):
    """Used both for first-time PIN setup on legacy accounts and 'forgot PIN' resets."""
    conn = get_connection()
    cursor = conn.cursor()
    clean_phone = _clean_phone(phone_number)
    pin_hash = _hash_pin(clean_phone, new_pin)
    cursor.execute("UPDATE shopkeepers SET pin_hash = ? WHERE phone_number = ?", (pin_hash, clean_phone))
    conn.commit()
    conn.close()


def update_shopkeeper_profile(phone_number, new_shop_name, new_owner_name, new_upi_id):
    conn = get_connection()
    cursor = conn.cursor()
    clean_phone = _clean_phone(phone_number)
    cursor.execute("""
        UPDATE shopkeepers
        SET shop_name = ?, owner_name = ?, upi_id = ?
        WHERE phone_number = ?
    """, (new_shop_name.strip(), new_owner_name.strip(), new_upi_id.strip(), clean_phone))
    conn.commit()
    conn.close()


# --- SESSION MANAGEMENT (for "stay logged in" across refresh, without exposing phone/PIN) ---
def create_session(phone_number):
    conn = get_connection()
    cursor = conn.cursor()
    clean_phone = _clean_phone(phone_number)
    token = secrets.token_urlsafe(24)
    now = datetime.now()
    expires = now + timedelta(days=SESSION_LIFETIME_DAYS)
    cursor.execute("""
        INSERT INTO sessions (token, store_phone, created_at, expires_at)
        VALUES (?, ?, ?, ?)
    """, (token, clean_phone, now.isoformat(), expires.isoformat()))
    conn.commit()
    conn.close()
    return token


def get_store_by_session(token):
    if not token:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT store_phone, expires_at FROM sessions WHERE token = ?", (token,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    store_phone, expires_at = row
    if datetime.fromisoformat(expires_at) < datetime.now():
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        return None
    conn.close()
    return get_shopkeeper(store_phone)


def delete_session(token):
    if not token:
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


# --- INVENTORY CRUD ---
def add_or_update_stock(store_phone, items_list):
    conn = get_connection()
    cursor = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    clean_phone = _clean_phone(store_phone)

    for item in items_list:
        name = str(item.get("Item Name", "")).strip()
        if not name:
            continue
        try:
            qty = max(int(item.get("Quantity", 1)), 0)
        except (TypeError, ValueError):
            qty = 0
        try:
            rate = max(float(item.get("Rate (₹)", item.get("Rate", 0.0))), 0.0)
        except (TypeError, ValueError):
            rate = 0.0

        cursor.execute("SELECT quantity FROM inventory WHERE store_phone = ? AND item_name = ?", (clean_phone, name))
        row = cursor.fetchone()

        if row:
            new_qty = row[0] + qty
            cursor.execute("""
                UPDATE inventory
                SET quantity = ?, wholesale_rate = ?, last_restocked = ?, status = 'Active / Restocked'
                WHERE store_phone = ? AND item_name = ?
            """, (new_qty, rate, today_str, clean_phone, name))
        else:
            cursor.execute("""
                INSERT INTO inventory (store_phone, item_name, quantity, wholesale_rate, last_restocked, status)
                VALUES (?, ?, ?, ?, ?, 'New SKU')
            """, (clean_phone, name, qty, rate, today_str))

    conn.commit()
    conn.close()


def delete_inventory_item(store_phone, item_name):
    conn = get_connection()
    cursor = conn.cursor()
    clean_phone = _clean_phone(store_phone)
    cursor.execute("DELETE FROM inventory WHERE store_phone = ? AND item_name = ?", (clean_phone, item_name))
    conn.commit()
    conn.close()


def mark_dead_stock(store_phone, item_name, is_dead=True):
    conn = get_connection()
    cursor = conn.cursor()
    clean_phone = _clean_phone(store_phone)
    new_status = "Dead / At-Risk" if is_dead else "Active"
    cursor.execute("UPDATE inventory SET status = ? WHERE store_phone = ? AND item_name = ?", (new_status, clean_phone, item_name))
    conn.commit()
    conn.close()


def get_inventory_dataframe(store_phone):
    conn = get_connection()
    clean_phone = _clean_phone(store_phone)
    df = pd.read_sql_query("""
        SELECT item_name AS 'Item SKU', quantity AS 'Stock Qty', wholesale_rate AS 'Rate (₹)',
               (quantity * wholesale_rate) AS 'Total Capital (₹)', status AS 'Status', last_restocked AS 'Last Updated'
        FROM inventory WHERE store_phone = ? ORDER BY id DESC
    """, conn, params=(clean_phone,))
    conn.close()
    return df


def get_low_stock_items(store_phone, threshold=LOW_STOCK_THRESHOLD):
    conn = get_connection()
    clean_phone = _clean_phone(store_phone)
    df = pd.read_sql_query("""
        SELECT item_name AS 'Item SKU', quantity AS 'Stock Qty', wholesale_rate AS 'Rate (₹)'
        FROM inventory WHERE store_phone = ? AND quantity <= ? AND quantity > 0
        ORDER BY quantity ASC
    """, conn, params=(clean_phone, threshold))
    conn.close()
    return df


def get_dead_stock_items(store_phone):
    conn = get_connection()
    clean_phone = _clean_phone(store_phone)
    df = pd.read_sql_query("""
        SELECT item_name AS 'Item SKU', quantity AS 'Stock Qty', (quantity * wholesale_rate) AS 'Capital Locked (₹)'
        FROM inventory WHERE store_phone = ? AND (status LIKE '%Dead%' OR status LIKE '%Stagnant%')
        ORDER BY (quantity * wholesale_rate) DESC
    """, conn, params=(clean_phone,))
    conn.close()
    return df


def get_kpi_metrics(store_phone):
    conn = get_connection()
    cursor = conn.cursor()
    clean_phone = _clean_phone(store_phone)
    cursor.execute("SELECT COUNT(*), SUM(quantity * wholesale_rate) FROM inventory WHERE store_phone = ?", (clean_phone,))
    row = cursor.fetchone()
    total_skus = row[0] or 0
    total_capital = row[1] or 0.0

    cursor.execute("SELECT SUM(quantity * wholesale_rate) FROM inventory WHERE store_phone = ? AND (status LIKE '%Dead%' OR status LIKE '%Stagnant%')", (clean_phone,))
    dead_capital = cursor.fetchone()[0] or 0.0

    cursor.execute("SELECT COUNT(*) FROM inventory WHERE store_phone = ? AND quantity <= ? AND quantity > 0", (clean_phone, LOW_STOCK_THRESHOLD))
    low_stock_count = cursor.fetchone()[0] or 0

    conn.close()
    return total_skus, round(total_capital, 2), round(dead_capital, 2), low_stock_count


# --- UDHAR CRUD ---
def add_udhar_entry(store_phone, customer_name, customer_phone, amount, items_note, due_date):
    conn = get_connection()
    cursor = conn.cursor()
    credit_date = datetime.now().strftime("%Y-%m-%d")
    clean_store_phone = _clean_phone(store_phone)
    clean_cust_phone = _clean_phone(customer_phone)

    cursor.execute("""
        INSERT INTO udhar_ledger (store_phone, customer_name, customer_phone, amount, items_note, credit_date, due_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending')
    """, (clean_store_phone, customer_name.strip(), clean_cust_phone, amount, items_note.strip(), credit_date, str(due_date)))
    conn.commit()
    conn.close()


def get_udhar_records(store_phone):
    conn = get_connection()
    clean_phone = _clean_phone(store_phone)
    df = pd.read_sql_query("""
        SELECT id, customer_name, customer_phone, amount, items_note, credit_date, due_date, status
        FROM udhar_ledger WHERE store_phone = ? ORDER BY due_date ASC
    """, conn, params=(clean_phone,))
    conn.close()
    return df


def settle_udhar(record_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE udhar_ledger SET status = 'Paid' WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()


def get_total_udhar_pending(store_phone):
    conn = get_connection()
    cursor = conn.cursor()
    clean_phone = _clean_phone(store_phone)
    cursor.execute("SELECT SUM(amount) FROM udhar_ledger WHERE store_phone = ? AND status != 'Paid'", (clean_phone,))
    total = cursor.fetchone()[0] or 0.0
    conn.close()
    return round(total, 2)
