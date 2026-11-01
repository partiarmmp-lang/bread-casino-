import asyncio
import os
import re
import threading
import requests
import random
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from database import (
    init_db, get_total_balance, get_balance, get_bonus_balance, update_balance, 
    try_deduct_balance, try_deduct_bonus, add_bonus, add_wager_progress,
    log_tx, set_referrer, get_referrers_chain, add_ref_earning, get_pool
)

load_dotenv()

XROCKET_TOKEN = os.getenv("XROCKET_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBJZCI6IjMwNzM2MiIsImp0aSI6ImFwcDozMDczNjI6ZDJjN2I2NDYtYzc3OC00ZjA3LWFkNDYtMGZiNDhjZTU3ZDU4IiwiaWF0IjoxNzkzNDY4MjYxfQ.a_Ml3oa5mBXnAMcQZDBS_G9JO-yu_TtUt10hfe3gaKE")
XROCKET_API_URL = "https://pay.api.xrocket.exchange/api/v1"

_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)

def _start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=_start_loop, args=(_loop,), daemon=True).start()

def run_async(coro):
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()

app = Flask(__name__)
CORS(app)

try:
    run_async(init_db())
    print("✅ База данных успешно инициализирована.")
except Exception as e:
    print(f"❌ ОШИБКА БД: {e}")

def get_telegram_user_id():
    user_id_arg = request.args.get("user_id")
    if user_id_arg:
        clean_id = re.sub(r'\D', '', str(user_id_arg))
        if clean_id: return int(clean_id)
    return None

# --- БАЗОВЫЕ ЭНДПОИНТЫ ---
@app.route("/api/balance")
def api_balance():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    try:
        real = run_async(get_balance(user_id))
        bonus = run_async(get_bonus_balance(user_id))
        return jsonify({"balance": real + bonus, "real": real, "bonus": bonus})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/register", methods=["POST"])
def api_register():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.args.to_dict() or {}
    ref_id = data.get("ref_id")
    try:
        is_new = False
        if ref_id: is_new = run_async(set_referrer(user_id, ref_id))
        bal = run_async(get_total_balance(user_id))
        if bal == 0.0:
            run_async(add_bonus(user_id, 0.10, 3.0))
            run_async(log_tx(user_id, "bonus", 0.10, "welcome"))
        return jsonify({"ok": True, "is_new": is_new})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ЛОГИКА СТАВОК ---
def place_bet(user_id, amount):
    if run_async(try_deduct_bonus(user_id, amount)):
        run_async(add_wager_progress(user_id, amount))
        run_async(log_tx(user_id, "bet", -amount, "bonus"))
        return "bonus"
    if run_async(try_deduct_balance(user_id, amount)):
        run_async(add_wager_progress(user_id, amount))
        run_async(log_tx(user_id, "bet", -amount, "main"))
        return "main"
    return None

def process_loss_refs(user_id, bet):
    lvl1, lvl2, lvl3 = run_async(get_referrers_chain(user_id))
    if lvl1: run_async(add_ref_earning(lvl1, bet * 0.10))
    if lvl2: run_async(add_ref_earning(lvl2, bet * 0.03))
    if lvl3: run_async(add_ref_earning(lvl3, bet * 0.01))

# --- PLINKO ---
@app.route("/api/play", methods=["POST"])
def api_play_plinko():
    user_id = get_telegram_user_id()
    data = request.get_json(silent=True) or request.args.to_dict() or {}
    try: bet = float(data.get("bet", 0.1))
    except: return jsonify({"error": "Неверная ставка"}), 400

    if not place_bet(user_id, bet): return jsonify({"error": "Недостаточно средств"}), 400

    r = random.random()
    if r < 0.60: mult = random.choice([0.2, 0.5])
    elif r < 0.85: mult = random.choice([1, 1.5])
    elif r < 0.95: mult = 3
    else: mult = 10

    win_amount = bet * mult
    if win_amount > 0:
        run_async(update_balance(user_id, win_amount))
        run_async(add_wager_progress(user_id, win_amount))
        run_async(log_tx(user_id, "win", win_amount, "plinko"))
    else:
        process_loss_refs(user_id, bet)

    real, bonus = run_async(get_balance(user_id)), run_async(get_bonus_balance(user_id))
    return jsonify({"success": True, "mult": mult, "win": win_amount, "real": real, "bonus": bonus})

# --- МИНЫ ---
active_mines = {}
def calc_mines_mult(opened, mines):
    if opened == 0: return 1.0
    mult = 1.0
    for i in range(opened): mult *= (25 - i) / (25 - mines - i)
    return mult * 0.97

@app.route("/api/mines/start", methods=["POST"])
def api_mines_start():
    user_id = get_telegram_user_id()
    data = request.get_json(silent=True) or {}
    try:
        bet = float(data.get("bet", 0.1))
        mines = int(data.get("mines", 2))
    except: return jsonify({"error": "Неверные данные"}), 400

    if not place_bet(user_id, bet): return jsonify({"error": "Недостаточно средств"}), 400

    bombs = set(random.sample(range(25), mines))
    active_mines[user_id] = {"bet": bet, "mines": mines, "bombs": bombs, "opened": set()}
    real, bonus = run_async(get_balance(user_id)), run_async(get_bonus_balance(user_id))
    return jsonify({"success": True, "real": real, "bonus": bonus})

