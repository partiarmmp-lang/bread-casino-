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

# --- 1. Один постоянный event loop на процесс (фикс для Render/Python 3.14) ---
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)

def _start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=_start_loop, args=(_loop,), daemon=True).start()

def run_async(coro):
    """Отправляет корутину в постоянный loop и ждёт результат."""
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()

# --- 2. Инициализация CryptoBot внутри loop ---
crypto = None

async def _init_crypto():
    global crypto
    crypto = AioCryptoPay(token=CRYPTO_TOKEN, network=Networks.MAIN_NET)

run_async(_init_crypto())

# --- 3. Flask + CORS ---
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Инициализация БД
run_async(init_db())

bot = Bot(token=BOT_TOKEN)

def get_telegram_user_id():
    """Достаёт user_id из initData Telegram WebApp."""
    init_data = (
        request.headers.get("X-Telegram-Init-Data")
        or request.args.get("init_data")
        or (request.get_json(silent=True) or {}).get("init_data")
    )
    if not init_data:
        return None
    try:
        parsed = safe_parse_webapp_init_data(token=BOT_TOKEN, init_data=init_data)
        if parsed and parsed.user:
            return parsed.user.id
    except Exception:
        pass
    return None

# --- 4. Эндпоинты ---

@app.route("/api/balance")
def api_balance():
    user_id = get_telegram_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized", "balance": 0}), 401
    balance = run_async(get_total_balance(user_id))
    return jsonify({"balance": balance})

@app.route("/api/spin", methods=["POST"])
def api_spin():
    user_id = get_telegram_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json() or {}
    color = data.get("color")
    amount = float(data.get("amount", 10))

    balance = run_async(get_balance(user_id))
    if balance < amount:
        return jsonify({"error": "Недостаточно средств"}), 400

    if not run_async(try_deduct_balance(user_id, amount)):
        return jsonify({"error": "Недостаточно средств"}), 400

    result = random.randint(0, 36)
    if result == 0:
        result_color = "zero"
    elif 1 <= result <= 10 or 19 <= result <= 28:
        result_color = "black"
    else:
        result_color = "red"

    win = (color == result_color)
    if win:
        multiplier = 14 if color == "zero" else 2
        win_amount = amount * multiplier
        run_async(update_balance(user_id, win_amount))
        message = f"Выпало {result} ({result_color}). Вы выиграли {win_amount:.2f} USDT!"
        won = True
    else:
        message = f"Выпало {result} ({result_color}). Вы проиграли."
        won = False

    new_balance = run_async(get_total_balance(user_id))
    return jsonify({
        "result": result, "color": result_color, "won": won,
        "message": message, "balance": new_balance
    })

@app.route("/api/topup", methods=["POST"])
def api_topup():
    user_id = get_telegram_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json() or {}
    try:
        amount = float(data.get("amount", 1))
    except (ValueError, TypeError):
        return jsonify({"error": "Неверная сумма"}), 400

    if amount < 0.05:
        return jsonify({"error": "Минимум 0.05 USDT"}), 400

    async def _create_invoice():
        return await crypto.create_invoice(asset="USDT", amount=amount, payload=str(user_id))

    try:
        invoice = run_async(_create_invoice())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "invoice_id": invoice.invoice_id,
        "pay_url": invoice.bot_invoice_url,
        "amount": amount
    })

@app.route("/api/check_payment/<int:invoice_id>")
def api_check_payment(invoice_id):
    user_id = get_telegram_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    async def _check():
        return await crypto.get_invoices(invoice_ids=invoice_id)

    try:
        inv = run_async(_check())
    except Exception as e:
        return jsonify({"paid": False, "error": str(e)}), 500

    if inv and inv.status == "paid":
        amount = float(inv.amount)
        run_async(update_balance(user_id, amount))
        run_async(log_tx(user_id, "deposit", amount, f"cryptobot_{invoice_id}"))
        return jsonify({"paid": True, "amount": amount})

    return jsonify({"paid": False, "status": inv.status if inv else "not_found"})

@app.route("/api/withdraw", methods=["POST"])
def api_withdraw():
    user_id = get_telegram_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json() or {}
    try:
        amount = float(data.get("amount", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Неверная сумма"}), 400

    if amount < 3.0:
        return jsonify({"error": "Минимум 3 USDT"}), 400

    balance = run_async(get_balance(user_id))
    if balance < amount:
        return jsonify({"error": "Недостаточно средств"}), 400

    if not run_async(try_deduct_balance(user_id, amount)):
        return jsonify({"error": "Недостаточно средств"}), 400

    async def _transfer():
        return await crypto.transfer(
            user_id=user_id, asset="USDT", amount=amount,
            spend_id=f"wd_{user_id}_{int(time.time())}"
        )

    try:
        run_async(_transfer())
    except Exception as e:
        run_async(update_balance(user_id, amount))
        return jsonify({"error": str(e)}), 500

    run_async(log_tx(user_id, "withdraw", -amount, "CryptoBot"))
    return jsonify({"ok": True, "amount": amount})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
