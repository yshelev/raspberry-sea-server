// Глобальная переменная для хранения ссылки на слой схемы
let currentSchemeLayer = null;
let map = null;

// Функция обновления темы карты
async function updateMapTheme(theme) {
    if (!map) return;
    
    try {
        const { YMapDefaultSchemeLayer } = ymaps3;
        
        // Удаляем старый слой схемы, если он есть
        if (currentSchemeLayer) {
            map.removeChild(currentSchemeLayer);
        }
        
        // Создаем новый слой с нужной темой
        currentSchemeLayer = new YMapDefaultSchemeLayer({ theme: theme });
        map.addChild(currentSchemeLayer);
        console.log(`Map theme updated to: ${theme}`);
    } catch (error) {
        console.error('Error updating map theme:', error);
    }
}

// Theme management
function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const btn = document.getElementById('themeBtn');
    
    if (savedTheme === 'light') {
        document.body.classList.add('light');
        if (btn) btn.textContent = '☀️';
        // Обновляем тему карты на светлую, если карта уже создана
        if (map) updateMapTheme('light');
    } else {
        document.body.classList.remove('light');
        if (btn) btn.textContent = '🌙';
        if (!savedTheme) {
            localStorage.setItem('theme', 'dark');
        }
        // Обновляем тему карты на темную, если карта уже создана
        if (map) updateMapTheme('dark');
    }
}

function toggleTheme() {
    const body = document.body;
    const btn = document.getElementById('themeBtn');
    
    if (body.classList.contains('light')) {
        body.classList.remove('light');
        btn.textContent = '🌙';
        localStorage.setItem('theme', 'dark');
        updateMapTheme('dark');
    } else {
        body.classList.add('light');
        btn.textContent = '☀️';
        localStorage.setItem('theme', 'light');
        updateMapTheme('light');
    }
}

const VLADIDOSTOK = [131.91523178522812, 43.123237734648214];

const WIND_BBOX = {
    minLat: 42.75, maxLat: 43.5,
    minLon: 131.5, maxLon: 133.0
};
const GRID_STEP_DEG = 0.1;
const INTERPOLATION_FACTOR = 2;

let lineFeature = null;
let ws = null;
let boatMarker = null;
let radarMode = false;
let currentBoatPosition = null;
let currentBoatCourse = 0;
let points = [];
let waypointsList = [];
let currentTargetIndex = 0;
let currentTargetMarker = null;
let YMapDefaultMarkerClass = null;
let ARRIVAL_THRESHOLD_M = 100;

function saveRouteToStorage() {
    const routeData = {
        waypoints: waypointsList.map(wp => ({ lat: wp.lat, lon: wp.lon })),
        currentTargetIndex: currentTargetIndex,
        timestamp: Date.now()
    };
    localStorage.setItem('sailing_route', JSON.stringify(routeData));
    console.log('Route saved to localStorage');
}

function loadRouteFromStorage() {
    const saved = localStorage.getItem('sailing_route');
    if (saved) {
        try {
            const routeData = JSON.parse(saved);
            if (Date.now() - routeData.timestamp < 3600000) {
                routeData.waypoints.forEach(wp => {
                    addPoint([wp.lon, wp.lat]);
                });
                currentTargetIndex = routeData.currentTargetIndex;
                updateCurrentTarget();
                console.log('Route loaded from localStorage');
            }
        } catch (e) {
            console.error('Error loading route from storage:', e);
        }
    }
}

