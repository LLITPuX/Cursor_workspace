# 🧬 Embedding Service

Python сервіс для генерації embeddings з використанням локальної моделі Ollama EmbeddingGemma.

## 🎯 Особливості

- ✅ **Локальна обробка** - використовує Ollama для генерації embeddings без залежності від зовнішніх API
- ✅ **Модульний чанкінг** - підтримка різних стратегій чанкінгу (simple, recursive, semantic)
- ✅ **Batch processing** - підтримка обробки батчів текстів
- ✅ **Гнучка конфігурація** - підтримка різних моделей та розмірностей
- ✅ **REST API** - зручний FastAPI інтерфейс
- ✅ **Інтеграція з Neon** - збереження embeddings в PostgreSQL з pgvector

## 📋 Вимоги

- Docker та Docker Compose (рекомендовано)
- Або Python 3.10+ та Ollama локально
- Neon PostgreSQL база даних (або інша PostgreSQL з pgvector)

## 🚀 Швидкий старт

### Варіант 1: Docker (Рекомендовано) 🐳

#### 1. Налаштування конфігурації

Створіть файл `.env` в корені `embedding-service`:

```bash
cd embedding-service
cp .env.example .env
```

Відредагуйте `.env` та встановіть `NEON_CONNECTION_STRING`:

```env
NEON_CONNECTION_STRING=postgresql://user:password@host/database?sslmode=require
```

#### 2. Запуск через Docker Compose

```bash
# Запуск всіх сервісів (Ollama + Embedding Service)
docker-compose up -d

# Перевірка статусу
docker-compose ps

# Перегляд логів
docker-compose logs -f embedding-service
```

#### 3. Завантаження моделі в Ollama

Після запуску контейнерів, завантажте модель:

```bash
# Завантажити модель EmbeddingGemma в контейнер Ollama
docker exec embedding-ollama ollama pull embeddinggemma:latest

# Перевірити, що модель завантажена
docker exec embedding-ollama ollama list

# Або використати Makefile команду
make init-model
```

#### 4. Перевірка роботи

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Або відкрийте в браузері
# http://localhost:8000/docs
```

#### 5. Зупинка сервісів

```bash
docker-compose down

# З видаленням volumes (очистить дані Ollama)
docker-compose down -v
```

#### Development режим з hot reload

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Варіант 2: Локальний запуск (без Docker)

#### 1. Встановлення Ollama та моделі

```bash
# Встановіть Ollama (якщо ще не встановлено)
# https://ollama.com

# Завантажте модель EmbeddingGemma
ollama pull embeddinggemma:latest
```

#### 2. Встановлення залежностей

```bash
cd embedding-service
pip install -r requirements.txt
```

#### 3. Налаштування конфігурації

Скопіюйте `.env.example` в `.env` та налаштуйте:

```bash
cp .env.example .env
# Відредагуйте .env файл
```

#### 4. Запуск міграції БД

Виконайте міграцію `migrations/002_update_embedding_dimension.sql` в вашій Neon базі даних.

#### 5. Запуск сервісу

```bash
python -m app.main
# або
uvicorn app.main:app --reload
```

Сервіс буде доступний на `http://localhost:8000`

## 📚 API Документація

Після запуску сервісу, документація доступна на:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🔧 API Endpoints

### Health Check
```bash
GET /api/v1/health
```

### Генерація embedding
```bash
POST /api/v1/embed
Content-Type: application/json

{
  "text": "Your text here"
}
```

### Генерація embeddings для чанкованого тексту
```bash
POST /api/v1/embed-chunked
Content-Type: application/json

{
  "text": "Long text to chunk...",
  "strategy": "recursive",
  "chunk_size": 512,
  "chunk_overlap": 50
}
```

### Список стратегій чанкінгу
```bash
GET /api/v1/strategies
```

## 🔍 RAG (Retrieval-Augmented Generation)

Сервіс підтримує векторний пошук для RAG:

### Векторний пошук по повідомленням
```bash
POST /api/v1/rag/search-messages
Content-Type: application/json

{
  "query_text": "Як працювати з базою даних?",
  "limit": 10,
  "similarity_threshold": 0.7,
  "session_id": "optional-session-id",
  "role": "assistant"
}
```

