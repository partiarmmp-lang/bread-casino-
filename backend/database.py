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
                bonus_balance REAL DEFAULT 0.0,
                wager_required REAL DEFAULT 0.0,
                wager_done REAL DEFAULT 0.0,
                referrer_id INTEGER,
                ref_earnings REAL DEFAULT 0.0,
                total_deposits REAL DEFAULT 0.0,
                total_lost REAL DEFAULT 0.0,
                deposit_count INTEGER DEFAULT 0,
                first_deposit_done INTEGER DEFAULT 0,
                roulette_freespins INTEGER DEFAULT 0,
                free_lottery_tickets INTEGER DEFAULT 0,
                channel_bonus_given INTEGER DEFAULT 0,
                referrer_lvl2 INTEGER,
                referrer_lvl3 INTEGER,
                luck_points INTEGER DEFAULT 0,
                luck_total INTEGER DEFAULT 0,
                weekly_lost REAL DEFAULT 0.0,
                monthly_deposits REAL DEFAULT 0.0,
                total_bonus_purchases REAL DEFAULT 0.0,
                bonus_purchase_count INTEGER DEFAULT 0,
                language TEXT DEFAULT NULL,
                coins INTEGER DEFAULT 0,
                energy INTEGER DEFAULT 100,
                energy_limit INTEGER DEFAULT 100,
                last_energy_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_daily_bonus TIMESTAMP DEFAULT NULL,
                pending_deposit_bonus REAL DEFAULT 0.0,
                daily_streak INTEGER DEFAULT 0,
                last_streak_day TEXT,
                last_wheel_spin TEXT,
                wheel_total_spins INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS luck_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                reward TEXT,
                amount REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions(user_id, id DESC)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                amount REAL NOT NULL,
                max_uses INTEGER NOT NULL,
                uses INTEGER DEFAULT 0,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_activations (
                code TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (code, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                code TEXT PRIMARY KEY,
                amount REAL NOT NULL,
                created_by INTEGER,
                claimed_by INTEGER,
                claimed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.commit()

        migrations = [
            "ALTER TABLE users ADD COLUMN luck_points INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN luck_total INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN weekly_lost REAL DEFAULT 0.0",
            "ALTER TABLE users ADD COLUMN monthly_deposits REAL DEFAULT 0.0",
            "ALTER TABLE users ADD COLUMN total_bonus_purchases REAL DEFAULT 0.0",
            "ALTER TABLE users ADD COLUMN bonus_purchase_count INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN bonus_balance REAL DEFAULT 0.0",
            "ALTER TABLE users ADD COLUMN wager_required REAL DEFAULT 0.0",
            "ALTER TABLE users ADD COLUMN wager_done REAL DEFAULT 0.0",
            "ALTER TABLE users ADD COLUMN referrer_id INTEGER",
            "ALTER TABLE users ADD COLUMN ref_earnings REAL DEFAULT 0.0",
            "ALTER TABLE users ADD COLUMN total_deposits REAL DEFAULT 0.0",
            "ALTER TABLE users ADD COLUMN total_lost REAL DEFAULT 0.0",
            "ALTER TABLE users ADD COLUMN deposit_count INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN first_deposit_done INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN roulette_freespins INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN free_lottery_tickets INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN channel_bonus_given INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN referrer_lvl2 INTEGER",
            "ALTER TABLE users ADD COLUMN referrer_lvl3 INTEGER",
            "ALTER TABLE users ADD COLUMN language TEXT DEFAULT NULL",
            "ALTER TABLE users ADD COLUMN coins INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN energy INTEGER DEFAULT 100",
            "ALTER TABLE users ADD COLUMN energy_limit INTEGER DEFAULT 100",
            "ALTER TABLE users ADD COLUMN last_energy_reset TIMESTAMP",
            "ALTER TABLE users ADD COLUMN last_daily_bonus TIMESTAMP DEFAULT NULL",
            "ALTER TABLE users ADD COLUMN pending_deposit_bonus REAL DEFAULT 0.0",
            "ALTER TABLE users ADD COLUMN daily_streak INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN last_streak_day TEXT",
            "ALTER TABLE users ADD COLUMN last_wheel_spin TEXT",
            "ALTER TABLE users ADD COLUMN wheel_total_spins INTEGER DEFAULT 0",
        ]
        for m in migrations:
            try:
                await db.execute(m)
                await db.commit()
            except Exception:
                pass


# ============ ЯЗЫК ============
async def get_language(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT language FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        return row[0] if row else None

async def set_language(user_id, lang: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
        await db.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, _uid(user_id)))
        await db.commit()
      # ============ ЛОГ ТРАНЗАКЦИЙ ============
async def log_tx(user_id, tx_type: str, amount: float, meta: str = ""):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO transactions (user_id, type, amount, meta) VALUES (?, ?, ?, ?)",
            (_uid(user_id), tx_type, amount, meta)
        )
        await db.commit()

async def get_transactions(user_id, limit: int = 15):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT type, amount, meta, created_at FROM transactions "
            "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (_uid(user_id), limit)
        )
        return await cur.fetchall()

# ============ ПОЛЬЗОВАТЕЛИ ============
async def is_new_user(user_id) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cursor.fetchone()
        return row is None

async def get_balance(user_id) -> float:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cursor.fetchone()
        if row is None:
            await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
            await db.commit()
            return 0.0
        return row[0] or 0.0

async def get_bonus_balance(user_id) -> float:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT bonus_balance FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cursor.fetchone()
        return (row[0] or 0.0) if row else 0.0

async def get_wager_info(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT wager_required, wager_done FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cursor.fetchone()
        if not row:
            return 0.0, 0.0
        return row[0] or 0.0, row[1] or 0.0

async def get_total_balance(user_id) -> float:
    return await get_balance(user_id) + await get_bonus_balance(user_id)

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

async def try_deduct_bonus(user_id, amount: float) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "UPDATE users SET bonus_balance = bonus_balance - ? WHERE user_id = ? AND bonus_balance >= ?",
            (amount, _uid(user_id), amount)
        )
        await db.commit()
        return cur.rowcount > 0

async def add_bonus(user_id, amount: float, wager_multiplier: float = 3.0):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
        await db.execute(
            "UPDATE users SET bonus_balance = bonus_balance + ?, wager_required = wager_required + ? WHERE user_id = ?",
            (amount, amount * wager_multiplier, _uid(user_id)))
        await db.commit()

async def use_bonus(user_id, amount: float):
    return await try_deduct_bonus(user_id, amount)

async def add_wager_progress(user_id, amount: float):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT wager_required, wager_done, bonus_balance FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        if not row:
            return
        req, done, bonus = row[0] or 0.0, row[1] or 0.0, row[2] or 0.0
        done += amount
        if done >= req and req > 0:
            await db.execute("UPDATE users SET balance = balance + ?, bonus_balance = 0.0, wager_required = 0.0, wager_done = 0.0 WHERE user_id = ?", (bonus, _uid(user_id)))
        else:
            await db.execute("UPDATE users SET wager_done = ? WHERE user_id = ?", (done, _uid(user_id)))
        await db.commit()

async def transfer_between_users(from_id, to_id, amount: float) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(from_id),))
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(to_id),))
        await db.commit()
        cur = await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
            (amount, _uid(from_id), amount)
        )
        if cur.rowcount == 0:
            await db.commit()
            return False
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, _uid(to_id)))
        await db.commit()
        return True
