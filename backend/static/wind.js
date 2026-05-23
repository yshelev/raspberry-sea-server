// Theme management
window.initTheme = function() {
    const savedTheme = localStorage.getItem('theme');
    const btn = document.getElementById('themeBtn');
    
    console.log('Wind initTheme called, savedTheme:', savedTheme);
    
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
    
    console.log('Wind toggleTheme called');
    
    if (body.classList.contains('light')) {
        body.classList.remove('light');
        if (btn) btn.textContent = '🌙';
        localStorage.setItem('theme', 'dark');
    } else {
        body.classList.add('light');
        if (btn) btn.textContent = '☀️';
        localStorage.setItem('theme', 'light');
    }
    
    if (dashboard) {
        dashboard.drawCompass();
    }
}

// Wind Dashboard — WebSocket клиент
class WindDashboard {
    constructor() {
        this.canvas = document.getElementById('windCompass');
        this.ctx = this.canvas.getContext('2d');
        
        this.tws = 0;
        this.twa = 0;
        this.twd = 0;
        this.boatSpeed = 0;

        this.ws = null;
        this.reconnectInterval = 3000;

        this.init();
        this.resizeCanvas();
        
        window.addEventListener('resize', () => this.resizeCanvas());
    }

    init() {
        window.initTheme();
        
        const themeBtn = document.getElementById('themeBtn');
        if (themeBtn) {
            themeBtn.onclick = window.toggleTheme;
        }
        
        const dataPageBtn = document.getElementById('dataPageBtn');
        if (dataPageBtn) {
            dataPageBtn.addEventListener('click', () => {
                window.location.href = '/data';
            });
        }
        
        this.connect();
        this.animate();
    }

    getColors() {
        const isLight = document.body.classList.contains('light');
        return {
            closeHauled: isLight ? '#ea580c' : '#b45309',
            beamReach: '#0d9488',
            broadReach: '#059669',
            running: isLight ? '#4f46e5' : '#6366f1',
            deadZone: '#dc2626',
            boat: isLight ? '#6366f1' : '#818cf8',
            boatOutline: '#c7d2fe',
            text: isLight ? '#6b7280' : '#9ca3af',
            grid: isLight ? '#f3f4f6' : '#1e293b',
            tick: isLight ? '#d1d5db' : '#475569',
            tickMajor: isLight ? '#9ca3af' : '#94a3b8',
            centerDot: isLight ? '#d1d5db' : '#64748b',
            value: isLight ? '#4f46e5' : '#a5b4fc'
        };
    }

    resizeCanvas() {
        const maxSize = Math.min(window.innerWidth, window.innerHeight) - 40;
        const size = Math.min(maxSize, 500);
        
        this.canvas.width = size;
        this.canvas.height = size;
        this.canvas.style.width = `${size}px`;
        this.canvas.style.height = `${size}px`;
        
        this.centerX = this.canvas.width / 2;
        this.centerY = this.canvas.height / 2;
        this.radius = this.canvas.width / 2 - 12;
        
        this.drawCompass();
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('Wind WebSocket connected');
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
            console.log('Wind WebSocket closed, reconnecting...');
            setTimeout(() => this.connect(), this.reconnectInterval);
        };

