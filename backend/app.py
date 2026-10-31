import asyncio
import os
import re
import threading
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiogram import Bot
from database import init_db, get_total_balance, update_balance, try_deduct_balance, log_tx

from aiorocket2 import xRocketClient

load_dotenv()
XROCKET_TOKEN = os.getenv("XROCKET_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")

_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)

def _start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=_start_loop, args=(_loop,), daemon=True).start()

def run_async(coro):
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()

rocket = None

async def _init_rocket():
    global rocket
    rocket = xRocketClient(api_key=XROCKET_TOKEN)

run_async(_init_rocket())

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
run_async(init_db())
bot = Bot(token=BOT_TOKEN)

def get_telegram_user_id():
    user_id_header = request.headers.get("X-User-ID")
    if user_id_header:
        clean_id = re.sub(r'\D', '', str(user_id_header))
        if clean_id:
            try: return int(clean_id)
            except ValueError: pass
            
    init_data = request.headers.get("X-Telegram-Init-Data")
    if init_data:
        try:
            parsed = safe_parse_webapp_init_data(token=BOT_TOKEN, init_data=init_data)
            if parsed and parsed.user: return parsed.user.id
        except Exception: pass
    return None

@app.route("/api/balance")
def api_balance():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"balance": run_async(get_total_balance(user_id))})

@app.route("/api/topup", methods=["POST"])
def api_topup():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    
    # Читаем и JSON, и данные из формы
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    try:
        amount = float(data.get("amount", 1))
    except (ValueError, TypeError):
        return jsonify({"error": "Неверная сумма"}), 400
    
    if amount < 0.05: 
        return jsonify({"error": "Минимум 0.05 USDT"}), 400

    async def _create_invoice():
        return await rocket.create_invoice(
            currency="USDT",
            amount=amount,
            min_payment=0,
            num_payments=1,
            description=f"Bread Casino ID: {user_id}",
            hidden_message="Спасибо за пополнение!"
        )

    try:
        invoice = run_async(_create_invoice())
        pay_url = getattr(invoice, 'link', None)
        
        if not pay_url:
            return jsonify({"error": "Не удалось получить ссылку"}), 500

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
        return await rocket.get_invoice(invoice_id)

    try:
        inv = run_async(_check())
        if inv.status == "paid":
            amount = float(inv.price_amount)
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
    
    # Читаем и JSON, и данные из формы
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    try:
        amount = float(data.get("amount", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Неверная сумма"}), 400
        
    target_id = data.get("xrocket_id")
    
    if amount < 3.0: 
        return jsonify({"error": "Минимум 3 USDT"}), 400
    
    if not target_id:
        return jsonify({"error": "Укажите ваш xRocket ID"}), 400
        
    if not run_async(try_deduct_balance(user_id, amount)):
        return jsonify({"error": "Недостаточно средств"}), 400

    async def _payout():
        return await rocket.create_payout(
            user_id=int(target_id),
            currency="USDT",
            amount=amount,
            description="Withdraw from Bread Casino"
        )

    try:
        run_async(_payout())
        run_async(log_tx(user_id, "withdraw", -amount, f"xrocket_payout_{target_id}"))
        return jsonify({"ok": True})
    except Exception as e:
        # Возвращаем деньги, если выплата не прошла
        run_async(update_balance(user_id, amount))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
