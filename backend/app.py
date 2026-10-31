import asyncio
import random
import os
import threading
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from aiocryptopay import AioCryptoPay, Networks
from database import init_db, get_balance, update_balance, get_total_balance, try_deduct_balance, log_tx
from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiogram import Bot

load_dotenv()
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- 1. Один постоянный event loop на процесс ---
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)

def _start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=_start_loop, args=(_loop,), daemon=True).start()

def run_async(coro):
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()

# --- 2. Инициализация CryptoBot ---
crypto = None
async def _init_crypto():
    global crypto
    crypto = AioCryptoPay(token=CRYPTO_TOKEN, network=Networks.MAIN_NET)
run_async(_init_crypto())

# --- 3. Flask + CORS ---
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
run_async(init_db())

bot = Bot(token=BOT_TOKEN)

def get_telegram_user_id():
    user_id_header = request.headers.get("X-User-ID")
    if user_id_header:
        try: return int(user_id_header)
        except ValueError: pass
    init_data = request.headers.get("X-Telegram-Init-Data")
    if init_data:
        try:
            parsed = safe_parse_webapp_init_data(token=BOT_TOKEN, init_data=init_data)
            if parsed and parsed.user: return parsed.user.id
        except Exception: pass
    return None

# --- 4. Эндпоинты ---

@app.route("/api/balance")
def api_balance():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    balance = run_async(get_total_balance(user_id))
    return jsonify({"balance": balance})

@app.route("/api/spin", methods=["POST"])
def api_spin():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    amount = float(data.get("amount", 1))
    if not run_async(try_deduct_balance(user_id, amount)):
        return jsonify({"error": "Недостаточно средств"}), 400
    win = random.choice([True, False]) # Упрощенная логика для теста
    if win:
        run_async(update_balance(user_id, amount * 2))
    return jsonify({"win": win, "balance": run_async(get_total_balance(user_id))})

@app.route("/api/plinko", methods=["POST"])
def api_plinko():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    amount = float(data.get("amount", 1))
    
    if not run_async(try_deduct_balance(user_id, amount)):
        return jsonify({"error": "Недостаточно средств"}), 400

    # Логика Плинко: случайный множитель из массива
    multipliers = [10, 3, 1.5, 1, 0.5, 0.2, 0.2, 0.5, 1, 1.5, 3, 10]
    mult = random.choice(multipliers)
    win_amount = amount * mult
    
    if win_amount > 0:
        run_async(update_balance(user_id, win_amount))
    
    return jsonify({
        "multiplier": mult,
        "win_amount": win_amount,
        "balance": run_async(get_total_balance(user_id))
    })

@app.route("/api/topup", methods=["POST"])
def api_topup():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    amount = float(data.get("amount", 1))
    if amount < 0.05: return jsonify({"error": "Минимум 0.05 USDT"}), 400
    async def _create_invoice():
        return await crypto.create_invoice(asset="USDT", amount=amount, payload=str(user_id))
    try:
        invoice = run_async(_create_invoice())
        return jsonify({"invoice_id": invoice.invoice_id, "pay_url": invoice.bot_invoice_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/check_payment/<int:invoice_id>")
def api_check_payment(invoice_id):
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    async def _check():
        return await crypto.get_invoices(invoice_ids=invoice_id)
    try:
        inv = run_async(_check())
        if inv and inv.status == "paid":
            amount = float(inv.amount)
            run_async(update_balance(user_id, amount))
            return jsonify({"paid": True, "amount": amount})
        return jsonify({"paid": False, "status": inv.status if inv else "not_found"})
    except Exception as e:
        return jsonify({"paid": False, "error": str(e)}), 500

@app.route("/api/withdraw", methods=["POST"])
def api_withdraw():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    amount = float(data.get("amount", 0))
    if amount < 3.0: return jsonify({"error": "Минимум 3 USDT"}), 400
    if not run_async(try_deduct_balance(user_id, amount)):
        return jsonify({"error": "Недостаточно средств"}), 400
    async def _transfer():
        return await crypto.transfer(user_id=user_id, asset="USDT", amount=amount, spend_id=f"wd_{user_id}_{int(time.time())}")
    try:
        run_async(_transfer())
        return jsonify({"ok": True})
    except Exception as e:
        run_async(update_balance(user_id, amount))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
