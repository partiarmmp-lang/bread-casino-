const API_URL = 'https://bread-casino-14.onrender.com';

function getUserId() {
    return localStorage.getItem('tg_user_id') || '';
}

async function apiRequest(endpoint, method = 'GET', body = null) {
    let url = `${API_URL}${endpoint}`;
    const headers = { 'X-User-ID': getUserId() };
    const options = { method, headers };

    // Для GET-запросов параметры добавляем в URL
    if (method === 'GET' && body) {
        const params = new URLSearchParams(body).toString();
        url += `?${params}`;
    } 
    // Для POST-запросов отправляем JSON
    else if (body) {
        options.body = JSON.stringify(body);
        headers['Content-Type'] = 'application/json';
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 90000); 
    options.signal = controller.signal;

    try {
        const response = await fetch(url, options);
        clearTimeout(timeoutId);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Ошибка сервера');
        return data;
    } catch (error) {
        clearTimeout(timeoutId);
        console.error('API Error:', error);
        throw error;
    }
}

const API = {
    getBalance: () => apiRequest('/api/balance'),
    // Используем GET для пополнения, чтобы обойти Safari
    topup: (amount) => apiRequest('/api/topup', 'GET', { amount }),
    checkPayment: (id) => apiRequest(`/api/check_payment/${id}`),
    withdraw: (amount) => apiRequest('/api/withdraw', 'POST', { amount })
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
