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


async def set_referrer_full(user_id, lvl1_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
        await db.commit()
        cur = await db.execute("SELECT referrer_id FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        if row and row[0]:
            return False
        lvl2_id = None
        lvl3_id = None
        cur = await db.execute("SELECT referrer_id FROM users WHERE user_id = ?", (_uid(lvl1_id),))
        r = await cur.fetchone()
        if r and r[0]:
            lvl2_id = r[0]
            cur = await db.execute("SELECT referrer_id FROM users WHERE user_id = ?", (_uid(lvl2_id),))
            r2 = await cur.fetchone()
            if r2 and r2[0]:
                lvl3_id = r2[0]
        await db.execute("UPDATE users SET referrer_id = ?, referrer_lvl2 = ?, referrer_lvl3 = ? WHERE user_id = ?",
                         (_uid(lvl1_id), lvl2_id, lvl3_id, _uid(user_id)))
        await db.commit()
        return True


async def get_referrers_chain(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT referrer_id, referrer_lvl2, referrer_lvl3 FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        if not row:
            return [None, None, None]
        return [row[0], row[1], row[2]]


async def get_referrer(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT referrer_id FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_referral_count(user_id) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (_uid(user_id),))
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_referral_earnings(user_id) -> float:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT ref_earnings FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cursor.fetchone()
        return row[0] if row else 0.0


async def add_ref_earning(referrer_id, amount: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(referrer_id),))
        await db.execute("UPDATE users SET balance = balance + ?, ref_earnings = ref_earnings + ? WHERE user_id = ?",
                         (amount, amount, _uid(referrer_id)))
        await db.commit()


async def add_loss(user_id, amount: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
        await db.execute("UPDATE users SET total_lost = total_lost + ? WHERE user_id = ?", (amount, _uid(user_id)))
        await db.execute("UPDATE users SET weekly_lost = weekly_lost + ? WHERE user_id = ?", (amount, _uid(user_id)))
        await db.commit()


async def is_first_deposit(user_id) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT deposit_count FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cursor.fetchone()
        return not (row and row[0] and row[0] > 0)


async def mark_deposit(user_id, amount: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
        await db.execute("UPDATE users SET first_deposit_done = 1, deposit_count = deposit_count + 1, total_deposits = total_deposits + ? WHERE user_id = ?",
                         (amount, _uid(user_id)))
        await db.execute("UPDATE users SET monthly_deposits = monthly_deposits + ? WHERE user_id = ?",
                         (amount, _uid(user_id)))
        await db.commit()


async def has_deposit(user_id) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT total_deposits FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        return bool(row and row[0] and row[0] > 0)


async def give_channel_bonus(user_id, amount=5.0) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT channel_bonus_given FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        if row and row[0]:
            return False
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
        await db.execute("UPDATE users SET balance = balance + ?, channel_bonus_given = 1 WHERE user_id = ?", (amount, _uid(user_id)))
        await db.commit()
        return True


async def add_freespins(user_id, roulette: int = 0, lottery: int = 0):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
        await db.execute("UPDATE users SET roulette_freespins = roulette_freespins + ?, free_lottery_tickets = free_lottery_tickets + ? WHERE user_id = ?",
                         (roulette, lottery, _uid(user_id)))
        await db.commit()


async def get_freespins(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT roulette_freespins, free_lottery_tickets FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        if not row:
            return 0, 0
        return row[0] or 0, row[1] or 0


async def use_roulette_freespin(user_id) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT roulette_freespins FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        if row and row[0] and row[0] > 0:
            await db.execute("UPDATE users SET roulette_freespins = roulette_freespins - 1 WHERE user_id = ?", (_uid(user_id),))
            await db.commit()
            return True
        return False


async def use_lottery_tickets(user_id, count: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT free_lottery_tickets FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        if row and row[0] and row[0] >= count:
            await db.execute("UPDATE users SET free_lottery_tickets = free_lottery_tickets - ? WHERE user_id = ?", (count, _uid(user_id)))
            await db.commit()
            return True
        return False


async def set_partner_percent(user_id, percent):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS partner_percents (user_id INTEGER PRIMARY KEY, percent REAL NOT NULL)")
        await db.execute("INSERT OR REPLACE INTO partner_percents (user_id, percent) VALUES (?, ?)", (_uid(user_id), float(percent)))
        await db.commit()


async def get_partner_percent(user_id, default=10.0):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS partner_percents (user_id INTEGER PRIMARY KEY, percent REAL NOT NULL)")
        cursor = await db.execute("SELECT percent FROM partner_percents WHERE user_id = ?", (_uid(user_id),))
        row = await cursor.fetchone()
        return row[0] if row else default


# ============ ОЧКИ УДАЧИ ============
async def add_luck_points(user_id, points: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
        await db.execute("UPDATE users SET luck_points = luck_points + ?, luck_total = luck_total + ? WHERE user_id = ?",
                         (points, points, _uid(user_id)))
        await db.commit()


async def get_luck_points(user_id) -> tuple:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT luck_points, luck_total FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        if not row:
            return 0, 0
        return row[0] or 0, row[1] or 0


async def spend_luck_points(user_id, points: int = 100):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT luck_points FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        if not row or (row[0] or 0) < points:
            return False
        await db.execute("UPDATE users SET luck_points = luck_points - ? WHERE user_id = ?", (points, _uid(user_id)))
        await db.commit()
        return True


async def log_luck_reward(user_id, reward: str, amount: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO luck_log (user_id, reward, amount) VALUES (?, ?, ?)",
                         (_uid(user_id), reward, amount))
        await db.commit()


async def get_luck_history(user_id, limit: int = 5):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT reward, amount, created_at FROM luck_log WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                               (_uid(user_id), limit))
        return await cur.fetchall()


# ============ КЭШБЭК ============
async def get_weekly_lost(user_id) -> float:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT weekly_lost FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        return (row[0] or 0.0) if row else 0.0


async def reset_weekly(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET weekly_lost = 0.0 WHERE user_id = ?", (_uid(user_id),))
        await db.commit()


def get_cashback_percent(weekly_lost: float) -> int:
    if weekly_lost >= 500:
        return 15
    elif weekly_lost >= 100:
        return 10
    elif weekly_lost >= 50:
        return 7
    elif weekly_lost >= 10:
        return 5
    return 0


async def get_monthly_deposits(user_id) -> float:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT monthly_deposits FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        return (row[0] or 0.0) if row else 0.0


async def reset_monthly(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET monthly_deposits = 0.0 WHERE user_id = ?", (_uid(user_id),))
        await db.commit()


# ============ БОНУС-ПАКЕТЫ ============
async def add_bonus_purchase(user_id, amount_paid: float, bonus_amount: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
        await db.execute(
            "UPDATE users SET total_bonus_purchases = total_bonus_purchases + ?, "
            "bonus_purchase_count = bonus_purchase_count + 1 WHERE user_id = ?",
            (amount_paid, _uid(user_id))
        )
        await db.commit()


# ============ ПРОМОКОДЫ ============
async def create_promo(code: str, amount: float, max_uses: int, created_by: int) -> bool:
    code = code.upper().strip()
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute(
                "INSERT INTO promocodes (code, amount, max_uses, created_by) VALUES (?, ?, ?, ?)",
                (code, amount, max_uses, _uid(created_by))
            )
            await db.commit()
            return True
        except Exception:
            return False


async def delete_promo(code: str) -> bool:
    code = code.upper().strip()
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("DELETE FROM promocodes WHERE code = ?", (code,))
        await db.commit()
        return cur.rowcount > 0


async def list_promos(limit: int = 20):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT code, amount, max_uses, uses, created_at FROM promocodes ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        return await cur.fetchall()


async def get_promo(code: str):
    code = code.upper().strip()
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT code, amount, max_uses, uses FROM promocodes WHERE code = ?", (code,)
        )
        return await cur.fetchone()


async def activate_promo(code: str, user_id) -> tuple:
    code = code.upper().strip()
    uid = _uid(user_id)
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT amount, max_uses, uses FROM promocodes WHERE code = ?", (code,)
        )
        row = await cur.fetchone()
        if not row:
            return False, "not_found", 0.0
        amount, max_uses, uses = row
        if uses >= max_uses:
            return False, "limit", 0.0
        cur = await db.execute(
            "SELECT 1 FROM promo_activations WHERE code = ? AND user_id = ?", (code, uid)
        )
        if await cur.fetchone():
            return False, "already", 0.0
        cur = await db.execute(
            "UPDATE promocodes SET uses = uses + 1 WHERE code = ? AND uses < max_uses",
            (code,)
        )
        if cur.rowcount == 0:
            return False, "limit", 0.0
        await db.execute(
            "INSERT INTO promo_activations (code, user_id) VALUES (?, ?)", (code, uid)
        )
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (uid,))
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, uid))
        await db.commit()
        return True, "OK", amount


# ============ ЧЕКИ ============
async def create_check(amount: float, created_by) -> str:
    code = _gen_code(12)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO checks (code, amount, created_by) VALUES (?, ?, ?)",
            (code, amount, _uid(created_by))
        )
        await db.commit()
    return code


async def get_check(code: str):
    code = code.upper().strip()
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT code, amount, created_by, claimed_by FROM checks WHERE code = ?", (code,)
        )
        return await cur.fetchone()


async def claim_check(code: str, user_id) -> tuple:
    code = code.upper().strip()
    uid = _uid(user_id)
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT amount, claimed_by FROM checks WHERE code = ?", (code,)
        )
        row = await cur.fetchone()
        if not row:
            return False, "not_found", 0.0
        amount, claimed_by = row
        if claimed_by is not None:
            return False, "already", 0.0
        cur = await db.execute(
            "UPDATE checks SET claimed_by = ?, claimed_at = CURRENT_TIMESTAMP "
            "WHERE code = ? AND claimed_by IS NULL",
            (uid, code)
        )
        if cur.rowcount == 0:
            await db.commit()
            return False, "already", 0.0
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (uid,))
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, uid))
        await db.commit()
        return True, "OK", amount


