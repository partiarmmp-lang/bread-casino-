import asyncio
import random
import os
import uuid
import aiohttp
import datetime
import logging
import aiosqlite
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, PreCheckoutQuery, LabeledPrice, WebAppInfo
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiocryptopay import AioCryptoPay, Networks

from database import (
    init_db, get_balance, get_bonus_balance, get_total_balance,
    update_balance, add_bonus, use_bonus, add_wager_progress,
    get_wager_info, is_new_user,
    get_referrer, get_referral_count, get_referral_earnings,
    add_ref_earning, add_loss,
    is_first_deposit, mark_deposit,
    set_referrer_full, get_referrers_chain,
    give_channel_bonus, has_deposit,
    get_partner_percent,
    add_freespins, get_freespins,
    use_roulette_freespin, use_lottery_tickets,
    add_luck_points, get_luck_points, spend_luck_points,
    log_luck_reward, get_luck_history,
    get_weekly_lost, reset_weekly, get_cashback_percent,
    get_monthly_deposits, reset_monthly,
    add_bonus_purchase,
    try_deduct_balance, try_deduct_bonus,
    transfer_between_users,
    log_tx, get_transactions,
    create_promo, delete_promo, list_promos, get_promo, activate_promo,
    create_check, get_check, claim_check,
    get_language, set_language,
    get_tap_data, update_tap_click, regenerate_energy, 
    deduct_coins, upgrade_energy_limit, add_pending_bonus, 
    get_pending_bonus, reset_pending_bonus, claim_daily_bonus,
    get_streak_info, claim_daily_streak, get_wheel_info, mark_wheel_spin,
    DB_NAME,
)

load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")

crypto = AioCryptoPay(token=CRYPTO_TOKEN, network=Networks.MAIN_NET)
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

BOT_USERNAME = ""
REF_PERCENT = 10
ADMIN_IDS = [7022463747] # ЗАМЕНИТЕ НА СВОЙ ID
MIN_DEPOSIT = 0.05
MIN_STARS_DEPOSIT = 50
MIN_WITHDRAW = 3.0
MIN_BET = 0.05
MAX_BET = 10000
MIN_TRANSFER = 0.01
MIN_CHECK = 0.01
MIN_PROMO = 0.01
CHANNEL_URL = "https://t.me/Caswino_big"
CHANNEL_USERNAME = "@Caswino_big"
CHANNEL_BONUS = 0.5
WAGER_MULTIPLIER = 3.0

MINES_GAMES = {}
FREESPIN_GAMES = {}
PRICE_GAMES = {}
PRICE_ROUND_SECONDS = 300
MIN_PRICE_BET = 0.10
MAX_PRICE_BET = 10.0

LOTTERY_PRICE = 0.5
LOTTERY_MAX = 25
LOTTERY_PICKS = 5
LOTTERY_PAYOUTS = {5: 10000, 4: 50, 3: 5, 2: 1.5}

BONUS_PACKAGES = {
    "start": {"price": 0.5, "bonus": 0.6, "fs": 3, "tickets": 0, "name": {"ru": "🥉 Стартовый", "en": "🥉 Starter"}},
    "medium": {"price": 2.0, "bonus": 2.5, "fs": 10, "tickets": 0, "name": {"ru": "🥈 Средний", "en": "🥈 Medium"}},
    "pro": {"price": 10.0, "bonus": 13.0, "fs": 30, "tickets": 20, "name": {"ru": "🥇 Про", "en": "🥇 Pro"}},
    "vip": {"price": 50.0, "bonus": 70.0, "fs": 100, "tickets": 100, "name": {"ru": "💎 VIP", "en": "💎 VIP"}},
}

class States(StatesGroup):
    waiting_deposit = State()
    waiting_bet = State()
    waiting_mines_bet = State()
    waiting_lottery_count = State()
    waiting_transfer_id = State()
    waiting_transfer_amount = State()
    waiting_promo = State()
    waiting_check_amount = State()
    waiting_check_claim = State()
    waiting_stars_amount = State()

