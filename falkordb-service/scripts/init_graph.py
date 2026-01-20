#!/usr/bin/env python3
"""
Скрипт для ініціалізації базової структури графу в FalkorDB.
"""

import os
import sys
from typing import Optional

try:
    from falkordb import FalkorDB
except ImportError:
    print("Помилка: не встановлено falkordb. Встановіть через:")
    print("  pip install -r requirements.txt")
    sys.exit(1)


def create_base_structure(
    host: str = "localhost",
    port: int = 6379,
    password: Optional[str] = None,
    graph_name: str = "agent_memory"
) -> bool:
    """Створює базову структуру графу в FalkorDB."""
    try:
        print(f"🔌 Підключення до FalkorDB на {host}:{port}...")
        
        client = FalkorDB(host=host, port=port, password=password)
        graph = client.select_graph(graph_name)
        print(f"✅ Підключено до графу '{graph_name}'")
        
        # Створення базових типів класифікації
        print("\n📋 Створення базових типів...")
        
        # Sentiment типи
        sentiment_types = ["neutral", "positive_feedback", "negative_feedback", "frustrated"]
        for sentiment in sentiment_types:
            query = f"MERGE (s:Sentiment {{name: '{sentiment}'}}) SET s.created_at = datetime() RETURN s"
            graph.query(query)
        print(f"✅ Створено {len(sentiment_types)} типів Sentiment")
        
        # Intent типи
        intent_types = [
            "information_seeking", "capability_inquiry", "task_execution",
            "project_discussion", "error_resolution", "clarification_needed"
        ]
        for intent in intent_types:
            query = f"MERGE (i:Intent {{name: '{intent}'}}) SET i.created_at = datetime() RETURN i"
            graph.query(query)
        print(f"✅ Створено {len(intent_types)} типів Intent")
        
        # Complexity типи
        complexity_types = ["simple_question", "structured_prompt", "architectural", "requires_clarification"]
        for complexity in complexity_types:
            query = f"MERGE (c:Complexity {{name: '{complexity}'}}) SET c.created_at = datetime() RETURN c"
            graph.query(query)
        print(f"✅ Створено {len(complexity_types)} типів Complexity")
        
        # ResponseType типи
        response_types = ["explanation", "code_proposal", "analysis", "question"]
        for rtype in response_types:
            query = f"MERGE (r:ResponseType {{name: '{rtype}'}}) SET r.created_at = datetime() RETURN r"
            graph.query(query)
        print(f"✅ Створено {len(response_types)} типів ResponseType")
        
        # EntityType типи
        entity_types = [
            "Technology", "Framework", "Library", "Database", "Language",
            "Project", "Component", "Service", "API", "Endpoint",
            "Task", "Feature", "Bug", "Requirement",
            "Concept", "Pattern", "Architecture", "Design",
            "Person", "Role", "Team",
            "File", "Directory", "Config", "Script",
            "Preference", "Constraint", "Decision",
            "Tool", "CodeBlock", "Recommendation", "Action", "Analysis", "Question"
        ]
        for etype in entity_types:
            query = f"MERGE (e:EntityType {{name: '{etype}'}}) SET e.created_at = datetime() RETURN e"
            graph.query(query)
        print(f"✅ Створено {len(entity_types)} типів EntityType")
        
        # Перевірка створеної структури
        print("\n📊 Перевірка створеної структури...")
        stats_query = "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label"
        stats_result = graph.query(stats_query)
        
        print("\nСтворені типи вузлів:")
        for row in stats_result.result_set:
            print(f"  - {row[0]}: {row[1]} вузлів")
        
        print("\n✅ Базова структура графу успішно створена!")
        return True
        
    except Exception as e:
        print(f"\n❌ Помилка: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    password = os.getenv("FALKORDB_PASSWORD", None)
    graph_name = os.getenv("FALKORDB_GRAPH_NAME", "agent_memory")
    
    print("=" * 60)
    print("🏗️  Ініціалізація базової структури графу FalkorDB")
    print("=" * 60)
    
    success = create_base_structure(host, port, password, graph_name)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
