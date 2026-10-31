const API_URL = 'https://bread-casino-14.onrender.com';

function getUserId() {
    return localStorage.getItem('tg_user_id') || '';
}

// Простая функция запроса
async function apiRequest(endpoint, method = 'GET', body = null) {
    let url = API_URL + endpoint;
    const userId = getUserId();
    
    // Всегда добавляем user_id в URL
    if (userId) {
        url += (url.includes('?') ? '&' : '?') + 'user_id=' + userId;
    }

    // Если передали body, добавляем его в URL для GET
    if (method === 'GET' && body) {
        for (const key in body) {
            url += '&' + key + '=' + encodeURIComponent(body[key]);
        }
    }

    console.log("Отправка запроса на:", url);

    try {
        const response = await fetch(url, { method: method });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Ошибка');
        return data;
    } catch (error) {
        console.error("Ошибка сети:", error);
        alert("Ошибка: " + error.message);
        throw error;
    }
}

const API = {
    getBalance: () => apiRequest('/api/balance'),
    topup: (amount) => apiRequest('/api/topup', 'GET', { amount: amount }),
    checkPayment: (id) => apiRequest('/api/check_payment/' + id),
    withdraw: (amount) => apiRequest('/api/withdraw', 'POST', { amount: amount })
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