TEXTS = {
    "choose_language": {"ru": "🌐 Выберите язык / Choose language:", "en": "🌐 Choose language / Выберите язык:"},
    "welcome_new": {"ru": "🎁 <b>Вам начислен приветственный бонус: 0.10 USDT!</b>\n\n", "en": "🎁 <b>You received a welcome bonus: 0.10 USDT!</b>\n\n"},
    "welcome": {"ru": "👋 <b>Добро пожаловать в казино!</b>\n\n💼 Ваш баланс: <b>{balance:.4f} USDT</b>\n\n🎮 Выбирайте игру:", "en": "👋 <b>Welcome to the casino!</b>\n\n💼 Your balance: <b>{balance:.4f} USDT</b>\n\n🎮 Choose a game:"},
    "main_menu": {"ru": "🏠 <b>Главное меню</b>\n\n💼 Баланс: <b>{balance:.4f} USDT</b>", "en": "🏠 <b>Main menu</b>\n\n💼 Balance: <b>{balance:.4f} USDT</b>"},
    "balance": {"ru": "💰 <b>Ваш баланс</b>\n\n💵 Основной: <b>{main:.4f} USDT</b>\n", "en": "💰 <b>Your balance</b>\n\n💵 Main: <b>{main:.4f} USDT</b>\n"},
    "balance_bonus": {"ru": "🎁 Бонусный: <b>{bonus:.4f} USDT</b>\n📊 Вейджер: <b>{done:.2f} / {req:.2f}</b>\n", "en": "🎁 Bonus: <b>{bonus:.4f} USDT</b>\n📊 Wager: <b>{done:.2f} / {req:.2f}</b>\n"},
    "balance_fs": {"ru": "\n🎡 Фриспинов: <b>{r_fs}</b>\n🎟️ Билетов: <b>{l_fs}</b>", "en": "\n🎡 Freespins: <b>{r_fs}</b>\n🎟️ Tickets: <b>{l_fs}</b>"},
    "back": {"ru": "⬅️ Назад", "en": "⬅️ Back"},
    "cancel": {"ru": "❌ Отмена", "en": "❌ Cancel"},
    "not_enough": {"ru": "❌ Недостаточно средств!", "en": "❌ Not enough funds!"},
    "enter_number": {"ru": "❌ Введите число", "en": "❌ Enter a number"},
    "min_bet": {"ru": "❌ Минимум {x} USDT", "en": "❌ Minimum {x} USDT"},
    "bet_range": {"ru": "❌ Ставка от {a} до {b} USDT", "en": "❌ Bet from {a} to {b} USDT"},
    "choose_bet": {"ru": "{title}\n\nВыберите ставку (мин. {x} USDT):", "en": "{title}\n\nChoose your bet (min. {x} USDT):"},
    "your_bet": {"ru": "{title}\n\n💰 Ставка: <b>{amount} USDT</b>\n\n{hint}", "en": "{title}\n\n💰 Bet: <b>{amount} USDT</b>\n\n{hint}"},
    "change_bet": {"ru": "⬅️ Изменить ставку", "en": "⬅️ Change bet"},
    "enter_amount": {"ru": "✏️ <b>Введите сумму</b>\n\nМинимум: {min} USDT\nМаксимум: {max} USDT", "en": "✏️ <b>Enter amount</b>\n\nMinimum: {min} USDT\nMaximum: {max} USDT"},
    "win": {"ru": "🎉 Выигрыш: <b>{x:.4f} USDT</b>", "en": "🎉 Win: <b>{x:.4f} USDT</b>"},
    "lose": {"ru": "😢 Проигрыш.", "en": "😢 You lost."},
    "history": {"ru": "📜 <b>Последние операции</b>\n", "en": "📜 <b>Recent transactions</b>\n"},
    "history_empty": {"ru": "📜 <b>История операций</b>\n\nПока пусто.", "en": "📜 <b>Transaction history</b>\n\nEmpty for now."},
    "promo_enter": {"ru": "🎟️ <b>Введите промокод</b>\n\nЕсли у вас есть код от администратора — введите его сообщением.", "en": "🎟️ <b>Enter promo code</b>\n\nIf you have an admin code — send it as a message."},
    "promo_ok": {"ru": "✅ <b>Промокод активирован!</b>\n\n💰 Начислено: <b>+{x:.4f} USDT</b>\n💼 Баланс: <b>{bal:.4f} USDT</b>", "en": "✅ <b>Promo activated!</b>\n\n💰 Credited: <b>+{x:.4f} USDT</b>\n💼 Balance: <b>{bal:.4f} USDT</b>"},
    "promo_not_found": {"ru": "❌ Код не найден", "en": "❌ Code not found"},
    "promo_limit": {"ru": "❌ Лимит активаций исчерпан", "en": "❌ Activation limit reached"},
    "promo_already": {"ru": "❌ Вы уже активировали этот код", "en": "❌ You already activated this code"},
    "check_menu_title": {"ru": "🎁 <b>Чеки</b>\n\n💵 Ваш баланс: <b>{bal:.4f} USDT</b>\nМинимум чека: <b>{min} USDT</b>\n\nСоздайте чек и отправьте код (или ссылку) любому — он получит деньги на баланс.\nИли активируйте чужой чек.", "en": "🎁 <b>Checks</b>\n\n💵 Your balance: <b>{bal:.4f} USDT</b>\nMin check: <b>{min} USDT</b>\n\nCreate a check and send the code (or link) to anyone — they get the money on their balance.\nOr claim someone else's check."},
    "check_create": {"ru": "🎁 <b>Создать чек</b>\n\n💵 Баланс: <b>{bal:.4f} USDT</b>\nМинимум: <b>{min} USDT</b>\n\nВведите сумму чека:", "en": "🎁 <b>Create check</b>\n\n💵 Balance: <b>{bal:.4f} USDT</b>\nMinimum: <b>{min} USDT</b>\n\nEnter check amount:"},
    "check_created": {"ru": "✅ <b>Чек создан!</b>\n\n💰 Сумма: <b>{x:.4f} USDT</b>\n🎟️ Код: <code>{code}</code>\n\n🔗 Ссылка:\n<code>{link}</code>\n\nОтправьте код или ссылку любому — он получит деньги на баланс.", "en": "✅ <b>Check created!</b>\n\n💰 Amount: <b>{x:.4f} USDT</b>\n🎟️ Code: <code>{code}</code>\n\n🔗 Link:\n<code>{link}</code>\n\nSend the code or link to anyone — they get the money on their balance."},
    "check_claim": {"ru": "🎟️ <b>Активировать чек</b>\n\nВведите код чека:", "en": "🎟️ <b>Claim check</b>\n\nEnter the check code:"},
    "check_ok": {"ru": "🎁 <b>Чек активирован!</b>\n\n💰 Начислено: <b>+{x:.4f} USDT</b>\n💼 Баланс: <b>{bal:.4f} USDT</b>", "en": "🎁 <b>Check claimed!</b>\n\n💰 Credited: <b>+{x:.4f} USDT</b>\n💼 Balance: <b>{bal:.4f} USDT</b>"},
    "check_not_found": {"ru": "❌ Чек не найден", "en": "❌ Check not found"},
    "check_already": {"ru": "❌ Чек уже активирован", "en": "❌ Check already claimed"},
    "transfer_title": {"ru": "🎁 <b>Подарить USDT</b>\n\n💵 Ваш баланс: <b>{bal:.4f} USDT</b>\nМинимум перевода: <b>{min} USDT</b>\n\nВведите <b>ID игрока</b>, которому хотите подарить:", "en": "🎁 <b>Gift USDT</b>\n\n💵 Your balance: <b>{bal:.4f} USDT</b>\nMin transfer: <b>{min} USDT</b>\n\nEnter <b>player ID</b> to gift:"},
    "transfer_self": {"ru": "❌ Нельзя подарить самому себе", "en": "❌ Can't gift yourself"},
    "transfer_amount": {"ru": "🎁 Получатель: <code>{id}</code>\n\nВведите сумму для подарка (минимум {min} USDT):", "en": "🎁 Recipient: <code>{id}</code>\n\nEnter gift amount (minimum {min} USDT):"},
    "transfer_sent": {"ru": "✅ <b>Подарок отправлен!</b>\n\n👤 Получатель: <code>{id}</code>\n💰 Сумма: <b>{x:.4f} USDT</b>", "en": "✅ <b>Gift sent!</b>\n\n👤 Recipient: <code>{id}</code>\n💰 Amount: <b>{x:.4f} USDT</b>"},
    "transfer_received": {"ru": "🎁 <b>Вам подарок!</b>\n\n👤 От: <code>{id}</code>\n💰 Сумма: <b>{x:.4f} USDT</b> на основной баланс", "en": "🎁 <b>You got a gift!</b>\n\n👤 From: <code>{id}</code>\n💰 Amount: <b>{x:.4f} USDT</b> to main balance"},
    "deposit_title": {"ru": "💳 <b>Пополнение</b>\n\nМинимум: <b>{min} USDT</b>\n\n🎁 Бонус 50% (1-й депозит), 20% (следующие)\nОт 10 USDT → +10 фриспинов и билетов\n\nВыберите сумму:", "en": "💳 <b>Deposit</b>\n\nMinimum: <b>{min} USDT</b>\n\n🎁 Bonus 50% (first deposit), 20% (next)\nFrom 10 USDT → +10 freespins and tickets\n\nChoose amount:"},
    "deposit_custom": {"ru": "✏️ <b>Введите сумму</b>\n\nМинимум: {min} USDT", "en": "✏️ <b>Enter amount</b>\n\nMinimum: {min} USDT"},
    "deposit_too_much": {"ru": "❌ Слишком много", "en": "❌ Too much"},
    "deposit_cancelled": {"ru": "Отменено.", "en": "Cancelled."},
    "deposit_invoice": {"ru": "💳 Счёт на <b>{x} USDT</b>.\n\n🎁 <b>Бонус: +{bonus:.4f} USDT ({rate})</b>{extra}\n⚠️ Отыграть ×{wager:.0f}.\n\nОплатите:", "en": "💳 Invoice for <b>{x} USDT</b>.\n\n🎁 <b>Bonus: +{bonus:.4f} USDT ({rate})</b>{extra}\n⚠️ Wager ×{wager:.0f}.\n\nPay:"},
    "deposit_paid": {"ru": "✅ <b>Пополнено {x:.4f} USDT!</b>", "en": "✅ <b>Deposited {x:.4f} USDT!</b>"},
    "deposit_not_paid": {"ru": "⏳ Платёж не поступил", "en": "⏳ Payment not received"},
    "withdraw_title": {"ru": "💸 <b>Вывод</b>\n\n💵 Основной: <b>{main:.4f} USDT</b>\n", "en": "💸 <b>Withdraw</b>\n\n💵 Main: <b>{main:.4f} USDT</b>\n"},
    "withdraw_bonus": {"ru": "\n🎁 Бонусный: <b>{bonus:.4f} USDT</b>\n📊 Вейджер: <b>{done:.2f} / {req:.2f}</b>\n⚠️ Отыграй его полностью.\n", "en": "\n🎁 Bonus: <b>{bonus:.4f} USDT</b>\n📊 Wager: <b>{done:.2f} / {req:.2f}</b>\n⚠️ Wager it fully first.\n"},
    "withdraw_min": {"ru": "\nМинимум: <b>{min} USDT</b>\n\nВыберите:", "en": "\nMinimum: <b>{min} USDT</b>\n\nChoose:"},
    "withdraw_all": {"ru": "Всё", "en": "All"},
    "withdraw_ok": {"ru": "✅ <b>Выведено {x:.4f} USDT</b>\n\n💼 Остаток: <b>{bal:.4f} USDT</b>", "en": "✅ <b>Withdrawn {x:.4f} USDT</b>\n\n💼 Remaining: <b>{bal:.4f} USDT</b>"},
    "withdraw_empty": {"ru": "⏳ Касса пуста. Попробуйте позже.", "en": "⏳ Cashier is empty. Try later."},
    "withdraw_error": {"ru": "❌ Ошибка вывода: {e}", "en": "❌ Withdraw error: {e}"},
    "stats": {"ru": "📊 <b>Статистика</b>\n\n👤 ID: <code>{id}</code>\n💼 Баланс: <b>{bal:.4f} USDT</b>\n👥 Рефералов: <b>{refs}</b>\n💰 С рефералов: <b>{earn:.4f} USDT</b>", "en": "📊 <b>Statistics</b>\n\n👤 ID: <code>{id}</code>\n💼 Balance: <b>{bal:.4f} USDT</b>\n👥 Referrals: <b>{refs}</b>\n💰 From referrals: <b>{earn:.4f} USDT</b>"},
    "referrals": {"ru": "👥 <b>Партнёрская программа</b>\n\n• 1 уровень: <b>10%</b>\n• 2 уровень: <b>3%</b>\n• 3 уровень: <b>1%</b>\n\n📊 Рефералов: <b>{count}</b>\n💰 Заработано: <b>{earn:.4f} USDT</b>\n\n🔗 Ваша ссылка:\n<code>{link}</code>", "en": "👥 <b>Affiliate program</b>\n\n• Level 1: <b>10%</b>\n• Level 2: <b>3%</b>\n• Level 3: <b>1%</b>\n\n📊 Referrals: <b>{count}</b>\n💰 Earned: <b>{earn:.4f} USDT</b>\n\n🔗 Your link:\n<code>{link}</code>"},
    "bonuses_title": {"ru": "🎁 <b>Ваши бонусы</b>\n\n", "en": "🎁 <b>Your bonuses</b>\n\n"},
    "bonuses_none": {"ru": "Активных бонусов нет.\n\n", "en": "No active bonuses.\n\n"},
    "bonuses_bonus": {"ru": "💎 Бонусный: <b>{bonus:.4f} USDT</b>\n📊 Отыграно: <b>{done:.2f} / {req:.2f}</b>\n\n", "en": "💎 Bonus: <b>{bonus:.4f} USDT</b>\n📊 Wagered: <b>{done:.2f} / {req:.2f}</b>\n\n"},
    "luck_title": {"ru": "🍀 <b>Прогресс удачи</b>\n\n⭐ Текущие очки: <b>{points}</b>\n📊 Всего накоплено: <b>{total}</b>\n\n<b>Как получать очки:</b>\n• Ставка в игре → +1 очко\n• Депозит 1 USDT → +10 очков\n• Новый реферал → +50 очков\n• Подписка на канал → +100 очков\n• Покупка бонуса → +20 очков за 1 USDT\n\n<b>Награды за 100 очков:</b>\n• 50% — 0.5 USDT бонус\n• 30% — 1 USDT бонус\n• 15% — 5 фриспинов\n• 5% — ДЖЕКПОТ 10 USDT + 20 фриспинов", "en": "🍀 <b>Luck progress</b>\n\n⭐ Current points: <b>{points}</b>\n📊 Total earned: <b>{total}</b>\n\n<b>How to earn points:</b>\n• Bet in game → +1 point\n• Deposit 1 USDT → +10 points\n• New referral → +50 points\n• Channel subscription → +100 points\n• Bonus purchase → +20 points per 1 USDT\n\n<b>Rewards for 100 points:</b>\n• 50% — 0.5 USDT bonus\n• 30% — 1 USDT bonus\n• 15% — 5 freespins\n• 5% — JACKPOT 10 USDT + 20 freespins"},
    "luck_not_enough": {"ru": "❌ Нужно 100 очков. У тебя {x}", "en": "❌ Need 100 points. You have {x}"},
    "luck_open": {"ru": "🎊 <b>Подарок открыт!</b>\n\n🏆 Ты получил: <b>{name}</b>\n🎁 {value}\n\n⚠️ Бонус нужно отыграть x3 перед выводом.\n\n⭐ Осталось очков: <b>{points}</b>", "en": "🎊 <b>Gift opened!</b>\n\n🏆 You got: <b>{name}</b>\n🎁 {value}\n\n⚠️ Bonus must be wagered x3 before withdrawal.\n\n⭐ Points left: <b>{points}</b>"},
    "luck_history": {"ru": "📜 <b>Последние награды</b>\n", "en": "📜 <b>Recent rewards</b>\n"},
    "luck_history_empty": {"ru": "📜 <b>История наград</b>\n\nПока пусто.", "en": "📜 <b>Reward history</b>\n\nEmpty for now."},
    "cashback_title": {"ru": "💸 <b>Еженедельный кэшбэк</b>\n\n📉 Проиграно за неделю: <b>{lost:.2f} USDT</b>\n🎁 Твой кэшбэк: <b>{percent}%</b>\n💰 К получению: <b>{cashback:.2f} USDT</b>\n\n<b>Как повысить:</b>\n• 10+ USDT → 5%\n• 50+ USDT → 7%\n• 100+ USDT → 10%\n• 500+ USDT → 15%", "en": "💸 <b>Weekly cashback</b>\n\n📉 Lost this week: <b>{lost:.2f} USDT</b>\n🎁 Your cashback: <b>{percent}%</b>\n💰 To receive: <b>{cashback:.2f} USDT</b>\n\n<b>How to increase:</b>\n• 10+ USDT → 5%\n• 50+ USDT → 7%\n• 100+ USDT → 10%\n• 500+ USDT → 15%"},
    "cashback_ok": {"ru": "✅ <b>Кэшбэк получен!</b>\n\n💰 +{x:.4f} USDT на баланс", "en": "✅ <b>Cashback received!</b>\n\n💰 +{x:.4f} USDT to balance"},
    "cashback_small": {"ru": "❌ Слишком маленький проигрыш", "en": "❌ Loss is too small"},
    "channel_bonus_title": {"ru": "📢 <b>Бонус за подписку — {bonus} USDT!</b>\n\n1. Подпишись: {url}\n2. Вернись и нажми «✅ Я подписался»\n\n💰 Бонус: <b>+{bonus} USDT</b> (вейджер x3) +100 очков удачи", "en": "📢 <b>Subscribe bonus — {bonus} USDT!</b>\n\n1. Subscribe: {url}\n2. Come back and press «✅ I subscribed»\n\n💰 Bonus: <b>+{bonus} USDT</b> (wager x3) +100 luck points"},
    "channel_bonus_no_dep": {"ru": "📢 <b>Бонус за подписку</b>\n\nБонус доступен только после первого депозита.", "en": "📢 <b>Subscribe bonus</b>\n\nBonus is available after your first deposit."},
    "channel_bonus_ok": {"ru": "✅ <b>Бонус {bonus} USDT начислен!</b>\n\n⚠️ Вейджер x3.\n+100 очков удачи\n\n💼 Баланс: <b>{bal:.4f} USDT</b>", "en": "✅ <b>Bonus {bonus} USDT credited!</b>\n\n⚠️ Wager x3.\n+100 luck points\n\n💼 Balance: <b>{bal:.4f} USDT</b>"},
    "channel_bonus_already": {"ru": "Вы уже получили этот бонус", "en": "You already got this bonus"},
    "channel_bonus_not_sub": {"ru": "❌ Вы ещё не подписались", "en": "❌ You haven't subscribed yet"},
    "channel_bonus_error": {"ru": "⚠️ Ошибка проверки. Попробуйте ещё раз.", "en": "⚠️ Check error. Try again."},
    "bonus_shop_title": {"ru": "🛒 <b>Магазин бонусов</b>\n\nПокупай бонус-пакеты и получай больше на игру:\n\n", "en": "🛒 <b>Bonus shop</b>\n\nBuy bonus packages and get more to play:\n\n"},
    "bonus_shop_footer": {"ru": "⚠️ Все бонусы с вейджером x3.", "en": "⚠️ All bonuses have x3 wager."},
    "bonus_bought": {"ru": "✅ <b>Пакет {name} куплен!</b>\n\n💰 Списано: {price} USDT\n🎁 Начислено бонусом: <b>{bonus} USDT</b> (вейджер x3)\n", "en": "✅ <b>Package {name} purchased!</b>\n\n💰 Charged: {price} USDT\n🎁 Bonus credited: <b>{bonus} USDT</b> (wager x3)\n"},
    "bonus_bought_fs": {"ru": "🎡 Фриспинов: +{x}\n", "en": "🎡 Freespins: +{x}\n"},
    "bonus_bought_tickets": {"ru": "🎟️ Билетов: +{x}\n", "en": "🎟️ Tickets: +{x}\n"},
    "bonus_bought_luck": {"ru": "⭐ Очков удачи: +{x}\n\n💼 Баланс: <b>{bal:.4f} USDT</b>", "en": "⭐ Luck points: +{x}\n\n💼 Balance: <b>{bal:.4f} USDT</b>"},
    "need_main_balance": {"ru": "❌ Нужно {x} USDT на основном балансе", "en": "❌ Need {x} USDT on main balance"},
    "mines_title": {"ru": "💣 <b>Мины</b>\n\nСетка 5×5.\n\nВыберите количество мин:", "en": "💣 <b>Mines</b>\n\n5×5 grid.\n\nChoose number of mines:"},
    "mines_count": {"ru": "💣 <b>Мины</b>: {n} бомб\n\nВыберите ставку:", "en": "💣 <b>Mines</b>: {n} bombs\n\nChoose your bet:"},
    "mines_custom": {"ru": "✏️ <b>Введите ставку ({n} бомб)</b>\n\nМинимум: {min} USDT", "en": "✏️ <b>Enter bet ({n} bombs)</b>\n\nMinimum: {min} USDT"},
    "mines_game": {"ru": "💣 <b>Мины {n}</b>\n\n💰 Ставка: <b>{bet} USDT</b>\n📦 Открыто: <b>{opened}</b>/25\n✖️ Множитель: <b>x{mult:.2f}</b>\n💎 Можно забрать: <b>{potential:.4f} USDT</b>", "en": "💣 <b>Mines {n}</b>\n\n💰 Bet: <b>{bet} USDT</b>\n📦 Opened: <b>{opened}</b>/25\n✖️ Multiplier: <b>x{mult:.2f}</b>\n💎 Can cash out: <b>{potential:.4f} USDT</b>"},
    "mines_cashout_btn": {"ru": "💰 Забрать {x:.4f} USDT (x{mult:.2f})", "en": "💰 Cash out {x:.4f} USDT (x{mult:.2f})"},
    "mines_start_btn": {"ru": "🎯 Ставка: {bet} — открывай клетки!", "en": "🎯 Bet: {bet} — open cells!"},
    "mines_cancel": {"ru": "❌ Отменить", "en": "❌ Cancel"},
    "mines_safe": {"ru": "💎 Безопасно!", "en": "💎 Safe!"},
    "mines_bomb": {"ru": "💥 Бомба!", "en": "💥 Bomb!"},
    "mines_bomb_text": {"ru": "💥 <b>БОМБА!</b>\n\n❌ Проиграли <b>{bet} USDT</b>\n\n💼 Баланс: <b>{bal:.4f} USDT</b>", "en": "💥 <b>BOMB!</b>\n\n❌ Lost <b>{bet} USDT</b>\n\n💼 Balance: <b>{bal:.4f} USDT</b>"},
    "mines_cashout_text": {"ru": "💰 <b>Забрали выигрыш!</b>\n\n📦 {opened}\n✖️ x{mult:.2f}\n💎 <b>{x:.4f} USDT</b>\n\n💼 Баланс: <b>{bal:.4f} USDT</b>", "en": "💰 <b>Cashed out!</b>\n\n📦 {opened}\n✖️ x{mult:.2f}\n💎 <b>{x:.4f} USDT</b>\n\n💼 Balance: <b>{bal:.4f} USDT</b>"},
    "mines_cancelled": {"ru": "❌ Отменено.\n\n💼 Баланс: <b>{bal:.4f} USDT</b>", "en": "❌ Cancelled.\n\n💼 Balance: <b>{bal:.4f} USDT</b>"},
    "mines_new_game": {"ru": "🎮 Новая игра", "en": "🎮 New game"},
    "mines_to_menu": {"ru": "🏠 В меню", "en": "🏠 To menu"},
    "mines_open_first": {"ru": "Откройте клетку", "en": "Open a cell first"},
    "mines_not_found": {"ru": "Игра не найдена", "en": "Game not found"},
    "already_opened": {"ru": "Уже открыто", "en": "Already opened"},
    "lottery_title": {"ru": "🎟️ <b>Лотерея</b>\n\nБилет: <b>{price} USDT</b>\n5 из {max}.\n\n<b>Выплаты:</b>\n5 из 5 → x10000\n4 из 5 → x50\n3 из 5 → x5\n2 из 5 → x1.5\n\n🎁 Бесплатных билетов: <b>{tickets}</b>", "en": "🎟️ <b>Lottery</b>\n\nTicket: <b>{price} USDT</b>\n5 out of {max}.\n\n<b>Payouts:</b>\n5 of 5 → x10000\n4 of 5 → x50\n3 of 5 → x5\n2 of 5 → x1.5\n\n🎁 Free tickets: <b>{tickets}</b>"},
    "lottery_how_many": {"ru": "✏️ <b>Сколько билетов?</b>\n\nЦена: {price} USDT за билет\nМаксимум: 100", "en": "✏️ <b>How many tickets?</b>\n\nPrice: {price} USDT per ticket\nMaximum: 100"},
    "lottery_int_only": {"ru": "❌ Введите целое число", "en": "❌ Enter an integer"},
    "lottery_range": {"ru": "❌ От 1 до 100 билетов", "en": "❌ From 1 to 100 tickets"},
    "lottery_no_tickets": {"ru": "❌ У вас нет бесплатных билетов", "en": "❌ You have no free tickets"},
    "lottery_not_enough": {"ru": "❌ Не хватает билетов", "en": "❌ Not enough tickets"},
    "lottery_used": {"ru": "🎁 Использовано {x} билетов (выигрыш в бонус)", "en": "🎁 Used {x} tickets (win goes to bonus)"},
    "lottery_result": {"ru": "{header}\n\n🎯 Выигрышная: <b>{winning}</b>\n\n<b>Ваши билеты:</b>\n{tickets}\n\n{result}", "en": "{header}\n\n🎯 Winning: <b>{winning}</b>\n\n<b>Your tickets:</b>\n{tickets}\n\n{result}"},
    "lottery_free_header": {"ru": "🎁 <b>Бесплатная лотерея!</b>", "en": "🎁 <b>Free lottery!</b>"},
    "lottery_header": {"ru": "🎟️ <b>Лотерея</b>", "en": "🎟️ <b>Lottery</b>"},
    "lottery_win_free": {"ru": "💎 <b>Выигрыш: {x:.4f} USDT (в бонус x3)</b>", "en": "💎 <b>Win: {x:.4f} USDT (to bonus x3)</b>"},
    "lottery_win": {"ru": "💎 <b>Общий выигрыш: {x:.4f} USDT</b>", "en": "💎 <b>Total win: {x:.4f} USDT</b>"},
    "lottery_no_win": {"ru": "😢 Увы, ничего не выиграли", "en": "😢 No win this time"},
    "freespin_title": {"ru": "🎁 <b>ФРИСПИН (x{mult})</b>", "en": "🎁 <b>FREESPIN (x{mult})</b>"},
    "freespin_no_luck": {"ru": "😢 Не повезло", "en": "😢 No luck"},
    "freespin_more": {"ru": "⭐ Ещё +{x} фриспинов!", "en": "⭐ +{x} more freespins!"},
    "freespin_left": {"ru": "🎁 Осталось: <b>{x}</b>", "en": "🎁 Left: <b>{x}</b>"},
    "freespin_over": {"ru": "🏁 Фриспины закончились.", "en": "🏁 Freespins are over."},
    "freespin_btn": {"ru": "🎁 Фриспин [{x} ост.]", "en": "🎁 Freespin [{x} left]"},
    "free_spin_title": {"ru": "🎁 <b>Бесплатный спин!</b>", "en": "🎁 <b>Free spin!</b>"},
    "free_spin_win": {"ru": "💰 Выигрыш: <b>{x:.4f} USDT</b> (бонус, вейджер x3)\n🎡 Осталось: <b>{left}</b>", "en": "💰 Win: <b>{x:.4f} USDT</b> (bonus, wager x3)\n🎡 Left: <b>{left}</b>"},
    "no_freespins": {"ru": "❌ У вас нет бесплатных спинов", "en": "❌ You have no free spins"},
    "price_title": {"ru": "📈 <b>Ставки на курс BTC</b>\n\nТекущая цена: <b>{price:.2f} USDT</b>\n\nУгадайте, куда пойдёт цена через {min} минут. Выплата: <b>x1.9</b>", "en": "📈 <b>BTC Price bets</b>\n\nCurrent price: <b>{price:.2f} USDT</b>\n\nGuess where the price goes in {min} minutes. Payout: <b>x1.9</b>"},
    "price_choose_bet": {"ru": "📈 <b>Ставки на курс BTC</b>\n\nВыберите сумму ставки:", "en": "📈 <b>BTC Price bets</b>\n\nChoose your bet amount:"},
    "price_choose_direction": {"ru": "📈 <b>BTC Up/Down</b>\n\n💰 Ставка: <b>{bet} USDT</b>\n\nВыберите направление:", "en": "📈 <b>BTC Up/Down</b>\n\n💰 Bet: <b>{bet} USDT</b>\n\nChoose direction:"},
    "price_already_active": {"ru": "❌ У вас уже есть активная ставка на курс. Дождитесь результата.", "en": "❌ You already have an active price bet. Wait for result."},
    "price_no_price": {"ru": "❌ Не удалось получить текущую цену. Попробуйте позже.", "en": "❌ Failed to get current price. Try later."},
    "price_bet_accepted": {"ru": "✅ <b>Ставка принята!</b>\n\n💰 {bet} USDT на {direction}\n📊 Стартовая цена: <b>{start:.2f} USDT</b>\n\n⏳ Результат через {min} минут.", "en": "✅ <b>Bet placed!</b>\n\n💰 {bet} USDT on {direction}\n📊 Start price: <b>{start:.2f} USDT</b>\n\n⏳ Result in {min} minutes."},
    "price_up": {"ru": "ВВЕРХ", "en": "UP"},
    "price_down": {"ru": "ВНИЗ", "en": "DOWN"},
    "price_win": {"ru": "🎉 <b>Выигрыш!</b>\n\n📊 Старт: {start:.2f} → Финиш: {end:.2f}\n💰 +{win:.4f} USDT", "en": "🎉 <b>You won!</b>\n\n📊 Start: {start:.2f} → End: {end:.2f}\n💰 +{win:.4f} USDT"},
    "price_lose": {"ru": "😢 <b>Проигрыш</b>\n\n📊 Старт: {start:.2f} → Финиш: {end:.2f}\n❌ -{bet:.4f} USDT", "en": "😢 <b>You lost</b>\n\n📊 Start: {start:.2f} → End: {end:.2f}\n❌ -{bet:.4f} USDT"},
    "price_refund": {"ru": "⚠️ Не удалось получить результат. Ставка возвращена.", "en": "⚠️ Failed to get result. Bet refunded."},
    "price_no_bet": {"ru": "❌ У вас нет активной ставки на курс.", "en": "❌ You have no active price bet."},
    "price_current": {"ru": "📈 <b>Курсы</b>\n\nBTC: <b>{price:.2f} USDT</b>", "en": "📈 <b>Prices</b>\n\nBTC: <b>{price:.2f} USDT</b>"},
    "stars_amount_title": {"ru": "⭐ <b>Пополнение через Stars</b>\n\nВведите сумму в <b>USDT</b>, на которую хотите пополнить баланс.\nМинимум: <b>{min} USDT</b>\n\nМы автоматически пересчитаем это в Stars по курсу (1 Star ≈ 0.014 USDT).", "en": "⭐ <b>Top up with Stars</b>\n\nEnter the amount in <b>USDT</b> you want to deposit.\nMinimum: <b>{min} USDT</b>\n\nWe will automatically convert it to Stars (1 Star ≈ 0.014 USDT)."},
    "stars_invoice_title": {"ru": "Пополнение баланса", "en": "Balance top-up"},
    "stars_invoice_desc": {"ru": "Пополнение на {usdt:.2f} USDT ({stars} Stars)", "en": "Top up {usdt:.2f} USDT ({stars} Stars)"},
    "stars_paid_ok": {"ru": "✅ <b>Баланс пополнен!</b>\n\n⭐ Оплачено Stars: <b>{stars}</b>\n💵 Начислено: <b>{usdt:.4f} USDT</b>\n", "en": "✅ <b>Balance topped up!</b>\n\n⭐ Stars paid: <b>{stars}</b>\n💵 Credited: <b>{usdt:.4f} USDT</b>\n"},
    "daily_title": {"ru": "🎁 <b>Ежедневный бонус</b>\n\n🔥 Серия: <b>{streak}</b> дн.\n📅 Последний вход: <b>{last}</b>\n\n<b>Множители:</b>\n• 3 дня → 0.02 USDT\n• 7 дней → 0.03 USDT\n• 14 дней → 0.05 USDT\n• 30 дней → 0.10 USDT\n\nНажми кнопку ниже, чтобы забрать бонус.", "en": "🎁 <b>Daily bonus</b>\n\n🔥 Streak: <b>{streak}</b> d.\n📅 Last visit: <b>{last}</b>\n\n<b>Multipliers:</b>\n• 3 days → 0.02 USDT\n• 7 days → 0.03 USDT\n• 14 days → 0.05 USDT\n• 30 days → 0.10 USDT\n\nPress the button below to claim."},
    "daily_already": {"ru": "✅ Ты уже забрал бонус сегодня. Возвращайся завтра!", "en": "✅ You already claimed today. Come back tomorrow!"},
    "daily_ok": {"ru": "🎉 <b>Бонус получен!</b>\n\n🔥 Серия: <b>{streak}</b> дн.\n💰 +<b>{bonus:.4f} USDT</b> на баланс.\n\nЗаходи завтра, чтобы продолжить серию!", "en": "🎉 <b>Bonus claimed!</b>\n\n🔥 Streak: <b>{streak}</b> d.\n💰 +<b>{bonus:.4f} USDT</b> to balance.\n\nCome back tomorrow to continue!"},
    "wheel_title": {"ru": "🎡 <b>Колесо дня</b>\n\nКрутить можно <b>раз в 24 часа</b>.\n\n<b>Призы:</b>\n❌ Пусто\n🟢 0.01 USDT\n🔵 0.05 USDT\n🟣 0.10 USDT\n🟡 Фриспин\n🔴 1 USDT (редко)", "en": "🎡 <b>Wheel of the day</b>\n\nYou can spin <b>once per 24 hours</b>.\n\n<b>Prizes:</b>\n❌ Empty\n🟢 0.01 USDT\n🔵 0.05 USDT\n🟣 0.10 USDT\n🟡 Freespin\n🔴 1 USDT (rare)"},
    "wheel_wait": {"ru": "⏳ Следующее вращение через <b>{h}ч {m}м</b>.", "en": "⏳ Next spin in <b>{h}h {m}m</b>."},
    "wheel_result": {"ru": "🎡 <b>Результат:</b> {prize}\n\n{reward}\n\n💼 Баланс: <b>{bal:.4f} USDT</b>", "en": "🎡 <b>Result:</b> {prize}\n\n{reward}\n\n💼 Balance: <b>{bal:.4f} USDT</b>"},
}
GAME_TITLES = {
    "roulette": {"ru": "🎰 Рулетка", "en": "🎰 Roulette"},
    "slots": {"ru": "🎲 Слоты", "en": "🎲 Slots"},
    "coin": {"ru": "🪙 Монетка", "en": "🪙 Coinflip"},
    "dice": {"ru": "🎲 Кости", "en": "🎲 Dice"},
    "wheel": {"ru": "🎡 Колесо фортуны", "en": "🎡 Wheel"},
    "cards": {"ru": "🃏 Карты", "en": "🃏 Cards"},
    "mines": {"ru": "💣 Мины", "en": "💣 Mines"},
    "lottery": {"ru": "🎟️ Лотерея", "en": "🎟️ Lottery"},
    "darts": {"ru": "🎯 Дартс", "en": "🎯 Darts"},
    "basket": {"ru": "🏀 Баскетбол", "en": "🏀 Basketball"},
    "craps": {"ru": "🎲 Крэпс", "en": "🎲 Craps"},
}
GAME_HINTS = {
    "roulette": {"ru": "Выберите цвет:", "en": "Choose a color:"},
    "slots": {"ru": "Нажмите, чтобы крутить:", "en": "Press to spin:"},
    "coin": {"ru": "Угадайте сторону:", "en": "Guess the side:"},
    "dice": {"ru": "Угадайте число (выплата x5):", "en": "Guess the number (payout x5):"},
    "wheel": {"ru": "Испытайте удачу:", "en": "Try your luck:"},
    "cards": {"ru": "Угадайте: следующая карта больше или меньше?", "en": "Guess: next card higher or lower?"},
    "lottery": {"ru": "Купите билет — 5 чисел из 25:", "en": "Buy a ticket — 5 out of 25:"},
    "darts": {"ru": "Выберите сектор броска:", "en": "Choose your sector:"},
    "basket": {"ru": "Выберите тип броска:", "en": "Choose your shot:"},
    "craps": {"ru": "Сделайте ставку:", "en": "Place your bet:"},
}

