// Состояние
let ws = null;
let currentBoatPosition = null;
let waypoints = [];
let currentTargetIndex = 0;

// DOM элементы
const connectionStatusSpan = document.getElementById('connectionStatus');
const gpsSpan = document.getElementById('gpsData');
const windSpan = document.getElementById('windData');
const trueWindSpan = document.getElementById('trueWindData');
const depthSpan = document.getElementById('depthData');
const lagSpan = document.getElementById('lagData');
const nextPointIndexSpan = document.getElementById('nextPointIndex');
const nextPointDistanceSpan = document.getElementById('nextPointDistance');
const nextPointBearingSpan = document.getElementById('nextPointBearing');
const gotoMapBtn = document.getElementById('gotoMapBtn');

// Загрузка маршрута из localStorage
function loadRouteFromStorage() {
    const saved = localStorage.getItem('sailing_route');
    if (saved) {
        try {
            const routeData = JSON.parse(saved);
            // Проверяем, что данные не старше 1 часа
            if (Date.now() - routeData.timestamp < 3600000) {
                waypoints = routeData.waypoints;
                currentTargetIndex = routeData.currentTargetIndex;
                updateNextPointInfo();
                console.log('Route loaded from localStorage:', waypoints.length, 'points');
            } else {
                console.log('Saved route is too old, ignoring');
            }
        } catch (e) {
            console.error('Error loading route from storage:', e);
        }
    }
}

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

function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
            Math.cos(φ1) * Math.cos(φ2) *
            Math.sin(Δλ/2) * Math.sin(Δλ/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

function calculateBearing(lat1, lon1, lat2, lon2) {
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;
    const y = Math.sin(Δλ) * Math.cos(φ2);
    const x = Math.cos(φ1) * Math.sin(φ2) -
            Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

function updateNextPointInfo() {
    if (!nextPointIndexSpan || !nextPointDistanceSpan || !nextPointBearingSpan) return;
    
    if (waypoints.length === 0) {
        nextPointIndexSpan.textContent = '—';
        nextPointDistanceSpan.textContent = '—';
        nextPointBearingSpan.textContent = '—';
        return;
    }
    
    if (!currentBoatPosition) {
        nextPointIndexSpan.textContent = `${currentTargetIndex+1}/${waypoints.length}`;
        nextPointDistanceSpan.textContent = 'ожидание GPS';
        nextPointBearingSpan.textContent = 'ожидание GPS';
        return;
    }
    
    if (currentTargetIndex >= waypoints.length) {
        nextPointIndexSpan.textContent = '✅ Маршрут завершён';
        nextPointDistanceSpan.textContent = '0 м';
        nextPointBearingSpan.textContent = '—';
        return;
    }

    const target = waypoints[currentTargetIndex];
    const distance = calculateDistance(
        currentBoatPosition.lat, currentBoatPosition.lon,
        target.lat, target.lon
    );
    const distanceMeters = distance * 1000;
    const bearing = calculateBearing(
        currentBoatPosition.lat, currentBoatPosition.lon,
        target.lat, target.lon
    );

    nextPointIndexSpan.textContent = `${currentTargetIndex+1}/${waypoints.length}`;
    nextPointDistanceSpan.textContent = `${distanceMeters.toFixed(0)} м`;
    nextPointBearingSpan.textContent = `${bearing.toFixed(0)}°`;
}

function checkArrival() {
    if (!currentBoatPosition || waypoints.length === 0 || currentTargetIndex >= waypoints.length) return;
    const target = waypoints[currentTargetIndex];
    const distance = calculateDistance(
        currentBoatPosition.lat, currentBoatPosition.lon,
        target.lat, target.lon
    );
    const distanceMeters = distance * 1000;
    const ARRIVAL_THRESHOLD = 100;
    if (distanceMeters <= ARRIVAL_THRESHOLD) {
        console.log(`Прибыли в точку ${currentTargetIndex+1}, переходим к следующей`);
        currentTargetIndex++;
        updateNextPointInfo();
        // Обновляем сохранённый маршрут
        const routeData = {
            waypoints: waypoints,
            currentTargetIndex: currentTargetIndex,
            timestamp: Date.now()
        };
        localStorage.setItem('sailing_route', JSON.stringify(routeData));
    }
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'gps':
            const gps = data.data;
            if (gpsSpan) {
                gpsSpan.innerHTML = `${gps.lat?.toFixed(6) || '?'}°, ${gps.lon?.toFixed(6) || '?'}°`;
            }
            if (gps.lat && gps.lon) {
                currentBoatPosition = { lat: gps.lat, lon: gps.lon };
                updateNextPointInfo();
                checkArrival();
            }
            break;
        case 'wind':
            const wind = data.data;
            if (windSpan) {
                windSpan.innerHTML = `${wind.aws || 0} м/с, ${wind.direction || 0}°`;
            }
            break;
        case 'true_wind':
            const tw = data.data;
            if (trueWindSpan) {
                trueWindSpan.innerHTML = `${tw.tws?.toFixed(1) || 0} м/с, ${tw.twd?.toFixed(0) || 0}°`;
            }
            break;
        case 'depth':
            if (depthSpan) {
                depthSpan.innerHTML = `${data.data.depth_m || 0} м`;
            }
            break;
        case 'lag':
            const lag = data.data;
            if (lagSpan) {
                lagSpan.innerHTML = `${lag.speed_knots || 0} узлов`;
            }
            break;
        default:
            console.log('Неизвестный тип данных:', data.type);
    }
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        updateConnectionStatus(true);
        console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (error) {
            console.error('Ошибка разбора JSON:', error);
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateConnectionStatus(false);
    };

    ws.onclose = () => {
        updateConnectionStatus(false);
        console.log('WebSocket closed, reconnecting in 3s...');
        setTimeout(connectWebSocket, 3000);
    };
}

function goToMap() {
    window.location.href = '/map';
}

function init() {
    if (gotoMapBtn) {
        gotoMapBtn.addEventListener('click', goToMap);
    }
    
    // Загружаем маршрут из localStorage
    loadRouteFromStorage();
    
    connectWebSocket();
    updateConnectionStatus(false);
}

init();