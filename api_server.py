import asyncio
import random
import os
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
from database import init_db, get_balance, update_balance, try_deduct_balance, log_tx
from aiocryptopay import AioCryptoPay, Networks

app = Flask(__name__)
CORS(app)

CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
crypto = AioCryptoPay(token=CRYPTO_TOKEN, network=Networks.MAIN_NET)

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

@app.route("/")
def index():
    return "BREAD CASINO API is running!"

@app.route("/api/balance", methods=["POST"])
def get_user_balance():
    data = request.json
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "No user ID"}), 400
    run_async(init_db())
    balance = run_async(get_balance(user_id))
    return jsonify({"balance": balance})

# --- СОЗДАНИЕ СЧЕТА НА ОПЛАТУ (ДЕПОЗИТ) ---
@app.route("/api/deposit", methods=["POST"])
def create_deposit():
    data = request.json
    user_id = data.get("user_id")
    amount = float(data.get("amount", 1.0))
    
    if not user_id or amount < 0.1:
        return jsonify({"error": "Минимальная сумма 0.1 USDT"}), 400

    async def create_inv():
        invoice = await crypto.create_invoice(asset='USDT', amount=amount)
        return invoice.bot_invoice_url
    
    try:
        pay_url = run_async(create_inv())
        return jsonify({"success": True, "pay_url": pay_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ВЫВОД СРЕДСТВ ---
@app.route("/api/withdraw", methods=["POST"])
def withdraw_funds():
    data = request.json
    user_id = data.get("user_id")
    amount = float(data.get("amount", 0))

    if not user_id or amount < 3.0:
        return jsonify({"error": "Минимум для вывода 3 USDT"}), 400

    if not run_async(try_deduct_balance(user_id, amount)):
        return jsonify({"error": "Недостаточно средств"}), 400

    async def do_transfer():
        try:
            await crypto.transfer(user_id=user_id, asset='USDT', amount=amount, spend_id=str(uuid.uuid4()))
            return True
        except Exception as e:
            run_async(update_balance(user_id, amount)) # Возврат при ошибке
            raise e

    try:
        run_async(do_transfer())
        run_async(log_tx(user_id, "withdraw", -amount, "web_crypto"))
        return jsonify({"success": True, "balance": run_async(get_balance(user_id))})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ИГРА PLINKO ---
@app.route("/api/play", methods=["POST"])
def play_plinko():
    data = request.json
    user_id = data.get("user_id")
    bet = float(data.get("bet", 0.1))
    
    if not user_id:
        return jsonify({"error": "No user ID"}), 400

    if not run_async(try_deduct_balance(user_id, bet)):
        return jsonify({"error": "Недостаточно средств"}), 400

    r = random.random()
    if r < 0.60: mult = random.choice([0.2, 0.5])
    elif r < 0.85: mult = random.choice([1, 1.5])
    elif r < 0.95: mult = 3
    else: mult = 10

    win_amount = bet * mult
    if win_amount > 0:
        run_async(update_balance(user_id, win_amount))
        run_async(log_tx(user_id, "win", win_amount, "web_plinko"))

    return jsonify({"success": True, "mult": mult, "win": win_amount, "balance": run_async(get_balance(user_id))})

# --- ИГРА CRASH ---
@app.route("/api/crash/start", methods=["POST"])
def crash_start():
    data = request.json
    user_id = data.get("user_id")
    bet = float(data.get("bet", 0.1))
    
    if not run_async(try_deduct_balance(user_id, bet)):
        return jsonify({"error": "Недостаточно средств"}), 400

    r = random.random() * 100
    if r < 50: crash_point = round(random.uniform(1.0, 1.5), 2)
    elif r < 80: crash_point = round(random.uniform(1.5, 2.5), 2)
    elif r < 95: crash_point = round(random.uniform(2.5, 5.0), 2)
    else: crash_point = round(random.uniform(5.0, 10.0), 2)

    return jsonify({"success": True, "crash_point": crash_point})

@app.route("/api/crash/cashout", methods=["POST"])
def crash_cashout():
    data = request.json
    user_id = data.get("user_id")
    bet = float(data.get("bet", 0.1))
    multiplier = float(data.get("multiplier", 1.0))
    
    win_amount = bet * multiplier
    run_async(update_balance(user_id, win_amount))
    run_async(log_tx(user_id, "win", win_amount, "web_crash"))

    return jsonify({"success": True, "balance": run_async(get_balance(user_id))})

# --- ИГРА СЛОТЫ ---
@app.route("/api/slots", methods=["POST"])
def play_slots():
    data = request.json
    user_id = data.get("user_id")
    bet_total = float(data.get("bet", 0.01))
    bet_line = float(data.get("bet_line", 0.01))
    lines_count = int(data.get("lines", 1))
    is_freespin = data.get("is_freespin", False)
    
    if not user_id:
        return jsonify({"error": "No user ID"}), 400

    if not is_freespin:
        if not run_async(try_deduct_balance(user_id, bet_total)):
            return jsonify({"error": "Недостаточно средств"}), 400

    symbols = ["🍒", "🍋", "🍇", "🔔", "⭐", "💎", "7️⃣"]
    weights = [30, 25, 20, 12, 8, 4, 1]
    grid = []
    scatter_count = 0
    
    for r in range(3):
        row = []
        for c in range(5):
            sym = random.choices(symbols, weights=weights, k=1)[0]
            row.append(sym)
            if sym == "⭐":
                scatter_count += 1
        grid.append(row)

    payouts = {
        "🍒": {3: 2, 4: 5, 5: 10},
        "🍋": {3: 3, 4: 8, 5: 15},
        "🍇": {3: 5, 4: 12, 5: 25},
        "🔔": {3: 10, 4: 25, 5: 50},
        "💎": {3: 20, 4: 50, 5: 100},
        "7️⃣": {3: 50, 4: 150, 5: 500}
    }

    total_win = 0.0
    freespins_won = 0

    for r in range(lines_count):
        first_sym = grid[r][0]
        if first_sym == "⭐": continue
        count = 1
        for c in range(1, 5):
            if grid[r][c] == first_sym:
                count += 1
            else:
                break
        if count >= 3:
            mult = payouts.get(first_sym, {}).get(count, 0)
            if mult > 0:
                win_for_line = bet_line * mult
                total_win += win_for_line

    if scatter_count >= 3:
        freespins_won = 10

    if is_freespin and total_win > 0:
        total_win *= 2

    if total_win > 0:
        run_async(update_balance(user_id, total_win))
        run_async(log_tx(user_id, "win", total_win, "web_slots"))

    return jsonify({
        "success": True,
        "grid": grid,
        "win": total_win,
        "freespins_won": freespins_won,
        "balance": run_async(get_balance(user_id))
    })

# --- КОЛЕСО ФОРТУНЫ ---
@app.route("/api/wheel/spin", methods=["POST"])
def wheel_spin():
    data = request.json
    user_id = data.get("user_id")
    
    if not user_id:
        return jsonify({"error": "No user ID"}), 400

    segments_indices = [0, 1, 2, 3, 4, 5, 6, 7]
    weights =        [30, 25, 20, 15, 5, 3, 1, 1] 
    
    win_index = random.choices(segments_indices, weights=weights, k=1)[0]
    
    payouts = [0.0, 0.01, 0.05, 0.10, 0.0, 0.50, 0.0, 1.00]
    win_amount = payouts[win_index]

    if win_amount > 0:
        run_async(update_balance(user_id, win_amount))
        run_async(log_tx(user_id, "win", win_amount, "web_wheel"))

    return jsonify({
        "success": True,
        "win_segment": win_index,
        "win_amount": win_amount,
        "balance": run_async(get_balance(user_id))
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)