TX_LABELS = {
    "deposit": {"ru": "💳 Депозит", "en": "💳 Deposit"},
    "withdraw": {"ru": "💸 Вывод", "en": "💸 Withdraw"},
    "bet": {"ru": "🎰 Ставка", "en": "🎰 Bet"},
    "win": {"ru": "🏆 Выигрыш", "en": "🏆 Win"},
    "bonus": {"ru": "🎁 Бонус", "en": "🎁 Bonus"},
    "cashback": {"ru": "💸 Кэшбэк", "en": "💸 Cashback"},
    "referral": {"ru": "👥 Реферал", "en": "👥 Referral"},
    "transfer_in": {"ru": "🎁 Подарок получен", "en": "🎁 Gift received"},
    "transfer_out": {"ru": "🎁 Подарок отправлен", "en": "🎁 Gift sent"},
    "purchase": {"ru": "🛒 Покупка бонуса", "en": "🛒 Bonus purchase"},
    "promo": {"ru": "🎟️ Промокод", "en": "🎟️ Promo"},
    "check_in": {"ru": "🎁 Чек получен", "en": "🎁 Check received"},
    "check_out": {"ru": "🎁 Чек создан", "en": "🎁 Check created"},
    "channel_bonus": {"ru": "📢 Бонус за подписку", "en": "📢 Subscribe bonus"},
    "luck": {"ru": "🍀 Очки удачи", "en": "🍀 Luck points"},
    "price_bet": {"ru": "📈 Ставка на курс", "en": "📈 Price bet"},
    "price_win": {"ru": "📈 Выигрыш по курсу", "en": "📈 Price win"},
}

def t(lang: str, key: str, **kw) -> str:
    lang = lang if lang in ("ru", "en") else "ru"
    block = TEXTS.get(key) or GAME_TITLES.get(key) or GAME_HINTS.get(key) or TX_LABELS.get(key)
    if not block:
        return key
    text = block.get(lang) or block.get("ru") or ""
    if kw:
        try:
            text = text.format(**kw)
        except Exception:
            pass
    return text

def lang_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
         InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")],
    ])

def main_menu(lang="ru"):
    if lang == "en":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Play Plinko (Ball)", web_app=WebAppInfo(url="https://partiarmmp-lang.github.io/bread-casino-/"))],
            [InlineKeyboardButton(text="🚀 Play Crash (Rocket)", web_app=WebAppInfo(url="https://partiarmmp-lang.github.io/bread-casino-/crash.html"))],
            [InlineKeyboardButton(text="🔥 DELUXE SLOTS (Exclusive)", web_app=WebAppInfo(url="https://partiarmmp-lang.github.io/bread-casino-/slots.html"))],
            [InlineKeyboardButton(text="🎰 Roulette", callback_data="game_roulette"),
             InlineKeyboardButton(text="🎲 Slots", callback_data="game_slots")],
            [InlineKeyboardButton(text="💣 Mines", callback_data="game_mines"),
             InlineKeyboardButton(text="🎟️ Lottery", callback_data="game_lottery")],
            [InlineKeyboardButton(text="🎡 Wheel", callback_data="game_wheel"),
             InlineKeyboardButton(text="🪙 Coinflip", callback_data="game_coin")],
            [InlineKeyboardButton(text="🎲 Dice", callback_data="game_dice"),
             InlineKeyboardButton(text="🃏 Cards", callback_data="game_cards")],
            [InlineKeyboardButton(text="🎯 Darts", callback_data="game_darts"),
             InlineKeyboardButton(text="🏀 Basketball", callback_data="game_basket")],
            [InlineKeyboardButton(text="🎲 Craps", callback_data="game_craps")],
            [InlineKeyboardButton(text="💰 Balance", callback_data="balance"),
             InlineKeyboardButton(text="📜 History", callback_data="history")],
            [InlineKeyboardButton(text="🎁 Bonuses", callback_data="bonuses"),
             InlineKeyboardButton(text="🍀 Luck", callback_data="luck")],
            [InlineKeyboardButton(text="💸 Cashback", callback_data="cashback"),
             InlineKeyboardButton(text="👥 Referrals", callback_data="referrals")],
            [InlineKeyboardButton(text="📊 Stats", callback_data="stats"),
             InlineKeyboardButton(text="🎁 Gift", callback_data="transfer_start")],
            [InlineKeyboardButton(text="🎟️ Promo", callback_data="promo_enter"),
             InlineKeyboardButton(text="🎁 Check", callback_data="check_menu")],
            [InlineKeyboardButton(text="🪙 Coins", callback_data="tap_menu")],
            [InlineKeyboardButton(text="🎁 Daily bonus", callback_data="daily_open")],
            [InlineKeyboardButton(text="📈 Price bets", callback_data="price_game")],
            [InlineKeyboardButton(text="📢 Subscribe bonus", callback_data="channel_bonus")],
            [InlineKeyboardButton(text="🛒 Bonus shop", callback_data="bonus_shop")],
            [InlineKeyboardButton(text="🌐 Language", callback_data="change_lang")],
            [InlineKeyboardButton(text="💳 Deposit", callback_data="topup"),
             InlineKeyboardButton(text="💸 Withdraw", callback_data="withdraw")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Играть в Plinko (Шарик)", web_app=WebAppInfo(url="https://partiarmmp-lang.github.io/bread-casino-/"))],
        [InlineKeyboardButton(text="🚀 Играть в Crash (Ракетка)", web_app=WebAppInfo(url="https://partiarmmp-lang.github.io/bread-casino-/crash.html"))],
                [InlineKeyboardButton(text="🔥 DELUXE SLOTS (Эксклюзив)", web_app=WebAppInfo(url="https://partiarmmp-lang.github.io/bread-casino-/slots.html"))],
        [InlineKeyboardButton(text="🎰 Рулетка", callback_data="game_roulette"),
         InlineKeyboardButton(text="🎲 Слоты", callback_data="game_slots")],
        [InlineKeyboardButton(text="💣 Мины", callback_data="game_mines"),
         InlineKeyboardButton(text="🎟️ Лотерея", callback_data="game_lottery")],
        [InlineKeyboardButton(text="🎡 Колесо", callback_data="game_wheel"),
         InlineKeyboardButton(text="🪙 Монетка", callback_data="game_coin")],
        [InlineKeyboardButton(text="🎲 Кости", callback_data="game_dice"),
         InlineKeyboardButton(text="🃏 Карты", callback_data="game_cards")],
        [InlineKeyboardButton(text="🎯 Дартс", callback_data="game_darts"),
         InlineKeyboardButton(text="🏀 Баскетбол", callback_data="game_basket")],
        [InlineKeyboardButton(text="🎲 Крэпс", callback_data="game_craps")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
         InlineKeyboardButton(text="📜 История", callback_data="history")],
        [InlineKeyboardButton(text="🎁 Бонусы", callback_data="bonuses"),
         InlineKeyboardButton(text="🍀 Очки удачи", callback_data="luck")],
        [InlineKeyboardButton(text="💸 Кэшбэк", callback_data="cashback"),
         InlineKeyboardButton(text="👥 Рефералы", callback_data="referrals")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
         InlineKeyboardButton(text="🎁 Подарить", callback_data="transfer_start")],
        [InlineKeyboardButton(text="🎟️ Промокод", callback_data="promo_enter"),
         InlineKeyboardButton(text="🎁 Чек", callback_data="check_menu")],
        [InlineKeyboardButton(text="🪙 Монеты", callback_data="tap_menu")],
        [InlineKeyboardButton(text="🎁 Ежедневный бонус", callback_data="daily_open")],
        [InlineKeyboardButton(text="📈 Ставки на курс", callback_data="price_game")],
        [InlineKeyboardButton(text="📢 Бонус за подписку", callback_data="channel_bonus")],
        [InlineKeyboardButton(text="🛒 Магазин бонусов", callback_data="bonus_shop")],
        [InlineKeyboardButton(text="🌐 Язык", callback_data="change_lang")],
        [InlineKeyboardButton(text="💳 Пополнить", callback_data="topup"),
         InlineKeyboardButton(text="💸 Вывести", callback_data="withdraw")],
    ])

def price_menu(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 0.10 USDT", callback_data="price_bet_0.10"),
         InlineKeyboardButton(text="💰 0.50 USDT", callback_data="price_bet_0.50")],
        [InlineKeyboardButton(text="💰 1 USDT", callback_data="price_bet_1"),
         InlineKeyboardButton(text="💰 5 USDT", callback_data="price_bet_5")],
        [InlineKeyboardButton(text="🔄 Refresh price" if lang == "en" else "🔄 Обновить цену", callback_data="price_game")],
        [InlineKeyboardButton(text=t(lang, "back"), callback_data="back")]
    ])

def price_direction_menu(bet: float, lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 UP (x1.9)" if lang == "en" else "🟢 ВВЕРХ (x1.9)", callback_data=f"price_dir_up_{bet}"),
         InlineKeyboardButton(text="🔴 DOWN (x1.9)" if lang == "en" else "🔴 ВНИЗ (x1.9)", callback_data=f"price_dir_down_{bet}")],
        [InlineKeyboardButton(text="⬅️ Back" if lang == "en" else "⬅️ Назад", callback_data="price_game")]
    ])

def back_kb(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "back"), callback_data="back")]])

def check_menu_kb(lang="ru"):
    if lang == "en":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Create check", callback_data="check_create")],
            [InlineKeyboardButton(text="🎟️ Claim check", callback_data="check_claim")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="back")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Создать чек", callback_data="check_create")],
        [InlineKeyboardButton(text="🎟️ Активировать чек", callback_data="check_claim")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")],
    ])

def bet_menu(game, lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0.05 USDT", callback_data=f"{game}_bet_0.05"),
         InlineKeyboardButton(text="0.10 USDT", callback_data=f"{game}_bet_0.1")],
        [InlineKeyboardButton(text="0.50 USDT", callback_data=f"{game}_bet_0.5"),
         InlineKeyboardButton(text="1 USDT", callback_data=f"{game}_bet_1")],
        [InlineKeyboardButton(text="5 USDT", callback_data=f"{game}_bet_5"),
         InlineKeyboardButton(text="✏️ Custom amount" if lang == "en" else "✏️ Своя сумма", callback_data=f"{game}_bet_custom")],
        [InlineKeyboardButton(text=t(lang, "back"), callback_data="back")]
    ])

async def get_binance_price(symbol: str = "BTCUSDT") -> float:
    url = "https://api.binance.com/api/v3/ticker/price"
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params={"symbol": symbol}) as resp:
                data = await resp.json()
                return float(data["price"])
    except Exception:
        logging.exception("get_binance_price failed")
        return 0.0