function updateArrivalThreshold() {
    const slider = document.getElementById('arrivalDistance');
    const valueDisplay = document.getElementById('distanceValue');
    if (slider && valueDisplay) {
        ARRIVAL_THRESHOLD_M = parseInt(slider.value);
        valueDisplay.textContent = ARRIVAL_THRESHOLD_M;
        console.log(`Arrival threshold updated to ${ARRIVAL_THRESHOLD_M} meters`);
        if (radarMode) updateRadarPoints();
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

function windColor(spd) {
    if (spd < 3)  return '#adb5bd';
    if (spd < 7)  return '#4dabf7';
    if (spd < 12) return '#69db7c';
    if (spd < 18) return '#ffd43b';
    if (spd < 25) return '#ff922b';
    return '#f03e3e';
}

async function fetchWindAtPoint(lat, lon) {
    try {
        const resp = await fetch(`/api/wind?lat=${lat}&lon=${lon}`);
        if (!resp.ok) throw new Error(`Wind fetch failed: ${resp.status}`);
        return await resp.json();
    } catch (error) {
        console.warn(`Failed to fetch wind at (${lat}, ${lon}):`, error);
        return { lat, lon, speed: 0, dir: 0 };
    }
}

async function buildWindGrid() {
    const basePoints = [];
    for (let lat = WIND_BBOX.minLat; lat <= WIND_BBOX.maxLat; lat += GRID_STEP_DEG) {
        for (let lon = WIND_BBOX.minLon; lon <= WIND_BBOX.maxLon; lon += GRID_STEP_DEG) {
            basePoints.push({ lat, lon, isBase: true });
        }
    }
    
    const finePoints = [];
    for (let lat = WIND_BBOX.minLat; lat < WIND_BBOX.maxLat; lat += GRID_STEP_DEG) {
        for (let lon = WIND_BBOX.minLon; lon < WIND_BBOX.maxLon; lon += GRID_STEP_DEG) {
            finePoints.push({ lat: lat + GRID_STEP_DEG/2, lon: lon, isBase: false });
            finePoints.push({ lat: lat, lon: lon + GRID_STEP_DEG/2, isBase: false });
            finePoints.push({ lat: lat + GRID_STEP_DEG/2, lon: lon + GRID_STEP_DEG/2, isBase: false });
            finePoints.push({ lat: lat + GRID_STEP_DEG/2, lon: lon + GRID_STEP_DEG, isBase: false });
            finePoints.push({ lat: lat + GRID_STEP_DEG, lon: lon + GRID_STEP_DEG/2, isBase: false });
        }
    }
    
    const seen = new Set();
    const allPoints = [...basePoints, ...finePoints].filter(p => {
        const key = `${p.lat},${p.lon}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return p.lat <= WIND_BBOX.maxLat && p.lon <= WIND_BBOX.maxLon;
    });
    
    console.log(`Fetching wind data for ${allPoints.length} points...`);
    
    const baseResults = [];
    for (let i = 0; i < basePoints.length; i += 5) {
        const batch = basePoints.slice(i, i + 5);
        const fetched = await Promise.all(batch.map(p => fetchWindAtPoint(p.lat, p.lon)));
        baseResults.push(...fetched);
        await new Promise(r => setTimeout(r, 100));
    }
    
    const baseWindMap = new Map();
    basePoints.forEach((p, i) => {
        const w = baseResults[i];
        const key = `${p.lat},${p.lon}`;
        baseWindMap.set(key, w);
    });
    
    const fineResults = allPoints
        .filter(p => !p.isBase)
        .map(p => interpolateWind(p.lat, p.lon, baseWindMap));
    
    console.log(`Fetched ${baseResults.length} base + ${fineResults.length} interpolated points`);
    return [...baseResults, ...fineResults];
}

function interpolateWind(lat, lon, baseWindMap) {
    const latBase = Math.round(Math.floor(lat / GRID_STEP_DEG) * GRID_STEP_DEG * 10) / 10;
    const lonBase = Math.round(Math.floor(lon / GRID_STEP_DEG) * GRID_STEP_DEG * 10) / 10;
    
    const key00 = `${latBase},${lonBase}`;
    const key10 = `${latBase + GRID_STEP_DEG},${lonBase}`;
    const key01 = `${latBase},${lonBase + GRID_STEP_DEG}`;
    const key11 = `${latBase + GRID_STEP_DEG},${lonBase + GRID_STEP_DEG}`;
    
    const p00 = baseWindMap.get(key00);
    const p10 = baseWindMap.get(key10);
    const p01 = baseWindMap.get(key01);
    const p11 = baseWindMap.get(key11);
    
    let speed = 0, dirX = 0, dirY = 0, totalWeight = 0;
    
    [p00, p10, p01, p11].forEach(p => {
        if (!p) return;
        const latWeight = 1 - Math.abs(p.lat - lat) / GRID_STEP_DEG;
        const lonWeight = 1 - Math.abs(p.lon - lon) / GRID_STEP_DEG;
        const weight = latWeight * lonWeight;
        
        speed += p.speed * weight;
        const rad = p.dir * Math.PI / 180;
        dirX += Math.sin(rad) * weight;
        dirY += Math.cos(rad) * weight;
        totalWeight += weight;
    });
    
    if (totalWeight === 0) {
        let nearest = null;
        let minDist = Infinity;
        for (const [key, p] of baseWindMap) {
            const d = Math.abs(p.lat - lat) + Math.abs(p.lon - lon);
            if (d < minDist) {
                minDist = d;
                nearest = p;
            }
        }
        return nearest ? { lat, lon, speed: nearest.speed, dir: nearest.dir } : { lat, lon, speed: 0, dir: 0 };
    }
    
    speed /= totalWeight;
    
    const dirLen = Math.sqrt(dirX * dirX + dirY * dirY);
    let dir;
    if (dirLen < 0.001) {
        const nearest = [p00, p10, p01, p11].find(p => p && p.speed > 0.1);
        dir = nearest ? nearest.dir : 0;
    } else {
        dir = (Math.atan2(dirX / dirLen, dirY / dirLen) * 180 / Math.PI + 360) % 360;
    }
    
    return { lat, lon, speed, dir };
}

function drawWindLayer(windData) {
    if (!windData || windData.length === 0) {
        console.warn('No wind data to draw');
        return;
    }
    
    console.log(`Drawing ${windData.length} wind arrows`);
    
    windData.forEach(({ lat, lon, speed, dir }) => {
        const stroke = windColor(speed);
        const len = 14 + speed * 3.5;
        const lw = 2 + speed * 0.15;
        
        const tipY = (len * 0.7).toFixed(2);
        const headBaseY = Math.max(len * 0.7 - 10, 2).toFixed(2);
        const tailY = (len * 0.3).toFixed(2);
        const lineWidth = Math.max(lw, 1).toFixed(2);
        const rotation = (dir + 180).toFixed(2);

        const svg = `
            <svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="-48 -48 96 96">
            <line
                x1="0" y1="${tailY}"
                x2="0" y2="-${tipY}"
                stroke="${stroke}"
                stroke-width="${lineWidth}"
                stroke-linecap="round"
                transform="rotate(${rotation})"
            />
            <polygon
                points="0,-${tipY} -5,-${headBaseY} 5,-${headBaseY}"
                fill="${stroke}"
                transform="rotate(${rotation})"
            />
            </svg>`;

        const el = document.createElement('div');
        el.innerHTML = svg;
        el.style.pointerEvents = 'none';

        const marker = new ymaps3.YMapMarker(
            { coordinates: [lon, lat] },
            el
        );
        map.addChild(marker);
    });
}

function updateLine() {
    if (lineFeature) {
        map.removeChild(lineFeature);
    }
    
    if (points.length >= 2) {
        const coordinates = points.map(p => p.coordinates);
        lineFeature = new ymaps3.YMapFeature({
            id: 'line',
            geometry: {
                type: 'LineString',
                coordinates: coordinates
            },
            style: {
                stroke: [{width: 3, color: '#74ACFC', opacity: 0.7}]
            }
        });
        map.addChild(lineFeature);
    }
}

function updateWaypointsList() {
    waypointsList = points.map((point, index) => ({
        lat: point.coordinates[1],
        lon: point.coordinates[0],
        marker: point,
        index: index
    }));
    saveRouteToStorage();
}

async function updateCurrentTarget() {
    if (currentTargetMarker) {
        map.removeChild(currentTargetMarker);
    }

    if (currentTargetIndex < waypointsList.length) {
        const target = waypointsList[currentTargetIndex];
        const currentTargetCoordinates = [target.lon, target.lat];

        const { YMapDefaultMarker } = await ymaps3.import('@yandex/ymaps3-default-ui-theme');
        currentTargetMarker = new YMapDefaultMarker({
            coordinates: currentTargetCoordinates,
            color: 'orange',
            size: 'micro',
            draggable: false
        });
        map.addChild(currentTargetMarker);

        if (radarMode) updateRadarPoints();
    } else if (waypointsList.length > 0) {
        if (radarMode) document.getElementById('radarPoints').innerHTML = '';
    }
    saveRouteToStorage();
}

function checkArrival() {
    if (!currentBoatPosition || currentTargetIndex >= waypointsList.length) return;
    const target = waypointsList[currentTargetIndex];
    const distance = calculateDistance(
        currentBoatPosition.lat, currentBoatPosition.lon,
        target.lat, target.lon
    );
    const distanceMeters = distance * 1000;
    console.log(`Distance to target: ${distanceMeters.toFixed(0)} m (threshold: ${ARRIVAL_THRESHOLD_M} m)`);
    if (distanceMeters <= ARRIVAL_THRESHOLD_M) {
        console.log(`Arrived at point ${currentTargetIndex + 1}!`);
        currentTargetIndex++;
        updateCurrentTarget();
    }
}

function drawRadarGrid() {
    const radarGrid = document.getElementById('radarGrid');
    radarGrid.innerHTML = '';
    [25, 50, 75].forEach(radius => {
        const circle = document.createElement('div');
        circle.className = 'radar-grid-circle';
        circle.style.width = `${radius * 2}%`;
        circle.style.height = `${radius * 2}%`;
        circle.style.border = '1px solid var(--radar-grid)';
        radarGrid.appendChild(circle);
    });
    const lineV = document.createElement('div');
    lineV.className = 'radar-grid-line';
    radarGrid.appendChild(lineV);
    const lineH = document.createElement('div');
    lineH.className = 'radar-grid-line-horizontal';
    radarGrid.appendChild(lineH);
}

function updateRadarPoints() {
    if (!currentBoatPosition || currentTargetIndex >= waypointsList.length) {
        document.getElementById('radarPoints').innerHTML = '';
        return;
    }

    const radarPointsDiv = document.getElementById('radarPoints');
    radarPointsDiv.innerHTML = '';

    document.getElementById('radarRotationLayer').style.transform = 
        `rotate(${-currentBoatCourse}deg)`;

    const target = waypointsList[currentTargetIndex];
    const bearing = calculateBearing(
        currentBoatPosition.lat, currentBoatPosition.lon,
        target.lat, target.lon
    );
    const distance = calculateDistance(
        currentBoatPosition.lat, currentBoatPosition.lon,
        target.lat, target.lon
    );
    const distanceMeters = distance * 1000;

    const maxRadarRange = 10, radarRadius = 40;
    const radarDistance = Math.min((distance / maxRadarRange) * radarRadius, radarRadius);
    const angleRad = bearing * Math.PI / 180;
    const x = 50 + Math.sin(angleRad) * radarDistance;
    const y = 50 - Math.cos(angleRad) * radarDistance;

    const pointDiv = document.createElement('div');
    pointDiv.className = 'radar-point';
    pointDiv.style.left = `${x}%`;
    pointDiv.style.top = `${y}%`;
    pointDiv.title = `Target ${currentTargetIndex + 1}\nAzimut: ${bearing.toFixed(1)}°\nDistance: ${distanceMeters.toFixed(0)} m`;
    radarPointsDiv.appendChild(pointDiv);
}

function toggleRadarMode() {
    const mapDiv = document.getElementById('map');
    const radarContainer = document.getElementById('radarContainer');
    const toggleBtn = document.getElementById('radarToggle');
    radarMode = !radarMode;
    if (radarMode) {
        mapDiv.style.display = 'none';
        radarContainer.style.display = 'block';
        toggleBtn.innerHTML = 'Карта';
        drawRadarGrid();
        updateRadarPoints();
    } else {
        mapDiv.style.display = 'block';
        radarContainer.style.display = 'none';
        toggleBtn.innerHTML = 'Режим радара';
    }
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'gps') {
                const gps = data.data;
                if (gps.lon && gps.lat) {
                    currentBoatPosition = { lat: gps.lat, lon: gps.lon };
                    updateBoatMarker([gps.lon, gps.lat]);
                    checkArrival();
                    if (radarMode) updateRadarPoints();
                }
            } else if (data.type === 'lag') {
                const lag = data.data;
                if (lag.course !== undefined && lag.course !== null) {
                    currentBoatCourse = lag.course;
                    if (radarMode) updateRadarPoints();
                }
            }
        } catch (error) {
            console.error('Error parsing message:', error);
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
        console.log('WebSocket closed, reconnecting in 3s...');
        ws = null;
        setTimeout(connectWebSocket, 3000);
    };
}

async function updateBoatMarker(coordinates) {
    await ymaps3.ready;
    const { YMapDefaultMarker } = await ymaps3.import('@yandex/ymaps3-default-ui-theme');
    if (boatMarker) map.removeChild(boatMarker);
    boatMarker = new YMapDefaultMarker({
        coordinates,
        color: 'red',
        size: 'micro'
    });
    map.addChild(boatMarker);
}

function addPoint(coordinates) {
    const marker = new YMapDefaultMarkerClass({
        coordinates: coordinates,
        color: 'white',
        size: 'micro',
        draggable: true
    });
    
    points.push(marker);
    map.addChild(marker);
    
    updateLine();
    updateWaypointsList();
    
    if (points.length === 1) {
        currentTargetIndex = 0;
        updateCurrentTarget();
    }
    
    if (radarMode) {
        updateRadarPoints();
    }
}

async function main() {
    // Инициализация темы ДО создания карты
    initTheme();
    
    // Добавляем обработчик для кнопки темы
    const themeBtn = document.getElementById('themeBtn');
    if (themeBtn) {
        themeBtn.addEventListener('click', toggleTheme);
    }
    
    await ymaps3.ready;

    const {
        YMap,
        YMapListener,
        YMapDefaultSchemeLayer,
        YMapDefaultFeaturesLayer,
        YMapControls,
        YMapControlButton
    } = ymaps3;

    ymaps3.import.registerCdn('https://cdn.jsdelivr.net/npm/{package}', [
        '@yandex/ymaps3-default-ui-theme@latest',
        '@yandex/ymaps3-hint@latest'
    ]);

    const {YMapDefaultMarker} = await ymaps3.import('@yandex/ymaps3-default-ui-theme');
    YMapDefaultMarkerClass = YMapDefaultMarker;

    // Получаем текущую тему для карты
    const currentTheme = document.body.classList.contains('light') ? 'light' : 'dark';
    
    map = new YMap(
        document.getElementById('map'),
        {
            location: {
                center: VLADIDOSTOK,
                zoom: 10
            },
            theme: currentTheme
        }
    );

    // Создаем и сохраняем слой схемы для возможности обновления
    currentSchemeLayer = new YMapDefaultSchemeLayer({ theme: currentTheme });
    map.addChild(currentSchemeLayer);
    map.addChild(new YMapDefaultFeaturesLayer());

    const clickHandler = async (object, data) => {
        if (points.length == 0 || points[points.length - 1].coordinates != object?.entity?.coordinates) {
            addPoint(data.coordinates);
        }
    };

    const dragHandler = (object, data) => {
        if (object?.type == 'marker') {
            updateLine();
            updateWaypointsList();
            if (radarMode) {
                updateRadarPoints();
            }
        }
    };

    map.addChild(new YMapListener({
        layer: 'any',
        onClick: clickHandler,
        onDrag: dragHandler
    }));

    const controls = new YMapControls({position: 'top right'});
    
    const center_button = new YMapControlButton({
        text: 'Владивосток',
        onClick: () => {
            map.setLocation({
                center: VLADIDOSTOK,
                zoom: 10
            });
        }
    });
    
    const clear_button = new YMapControlButton({
        text: 'Очистить',
        onClick: () => {
            points.forEach(p => {
                map.removeChild(p);
            });
            points = [];
            waypointsList = [];
            currentTargetIndex = 0;

            if (lineFeature) {
                map.removeChild(lineFeature);
                lineFeature = null;
            }
            
            if (currentTargetMarker) {
                map.removeChild(currentTargetMarker);
                currentTargetMarker = null;
            }
            
            if (radarMode) {
                document.getElementById('radarPoints').innerHTML = '';
            }
            saveRouteToStorage();
        }
    });
    
    controls.addChild(center_button);
    controls.addChild(clear_button);
    
    map.addChild(controls);
    
    const distanceSlider = document.getElementById('arrivalDistance');
    if (distanceSlider) {
        distanceSlider.addEventListener('input', updateArrivalThreshold);
    }
    
    const dataPageBtn = document.getElementById('dataPageBtn');
    if (dataPageBtn) {
        dataPageBtn.addEventListener('click', () => {
            window.location.href = '/data';
        });
    }
    
    const radarToggleBtn = document.getElementById('radarToggle');
    if (radarToggleBtn) {
        radarToggleBtn.addEventListener('click', toggleRadarMode);
    }
    
    updateArrivalThreshold();
    connectWebSocket();
    
    loadRouteFromStorage();
    
    buildWindGrid().then(drawWindLayer).catch(err => {
        console.error('Wind load error:', err);
    });
}

main();

let currentWindTwd = null;
let currentWindTws = null;
let aiTrajectoryFeature = null;
let aiHeadingMarker = null;

window.clearAiRoute = function() {
    if (aiTrajectoryFeature && map) { 
        try { map.removeChild(aiTrajectoryFeature); } catch(e) {}
        aiTrajectoryFeature = null; 
    }
    if (aiHeadingMarker && map) { 
        try { map.removeChild(aiHeadingMarker); } catch(e) {}
        aiHeadingMarker = null; 
    }
    const panel = document.getElementById('aiResultPanel');
    if (panel) panel.style.display = 'none';
};

window.drawAiTrajectory = function(trajectory, recommendedHeading) {
    if (!map) return;
    window.clearAiRoute();
    if (!trajectory || trajectory.length < 2) return;

    aiTrajectoryFeature = new ymaps3.YMapFeature({
        id: 'ai-trajectory',
        geometry: {
            type: 'LineString',
            coordinates: trajectory.map(([lat, lon]) => [lon, lat])
        },
        style: { stroke: [{ width: 3, color: '#4ade80', opacity: 0.85, dasharray: '8 5' }] }
    });
    map.addChild(aiTrajectoryFeature);

    if (recommendedHeading !== null && trajectory.length > 0) {
        const [startLat, startLon] = trajectory[0];
        const el = document.createElement('div');
        el.style.cssText = 'position:relative; pointer-events:none;';
        el.innerHTML = `
            <div style="transform:rotate(${recommendedHeading}deg);filter:drop-shadow(0 0 5px #4ade80);">
                <svg width="44" height="44" viewBox="0 0 44 44">
                    <polygon points="22,3 32,36 22,29 12,36" fill="#4ade80" opacity="0.95"/>
                    <circle cx="22" cy="22" r="3" fill="#fff"/>
                </svg>
            </div>
            <div style="position:absolute;top:46px;left:50%;transform:translateX(-50%);
                background:rgba(0,0,0,0.75);color:#4ade80;font:bold 11px monospace;
                padding:2px 7px;border-radius:5px;white-space:nowrap;border:1px solid #4ade80;">
                ${Math.round(recommendedHeading)}°
            </div>`;
        aiHeadingMarker = new ymaps3.YMapMarker(
            { coordinates: [startLon, startLat], anchor: [0.5, 0.5] },
            el
        );
        map.addChild(aiHeadingMarker);
    }
};

window.showAiResultPanel = function(result) {
    const panel = document.getElementById('aiResultPanel');
    if (!panel) return;
    const cp = result.checkpoints_reachable;
    const total = result.total_checkpoints;
    const allOk = cp >= total;
    panel.innerHTML = `
        <div class="ai-result-panel__header">
            <span>🤖 AI Маршрут</span>
            <button class="ai-result-panel__close" onclick="window.clearAiRoute()">✕</button>
        </div>
        <div class="ai-result-panel__grid">
            <span class="ai-result-panel__label">Курс</span>
            <span class="ai-result-panel__value">${result.recommended_heading !== null ? Math.round(result.recommended_heading) + '°' : '—'}</span>
            <span class="ai-result-panel__label">Время</span>
            <span class="ai-result-panel__value">${result.estimated_time_min} мин</span>
            <span class="ai-result-panel__label">Точки</span>
            <span class="ai-result-panel__value" style="color:${allOk ? 'var(--value-color)' : '#ffd43b'}">${allOk ? '✅' : '⚠️'} ${cp}/${total}</span>
            <span class="ai-result-panel__label">Ветер</span>
            <span class="ai-result-panel__value">${result.wind_tws?.toFixed(1) ?? '—'} кн / ${result.wind_twd !== undefined ? Math.round(result.wind_twd) + '°' : '—'}</span>
        </div>`;
    panel.style.display = 'block';
};

window.requestAiRoute = async function() {
    if (!waypointsList || waypointsList.length < 2) {
        alert('Добавьте минимум 2 точки маршрута на карту');
        return;
    }
    const btn = document.getElementById('aiRouteBtn');
    const originalText = btn ? btn.textContent : 'AI Маршрут';
    if (btn) { btn.textContent = 'Расчёт...'; btn.disabled = true; }

    try {
        const body = {
            checkpoints: waypointsList.map(wp => ({ lat: wp.lat, lon: wp.lon })),
            wind_twd: currentWindTwd,
            wind_tws: currentWindTws,
        };
        const resp = await fetch('/api/ai-route', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const result = await resp.json();
        if (result.error) { alert('AI: ' + result.error); return; }
        window.drawAiTrajectory(result.trajectory, result.recommended_heading);
        window.showAiResultPanel(result);
    } catch (e) {
        console.error('AI route error:', e);
        alert('Ошибка запроса AI-маршрута. Проверь консоль.');
    } finally {
        if (btn) { btn.textContent = originalText; btn.disabled = false; }
    }
};

(function patchWebSocketForAI() {
    let checkCount = 0;
    const interval = setInterval(() => {
        if (ws && ws._aiPatched !== true) {
            ws._aiPatched = true;
            const originalOnMessage = ws.onmessage;
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'true_wind') {
                        if (data.data.twd !== undefined) currentWindTwd = data.data.twd;
                        if (data.data.tws !== undefined) currentWindTws = data.data.tws;
                        console.log(`AI получил данные ветра: ${currentWindTws} узлов, направление ${currentWindTwd}°`);
                    }
                } catch (e) {}
                if (originalOnMessage) originalOnMessage.call(ws, event);
            };
            clearInterval(interval);
            console.log('AI WebSocket патч успешно установлен');
        }
        checkCount++;
        if (checkCount > 100) clearInterval(interval);
    }, 200);
})();

setTimeout(() => {
    const aiBtn = document.getElementById('aiRouteBtn');
    if (aiBtn) {
        const newAiBtn = aiBtn.cloneNode(true);
        aiBtn.parentNode.replaceChild(newAiBtn, aiBtn);
        newAiBtn.addEventListener('click', window.requestAiRoute);
        console.log('AI кнопка активирована');
    } else {
        console.log('AI кнопка не найдена');
    }
}, 1500);