@app.route("/api/mines/open", methods=["POST"])
def api_mines_open():
    user_id = get_telegram_user_id()
    data = request.get_json(silent=True) or {}
    cell = int(data.get("cell", -1))
    game = active_mines.get(user_id)
    if not game: return jsonify({"error": "Игра не найдена"}), 400

    if cell in game["bombs"]:
        del active_mines[user_id]
        process_loss_refs(user_id, game["bet"])
        return jsonify({"bomb": True, "success": True})

    game["opened"].add(cell)
    mult = calc_mines_mult(len(game["opened"]), game["mines"])
    return jsonify({"bomb": False, "mult": mult, "win": game["bet"] * mult})

@app.route("/api/mines/cashout", methods=["POST"])
def api_mines_cashout():
    user_id = get_telegram_user_id()
    game = active_mines.get(user_id)
    if not game or not game["opened"]: return jsonify({"error": "Нечего забирать"}), 400

    mult = calc_mines_mult(len(game["opened"]), game["mines"])
    win = game["bet"] * mult
    run_async(update_balance(user_id, win))
    run_async(add_wager_progress(user_id, win))
    run_async(log_tx(user_id, "win", win, "mines_cashout"))
    del active_mines[user_id]
    real, bonus = run_async(get_balance(user_id)), run_async(get_bonus_balance(user_id))
    return jsonify({"success": True, "win": win, "real": real, "bonus": bonus})

# --- ЛОТЕРЕЯ ---
@app.route("/api/lottery/buy", methods=["POST"])
def api_lottery_buy():
    user_id = get_telegram_user_id()
    data = request.get_json(silent=True) or {}
    try: count = int(data.get("count", 1))
    except: return jsonify({"error": "Неверное количество"}), 400

    cost = 0.5 * count
    if not place_bet(user_id, cost): return jsonify({"error": "Недостаточно средств"}), 400

    winning = sorted(random.sample(range(1, 26), 5))
    tickets = []
    total_win = 0.0

    for _ in range(count):
        ticket = sorted(random.sample(range(1, 26), 5))
        matches = len(set(ticket) & set(winning))
        mult = 0
        if matches == 5: mult = 10000
        elif matches == 4: mult = 50
        elif matches == 3: mult = 5
        elif matches == 2: mult = 1.5
        win = 0.5 * mult
        total_win += win
        tickets.append({"numbers": ticket, "matches": matches})

    if total_win > 0:
        run_async(update_balance(user_id, total_win))
        run_async(add_wager_progress(user_id, total_win))
        run_async(log_tx(user_id, "win", total_win, "lottery"))
    else:
        process_loss_refs(user_id, cost)

    real, bonus = run_async(get_balance(user_id)), run_async(get_bonus_balance(user_id))
    return jsonify({"success": True, "winning": winning, "tickets": tickets, "total_win": total_win, "real": real, "bonus": bonus})

# --- КЛИКЕР (ЧЕРЕЗ ОБЩИЙ ПУЛ БД) ---
async def _get_clicker_data(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0.0) ON CONFLICT DO NOTHING", int(user_id))
        row = await db.fetchrow("SELECT coins, energy, energy_limit, last_energy_reset FROM users WHERE user_id = $1", int(user_id))
        
        coins = row['coins'] if row and row['coins'] is not None else 0
        energy = row['energy'] if row and row['energy'] is not None else 100
        limit = row['energy_limit'] if row and row['energy_limit'] is not None else 100
        
        now = datetime.datetime.now()
        last = row['last_energy_reset'] if row else None
        
        if last:
            delta = (now - last).total_seconds()
            regen = int(delta / 10)
            if regen > 0:
                energy = min(limit, energy + regen)
                await db.execute("UPDATE users SET energy = $1, last_energy_reset = $2 WHERE user_id = $3", energy, now, int(user_id))
        else:
            await db.execute("UPDATE users SET last_energy_reset = $1 WHERE user_id = $2", now, int(user_id))
        return {"coins": coins, "energy": energy, "limit": limit}

@app.route("/api/clicker/data")
def api_clicker_data():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    try:
        data = run_async(_get_clicker_data(user_id))
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

async def _do_click(user_id):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT coins, energy FROM users WHERE user_id = $1", int(user_id))
        current_energy = row['energy'] if row and row['energy'] is not None else 0
        if current_energy < 1:
            return {"error": "Нет энергии"}
        new_coins = (row['coins'] if row and row['coins'] is not None else 0) + 1
        new_energy = current_energy - 1
        await db.execute("UPDATE users SET coins = $1, energy = $2, last_energy_reset = $3 WHERE user_id = $4", new_coins, new_energy, datetime.datetime.now(), int(user_id))
        return {"coins": new_coins, "energy": new_energy}