async def price_round_timer(user_id, bet, start_price, direction, lang):
    await asyncio.sleep(PRICE_ROUND_SECONDS)
    end_price = await get_binance_price("BTCUSDT")
    game = PRICE_GAMES.pop(user_id, None)
    if not game:
        return

    if end_price == 0.0:
        await update_balance(user_id, bet)
        try:
            await bot.send_message(user_id, t(lang, "price_refund"), parse_mode="HTML")
        except Exception:
            pass
        return

    price_up = end_price > start_price
    won = (direction == "up" and price_up) or (direction == "down" and not price_up)

    if won:
        win_amount = bet * 1.9
        await update_balance(user_id, win_amount)
        await process_win(user_id, win_amount)
        await log_tx(user_id, "price_win", win_amount, direction)
        msg = t(lang, "price_win", start=start_price, end=end_price, win=win_amount)
    else:
        await process_loss(user_id, bet, is_real=True)
        msg = t(lang, "price_lose", start=start_price, end=end_price, bet=bet)

    try:
        await bot.send_message(user_id, msg, parse_mode="HTML")
    except Exception:
        pass

@dp.message(Command("start"))
async def start(message: Message, command: CommandObject):
    await init_db()
    user_id = message.from_user.id
    is_new = await is_new_user(user_id)
    lang = await get_language(user_id)

    if command.args and command.args.startswith("ref_"):
        try:
            referrer_id = int(command.args.replace("ref_", ""))
            if referrer_id != user_id and is_new:
                await get_balance(user_id)
                ok = await set_referrer_full(user_id, referrer_id)
                if ok:
                    await add_luck_points(referrer_id, 50)
                    try:
                        await bot.send_message(
                            referrer_id,
                            "🎉 <b>Новый реферал!</b>\n\n+50 очков удачи!\n10% / 3% / 1% от проигрышей.",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
        except Exception:
            pass

    if command.args and command.args.startswith("check_"):
        code = command.args.replace("check_", "")
        await handle_check_claim(user_id, code, message, lang or "ru")
        return

    if is_new:
        await update_balance(user_id, 0.10)
        await log_tx(user_id, "bonus", 0.10, "welcome")

    if lang is None:
        await message.answer(t("ru", "choose_language"), reply_markup=lang_menu())
        return

    welcome = t(lang, "welcome_new") if is_new else ""
    balance = await get_total_balance(user_id)
    await message.answer(
        f"{welcome}{t(lang, 'welcome', balance=balance)}",
        reply_markup=main_menu(lang), parse_mode="HTML"
    )

@dp.callback_query(F.data == "change_lang")
async def change_lang(call: CallbackQuery):
    await call.message.edit_text(t("ru", "choose_language"), reply_markup=lang_menu())
    await call.answer()

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(call: CallbackQuery):
    lang = call.data.replace("lang_", "")
    await set_language(call.from_user.id, lang)
    balance = await get_total_balance(call.from_user.id)
    await call.message.edit_text(
        t(lang, "main_menu", balance=balance),
        reply_markup=main_menu(lang), parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    balance = await get_total_balance(call.from_user.id)
    await call.message.edit_text(
        t(lang, "main_menu", balance=balance),
        reply_markup=main_menu(lang), parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "history")
async def show_history(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    rows = await get_transactions(call.from_user.id, 15)
    if not rows:
        text = t(lang, "history_empty")
    else:
        lines = [t(lang, "history")]
        for tx_type, amount, meta, created_at in rows:
            label = (TX_LABELS.get(tx_type) or {}).get(lang) or tx_type
            sign = "+" if amount >= 0 else ""
            date = (created_at or "")[:16]
            meta_str = f" — {meta}" if meta else ""
            lines.append(f"{label} <b>{sign}{amount:.4f}</b>{meta_str}\n<i>{date}</i>")
        text = "\n\n".join(lines)
    await call.message.edit_text(text, reply_markup=back_kb(lang), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "price_game")
async def show_price_game(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    if call.from_user.id in PRICE_GAMES:
        await call.answer(t(lang, "price_already_active"), show_alert=True)
        return
    price = await get_binance_price("BTCUSDT")
    if price == 0.0:
        await call.answer(t(lang, "price_no_price"), show_alert=True)
        return
    text = t(lang, "price_title", price=price, min=PRICE_ROUND_SECONDS // 60)
    await call.message.edit_text(text, reply_markup=price_menu(lang), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("price_bet_"))
async def price_choose_direction(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    try:
        bet = float(call.data.replace("price_bet_", ""))
    except ValueError:
        return
    if bet < MIN_PRICE_BET or bet > MAX_PRICE_BET:
        await call.answer(t(lang, "bet_range", a=MIN_PRICE_BET, b=MAX_PRICE_BET), show_alert=True)
        return
    text = t(lang, "price_choose_direction", bet=bet)
    await call.message.edit_text(text, reply_markup=price_direction_menu(bet, lang), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("price_dir_"))
async def price_place_bet(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    user_id = call.from_user.id

    parts = call.data.split("_")
    if len(parts) != 4:
        return
    direction = parts[2]
    try:
        bet = float(parts[3])
    except ValueError:
        return

    if user_id in PRICE_GAMES:
        await call.answer(t(lang, "price_already_active"), show_alert=True)
        return

    if not await try_deduct_balance(user_id, bet):
        await call.answer(t(lang, "not_enough"), show_alert=True)
        return

    start_price = await get_binance_price("BTCUSDT")
    if start_price == 0.0:
        await update_balance(user_id, bet)
        await call.answer(t(lang, "price_no_price"), show_alert=True)
        return

    await log_tx(user_id, "price_bet", -bet, direction)

    task = asyncio.create_task(price_round_timer(user_id, bet, start_price, direction, lang))
    PRICE_GAMES[user_id] = {
        "bet": bet,
        "start_price": start_price,
        "direction": direction,
        "task": task
    }

    dir_text = t(lang, "price_up") if direction == "up" else t(lang, "price_down")
    text = t(lang, "price_bet_accepted", bet=bet, direction=dir_text, start=start_price, min=PRICE_ROUND_SECONDS // 60)
    await call.message.edit_text(text, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "balance")
async def show_balance(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    main = await get_balance(call.from_user.id)
    bonus = await get_bonus_balance(call.from_user.id)
    wager_req, wager_done = await get_wager_info(call.from_user.id)
    r_fs, l_fs = await get_freespins(call.from_user.id)
    text = t(lang, "balance", main=main)
    if bonus > 0:
        text += t(lang, "balance_bonus", bonus=bonus, done=wager_done, req=wager_req)
    if r_fs or l_fs:
        text += t(lang, "balance_fs", r_fs=r_fs, l_fs=l_fs)
    await call.message.edit_text(text, reply_markup=main_menu(lang), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "bonuses")
async def show_bonuses(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    bonus = await get_bonus_balance(call.from_user.id)
    wager_req, wager_done = await get_wager_info(call.from_user.id)
    r_fs, l_fs = await get_freespins(call.from_user.id)
    text = t(lang, "bonuses_title")
    if bonus > 0:
        text += t(lang, "bonuses_bonus", bonus=bonus, done=wager_done, req=wager_req)
    else:
        text += t(lang, "bonuses_none")
    text += t(lang, "balance_fs", r_fs=r_fs, l_fs=l_fs)
    await call.message.edit_text(text, reply_markup=back_kb(lang), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "stats")
async def show_stats(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    user_id = call.from_user.id
    balance = await get_total_balance(user_id)
    refs = await get_referral_count(user_id)
    earn = await get_referral_earnings(user_id)
    await call.message.edit_text(
        t(lang, "stats", id=user_id, bal=balance, refs=refs, earn=earn),
        reply_markup=back_kb(lang), parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "referrals")
async def show_referrals(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    user_id = call.from_user.id
    count = await get_referral_count(user_id)
    earn = await get_referral_earnings(user_id)
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    await call.message.edit_text(
        t(lang, "referrals", count=count, earn=earn, link=link),
        reply_markup=back_kb(lang), parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "promo_enter")
async def promo_enter(call: CallbackQuery, state: FSMContext):
    lang = await get_language(call.from_user.id) or "ru"
    await state.set_state(States.waiting_promo)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "cancel"), callback_data="back")]])
    await call.message.edit_text(t(lang, "promo_enter"), reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.message(States.waiting_promo)
async def promo_process(message: Message, state: FSMContext):
    lang = await get_language(message.from_user.id) or "ru"
    code = (message.text or "").strip().upper()
    if not code:
        await message.answer(t(lang, "enter_number"))
        return
    ok, reason, amount = await activate_promo(code, message.from_user.id)
    await state.clear()
    if not ok:
        err_key = {"not_found": "promo_not_found", "limit": "promo_limit", "already": "promo_already"}.get(reason, "promo_not_found")
        await message.answer(t(lang, err_key), reply_markup=main_menu(lang))
        return
    await log_tx(message.from_user.id, "promo", amount, code)
    balance = await get_total_balance(message.from_user.id)
    await message.answer(
        t(lang, "promo_ok", x=amount, bal=balance),
        reply_markup=main_menu(lang), parse_mode="HTML"
    )

@dp.callback_query(F.data == "check_menu")
async def check_menu_handler(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    main = await get_balance(call.from_user.id)
    await call.message.edit_text(
        t(lang, "check_menu_title", bal=main, min=MIN_CHECK),
        reply_markup=check_menu_kb(lang), parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "check_create")
async def check_create_start(call: CallbackQuery, state: FSMContext):
    lang = await get_language(call.from_user.id) or "ru"
    main = await get_balance(call.from_user.id)
    if main < MIN_CHECK:
        await call.answer(t(lang, "need_main_balance", x=MIN_CHECK), show_alert=True)
        return
    await state.set_state(States.waiting_check_amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "cancel"), callback_data="check_menu")]])
    await call.message.edit_text(
        t(lang, "check_create", bal=main, min=MIN_CHECK),
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()

@dp.message(States.waiting_check_amount)
async def check_create_process(message: Message, state: FSMContext):
    lang = await get_language(message.from_user.id) or "ru"
    try:
        amount = float(message.text.replace(",", ".").strip())
    except (ValueError, AttributeError):
        await message.answer(t(lang, "enter_number"))
        return
    if amount < MIN_CHECK:
        await message.answer(t(lang, "min_bet", x=MIN_CHECK))
        return
    user_id = message.from_user.id
    if not await try_deduct_balance(user_id, amount):
        await message.answer(t(lang, "not_enough"))
        return
    code = await create_check(amount, user_id)
    await log_tx(user_id, "check_out", -amount, code)
    await state.clear()
    link = f"https://t.me/{BOT_USERNAME}?start=check_{code}"
    await message.answer(
        t(lang, "check_created", x=amount, code=code, link=link),
        reply_markup=main_menu(lang), parse_mode="HTML"
    )

@dp.callback_query(F.data == "check_claim")
async def check_claim_start(call: CallbackQuery, state: FSMContext):
    lang = await get_language(call.from_user.id) or "ru"
    await state.set_state(States.waiting_check_claim)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "cancel"), callback_data="check_menu")]])
    await call.message.edit_text(t(lang, "check_claim"), reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.message(States.waiting_check_claim)
async def check_claim_process(message: Message, state: FSMContext):
    lang = await get_language(message.from_user.id) or "ru"
    code = (message.text or "").strip().upper()
    await state.clear()
    await handle_check_claim(message.from_user.id, code, message, lang)

async def handle_check_claim(user_id, code, target, lang="ru"):
    ok, reason, amount = await claim_check(code, user_id)
    if not ok:
        err_key = {"not_found": "check_not_found", "already": "check_already"}.get(reason, "check_not_found")
        try:
            await target.answer(t(lang, err_key), reply_markup=main_menu(lang))
        except Exception:
            pass
        return
    await log_tx(user_id, "check_in", amount, code)
    balance = await get_total_balance(user_id)
    text = t(lang, "check_ok", x=amount, bal=balance)
    try:
        await target.answer(text, reply_markup=main_menu(lang), parse_mode="HTML")
    except Exception:
        await target.answer(text, parse_mode="HTML")

@dp.callback_query(F.data == "transfer_start")
async def transfer_start(call: CallbackQuery, state: FSMContext):
    lang = await get_language(call.from_user.id) or "ru"
    main = await get_balance(call.from_user.id)
    if main < MIN_TRANSFER:
        await call.answer(t(lang, "need_main_balance", x=MIN_TRANSFER), show_alert=True)
        return
    await state.set_state(States.waiting_transfer_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "cancel"), callback_data="back")]])
    await call.message.edit_text(
        t(lang, "transfer_title", bal=main, min=MIN_TRANSFER),
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()

@dp.message(States.waiting_transfer_id)
async def transfer_recipient(message: Message, state: FSMContext):
    lang = await get_language(message.from_user.id) or "ru"
    try:
        recipient_id = int(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer(t(lang, "enter_number"))
        return
    if recipient_id == message.from_user.id:
        await message.answer(t(lang, "transfer_self"))
        return
    await get_balance(recipient_id)
    await state.update_data(recipient_id=recipient_id)
    await state.set_state(States.waiting_transfer_amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "cancel"), callback_data="back")]])
    await message.answer(
        t(lang, "transfer_amount", id=recipient_id, min=MIN_TRANSFER),
        reply_markup=kb, parse_mode="HTML"
    )

@dp.message(States.waiting_transfer_amount)
async def transfer_amount(message: Message, state: FSMContext):
    lang = await get_language(message.from_user.id) or "ru"
    data = await state.get_data()
    recipient_id = data.get("recipient_id")
    try:
        amount = float(message.text.replace(",", ".").strip())
    except (ValueError, AttributeError):
        await message.answer(t(lang, "enter_number"))
        return
    if amount < MIN_TRANSFER:
        await message.answer(t(lang, "min_bet", x=MIN_TRANSFER))
        return
    sender_id = message.from_user.id
    if not await transfer_between_users(sender_id, recipient_id, amount):
        await message.answer(t(lang, "not_enough"))
        return
    await log_tx(sender_id, "transfer_out", -amount, f"-> {recipient_id}")
    await log_tx(recipient_id, "transfer_in", amount, f"<- {sender_id}")
    await state.clear()
    await message.answer(
        t(lang, "transfer_sent", id=recipient_id, x=amount),
        reply_markup=main_menu(lang), parse_mode="HTML"
    )
    rec_lang = await get_language(recipient_id) or "ru"
    try:
        await bot.send_message(
            recipient_id,
            t(rec_lang, "transfer_received", id=sender_id, x=amount),
            parse_mode="HTML"
        )
    except Exception:
        pass

@dp.callback_query(F.data == "luck")
async def show_luck(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    points, total = await get_luck_points(call.from_user.id)
    await call.message.edit_text(
        t(lang, "luck_title", points=points, total=total),
        reply_markup=luck_menu(lang), parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "luck_open")
async def luck_open(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    user_id = call.from_user.id
    points, _ = await get_luck_points(user_id)
    if points < 100:
        await call.answer(t(lang, "luck_not_enough", x=points), show_alert=True)
        return
    if not await spend_luck_points(user_id, 100):
        await call.answer("❌", show_alert=True)
        return
    r = random.random() * 100
    if r < 5:
        await add_bonus(user_id, 10.0, 3.0)
        await add_freespins(user_id, roulette=20, lottery=0)
        name = "🎉 JACKPOT" if lang == "en" else "🎉 ДЖЕКПОТ"
        value = "10 USDT bonus (wager x3) + 20 freespins" if lang == "en" else "10 USDT бонусом (вейджер x3) + 20 фриспинов"
        await log_luck_reward(user_id, name, 10.0)
    elif r < 20:
        await add_freespins(user_id, roulette=5, lottery=0)
        name = "🎡 5 freespins" if lang == "en" else "🎡 5 фриспинов"
        value = "5 freespins (win to bonus x3)" if lang == "en" else "5 фриспинов (выигрыш в бонус x3)"
        await log_luck_reward(user_id, name, 0.0)
    elif r < 50:
        await add_bonus(user_id, 1.0, 3.0)
        name = "💰 1 USDT"
        value = "1 USDT bonus (wager x3)" if lang == "en" else "1 USDT бонусом (вейджер x3)"
        await log_luck_reward(user_id, name, 1.0)
    else:
        await add_bonus(user_id, 0.5, 3.0)
        name = "🎁 0.5 USDT"
        value = "0.5 USDT bonus (wager x3)" if lang == "en" else "0.5 USDT бонусом (вейджер x3)"
        await log_luck_reward(user_id, name, 0.5)
    new_points, _ = await get_luck_points(user_id)
    await call.message.edit_text(
        t(lang, "luck_open", name=name, value=value, points=new_points),
        reply_markup=luck_menu(lang), parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "luck_history")
async def luck_history(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    history = await get_luck_history(call.from_user.id, 5)
    if not history:
        text = t(lang, "luck_history_empty")
    else:
        lines = [t(lang, "luck_history")]
        for reward, amount, created_at in history:
            lines.append(f"• {reward} — {amount} USDT — {created_at[:10]}")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=luck_menu(lang), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "cashback")
async def show_cashback(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    user_id = call.from_user.id
    weekly = await get_weekly_lost(user_id)
    percent = get_cashback_percent(weekly)
    cashback = weekly * percent / 100
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Claim cashback" if lang == "en" else "🎁 Забрать кэшбэк", callback_data="cashback_claim")],
        [InlineKeyboardButton(text=t(lang, "back"), callback_data="back")]
    ])
    await call.message.edit_text(
        t(lang, "cashback_title", lost=weekly, percent=percent, cashback=cashback),
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "cashback_claim")
async def cashback_claim(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    user_id = call.from_user.id
    weekly = await get_weekly_lost(user_id)
    percent = get_cashback_percent(weekly)
    if percent == 0:
        await call.answer(t(lang, "cashback_small"), show_alert=True)
        return
    cashback = weekly * percent / 100
    await update_balance(user_id, cashback)
    await reset_weekly(user_id)
    await log_tx(user_id, "cashback", cashback, f"{percent}%")
    await call.message.edit_text(
        t(lang, "cashback_ok", x=cashback),
        reply_markup=main_menu(lang), parse_mode="HTML"
    )
    await call.answer(f"+{cashback:.4f} USDT")

@dp.callback_query(F.data == "channel_bonus")
async def channel_bonus(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    if not await has_deposit(call.from_user.id):
        await call.message.edit_text(
            t(lang, "channel_bonus_no_dep"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Deposit" if lang == "en" else "💳 Пополнить", callback_data="topup")],
                [InlineKeyboardButton(text=t(lang, "back"), callback_data="back")]
            ]),
            parse_mode="HTML"
        )
        await call.answer()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I subscribed" if lang == "en" else "✅ Я подписался", callback_data="check_subscription")],
        [InlineKeyboardButton(text=t(lang, "back"), callback_data="back")]
    ])
    await call.message.edit_text(
        t(lang, "channel_bonus_title", bonus=CHANNEL_BONUS, url=CHANNEL_URL),
        reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True
    )
    await call.answer()