        this.ws.onerror = (err) => {
            console.error('Wind WebSocket error:', err);
        };
    }

    handleMessage(msg) {
        const type = msg.type;
        const data = msg.data;

        switch (type) {
            case 'true_wind':
                this.tws = data.tws || 0;
                this.twa = data.twa || 0;
                this.twd = data.twd || 0;
                this.boatSpeed = data.boat_speed || 0;
                this.updateDisplay('twa', Math.round(this.twa) + '°');
                this.updateDisplay('twd', Math.round(this.twd) + '°');
                this.updateDisplay('boatSpeed', this.boatSpeed.toFixed(1));
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
        const colors = this.getColors();
        if (a < 30 || a > 330) return colors.deadZone;
        if (a >= 30 && a < 60) return colors.closeHauled;
        if (a >= 60 && a < 120) return colors.beamReach;
        if (a >= 120 && a < 150) return colors.broadReach;
        if (a >= 150 && a <= 210) return colors.running;
        if (a > 210 && a < 240) return colors.broadReach;
        if (a >= 240 && a < 300) return colors.beamReach;
        if (a >= 300 && a <= 330) return colors.closeHauled;
        return colors.text;
    }

    drawCompass() {
        const ctx = this.ctx;
        const cx = this.centerX;
        const cy = this.centerY;
        const r = this.radius;
        const colors = this.getColors();
        const isLight = document.body.classList.contains('light');

        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fillStyle = isLight ? '#ffffff' : '#0f1117';
        ctx.fill();
        ctx.strokeStyle = colors.tickMajor;
        ctx.lineWidth = 3;
        ctx.stroke();

        for (let i = 1; i <= 4; i++) {
            ctx.beginPath();
            ctx.arc(cx, cy, r * i / 4, 0, Math.PI * 2);
            ctx.strokeStyle = colors.grid;
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }

        for (let angle = 0; angle < 360; angle += 30) {
            const rad = (angle - 90) * Math.PI / 180;
            const isMajor = angle % 90 === 0;
            ctx.beginPath();
            ctx.moveTo(cx + r * 0.85 * Math.cos(rad), cy + r * 0.85 * Math.sin(rad));
            ctx.lineTo(cx + r * Math.cos(rad), cy + r * Math.sin(rad));
            ctx.strokeStyle = isMajor ? colors.tickMajor : colors.tick;
            ctx.lineWidth = isMajor ? 3 : 1.5;
            ctx.stroke();

            const labelR = r * 0.72;
            const lx = cx + labelR * Math.cos(rad);
            const ly = cy + labelR * Math.sin(rad);
            ctx.fillStyle = isMajor ? colors.tickMajor : colors.tick;
            ctx.font = isMajor ? `bold ${Math.max(16, r * 0.12)}px sans-serif` : `${Math.max(12, r * 0.09)}px sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(angle.toString(), lx, ly);
        }

        this.drawWindSectors(cx, cy, r);
        this.drawBoat(cx, cy, r * 0.28);
        this.drawWindArrow(cx, cy, r * 0.7);

        ctx.beginPath();
        ctx.arc(cx, cy, 6, 0, Math.PI * 2);
        ctx.fillStyle = colors.centerDot;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(cx, cy, 3, 0, Math.PI * 2);
        ctx.fillStyle = colors.value;
        ctx.fill();
        
        // Показываем TWS (скорость ветра) в центре компаса
        ctx.fillStyle = colors.value;
        ctx.font = `bold ${Math.max(18, r * 0.12)}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(this.tws.toFixed(1) + ' kts', cx, cy - r * 0.45);
    }

    drawWindSectors(cx, cy, r) {
        const ctx = this.ctx;
        const colors = this.getColors();
        const zones = [
            { start: 30, end: 60, color: colors.closeHauled },
            { start: 60, end: 120, color: colors.beamReach },
            { start: 120, end: 150, color: colors.broadReach },
            { start: 150, end: 210, color: colors.running },
            { start: 210, end: 240, color: colors.broadReach },
            { start: 240, end: 300, color: colors.beamReach },
            { start: 300, end: 330, color: colors.closeHauled },
        ];

        zones.forEach(zone => {
            ctx.beginPath();
            ctx.arc(cx, cy, r + 8, 
                (zone.start - 90) * Math.PI / 180, 
                (zone.end - 90) * Math.PI / 180);
            ctx.strokeStyle = zone.color;
            ctx.lineWidth = 6;
            ctx.stroke();
        });

        ctx.beginPath();
        ctx.arc(cx, cy, r + 8, 
            (330 - 90) * Math.PI / 180, 
            (390 - 90) * Math.PI / 180);
        ctx.strokeStyle = colors.deadZone;
        ctx.lineWidth = 6;
        ctx.stroke();
    }

    drawBoat(cx, cy, size) {
        const ctx = this.ctx;
        const colors = this.getColors();

        ctx.beginPath();
        ctx.moveTo(cx, cy - size);
        ctx.lineTo(cx + size * 0.4, cy + size * 0.5);
        ctx.lineTo(cx, cy + size * 0.3);
        ctx.lineTo(cx - size * 0.4, cy + size * 0.5);
        ctx.closePath();

        ctx.fillStyle = colors.boat;
        ctx.fill();
        ctx.strokeStyle = colors.boatOutline;
        ctx.lineWidth = 2.5;
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(cx, cy - size);
        ctx.lineTo(cx, cy + size * 0.75);
        ctx.strokeStyle = colors.tickMajor;
        ctx.lineWidth = 2;
        ctx.stroke();
    }

    drawWindArrow(cx, cy, length) {
        const ctx = this.ctx;
        const r = this.radius;

        const startAngleRad = (this.twa - 90) * Math.PI / 180;
        const startX = cx + length * Math.cos(startAngleRad);
        const startY = cy + length * Math.sin(startAngleRad);

        const gap = 50;
        const endX = cx + gap * Math.cos(startAngleRad);
        const endY = cy + gap * Math.sin(startAngleRad);

        const arrowColor = this.getZoneColor(this.twa);

        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(endX, endY);
        ctx.strokeStyle = arrowColor;
        ctx.lineWidth = 5;
        ctx.stroke();

        const headLen = 16;
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
        
        ctx.strokeStyle = arrowColor;
        ctx.lineWidth = 1.5;
        ctx.stroke();
    }

    animate() {
        this.drawCompass();
        requestAnimationFrame(() => this.animate());
    }
}

let dashboard;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        dashboard = new WindDashboard();
    });
} else {
    dashboard = new WindDashboard();
}