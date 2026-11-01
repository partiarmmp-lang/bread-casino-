import asyncpg
import os
import secrets
import string
import datetime

DB_URL = os.environ.get(
    'DATABASE_URL', 
    'postgresql://postgres.nweygfqvmlwdmdnddxre:Dundel2009!.@aws-1-eu-west-3.pooler.supabase.com:6543/postgres'
)

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DB_URL, max_size=10)
    return _pool

def _uid(user_id):
    try:
        return int(user_id)
    except (ValueError, TypeError):
        return abs(hash(str(user_id))) % (10**15)

# Обновленная инициализация БД с новыми колонками
async def init_db():
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                balance DOUBLE PRECISION DEFAULT 0.0,
                bonus_balance DOUBLE PRECISION DEFAULT 0.0,
                wager_required DOUBLE PRECISION DEFAULT 0.0,
                wager_done DOUBLE PRECISION DEFAULT 0.0,
                referrer_id BIGINT,
                ref_earnings DOUBLE PRECISION DEFAULT 0.0,
                total_deposits DOUBLE PRECISION DEFAULT 0.0,
                first_deposit_done INTEGER DEFAULT 0,
                lucky_points INTEGER DEFAULT 0,
                coins INTEGER DEFAULT 0,
                energy INTEGER DEFAULT 100,
                energy_limit INTEGER DEFAULT 100,
                last_energy_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_daily_bonus TIMESTAMP DEFAULT NULL,
                last_wheel_spin TIMESTAMP DEFAULT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                type TEXT NOT NULL,
                amount DOUBLE PRECISION NOT NULL,
                meta TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

# --- БАЛАНСЫ ---
async def get_total_balance(user_id) -> float:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT balance, bonus_balance FROM users WHERE user_id = $1", _uid(user_id))
        if not row: return 0.0
        return (row['balance'] or 0.0) + (row['bonus_balance'] or 0.0)

async def get_balance(user_id) -> float:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT balance FROM users WHERE user_id = $1", _uid(user_id))
        return (row['balance'] or 0.0) if row else 0.0

async def get_bonus_balance(user_id) -> float:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT bonus_balance FROM users WHERE user_id = $1", _uid(user_id))
        return (row['bonus_balance'] or 0.0) if row else 0.0

async def update_balance(user_id, amount: float):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
        await db.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, _uid(user_id))

async def try_deduct_balance(user_id, amount: float) -> bool:
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
        res = await db.execute("UPDATE users SET balance = balance - $1 WHERE user_id = $2 AND balance >= $1", amount, _uid(user_id))
        return res == "UPDATE 1"

async def try_deduct_bonus(user_id, amount: float) -> bool:
    pool = await get_pool()
    async with pool.acquire() as db:
        res = await db.execute("UPDATE users SET bonus_balance = bonus_balance - $1 WHERE user_id = $2 AND bonus_balance >= $1", amount, _uid(user_id))
        return res == "UPDATE 1"

# --- БОНУСЫ И ВЕЙДЖЕР (x3) ---
async def add_bonus(user_id, amount: float, wager_multiplier: float = 3.0):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
        await db.execute("UPDATE users SET bonus_balance = bonus_balance + $1, wager_required = wager_required + $2 WHERE user_id = $3", amount, amount * wager_multiplier, _uid(user_id))

async def get_wager_info(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT wager_required, wager_done FROM users WHERE user_id = $1", _uid(user_id))
        return (row['wager_required'] or 0.0, row['wager_done'] or 0.0) if row else (0.0, 0.0)

async def add_wager_progress(user_id, amount: float):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT wager_required, wager_done, bonus_balance FROM users WHERE user_id = $1", _uid(user_id))
        if not row: return
        req, done, bonus = row['wager_required'] or 0.0, row['wager_done'] or 0.0, row['bonus_balance'] or 0.0
        done += amount
        if done >= req and req > 0:
            await db.execute("UPDATE users SET balance = balance + $1, bonus_balance = 0.0, wager_required = 0.0, wager_done = 0.0 WHERE user_id = $2", bonus, _uid(user_id))
        else:
            await db.execute("UPDATE users SET wager_done = $1 WHERE user_id = $2", done, _uid(user_id))

# --- РЕФЕРАЛКА ---
async def set_referrer(user_id, referrer_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
        row = await db.fetchrow("SELECT referrer_id FROM users WHERE user_id = $1", _uid(user_id))
        if row and row['referrer_id']: return False
        if user_id == referrer_id: return False
        await db.execute("UPDATE users SET referrer_id = $1 WHERE user_id = $2", _uid(referrer_id), _uid(user_id))
        return True

async def get_referrers_chain(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT referrer_id FROM users WHERE user_id = $1", _uid(user_id))
        if not row or not row['referrer_id']: return [None, None, None]
        lvl1 = row['referrer_id']
        r2 = await db.fetchrow("SELECT referrer_id FROM users WHERE user_id = $1", _uid(lvl1))
        lvl2 = r2['referrer_id'] if r2 else None
        lvl3 = None
        if lvl2:
            r3 = await db.fetchrow("SELECT referrer_id FROM users WHERE user_id = $1", _uid(lvl2))
            lvl3 = r3['referrer_id'] if r3 else None
        return [lvl1, lvl2, lvl3]

async def add_ref_earning(referrer_id, amount: float):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(referrer_id))
        await db.execute("UPDATE users SET balance = balance + $1, ref_earnings = ref_earnings + $1 WHERE user_id = $2", amount, _uid(referrer_id))

async def get_referral_count(user_id) -> int:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT COUNT(*) as c FROM users WHERE referrer_id = $1", _uid(user_id))
        return row['c'] if row else 0

async def get_referral_earnings(user_id) -> float:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT ref_earnings FROM users WHERE user_id = $1", _uid(user_id))
        return (row['ref_earnings'] or 0.0) if row else 0.0

async def log_tx(user_id, tx_type: str, amount: float, meta: str = ""):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO transactions (user_id, type, amount, meta) VALUES ($1, $2, $3, $4)", _uid(user_id), tx_type, amount, meta)