@dp.callback_query(F.data == "check_subscription")
async def check_subscription(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    user_id = call.from_user.id
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        status = member.status
        if status in ("member", "administrator", "creator"):
            success = await give_channel_bonus(user_id, CHANNEL_BONUS)
            if success:
                await update_balance(user_id, -CHANNEL_BONUS)
                await add_bonus(user_id, CHANNEL_BONUS, 3.0)
                await add_luck_points(user_id, 100)
                await log_tx(user_id, "channel_bonus", -CHANNEL_BONUS, "moved to bonus")
                balance = await get_total_balance(user_id)
                await call.message.edit_text(
                    t(lang, "channel_bonus_ok", bonus=CHANNEL_BONUS, bal=balance),
                    reply_markup=main_menu(lang), parse_mode="HTML"
                )
                await call.answer(f"+{CHANNEL_BONUS} USDT")
            else:
                await call.answer(t(lang, "channel_bonus_already"), show_alert=True)
        else:
            await call.answer(t(lang, "channel_bonus_not_sub"), show_alert=True)
    except Exception:
        await call.answer(t(lang, "channel_bonus_error"), show_alert=True)

@dp.callback_query(F.data == "bonus_shop")
async def show_bonus_shop(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    text = t(lang, "bonus_shop_title")
    for key, p in BONUS_PACKAGES.items():
        name = p["name"][lang] if isinstance(p["name"], dict) else p["name"]
        text += f"<b>{name}</b>\n"
        text += f"💰 {'Price' if lang == 'en' else 'Цена'}: <b>{p['price']} USDT</b>\n"
        text += f"🎁 {'Bonus' if lang == 'en' else 'Бонус'}: <b>{p['bonus']} USDT</b> (wager x3)\n"
        if p["fs"]:
            text += f"🎡 +{p['fs']} {'freespins' if lang == 'en' else 'фриспинов'}\n"
        if p["tickets"]:
            text += f"🎟️ +{p['tickets']} {'tickets' if lang == 'en' else 'билетов'}\n"
        text += "\n"
    text += t(lang, "bonus_shop_footer")
    await call.message.edit_text(text, reply_markup=bonus_shop_menu(lang), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("buybonus_"))
async def buy_bonus(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    key = call.data.replace("buybonus_", "")
    p = BONUS_PACKAGES.get(key)
    if not p:
        await call.answer("Not found", show_alert=True)
        return
    uid = call.from_user.id
    if not await try_deduct_balance(uid, p["price"]):
        await call.answer(t(lang, "need_main_balance", x=p["price"]), show_alert=True)
        return
    await add_bonus(uid, p["bonus"], 3.0)
    if p["fs"] or p["tickets"]:
        await add_freespins(uid, roulette=p["fs"], lottery=p["tickets"])
    await add_bonus_purchase(uid, p["price"], p["bonus"])
    await add_luck_points(uid, int(p["price"] * 20))
    await log_tx(uid, "purchase", -p["price"], key)
    new_balance = await get_total_balance(uid)
    name = p["name"][lang] if isinstance(p["name"], dict) else p["name"]
    text = t(lang, "bonus_bought", name=name, price=p["price"], bonus=p["bonus"])
    if p["fs"]:
        text += t(lang, "bonus_bought_fs", x=p["fs"])
    if p["tickets"]:
        text += t(lang, "bonus_bought_tickets", x=p["tickets"])
    text += t(lang, "bonus_bought_luck", x=int(p["price"] * 20), bal=new_balance)
    await call.message.edit_text(text, reply_markup=main_menu(lang), parse_mode="HTML")
    await call.answer("🎁")

def tap_menu_kb(has_energy, daily_available, lang="ru"):
    buttons = []
    if has_energy:
        buttons.append([InlineKeyboardButton(
            text="🪙 Кликнуть (+1 монета)" if lang == "ru" else "🪙 Click (+1 coin)", 
            callback_data="tap_click"
        )])
    else:
        buttons.append([InlineKeyboardButton(
            text="🔋 Энергия восстанавливается..." if lang == "ru" else "🔋 Energy restoring...", 
            callback_data="tap_noop"
        )])
        
    if daily_available:
        buttons.append([InlineKeyboardButton(
            text="🎁 Ежедневный бонус (+50 монет)" if lang == "ru" else "🎁 Daily bonus (+50 coins)", 
            callback_data="tap_daily"
        )])
        
    buttons.append([InlineKeyboardButton(
        text="🔄 Обменять монеты" if lang == "ru" else "🔄 Exchange coins", 
        callback_data="tap_exchange"
    )])
    buttons.append([InlineKeyboardButton(
        text="⬅️ Назад" if lang == "ru" else "⬅️ Back", 
        callback_data="back"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_tap_screen(user_id, lang="ru"):
    tap_data = await get_tap_data(user_id)
    if not tap_data:
        return "Ошибка данных", back_kb(lang)
    
    coins, energy, energy_limit, last_reset, last_daily = tap_data
    
    await regenerate_energy(user_id, energy_limit, regen_rate=10)
    tap_data = await get_tap_data(user_id)
    coins, energy, energy_limit, last_reset, last_daily = tap_data

    daily_available = False
    if not last_daily:
        daily_available = True
    else:
        try:
            last_bonus = datetime.datetime.strptime(last_daily.split('.')[0], "%Y-%m-%d %H:%M:%S")
            if (datetime.datetime.utcnow() - last_bonus).total_seconds() >= 86400:
                daily_available = True
        except:
            daily_available = True

    text = (
        f"🪙 <b>Монеты</b>\n\n"
        f"💰 Баланс: <b>{coins}</b>\n"
        f"⚡ Энергия: <b>{energy} / {energy_limit}</b>\n\n"
        f"Кликай и копи монеты, чтобы обменять их на бонусы и фриспины!"
    ) if lang == "ru" else (
        f"🪙 <b>Coins</b>\n\n"
        f"💰 Balance: <b>{coins}</b>\n"
        f"⚡ Energy: <b>{energy} / {energy_limit}</b>\n\n"
        f"Click and earn coins to exchange for bonuses and freespins!"
    )
    return text, tap_menu_kb(energy >= 1, daily_available, lang)

@dp.callback_query(F.data == "tap_menu")
async def show_tap_menu(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    text, kb = await get_tap_screen(call.from_user.id, lang)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "tap_click")
async def handle_tap_click(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    user_id = call.from_user.id
    
    success = await update_tap_click(user_id)
    if not success:
        await call.answer("❌ Нет энергии!" if lang == "ru" else "❌ No energy!", show_alert=True)
    
    text, kb = await get_tap_screen(user_id, lang)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer("+1 🪙")

@dp.callback_query(F.data == "tap_daily")
async def handle_tap_daily(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    success, seconds_left = await claim_daily_bonus(call.from_user.id)
    
    if success:
        await call.answer("🎁 +50 монет!" if lang == "ru" else "🎁 +50 coins!", show_alert=True)
    else:
        hours = seconds_left // 3600
        mins = (seconds_left % 3600) // 60
        await call.answer(
            f"⏳ Следующий бонус через {hours}ч {mins}м" if lang == "ru" else f"⏳ Next bonus in {hours}h {mins}m", 
            show_alert=True
        )
        
    text, kb = await get_tap_screen(call.from_user.id, lang)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "tap_noop")
async def tap_noop(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    await call.answer("Энергия восстанавливается..." if lang == "ru" else "Energy is restoring...")

@dp.callback_query(F.data == "tap_exchange")
async def show_tap_exchange(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    tap_data = await get_tap_data(call.from_user.id)
    coins = tap_data[0]
    
    text = (
        f"🔄 <b>Обмен монет</b>\n\n"
        f"💰 У вас: <b>{coins}</b> монет\n\n"
        f"Выберите, на что обменять:"
    ) if lang == "ru" else (
        f"🔄 <b>Exchange coins</b>\n\n"
        f"💰 You have: <b>{coins}</b> coins\n\n"
        f"Choose what to exchange for:"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 1 Фриспин (100 монет)", callback_data="tap_ex_freespin")],
        [InlineKeyboardButton(text="💳 Бонус +10% к депозиту (300 монет)", callback_data="tap_ex_b10")],
        [InlineKeyboardButton(text="⚡ +20 к лимиту энергии (500 монет)", callback_data="tap_ex_energy")],
        [InlineKeyboardButton(text="💳 Бонус +25% к депозиту (1000 монет)", callback_data="tap_ex_b25")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="tap_menu")]
    ]) if lang == "ru" else InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 1 Freespin (100 coins)", callback_data="tap_ex_freespin")],
        [InlineKeyboardButton(text="💳 +10% Deposit Bonus (300 coins)", callback_data="tap_ex_b10")],
        [InlineKeyboardButton(text="⚡ +20 Energy Limit (500 coins)", callback_data="tap_ex_energy")],
        [InlineKeyboardButton(text="💳 +25% Deposit Bonus (1000 coins)", callback_data="tap_ex_b25")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="tap_menu")]
    ])
    
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("tap_ex_"))
async def process_tap_exchange(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    user_id = call.from_user.id
    item = call.data.replace("tap_ex_", "")
    
    cost = 0
    if item == "freespin": cost = 100
    elif item == "b10": cost = 300
    elif item == "energy": cost = 500
    elif item == "b25": cost = 1000
    
    success = await deduct_coins(user_id, cost)
    if not success:
        await call.answer("❌ Недостаточно монет!" if lang == "ru" else "❌ Not enough coins!", show_alert=True)
        return
        
    if item == "freespin":
        await add_freespins(user_id, roulette=1)
        await call.answer("🎰 Вы получили 1 фриспин!" if lang == "ru" else "🎰 You got 1 freespin!", show_alert=True)
    elif item == "b10":
        await add_pending_bonus(user_id, 10)
        await call.answer("💳 Бонус +10% активирован! Сработает при следующем депозите." if lang == "ru" else "💳 +10% bonus activated! Works on next deposit.", show_alert=True)
    elif item == "energy":
        await upgrade_energy_limit(user_id, 20)
        await call.answer("⚡ Лимит энергии повышен на 20!" if lang == "ru" else "⚡ Energy limit increased by 20!", show_alert=True)
    elif item == "b25":
        await add_pending_bonus(user_id, 25)
        await call.answer("💳 Бонус +25% активирован! Сработает при следующем депозите." if lang == "ru" else "💳 +25% bonus activated! Works on next deposit.", show_alert=True)
        
    text, kb = await get_tap_screen(user_id, lang)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("game_"))
async def show_game_bet(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    game = call.data.replace("game_", "")
    
    if game == "price":
        return
        
    if game == "mines":
        if call.from_user.id in MINES_GAMES and MINES_GAMES[call.from_user.id]["active"]:
            await render_mines_game(call, lang)
            return
        await call.message.edit_text(
            t(lang, "mines_title"),
            reply_markup=mines_setup_menu(lang), parse_mode="HTML"
        )
        await call.answer()
        return
    if game == "lottery":
        _, l_fs = await get_freespins(call.from_user.id)
        await call.message.edit_text(
            t(lang, "lottery_title", price=LOTTERY_PRICE, max=LOTTERY_MAX, tickets=l_fs),
            reply_markup=lottery_action_menu(lang), parse_mode="HTML"
        )
        await call.answer()
        return
    if game not in GAME_TITLES:
        return
    title = GAME_TITLES[game][lang]
    await call.message.edit_text(
        t(lang, "choose_bet", title=title, x=MIN_BET),
        reply_markup=bet_menu(game, lang), parse_mode="HTML"
    )
    await call.answer()

def roulette_action_menu(a, lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Red (x2)" if lang == "en" else "🔴 Красное (x2)", callback_data=f"play_roulette_red_{a}"),
         InlineKeyboardButton(text="⚫ Black (x2)" if lang == "en" else "⚫ Чёрное (x2)", callback_data=f"play_roulette_black_{a}")],
        [InlineKeyboardButton(text="🟢 Zero (x36)" if lang == "en" else "🟢 Зеро (x36)", callback_data=f"play_roulette_zero_{a}")],
        [InlineKeyboardButton(text="🎁 Free spin" if lang == "en" else "🎁 Бесплатный спин", callback_data=f"free_roulette_spin_{a}")],
        [InlineKeyboardButton(text=t(lang, "change_bet"), callback_data="game_roulette")]
    ])

def slots_action_menu(a, lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎰 Spin ({a} USDT)" if lang == "en" else f"🎰 Крутить ({a} USDT)", callback_data=f"play_slots_spin_{a}")],
        [InlineKeyboardButton(text=t(lang, "change_bet"), callback_data="game_slots")]
    ])

def coin_action_menu(a, lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🦅 Heads (x1.9)" if lang == "en" else "🦅 Орёл (x1.9)", callback_data=f"play_coin_heads_{a}"),
         InlineKeyboardButton(text="🪙 Tails (x1.9)" if lang == "en" else "🪙 Решка (x1.9)", callback_data=f"play_coin_tails_{a}")],
        [InlineKeyboardButton(text=t(lang, "change_bet"), callback_data="game_coin")]
    ])

def dice_action_menu(a, lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data=f"play_dice_1_{a}"),
         InlineKeyboardButton(text="2", callback_data=f"play_dice_2_{a}"),
         InlineKeyboardButton(text="3", callback_data=f"play_dice_3_{a}")],
        [InlineKeyboardButton(text="4", callback_data=f"play_dice_4_{a}"),
         InlineKeyboardButton(text="5", callback_data=f"play_dice_5_{a}"),
         InlineKeyboardButton(text="6", callback_data=f"play_dice_6_{a}")],
        [InlineKeyboardButton(text=t(lang, "change_bet"), callback_data="game_dice")]
    ])

def wheel_action_menu(a, lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎡 Spin ({a} USDT)" if lang == "en" else f"🎡 Крутить ({a} USDT)", callback_data=f"play_wheel_spin_{a}")],
        [InlineKeyboardButton(text=t(lang, "change_bet"), callback_data="game_wheel")]
    ])

def cards_action_menu(a, lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬆️ Higher (x1.9)" if lang == "en" else "⬆️ Больше (x1.9)", callback_data=f"play_cards_high_{a}"),
         InlineKeyboardButton(text="⬇️ Lower (x1.9)" if lang == "en" else "⬇️ Меньше (x1.9)", callback_data=f"play_cards_low_{a}")],
        [InlineKeyboardButton(text=t(lang, "change_bet"), callback_data="game_cards")]
    ])

def darts_action_menu(a, lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Sector x2", callback_data=f"play_darts_x2_{a}"),
         InlineKeyboardButton(text="🎯 Sector x5", callback_data=f"play_darts_x5_{a}")],
        [InlineKeyboardButton(text="🎯 Bullseye x10", callback_data=f"play_darts_bull_{a}")],
        [InlineKeyboardButton(text=t(lang, "change_bet"), callback_data="game_darts")]
    ])

def basket_action_menu(a, lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏀 2 points (x2)" if lang == "en" else "🏀 2 очка (x2)", callback_data=f"play_basket_2_{a}"),
         InlineKeyboardButton(text="🏀 3 points (x3)" if lang == "en" else "🏀 3 очка (x3)", callback_data=f"play_basket_3_{a}")],
        [InlineKeyboardButton(text=t(lang, "change_bet"), callback_data="game_basket")]
    ])

def craps_action_menu(a, lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 7 or 11 (x2)" if lang == "en" else "🎲 7 или 11 (x2)", callback_data=f"play_craps_711_{a}"),
         InlineKeyboardButton(text="🎲 Double (x5)" if lang == "en" else "🎲 Дубль (x5)", callback_data=f"play_craps_double_{a}")],
        [InlineKeyboardButton(text=t(lang, "change_bet"), callback_data="game_craps")]
    ])

