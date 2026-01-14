#!/usr/bin/env python3
"""
Seed script for initializing the knowledge graph with base rules, instructions, and protocols.

This script creates the foundational structure of the knowledge graph:
- CriticalRules system node
- Base rules
- Base instructions
- Bootstrap protocol with triggers

Usage:
    python scripts/seed_knowledge_graph.py [--connection-string CONN_STR] [--force]
    
Environment:
    NEON_CONNECTION_STRING - Database connection string (required unless --connection-string provided)
"""
import os
import sys
import asyncio
import asyncpg
import argparse
import logging
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


BASE_RULES = [
    {
        "name": "AppendOnlyPrinciple",
        "description": "Ніколи не видаляй дані з бази даних. Використовуй valid_to для архівації. DELETE заборонено для всіх таблиць, крім технічного очищення (якщо явно дозволено). Гарантує повну історію та можливість відновлення."
    },
    {
        "name": "EntityRelationships",
        "description": "При створенні/використанні правил, інструкцій, протоколів — завжди створюй зв'язки через entity_edges. Це дозволяє відстежувати залежності та використання. Підтримує структуру Графу Знань."
    },
    {
        "name": "ProjectBranching",
        "description": "Нові проекти = нові гілки в Neon. Не засмічуй main гілку специфічними даними проекту. Використовуй create_branch для ізоляції. Зберігає порядок та ізоляцію між проектами."
    },
    {
        "name": "SessionContextSave",
        "description": "Після формування відповіді зберігай повідомлення в messages з embedding та створюй зв'язки через message_entity_links з використаними правилами/інструкціями (uses, applies, executed_in). Дозволяє RAG пошук та відстеження використання правил."
    },
    {
        "name": "SourcePriority",
        "description": "Пріоритет джерел: 1) entity_nodes в базі Neon (актуальна істина), 2) Код проекту (факти реалізації), 3) Зовнішні знання (потребує верифікації). Забезпечує використання найбільш актуальної інформації."
    },
    {
        "name": "TemporalFacts",
        "description": "Усі факти в entity_nodes мають valid_from та valid_to. При зміні факту: закрий старий (valid_to = NOW()) і створ новий (valid_from = NOW(), valid_to = NULL) в одній транзакції. Дозволяє відстежувати історію змін та знати актуальний стан."
    },
    {
        "name": "UseExistingTools",
        "description": "Перед створенням нового скрипта, файлу або інструменту - завжди перевіряй наявність існуючих рішень. Використовуй API endpoints, CLI інструменти або існуючі скрипти замість створення дублікатів. Створюй нові інструменти лише якщо: 1) їх немає, 2) існуючі не підходять для задачі, 3) потрібна універсалізація застарілих рішень. Зменшує дублювання коду та підтримує порядок в проекті."
    },
    {
        "name": "VerifyBeforeAct",
        "description": "Перед згадуванням файлу/функції/факту — перевір його існування через read_file, grep, codebase_search або SQL запити. Якщо не впевнений — скажи це прямо, не вигадуй. Зменшує галюцинації та помилки."
    }
]

BASE_INSTRUCTIONS = [
    {
        "name": "VectorSearchInstruction",
        "description": "Виконай векторний пошук в Neon для знаходження релевантної інформації: 1) Генеруй embedding для запиту через embedding-service, 2) Шукай в entity_nodes (тип: Instruction, Protocol, Fact) з фільтром по типу, 3) Шукай в messages (історія сесій) з фільтром по session_id/role, 4) Використовуй similarity_threshold для фільтрації результатів, 5) Повертай топ-N найбільш релевантних результатів з similarity scores"
    },
    {
        "name": "LoadCriticalRulesInstruction",
        "description": "При першому запиті до бази завантаж критичні правила: 1) Знайди вузол CriticalRules (type: SystemNode), 2) Завантаж всі правила через entity_edges (relation_type: contains), 3) Кешуй правила в контексті сесії, 4) Застосовуй правила автоматично при роботі"
    },
    {
        "name": "SaveSessionInstruction",
        "description": "Після формування відповіді збережи сесію: 1) Створи/онови запис в sessions, 2) Збережи повідомлення в messages з embedding_v2, 3) Створи зв'язки через message_entity_links з використаними правилами/інструкціями (uses, applies), 4) Створи зв'язки через session_entity_links з протоколами (executed_in)"
    },
    {
        "name": "EntityGraphNavigationInstruction",
        "description": "Для навігації по графу знань: 1) Використовуй get_entity_children для отримання дочірніх сутностей, 2) Використовуй entity_edges для знаходження зв'язків між сутностями, 3) Фільтруй по relation_type (contains, uses, depends_on, applies_to), 4) Враховуй темпоральність (valid_to IS NULL для активних)"
    }
]

