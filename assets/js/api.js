async function apiRequest(endpoint, method = 'GET', body = null) {
    let url = `${API_URL}${endpoint}`;
    const headers = {};
    const options = { method, headers };
    const userId = getUserId();

    if (method === 'GET') {
        const params = new URLSearchParams(body || {});
        if (userId) params.append('user_id', userId);
        if (params.toString()) url += `?${params.toString()}`;
    } else if (method === 'POST') {
        if (userId) url += `?user_id=${userId}`;
        if (body) {
            options.body = JSON.stringify(body);
            headers['Content-Type'] = 'application/json';
        }
    }

    // Показываем, на какой адрес уходит запрос
    alert("Отправка на: " + url);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 90000); 
    options.signal = controller.signal;

    try {
        const response = await fetch(url, options);
        clearTimeout(timeoutId);
        
        // Если ответ не JSON — показываем статус
        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            const text = await response.text();
            alert("Сервер ответил не JSON. Статус: " + response.status + ". Текст: " + text.substring(0, 200));
            throw new Error("Non-JSON response");
        }

        const data = await response.json();
        if (!response.ok) {
            alert("Ошибка сервера: " + (data.error || response.status));
            throw new Error(data.error || 'Ошибка сервера');
        }
        return data;
    } catch (error) {
        clearTimeout(timeoutId);
        // Показываем сетевую ошибку (например, Load failed)
        alert("Сетевая ошибка: " + error.message);
        console.error('API Error:', error);
        throw error;
    }
}