def lottery_action_menu(lang="ru"):
    if lang == "en":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🎟️ 1 ticket ({LOTTERY_PRICE} USDT)", callback_data="play_lottery_1_1"),
             InlineKeyboardButton(text=f"🎟️ 5 tickets ({LOTTERY_PRICE*5} USDT)", callback_data="play_lottery_5_1")],
            [InlineKeyboardButton(text=f"🎟️ 10 tickets ({LOTTERY_PRICE*10} USDT)", callback_data="play_lottery_10_1")],
            [InlineKeyboardButton(text="✏️ Custom amount", callback_data="lottery_custom")],
            [InlineKeyboardButton(text="🎁 Free tickets", callback_data="free_lottery")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="back")]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎟️ 1 билет ({LOTTERY_PRICE} USDT)", callback_data="play_lottery_1_1"),
         InlineKeyboardButton(text=f"🎟️ 5 билетов ({LOTTERY_PRICE*5} USDT)", callback_data="play_lottery_5_1")],
        [InlineKeyboardButton(text=f"🎟️ 10 билетов ({LOTTERY_PRICE*10} USDT)", callback_data="play_lottery_10_1")],
        [InlineKeyboardButton(text="✏️ Своё количество", callback_data="lottery_custom")],
        [InlineKeyboardButton(text="🎁 Бесплатные билеты", callback_data="free_lottery")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

def topup_menu(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0.5 USDT", callback_data="topup_0.5"),
         InlineKeyboardButton(text="1 USDT", callback_data="topup_1")],
        [InlineKeyboardButton(text="5 USDT", callback_data="topup_5"),
         InlineKeyboardButton(text="10 USDT", callback_data="topup_10")],
        [InlineKeyboardButton(text="20 USDT", callback_data="topup_20"),
         InlineKeyboardButton(text="✏️ Custom amount" if lang == "en" else "✏️ Своя сумма", callback_data="topup_custom")],
        [InlineKeyboardButton(text="⭐ Пополнить Stars" if lang == "ru" else "⭐ Top up with Stars", callback_data="topup_stars")],
        [InlineKeyboardButton(text=t(lang, "back"), callback_data="back")]
    ])

def withdraw_menu(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="3 USDT", callback_data="wd_3"),
         InlineKeyboardButton(text="5 USDT", callback_data="wd_5")],
        [InlineKeyboardButton(text="10 USDT", callback_data="wd_10"),
         InlineKeyboardButton(text="20 USDT", callback_data="wd_20")],
        [InlineKeyboardButton(text=t(lang, "withdraw_all"), callback_data="wd_all")],
        [InlineKeyboardButton(text=t(lang, "back"), callback_data="back")]
    ])

def mines_setup_menu(lang="ru"):
    if lang == "en":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💣 2 mines", callback_data="mines_mines_2"),
             InlineKeyboardButton(text="💣 3 mines", callback_data="mines_mines_3")],
            [InlineKeyboardButton(text="💣 5 mines", callback_data="mines_mines_5"),
             InlineKeyboardButton(text="💣 7 mines", callback_data="mines_mines_7")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="back")]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💣 2 мины", callback_data="mines_mines_2"),
         InlineKeyboardButton(text="💣 3 мины", callback_data="mines_mines_3")],
        [InlineKeyboardButton(text="💣 5 мин", callback_data="mines_mines_5"),
         InlineKeyboardButton(text="💣 7 мин", callback_data="mines_mines_7")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

def mines_bet_menu(mines_count, lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0.05 USDT", callback_data=f"mines_bet_{mines_count}_0.05"),
         InlineKeyboardButton(text="0.10 USDT", callback_data=f"mines_bet_{mines_count}_0.1")],
        [InlineKeyboardButton(text="0.50 USDT", callback_data=f"mines_bet_{mines_count}_0.5"),
         InlineKeyboardButton(text="1 USDT", callback_data=f"mines_bet_{mines_count}_1")],
        [InlineKeyboardButton(text="✏️ Custom amount" if lang == "en" else "✏️ Своя сумма", callback_data=f"mines_custom_{mines_count}")],
        [InlineKeyboardButton(text=t(lang, "back"), callback_data="game_mines")]
    ])

def calc_mines_multiplier(opened, mines, total=25):
    if opened == 0:
        return 1.0
    mult = 1.0
    for i in range(opened):
        mult *= (total - i) / (total - mines - i)
    return mult * 0.97

def mines_grid_menu(user_id, lang="ru"):
    game = MINES_GAMES.get(user_id)
    if not game:
        return None
    opened = game["opened"]
    mult = calc_mines_multiplier(len(opened), game["mines"])
    rows = []
    for r in range(5):
        row = []
        for c in range(5):
            idx = r * 5 + c
            emoji = "💎" if idx in opened else "⬜"
            row.append(InlineKeyboardButton(text=emoji, callback_data=f"mines_open_{idx}"))
        rows.append(row)
    if opened:
        potential = game["bet"] * mult
        rows.append([InlineKeyboardButton(
            text=t(lang, "mines_cashout_btn", x=potential, mult=mult),
            callback_data="mines_cashout"
        )])
    else:
        rows.append([InlineKeyboardButton(
            text=t(lang, "mines_start_btn", bet=game['bet']),
            callback_data="mines_noop"
        )])
    rows.append([InlineKeyboardButton(text=t(lang, "mines_cancel"), callback_data="mines_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def luck_menu(lang="ru"):
    if lang == "en":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Open gift (100 points)", callback_data="luck_open")],
            [InlineKeyboardButton(text="📜 Reward history", callback_data="luck_history")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="back")]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Открыть подарок (100 очков)", callback_data="luck_open")],
        [InlineKeyboardButton(text="📜 История наград", callback_data="luck_history")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

def bonus_shop_menu(lang="ru"):
    if lang == "en":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🥉 Starter — 0.5 USDT", callback_data="buybonus_start")],
            [InlineKeyboardButton(text="🥈 Medium — 2 USDT", callback_data="buybonus_medium")],
            [InlineKeyboardButton(text="🥇 Pro — 10 USDT", callback_data="buybonus_pro")],
            [InlineKeyboardButton(text="💎 VIP — 50 USDT", callback_data="buybonus_vip")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="back")]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥉 Стартовый — 0.5 USDT", callback_data="buybonus_start")],
        [InlineKeyboardButton(text="🥈 Средний — 2 USDT", callback_data="buybonus_medium")],
        [InlineKeyboardButton(text="🥇 Про — 10 USDT", callback_data="buybonus_pro")],
        [InlineKeyboardButton(text="💎 VIP — 50 USDT", callback_data="buybonus_vip")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

def daily_bonus_menu(lang="ru"):
    if lang == "en":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Claim daily bonus", callback_data="daily_claim")],
            [InlineKeyboardButton(text="🎡 Wheel of the day", callback_data="wheel_open")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="back")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Забрать ежедневный бонус", callback_data="daily_claim")],
        [InlineKeyboardButton(text="🎡 Колесо дня", callback_data="wheel_open")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")],
    ])

def wheel_menu(lang="ru"):
    if lang == "en":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎡 Spin (free)", callback_data="wheel_spin")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="daily_open")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎡 Крутить (бесплатно)", callback_data="wheel_spin")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="daily_open")],
    ])

ACTION_MENUS = {
    "roulette": roulette_action_menu,
    "slots": slots_action_menu,
    "coin": coin_action_menu,
    "dice": dice_action_menu,
    "wheel": wheel_action_menu,
    "cards": cards_action_menu,
    "darts": darts_action_menu,
    "basket": basket_action_menu,
    "craps": craps_action_menu,
}

async def process_loss(user_id, amount, is_real=True):
    await add_loss(user_id, amount)
    await add_wager_progress(user_id, amount)
    if not is_real:
        return
    lvl1, lvl2, lvl3 = await get_referrers_chain(user_id)
    if lvl1:
        try:
            percent1 = await get_partner_percent(lvl1, REF_PERCENT)
        except Exception:
            percent1 = REF_PERCENT
        ref_amount = amount * percent1 / 100
        await add_ref_earning(lvl1, ref_amount)
        await log_tx(lvl1, "referral", ref_amount, f"from {user_id}")
    if lvl2:
        ref_amount = amount * 3.0 / 100
        await add_ref_earning(lvl2, ref_amount)
        await log_tx(lvl2, "referral", ref_amount, f"L2 from {user_id}")
    if lvl3:
        ref_amount = amount * 1.0 / 100
        await add_ref_earning(lvl3, ref_amount)
        await log_tx(lvl3, "referral", ref_amount, f"L3 from {user_id}")

async def process_win(user_id, amount):
    await add_wager_progress(user_id, amount)

async def pay_bet(user_id, amount):
    if await try_deduct_balance(user_id, amount):
        await add_luck_points(user_id, 1)
        await log_tx(user_id, "bet", -amount, "main")
        return "main"
    if await try_deduct_bonus(user_id, amount):
        await add_luck_points(user_id, 1)
        await log_tx(user_id, "bet", -amount, "bonus")
        return "bonus"
    return None

async def get_app_usdt_balance():
    try:
        balances = await crypto.get_balance()
        for b in balances:
            if b.currency_code == "USDT":
                return float(b.available)
    except Exception:
        pass
    return 0.0

