import asyncio
import random
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from database import init_db, get_balance, update_balance, try_deduct_balance, log_tx

app = Flask(__name__)
CORS(app)

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

# --- ИГРА СЛОТЫ (МНОГОЛИНЕЙНЫЕ) ---
@app.route("/api/slots", methods=["POST"])
def play_slots():
    data = request.json
    user_id = data.get("user_id")
    bet_total = float(data.get("bet", 0.01)) # Общая ставка
    bet_line = float(data.get("bet_line", 0.01)) # Ставка на линию
    lines_count = int(data.get("lines", 1)) # Кол-во активных линий
    is_freespin = data.get("is_freespin", False)

    if not user_id:
        return jsonify({"error": "No user ID"}), 400

    # Если это не фриспин, списываем деньги
    if not is_freespin:
        if not run_async(try_deduct_balance(user_id, bet_total)):
            return jsonify({"error": "Недостаточно средств"}), 400

    # Генерация сетки 3x5
    symbols = ["🍒", "🍋", "🍇", "🔔", "⭐", "💎", "7️⃣"]
    weights = [30, 25, 20, 12, 8, 4, 1] # Вес для генерации
    
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

    # Логика подсчета выигрыша по линиям
    # Выигрышные комбинации (3, 4, 5 в ряд слева направо)
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

    # Считаем выигрыш только по активным линиям
    for r in range(lines_count):
        first_sym = grid[r][0]
        if first_sym == "⭐": continue # Скаттеры не дают выигрыш по линии
        
        count = 1
        for c in range(1, 5):
            if grid[r][c] == first_sym:
                count += 1
            else:
                break
        
        if count >= 3:
            mult = payouts.get(first_sym, {}).get(count, 0)
            if mult > 0:
                # Выигрыш = ставка на линию * множитель
                win_for_line = bet_line * mult
                total_win += win_for_line

    # Если выпало 3+ скаттера - даем фриспины (независимо от линий)
    if scatter_count >= 3:
        freespins_won = 10

    # Применяем множитель фриспина (x2) к выигрышу
    if is_freespin and total_win > 0:
        total_win *= 2

    # Начисляем деньги, если есть выигрыш
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
