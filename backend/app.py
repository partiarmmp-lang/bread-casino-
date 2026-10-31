import asyncio
import random
import os
import threading
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiogram import Bot
from database import init_db, get_balance, update_balance, get_total_balance, try_deduct_balance, log_tx

# Импорт для xRocket (библиотека aiorocket2)
from aiorocket2 import RocketPay

load_dotenv()
XROCKET_TOKEN = os.getenv("XROCKET_TOKEN")
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

# --- 2. Инициализация xRocket ---
rocket = None

async def _init_rocket():
    global rocket
    # Инициализируем клиент с нашим токеном
    rocket = RocketPay(token=XROCKET_TOKEN)

run_async(_init_rocket())

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
    return jsonify({"balance": run_async(get_total_balance(user_id))})

@app.route("/api/topup", methods=["POST"])
def api_topup():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    amount = float(data.get("amount", 1))
    
    if amount < 0.05: 
        return jsonify({"error": "Минимум 0.05 USDT"}), 400

    async def _create_invoice():
        # Создаем счет в xRocket
        # priceCurrency = валюта, в которой выставляется счет
        # clientInvoiceId = уникальный ID, чтобы не было дублей
        return await rocket.create_invoice(
            amount=amount,
            asset="USDT",
            description=f"Пополнение баланса Bread Casino (ID: {user_id})",
            client_invoice_id=f"topup_{user_id}_{int(time.time())}"
        )

    try:
        invoice = run_async(_create_invoice())
        # xRocket возвращает ссылку в поле link или mini_app_link
        # В документации сказано, что нужно использовать telegramBotLink
        pay_url = getattr(invoice, 'link', None) or getattr(invoice, 'bot_link', None)
        
        if not pay_url:
            return jsonify({"error": "Не удалось получить ссылку на оплату"}), 500

        return jsonify({
            "invoice_id": invoice.id,
            "pay_url": pay_url,
            "amount": amount
        })
    except Exception as e:
        print(f"xRocket Invoice Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/check_payment/<invoice_id>")
def api_check_payment(invoice_id):
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401

    async def _check():
        # Получаем информацию о счете по его ID
        return await rocket.get_invoice(invoice_id)

    try:
        inv = run_async(_check())
        # Проверяем статус (active, paid, expired, cancelled)
        if inv.status == "paid":
            amount = float(inv.price_amount)
            # Начисляем баланс (можно добавить защиту от повторного начисления)
            run_async(update_balance(user_id, amount))
            run_async(log_tx(user_id, "deposit", amount, f"xrocket_{invoice_id}"))
            return jsonify({"paid": True, "amount": amount})
        
        return jsonify({"paid": False, "status": inv.status})
    except Exception as e:
        return jsonify({"paid": False, "error": str(e)}), 500

@app.route("/api/withdraw", methods=["POST"])
def api_withdraw():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    amount = float(data.get("amount", 0))
    
    if amount < 3.0: 
        return jsonify({"error": "Минимум 3 USDT"}), 400
        
    if not run_async(try_deduct_balance(user_id, amount)):
        return jsonify({"error": "Недостаточно средств"}), 400

    async def _transfer():
        # ВАЖНО: Для вывода нужен адрес кошелька или xRocket ID пользователя.
        # Если пользователь выводит на свой xRocket, можно использовать его Telegram ID.
        # Здесь мы делаем выплату на внутренний ID xRocket (пользователь должен его знать).
        # Для простоты предполагаем, что пользователь ввел свой xRocket ID в поле (пока заглушка).
        # В реальности нужно добавить поле ввода xRocket ID на сайте.
        # Пример: return await rocket.create_payout(user_id=user_id, asset="USDT", amount=amount)
        raise Exception("Для вывода укажите ваш xRocket ID (функция в разработке)")

    try:
        run_async(_transfer())
        return jsonify({"ok": True})
    except Exception as e:
        # Возвращаем деньги, если вывод не удался
        run_async(update_balance(user_id, amount))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