@dp.callback_query(F.data.regexp(r"^(roulette|slots|coin|dice|wheel|cards|darts|basket|craps)_bet_([\d.]+)$"))
async def select_bet(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    parts = call.data.split("_bet_")
    game = parts[0]
    amount = float(parts[1])
    if amount < MIN_BET:
        await call.answer(t(lang, "min_bet", x=MIN_BET), show_alert=True)
        return
    title = GAME_TITLES[game][lang]
    hint = GAME_HINTS[game][lang]
    text = t(lang, "your_bet", title=title, amount=amount, hint=hint)
    await call.message.edit_text(text, reply_markup=ACTION_MENUS[game](amount, lang), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.regexp(r"^(roulette|slots|coin|dice|wheel|cards|darts|basket|craps)_bet_custom$"))
async def bet_custom(call: CallbackQuery, state: FSMContext):
    lang = await get_language(call.from_user.id) or "ru"
    game = call.data.split("_bet_")[0]
    await state.update_data(game=game)
    await state.set_state(States.waiting_bet)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "cancel"), callback_data=f"game_{game}")]])
    await call.message.edit_text(
        t(lang, "enter_amount", min=MIN_BET, max=MAX_BET),
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()

@dp.message(States.waiting_bet)
async def process_custom_bet(message: Message, state: FSMContext):
    lang = await get_language(message.from_user.id) or "ru"
    data = await state.get_data()
    game = data.get("game")
    try:
        amount = float(message.text.replace(",", ".").strip())
    except (ValueError, AttributeError):
        await message.answer(t(lang, "enter_number"))
        return
    if amount < MIN_BET or amount > MAX_BET:
        await message.answer(t(lang, "bet_range", a=MIN_BET, b=MAX_BET))
        return
    await state.clear()
    title = GAME_TITLES[game][lang]
    hint = GAME_HINTS[game][lang]
    text = t(lang, "your_bet", title=title, amount=amount, hint=hint)
    await message.answer(text, reply_markup=ACTION_MENUS[game](amount, lang), parse_mode="HTML")

@dp.callback_query(F.data == "lottery_custom")
async def lottery_custom(call: CallbackQuery, state: FSMContext):
    lang = await get_language(call.from_user.id) or "ru"
    await state.set_state(States.waiting_lottery_count)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "cancel"), callback_data="game_lottery")]])
    await call.message.edit_text(
        t(lang, "lottery_how_many", price=LOTTERY_PRICE),
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()

@dp.message(States.waiting_lottery_count)
async def process_lottery_count(message: Message, state: FSMContext):
    lang = await get_language(message.from_user.id) or "ru"
    try:
        qty = int(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer(t(lang, "lottery_int_only"))
        return
    if qty < 1 or qty > 100:
        await message.answer(t(lang, "lottery_range"))
        return
    await state.clear()
    await execute_lottery_buy(message.from_user.id, qty, message, lang=lang)

@dp.callback_query(F.data.startswith("play_lottery_"))
async def play_lottery(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    parts = call.data.split("_")
    qty = int(parts[2])
    await execute_lottery_buy(call.from_user.id, qty, call.message, lang=lang)
    await call.answer()

@dp.callback_query(F.data == "free_lottery")
async def free_lottery(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    user_id = call.from_user.id
    _, l_fs = await get_freespins(user_id)
    if l_fs <= 0:
        await call.answer(t(lang, "lottery_no_tickets"), show_alert=True)
        return
    use_count = min(l_fs, 10)
    if not await use_lottery_tickets(user_id, use_count):
        await call.answer(t(lang, "lottery_not_enough"), show_alert=True)
        return
    await execute_lottery_buy(user_id, use_count, call.message, free=True, lang=lang)
    await call.answer(t(lang, "lottery_used", x=use_count))

async def execute_lottery_buy(user_id, qty, target, free=False, lang="ru"):
    total_cost = 0 if free else LOTTERY_PRICE * qty
    paid_source = None
    if total_cost > 0:
        paid_source = await pay_bet(user_id, total_cost)
        if not paid_source:
            try:
                await target.answer(t(lang, "not_enough"))
            except Exception:
                pass
            return
    winning = sorted(random.sample(range(1, LOTTERY_MAX + 1), LOTTERY_PICKS))
    total_win = 0
    lines = []
    for i in range(qty):
        ticket = sorted(random.sample(range(1, LOTTERY_MAX + 1), LOTTERY_PICKS))
        matches = len(set(ticket) & set(winning))
        mult = LOTTERY_PAYOUTS.get(matches, 0)
        win = LOTTERY_PRICE * mult
        total_win += win
        icon = "🎉" if matches >= 3 else ("✅" if matches >= 2 else "❌")
        lines.append(f"{icon} {' '.join(str(n) for n in ticket)} — <b>{matches}</b> → <b>{win:.2f}</b>")
    if total_win > 0:
        if free:
            await add_bonus(user_id, total_win, 3.0)
        else:
            await update_balance(user_id, total_win)
            await process_win(user_id, total_win)
            await log_tx(user_id, "win", total_win, "lottery")
    else:
        if not free:
            await process_loss(user_id, total_cost, is_real=(paid_source == "main"))
    new_balance = await get_total_balance(user_id)
    tickets_text = "\n".join(lines) if qty <= 10 else f"({qty})"
    header = t(lang, "lottery_free_header") if free else t(lang, "lottery_header")
    if total_win > 0:
        result = t(lang, "lottery_win_free", x=total_win) if free else t(lang, "lottery_win", x=total_win)
    else:
        result = t(lang, "lottery_no_win")
    text = t(lang, "lottery_result", header=header, winning=' '.join(str(n) for n in winning), tickets=tickets_text, result=result)
    text += f"\n\n💼 {'Balance' if lang == 'en' else 'Баланс'}: <b>{new_balance:.4f} USDT</b>"
    try:
        await target.edit_text(text, reply_markup=lottery_action_menu(lang), parse_mode="HTML")
    except Exception:
        await target.answer(text, reply_markup=lottery_action_menu(lang), parse_mode="HTML")

SLOT_SYMBOLS = ["🍒", "🍋", "🍇", "🔔", "🍀", "💎", "7️⃣"]
SLOT_SCATTER = "⭐"
SLOT_ALL = SLOT_SYMBOLS + [SLOT_SCATTER]

SLOT_PAYOUTS = {
    "🍒": {5: 180, 4: 22, 3: 2.5, 2: 1},
    "🍋": {5: 250, 4: 30, 3: 3.5, 2: 1},
    "🍇": {5: 400, 4: 45, 3: 5, 2: 1},
    "🔔": {5: 600, 4: 70, 3: 7, 2: 1},
    "🍀": {5: 1000, 4: 120, 3: 10, 2: 1},
    "💎": {5: 2500, 4: 300, 3: 15, 2: 1},
    "7️⃣": {5: 6000, 4: 600, 3: 25, 2: 1},
}
FREESPIN_COUNT = 10
FREESPIN_MULT = 2.0
SCATTER_MIN = 3

def spin_slots_logic(bet, is_freespin=False):
    line = [random.choice(SLOT_ALL) for _ in range(5)]
    scatter_count = line.count(SLOT_SCATTER)
    if scatter_count >= SCATTER_MIN:
        return line, 0, scatter_count, True, "scatter"
    win_mult = 0
    count = 0
    first = line[0]
    if first in SLOT_PAYOUTS:
        count = 1
        for i in range(1, 5):
            if line[i] == first:
                count += 1
            else:
                break
        if count >= 2:
            win_mult = SLOT_PAYOUTS[first].get(count, 0)
    win_amount = bet * win_mult
    if is_freespin:
        win_amount *= FREESPIN_MULT
    combo = f"{first} x{count}" if count >= 2 else ""
    return line, win_amount, scatter_count, False, combo

WHEEL_OUTCOMES = [
    ("❌ Lose", 0, 50),
    ("🟢 x1.2", 1.2, 25),
    ("🔵 x1.5", 1.5, 15),
    ("🟣 x2", 2, 7),
    ("🟡 x3", 3, 2),
    ("🔴 x5", 5, 1),
]

@dp.callback_query(F.data.startswith("play_"))
async def play_game(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    parts = call.data.split("_")
    if len(parts) != 4:
        await call.answer("err")
        return
    _, game, action, amount_str = parts
    if game == "lottery":
        await call.answer()
        return
    try:
        amount = float(amount_str)
    except ValueError:
        await call.answer("err")
        return
    user_id = call.from_user.id

    if game == "slots" and user_id in FREESPIN_GAMES:
        fs = FREESPIN_GAMES[user_id]
        if fs.get("left", 0) > 0:
            amount = fs.get("bet", 0.05)
            line, win_amount, sc, trigger, combo = spin_slots_logic(amount, is_freespin=True)
            fs["left"] -= 1
            if win_amount > 0:
                await add_bonus(user_id, win_amount, 3.0)
                await log_tx(user_id, "win", win_amount, "freespin")
            line_str = " | ".join(line)
            new_balance = await get_total_balance(user_id)
            if trigger:
                fs["left"] += FREESPIN_COUNT
            text = f"{t(lang, 'freespin_title', mult=FREESPIN_MULT)}\n\n🎰 {line_str}\n\n"
            if win_amount > 0:
                text += f"🎉 {combo} → <b>{win_amount:.4f} USDT</b>\n"
            else:
                text += t(lang, "freespin_no_luck") + "\n"
            if trigger:
                text += t(lang, "freespin_more", x=FREESPIN_COUNT) + "\n"
            text += "\n" + t(lang, "freespin_left", x=fs['left'])
            if fs["left"] <= 0:
                FREESPIN_GAMES.pop(user_id, None)
                text += "\n\n" + t(lang, "freespin_over")
                kb = ACTION_MENUS[game](amount, lang)
            else:
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=t(lang, "freespin_btn", x=fs['left']), callback_data=f"play_slots_spin_{amount}")],
                    [InlineKeyboardButton(text=t(lang, "change_bet"), callback_data="game_slots")]
                ])
            text += f"\n\n💼 {'Balance' if lang == 'en' else 'Баланс'}: <b>{new_balance:.4f} USDT</b>"
            await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            await call.answer()
            return

    paid_source = await pay_bet(user_id, amount)
    if not paid_source:
        await call.answer(t(lang, "not_enough"), show_alert=True)
        return
    is_real = (paid_source == "main")
    result_text = ""

    if game == "roulette":
        res = random.randint(0, 36)
        if res == 0:
            res_color = "zero"
        elif 1 <= res <= 10 or 19 <= res <= 28:
            res_color = "black"
        else:
            res_color = "red"
        if action == res_color:
            mult = 36 if action == "zero" else 2
            win_amount = amount * mult
            await update_balance(user_id, win_amount)
            await process_win(user_id, win_amount)
            await log_tx(user_id, "win", win_amount, "roulette")
            result_text = f"🎉 <b>{res} ({res_color})</b>\n\n" + t(lang, "win", x=win_amount)
        else:
            await process_loss(user_id, amount, is_real=is_real)
            result_text = f"😢 <b>{res} ({res_color})</b>\n\n" + t(lang, "lose")

    elif game == "slots":
        line, win_amount, sc, trigger, combo = spin_slots_logic(amount)
        line_str = " | ".join(line)
        if win_amount > 0:
            await update_balance(user_id, win_amount)
            await process_win(user_id, win_amount)
            await log_tx(user_id, "win", win_amount, "slots")
            result_text = f"🎰 {line_str}\n\n🎉 <b>{combo}</b> → <b>{win_amount:.4f} USDT</b>"
        else:
            await process_loss(user_id, amount, is_real=is_real)
            result_text = f"🎰 {line_str}\n\n" + t(lang, "lose")
        if trigger:
            FREESPIN_GAMES[user_id] = {"left": FREESPIN_COUNT, "bet": amount}
            result_text += f"\n\n⭐ {FREESPIN_COUNT} freespins!" if lang == "en" else f"\n\n⭐ {FREESPIN_COUNT} фриспинов!"

    elif game == "coin":
        res = random.choice(["heads", "tails"])
        emoji = "🦅" if res == "heads" else "🪙"
        if lang == "en":
            name = "Heads" if res == "heads" else "Tails"
        else:
            name = "Орёл" if res == "heads" else "Решка"
        if res == action:
            win_amount = amount * 1.9
            await update_balance(user_id, win_amount)
            await process_win(user_id, win_amount)
            await log_tx(user_id, "win", win_amount, "coin")
            result_text = f"{emoji} <b>{name}</b>\n\n" + t(lang, "win", x=win_amount)
        else:
            await process_loss(user_id, amount, is_real=is_real)
            result_text = f"{emoji} <b>{name}</b>\n\n" + t(lang, "lose")

    elif game == "dice":
        choice = int(action)
        res = random.randint(1, 6)
        dice_emojis = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        if res == choice:
            win_amount = amount * 5
            await update_balance(user_id, win_amount)
            await process_win(user_id, win_amount)
            await log_tx(user_id, "win", win_amount, "dice")
            result_text = f"{dice_emojis[res-1]} <b>{res}</b>\n\n" + t(lang, "win", x=win_amount)
        else:
            await process_loss(user_id, amount, is_real=is_real)
            result_text = f"{dice_emojis[res-1]} <b>{res}</b>\n\n" + t(lang, "lose")

    elif game == "wheel":
        total = sum(w for _, _, w in WHEEL_OUTCOMES)
        r = random.uniform(0, total)
        cum = 0
        chosen = WHEEL_OUTCOMES[0]
        for o in WHEEL_OUTCOMES:
            cum += o[2]
            if r <= cum:
                chosen = o
                break
        label, mult, _ = chosen
        if mult == 0:
            await process_loss(user_id, amount, is_real=is_real)
            result_text = f"🎡 <b>{label}</b>\n\n" + t(lang, "lose")
        else:
            win_amount = amount * mult
            await update_balance(user_id, win_amount)
            await process_win(user_id, win_amount)
            await log_tx(user_id, "win", win_amount, "wheel")
            result_text = f"🎡 <b>{label}</b>\n\n" + t(lang, "win", x=win_amount)

    elif game == "cards":
        first = random.randint(2, 14)
        second = random.randint(2, 14)
        while second == first:
            second = random.randint(2, 14)

        def cn(n):
            return {11: "J", 12: "Q", 13: "K", 14: "A"}.get(n, str(n)) if lang == "en" else {11: "В", 12: "Д", 13: "К", 14: "Т"}.get(n, str(n))

        if lang == "en":
            line = f"1st: <b>{cn(first)}</b> | 2nd: <b>{cn(second)}</b>"
        else:
            line = f"1-я: <b>{cn(first)}</b> | 2-я: <b>{cn(second)}</b>"
        win = (action == "high" and second > first) or (action == "low" and second < first)
        if win:
            win_amount = amount * 1.9
            await update_balance(user_id, win_amount)
            await process_win(user_id, win_amount)
            await log_tx(user_id, "win", win_amount, "cards")
            result_text = f"{line}\n\n" + t(lang, "win", x=win_amount)
        else:
            await process_loss(user_id, amount, is_real=is_real)
            result_text = f"{line}\n\n" + t(lang, "lose")

    elif game == "darts":
        r = random.random()
        if action == "x2":
            win = r < 0.50
            mult = 2
        elif action == "x5":
            win = r < 0.20
            mult = 5
        elif action == "bull":
            win = r < 0.10
            mult = 10
        else:
            win = False
            mult = 0
        if win:
            win_amount = amount * mult
            await update_balance(user_id, win_amount)
            await process_win(user_id, win_amount)
            await log_tx(user_id, "win", win_amount, "darts")
            result_text = "🎯 <b>Hit!</b>\n\n" + t(lang, "win", x=win_amount) + f" (x{mult})"
        else:
            await process_loss(user_id, amount, is_real=is_real)
            result_text = "🎯 <b>Miss</b>\n\n" + t(lang, "lose")

    elif game == "basket":
        r = random.random()
        if action == "2":
            win = r < 0.50
            mult = 2
        else:
            win = r < 0.3333
            mult = 3
        if win:
            win_amount = amount * mult
            await update_balance(user_id, win_amount)
            await process_win(user_id, win_amount)
            await log_tx(user_id, "win", win_amount, "basket")
            result_text = "🏀 <b>Score!</b>\n\n" + t(lang, "win", x=win_amount) + f" (x{mult})"
        else:
            await process_loss(user_id, amount, is_real=is_real)
            result_text = "🏀 <b>Miss</b>\n\n" + t(lang, "lose")

    elif game == "craps":
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        s = d1 + d2
        faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        emoji = f"{faces[d1-1]} {faces[d2-1]}"
        if action == "711":
            win = s in (7, 11)
            mult = 2
        else:
            win = d1 == d2
            mult = 5
        if win:
            win_amount = amount * mult
            await update_balance(user_id, win_amount)
            await process_win(user_id, win_amount)
            await log_tx(user_id, "win", win_amount, "craps")
            result_text = f"🎲 <b>{emoji} = {s}</b>\n\n" + t(lang, "win", x=win_amount) + f" (x{mult})"
        else:
            await process_loss(user_id, amount, is_real=is_real)
            result_text = f"🎲 <b>{emoji} = {s}</b>\n\n" + t(lang, "lose")

    new_balance = await get_total_balance(user_id)
    if user_id in FREESPIN_GAMES and FREESPIN_GAMES[user_id].get("left", 0) > 0:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "freespin_btn", x=FREESPIN_GAMES[user_id]['left']), callback_data=f"play_slots_spin_{amount}")],
            [InlineKeyboardButton(text=t(lang, "change_bet"), callback_data="game_slots")]
        ])
    else:
        kb = ACTION_MENUS[game](amount, lang)
    await call.message.edit_text(
        f"{result_text}\n\n💼 {'Balance' if lang == 'en' else 'Баланс'}: <b>{new_balance:.4f} USDT</b>",
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("free_roulette_spin_"))
async def free_roulette_spin(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    user_id = call.from_user.id
    parts = call.data.split("_")
    amount = float(parts[-1])
    if not await use_roulette_freespin(user_id):
        await call.answer(t(lang, "no_freespins"), show_alert=True)
        return
    res = random.randint(0, 36)
    if res == 0:
        res_color = "zero"
    elif 1 <= res <= 10 or 19 <= res <= 28:
        res_color = "black"
    else:
        res_color = "red"
    r_fs_left, _ = await get_freespins(user_id)
    base = 0.05
    win_amount = base * 14 if res_color == "zero" else base
    await add_bonus(user_id, win_amount, 3.0)
    await log_tx(user_id, "win", win_amount, "free spin")
    new_balance = await get_total_balance(user_id)
    text = (
        f"{t(lang, 'free_spin_title')}\n\n🎰 <b>{res} ({res_color})</b>\n\n"
        + t(lang, "free_spin_win", x=win_amount, left=r_fs_left)
        + f"\n\n💼 {'Balance' if lang == 'en' else 'Баланс'}: <b>{new_balance:.4f} USDT</b>"
    )
    await call.message.edit_text(text, reply_markup=roulette_action_menu(amount, lang), parse_mode="HTML")
    await call.answer(f"+{win_amount:.4f} USDT")

async def render_mines_game(call: CallbackQuery, lang="ru", edit=True):
    user_id = call.from_user.id
    game = MINES_GAMES.get(user_id)
    if not game or not game["active"]:
        return
    opened_count = len(game["opened"])
    mult = calc_mines_multiplier(opened_count, game["mines"])
    potential = game["bet"] * mult
    text = t(lang, "mines_game", n=game['mines'], bet=game['bet'], opened=opened_count, mult=mult, potential=potential)
    kb = mines_grid_menu(user_id, lang)
    if edit:
        try:
            await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await call.message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await call.message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("mines_mines_"))
async def mines_select_count(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    mines_count = int(call.data.replace("mines_mines_", ""))
    await call.message.edit_text(
        t(lang, "mines_count", n=mines_count),
        reply_markup=mines_bet_menu(mines_count, lang), parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("mines_bet_"))
async def mines_start_with_bet(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    parts = call.data.split("_")
    mines_count = int(parts[2])
    amount = float(parts[3])
    user_id = call.from_user.id
    paid_source = await pay_bet(user_id, amount)
    if not paid_source:
        await call.answer(t(lang, "not_enough"), show_alert=True)
        return
    bombs = set(random.sample(range(25), mines_count))
    MINES_GAMES[user_id] = {
        "bet": amount, "mines": mines_count, "bombs": bombs,
        "opened": set(), "active": True, "is_real": (paid_source == "main")
    }
    await render_mines_game(call, lang, edit=True)
    await call.answer()

@dp.callback_query(F.data.startswith("mines_custom_"))
async def mines_custom_bet(call: CallbackQuery, state: FSMContext):
    lang = await get_language(call.from_user.id) or "ru"
    mines_count = int(call.data.replace("mines_custom_", ""))
    await state.update_data(mines_count=mines_count)
    await state.set_state(States.waiting_mines_bet)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "cancel"), callback_data="game_mines")]])
    await call.message.edit_text(
        t(lang, "mines_custom", n=mines_count, min=MIN_BET),
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()

@dp.message(States.waiting_mines_bet)
async def mines_process_custom_bet(message: Message, state: FSMContext):
    lang = await get_language(message.from_user.id) or "ru"
    data = await state.get_data()
    mines_count = data.get("mines_count", 3)
    try:
        amount = float(message.text.replace(",", ".").strip())
    except (ValueError, AttributeError):
        await message.answer(t(lang, "enter_number"))
        return
    if amount < MIN_BET or amount > MAX_BET:
        await message.answer(t(lang, "bet_range", a=MIN_BET, b=MAX_BET))
        return
    user_id = message.from_user.id
    paid_source = await pay_bet(user_id, amount)
    if not paid_source:
        await message.answer(t(lang, "not_enough"))
        return
    await state.clear()
    bombs = set(random.sample(range(25), mines_count))
    MINES_GAMES[user_id] = {
        "bet": amount, "mines": mines_count, "bombs": bombs,
        "opened": set(), "active": True, "is_real": (paid_source == "main")
    }
    text = t(lang, "mines_game", n=mines_count, bet=amount, opened=0, mult=1.0, potential=amount)
    await message.answer(text, reply_markup=mines_grid_menu(user_id, lang), parse_mode="HTML")

@dp.callback_query(F.data.startswith("mines_open_"))
async def mines_open_cell(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    user_id = call.from_user.id
    game = MINES_GAMES.get(user_id)
    if not game or not game["active"]:
        await call.answer(t(lang, "mines_not_found"), show_alert=True)
        return
    idx = int(call.data.replace("mines_open_", ""))
    if idx in game["opened"]:
        await call.answer(t(lang, "already_opened"))
        return
    if idx in game["bombs"]:
        game["active"] = False
        MINES_GAMES.pop(user_id, None)
        await process_loss(user_id, game["bet"], is_real=game.get("is_real", True))
        balance = await get_total_balance(user_id)
        rows = []
        for r in range(5):
            row = []
            for c in range(5):
                i = r * 5 + c
                emoji = "💥" if i in game["bombs"] else ("💎" if i in game["opened"] else "⬜")
                row.append(InlineKeyboardButton(text=emoji, callback_data="mines_noop"))
            rows.append(row)
        rows.append([InlineKeyboardButton(text=t(lang, "mines_new_game"), callback_data="game_mines")])
        rows.append([InlineKeyboardButton(text=t(lang, "mines_to_menu"), callback_data="back")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await call.message.edit_text(
            t(lang, "mines_bomb_text", bet=game['bet'], bal=balance),
            reply_markup=kb, parse_mode="HTML"
        )
        await call.answer(t(lang, "mines_bomb"), show_alert=True)
        return
    game["opened"].add(idx)
    await render_mines_game(call, lang, edit=True)
    await call.answer(t(lang, "mines_safe"))

@dp.callback_query(F.data == "mines_cashout")
async def mines_cashout(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    user_id = call.from_user.id
    game = MINES_GAMES.get(user_id)
    if not game or not game["active"]:
        await call.answer(t(lang, "mines_not_found"), show_alert=True)
        return
    if not game["opened"]:
        await call.answer(t(lang, "mines_open_first"), show_alert=True)
        return
    opened_count = len(game["opened"])
    mult = calc_mines_multiplier(opened_count, game["mines"])
    win_amount = game["bet"] * mult
    await update_balance(user_id, win_amount)
    await process_win(user_id, win_amount)
    await log_tx(user_id, "win", win_amount, "mines")
    game["active"] = False
    MINES_GAMES.pop(user_id, None)
    balance = await get_total_balance(user_id)
    await call.message.edit_text(
        t(lang, "mines_cashout_text", opened=opened_count, mult=mult, x=win_amount, bal=balance),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "mines_new_game"), callback_data="game_mines")],
            [InlineKeyboardButton(text=t(lang, "mines_to_menu"), callback_data="back")]
        ]),
        parse_mode="HTML"
    )
    await call.answer(f"+{win_amount:.4f} USDT")

