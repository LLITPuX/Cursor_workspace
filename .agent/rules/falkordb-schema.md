---
trigger: model_decision
description: FalkorDB Knowledge Graph Schema
globs: **/*.py, **/*.md
---

# FalkorDB Schema (GeminiMemory)

> [!IMPORTANT]
> **Мова графа:** Всі описи (`description`), інструкції, правила та контент вузлів повинні бути написані **виключно Українською мовою**.
> Англійська допускається лише в технічних полях (назви типів, ключів JSON, кодові імена).

## Вузли (Nodes)

### Identity Nodes
- **(:User)** — Учасник чату
  - `telegram_id` (int, UNIQUE)
  - `id` (string, UUID)
  - `name` (string)
  - `username` (string, optional)

- **(:Agent)** — AI-бот (джерело виходу)
  - `telegram_id` (int, UNIQUE)
  - `id` (string, UUID)
  - `name` (string)

### Context Nodes
- **(:Chat)** — Простір подій (груповий/приватний чат)
  - `chat_id` (int, UNIQUE)
  - `id` (string, UUID)
  - `name` (string)
  - `type` (string: `private`, `group`, `supergroup`)

### Event Nodes
- **(:Event:Message)** — Атомарна одиниця досвіду
  - `uid` (string: `{chat_id}:{message_id}`, INDEX)
  - `message_id` (int)
  - `text` (string)
  - `created_at` (float, Unix timestamp)

### Time Nodes
- **(:Year)** — Рік
  - `value` (int, UNIQUE, e.g. 2026)
  - `id` (string, UUID)
  - `name` (string, e.g. "2026")

- **(:Day)** — День
  - `date` (string, UNIQUE, e.g. "2026-02-03")
  - `id` (string, UUID)
  - `name` (string, номер дня в місяці, e.g. "3")

### Semantic Nodes (New)
- **(:Topic)** — Контекстний контейнер бесіди
  - `title` (string, UNIQUE constraint recommended on normalized title)
  - `description` (string)
  - `status` (string: `active`, `archived`)
  - `created_at` (timestamp)

- **(:Entity)** — Глобальні концепти (Tags)
  - `name` (string, UNIQUE)
  - `type` (string: `Technology`, `Person`, `Concept`, `Tool`)
  - `description` (string, optional)

## Зв'язки (Relationships)

### Авторство
- `(:User)-[:AUTHORED]->(:Event:Message)` — Юзер написав повідомлення
- `(:Agent)-[:GENERATED]->(:Event:Message)` — Агент згенерував відповідь

### Локація
- `(:Event:Message)-[:HAPPENED_IN]->(:Chat)` — Де сталося

### Час
- `(:Year)-[:MONTH {number: int}]->(:Day)` — Місяць як ребро з номером
- `(:Event:Message)-[:HAPPENED_AT {time: "HH:MM:SS"}]->(:Day)` — Точний час

### Хронологія (Linked List)
- `(:Event:Message)-[:NEXT]->(:Event:Message)` — Наступне повідомлення
- `(:Chat)-[:LAST_EVENT]->(:Event:Message)` — Вказівник на останнє повідомлення в чаті

### Семантика (Semantic Layer)
- `(:Event:Message)-[:DISCUSSES]->(:Topic)` — Повідомлення належить темі
- `(:Topic)-[:INVOLVES]->(:Entity)` — Тема стосується сутності (High-level)
- `(:Event:Message)-[:MENTIONS]->(:Entity)` — Повідомлення згадує сутність (Low-level granularity)

# FalkorDB Schema (ThinkerLogs)

> **Note:** Цей граф зберігається окремо під ключем `ThinkerLogs`.

## Вузли
- **(:LogEntry)** — Запис процесу мислення
  - `id` (uuid)
  - `timestamp` (float)
  - `prompt` (string, full input context)
  - `response` (string, raw LLM output)
  - `model` (string)

## Зв'язки
- `(:LogEntry)-[:TRIGGERED_BY]->(:Event:Message_Reference)` — (Опціонально) посилання на ID повідомлення з основного графа (тільки як text property, щоб не мішати графи).

## Приклад Cypher

```cypher
// Зберегти нове повідомлення від юзера
MATCH (u:User {telegram_id: $uid})
MATCH (c:Chat {chat_id: $cid})
MATCH (d:Day {date: $day_date})
CREATE (m:Event:Message {
    uid: $msg_uid,
    message_id: $msg_id,
    text: $text,
    created_at: $ts
})
CREATE (u)-[:AUTHORED]->(m)
CREATE (m)-[:HAPPENED_IN]->(c)
CREATE (m)-[:HAPPENED_AT {time: $time_str}]->(d)

// Linked List: оновити LAST_EVENT
WITH c, m
OPTIONAL MATCH (c)-[last_rel:LAST_EVENT]->(prev_msg)
DELETE last_rel
FOREACH (_ IN CASE WHEN prev_msg IS NOT NULL THEN [1] ELSE [] END |
    CREATE (prev_msg)-[:NEXT]->(m)
)
CREATE (c)-[:LAST_EVENT]->(m)
RETURN m.uid
```

## Команди для взаємодії

Використовуй `docker exec falkordb redis-cli` для прямих запитів:

```bash
docker exec falkordb redis-cli GRAPH.QUERY GeminiMemory "MATCH (n) RETURN n LIMIT 10"
```
