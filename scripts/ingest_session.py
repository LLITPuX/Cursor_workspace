#!/usr/bin/env python3
"""
Модуль для інгестії MD-файлів сесій у FalkorDB.
Обробляє файли, витягує сутності через QPE API та зберігає в граф з темпоральними метками.
"""

import os
import re
import sys
import uuid
import json
import httpx
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    from falkordb import FalkorDB
except ImportError:
    print("Помилка: не встановлено falkordb. Встановіть через:")
    print("  pip install falkordb")
    sys.exit(1)


def parse_datetime(date_str: str) -> Dict[str, Optional[str]]:
    """
    Парсить рядок дати та часу, повертає date та time окремо.
    
    Підтримує формати:
    - "20 січня 2026, 14:30:00" (новий формат з часом)
    - "20 січня 2026" (старий формат без часу)
    
    Args:
        date_str: Рядок з датою та опціонально часом
        
    Returns:
        Словник з 'date' та 'time' (time може бути None)
    """
    date_str = date_str.strip()
    
    # Перевірити чи є час у форматі ", HH:MM:SS"
    time_match = re.search(r',\s*(\d{1,2}:\d{2}:\d{2})$', date_str)
    
    if time_match:
        # Є час - розділити дату та час
        time_str = time_match.group(1)
        date_only = date_str[:time_match.start()].strip()
        return {
            'date': date_only,
            'time': time_str
        }
    else:
        # Немає часу - тільки дата
        return {
            'date': date_str,
            'time': None
        }


def parse_session_file(file_path: str) -> Dict[str, Any]:
    """
    Парсить MD-файл сесії та витягує метадані та повідомлення.
    
    Args:
        file_path: Шлях до MD-файлу
        
    Returns:
        Словник з метаданими та списком повідомлень
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Витягнути метадані з заголовка
    metadata = {}
    header_match = re.search(r'^#\s*Сесія:\s*(.+?)$', content, re.MULTILINE)
    if header_match:
        metadata['title'] = header_match.group(1).strip()
    
    # Витягнути дату та час
    date_match = re.search(r'\*\*Дата:\*\*\s*(.+?)$', content, re.MULTILINE)
    if date_match:
        date_time_str = date_match.group(1).strip()
        # Парсити дату та час
        parsed_dt = parse_datetime(date_time_str)
        metadata['date'] = parsed_dt['date']
        metadata['time'] = parsed_dt['time']
    else:
        metadata['date'] = ''
        metadata['time'] = None
    
    # Витягнути тему
    topic_match = re.search(r'\*\*Тема:\*\*\s*(.+?)$', content, re.MULTILINE)
    if topic_match:
        metadata['topic'] = topic_match.group(1).strip()
    
    # Розбити на блоки повідомлень
    messages = []
    
    # Паттерн для пошуку блоків "Запит користувача" та "Відповідь"
    user_pattern = r'##\s*Запит\s+користувача\s+#\d+\s*\n\n(.*?)(?=\n###|\n##|$)'
    assistant_pattern = r'###\s*(?:Аналіз\s+та\s+дії|Відповідь)\s*#\d+\s*\n\n(.*?)(?=\n##|$)'
    
    user_matches = list(re.finditer(user_pattern, content, re.DOTALL | re.IGNORECASE))
    assistant_matches = list(re.finditer(assistant_pattern, content, re.DOTALL | re.IGNORECASE))
    
    # Об'єднати та відсортувати за позицією в файлі
    all_matches = []
    for match in user_matches:
        all_matches.append(('user', match.start(), match.group(1).strip()))
    for match in assistant_matches:
        all_matches.append(('assistant', match.start(), match.group(1).strip()))
    
    all_matches.sort(key=lambda x: x[1])
    
    for role, _, text in all_matches:
        if text.strip():
            messages.append({
                'role': role,
                'content': text.strip()
            })
    
    return {
        'metadata': metadata,
        'messages': messages,
        'file_path': file_path
    }


async def process_message_with_qpe(
    message: Dict[str, Any],
    qpe_url: str
) -> Dict[str, Any]:
    """
    Обробляє повідомлення через QPE API.
    
    Args:
        message: Словник з 'role' та 'content'
        qpe_url: URL QPE Service
        
    Returns:
        Результат обробки з classifications, entities, embeddings
    """
    async with httpx.AsyncClient(timeout=300.0) as client:
        if message['role'] == 'user':
            # Обробка запиту користувача
            response = await client.post(
                f"{qpe_url}/api/v1/qpe/process-query",
                json={"query": message['content']}
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                'classifications': data.get('classifications', {}),
                'entities': data.get('entities', []),
                'embedding': data.get('embedding', [])
            }
        else:
            # Обробка відповіді асистента
            # Розбиваємо на частини (якщо є структура)
            structure = {
                'analysis': '',
                'response': message['content'],
                'questions': ''
            }
            
            response = await client.post(
                f"{qpe_url}/api/v1/qpe/process-assistant-response",
                json={
                    "response": message['content'],
                    "structure": structure
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                'classifications': data.get('classifications', {}),
                'entities': data.get('entities', []),
                'embeddings': data.get('embeddings', {})
            }


def get_current_timestamp() -> str:
    """Повертає поточний timestamp в ISO форматі для використання в Cypher."""
    return datetime.now().isoformat()


def create_session_node(
    graph,
    session_id: str,
    metadata: Dict[str, Any],
    file_path: str
) -> None:
    """Створює вузол Session з темпоральними метками."""
    topic = metadata.get('topic', metadata.get('title', 'Unknown'))
    date = metadata.get('date', '')
    time = metadata.get('time', None)
    
    # Формувати повну дату з часом для збереження в граф
    # Якщо час є, додаємо його до дати
    date_time_str = date
    if time:
        date_time_str = f"{date}, {time}"
    
    timestamp = get_current_timestamp()
    query = """
    CREATE (s:Session {
        id: $session_id,
        topic: $topic,
        file_path: $file_path,
        date: $date,
        time: $time,
        date_time: $date_time,
        created_at: $timestamp,
        valid_from: $timestamp,
        valid_to: null
    })
    RETURN s
    """
    
    graph.query(
        query,
        {
            'session_id': session_id,
            'topic': topic,
            'file_path': file_path,
            'date': date,
            'time': time if time else '',
            'date_time': date_time_str,
            'timestamp': timestamp
        }
    )


def create_message_node(
    graph,
    message_id: str,
    session_id: str,
    role: str,
    content: str,
    prev_message_id: Optional[str] = None
) -> None:
    """Створює вузол Message та зв'язки з темпоральними метками."""
    timestamp = get_current_timestamp()
    # Створення вузла Message
    query = """
    MATCH (s:Session {id: $session_id})
    CREATE (m:Message {
        id: $message_id,
        role: $role,
        content: $content,
        created_at: $timestamp,
        valid_from: $timestamp,
        valid_to: null
    })
    CREATE (s)-[:HAS_MESSAGE {
        created_at: $timestamp,
        valid_from: $timestamp,
        valid_to: null
    }]->(m)
    RETURN m
    """
    
    graph.query(
        query,
        {
            'session_id': session_id,
            'message_id': message_id,
            'role': role,
            'content': content,
            'timestamp': timestamp
        }
    )
    
    # Створення зв'язку NEXT (якщо є попереднє повідомлення)
    if prev_message_id:
        query = """
        MATCH (prev:Message {id: $prev_id}), (curr:Message {id: $curr_id})
        CREATE (prev)-[:NEXT {
            created_at: $timestamp,
            valid_from: $timestamp,
            valid_to: null
        }]->(curr)
        RETURN prev, curr
        """
        
        graph.query(
            query,
            {
                'prev_id': prev_message_id,
                'curr_id': message_id,
                'timestamp': timestamp
            }
        )


