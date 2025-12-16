# Збереження сесії в базу даних

## Налаштування підключення до бази даних

### 1. Отримайте connection string з Neon

1. Відкрийте [Neon Console](https://console.neon.tech)
2. Виберіть ваш проект
3. Скопіюйте connection string (формат: `postgresql://user:password@host/database?sslmode=require`)

### 2. Налаштуйте змінну оточення

#### Варіант A: Через .env файл (рекомендовано)

Створіть файл `.env` в директорії `embedding-service`:

```env
NEON_CONNECTION_STRING=postgresql://user:password@host/database?sslmode=require
LOG_LEVEL=INFO
```

#### Варіант B: Через змінні оточення Docker

Додайте в `docker-compose.yml`:

```yaml
environment:
  - NEON_CONNECTION_STRING=${NEON_CONNECTION_STRING}
```

І встановіть змінну перед запуском:

```bash
export NEON_CONNECTION_STRING="postgresql://..."
docker-compose up -d
```

### 3. Перезапустіть сервіс

```bash
docker-compose restart embedding-service
```

## Використання API для збереження сесії

### Endpoint: `POST /api/v1/sessions`

**Request Body:**
```json
{
  "topic": "Назва сесії (опціонально)",
  "messages": [
    {
      "role": "user",
      "content": "Текст повідомлення користувача"
    },
    {
      "role": "assistant",
      "content": "Текст відповіді асистента"
    }
  ],
  "generate_embeddings": true
}
```

**Response:**
```json
{
  "session_id": "uuid-сесії",
  "topic": "Назва сесії",
  "messages_saved": 2,
  "embeddings_generated": 2
}
```

### Приклад використання через curl:

```bash
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Тестування embedding-сервісу",
    "messages": [
      {
        "role": "user",
        "content": "Привіт! Я хочу протестувати embedding-сервіс."
      },
      {
        "role": "assistant",
        "content": "Привіт! Я готовий допомогти."
      }
    ],
    "generate_embeddings": true
  }'
```

### Приклад через PowerShell:

```powershell
$body = @{
    topic = "Тестування embedding-сервісу"
    messages = @(
        @{role = "user"; content = "Привіт! Я хочу протестувати embedding-сервіс."}
        @{role = "assistant"; content = "Привіт! Я готовий допомогти."}
    )
    generate_embeddings = $true
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri http://localhost:8000/api/v1/sessions `
    -Method POST `
    -Body $body `
    -ContentType 'application/json'
```

## Використання скрипта для збереження тестової сесії

### Запуск скрипта в контейнері:

```bash
# Переконайтеся, що NEON_CONNECTION_STRING встановлено
docker exec embedding-service python scripts/save_test_session.py
```

### Або локально (якщо встановлено залежності):

```bash
cd embedding-service
export NEON_CONNECTION_STRING="postgresql://..."
python scripts/save_test_session.py
```

## Перевірка збережених даних

Після збереження сесії ви можете перевірити дані в базі:

```sql
-- Переглянути всі сесії
SELECT id, topic, created_at FROM sessions ORDER BY created_at DESC LIMIT 10;

-- Переглянути повідомлення сесії
SELECT role, content, created_at 
FROM messages 
WHERE session_id = 'ваш-session-id'
ORDER BY created_at;

-- Перевірити наявність embeddings
SELECT 
    role, 
    LENGTH(content) as content_length,
    embedding_v2 IS NOT NULL as has_embedding
FROM messages 
WHERE session_id = 'ваш-session-id';
```

## Структура бази даних

- **sessions** - метадані сесій (id, topic, created_at, metadata)
- **messages** - повідомлення з embeddings (id, session_id, role, content, embedding_v2)
- **embedding_v2** - вектор розмірністю 768 (для EmbeddingGemma)

## Примітки

- Embeddings генеруються автоматично для всіх повідомлень, якщо `generate_embeddings: true`
- Якщо генерація embedding не вдалася, повідомлення все одно зберігається (без embedding)
- Розмірність embedding: **768** (модель EmbeddingGemma)
- Стара колонка `embedding` (1536d) залишається для сумісності з OpenAI моделями