# ============ МОНЕТЫ ЗА КЛИКИ (TAP-TO-EARN) ============

async def get_tap_data(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT coins, energy, energy_limit, last_energy_reset, last_daily_bonus "
            "FROM users WHERE user_id = ?", (_uid(user_id),)
        )
        row = await cur.fetchone()
        if not row:
            await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
            await db.commit()
            cur = await db.execute(
                "SELECT coins, energy, energy_limit, last_energy_reset, last_daily_bonus "
                "FROM users WHERE user_id = ?", (_uid(user_id),)
            )
            row = await cur.fetchone()
        return row

async def update_tap_click(user_id):
    """Списывает 1 энергию и добавляет 1 монету."""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "UPDATE users SET coins = coins + 1, energy = energy - 1 "
            "WHERE user_id = ? AND energy >= 1", (_uid(user_id),)
        )
        await db.commit()
        return cur.rowcount > 0

async def regenerate_energy(user_id, energy_limit, regen_rate=10):
    """Восстанавливает энергию: +10 в час (по умолчанию)."""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT energy, last_energy_reset FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        if not row:
            return
        
        current_energy, last_reset_str = row
        if not last_reset_str:
            last_reset = datetime.datetime.utcnow()
        else:
            try:
                last_reset = datetime.datetime.strptime(last_reset_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
            except Exception:
                last_reset = datetime.datetime.utcnow()
            
        now = datetime.datetime.utcnow()
        delta_seconds = (now - last_reset).total_seconds()
        hours_passed = delta_seconds / 3600.0
        
        gained_energy = int(hours_passed * regen_rate)
        if gained_energy > 0:
            new_energy = min(energy_limit, current_energy + gained_energy)
            await db.execute(
                "UPDATE users SET energy = ?, last_energy_reset = ? WHERE user_id = ?",
                (new_energy, now.strftime("%Y-%m-%d %H:%M:%S"), _uid(user_id))
            )
            await db.commit()

async def deduct_coins(user_id, amount):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "UPDATE users SET coins = coins - ? WHERE user_id = ? AND coins >= ?", 
            (amount, _uid(user_id), amount)
        )
        await db.commit()
        return cur.rowcount > 0