### Векторний пошук по сутностям
```bash
POST /api/v1/rag/search-entities
Content-Type: application/json

{
  "query_text": "Як зберігати сесії?",
  "types": ["Instruction", "Protocol"],
  "limit": 10,
  "similarity_threshold": 0.7,
  "active_only": true
}
```

## 📚 Робота з графом знань

Сервіс надає API для роботи з графом знань:

- `GET /api/v1/rules/critical` — отримання критичних правил
- `GET /api/v1/entities/{entity_id}/children` — отримання дочірніх сутностей
- `POST /api/v1/messages/{message_id}/link-entity` — створення зв'язків між повідомленнями та сутностями
- `POST /api/v1/sessions/{session_id}/link-entity` — створення зв'язків між сесіями та сутностями

## 🧩 Стратегії чанкінгу

### Simple
Простий чанкінг по символах з overlap:
```python
from chunking.strategies.simple import SimpleChunking

chunker = SimpleChunking(chunk_size=512, overlap=50)
chunks = chunker.chunk("Your text here")
```

### Recursive
Рекурсивний чанкінг на природних межах (параграфи, речення, слова):
```python
from chunking.strategies.recursive import RecursiveChunking

chunker = RecursiveChunking(chunk_size=512, overlap=50)
chunks = chunker.chunk("Your text here")
```

### Semantic
Семантичний чанкінг (placeholder - використовує recursive як fallback):
```python
from chunking.strategies.semantic import SemanticChunking

chunker = SemanticChunking(chunk_size=512, overlap=50)
chunks = chunker.chunk("Your text here")
```

## 🗄️ Структура бази даних

Сервіс використовує таблицю `embedding_models` для зберігання метаданих моделей:

```sql
SELECT * FROM embedding_models WHERE is_active = TRUE;
```

Embeddings зберігаються в колонках:
- `messages.embedding_v2` (vector(768))
- `entity_nodes.embedding_v2` (vector(768))

## 🔄 Інтеграція з основним сервісом

Для автоматичного збереження embeddings при збереженні повідомлень, додайте виклик API:

```python
import httpx

async def save_message_with_embedding(text: str, session_id: str):
    # Генеруємо embedding
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/embed",
            json={"text": text}
        )
        embedding = response.json()["embedding"]
    
    # Зберігаємо в БД
    # ... ваш код збереження
```

## 🐳 Docker команди

### Використання Makefile (рекомендовано)

```bash
# Показати всі доступні команди
make help

# Збудувати образи
make build

# Запустити сервіси
make up

# Завантажити модель EmbeddingGemma
make init-model

# Переглянути логи
make logs

# Перевірити health check
make test

# Зупинити сервіси
make down

# Development режим з hot reload
make dev

# Відкрити shell в контейнері
make shell
```

### Прямі docker-compose команди

```bash
# Збірка образу
docker-compose build

# Запуск в фоні
docker-compose up -d

# Перегляд логів
docker-compose logs -f embedding-service

# Зупинка
docker-compose down

# Перезапуск сервісу
docker-compose restart embedding-service

# Виконання команд в контейнері
docker-compose exec embedding-service python -c "print('Hello')"

# Завантаження моделі в Ollama контейнер
docker exec embedding-ollama ollama pull embeddinggemma:latest
```

## 🧪 Тестування

```bash
# Перевірка здоров'я сервісу
curl http://localhost:8000/api/v1/health

# Тест генерації embedding
curl -X POST http://localhost:8000/api/v1/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, world!"}'

# Запуск тестів (коли будуть додані)
pytest
```

## 📝 Примітки

- Розмірність EmbeddingGemma: **768** (не 1536 як у OpenAI)
- Модель підтримує 100+ мов
- Контекстне вікно: 2K токенів
- Розмір моделі: ~622MB

## 🔗 Посилання

- [Ollama EmbeddingGemma](https://ollama.com/library/embeddinggemma)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [pgvector Documentation](https://github.com/pgvector/pgvector)

## 📄 Ліцензія

MIT License