PROTOCOL_TRIGGERS = [
    "завантаж правила",
    "завантаж критичні правила",
    "покажи правила",
    "які правила",
    "critical rules",
    "load rules",
    "bootstrap protocol"
]


async def seed_knowledge_graph(
    connection_string: str,
    force: bool = False
) -> int:
    """Seed the knowledge graph with base data."""
    conn = None
    try:
        logger.info("Connecting to database...")
        conn = await asyncpg.connect(connection_string)
        
        async with conn.transaction():
            # 1. Create or get CriticalRules system node
            logger.info("Creating CriticalRules system node...")
            critical_rules_id = await conn.fetchval("""
                SELECT id FROM entity_nodes
                WHERE name = 'CriticalRules' AND type = 'SystemNode' AND valid_to IS NULL
                LIMIT 1
            """)
            
            if not critical_rules_id:
                critical_rules_id = await conn.fetchval("""
                    INSERT INTO entity_nodes (name, type, description)
                    VALUES ('CriticalRules', 'SystemNode', 
                        'Системний вузол для зберігання списку критичних правил. Правила пов''язані через entity_edges з relation_type ''contains''.')
                    RETURNING id
                """)
                logger.info(f"Created CriticalRules node: {critical_rules_id}")
            else:
                logger.info(f"CriticalRules node already exists: {critical_rules_id}")
                if not force:
                    logger.warning("Use --force to recreate existing entities")
            
            # 2. Create base rules
            logger.info("Creating base rules...")
            rule_ids = {}
            for rule in BASE_RULES:
                existing_id = await conn.fetchval("""
                    SELECT id FROM entity_nodes
                    WHERE name = $1 AND type = 'Rule' AND valid_to IS NULL
                    LIMIT 1
                """, rule["name"])
                
                if existing_id:
                    logger.info(f"  Rule '{rule['name']}' already exists")
                    rule_ids[rule["name"]] = existing_id
                else:
                    rule_id = await conn.fetchval("""
                        INSERT INTO entity_nodes (name, type, description)
                        VALUES ($1, 'Rule', $2)
                        RETURNING id
                    """, rule["name"], rule["description"])
                    rule_ids[rule["name"]] = rule_id
                    logger.info(f"  Created rule '{rule['name']}': {rule_id}")
                    
                    # Link to CriticalRules
                    await conn.execute("""
                        INSERT INTO entity_edges (source_id, target_id, relation_type)
                        VALUES ($1, $2, 'contains')
                        ON CONFLICT (source_id, target_id, relation_type) DO NOTHING
                    """, critical_rules_id, rule_id)
            
            # 3. Create base instructions
            logger.info("Creating base instructions...")
            instruction_ids = {}
            for instruction in BASE_INSTRUCTIONS:
                existing_id = await conn.fetchval("""
                    SELECT id FROM entity_nodes
                    WHERE name = $1 AND type = 'Instruction' AND valid_to IS NULL
                    LIMIT 1
                """, instruction["name"])
                
                if existing_id:
                    logger.info(f"  Instruction '{instruction['name']}' already exists")
                    instruction_ids[instruction["name"]] = existing_id
                else:
                    instruction_id = await conn.fetchval("""
                        INSERT INTO entity_nodes (name, type, description)
                        VALUES ($1, 'Instruction', $2)
                        RETURNING id
                    """, instruction["name"], instruction["description"])
                    instruction_ids[instruction["name"]] = instruction_id
                    logger.info(f"  Created instruction '{instruction['name']}': {instruction_id}")
            
            # Link instructions to rules
            logger.info("Linking instructions to rules...")
            # VectorSearchInstruction uses SourcePriority and VerifyBeforeAct
            if "VectorSearchInstruction" in instruction_ids:
                for rule_name in ["SourcePriority", "VerifyBeforeAct"]:
                    if rule_name in rule_ids:
                        await conn.execute("""
                            INSERT INTO entity_edges (source_id, target_id, relation_type)
                            VALUES ($1, $2, 'uses')
                            ON CONFLICT (source_id, target_id, relation_type) DO NOTHING
                        """, instruction_ids["VectorSearchInstruction"], rule_ids[rule_name])
            
            # SaveSessionInstruction uses SessionContextSave
            if "SaveSessionInstruction" in instruction_ids and "SessionContextSave" in rule_ids:
                await conn.execute("""
                    INSERT INTO entity_edges (source_id, target_id, relation_type)
                    VALUES ($1, $2, 'uses')
                    ON CONFLICT (source_id, target_id, relation_type) DO NOTHING
                """, instruction_ids["SaveSessionInstruction"], rule_ids["SessionContextSave"])
            
            # 4. Create Bootstrap Protocol
            logger.info("Creating Bootstrap Protocol...")
            bootstrap_protocol_id = await conn.fetchval("""
                SELECT id FROM entity_nodes
                WHERE name LIKE '%Bootstrap%' AND type = 'Protocol' AND valid_to IS NULL
                LIMIT 1
            """)
            
            if not bootstrap_protocol_id:
                bootstrap_protocol_id = await conn.fetchval("""
                    INSERT INTO entity_nodes (name, type, description)
                    VALUES ('BootstrapProtocol', 'Protocol', 
                        'Протокол для завантаження критичних правил та ініціалізації системи пам''яті')
                    RETURNING id
                """)
                logger.info(f"Created Bootstrap Protocol: {bootstrap_protocol_id}")
            else:
                logger.info(f"Bootstrap Protocol already exists: {bootstrap_protocol_id}")
            
            # Link instructions to protocol
            logger.info("Linking instructions to Bootstrap Protocol...")
            for instruction_name, instruction_id in instruction_ids.items():
                await conn.execute("""
                    INSERT INTO entity_edges (source_id, target_id, relation_type)
                    VALUES ($1, $2, 'contains')
                    ON CONFLICT (source_id, target_id, relation_type) DO NOTHING
                """, bootstrap_protocol_id, instruction_id)
            
            # 5. Create protocol triggers
            logger.info("Creating protocol triggers...")
            await conn.execute("""
                INSERT INTO protocol_triggers (protocol_id, trigger_examples, context_description)
                VALUES ($1, $2, $3)
                ON CONFLICT (protocol_id) DO UPDATE
                SET trigger_examples = EXCLUDED.trigger_examples,
                    context_description = EXCLUDED.context_description,
                    valid_to = NULL
                WHERE protocol_triggers.valid_to IS NOT NULL
            """, bootstrap_protocol_id, PROTOCOL_TRIGGERS, 
                "Тригер для автоматичного завантаження критичних правил при першому запиті до бази даних або при явному запиті користувача")
            
            logger.info("✓ Knowledge graph seeded successfully!")
            return 0
            
    except Exception as e:
        logger.error(f"Error seeding knowledge graph: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if conn:
            await conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed knowledge graph with base data",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--connection-string",
        help="Database connection string (overrides NEON_CONNECTION_STRING)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force recreation of existing entities (not implemented)"
    )
    
    args = parser.parse_args()
    
    # Get connection string
    connection_string = args.connection_string or os.getenv("NEON_CONNECTION_STRING")
    if not connection_string:
        logger.error(
            "Connection string required. "
            "Set NEON_CONNECTION_STRING env var or use --connection-string"
        )
        return 1
    
    # Run seeding
    return asyncio.run(seed_knowledge_graph(connection_string, args.force))


if __name__ == "__main__":
    sys.exit(main())
