#!/usr/bin/env python3
"""
Модуль для пошуку в FalkorDB графі знань.
Використовує QPE API для обробки запиту та векторний пошук.
"""

import os
import sys
import httpx
import json
from typing import Optional, Dict, Any, List

try:
    from falkordb import FalkorDB
except ImportError:
    print("Помилка: не встановлено falkordb. Встановіть через:")
    print("  pip install falkordb")
    sys.exit(1)


async def process_query_with_qpe(
    query: str,
    qpe_url: str
) -> Dict[str, Any]:
    """
    Обробляє запит через QPE API.
    
    Args:
        query: Текстовий запит
        qpe_url: URL QPE Service
        
    Returns:
        Результат обробки з classifications, entities, embedding
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{qpe_url}/api/v1/qpe/process-query",
            json={"query": query}
        )
        response.raise_for_status()
        return response.json()


def search_similar_entities(
    graph,
    query_embedding: List[float],
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Шукає подібні сутності за допомогою векторного пошуку.
    
    Примітка: Якщо FalkorDB не підтримує векторний пошук напряму,
    використовуємо простий пошук по тексту.
    
    Args:
        graph: FalkorDB граф
        query_embedding: Embedding вектор запиту
        limit: Максимальна кількість результатів
        
    Returns:
        Список знайдених сутностей
    """
    # Поки що використовуємо простий пошук по активним Entity
    # В майбутньому можна додати векторний пошук, якщо FalkorDB підтримує
    query = """
    MATCH (e:Entity)
    WHERE e.valid_to IS NULL
    RETURN e.name AS name, e.type AS type, e.id AS id
    LIMIT $limit
    """
    
    result = graph.query(query, {'limit': limit})
    
    entities = []
    for row in result.result_set:
        entities.append({
            'name': row[0],
            'type': row[1],
            'id': row[2]
        })
    
    return entities


