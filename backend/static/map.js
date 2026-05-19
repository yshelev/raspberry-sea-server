const VLADIDOSTOK = [131.91523178522812, 43.123237734648214];

const WIND_BBOX = {
    minLat: 42.75, maxLat: 43.5,
    minLon: 131.5, maxLon: 133.0
};
const GRID_STEP_DEG = 0.1;

let lineFeature = null;
let ws = null;
let boatMarker = null;
let radarMode = false;
let currentBoatPosition = null;
let currentBoatCourse = 0;
let map = null;
let points = [];
let waypointsList = [];
let currentTargetIndex = 0;
let currentTargetMarker = null;
let YMapDefaultMarkerClass = null;
let ARRIVAL_THRESHOLD_M = 100;

function updateConnectionStatus(connected) {
    const statusIndicator = document.getElementById('connectionStatus');
    if (connected) {
        statusIndicator.innerHTML = '✓';
        statusIndicator.title = 'Connected';
    } else {
        statusIndicator.innerHTML = '✗';
        statusIndicator.title = 'Disconnected';
    }
}

function updateArrivalThreshold() {
    const slider = document.getElementById('arrivalDistance');
    const valueDisplay = document.getElementById('distanceValue');
    if (slider && valueDisplay) {
        ARRIVAL_THRESHOLD_M = parseInt(slider.value);
        valueDisplay.textContent = ARRIVAL_THRESHOLD_M;
        console.log(`Arrival threshold updated to ${ARRIVAL_THRESHOLD_M} meters`);
        updateNextPointInfo();
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
    const points = [];
    for (let lat = WIND_BBOX.minLat; lat <= WIND_BBOX.maxLat; lat += GRID_STEP_DEG) {
        for (let lon = WIND_BBOX.minLon; lon <= WIND_BBOX.maxLon; lon += GRID_STEP_DEG) {
            points.push({ lat, lon });
        }
    }
    
    console.log(`Fetching wind data for ${points.length} points...`);
    
    const results = [];
    for (let i = 0; i < points.length; i += 5) {
        const batch = points.slice(i, i + 5);
        const fetched = await Promise.all(batch.map(p => fetchWindAtPoint(p.lat, p.lon)));
        results.push(...fetched);
        await new Promise(r => setTimeout(r, 100));
    }
    
    console.log(`Fetched ${results.length} wind points`);
    return results;
}

function drawWindLayer(windData) {
    if (!windData || windData.length === 0) {
        console.warn('No wind data to draw');
        return;
    }
    
    console.log(`Drawing ${windData.length} wind arrows`);
    
    windData.forEach(({ lat, lon, speed, dir }) => {
        const stroke = windColor(speed);
        const len = 8 + speed * 2.5;
        const lw = 1 + speed * 0.1;

        const svg = `
            <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="-32 -32 64 64">
            <line
                x1="0" y1="${len * 0.3}"
                x2="0" y2="-${len * 0.7}"
                stroke="${stroke}"
                stroke-width="${lw}"
                stroke-linecap="round"
                transform="rotate(${dir + 180})"
            />
            <polygon
                points="0,-${len * 0.7} -3,-${len * 0.7 - 6} 3,-${len * 0.7 - 6}"
                fill="${stroke}"
                transform="rotate(${dir + 180})"
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
    
    updateNextPointInfo();
}

function updateNextPointInfo() {
    const nextPointDiv = document.getElementById('nextPointInfo');
    
    if (waypointsList.length === 0) {
        nextPointDiv.innerHTML = `
            <div class="data-row">
                <span class="label">Next point:</span>
                <span class="value">Waiting...</span>
            </div>
            <div class="data-row">
                <span class="label">Distance:</span>
                <span class="value">Waiting...</span>
            </div>
            <div class="data-row">
                <span class="label">Bearing:</span>
                <span class="value">Waiting...</span>
            </div>
        `;
        return;
    }
    
    if (currentTargetIndex >= waypointsList.length) {
        nextPointDiv.innerHTML = `
            <div class="data-row">
                <span class="label">Next point:</span>
                <span class="value">Completed!</span>
            </div>
            <div class="data-row">
                <span class="label">Distance:</span>
                <span class="value">0 m</span>
            </div>
            <div class="data-row">
                <span class="label">Bearing:</span>
                <span class="value">0°</span>
            </div>
        `;
        return;
    }
    
    const target = waypointsList[currentTargetIndex];
    if (currentBoatPosition) {
        const distance = calculateDistance(
            currentBoatPosition.lat, currentBoatPosition.lon,
            target.lat, target.lon
        );
        const distanceMeters = distance * 1000;
        const bearing = calculateBearing(
            currentBoatPosition.lat, currentBoatPosition.lon,
            target.lat, target.lon
        );
        nextPointDiv.innerHTML = `
            <div class="data-row">
                <span class="label">Next point:</span>
                <span class="value">${currentTargetIndex + 1}/${waypointsList.length}</span>
            </div>
            <div class="data-row">
                <span class="label">Distance:</span>
                <span class="value">${distanceMeters.toFixed(0)} m</span>
            </div>
            <div class="data-row">
                <span class="label">Bearing:</span>
                <span class="value">${bearing.toFixed(0)}°</span>
            </div>
        `;
    } else {
        nextPointDiv.innerHTML = `
            <div class="data-row">
                <span class="label">Next point:</span>
                <span class="value">${currentTargetIndex + 1}/${waypointsList.length}</span>
            </div>
            <div class="data-row">
                <span class="label">Distance:</span>
                <span class="value">Waiting...</span>
            </div>
            <div class="data-row">
                <span class="label">Bearing:</span>
                <span class="value">Waiting...</span>
            </div>
        `;
    }
}

async function updateCurrentTarget() {
    if (currentTargetMarker) {
        map.removeChild(currentTargetMarker);
    }

    if (currentTargetIndex < waypointsList.length) {
        const target = waypointsList[currentTargetIndex];
        currentTargetCoordinates = [target.lon, target.lat];

        const { YMapDefaultMarker } = await ymaps3.import('@yandex/ymaps3-default-ui-theme');
        currentTargetMarker = new YMapDefaultMarker({
            coordinates: currentTargetCoordinates,
            color: 'orange',
            size: 'micro',
            draggable: false
        });
        map.addChild(currentTargetMarker);

        updateNextPointInfo();

        if (radarMode) updateRadarPoints();
    } else if (waypointsList.length > 0) {
        updateNextPointInfo();
        if (radarMode) document.getElementById('radarPoints').innerHTML = '';
    } else {
        document.getElementById('nextPointInfo').innerHTML = '<div class="data-row"><span class="label">Status:</span><span class="value">No route</span></div>';
    }
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
        circle.style.border = '1px solid #ddd';
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

    updateNextPointInfo();
}

function toggleRadarMode() {
    const mapDiv = document.getElementById('map');
    const radarContainer = document.getElementById('radarContainer');
    const toggleBtn = document.getElementById('radarToggle');
    radarMode = !radarMode;
    if (radarMode) {
        mapDiv.style.display = 'none';
        radarContainer.style.display = 'block';
        toggleBtn.innerHTML = 'Map mode';
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
        updateConnectionStatus(true);
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'gps') {
                const gps = data.data;
                document.getElementById('gpsData').innerHTML = 
                    `${gps.lat?.toFixed(6) || '?'}°, ${gps.lon?.toFixed(6) || '?'}°`;
                if (gps.lon && gps.lat) {
                    currentBoatPosition = { lat: gps.lat, lon: gps.lon };
                    updateBoatMarker([gps.lon, gps.lat]);
                    checkArrival();
                    if (radarMode) updateRadarPoints();
                    updateNextPointInfo();
                }
            } else if (data.type === 'wind') {
                const wind = data.data;
                document.getElementById('windData').innerHTML = 
                    `${wind.aws || 0} m/s, ${wind.direction || 0}°`;
            } else if (data.type === 'true_wind') {
                const trueWind = data.data;
                document.getElementById('trueWindData').innerHTML = 
                    `${trueWind.tws?.toFixed(1) || 0} m/s, ${trueWind.twd?.toFixed(0) || 0}°`;
            } else if (data.type === 'depth') {
                document.getElementById('depthData').innerHTML = 
                    `${data.data.depth_m || 0} m`;
            } else if (data.type === 'lag') {
                const lag = data.data;
                document.getElementById('lagData').innerHTML = 
                    `${lag.speed_knots || 0} knots`;
                if (lag.course !== undefined && lag.course !== null) {
                    currentBoatCourse = lag.course;
                    if (radarMode) updateRadarPoints();
                }
            }
        } catch (error) {
            console.error('Error parsing message:', error);
        }
    };

    ws.onerror = () => {
        updateConnectionStatus(false);
    };

    ws.onclose = () => {
        updateConnectionStatus(false);
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
    
    updateNextPointInfo();
    
    if (radarMode) {
        updateRadarPoints();
    }
}

async function main() {
    await ymaps3.ready;

    const {
        YMap,
        YMapListener,
        YMapDefaultSchemeLayer,
        YMapDefaultFeaturesLayer,
        YMapControls,
        YMapControlButton,
        YMapFeature
    } = ymaps3;

    ymaps3.import.registerCdn('https://cdn.jsdelivr.net/npm/{package}', [
        '@yandex/ymaps3-default-ui-theme@latest',
        '@yandex/ymaps3-hint@latest'
    ]);

    const {YMapDefaultMarker} = await ymaps3.import('@yandex/ymaps3-default-ui-theme');
    YMapDefaultMarkerClass = YMapDefaultMarker;

    map = new YMap(
        document.getElementById('map'),
        {
            location: {
                center: VLADIDOSTOK,
                zoom: 10
            }
        }
    );

    map.addChild(new YMapDefaultSchemeLayer());
    map.addChild(new YMapDefaultFeaturesLayer());

    const clickHandler = async (object, data) => {
        console.log(object);
        console.log(data);
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
            updateNextPointInfo();
        }
    };

    map.addChild(new YMapListener({
        layer: 'any',
        onClick: clickHandler,
        onPointerMove: dragHandler
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
            
            updateNextPointInfo();
            
            if (radarMode) {
                document.getElementById('radarPoints').innerHTML = '';
            }
        }
    });
    
    controls.addChild(center_button);
    controls.addChild(clear_button);
    
    map.addChild(controls);
    
    const distanceSlider = document.getElementById('arrivalDistance');
    if (distanceSlider) {
        distanceSlider.addEventListener('input', updateArrivalThreshold);
    }
    updateArrivalThreshold();
    
    connectWebSocket();
    updateConnectionStatus(false);
    
    updateNextPointInfo();
    document.getElementById('radarToggle').addEventListener('click', toggleRadarMode);
    
    buildWindGrid().then(drawWindLayer).catch(err => {
        console.error('Wind load error:', err);
    });
}

main();