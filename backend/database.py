import asyncpg
import os
import secrets
import string
import datetime

DB_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres.nweygfqvmlwdmdnddxre:Dundel2009!.@aws-1-eu-west-3.pooler.supabase.com:6543/postgres')
_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DB_URL)
    return _pool

def _uid(user_id):
    try: return int(user_id)
    except (ValueError, TypeError): return abs(hash(str(user_id))) % (10**15)

def _gen_code(length=10):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, balance DOUBLE PRECISION DEFAULT 0.0, bonus_balance DOUBLE PRECISION DEFAULT 0.0, wager_required DOUBLE PRECISION DEFAULT 0.0, wager_done DOUBLE PRECISION DEFAULT 0.0, referrer_id BIGINT, ref_earnings DOUBLE PRECISION DEFAULT 0.0, total_deposits DOUBLE PRECISION DEFAULT 0.0, total_lost DOUBLE PRECISION DEFAULT 0.0, deposit_count INTEGER DEFAULT 0, first_deposit_done INTEGER DEFAULT 0, roulette_freespins INTEGER DEFAULT 0, free_lottery_tickets INTEGER DEFAULT 0, channel_bonus_given INTEGER DEFAULT 0, referrer_lvl2 BIGINT, referrer_lvl3 BIGINT, luck_points INTEGER DEFAULT 0, luck_total INTEGER DEFAULT 0, weekly_lost DOUBLE PRECISION DEFAULT 0.0, monthly_deposits DOUBLE PRECISION DEFAULT 0.0, total_bonus_purchases DOUBLE PRECISION DEFAULT 0.0, bonus_purchase_count INTEGER DEFAULT 0, language TEXT DEFAULT NULL, coins INTEGER DEFAULT 0, energy INTEGER DEFAULT 100, energy_limit INTEGER DEFAULT 100, last_energy_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_daily_bonus TIMESTAMP DEFAULT NULL, pending_deposit_bonus DOUBLE PRECISION DEFAULT 0.0, daily_streak INTEGER DEFAULT 0, last_streak_day TEXT, last_wheel_spin TEXT, wheel_total_spins INTEGER DEFAULT 0)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS luck_log (id SERIAL PRIMARY KEY, user_id BIGINT, reward TEXT, amount DOUBLE PRECISION, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS transactions (id SERIAL PRIMARY KEY, user_id BIGINT, type TEXT NOT NULL, amount DOUBLE PRECISION NOT NULL, meta TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions(user_id, id DESC)")
        await db.execute("""CREATE TABLE IF NOT EXISTS promocodes (code TEXT PRIMARY KEY, amount DOUBLE PRECISION NOT NULL, max_uses INTEGER NOT NULL, uses INTEGER DEFAULT 0, created_by BIGINT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS promo_activations (code TEXT NOT NULL, user_id BIGINT NOT NULL, activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (code, user_id))""")
        await db.execute("""CREATE TABLE IF NOT EXISTS checks (code TEXT PRIMARY KEY, amount DOUBLE PRECISION NOT NULL, created_by BIGINT, claimed_by BIGINT, claimed_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

async def get_language(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT language FROM users WHERE user_id = $1", _uid(user_id))
        return row['language'] if row else None

async def set_language(user_id, lang: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
        await db.execute("UPDATE users SET language = $1 WHERE user_id = $2", lang, _uid(user_id))

async def log_tx(user_id, tx_type: str, amount: float, meta: str = ""):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO transactions (user_id, type, amount, meta) VALUES ($1, $2, $3, $4)", _uid(user_id), tx_type, amount, meta)

async def get_transactions(user_id, limit: int = 15):
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch("SELECT type, amount, meta, created_at FROM transactions WHERE user_id = $1 ORDER BY id DESC LIMIT $2", _uid(user_id), limit)
        return [(r['type'], r['amount'], r['meta'], r['created_at']) for r in rows]

async def is_new_user(user_id) -> bool:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT user_id FROM users WHERE user_id = $1", _uid(user_id))
        return row is None

async def get_balance(user_id) -> float:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT balance FROM users WHERE user_id = $1", _uid(user_id))
        if row is None:
            await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
            return 0.0
        return row['balance'] or 0.0

async def get_bonus_balance(user_id) -> float:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT bonus_balance FROM users WHERE user_id = $1", _uid(user_id))
        return (row['bonus_balance'] or 0.0) if row else 0.0

async def get_wager_info(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT wager_required, wager_done FROM users WHERE user_id = $1", _uid(user_id))
        return (row['wager_required'] or 0.0, row['wager_done'] or 0.0) if row else (0.0, 0.0)

async def get_total_balance(user_id) -> float:
    return await get_balance(user_id) + await get_bonus_balance(user_id)

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

async def add_bonus(user_id, amount: float, wager_multiplier: float = 3.0):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
        await db.execute("UPDATE users SET bonus_balance = bonus_balance + $1, wager_required = wager_required + $2 WHERE user_id = $3", amount, amount * wager_multiplier, _uid(user_id))

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

async def transfer_between_users(from_id, to_id, amount: float) -> bool:
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(from_id))
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(to_id))
        res = await db.execute("UPDATE users SET balance = balance - $1 WHERE user_id = $2 AND balance >= $1", amount, _uid(from_id))
        if res != "UPDATE 1": return False
        await db.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, _uid(to_id))
        return True
