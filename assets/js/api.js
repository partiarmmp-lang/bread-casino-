const API_URL = 'https://bread-casino-14.onrender.com';

function getUserId() {
    return localStorage.getItem('tg_user_id') || '';
}

async function apiRequest(endpoint, method = 'GET', body = null) {
    let url = `${API_URL}${endpoint}`;
    const headers = {};
    const options = { method, headers };
    const userId = getUserId();

    // Для GET-запросов все данные и user_id передаем в URL
    if (method === 'GET') {
        const params = new URLSearchParams(body || {});
        if (userId) params.append('user_id', userId);
        if (params.toString()) url += `?${params.toString()}`;
    } 
    // Для POST-запросов отправляем JSON, но user_id тоже дублируем в URL
    else if (method === 'POST') {
        if (userId) url += `?user_id=${userId}`;
        if (body) {
            options.body = JSON.stringify(body);
            headers['Content-Type'] = 'application/json';
        }
    }

    // Тайм-аут на случай долгого пробуждения сервера
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 90000); 
    options.signal = controller.signal;

    try {
        const response = await fetch(url, options);
        clearTimeout(timeoutId);
        
        // Проверка, что вернулся JSON (защита от HTML-ошибок)
        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            throw new Error(`Сервер вернул ошибку ${response.status}. Попробуйте позже.`);
        }

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
