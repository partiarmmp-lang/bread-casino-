import asyncpg
import os
import secrets
import string
import datetime

DB_URL = os.environ.get(
    'DATABASE_URL', 
    'postgresql://postgres.nweygfqvmlwdmdnddxre:Dundel2009!.@aws-1-eu-west-3.pooler.supabase.com:5432/postgres'
)

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DB_URL)
    return _pool

def _uid(user_id):
    try:
        return int(user_id)
    except (ValueError, TypeError):
        return abs(hash(str(user_id))) % (10**15)

def _gen_code(length=10):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

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
                language TEXT DEFAULT NULL,
                coins INTEGER DEFAULT 0,
                energy INTEGER DEFAULT 100,
                energy_limit INTEGER DEFAULT 100,
                last_energy_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_daily_bonus TIMESTAMP DEFAULT NULL,
                pending_deposit_bonus DOUBLE PRECISION DEFAULT 0.0,
                daily_streak INTEGER DEFAULT 0,
                last_streak_day TEXT,
                last_wheel_spin TEXT,
                wheel_total_spins INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS luck_log (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                reward TEXT,
                amount DOUBLE PRECISION,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                amount DOUBLE PRECISION NOT NULL,
                max_uses INTEGER NOT NULL,
                uses INTEGER DEFAULT 0,
                created_by BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_activations (
                code TEXT NOT NULL,
                user_id BIGINT NOT NULL,
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (code, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                code TEXT PRIMARY KEY,
                amount DOUBLE PRECISION NOT NULL,
                created_by BIGINT,
                claimed_by BIGINT,
                claimed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

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
        async def set_referrer_full(user_id, lvl1_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
        row = await db.fetchrow("SELECT referrer_id FROM users WHERE user_id = $1", _uid(user_id))
        if row and row['referrer_id']: return False
        lvl2_id, lvl3_id = None, None
        r = await db.fetchrow("SELECT referrer_id FROM users WHERE user_id = $1", _uid(lvl1_id))
        if r and r['referrer_id']:
            lvl2_id = r['referrer_id']
            r2 = await db.fetchrow("SELECT referrer_id FROM users WHERE user_id = $1", _uid(lvl2_id))
            if r2 and r2['referrer_id']: lvl3_id = r2['referrer_id']
        await db.execute("UPDATE users SET referrer_id = $1, referrer_lvl2 = $2, referrer_lvl3 = $3 WHERE user_id = $4", _uid(lvl1_id), lvl2_id, lvl3_id, _uid(user_id))
        return True

async def get_referrers_chain(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT referrer_id, referrer_lvl2, referrer_lvl3 FROM users WHERE user_id = $1", _uid(user_id))
        return [row['referrer_id'], row['referrer_lvl2'], row['referrer_lvl3']] if row else [None, None, None]

async def get_referrer(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT referrer_id FROM users WHERE user_id = $1", _uid(user_id))
        return row['referrer_id'] if row else None

async def get_referral_count(user_id) -> int:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT COUNT(*) as c FROM users WHERE referrer_id = $1", _uid(user_id))
        return row['c'] if row else 0

async def get_referral_earnings(user_id) -> float:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT ref_earnings FROM users WHERE user_id = $1", _uid(user_id))
        return row['ref_earnings'] if row else 0.0

async def add_ref_earning(referrer_id, amount: float):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(referrer_id))
        await db.execute("UPDATE users SET balance = balance + $1, ref_earnings = ref_earnings + $1 WHERE user_id = $2", amount, _uid(referrer_id))

async def add_loss(user_id, amount: float):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
        await db.execute("UPDATE users SET total_lost = total_lost + $1, weekly_lost = weekly_lost + $1 WHERE user_id = $2", amount, _uid(user_id))

async def is_first_deposit(user_id) -> bool:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT deposit_count FROM users WHERE user_id = $1", _uid(user_id))
        return not (row and row['deposit_count'] and row['deposit_count'] > 0)

async def mark_deposit(user_id, amount: float):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
        await db.execute("UPDATE users SET first_deposit_done = 1, deposit_count = deposit_count + 1, total_deposits = total_deposits + $1 WHERE user_id = $2", amount, _uid(user_id))
        await db.execute("UPDATE users SET monthly_deposits = monthly_deposits + $1 WHERE user_id = $2", amount, _uid(user_id))

async def has_deposit(user_id) -> bool:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT total_deposits FROM users WHERE user_id = $1", _uid(user_id))
        return bool(row and row['total_deposits'] and row['total_deposits'] > 0)

async def give_channel_bonus(user_id, amount=5.0) -> bool:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT channel_bonus_given FROM users WHERE user_id = $1", _uid(user_id))
        if row and row['channel_bonus_given']: return False
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
        await db.execute("UPDATE users SET balance = balance + $1, channel_bonus_given = 1 WHERE user_id = $2", amount, _uid(user_id))
        return True

async def add_freespins(user_id, roulette: int = 0, lottery: int = 0):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
        await db.execute("UPDATE users SET roulette_freespins = roulette_freespins + $1, free_lottery_tickets = free_lottery_tickets + $2 WHERE user_id = $3", roulette, lottery, _uid(user_id))

async def get_freespins(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT roulette_freespins, free_lottery_tickets FROM users WHERE user_id = $1", _uid(user_id))
        return (row['roulette_freespins'] or 0, row['free_lottery_tickets'] or 0) if row else (0, 0)

async def use_roulette_freespin(user_id) -> bool:
    pool = await get_pool()
    async with pool.acquire() as db:
        res = await db.execute("UPDATE users SET roulette_freespins = roulette_freespins - 1 WHERE user_id = $1 AND roulette_freespins > 0", _uid(user_id))
        return res == "UPDATE 1"

async def use_lottery_tickets(user_id, count: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as db:
        res = await db.execute("UPDATE users SET free_lottery_tickets = free_lottery_tickets - $1 WHERE user_id = $2 AND free_lottery_tickets >= $1", count, _uid(user_id))
        return res == "UPDATE 1"

async def set_partner_percent(user_id, percent):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS partner_percents (user_id BIGINT PRIMARY KEY, percent DOUBLE PRECISION NOT NULL)")
        await db.execute("INSERT INTO partner_percents (user_id, percent) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET percent = EXCLUDED.percent", _uid(user_id), float(percent))

async def get_partner_percent(user_id, default=10.0):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS partner_percents (user_id BIGINT PRIMARY KEY, percent DOUBLE PRECISION NOT NULL)")
        row = await db.fetchrow("SELECT percent FROM partner_percents WHERE user_id = $1", _uid(user_id))
        return row['percent'] if row else default
        async def add_luck_points(user_id, points: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
        await db.execute("UPDATE users SET luck_points = luck_points + $1, luck_total = luck_total + $1 WHERE user_id = $2", points, _uid(user_id))

async def get_luck_points(user_id) -> tuple:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT luck_points, luck_total FROM users WHERE user_id = $1", _uid(user_id))
        return (row['luck_points'] or 0, row['luck_total'] or 0) if row else (0, 0)

async def spend_luck_points(user_id, points: int = 100):
    pool = await get_pool()
    async with pool.acquire() as db:
        res = await db.execute("UPDATE users SET luck_points = luck_points - $1 WHERE user_id = $2 AND luck_points >= $1", points, _uid(user_id))
        return res == "UPDATE 1"

async def log_luck_reward(user_id, reward: str, amount: float):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO luck_log (user_id, reward, amount) VALUES ($1, $2, $3)", _uid(user_id), reward, amount)

async def get_luck_history(user_id, limit: int = 5):
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch("SELECT reward, amount, created_at FROM luck_log WHERE user_id = $1 ORDER BY id DESC LIMIT $2", _uid(user_id), limit)
        return [(r['reward'], r['amount'], r['created_at']) for r in rows]

async def get_weekly_lost(user_id) -> float:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT weekly_lost FROM users WHERE user_id = $1", _uid(user_id))
        return (row['weekly_lost'] or 0.0) if row else 0.0

async def reset_weekly(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE users SET weekly_lost = 0.0 WHERE user_id = $1", _uid(user_id))

def get_cashback_percent(weekly_lost: float) -> int:
    if weekly_lost >= 500: return 15
    elif weekly_lost >= 100: return 10
    elif weekly_lost >= 50: return 7
    elif weekly_lost >= 10: return 5
    return 0

async def get_monthly_deposits(user_id) -> float:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT monthly_deposits FROM users WHERE user_id = $1", _uid(user_id))
        return (row['monthly_deposits'] or 0.0) if row else 0.0

async def reset_monthly(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE users SET monthly_deposits = 0.0 WHERE user_id = $1", _uid(user_id))

async def add_bonus_purchase(user_id, amount_paid: float, bonus_amount: float):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
        await db.execute("UPDATE users SET total_bonus_purchases = total_bonus_purchases + $1, bonus_purchase_count = bonus_purchase_count + 1 WHERE user_id = $2", amount_paid, _uid(user_id))

async def create_promo(code: str, amount: float, max_uses: int, created_by: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as db:
        try:
            await db.execute("INSERT INTO promocodes (code, amount, max_uses, created_by) VALUES ($1, $2, $3, $4)", code.upper().strip(), amount, max_uses, _uid(created_by))
            return True
        except asyncpg.UniqueViolationError:
            return False

async def delete_promo(code: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as db:
        res = await db.execute("DELETE FROM promocodes WHERE code = $1", code.upper().strip())
        return res == "DELETE 1"

async def list_promos(limit: int = 20):
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch("SELECT code, amount, max_uses, uses, created_at FROM promocodes ORDER BY created_at DESC LIMIT $1", limit)
        return [(r['code'], r['amount'], r['max_uses'], r['uses'], r['created_at']) for r in rows]

async def get_promo(code: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT code, amount, max_uses, uses FROM promocodes WHERE code = $1", code.upper().strip())
        return (row['code'], row['amount'], row['max_uses'], row['uses']) if row else None

async def activate_promo(code: str, user_id) -> tuple:
    code = code.upper().strip()
    uid = _uid(user_id)
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT amount, max_uses, uses FROM promocodes WHERE code = $1", code)
        if not row: return False, "not_found", 0.0
        amount, max_uses, uses = row['amount'], row['max_uses'], row['uses']
        if uses >= max_uses: return False, "limit", 0.0
        act = await db.fetchrow("SELECT 1 FROM promo_activations WHERE code = $1 AND user_id = $2", code, uid)
        if act: return False, "already", 0.0
        res = await db.execute("UPDATE promocodes SET uses = uses + 1 WHERE code = $1 AND uses < max_uses", code)
        if res != "UPDATE 1": return False, "limit", 0.0
        await db.execute("INSERT INTO promo_activations (code, user_id) VALUES ($1, $2)", code, uid)
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", uid)
        await db.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, uid)
        return True, "OK", amount

async def create_check(amount: float, created_by) -> str:
    code = _gen_code(12)
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO checks (code, amount, created_by) VALUES ($1, $2, $3)", code, amount, _uid(created_by))
    return code

async def get_check(code: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT code, amount, created_by, claimed_by FROM checks WHERE code = $1", code.upper().strip())
        return (row['code'], row['amount'], row['created_by'], row['claimed_by']) if row else None

async def claim_check(code: str, user_id) -> tuple:
    code = code.upper().strip()
    uid = _uid(user_id)
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT amount, claimed_by FROM checks WHERE code = $1", code)
        if not row: return False, "not_found", 0.0
        amount, claimed_by = row['amount'], row['claimed_by']
        if claimed_by is not None: return False, "already", 0.0
        res = await db.execute("UPDATE checks SET claimed_by = $1, claimed_at = CURRENT_TIMESTAMP WHERE code = $2 AND claimed_by IS NULL", uid, code)
        if res != "UPDATE 1": return False, "already", 0.0
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", uid)
        await db.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, uid)
        return True, "OK", amount

async def get_tap_data(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT coins, energy, energy_limit, last_energy_reset, last_daily_bonus FROM users WHERE user_id = $1", _uid(user_id))
        if not row:
            await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
            row = await db.fetchrow("SELECT coins, energy, energy_limit, last_energy_reset, last_daily_bonus FROM users WHERE user_id = $1", _uid(user_id))
        return (row['coins'], row['energy'], row['energy_limit'], row['last_energy_reset'], row['last_daily_bonus'])

async def update_tap_click(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        res = await db.execute("UPDATE users SET coins = coins + 1, energy = energy - 1 WHERE user_id = $1 AND energy >= 1", _uid(user_id))
        return res == "UPDATE 1"

async def regenerate_energy(user_id, energy_limit, regen_rate=10):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT energy, last_energy_reset FROM users WHERE user_id = $1", _uid(user_id))
        if not row: return
        current_energy = row['energy']
        last_reset = row['last_energy_reset'] or datetime.datetime.utcnow()
        now = datetime.datetime.utcnow()
        gained = int(((now - last_reset).total_seconds() / 3600.0) * regen_rate)
        if gained > 0:
            new_energy = min(energy_limit, current_energy + gained)
            await db.execute("UPDATE users SET energy = $1, last_energy_reset = $2 WHERE user_id = $3", new_energy, now, _uid(user_id))

async def deduct_coins(user_id, amount):
    pool = await get_pool()
    async with pool.acquire() as db:
        res = await db.execute("UPDATE users SET coins = coins - $1 WHERE user_id = $2 AND coins >= $1", amount, _uid(user_id))
        return res == "UPDATE 1"

async def upgrade_energy_limit(user_id, amount):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE users SET energy_limit = energy_limit + $1 WHERE user_id = $2", amount, _uid(user_id))

async def add_pending_bonus(user_id, percent):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE users SET pending_deposit_bonus = pending_deposit_bonus + $1 WHERE user_id = $2", percent, _uid(user_id))

async def get_pending_bonus(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT pending_deposit_bonus FROM users WHERE user_id = $1", _uid(user_id))
        return row['pending_deposit_bonus'] if row else 0.0

async def reset_pending_bonus(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE users SET pending_deposit_bonus = 0.0 WHERE user_id = $1", _uid(user_id))

async def claim_daily_bonus(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT last_daily_bonus FROM users WHERE user_id = $1", _uid(user_id))
        if not row: return False, 0
        last_bonus = row['last_daily_bonus']
        now = datetime.datetime.utcnow()
        if last_bonus and (now - last_bonus).total_seconds() < 86400:
            return False, int(86400 - (now - last_bonus).total_seconds())
        await db.execute("UPDATE users SET coins = coins + 50, last_daily_bonus = $1 WHERE user_id = $2", now, _uid(user_id))
        return True, 0

def _now_utc(): return datetime.datetime.utcnow()
def _parse_dt(s): return s if isinstance(s, datetime.datetime) else None

async def get_streak_info(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT daily_streak, last_streak_day FROM users WHERE user_id = $1", _uid(user_id))
        if not row: return 0, None, True
        streak, last_day = row['daily_streak'] or 0, row['last_streak_day']
        today = _now_utc().strftime("%Y-%m-%d")
        return streak, last_day, last_day != today

async def claim_daily_streak(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT daily_streak, last_streak_day FROM users WHERE user_id = $1", _uid(user_id))
        if not row:
            await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
            streak, last_day = 0, None
        else:
            streak, last_day = row['daily_streak'] or 0, row['last_streak_day']
        now = _now_utc()
        today = now.strftime("%Y-%m-%d")
        if last_day == today: return False, streak, 0.0, "already"
        if last_day:
            try:
                last_date = datetime.datetime.strptime(last_day, "%Y-%m-%d").date()
                yesterday = (now.date() - datetime.timedelta(days=1))
                if last_date == yesterday: streak += 1
                else: streak = 1
            except Exception: streak = 1
        else: streak = 1
        if streak >= 30: bonus = 0.10
        elif streak >= 14: bonus = 0.05
        elif streak >= 7: bonus = 0.03
        elif streak >= 3: bonus = 0.02
        else: bonus = 0.01
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
        await db.execute("UPDATE users SET daily_streak = $1, last_streak_day = $2, balance = balance + $3 WHERE user_id = $4", streak, today, bonus, _uid(user_id))
        return True, streak, bonus, "ok"

async def get_wheel_info(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT last_wheel_spin, wheel_total_spins FROM users WHERE user_id = $1", _uid(user_id))
        if not row: return True, None, 0
        last_spin, total = row['last_wheel_spin'], row['wheel_total_spins'] or 0
        if not last_spin: return True, last_spin, total
        try:
            dt = datetime.datetime.strptime(str(last_spin).split('.')[0], "%Y-%m-%d %H:%M:%S")
            if (_now_utc() - dt).total_seconds() >= 86400: return True, last_spin, total
            return False, last_spin, total
        except Exception: return True, last_spin, total

async def mark_wheel_spin(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", _uid(user_id))
        now = _now_utc().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute("UPDATE users SET last_wheel_spin = $1, wheel_total_spins = wheel_total_spins + 1 WHERE user_id = $2", now, _uid(user_id))