def create_entity_nodes_and_links(
    graph,
    message_id: str,
    entities: List[Dict[str, Any]],
    entity_embeddings: Dict[str, List[float]]
) -> None:
    """
    Створює вузли Entity та зв'язки [:MENTIONS] з темпоральними метками.
    
    Args:
        graph: FalkorDB граф
        message_id: ID повідомлення
        entities: Список сутностей з QPE
        entity_embeddings: Словник {entity_name: embedding_vector}
    """
    for entity in entities:
        entity_name = entity.get('text', '').strip()
        entity_type = entity.get('type', 'Unknown')
        
        if not entity_name:
            continue
        
        # Отримати embedding для цієї сутності
        embedding = entity_embeddings.get(entity_name, None)
        
        # Створити або оновити Entity
        entity_id = str(uuid.uuid4())
        timestamp = get_current_timestamp()
        
        if embedding:
            # Зберігаємо embedding як JSON рядок (FalkorDB може не підтримувати vecf32 напряму)
            embedding_json = json.dumps(embedding)
            
            query = """
            MERGE (e:Entity {name: $entity_name})
            ON CREATE SET 
                e.id = $entity_id,
                e.type = $entity_type,
                e.embedding = $embedding,
                e.created_at = $timestamp,
                e.valid_from = $timestamp,
                e.valid_to = null
            ON MATCH SET
                e.valid_to = null
            WITH e
            MATCH (m:Message {id: $message_id})
            CREATE (m)-[:MENTIONS {
                weight: 1.0,
                created_at: $timestamp,
                valid_from: $timestamp,
                valid_to: null
            }]->(e)
            RETURN e, m
            """
            
            graph.query(
                query,
                {
                    'entity_name': entity_name,
                    'entity_id': entity_id,
                    'entity_type': entity_type,
                    'embedding': embedding_json,
                    'message_id': message_id,
                    'timestamp': timestamp
                }
            )
        else:
            # Якщо немає embedding, створюємо без нього
            query = """
            MERGE (e:Entity {name: $entity_name})
            ON CREATE SET 
                e.id = $entity_id,
                e.type = $entity_type,
                e.created_at = $timestamp,
                e.valid_from = $timestamp,
                e.valid_to = null
            ON MATCH SET
                e.valid_to = null
            WITH e
            MATCH (m:Message {id: $message_id})
            CREATE (m)-[:MENTIONS {
                weight: 1.0,
                created_at: $timestamp,
                valid_from: $timestamp,
                valid_to: null
            }]->(e)
            RETURN e, m
            """
            
            graph.query(
                query,
                {
                    'entity_name': entity_name,
                    'entity_id': entity_id,
                    'entity_type': entity_type,
                    'message_id': message_id,
                    'timestamp': timestamp
                }
            )


