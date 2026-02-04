---
trigger: model_decision
description: Правило для редагування графу FalkorDB напряму через redis-cli
globs: **/*.py, **/*.md
---

# Редагування Графу FalkorDB

Коли користувач просить редагувати граф, створювати вузли, зв'язки або виконувати Cypher-запити:

## Метод виконання

**Виконуй Cypher-запити напряму через docker exec:**

```powershell
docker exec falkordb redis-cli GRAPH.QUERY GeminiMemory "<cypher_query>"
```

**НЕ використовуй:**
- Python скрипти
- db_cli.py
- Окремі файли для виконання запитів

## Приклади

### Створення вузла
```powershell
docker exec falkordb redis-cli GRAPH.QUERY GeminiMemory "CREATE (:User {id: 'user_123', name: 'John', telegram_id: 123456789})"
```

### Оновлення властивостей
```powershell
docker exec falkordb redis-cli GRAPH.QUERY GeminiMemory "MATCH (u:User {id: 'user_123'}) SET u.name = 'Jane' RETURN u"
```

### Створення зв'язку
```powershell
docker exec falkordb redis-cli GRAPH.QUERY GeminiMemory "MATCH (u:User {id: 'user_123'}), (c:Chat {id: 'chat_456'}) CREATE (u)-[:MEMBER_OF]->(c)"
```

### Перегляд графу
```powershell
docker exec falkordb redis-cli GRAPH.QUERY GeminiMemory "MATCH (n) RETURN labels(n), n.id, n.name"
```

### Видалення вузла
```powershell
docker exec falkordb redis-cli GRAPH.QUERY GeminiMemory "MATCH (n:User {id: 'user_123'}) DETACH DELETE n"
```

## Важливо

- Граф за замовчуванням: `GeminiMemory`
- Контейнер: `falkordb`
- Кожен вузол ПОВИНЕН мати атрибути `id` та `name`
- Використовуй `MERGE` для уникнення дублікатів
- Перевіряй результат після виконання запиту
