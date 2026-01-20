# FalkorDB Service

Сервіс для роботи з FalkorDB - графовою базою даних.

## Запуск

```bash
docker-compose up -d
```

## Перевірка підключення

Після запуску контейнера:

```bash
pip install -r requirements.txt
python scripts/test_connection.py
```

## Ініціалізація структури графу

```bash
python scripts/init_graph.py
```

## Структура

- `docker-compose.yml` - Docker Compose конфігурація
- `requirements.txt` - Python залежності
- `scripts/test_connection.py` - Тестування підключення
- `scripts/init_graph.py` - Ініціалізація структури графу
