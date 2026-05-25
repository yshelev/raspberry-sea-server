// Theme management
window.initTheme = function() {
    const savedTheme = localStorage.getItem('theme');
    const btn = document.getElementById('themeBtn');
    
    console.log('Polar initTheme called, savedTheme:', savedTheme);
    
    if (savedTheme === 'light') {
        document.body.classList.add('light');
        if (btn) btn.textContent = '☀️';
    } else {
        document.body.classList.remove('light');
        if (btn) btn.textContent = '🌙';
        if (!savedTheme) {
            localStorage.setItem('theme', 'dark');
        }
    }
}

window.toggleTheme = function() {
    const body = document.body;
    const btn = document.getElementById('themeBtn');
    
    console.log('Polar toggleTheme called');
    
    if (body.classList.contains('light')) {
        body.classList.remove('light');
        if (btn) btn.textContent = '🌙';
        localStorage.setItem('theme', 'dark');
    } else {
        body.classList.add('light');
        if (btn) btn.textContent = '☀️';
        localStorage.setItem('theme', 'light');
    }
}

// Состояние
let ws = null;
let reconnectAttempts = 0;
let reconnectTimeout = null;
let currentImage = null; // Храним ссылку на текущий img элемент

// DOM элементы
const connectionStatusSpan = document.getElementById('connectionStatus');
const imageContainer = document.getElementById('imageContainer');
const updateInfo = document.getElementById('updateInfo');

// Функции обновления UI
function updateConnectionStatus(connected) {
    if (connectionStatusSpan) {
        if (connected) {
            connectionStatusSpan.textContent = '✓';
            connectionStatusSpan.dataset.connected = 'true';
        } else {
            connectionStatusSpan.textContent = '✗';
            connectionStatusSpan.dataset.connected = 'false';
        }
    }
}

function displayImage(base64Data) {
    // Если изображения еще нет - создаем
    if (!currentImage) {
        currentImage = document.createElement('img');
        currentImage.alt = 'Полярная диаграмма';
        currentImage.style.maxWidth = '100%';
        currentImage.style.height = 'auto';
        currentImage.style.borderRadius = '8px';
        currentImage.style.boxShadow = '0 5px 15px rgba(0, 0, 0, 0.3)';
        imageContainer.innerHTML = '';
        imageContainer.appendChild(currentImage);
    }
    
    // Просто заменяем src
    currentImage.src = `data:image/png;base64,${base64Data}`;
    
    // Обновляем время
    const now = new Date();
    updateInfo.textContent = `Последнее обновление: ${now.toLocaleTimeString()}`;
    updateInfo.style.color = 'var(--update-text)';
}

function showLoading() {
    // Если нет изображения - показываем плейсхолдер
    if (!currentImage) {
        imageContainer.innerHTML = `
            <div class="loading-placeholder">
                <div class="loading-spinner"></div>
                <p>Ожидание полярной диаграммы...</p>
            </div>
        `;
    }
    updateInfo.textContent = 'Подключение...';
    updateInfo.style.color = 'var(--text-secondary)';
}

function updateStatus(message, isConnected) {
    if (updateInfo) {
        updateInfo.textContent = message;
        updateInfo.style.color = isConnected ? 'var(--update-text)' : 'var(--status-disconnected)';
    }
}

// WebSocket соединение
function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/polar`;
    
    updateStatus('Подключение к вебсокету...', false);
    showLoading();
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        updateConnectionStatus(true);
        updateStatus('Подключены к серверу', true);
        reconnectAttempts = 0;
    };
    
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'polar_image' && data.data) {
                displayImage(data.data);
            } else if (data.type === 'polar_diagram' && data.data) {
                displayImage(data.data);
            } else {
                console.log('Unknown message type:', data);
            }
        } catch (error) {
            console.error('Error parsing message:', error);
            updateStatus('Ошибка при попытке прочитать сообщение сервера', false);
        }
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateConnectionStatus(false);
        updateStatus('Ошибка Вебсокета', false);
    };
    
    ws.onclose = () => {
        console.log('Polar WebSocket disconnected');
        updateConnectionStatus(false);
        updateStatus('❌ Disconnected from server', false);
        scheduleReconnect();
    };
}

function scheduleReconnect() {
    if (reconnectTimeout) clearTimeout(reconnectTimeout);
    
    const delay = Math.min(5000 * Math.pow(2, reconnectAttempts), 30000);
    reconnectAttempts++;
    
    updateStatus(`Переподключение через ${delay/1000}с...`, false);
    
    reconnectTimeout = setTimeout(() => {
        console.log(`Reconnecting polar... Attempt ${reconnectAttempts}`);
        connect();
    }, delay);
}

function reconnect() {
    if (reconnectTimeout) clearTimeout(reconnectTimeout);
    if (ws) {
        ws.close();
    }
    reconnectAttempts = 0;
    connect();
}

// Навигация
function goToData() {
    window.location.href = '/data';
}

// Инициализация
function init() {
    console.log('Initializing polar page...');
    
    // Инициализация темы
    window.initTheme();
    
    // Обработчик кнопки темы
    const themeBtn = document.getElementById('themeBtn');
    if (themeBtn) {
        console.log('Theme button found, attaching handler');
        themeBtn.onclick = window.toggleTheme;
    }
    
    // Кнопка перехода на страницу данных
    const gotoDataBtn = document.getElementById('gotoDataBtn');
    if (gotoDataBtn) {
        gotoDataBtn.addEventListener('click', goToData);
    }
    
    connect();
}

// Обработка закрытия страницы
window.addEventListener('beforeunload', () => {
    if (ws) {
        ws.close();
    }
    if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
    }
});

// Запуск после загрузки DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}