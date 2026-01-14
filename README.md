# 🧠 Cursor Workspace with Neon Memory

**Репозиторій для роботи з Cursor AI та системою пам'яті на базі Neon PostgreSQL.**

Цей воркспейс містить:
- **Embedding Service** — сервіс для генерації векторних представлень (embeddings) з використанням Ollama
- **Система пам'яті** — збереження сесій та повідомлень в Neon PostgreSQL з підтримкою векторного пошуку
- **Граф знань** — система правил, інструкцій та протоколів для AI агента
- **RAG (Retrieval-Augmented Generation)** — векторний пошук для знаходження релевантної інформації

---

## 🎯 Філософія проекту

Цей проект реалізує систему пам'яті для AI агента на основі графу знань:

- **Правила (Rules)** — фундаментальні принципи роботи системи
- **Інструкції (Instructions)** — покрокові керівництва для конкретних задач
- **Протоколи (Protocols)** — стандартизовані набори інструкцій з триггерами
- **Граф знань** — зв'язки між правилами, інструкціями та протоколами через `entity_edges`
- **RAG (Retrieval-Augmented Generation)** — векторний пошук для знаходження релевантної інформації

Система дотримується принципу **Append-Only**: дані ніколи не видаляються, тільки архівуються через `valid_to`.

📖 **Детальна філософія:** [`PHILOSOPHY.md`](PHILOSOPHY.md)

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
│   ├── init.sql                # Початкова схема БД
│   ├── 003_schema_versioning.sql
│   ├── 004_add_instructions_and_triggers.sql
│   └── 005_cleanup_unused_columns.sql
│
├── AGENT.md                    # Правила для AI агента
├── PHILOSOPHY.md               # Філософія проекту
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
- ✅ **RAG (Retrieval-Augmented Generation)** — векторний пошук по повідомленням та сутностям
- ✅ **Граф знань** — робота з правилами, інструкціями та протоколами
- ✅ **Версіонування схеми** — автоматичне відстеження міграцій

### API Endpoints:

#### Генерація embeddings
- `POST /api/v1/embed` — генерація embedding для тексту
- `POST /api/v1/embed-chunked` — генерація embeddings для чанкованого тексту
- `GET /api/v1/strategies` — список доступних стратегій чанкінгу

#### Робота з сесіями
- `POST /api/v1/sessions` — збереження сесії з повідомленнями
- `POST /api/v1/sessions/{session_id}/generate-embeddings` — генерація embeddings для конкретної сесії
- `POST /api/v1/sessions/generate-embeddings/all` — генерація embeddings для всіх сесій
- `GET /api/v1/sessions/stats` — статистика про сесії та embeddings

#### RAG (Retrieval-Augmented Generation)
- `POST /api/v1/rag/search-messages` — векторний пошук по повідомленням
- `POST /api/v1/rag/search-entities` — векторний пошук по сутностям графу знань

#### Робота з графом знань
- `GET /api/v1/rules/critical` — отримання критичних правил
- `GET /api/v1/entities/{entity_id}/children` — отримання дочірніх сутностей
- `POST /api/v1/messages/{message_id}/link-entity` — створення зв'язку повідомлення-сутність
- `POST /api/v1/sessions/{session_id}/link-entity` — створення зв'язку сесія-сутність

#### Системні
- `GET /api/v1/health` — перевірка здоров'я сервісу

📖 **Детальна документація:** [`embedding-service/README.md`](embedding-service/README.md)

---

## 🔍 RAG (Retrieval-Augmented Generation)

Система підтримує векторний пошук для знаходження релевантних інструкцій та історії сесій:

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

### Векторний пошук по сутностям графу знань
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

### Критичні правила системи

Система містить 9 критичних правил, які завантажуються автоматично:

1. **AlwaysConfirmBeforeChanges** - ЗАВЖДИ отримуй явне підтвердження перед внесенням змін
2. **AppendOnlyPrinciple** - Ніколи не видаляй дані, тільки архівуй
3. **EntityRelationships** - Завжди створюй зв'язки через entity_edges
4. **ProjectBranching** - Нові проекти = нові гілки в Neon
5. **SessionContextSave** - Зберігай повідомлення з embeddings та зв'язками
6. **SourcePriority** - Пріоритет джерел інформації
7. **TemporalFacts** - Темпоральність для всіх фактів
8. **UseExistingTools** - Перевіряй наявність існуючих рішень
9. **VerifyBeforeAct** - Перевіряй існування перед згадуванням

Детальні описи правил доступні через API: `GET /api/v1/rules/critical`

