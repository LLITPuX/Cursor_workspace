# FalkorDB Service + QPE (Query Processing Engine)

Сервіс для роботи з FalkorDB та Query Processing Engine (QPE) для обробки запитів та відповідей агента.

## 🚀 Запуск

```bash
docker-compose up -d
```

Це запустить три сервіси:
- **FalkorDB** - графова база даних (порт 6379, UI на порту 3000)
- **Ollama** - сервіс для генерації embeddings (порт 11434)
- **QPE Service** - API для обробки запитів та відповідей (порт 8001)

## 📋 Перевірка статусу

```bash
# Перевірка всіх сервісів
docker-compose ps

# Перегляд логів QPE Service
docker-compose logs -f qpe-service

# Перегляд логів Ollama
docker-compose logs -f ollama
```

## 🔧 Налаштування Ollama

Після запуску контейнерів, завантажте модель для embeddings:

```bash
docker exec -it falkordb-ollama ollama pull embeddinggemma:latest
```

## 🧪 Тестування підключення

### Тестування FalkorDB

```bash
pip install -r requirements.txt
python scripts/test_connection.py
```

### Тестування QPE API

```bash
# Health check
curl http://localhost:8001/api/v1/qpe/health

# Process query
curl -X POST http://localhost:8001/api/v1/qpe/process-query \
  -H "Content-Type: application/json" \
  -d '{"query": "Як зберегти сесію у FalkorDB?"}'

# Process assistant response
curl -X POST http://localhost:8001/api/v1/qpe/process-assistant-response \
  -H "Content-Type: application/json" \
  -d '{
    "response": "Для збереження сесії...",
    "structure": {
      "analysis": "Прочитано документацію",
      "response": "Для збереження потрібно...",
      "questions": ""
    }
  }'
```

## 📁 Структура проекту

```
falkordb-service/
├── app/                          # QPE API (FastAPI)
│   ├── main.py                   # FastAPI app
│   ├── config.py                 # Settings
│   ├── embedding.py              # Embedding service (Ollama)
│   ├── api/
│   │   └── routes.py            # QPE endpoints
│   └── models/
│       ├── request.py           # Request models
│       └── response.py          # Response models
├── scripts/
│   ├── test_connection.py       # Тестування підключення до FalkorDB
│   └── init_graph.py            # Ініціалізація структури графу
├── docker-compose.yml            # Docker Compose конфігурація
├── Dockerfile                    # Docker образ для QPE Service
├── requirements.txt              # Python залежності
└── README.md                    # Ця документація
```

## 🔌 API Endpoints

### Health Check
```
GET /api/v1/qpe/health
```

### Process Query
```
POST /api/v1/qpe/process-query
Body: {"query": "текст запиту"}
```

### Process Assistant Response
```
POST /api/v1/qpe/process-assistant-response
Body: {
  "response": "текст відповіді",
  "structure": {
    "analysis": "...",
    "response": "...",
    "questions": "..."
  }
}
```

## 📝 Примітки

- На Етапі 2 класифікація та вилучення сутностей використовують mock-дані
- Реальні компоненти (DeBERTa, GLINER) будуть інтегровані в наступних етапах
- Embeddings генеруються через Ollama з моделлю `embeddinggemma:latest`