def search_relevant_messages(
    graph,
    query_text: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Шукає релевантні повідомлення за текстом запиту.
    
    Args:
        graph: FalkorDB граф
        query_text: Текст запиту
        limit: Максимальна кількість результатів
        
    Returns:
        Список знайдених повідомлень з контекстом
    """
    # Пошук повідомлень, які містять ключові слова з запиту
    keywords = query_text.lower().split()
    keyword_patterns = '|'.join(keywords[:5])  # Обмежуємо до 5 ключових слів
    
    query = """
    MATCH (s:Session)-[:HAS_MESSAGE]->(m:Message)
    WHERE m.valid_to IS NULL 
    AND s.valid_to IS NULL
    AND (toLower(m.content) CONTAINS toLower($query_text)
         OR any(keyword IN $keywords WHERE toLower(m.content) CONTAINS keyword))
    RETURN s.topic AS topic, m.role AS role, m.content AS content, 
           m.created_at AS created_at, s.id AS session_id, m.id AS message_id
    ORDER BY m.created_at DESC
    LIMIT $limit
    """
    
    result = graph.query(
        query,
        {
            'query_text': query_text,
            'keywords': keywords[:5],
            'limit': limit
        }
    )
    
    messages = []
    for row in result.result_set:
        messages.append({
            'topic': row[0],
            'role': row[1],
            'content': row[2],
            'created_at': row[3],
            'session_id': row[4],
            'message_id': row[5]
        })
    
    return messages


def search_entities_by_name(
    graph,
    entity_names: List[str]
) -> List[Dict[str, Any]]:
    """
    Шукає сутності за назвами та повертає пов'язані повідомлення.
    
    Args:
        graph: FalkorDB граф
        entity_names: Список назв сутностей
        
    Returns:
        Список сутностей з пов'язаними повідомленнями
    """
    query = """
    MATCH (e:Entity)-[r:MENTIONS]-(m:Message)-[:HAS_MESSAGE]-(s:Session)
    WHERE e.name IN $entity_names
    AND e.valid_to IS NULL
    AND m.valid_to IS NULL
    AND r.valid_to IS NULL
    AND s.valid_to IS NULL
    RETURN e.name AS entity_name, e.type AS entity_type,
           s.topic AS topic, m.role AS role, m.content AS content,
           r.weight AS weight, m.created_at AS created_at
    ORDER BY r.weight DESC, m.created_at DESC
    LIMIT 20
    """
    
    result = graph.query(query, {'entity_names': entity_names})
    
    results = []
    for row in result.result_set:
        results.append({
            'entity_name': row[0],
            'entity_type': row[1],
            'topic': row[2],
            'role': row[3],
            'content': row[4],
            'weight': row[5],
            'created_at': row[6]
        })
    
    return results


def format_search_results(
    qpe_result: Dict[str, Any],
    messages: List[Dict[str, Any]],
    entities: List[Dict[str, Any]]
) -> str:
    """
    Форматує результати пошуку для виводу.
    
    Args:
        qpe_result: Результат обробки через QPE
        messages: Знайдені повідомлення
        entities: Знайдені сутності
        
    Returns:
        Відформатований рядок з результатами
    """
    output = []
    output.append("=" * 80)
    output.append("🔍 РЕЗУЛЬТАТИ ПОШУКУ")
    output.append("=" * 80)
    
    # Класифікація запиту
    classifications = qpe_result.get('classifications', {})
    if classifications:
        output.append("\n📊 Класифікація запиту:")
        output.append(f"  Sentiment: {classifications.get('sentiment', 'N/A')}")
        output.append(f"  Intents: {', '.join(classifications.get('intents', []))}")
        output.append(f"  Complexity: {classifications.get('complexity', 'N/A')}")
    
    # Знайдені сутності
    qpe_entities = qpe_result.get('entities', [])
    if qpe_entities:
        output.append(f"\n🏷️  Витягнуті сутності ({len(qpe_entities)}):")
        for entity in qpe_entities[:10]:  # Показуємо перші 10
            output.append(f"  - [{entity.get('type', 'Unknown')}] {entity.get('text', '')}")
    
    # Знайдені повідомлення
    if messages:
        output.append(f"\n💬 Знайдені повідомлення ({len(messages)}):")
        for i, msg in enumerate(messages[:5], 1):  # Показуємо перші 5
            output.append(f"\n  {i}. [{msg['role']}] Сесія: {msg['topic']}")
            content_preview = msg['content'][:200] + "..." if len(msg['content']) > 200 else msg['content']
            output.append(f"     {content_preview}")
    
    # Знайдені сутності в графі
    if entities:
        output.append(f"\n🔗 Сутності в графі ({len(entities)}):")
        for entity in entities[:10]:  # Показуємо перші 10
            output.append(f"  - [{entity.get('type', 'Unknown')}] {entity.get('name', '')}")
    
    if not messages and not entities:
        output.append("\n⚠️  Нічого не знайдено. Спробуйте інший запит або переконайтеся, що дані завантажені в граф.")
    
    output.append("\n" + "=" * 80)
    
    return "\n".join(output)


async def search_memory(
    query: str,
    graph_name: str = "cursor_graph",
    falkordb_host: str = "localhost",
    falkordb_port: int = 6379,
    qpe_url: str = "http://localhost:8001"
) -> str:
    """
    Головна функція пошуку в графі знань.
    
    Args:
        query: Текстовий запит
        graph_name: Назва графу в FalkorDB
        falkordb_host: Хост FalkorDB
        falkordb_port: Порт FalkorDB
        qpe_url: URL QPE Service
        
    Returns:
        Відформатований рядок з результатами пошуку
    """
    # Обробка запиту через QPE
    import asyncio
    qpe_result = asyncio.run(process_query_with_qpe(query, qpe_url))
    
    # Підключення до FalkorDB
    client = FalkorDB(host=falkordb_host, port=falkordb_port, password=None)
    graph = client.select_graph(graph_name)
    
    # Витягнути назви сутностей з QPE результату
    entity_names = [e.get('text', '').strip() for e in qpe_result.get('entities', [])]
    entity_names = [name for name in entity_names if name]
    
    # Пошук повідомлень
    messages = search_relevant_messages(graph, query, limit=10)
    
    # Пошук сутностей
    entities = []
    if entity_names:
        entities = search_entities_by_name(graph, entity_names[:10])  # Обмежуємо до 10
    
    # Форматування результатів
    return format_search_results(qpe_result, messages, entities)