@app.route("/api/clicker/click", methods=["POST"])
def api_clicker_click():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    try:
        res = run_async(_do_click(user_id))
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/clicker/buy", methods=["POST"])
def api_clicker_buy():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json(silent=True) or {}
    item = data.get("item")
    
    async def do_buy(cost, reward_type):
        pool = await get_pool()
        async with pool.acquire() as db:
            row = await db.fetchrow("SELECT coins FROM users WHERE user_id = $1", int(user_id))
            if not row or (row['coins'] or 0) < cost: return False
            
            if reward_type == "freespin":
                await db.execute("UPDATE users SET coins = coins - $1, roulette_freespins = roulette_freespins + 1 WHERE user_id = $2", cost, int(user_id))
            elif reward_type == "bonus":
                await db.execute("UPDATE users SET coins = coins - $1, pending_deposit_bonus = pending_deposit_bonus + 10 WHERE user_id = $2", cost, int(user_id))
            elif reward_type == "energy":
                await db.execute("UPDATE users SET coins = coins - $1, energy_limit = energy_limit + 20 WHERE user_id = $2", cost, int(user_id))
            return True

    if item == "freespin":
        if run_async(do_buy(100, "freespin")): return jsonify({"success": True})
        else: return jsonify({"error": "Мало монет"}), 400
    elif item == "bonus10":
        if run_async(do_buy(300, "bonus")): return jsonify({"success": True})
        else: return jsonify({"error": "Мало монет"}), 400
    elif item == "energy":
        if run_async(do_buy(500, "energy")): return jsonify({"success": True})
        else: return jsonify({"error": "Мало монет"}), 400

    return jsonify({"error": "Товар не найден"}), 400

# --- ПЛАТЕЖИ XROCKET (ОПЛАТА) ---
@app.route("/api/topup", methods=["GET", "POST"])
def api_topup():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.args.to_dict() or {}
    try: amount = float(data.get("amount", 1))
    except: return jsonify({"error": "Неверная сумма"}), 400
    if amount < 0.05: return jsonify({"error": "Минимум 0.05 USDT"}), 400

    headers = {"Authorization": f"Bearer {XROCKET_TOKEN}", "Content-Type": "application/json"}
    payload = {"priceAmount": str(amount), "priceCurrency": "USDT", "description": f"Bread Casino ID: {user_id}", "numPayments": 1}

    try:
        response = requests.post(f"{XROCKET_API_URL}/invoices", json=payload, headers=headers, timeout=15)
        res_data = response.json()
        if response.status_code not in (200, 201): return jsonify({"error": f"xRocket: {res_data}"}), 500

        links = res_data.get("links", {})
        pay_url = links.get("webLink") or res_data.get("url") or links.get("telegramBotLink")
        if not pay_url: return jsonify({"error": "Нет ссылки"}), 500

        return jsonify({"invoice_id": res_data.get("id"), "pay_url": pay_url, "amount": amount})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/check_payment/<invoice_id>")
def api_check_payment(invoice_id):
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    headers = {"Authorization": f"Bearer {XROCKET_TOKEN}"}
    try:
        response = requests.get(f"{XROCKET_API_URL}/invoices/{invoice_id}", headers=headers, timeout=10)
        res_data = response.json()
        if res_data.get("status") == "paid":
            amount = float(res_data.get("priceAmount", 0))
            run_async(update_balance(user_id, amount))
            run_async(log_tx(user_id, "deposit", amount, f"xrocket_{invoice_id}"))
            return jsonify({"paid": True, "amount": amount})
        return jsonify({"paid": False})
    except Exception as e:
        return jsonify({"paid": False, "error": str(e)}), 500

@app.route("/api/withdraw", methods=["POST"])
def api_withdraw():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    try: amount = float(data.get("amount", 0))
    except: return jsonify({"error": "Неверная сумма"}), 400
    target_id = data.get("xrocket_id")
    if amount < 3.0: return jsonify({"error": "Минимум 3 USDT"}), 400
    if not target_id: return jsonify({"error": "Укажите xRocket ID"}), 400
    if not run_async(try_deduct_balance(user_id, amount)): return jsonify({"error": "Недостаточно средств"}), 400

    headers = {"Authorization": f"Bearer {XROCKET_TOKEN}", "Content-Type": "application/json"}
    payload = {"userId": int(target_id), "currency": "USDT", "amount": str(amount), "description": "Withdraw"}
    try:
        response = requests.post(f"{XROCKET_API_URL}/payouts", json=payload, headers=headers, timeout=15)
        if response.status_code not in (200, 201):
            run_async(update_balance(user_id, amount))
            return jsonify({"error": "Ошибка вывода"}), 500
        run_async(log_tx(user_id, "withdraw", -amount, f"xrocket_payout_{target_id}"))
        return jsonify({"ok": True})
    except Exception as e:
        run_async(update_balance(user_id, amount))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)