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

# Тест сокета
в root директории выполнить: 
```sh
python -m http.server 8080
```

перейти на http://localhost:8080

(предварительно запустив докер контейнеры)

