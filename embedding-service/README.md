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

- Python 3.10+
- Ollama з встановленою моделлю `embeddinggemma`
- Neon PostgreSQL база даних (або інша PostgreSQL з pgvector)

## 🚀 Швидкий старт

### 1. Встановлення Ollama та моделі

```bash
# Встановіть Ollama (якщо ще не встановлено)
# https://ollama.com

# Завантажте модель EmbeddingGemma
ollama pull embeddinggemma:latest
```

### 2. Встановлення залежностей

```bash
cd embedding-service
pip install -r requirements.txt
```

### 3. Налаштування конфігурації

Скопіюйте `.env.example` в `.env` та налаштуйте:

```bash
cp .env.example .env
# Відредагуйте .env файл
```

### 4. Запуск міграції БД

Виконайте міграцію `migrations/002_update_embedding_dimension.sql` в вашій Neon базі даних.

### 5. Запуск сервісу

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

## 🧪 Тестування

```bash
# Запуск тестів (коли будуть додані)
pytest

# Перевірка здоров'я сервісу
curl http://localhost:8000/api/v1/health
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

