// Wind Dashboard — WebSocket клиент
// Стрелка показывает ОТКУДА дует ветер, направлена В КОРАБЛЬ
// Стрелка не доходит до центра — зазор 35px

class WindDashboard {
    constructor() {
        this.canvas = document.getElementById('windCompass');
        this.ctx = this.canvas.getContext('2d');
        this.centerX = this.canvas.width / 2;
        this.centerY = this.canvas.height / 2;
        this.radius = 120;

        this.tws = 0;
        this.twa = 0;
        this.twd = 0;

        this.colors = {
            closeHauled: '#b45309',
            beamReach: '#0d9488',
            broadReach: '#059669',
            running: '#6366f1',
            deadZone: '#dc2626',
            boat: '#818cf8',
            boatOutline: '#c7d2fe',
            text: '#9ca3af',
            grid: '#1e293b',
            tick: '#475569',
            tickMajor: '#94a3b8'
        };

        this.ws = null;
        this.reconnectInterval = 3000;

        this.connect();
        this.animate();
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.setStatus(true, 'Connected');
        };

        this.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                this.handleMessage(msg);
            } catch (e) {
                console.error('Parse error:', e);
            }
        };

        this.ws.onclose = () => {
            console.log('WebSocket closed, reconnecting...');
            this.setStatus(false, 'Reconnecting...');
            setTimeout(() => this.connect(), this.reconnectInterval);
        };

        this.ws.onerror = (err) => {
            console.error('WebSocket error:', err);
            this.setStatus(false, 'Connection error');
        };
    }

    setStatus(connected, text) {
        const dot = document.getElementById('status-dot');
        const statusText = document.getElementById('status-text');
        if (dot) dot.classList.toggle('connected', connected);
        if (statusText) statusText.textContent = text;
    }

    handleMessage(msg) {
        const type = msg.type;
        const data = msg.data;

        switch (type) {
            case 'true_wind':
                this.tws = data.tws || 0;
                this.twa = data.twa || 0;
                this.twd = data.twd || 0;
                this.updateDisplay('tws', this.tws.toFixed(1));
                this.updateDisplay('twa', Math.round(this.twa) + '°');
                this.updateDisplay('twd', Math.round(this.twd) + '°');
                break;
        }
    }

    updateDisplay(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    normalizeAngle(angle) {
        return ((angle % 360) + 360) % 360;
    }

    getZoneColor(twa) {
        const a = this.normalizeAngle(twa);
        if (a < 30 || a > 330) return this.colors.deadZone;
        if (a >= 30 && a < 60) return this.colors.closeHauled;
        if (a >= 60 && a < 120) return this.colors.beamReach;
        if (a >= 120 && a < 150) return this.colors.broadReach;
        if (a >= 150 && a <= 210) return this.colors.running;
        if (a > 210 && a < 240) return this.colors.broadReach;
        if (a >= 240 && a < 300) return this.colors.beamReach;
        if (a >= 300 && a <= 330) return this.colors.closeHauled;
        return this.colors.text;
    }

    drawCompass() {
        const ctx = this.ctx;
        const cx = this.centerX;
        const cy = this.centerY;
        const r = this.radius;

        // Определяем тему через CSS переменные
        const style = getComputedStyle(document.body);
        const isLight = document.body.classList.contains('light');

        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Фон компаса
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fillStyle = isLight ? '#ffffff' : '#0f1117';
        ctx.fill();
        ctx.strokeStyle = isLight ? '#e5e7eb' : '#1e293b';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Концентрические круги
        for (let i = 1; i <= 4; i++) {
            ctx.beginPath();
            ctx.arc(cx, cy, r * i / 4, 0, Math.PI * 2);
            ctx.strokeStyle = isLight ? '#f3f4f6' : '#1e293b';
            ctx.lineWidth = 1;
            ctx.stroke();
        }

        // Линии направлений
        for (let angle = 0; angle < 360; angle += 30) {
            const rad = (angle - 90) * Math.PI / 180;
            const isMajor = angle % 90 === 0;
            ctx.beginPath();
            ctx.moveTo(cx + r * 0.85 * Math.cos(rad), cy + r * 0.85 * Math.sin(rad));
            ctx.lineTo(cx + r * Math.cos(rad), cy + r * Math.sin(rad));
            ctx.strokeStyle = isLight 
                ? (isMajor ? '#9ca3af' : '#d1d5db')
                : (isMajor ? '#94a3b8' : '#475569');
            ctx.lineWidth = isMajor ? 2 : 1;
            ctx.stroke();

            const labelR = r * 0.72;
            const lx = cx + labelR * Math.cos(rad);
            const ly = cy + labelR * Math.sin(rad);
            ctx.fillStyle = isLight
                ? (isMajor ? '#6b7280' : '#d1d5db')
                : (isMajor ? '#94a3b8' : '#475569');
            ctx.font = isMajor ? 'bold 13px sans-serif' : '11px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(angle.toString(), lx, ly);
        }

        this.drawWindSectors(cx, cy, r);
        this.drawBoat(cx, cy, r * 0.28);
        this.drawWindArrow(cx, cy, r * 0.7);

        ctx.beginPath();
        ctx.arc(cx, cy, 3, 0, Math.PI * 2);
        ctx.fillStyle = isLight ? '#d1d5db' : '#64748b';
        ctx.fill();
    }

    drawWindSectors(cx, cy, r) {
        const ctx = this.ctx;
        const zones = [
            { start: 30, end: 60, color: this.colors.closeHauled },
            { start: 60, end: 120, color: this.colors.beamReach },
            { start: 120, end: 150, color: this.colors.broadReach },
            { start: 150, end: 210, color: this.colors.running },
            { start: 210, end: 240, color: this.colors.broadReach },
            { start: 240, end: 300, color: this.colors.beamReach },
            { start: 300, end: 330, color: this.colors.closeHauled },
        ];

        zones.forEach(zone => {
            ctx.beginPath();
            ctx.arc(cx, cy, r + 6, 
                (zone.start - 90) * Math.PI / 180, 
                (zone.end - 90) * Math.PI / 180);
            ctx.strokeStyle = zone.color;
            ctx.lineWidth = 4;
            ctx.stroke();
        });

        ctx.beginPath();
        ctx.arc(cx, cy, r + 6, 
            (330 - 90) * Math.PI / 180, 
            (390 - 90) * Math.PI / 180);
        ctx.strokeStyle = this.colors.deadZone;
        ctx.lineWidth = 4;
        ctx.stroke();
    }

    drawBoat(cx, cy, size) {
        const ctx = this.ctx;
        const isLight = document.body.classList.contains('light');

        ctx.beginPath();
        ctx.moveTo(cx, cy - size);
        ctx.lineTo(cx + size * 0.35, cy + size * 0.45);
        ctx.lineTo(cx, cy + size * 0.25);
        ctx.lineTo(cx - size * 0.35, cy + size * 0.45);
        ctx.closePath();

        ctx.fillStyle = isLight ? '#6366f1' : '#818cf8';
        ctx.fill();
        ctx.strokeStyle = isLight ? '#4338ca' : '#c7d2fe';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(cx, cy - size);
        ctx.lineTo(cx, cy + size * 0.7);
        ctx.strokeStyle = isLight ? '#d1d5db' : '#475569';
        ctx.lineWidth = 1;
        ctx.stroke();
    }

    drawWindArrow(cx, cy, length) {
        const ctx = this.ctx;
        const r = this.radius;

        // Стрелка показывает ОТКУДА дует ветер (направлена В КОРАБЛЬ)
        // TWA = 0° — ветер в нос, стрелка сверху → в центр
        // TWA = 90° — ветер с правого борта, стрелка справа → в центр
        // TWA = 180° — ветер с кормы, стрелка снизу → в центр

        // Начало стрелки — на периметре компаса
        const startAngleRad = (this.twa - 90) * Math.PI / 180;
        const startX = cx + length * Math.cos(startAngleRad);
        const startY = cy + length * Math.sin(startAngleRad);

        // Конец стрелки — зазор 35px от центра, не доходит до лодки
        const gap = 35;
        const endX = cx + gap * Math.cos(startAngleRad);
        const endY = cy + gap * Math.sin(startAngleRad);

        const arrowColor = this.getZoneColor(this.twa);

        // Линия стрелки
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(endX, endY);
        ctx.strokeStyle = arrowColor;
        ctx.lineWidth = 3;
        ctx.stroke();

        // Наконечник стрелки — у зазора, смотрит ВНУТРЬ к лодке
        const headLen = 12;
        const angle = Math.atan2(endY - startY, endX - startX);

        ctx.beginPath();
        ctx.moveTo(endX, endY);
        ctx.lineTo(
            endX - headLen * Math.cos(angle - Math.PI / 6),
            endY - headLen * Math.sin(angle - Math.PI / 6)
        );
        ctx.lineTo(
            endX - headLen * Math.cos(angle + Math.PI / 6),
            endY - headLen * Math.sin(angle + Math.PI / 6)
        );
        ctx.closePath();
        ctx.fillStyle = arrowColor;
        ctx.fill();

        // Подпись скорости ветра
        const isLight = document.body.classList.contains('light');
        ctx.fillStyle = isLight ? '#4f46e5' : '#a5b4fc';
        ctx.font = 'bold 14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(this.tws.toFixed(1) + ' kts', cx, cy - r * 0.45);

        // Подпись TWA
        ctx.fillStyle = isLight ? '#9ca3af' : '#6b7280';
        ctx.font = '11px sans-serif';
        ctx.fillText('TWA ' + Math.round(this.twa) + '°', cx, cy + r * 0.82);
    }

    animate() {
        this.drawCompass();
        requestAnimationFrame(() => this.animate());
    }
}

const dashboard = new WindDashboard();

// === Theme Toggle ===
function toggleTheme() {
    const body = document.body;
    const btn = document.getElementById('themeBtn');

    if (body.classList.contains('light')) {
        body.classList.remove('light');
        btn.textContent = '🌙';
        localStorage.setItem('theme', 'dark');
    } else {
        body.classList.add('light');
        btn.textContent = '☀️';
        localStorage.setItem('theme', 'light');
    }
}

// Restore theme on load
(function() {
    const saved = localStorage.getItem('theme');
    const btn = document.getElementById('themeBtn');
    if (saved === 'light') {
        document.body.classList.add('light');
        if (btn) btn.textContent = '☀️';
    }
})();