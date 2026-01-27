#!/usr/bin/env python3
"""
Універсальний CLI для команди /db.
Працює в двох режимах:
- Інгестія: коли на вході файл (парсинг → збереження в граф)
- Пошук: коли на вході текстовий запит (векторний пошук + Cypher)
"""

import os
import sys
import argparse
import asyncio
from pathlib import Path

# Додаємо scripts до шляху для імпорту ingest_session
sys.path.insert(0, str(Path(__file__).parent))

from ingest_session import ingest_session_file
from search_memory import search_memory


def main():
    """Головна функція CLI."""
    parser = argparse.ArgumentParser(
        description="Універсальний CLI для роботи з FalkorDB пам'яттю",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Приклади використання:
  # Інгестія файлу сесії
  python scripts/db_cli.py saved_sessions/session_2026-01-20_falkordb_planning.md
  
  # Пошук в графі
  python scripts/db_cli.py "Яка була стратегія міграції?"
        """
    )
    
    parser.add_argument(
        "input",
        help="Шлях до файлу для інгестії або текстовий запит для пошуку"
    )
    
    parser.add_argument(
        "--graph-name",
        default=os.getenv("FALKORDB_GRAPH_NAME", "agent_memory"),
        help="Назва графу в FalkorDB (за замовчуванням: agent_memory)"
    )
    
    parser.add_argument(
        "--falkordb-host",
        default=os.getenv("FALKORDB_HOST", "localhost"),
        help="Хост FalkorDB (за замовчуванням: localhost)"
    )
    
    parser.add_argument(
        "--falkordb-port",
        type=int,
        default=int(os.getenv("FALKORDB_PORT", "6379")),
        help="Порт FalkorDB (за замовчуванням: 6379)"
    )
    
    parser.add_argument(
        "--qpe-url",
        default=os.getenv("QPE_URL", "http://localhost:8001"),
        help="URL QPE Service (за замовчуванням: http://localhost:8001)"
    )
    
    args = parser.parse_args()
    
    # Перевірка чи це файл
    input_path = Path(args.input)
    
    if input_path.is_file():
        print(f"📂 Виявлено файл: {args.input}")
        print("🚀 Запуск процесу інгестії...")
        try:
            asyncio.run(ingest_session_file(
                file_path=str(input_path),
                graph_name=args.graph_name,
                falkordb_host=args.falkordb_host,
                falkordb_port=args.falkordb_port,
                qpe_url=args.qpe_url
            ))
            print("✅ Інгестія завершена успішно!")
            return 0
        except Exception as e:
            print(f"❌ Помилка під час інгестії: {e}")
            import traceback
            traceback.print_exc()
            return 1
    else:
        print(f"🔍 Виявлено запит: {args.input}")
        print("🧠 Пошук в Knowledge Graph...")
        try:
            results = search_memory(
                query=args.input,
                graph_name=args.graph_name,
                falkordb_host=args.falkordb_host,
                falkordb_port=args.falkordb_port,
                qpe_url=args.qpe_url
            )
            print("\n📊 Результати пошуку:")
            print(results)
            return 0
        except Exception as e:
            print(f"❌ Помилка під час пошуку: {e}")
            import traceback
            traceback.print_exc()
            return 1


if __name__ == "__main__":
    sys.exit(main())