async def upgrade_energy_limit(user_id, amount):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET energy_limit = energy_limit + ? WHERE user_id = ?", 
            (amount, _uid(user_id))
        )
        await db.commit()

async def add_pending_bonus(user_id, percent):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET pending_deposit_bonus = pending_deposit_bonus + ? WHERE user_id = ?",
            (percent, _uid(user_id))
        )
        await db.commit()

async def get_pending_bonus(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT pending_deposit_bonus FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        return row[0] if row else 0.0

async def reset_pending_bonus(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET pending_deposit_bonus = 0.0 WHERE user_id = ?", (_uid(user_id),))
        await db.commit()

async def claim_daily_bonus(user_id):
    """Выдает 50 монет раз в 24 часа."""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT last_daily_bonus FROM users WHERE user_id = ?", (_uid(user_id),))
        row = await cur.fetchone()
        if not row:
            return False, 0
            
        last_bonus_str = row[0]
        now = datetime.datetime.utcnow()
        
        if last_bonus_str:
            try:
                last_bonus = datetime.datetime.strptime(last_bonus_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
                if (now - last_bonus).total_seconds() < 86400:
                    return False, int(86400 - (now - last_bonus).total_seconds())
            except Exception:
                pass
                
        await db.execute(
            "UPDATE users SET coins = coins + 50, last_daily_bonus = ? WHERE user_id = ?",
            (now.strftime("%Y-%m-%d %H:%M:%S"), _uid(user_id))
        )
        await db.commit()
        return True, 0


# ============ КОЛЕСО ДНЯ + ЕЖЕДНЕВНАЯ СЕРИЯ ============

import datetime as _dt


def _now_utc():
    return _dt.datetime.utcnow()


def _parse_dt(s):
    if not s:
        return None
    try:
        return _dt.datetime.strptime(str(s).split('.')[0], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


async def get_streak_info(user_id):
    """Возвращает (streak, last_streak_day_str, can_claim_today)."""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT daily_streak, last_streak_day FROM users WHERE user_id = ?",
            (_uid(user_id),)
        )
        row = await cur.fetchone()
        if not row:
            return 0, None, True
        streak = row[0] or 0
        last_day = row[1]
        today = _now_utc().strftime("%Y-%m-%d")
        if last_day == today:
            return streak, last_day, False
        return streak, last_day, True


async def claim_daily_streak(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT daily_streak, last_streak_day FROM users WHERE user_id = ?",
            (_uid(user_id),)
        )
        row = await cur.fetchone()
        if not row:
            await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
            await db.commit()
            streak, last_day = 0, None
        else:
            streak, last_day = row[0] or 0, row[1]

        now = _now_utc()
        today = now.strftime("%Y-%m-%d")

        if last_day == today:
            return False, streak, 0.0, "already"

        if last_day:
            try:
                last_date = _dt.datetime.strptime(last_day, "%Y-%m-%d").date()
                yesterday = (now.date() - _dt.timedelta(days=1))
                if last_date == yesterday:
                    streak += 1
                else:
                    streak = 1
            except Exception:
                streak = 1
        else:
            streak = 1

        if streak >= 30:
            bonus = 0.10
        elif streak >= 14:
            bonus = 0.05
        elif streak >= 7:
            bonus = 0.03
        elif streak >= 3:
            bonus = 0.02
        else:
            bonus = 0.01

        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
        await db.execute(
            "UPDATE users SET daily_streak = ?, last_streak_day = ?, balance = balance + ? WHERE user_id = ?",
            (streak, today, bonus, _uid(user_id))
        )
        await db.commit()
        return True, streak, bonus, "ok"


async def get_wheel_info(user_id):
    """Возвращает (can_spin, last_spin_str, total_spins)."""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT last_wheel_spin, wheel_total_spins FROM users WHERE user_id = ?",
            (_uid(user_id),)
        )
        row = await cur.fetchone()
        if not row:
            return True, None, 0
        last_spin, total = row[0], row[1] or 0
        dt = _parse_dt(last_spin)
        if not dt:
            return True, last_spin, total
        if (_now_utc() - dt).total_seconds() >= 86400:
            return True, last_spin, total
        return False, last_spin, total


async def mark_wheel_spin(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0.0)", (_uid(user_id),))
        now = _now_utc().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute(
            "UPDATE users SET last_wheel_spin = ?, wheel_total_spins = wheel_total_spins + 1 WHERE user_id = ?",
            (now, _uid(user_id))
        )
        await db.commit()
