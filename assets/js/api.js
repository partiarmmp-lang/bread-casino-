// Адрес твоего сервера на Render
const API_URL = 'https://bread-casino-14.onrender.com';

// Получение initData (если открыто из Telegram)
function getInitData() {
    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) {
        return window.Telegram.WebApp.initData;
    }
    // Если открыто в браузере, пробуем достать из localStorage (сохраняется после входа)
    return localStorage.getItem('tg_init_data') || '';
}

// Универсальная функция запроса к серверу
async function apiRequest(endpoint, method = 'GET', body = null) {
    const headers = {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': getInitData()
    };

    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);

    try {
        const response = await fetch(`${API_URL}${endpoint}`, options);
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Ошибка сервера');
        }
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// Функции для работы с API
const API = {
    getBalance: () => apiRequest('/api/balance'),
    topup: (amount) => apiRequest('/api/topup', 'POST', { amount }),
    checkPayment: (invoiceId) => apiRequest(`/api/check_payment/${invoiceId}`),
    withdraw: (amount) => apiRequest('/api/withdraw', 'POST', { amount }),
    spinRoulette: (color, amount) => apiRequest('/api/spin', 'POST', { color, amount })
};

// Функция для обновления баланса на странице
async function updateBalanceUI() {
    try {
        const data = await API.getBalance();
        const balanceElements = document.querySelectorAll('.balance-amount');
        balanceElements.forEach(el => {
            el.textContent = data.balance.toFixed(2) + ' USDT';
        });
    } catch (error) {
        console.error('Не удалось получить баланс');
    }
}
