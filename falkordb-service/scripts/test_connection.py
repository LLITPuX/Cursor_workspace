#!/usr/bin/env python3
"""
Скрипт для тестування підключення до FalkorDB та базових операцій.
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


def test_connection(
    host: str = "localhost",
    port: int = 6379,
    password: Optional[str] = None,
    graph_name: str = "agent_memory"
) -> bool:
    """Тестує підключення до FalkorDB та базові операції."""
    try:
        print(f"🔌 Підключення до FalkorDB на {host}:{port}...")
        
        client = FalkorDB(host=host, port=port, password=password)
        graph = client.select_graph(graph_name)
        print(f"✅ Підключено до графу '{graph_name}'")
        
        # Тест: Створення тестового вузла
        print("\n📝 Тест: Створення тестового вузла...")
        query = "CREATE (n:TestNode {name: 'test', value: 42}) RETURN n"
        result = graph.query(query)
        print(f"✅ Вузол створено")
        
        # Тест: Читання вузла
        print("\n📖 Тест: Читання вузла...")
        query = "MATCH (n:TestNode {name: 'test'}) RETURN n.name AS name, n.value AS value"
        result = graph.query(query)
        print(f"✅ Вузол знайдено: {result.result_set}")
        
        # Тест: Видалення тестових даних
        print("\n🗑️  Тест: Видалення тестових даних...")
        query = "MATCH (n:TestNode) DELETE n"
        graph.query(query)
        print(f"✅ Тестові дані видалено")
        
        print("\n✅ Всі тести пройшли успішно!")
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
    print("🧪 Тестування підключення до FalkorDB")
    print("=" * 60)
    
    success = test_connection(host, port, password, graph_name)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
