FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install gps3 redis

CMD ["python", "main.py"]