### Отримання критичних правил
```bash
GET /api/v1/rules/critical
```

### Отримання дочірніх сутностей
```bash
GET /api/v1/entities/{entity_id}/children?relation_type=contains&child_type=Instruction
```

### Створення зв'язків між повідомленнями та правилами
```bash
POST /api/v1/messages/{message_id}/link-entity?entity_id={rule_id}&relation_type=uses
```

### Створення зв'язків між сесіями та протоколами
```bash
POST /api/v1/sessions/{session_id}/link-entity?entity_id={protocol_id}&relation_type=executed_in
```

## 🗄️ Структура бази даних

База даних містить:

- **sessions** — метадані сесій (id, topic, created_at, metadata)
- **messages** — повідомлення з embeddings (session_id, role, content, embedding_v2, embedding_model_id)
- **entity_nodes** — вузли графу знань (правила, інструкції, протоколи, факти)
  - type: 'Rule' | 'Instruction' | 'Protocol' | 'Fact' | 'Technology' | 'Tool' | 'SystemNode'
- **entity_edges** — зв'язки між вузлами
  - relation_type: 'contains' | 'uses' | 'depends_on' | 'applies_to' | 'applies' | 'executed_in'
- **protocol_triggers** — тригери для запуску протоколів
- **message_entity_links** — зв'язки між повідомленнями та правилами/інструкціями
- **session_entity_links** — зв'язки між сесіями та протоколами
- **embedding_models** — метадані моделей embeddings
- **schema_migrations** — історія застосованих міграцій

Всі embeddings зберігаються в колонці `embedding_v2` типу `vector(768)`.

## 🔄 Версіонування схеми

Система автоматично відстежує застосовані міграції через таблицю `schema_migrations`:

```sql
-- Перевірити застосовані міграції
SELECT version, name, description, applied_at 
FROM schema_migrations 
ORDER BY version;
```

Міграції застосовуються вручну через Neon Console або автоматично через скрипти.

---

## 📝 Скрипти та утиліти

### Застосування міграцій

**Автоматичний скрипт для застосування міграцій** `scripts/run_migrations.py`:

```bash
# Dry run (перевірка що буде застосовано)
python scripts/run_migrations.py --dry-run

# Застосування міграцій
NEON_CONNECTION_STRING="..." python scripts/run_migrations.py

# Або з явним connection string
python scripts/run_migrations.py --connection-string "postgresql://..."
```

Скрипт автоматично:
- Знаходить всі міграції в `migrations/` директорії
- Перевіряє які вже застосовані через `schema_migrations`
- Застосовує тільки нові міграції
- Перевіряє checksums для безпеки

### Ініціалізація графу знань

**Seed скрипт** для створення базових правил, інструкцій та протоколів:

```bash
# Ініціалізація базових даних
NEON_CONNECTION_STRING="..." python scripts/seed_knowledge_graph.py

# Або з явним connection string
python scripts/seed_knowledge_graph.py --connection-string "postgresql://..."
```

Скрипт створює:
- CriticalRules system node
- 9 базових правил (включаючи AlwaysConfirmBeforeChanges)
- 5 базових інструкцій (включаючи ChangeConfirmationInstruction)
- 2 протоколи (Bootstrap Protocol та SafeChangeProtocol)
- Всі необхідні зв'язки між сутностями

### Робота з графом знань (CLI)

**CLI інструмент** для управління правилами, інструкціями та протоколами:

```bash
# Створити правило
python scripts/knowledge_graph_cli.py create-rule \
  --name "MyRule" \
  --description "Опис правила" \
  --link-to-critical

# Створити інструкцію
python scripts/knowledge_graph_cli.py create-instruction \
  --name "MyInstruction" \
  --description "Опис інструкції" \
  --rule-ids "rule-id-1" "rule-id-2"

# Створити протокол
python scripts/knowledge_graph_cli.py create-protocol \
  --name "MyProtocol" \
  --description "Опис протоколу" \
  --instruction-ids "inst-id-1" "inst-id-2" \
  --triggers "тригер 1" "тригер 2"

# Список сутностей
python scripts/knowledge_graph_cli.py list --type Rule
python scripts/knowledge_graph_cli.py list --type Instruction

# Показати деталі сутності
python scripts/knowledge_graph_cli.py show --id "entity-id"

# Пошук сутностей
python scripts/knowledge_graph_cli.py search --query "пошук"

# Зв'язати дві сутності
python scripts/knowledge_graph_cli.py link \
  --source-id "source-id" \
  --target-id "target-id" \
  --relation-type "uses"
```

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
