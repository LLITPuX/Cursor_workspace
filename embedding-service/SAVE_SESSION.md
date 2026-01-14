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

## Використання універсального скрипта для збереження сесії

### Універсальний скрипт `save_session.py`

Скрипт приймає дані з різних джерел: stdin, файлу, аргументів командного рядка або через API.

#### 1. З stdin (JSON):

```bash
echo '{"topic": "Test", "messages": [{"role": "user", "content": "Hello"}]}' | \
  python scripts/save_session.py
```

#### 2. З файлу:

```bash
# Створіть файл session.json з даними сесії
python scripts/save_session.py --file session.json
```

#### 3. Через API (якщо сервер запущений):

```bash
python scripts/save_session.py --use-api --file session.json
```

#### 4. З аргументів командного рядка:

```bash
python scripts/save_session.py \
  --topic "Test Session" \
  --messages '[{"role": "user", "content": "Hello"}]'
```

#### 5. Через Docker:

```bash
docker exec -e NEON_CONNECTION_STRING="..." embedding-service \
  python /app/scripts/save_session.py --file /app/session.json
```

#### Формат JSON файлу:

```json
{
  "topic": "Назва сесії (опціонально)",
  "messages": [
    {"role": "user", "content": "Текст повідомлення"},
    {"role": "assistant", "content": "Відповідь"}
  ],
  "generate_embeddings": true,
  "metadata": {"source": "custom", "custom_field": "value"}
}
```

#### Опції скрипта:

- `--file, -f` - шлях до JSON файлу з даними сесії
- `--use-api` - використовувати API endpoint замість прямого доступу до БД
- `--topic, -t` - тема сесії
- `--messages, -m` - JSON масив повідомлень
- `--no-embeddings` - не генерувати embeddings
- `--api-url` - URL API сервера (за замовчуванням: http://localhost:8000)

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
- **messages** - повідомлення з embeddings (id, session_id, role, content, embedding_v2, embedding_model_id)
- **embedding_v2** - вектор розмірністю 768 (для EmbeddingGemma)
- **message_entity_links** - зв'язки між повідомленнями та правилами/інструкціями
- **session_entity_links** - зв'язки між сесіями та протоколами

## Створення зв'язків з правилами та інструкціями

Після збереження сесії можна створити зв'язки між повідомленнями та використаними правилами/інструкціями:

### Через API

```bash
# Зв'язати повідомлення з правилом
POST /api/v1/messages/{message_id}/link-entity?entity_id={rule_id}&relation_type=uses

# Зв'язати повідомлення з інструкцією
POST /api/v1/messages/{message_id}/link-entity?entity_id={instruction_id}&relation_type=applies

# Зв'язати сесію з протоколом
POST /api/v1/sessions/{session_id}/link-entity?entity_id={protocol_id}&relation_type=executed_in
```

### Через SQL

```sql
-- Створити зв'язок між повідомленням та правилом
INSERT INTO message_entity_links (message_id, entity_id, relation_type)
VALUES ('message-uuid', 'rule-uuid', 'uses');

-- Створити зв'язок між сесією та протоколом
INSERT INTO session_entity_links (session_id, entity_id, relation_type)
VALUES ('session-uuid', 'protocol-uuid', 'executed_in');
```

## Примітки

- Embeddings генеруються автоматично для всіх повідомлень, якщо `generate_embeddings: true`
- Якщо генерація embedding не вдалася, повідомлення все одно зберігається (без embedding)
- Розмірність embedding: **768** (модель EmbeddingGemma)
- Стара колонка `embedding` (1536d) залишається для сумісності з OpenAI моделями
- Зв'язки між повідомленнями та правилами/інструкціями дозволяють відстежувати використання та використовувати RAG для пошуку релевантних інструкцій


