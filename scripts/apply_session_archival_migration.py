#!/usr/bin/env python3
"""
Скрипт для застосування міграції архітектури сервису архівації сесій.
Виконує міграцію 006_session_archival_service_architecture.sql
"""
import os
import sys
import asyncio
import asyncpg
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def apply_migration(connection_string: str):
    """Застосувати міграцію архітектури сервису архівації."""
    conn = None
    try:
        logger.info("Підключення до бази даних...")
        conn = await asyncpg.connect(connection_string)
        
        # Читаємо міграцію
        migration_file = Path(__file__).parent.parent / "migrations" / "006_session_archival_service_architecture.sql"
        if not migration_file.exists():
            logger.error(f"Файл міграції не знайдено: {migration_file}")
            return False
        
        logger.info(f"Читаю міграцію з {migration_file}")
        migration_sql = migration_file.read_text(encoding='utf-8')
        
        # Виконуємо міграцію в транзакції
        logger.info("Виконую міграцію...")
        async with conn.transaction():
            await conn.execute(migration_sql)
        
        logger.info("✓ Міграція успішно застосована!")
        return True
        
    except Exception as e:
        logger.error(f"✗ Помилка при застосуванні міграції: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            await conn.close()


def main():
    """Головна функція."""
    # Отримуємо connection string
    connection_string = os.getenv("NEON_CONNECTION_STRING")
    
    if not connection_string:
        logger.error(
            "NEON_CONNECTION_STRING не встановлено. "
            "Встановіть змінну оточення або передайте через аргумент."
        )
        logger.info("Приклад: $env:NEON_CONNECTION_STRING='postgresql://...'")
        return 1
    
    # Застосовуємо міграцію
    success = asyncio.run(apply_migration(connection_string))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