def ensure_vector_index(graph) -> None:
    """Перевіряє та створює векторний індекс для Entity, якщо потрібно."""
    # Примітка: FalkorDB може не підтримувати векторні індекси напряму
    # Якщо підтримує, використовуємо, інакше - пропускаємо
    try:
        query = """
        CREATE VECTOR INDEX FOR (e:Entity) ON (e.embedding) 
        OPTIONS {dimension: 768, similarityFunction: 'cosine'}
        """
        graph.query(query)
        print("✅ Векторний індекс створено або вже існує")
    except Exception as e:
        # Індекс може вже існувати або не підтримуватися
        error_str = str(e).lower()
        if "already exists" in error_str or "not supported" in error_str or "syntax" in error_str:
            print(f"ℹ️  Векторний індекс не створено (може не підтримуватися): {e}")
        else:
            print(f"⚠️  Попередження при створенні індексу: {e}")


async def ingest_session_file(
    file_path: str,
    graph_name: str = os.getenv("FALKORDB_GRAPH_NAME", "agent_memory"),
    falkordb_host: str = "localhost",
    falkordb_port: int = 6379,
    qpe_url: str = "http://localhost:8001"
) -> None:
    """
    Головна функція інгестії сесії.
    
    Args:
        file_path: Шлях до MD-файлу сесії
        graph_name: Назва графу в FalkorDB
        falkordb_host: Хост FalkorDB
        falkordb_port: Порт FalkorDB
        qpe_url: URL QPE Service
    """
    print(f"📖 Читання файлу: {file_path}")
    
    # Парсинг файлу
    parsed = parse_session_file(file_path)
    print(f"✅ Знайдено {len(parsed['messages'])} повідомлень")
    
    # Підключення до FalkorDB
    print(f"🔌 Підключення до FalkorDB на {falkordb_host}:{falkordb_port}...")
    client = FalkorDB(host=falkordb_host, port=falkordb_port, password=None)
    graph = client.select_graph(graph_name)
    print(f"✅ Підключено до графу '{graph_name}'")
    
    # Перевірка векторного індексу
    ensure_vector_index(graph)
    
    # Створення Session
    session_id = str(uuid.uuid4())
    print(f"📝 Створення сесії: {session_id}")
    create_session_node(graph, session_id, parsed['metadata'], file_path)
    
    # Обробка повідомлень
    prev_message_id = None
    
    for i, message in enumerate(parsed['messages'], 1):
        print(f"  📨 Обробка повідомлення {i}/{len(parsed['messages'])} ({message['role']})...")
        
        # Обробка через QPE
        qpe_result = await process_message_with_qpe(message, qpe_url)
        
        # Створення Message
        message_id = str(uuid.uuid4())
        create_message_node(
            graph,
            message_id,
            session_id,
            message['role'],
            message['content'],
            prev_message_id
        )
        
        # Обробка сутностей
        entities = []
        entity_embeddings = {}
        
        if message['role'] == 'user':
            # Для user messages entities вже є в qpe_result
            entities = qpe_result.get('entities', [])
            if entities:
                print(f"    🔍 Знайдено {len(entities)} сутностей")
                # Для user messages embedding вже є в qpe_result
                embedding = qpe_result.get('embedding', [])
                # Створити embedding для кожної сутності (спрощено - використовуємо загальний)
                for entity in entities:
                    entity_name = entity.get('text', '').strip()
                    if entity_name and embedding:
                        entity_embeddings[entity_name] = embedding
        else:
            # Для assistant messages entities в окремих полях
            analysis_entities = qpe_result.get('analysis_entities', [])
            response_entities = qpe_result.get('response_entities', [])
            entities = analysis_entities + response_entities
            
            if entities:
                print(f"    🔍 Знайдено {len(entities)} сутностей")
                # Для assistant messages embeddings в словнику
                embeddings = qpe_result.get('embeddings', {})
                # Використовуємо embedding з response частини
                response_embedding = embeddings.get('response', [])
                for entity in entities:
                    entity_name = entity.get('text', '').strip()
                    if entity_name and response_embedding:
                        entity_embeddings[entity_name] = response_embedding
        
        if entities:
            
            # Створити Entity та зв'язки
            create_entity_nodes_and_links(
                graph,
                message_id,
                entities,
                entity_embeddings
            )
        
        prev_message_id = message_id
    
    print(f"✅ Інгестія завершена! Сесія збережена з ID: {session_id}")
