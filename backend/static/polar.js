// Состояние
let ws = null;
let reconnectAttempts = 0;
let reconnectTimeout = null;

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
            connectionStatusSpan.style.color = '#4ade80';
        } else {
            connectionStatusSpan.textContent = '✗';
            connectionStatusSpan.dataset.connected = 'false';
            connectionStatusSpan.style.color = '#ff4444';
        }
    }
}

function displayImage(base64Data) {
    // Очищаем контейнер
    imageContainer.innerHTML = '';
    
    // Создаем изображение
    const img = document.createElement('img');
    
    img.onload = () => {
        imageContainer.appendChild(img);
        // Обновляем время
        const now = new Date();
        updateInfo.textContent = `Last update: ${now.toLocaleTimeString()}`;
        updateInfo.style.color = '#4ade80';
    };
    
    img.onerror = () => {
        imageContainer.innerHTML = '<div class="loading-placeholder"><p style="color: #ff4444;">❌ Failed to load image</p></div>';
        updateInfo.textContent = 'Failed to load image';
        updateInfo.style.color = '#ff4444';
    };
    
    img.src = `data:image/png;base64,${base64Data}`;
    img.alt = 'Polar Diagram';
}

function showLoading() {
    imageContainer.innerHTML = `
        <div class="loading-placeholder">
            <div class="loading-spinner"></div>
            <p>Waiting for polar diagram...</p>
        </div>
    `;
    updateInfo.textContent = 'Connecting...';
    updateInfo.style.color = '#aaa';
}

function updateStatus(message, isConnected) {
    if (updateInfo) {
        updateInfo.textContent = message;
        updateInfo.style.color = isConnected ? '#4ade80' : '#ff4444';
    }
}

// WebSocket соединение
function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/polar`;
    
    updateStatus('Connecting to WebSocket...', false);
    showLoading();
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('Polar WebSocket connected');
        updateConnectionStatus(true);
        updateStatus('✅ Connected to polar diagram server', true);
        reconnectAttempts = 0;
    };
    
    ws.onmessage = (event) => {
        console.log('Received polar message');
        
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
            updateStatus('❌ Error parsing polar data', false);
        }
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateConnectionStatus(false);
        updateStatus('❌ WebSocket error occurred', false);
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
    
    updateStatus(`Reconnecting in ${delay/1000}s...`, false);
    
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
    // Кнопка навигации
    const gotoDataBtn = document.getElementById('gotoDataBtn');
    
    if (gotoDataBtn) {
        gotoDataBtn.addEventListener('click', goToData);
    }
    
    // Запускаем WebSocket соединение
    connect();
}

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (ws) {
        ws.close();
    }
    if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
    }
});

// Запуск
init();