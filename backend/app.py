import asyncio
import os
import re
import threading
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from database import init_db, get_total_balance, update_balance, try_deduct_balance, log_tx

load_dotenv()

# ТОКЕН, КОТОРЫЙ ТЫ ПРИСЛАЛ В ПОСЛЕДНЕМ СООБЩЕНИИ
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
        bal = run_async(get_total_balance(user_id))
        return jsonify({"balance": bal})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/topup", methods=["GET", "POST"])
def api_topup():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json(silent=True) or request.args.to_dict() or {}
    try:
        amount = float(data.get("amount", 1))
    except (ValueError, TypeError):
        return jsonify({"error": "Неверная сумма"}), 400
    
    if amount < 0.05: 
        return jsonify({"error": "Минимум 0.05 USDT"}), 400

    headers = {
        "Authorization": f"Bearer {XROCKET_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # ПОЛЯ ИСПРАВЛЕНЫ ПО ДОКУМЕНТАЦИИ
    payload = {
        "priceAmount": str(amount),
        "priceCurrency": "USDT",
        "description": f"Bread Casino ID: {user_id}",
        "numPayments": 1
    }

    try:
        response = requests.post(f"{XROCKET_API_URL}/invoices", json=payload, headers=headers, timeout=15)
        
        try:
            res_data = response.json()
        except:
            res_data = {"raw_text": response.text}

        if response.status_code not in (200, 201):
            return jsonify({"error": f"xRocket вернул ошибку {response.status_code}: {res_data}"}), 500

        pay_url = res_data.get("url") or res_data.get("data", {}).get("url")
        
        if not pay_url:
            return jsonify({"error": f"xRocket не вернул ссылку. Ответ: {res_data}"}), 500

        return jsonify({
            "invoice_id": res_data.get("id"),
            "pay_url": pay_url,
            "amount": amount
        })
    except Exception as e:
        print(f"ОШИБКА xROCKET: {e}")
        return jsonify({"error": f"Ошибка соединения с xRocket: {str(e)}"}), 500

@app.route("/api/check_payment/<invoice_id>")
def api_check_payment(invoice_id):
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401

    headers = {"Authorization": f"Bearer {XROCKET_TOKEN}"}
    
    try:
        response = requests.get(f"{XROCKET_API_URL}/invoices/{invoice_id}", headers=headers, timeout=10)
        res_data = response.json()
        
        status = res_data.get("status")
        
        if status == "paid":
            amount = float(res_data.get("priceAmount", 0))
            run_async(update_balance(user_id, amount))
            run_async(log_tx(user_id, "deposit", amount, f"xrocket_{invoice_id}"))
            return jsonify({"paid": True, "amount": amount})
        
        return jsonify({"paid": False, "status": status})
    except Exception as e:
        return jsonify({"paid": False, "error": str(e)}), 500

@app.route("/api/withdraw", methods=["POST"])
def api_withdraw():
    user_id = get_telegram_user_id()
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get("amount", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Неверная сумма"}), 400
        
    target_id = data.get("xrocket_id")
    
    if amount < 3.0: return jsonify({"error": "Минимум 3 USDT"}), 400
    if not target_id: return jsonify({"error": "Укажите ваш xRocket ID"}), 400
        
    if not run_async(try_deduct_balance(user_id, amount)):
        return jsonify({"error": "Недостаточно средств"}), 400

    headers = {
        "Authorization": f"Bearer {XROCKET_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "userId": int(target_id),
        "currency": "USDT",
        "amount": str(amount),
        "description": "Withdraw from Bread Casino"
    }

    try:
        response = requests.post(f"{XROCKET_API_URL}/payouts", json=payload, headers=headers, timeout=15)
        res_data = response.json()
        
        if response.status_code not in (200, 201):
            run_async(update_balance(user_id, amount))
            return jsonify({"error": f"xRocket ошибка: {res_data}"}), 500

        run_async(log_tx(user_id, "withdraw", -amount, f"xrocket_payout_{target_id}"))
        return jsonify({"ok": True})
    except Exception as e:
        run_async(update_balance(user_id, amount))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)