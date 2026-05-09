# Формат данных 
по сокету приходят данные вида 
{ "time": "2026-04-01T06:22:27.601152", "timestamp": 1775024547.601178, "lat": 55.75263, "lon": 37.64094, "alt": 150, "speed": 55, "track": 120 }

# Тестовый запуск
```sh
docker compose -f docker-compose.test.yaml up -d
```

# Реальный запуск (требует /dev/serial0 порта и запуска на raspberry pi)
```sh
docker compose up 
```

# Эндпоинты FastAPI
**localhost:8000**
- **GET** [`/`](http://localhost:8000/) - состояние
- **GET** [`/ws`](http://localhost:8000/ws) - вебсокет
- **GET** [`/map`](http://localhost:8000/map) - карта

