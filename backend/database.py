import asyncpg
import os
import secrets
import string

# Берем URL из переменных окружения. Убедись, что в Render добавлена переменная DATABASE_URL
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
                total_lost DOUBLE PRECISION DEFAULT 0.0,
                deposit_count INTEGER DEFAULT 0,
                first_deposit_done INTEGER DEFAULT 0,
                roulette_freespins INTEGER DEFAULT 0,
                free_lottery_tickets INTEGER DEFAULT 0,
                channel_bonus_given INTEGER DEFAULT 0,
                referrer_lvl2 BIGINT,
                referrer_lvl3 BIGINT,
                luck_points INTEGER DEFAULT 0,
                luck_total INTEGER DEFAULT 0,
                weekly_lost DOUBLE PRECISION DEFAULT 0.0,
                monthly_deposits DOUBLE PRECISION DEFAULT 0.0,
                total_bonus_purchases DOUBLE PRECISION DEFAULT 0.0,
                bonus_purchase_count INTEGER DEFAULT 0,
                language TEXT DEFAULT NULL
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

async def get_total_balance(user_id) -> float:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT balance, bonus_balance FROM users WHERE user_id = $1", _uid(user_id))
        if not row: return 0.0
        return (row['balance'] or 0.0) + (row['bonus_balance'] or 0.0)

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

async def log_tx(user_id, tx_type: str, amount: float, meta: str = ""):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO transactions (user_id, type, amount, meta) VALUES ($1, $2, $3, $4)", _uid(user_id), tx_type, amount, meta)