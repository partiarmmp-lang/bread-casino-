import aiosqlite
import os
import secrets
import string
import datetime

DB_NAME = os.environ.get('DB_PATH', 'casino.db')

def _uid(user_id):
    try:
        return int(user_id)
    except (ValueError, TypeError):
        return abs(hash(str(user_id))) % (10**15)

def _gen_code(length=10):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 0.0,
                bonus_balance REAL DEFAULT 0.0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                meta TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def get_balance(user_id) -> float:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cursor.fetchone()
        if row is None:
            await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
            await db.commit()
            return 0.0
        return row[0] or 0.0

async def update_balance(user_id, amount: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, _uid(user_id)))
        await db.commit()

async def try_deduct_balance(user_id, amount: float) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
        cur = await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
            (amount, _uid(user_id), amount)
        )
        await db.commit()
        return cur.rowcount > 0

async def log_tx(user_id, tx_type: str, amount: float, meta: str = ""):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO transactions (user_id, type, amount, meta) VALUES (?, ?, ?, ?)",
            (_uid(user_id), tx_type, amount, meta)
        )
        await db.commit()
