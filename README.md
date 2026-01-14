# 🧠 Cursor Workspace with Neon Memory

**Репозиторій для роботи з Cursor AI та системою пам'яті на базі Neon PostgreSQL.**

Цей воркспейс містить:
- **Embedding Service** — сервіс для генерації векторних представлень (embeddings) з використанням Ollama
- **Система пам'яті** — збереження сесій та повідомлень в Neon PostgreSQL з підтримкою векторного пошуку

---

## 📁 Структура проекту

```
C:\Cursor workspace\
├── embedding-service/          # 🧬 Сервіс генерації embeddings
│   ├── app/                    # FastAPI додаток
│   │   ├── api/                # API endpoints
│   │   ├── database.py         # Робота з БД
│   │   ├── embedding.py        # Генерація embeddings через Ollama
│   │   └── main.py             # Точка входу
│   ├── chunking/               # Стратегії чанкінгу тексту
│   ├── scripts/                # Утиліти та скрипти
│   │   ├── generate_embeddings_for_all_sessions.py
│   │   └── save_session.py
│   ├── docker-compose.yml      # Docker конфігурація
│   └── README.md               # Документація embedding-service
│
├── migrations/                 # 🛠 SQL міграції для БД
│   └── init.sql                # Початкова схема БД
│
├── AGENT.md                    # Правила для AI агента
└── README.md                   # Цей файл
```

---

## 🚀 Швидкий старт

### 1. Налаштування Neon бази даних

1. Створіть проект на [Neon](https://console.neon.tech)
2. Виконайте SQL скрипт [`migrations/init.sql`](migrations/init.sql) в консолі Neon
3. Збережіть connection string

### 2. Запуск Embedding Service

#### Варіант A: Docker (рекомендовано)

```bash
cd embedding-service

# Створіть .env файл з NEON_CONNECTION_STRING
# Відредагуйте docker-compose.yml або створіть .env

# Запуск сервісів
docker-compose up -d

# Завантаження моделі Ollama
docker exec embedding-ollama ollama pull embeddinggemma:latest

# Перевірка
curl http://localhost:8000/api/v1/health
```

#### Варіант B: Локально

```bash
cd embedding-service

# Встановіть залежності
pip install -r requirements.txt

# Запустіть Ollama локально
ollama pull embeddinggemma:latest

# Налаштуйте .env з NEON_CONNECTION_STRING

# Запуск сервісу
python -m app.main
```

### 3. Налаштування Cursor + Neon MCP

1. Відкрийте Cursor Settings → Tools & MCP
2. Додайте Neon MCP сервер з connection string
3. Перевірте що сервер активний

---

## 🧬 Embedding Service

Сервіс для генерації embeddings з використанням локальної моделі Ollama EmbeddingGemma.

### Основні можливості:

- ✅ Генерація embeddings через REST API
- ✅ Підтримка різних стратегій чанкінгу (simple, recursive, semantic)
- ✅ Збереження embeddings в Neon PostgreSQL з pgvector
- ✅ Batch обробка повідомлень
- ✅ API для генерації embeddings для всіх сесій

### API Endpoints:

- `POST /api/v1/embed` — генерація embedding для тексту
- `POST /api/v1/embed-chunked` — генерація embeddings для чанкованого тексту
- `POST /api/v1/sessions` — збереження сесії з повідомленнями
- `POST /api/v1/sessions/{session_id}/generate-embeddings` — генерація embeddings для конкретної сесії
- `POST /api/v1/sessions/generate-embeddings/all` — генерація embeddings для всіх сесій
- `GET /api/v1/sessions/stats` — статистика про сесії та embeddings
- `GET /api/v1/health` — перевірка здоров'я сервісу

📖 **Детальна документація:** [`embedding-service/README.md`](embedding-service/README.md)

---

## 🗄️ Структура бази даних

База даних містить:

- **sessions** — метадані сесій (id, topic, created_at, metadata)
- **messages** — повідомлення з embeddings (session_id, role, content, embedding_v2)
- **entity_nodes** — вузли графу знань (правила, інструкції, протоколи)
- **entity_edges** — зв'язки між вузлами
- **protocol_triggers** — тригери для запуску протоколів

Всі embeddings зберігаються в колонці `embedding_v2` типу `vector(768)`.

---

## 📝 Скрипти та утиліти

### Генерація embeddings для всіх сесій

```bash
# Через Docker
docker exec -e NEON_CONNECTION_STRING="..." embedding-service \
  python /app/scripts/generate_embeddings_for_all_sessions.py

# Локально
cd embedding-service
python scripts/generate_embeddings_for_all_sessions.py
```

### Збереження сесії

**Універсальний скрипт `save_session.py`** приймає дані з різних джерел:

```bash
# 1. З stdin (JSON)
echo '{"topic": "Test", "messages": [{"role": "user", "content": "Hello"}]}' | \
  python scripts/save_session.py

# 2. З файлу
python scripts/save_session.py --file session.json

# 3. Через API (якщо сервер запущений)
python scripts/save_session.py --use-api --file session.json

# 4. З аргументів командного рядка
python scripts/save_session.py \
  --topic "Test Session" \
  --messages '[{"role": "user", "content": "Hello"}]'

# Через Docker
docker exec -e NEON_CONNECTION_STRING="..." embedding-service \
  python /app/scripts/save_session.py --file /app/session.json
```

**Формат JSON файлу:**
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

---

## 🛠 Технології

- **Neon PostgreSQL** + **pgvector** — база даних для пам'яті та векторного пошуку
- **Ollama** + **EmbeddingGemma** — локальна генерація embeddings
- **FastAPI** — REST API сервіс
- **Docker** — контейнеризація
- **MCP (Model Context Protocol)** — інтеграція з Cursor AI

---

## 📊 Статистика

Перевірити статистику про сесії та embeddings:

```bash
# Через API
curl http://localhost:8000/api/v1/sessions/stats

# Або через Neon MCP
# Попросіть AI: "Покажи статистику про сесії в базі даних"
```

---

## 🔧 Розробка

### Додавання нових endpoints

1. Додайте endpoint в `embedding-service/app/api/routes.py`
2. Додайте методи в `embedding-service/app/database.py` якщо потрібно
3. Перезапустіть сервіс

### Тестування

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Генерація embedding
curl -X POST http://localhost:8000/api/v1/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "Test text"}'

# Документація API
# Відкрийте http://localhost:8000/docs
```

---

## 📄 Ліцензія

MIT License
