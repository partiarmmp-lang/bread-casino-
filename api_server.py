import asyncio
import random
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from database import init_db, get_balance, update_balance, try_deduct_balance, log_tx

app = Flask(__name__)
CORS(app) # Разрешаем запросы с твоего сайта на GitHub

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

if __name__ == "__main__":
    # Render сам подставляет нужный порт в переменную окружения PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
