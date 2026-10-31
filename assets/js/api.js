const API_URL = 'https://bread-casino-14.onrender.com';

function getUserId() {
    return localStorage.getItem('tg_user_id') || '';
}

async function apiRequest(endpoint, method = 'GET', body = null) {
    // Убираем Content-Type: application/json
    const headers = {
        'X-User-ID': getUserId()
    };
    
    const options = { method, headers };

    if (body) {
        // Отправляем данные как HTML-форму (application/x-www-form-urlencoded)
        // Это не требует OPTIONS-запроса
        const formData = new URLSearchParams();
        for (const key in body) {
            formData.append(key, body[key]);
        }
        options.body = formData;
        headers['Content-Type'] = 'application/x-www-form-urlencoded';
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 90000); 
    options.signal = controller.signal;

    try {
        const response = await fetch(`${API_URL}${endpoint}`, options);
        clearTimeout(timeoutId);
        
        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            throw new Error(`Сервер вернул ошибку ${response.status}. Проверьте логи Render.`);
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
    topup: (amount) => apiRequest('/api/topup', 'POST', { amount }),
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
