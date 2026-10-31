// Ссылка на твой сервер Render
const API_URL = 'https://bread-casino-14.onrender.com';

// Получаем ID из localStorage (сохраняется после входа через Telegram)
function getUserId() {
    return localStorage.getItem('tg_user_id') || '';
}

// Универсальная функция запроса
async function apiRequest(endpoint, method = 'GET', body = null) {
    const headers = {
        'Content-Type': 'application/json',
        'X-User-ID': getUserId()
    };
    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);

    try {
        const response = await fetch(`${API_URL}${endpoint}`, options);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Ошибка сервера');
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

const API = {
    getBalance: () => apiRequest('/api/balance'),
    topup: (amount) => apiRequest('/api/topup', 'POST', { amount }),
    checkPayment: (id) => apiRequest(`/api/check_payment/${id}`),
    withdraw: (amount) => apiRequest('/api/withdraw', 'POST', { amount }),
    playPlinko: (amount) => apiRequest('/api/plinko', 'POST', { amount })
};

async function updateBalanceUI() {
    const display = document.getElementById('balance-display');
    if (!display) return;
    try {
        const data = await API.getBalance();
        display.textContent = parseFloat(data.balance).toFixed(2) + ' USDT';
    } catch (error) {
        display.textContent = "Ошибка";
    }
}