@dp.callback_query(F.data == "mines_cancel")
async def mines_cancel(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    user_id = call.from_user.id
    game = MINES_GAMES.get(user_id)
    if not game or not game["active"]:
        await call.answer(t(lang, "mines_not_found"), show_alert=True)
        return
    if not game["opened"]:
        await update_balance(user_id, game["bet"])
    game["active"] = False
    MINES_GAMES.pop(user_id, None)
    balance = await get_total_balance(user_id)
    await call.message.edit_text(
        t(lang, "mines_cancelled", bal=balance),
        reply_markup=main_menu(lang), parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "mines_noop")
async def mines_noop(call: CallbackQuery):
    await call.answer()

@dp.callback_query(F.data == "topup")
async def topup(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    await call.message.edit_text(
        t(lang, "deposit_title", min=MIN_DEPOSIT),
        reply_markup=topup_menu(lang), parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "topup_custom")
async def topup_custom(call: CallbackQuery, state: FSMContext):
    lang = await get_language(call.from_user.id) or "ru"
    await state.set_state(States.waiting_deposit)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "cancel"), callback_data="cancel_deposit")]])
    await call.message.edit_text(t(lang, "deposit_custom", min=MIN_DEPOSIT), reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.message(States.waiting_deposit)
async def process_custom_deposit(message: Message, state: FSMContext):
    lang = await get_language(message.from_user.id) or "ru"
    try:
        amount = float(message.text.replace(",", ".").strip())
    except (ValueError, AttributeError):
        await message.answer(t(lang, "enter_number"))
        return
    if amount < MIN_DEPOSIT:
        await message.answer(t(lang, "min_bet", x=MIN_DEPOSIT))
        return
    if amount > 100000:
        await message.answer(t(lang, "deposit_too_much"))
        return
    await state.clear()
    await create_invoice_and_send(message, message.from_user.id, amount, lang)

@dp.callback_query(F.data == "cancel_deposit")
async def cancel_deposit(call: CallbackQuery, state: FSMContext):
    lang = await get_language(call.from_user.id) or "ru"
    await state.clear()
    await call.message.edit_text(t(lang, "deposit_cancelled"), reply_markup=main_menu(lang))
    await call.answer()

@dp.callback_query(F.data.startswith("topup_"))
async def process_topup(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    try:
        amount = float(call.data.replace("topup_", ""))
    except ValueError:
        return
    await create_invoice_and_send(call.message, call.from_user.id, amount, lang)
    await call.answer()

async def create_invoice_and_send(message, user_id, amount, lang="ru"):
    is_first = await is_first_deposit(user_id)
    rate = 0.50 if is_first else 0.20
    rate_text = "50%" if is_first else "20%"
    bonus = amount * rate
    extra = ("\n🎡 <b>+10 freespins</b>\n🎟️ <b>+10 tickets</b>" if lang == "en" else "\n🎡 <b>+10 фриспинов</b>\n🎟️ <b>+10 билетов</b>") if amount >= 10 else ""
    try:
        invoice = await crypto.create_invoice(asset='USDT', amount=amount)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Pay" if lang == "en" else "💳 Оплатить", url=invoice.bot_invoice_url)],
            [InlineKeyboardButton(text="✅ I paid" if lang == "en" else "✅ Я оплатил", callback_data=f"check_{invoice.invoice_id}_{amount}_{bonus}")]
        ])
        await message.answer(
            t(lang, "deposit_invoice", x=amount, bonus=bonus, rate=rate_text, extra=extra, wager=WAGER_MULTIPLIER),
            reply_markup=kb, parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ {e}")

@dp.callback_query(F.data.startswith("check_") & ~F.data.startswith("check_menu") & ~F.data.startswith("check_create") & ~F.data.startswith("check_claim"))
async def check_payment(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    parts = call.data.split("_")
    invoice_id = int(parts[1])
    amount = float(parts[2])
    bonus = float(parts[3]) if len(parts) > 3 else 0.0
    invoices = await crypto.get_invoices(invoice_ids=invoice_id)
    if invoices and invoices.status == "paid":
        await update_balance(call.from_user.id, amount)
        await mark_deposit(call.from_user.id, amount)
        await log_tx(call.from_user.id, "deposit", amount, "CryptoBot")
        
        pending_bonus_percent = await get_pending_bonus(call.from_user.id)
        if pending_bonus_percent > 0:
            pending_bonus_amount = amount * (pending_bonus_percent / 100.0)
            await add_bonus(call.from_user.id, pending_bonus_amount, WAGER_MULTIPLIER)
            await log_tx(call.from_user.id, "bonus", pending_bonus_amount, "tap_bonus")
            await reset_pending_bonus(call.from_user.id)
            bonus += pending_bonus_amount

        if bonus > 0:
            await add_bonus(call.from_user.id, bonus, WAGER_MULTIPLIER)
            await log_tx(call.from_user.id, "bonus", bonus, "deposit bonus")
        if amount >= 10.0:
            await add_freespins(call.from_user.id, roulette=10, lottery=10)
        await add_luck_points(call.from_user.id, int(amount * 10))
        lvl1, _, _ = await get_referrers_chain(call.from_user.id)
        if lvl1 and amount >= 1.0:
            ref_bonus = amount * 0.05
            await add_ref_earning(lvl1, ref_bonus)
            await log_tx(lvl1, "referral", ref_bonus, f"deposit {call.from_user.id}")
            try:
                l1_lang = await get_language(lvl1) or "ru"
                msg = (f"💰 <b>Referral deposit bonus!</b>\n\n+{ref_bonus:.4f} USDT" if l1_lang == "en"
                       else f"💰 <b>Бонус с депозита реферала!</b>\n\n+{ref_bonus:.4f} USDT")
                await bot.send_message(lvl1, msg, parse_mode="HTML")
            except Exception:
                pass
        balance = await get_total_balance(call.from_user.id)
        msg = t(lang, "deposit_paid", x=amount)
        if bonus > 0:
            msg += f"\n🎁 Bonus: +{bonus:.4f} USDT" if lang == "en" else f"\n🎁 Бонус: +{bonus:.4f} USDT"
        if amount >= 10.0:
            msg += "\n🎡 +10 freespins\n🎟️ +10 tickets" if lang == "en" else "\n🎡 +10 фриспинов\n🎟️ +10 билетов"
        msg += f"\n\n⭐ +{int(amount * 10)}"
        msg += f"\n\n💼 {'Balance' if lang == 'en' else 'Баланс'}: <b>{balance:.4f} USDT</b>"
        await call.message.edit_text(msg, reply_markup=main_menu(lang), parse_mode="HTML")
    else:
        await call.answer(t(lang, "deposit_not_paid"), show_alert=True)

@dp.callback_query(F.data == "withdraw")
async def withdraw(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    user_id = call.from_user.id
    main = await get_balance(user_id)
    bonus = await get_bonus_balance(user_id)
    wager_req, wager_done = await get_wager_info(user_id)
    text = t(lang, "withdraw_title", main=main)
    if bonus > 0:
        text += t(lang, "withdraw_bonus", bonus=bonus, done=wager_done, req=wager_req)
    text += t(lang, "withdraw_min", min=MIN_WITHDRAW)
    await call.message.edit_text(text, reply_markup=withdraw_menu(lang), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("wd_"))
async def process_withdraw(call: CallbackQuery):
    lang = await get_language(call.from_user.id) or "ru"
    value = call.data.replace("wd_", "")
    user_id = call.from_user.id
    main = await get_balance(user_id)
    amount = main if value == "all" else float(value)
    if amount < MIN_WITHDRAW:
        await call.answer(t(lang, "min_bet", x=MIN_WITHDRAW), show_alert=True)
        return
    if main < amount:
        await call.answer(t(lang, "not_enough"), show_alert=True)
        return
    if user_id not in ADMIN_IDS:
        app_balance = await get_app_usdt_balance()
        if app_balance < amount:
            await call.answer(t(lang, "withdraw_empty"), show_alert=True)
            return
    if not await try_deduct_balance(user_id, amount):
        await call.answer(t(lang, "not_enough"), show_alert=True)
        return
    try:
        await crypto.transfer(user_id=user_id, asset='USDT', amount=amount, spend_id=str(uuid.uuid4()))
    except Exception as e:
        await update_balance(user_id, amount)
        await call.message.edit_text(t(lang, "withdraw_error", e=e), parse_mode="HTML")
        await call.answer()
        return
    await log_tx(user_id, "withdraw", -amount, "CryptoBot")
    new_balance = await get_total_balance(user_id)
    await call.message.edit_text(
        t(lang, "withdraw_ok", x=amount, bal=new_balance),
        reply_markup=main_menu(lang), parse_mode="HTML"
    )
    await call.answer()

@dp.message(Command("broadcast"))
async def admin_broadcast(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    text = message.text.replace("/broadcast", "", 1).strip()
    if not text:
        await message.answer("Формат: /broadcast Текст")
        return
    import aiosqlite
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT user_id FROM users")
        rows = await cur.fetchall()
    status = await message.answer(f"📤 {len(rows)}...")
    sent = failed = 0
    for (uid,) in rows:
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await status.edit_text(f"✅ {sent} / ❌ {failed}", parse_mode="HTML")

@dp.message(Command("broadcast_nodef"))
async def admin_broadcast_nodef(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    text = message.text.replace("/broadcast_nodef", "", 1).strip()
    if not text:
        await message.answer("Формат: /broadcast_nodef Текст")
        return
    import aiosqlite
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT user_id FROM users "
            "WHERE (total_deposits IS NULL OR total_deposits = 0) "
            "AND (deposit_count IS NULL OR deposit_count = 0)"
        )
        rows = await cur.fetchall()
    status = await message.answer(f"📤 {len(rows)}...")
    sent = failed = 0
    for (uid,) in rows:
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await status.edit_text(f"✅ {sent} / ❌ {failed}", parse_mode="HTML")

@dp.message(Command("createpromo"))
async def admin_create_promo(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split()
        code = parts[1].upper().strip()
        amount = float(parts[2].replace(",", "."))
        max_uses = int(parts[3])
    except (IndexError, ValueError):
        await message.answer("Формат: /createpromo КОД СУММА ЛИМИТ")
        return
    if amount < MIN_PROMO or max_uses < 1 or not code.isalnum() or len(code) > 32:
        await message.answer("❌ Проверьте параметры")
        return
    ok = await create_promo(code, amount, max_uses, message.from_user.id)
    if not ok:
        await message.answer(f"❌ Код {code} уже есть")
        return
    await message.answer(f"✅ <code>{code}</code> — {amount} USDT × {max_uses}", parse_mode="HTML")

@dp.message(Command("listpromos"))
async def admin_list_promos(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    rows = await list_promos(20)
    if not rows:
        await message.answer("Промокодов нет")
        return
    lines = ["🎟️ <b>Промокоды</b>"]
    for code, amount, max_uses, uses, created_at in rows:
        lines.append(f"<code>{code}</code> — {amount:.2f} — {uses}/{max_uses}")
    await message.answer("\n".join(lines), parse_mode="HTML")

@dp.message(Command("delpromo"))
async def admin_del_promo(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        code = message.text.split()[1].upper()
    except IndexError:
        await message.answer("Формат: /delpromo КОД")
        return
    ok = await delete_promo(code)
    await message.answer(f"{'✅' if ok else '❌'} <code>{code}</code>", parse_mode="HTML")

@dp.message(Command("check"))
async def admin_create_check(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        amount = float(message.text.split()[1].replace(",", "."))
    except (IndexError, ValueError):
        await message.answer("Формат: /check СУММА")
        return
    if amount < MIN_CHECK:
        await message.answer(f"❌ Минимум {MIN_CHECK}")
        return
    code = await create_check(amount, message.from_user.id)
    link = f"https://t.me/{BOT_USERNAME}?start=check_{code}"
    await message.answer(
        f"✅ Чек <b>{amount} USDT</b>\nКод: <code>{code}</code>\nСсылка: <code>{link}</code>",
        parse_mode="HTML"
    )

@dp.message(Command("give"))
async def admin_give(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split()
        target_id = int(parts[1])
        amount = float(parts[2].replace(",", "."))
    except (IndexError, ValueError):
        await message.answer("Формат: /give ID AMOUNT")
        return
    await update_balance(target_id, amount)
    await log_tx(target_id, "bonus", amount, "admin")
    await message.answer(f"✅ +{amount} USDT", parse_mode="HTML")

@dp.message(Command("setpercent"))
async def admin_set_percent(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split()
        target_id = int(parts[1])
        percent = float(parts[2])
    except (IndexError, ValueError):
        await message.answer("Формат: /setpercent ID PERCENT")
        return
    if percent < 0 or percent > 90:
        await message.answer("0-90%")
        return
    from database import set_partner_percent
    await set_partner_percent(target_id, percent)
    await message.answer(f"✅ {target_id} → {percent}%", parse_mode="HTML")

@dp.message(Command("botstats"))
async def bot_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    import aiosqlite
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        total = (await cur.fetchone())[0]
        cur = await db.execute("SELECT SUM(balance) FROM users")
        sum_bal = (await cur.fetchone())[0] or 0
        cur = await db.execute("SELECT SUM(bonus_balance) FROM users")
        sum_bon = (await cur.fetchone())[0] or 0
    await message.answer(
        f"📊 Игроков: <b>{total}</b>\n"
        f"💵 Основных: <b>{sum_bal:.2f} USDT</b>\n"
        f"🎁 Бонусных: <b>{sum_bon:.2f} USDT</b>",
        parse_mode="HTML"
    )

# ============ ОПЛАТА ЗВЕЗДАМИ (TELEGRAM STARS) ============

@dp.callback_query(F.data == "topup_stars")
async def topup_stars_menu(call: CallbackQuery, state: FSMContext):
    lang = await get_language(call.from_user.id) or "ru"
    await state.set_state(States.waiting_stars_amount)
    
    text = t(lang, "stars_amount_title", min=MIN_DEPOSIT)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "cancel"), callback_data="topup")]
    ])
    
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.message(States.waiting_stars_amount)
async def process_stars_amount(message: Message, state: FSMContext):
    lang = await get_language(message.from_user.id) or "ru"
    try:
        amount_usdt = float(message.text.replace(",", ".").strip())
    except (ValueError, AttributeError):
        await message.answer(t(lang, "enter_number"))
        return

    stars_amount = int(amount_usdt / 0.014)

    if stars_amount < MIN_STARS_DEPOSIT:
        await message.answer(
            f"❌ Минимальный депозит: {MIN_STARS_DEPOSIT} звёзд"
            if lang == "ru" else
            f"❌ Minimum deposit: {MIN_STARS_DEPOSIT} Stars"
        )
        return

    await state.clear()

    try:
        await bot.send_invoice(
            chat_id=message.from_user.id,
            title=t(lang, "stars_invoice_title"),
            description=t(lang, "stars_invoice_desc", usdt=amount_usdt, stars=stars_amount),
            payload=f"stars_deposit_{message.from_user.id}_{stars_amount}_{amount_usdt}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="Telegram Stars", amount=stars_amount)],
            start_parameter="stars_deposit"
        )
    except Exception as e:
        logging.exception(f"SEND_INVOICE FAILED: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payment = message.successful_payment
    if not payment.invoice_payload.startswith("stars_deposit_"):
        return

    parts = payment.invoice_payload.split("_")
    stars_paid = payment.total_amount
    usdt_amount = float(parts[-1])
    user_id = message.from_user.id

    await update_balance(user_id, usdt_amount)
    await log_tx(user_id, "deposit", usdt_amount, f"Stars: {stars_paid} XTR")

    is_first = await is_first_deposit(user_id)
    rate = 0.50 if is_first else 0.20
    bonus = usdt_amount * rate

    if bonus > 0:
        await add_bonus(user_id, bonus, WAGER_MULTIPLIER)
        await log_tx(user_id, "bonus", bonus, "stars deposit bonus")

    await mark_deposit(user_id, usdt_amount)
    await add_luck_points(user_id, int(usdt_amount * 10))

    if usdt_amount >= 10.0:
        await add_freespins(user_id, roulette=10, lottery=10)

    lang = await get_language(user_id) or "ru"
    balance = await get_total_balance(user_id)

    msg = t(lang, "stars_paid_ok", stars=stars_paid, usdt=usdt_amount)

    if bonus > 0:
        msg += f"🎁 Бонус: +{bonus:.4f} USDT\n" if lang == "ru" else f"🎁 Bonus: +{bonus:.4f} USDT\n"

    if usdt_amount >= 10.0:
        msg += "🎡 +10 фриспинов\n🎟️ +10 билетов\n" if lang == "ru" else "🎡 +10 freespins\n🎟️ +10 tickets\n"

    msg += f"\n💼 {'Баланс' if lang == 'ru' else 'Balance'}: <b>{balance:.4f} USDT</b>"

    await message.answer(msg, reply_markup=main_menu(lang), parse_mode="HTML")

async def fix_database():
    """Принудительно добавляет недостающие колонки в БД при запуске."""
    async with aiosqlite.connect(DB_NAME) as db:
        columns = [
            ("coins", "INTEGER DEFAULT 0"),
            ("energy", "INTEGER DEFAULT 100"),
            ("energy_limit", "INTEGER DEFAULT 100"),
            ("last_energy_reset", "TIMESTAMP"),
            ("last_daily_bonus", "TIMESTAMP DEFAULT NULL"),
            ("pending_deposit_bonus", "REAL DEFAULT 0.0"),
            ("language", "TEXT DEFAULT NULL"),
            ("daily_streak", "INTEGER DEFAULT 0"),
            ("last_streak_day", "TEXT"),
            ("last_wheel_spin", "TEXT"),
            ("wheel_total_spins", "INTEGER DEFAULT 0"),
        ]
        for col_name, col_type in columns:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                await db.commit()
            except Exception:
                pass

async def main():
    global BOT_USERNAME
    await init_db()
    await fix_database()
    me = await bot.get_me()
    BOT_USERNAME = me.username
    print(f"Бот запущен: @{BOT_USERNAME}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass