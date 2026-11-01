import asyncio
import os
import re
import threading
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from database import (
    init_db, get_total_balance, get_balance, get_bonus_balance, update_balance, 
    try_deduct_balance, try_deduct_bonus, add_bonus, add_wager_progress,
    log_tx, set_referrer, get_referrers_chain, add_ref_earning
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

# ЭНДПОИНТ РЕГИСТРАЦИИ (ДЛЯ РЕФЕРАЛКИ И БОНУСА)
@app.route("/api/register", methods=["POST"])
def api_register():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json(silent=True) or {}
    ref_id = data.get("ref_id")
    
    try:
        # Пытаемся установить реферера (если юзер новый)
        is_new = False
        if ref_id:
            is_new = run_async(set_referrer(user_id, ref_id))
        
        # Даем бонус за первый вход, если баланс 0
        bal = run_async(get_total_balance(user_id))
        if bal == 0.0:
            run_async(add_bonus(user_id, 0.10, 3.0)) # Выдаем 0.10 в бонусный
            run_async(log_tx(user_id, "bonus", 0.10, "welcome"))
            
        return jsonify({"ok": True, "is_new": is_new})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ЕДИНАЯ ФУНКЦИЯ СПИСАНИЯ СТАВКИ (СНАЧАЛА БОНУС, ПОТОМ РЕАЛ)
def place_bet(user_id, amount):
    # 1. Пытаемся списать с бонусного
    if run_async(try_deduct_bonus(user_id, amount)):
        run_async(add_wager_progress(user_id, amount))
        run_async(log_tx(user_id, "bet", -amount, "bonus"))
        return "bonus"
    # 2. Если бонусных не хватило, списываем с реального
    if run_async(try_deduct_balance(user_id, amount)):
        run_async(add_wager_progress(user_id, amount))
        run_async(log_tx(user_id, "bet", -amount, "main"))
        return "main"
    return None

# Пример игры (Plinko) с новой логикой списания
@app.route("/api/play", methods=["POST"])
def api_play_plinko():
    user_id = get_telegram_user_id()
    data = request.get_json(silent=True) or request.args.to_dict() or {}
    try: bet = float(data.get("bet", 0.1))
    except: return jsonify({"error": "Неверная ставка"}), 400

    paid_with = place_bet(user_id, bet)
    if not paid_with: return jsonify({"error": "Недостаточно средств"}), 400

    import random
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
        # ПРОИГРЫШ: Начисляем реферальные проценты
        lvl1, lvl2, lvl3 = run_async(get_referrers_chain(user_id))
        if lvl1: run_async(add_ref_earning(lvl1, bet * 0.10)) # 10%
        if lvl2: run_async(add_ref_earning(lvl2, bet * 0.03)) # 3%
        if lvl3: run_async(add_ref_earning(lvl3, bet * 0.01)) # 1%

    real, bonus = run_async(get_balance(user_id)), run_async(get_bonus_balance(user_id))
    return jsonify({"success": True, "mult": mult, "win": win_amount, "real": real, "bonus": bonus})

# ... Остальные эндпоинты (topup, check_payment, withdraw) оставляем как были ...
# Скопируй их из предыдущего рабочего файла app.py