const API_URL = 'https://bread-casino-14.onrender.com';

function getUserId() {
    return localStorage.getItem('tg_user_id') || '';
}

async function apiRequest(endpoint, method = 'GET', body = null) {
    const headers = {
        'X-User-ID': getUserId()
    };
    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 90000); 
    options.signal = controller.signal;

    try {
        const response = await fetch(`${API_URL}${endpoint}`, options);
        clearTimeout(timeoutId);
        
        // Проверяем, что сервер вернул именно JSON
        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            // Если пришел не JSON (например, HTML-ошибка), выбрасываем понятную ошибку
            const text = await response.text();
            console.error("Сервер вернул не JSON:", text.substring(0, 100));
            throw new Error("Сервер вернул ошибку. Проверьте логи Render.");
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
