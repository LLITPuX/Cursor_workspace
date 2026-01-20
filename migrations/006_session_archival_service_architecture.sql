-- Migration: Session Archival Service Architecture
-- Date: 2026-01-16
-- Description: Збереження архітектури нового сервису архівації сесій

-- 1. Створюємо Protocol для архітектури сервису архівації
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'SessionArchivalServiceProtocol',
    'Protocol',
    'Протокол для повноцінної архівації сесій та автоматичного витягування релевантного контексту. Сервис зберігає ВСЮ інформацію сесії без сумаризації, а при запиті повертає структурований контекст з сумаризацією історії, правилами, інструкціями та протоколами для застосування.',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- 2. Створюємо Instruction для кожного блоку системи

-- Блок 1: API Gateway
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'APIGatewayBlockInstruction',
    'Instruction',
    'Блок API Gateway: Прийом HTTP запитів, маршрутизація, валідація вхідних даних, формування відповідей. Відповідає за зовнішній інтерфейс сервису.',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- Блок 2: Архіватор
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'ArchiverBlockInstruction',
    'Instruction',
    'Блок Архіватор: Збереження повідомлень (повний текст без сумаризації), генерація embeddings, управління сесіями, створення зв''язків між сутностями. Відповідає за повне збереження всієї інформації.',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- Блок 3: Аналізатор контексту
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'ContextAnalyzerBlockInstruction',
    'Instruction',
    'Блок Аналізатор контексту: Векторний пошук в історії сесій, визначення релевантних правил/інструкцій, визначення протоколів за тригерами, побудова графу зв''язків. Відповідає за аналіз та витягування релевантної інформації.',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- Блок 4: Генератор сумаризації
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'SummaryGeneratorBlockInstruction',
    'Instruction',
    'Блок Генератор сумаризації: Аналіз історії сесії, створення структурованої сумаризації, додавання посилань на конкретні повідомлення (message_id), визначення ключових тем. Відповідає за створення читабельної сумаризації з референсами.',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- Блок 5: Менеджер правил
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'RuleManagerBlockInstruction',
    'Instruction',
    'Блок Менеджер правил: Завантаження критичних правил, пошук релевантних правил через векторний пошук, навігація по графу правил, визначення залежностей між правилами, пріоритизація правил. Відповідає за роботу з правилами системи.',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- Блок 6: Менеджер протоколів
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'ProtocolManagerBlockInstruction',
    'Instruction',
    'Блок Менеджер протоколів: Визначення протоколів за тригерами, завантаження інструкцій протоколу, визначення послідовності виконання, відстеження виконання протоколів. Відповідає за роботу з протоколами системи.',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- 3. Створюємо Instruction для кожного модуля

-- Модуль 1: Database Layer
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'DatabaseLayerModuleInstruction',
    'Instruction',
    'Модуль Database Layer: Підключення до Neon PostgreSQL, CRUD операції для sessions/messages, робота з entity_nodes/entity_edges, векторний пошук (pgvector), транзакції та безпека. Відповідає за всі операції з базою даних.',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- Модуль 2: Embedding Service
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'EmbeddingServiceModuleInstruction',
    'Instruction',
    'Модуль Embedding Service: Інтеграція з Ollama (або embedding-service як fallback), генерація embeddings, batch обробка, кешування embeddings. Відповідає за генерацію векторних представлень тексту.',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- Модуль 3: Vector Search Engine
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'VectorSearchEngineModuleInstruction',
    'Instruction',
    'Модуль Vector Search Engine: Пошук в messages (по session_id, role, similarity), пошук в entity_nodes (по type, similarity), гібридний пошук (векторний + ключові слова), ранжування результатів. Відповідає за векторний пошук релевантної інформації.',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- Модуль 4: Context Builder
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'ContextBuilderModuleInstruction',
    'Instruction',
    'Модуль Context Builder: Агрегація результатів пошуку, побудова хронології повідомлень, визначення релевантності, формування структурованого контексту. Відповідає за побудову контексту з різних джерел.',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- Модуль 5: Summary Generator
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'SummaryGeneratorModuleInstruction',
    'Instruction',
    'Модуль Summary Generator: Аналіз історії сесії, витяг ключових моментів, створення структурованої сумаризації, додавання посилань на message_id. Відповідає за генерацію сумаризації з референсами.',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- Модуль 6: Rule Matcher
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'RuleMatcherModuleInstruction',
    'Instruction',
    'Модуль Rule Matcher: Векторний пошук правил, аналіз зв''язків через entity_edges, визначення залежностей, пріоритизація правил. Відповідає за знаходження релевантних правил для застосування.',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- Модуль 7: Protocol Detector
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'ProtocolDetectorModuleInstruction',
    'Instruction',
    'Модуль Protocol Detector: Аналіз тригерів з protocol_triggers, визначення протоколів за контекстом, завантаження інструкцій протоколу, визначення послідовності виконання. Відповідає за визначення протоколів для виконання.',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- Модуль 8: Link Manager
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'LinkManagerModuleInstruction',
    'Instruction',
    'Модуль Link Manager: Створення message_entity_links, створення session_entity_links, відстеження використання правил, оновлення метаданих. Відповідає за створення зв''язків між повідомленнями та правилами/інструкціями.',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- 4. Створюємо зв'язки: Protocol містить всі блоки
DO $$
DECLARE
    v_protocol_id UUID;
    block_ids UUID[];
BEGIN
    -- Знаходимо Protocol
    SELECT id INTO v_protocol_id
    FROM entity_nodes
    WHERE name = 'SessionArchivalServiceProtocol'
    AND type = 'Protocol'
    AND valid_to IS NULL;
    
    -- Знаходимо всі блоки
    SELECT ARRAY_AGG(id) INTO block_ids
    FROM entity_nodes
    WHERE type = 'Instruction'
    AND name IN (
        'APIGatewayBlockInstruction',
        'ArchiverBlockInstruction',
        'ContextAnalyzerBlockInstruction',
        'SummaryGeneratorBlockInstruction',
        'RuleManagerBlockInstruction',
        'ProtocolManagerBlockInstruction'
    )
    AND valid_to IS NULL;
    
    -- Створюємо зв'язки
    IF v_protocol_id IS NOT NULL AND block_ids IS NOT NULL THEN
        INSERT INTO entity_edges (source_id, target_id, relation_type, valid_from, valid_to)
        SELECT v_protocol_id, block_id, 'contains', NOW(), NULL
        FROM UNNEST(block_ids) AS block_id
        ON CONFLICT (source_id, target_id, relation_type) DO UPDATE
        SET valid_to = NULL
        WHERE entity_edges.valid_to IS NOT NULL;
    END IF;
END $$;

-- 5. Створюємо зв'язки: Блоки містять модулі
DO $$
DECLARE
    archiver_id UUID;
    analyzer_id UUID;
    summary_id UUID;
    rule_manager_id UUID;
    protocol_manager_id UUID;
    module_ids UUID[];
BEGIN
    -- Знаходимо блоки
    SELECT id INTO archiver_id FROM entity_nodes WHERE name = 'ArchiverBlockInstruction' AND valid_to IS NULL;
    SELECT id INTO analyzer_id FROM entity_nodes WHERE name = 'ContextAnalyzerBlockInstruction' AND valid_to IS NULL;
    SELECT id INTO summary_id FROM entity_nodes WHERE name = 'SummaryGeneratorBlockInstruction' AND valid_to IS NULL;
    SELECT id INTO rule_manager_id FROM entity_nodes WHERE name = 'RuleManagerBlockInstruction' AND valid_to IS NULL;
    SELECT id INTO protocol_manager_id FROM entity_nodes WHERE name = 'ProtocolManagerBlockInstruction' AND valid_to IS NULL;
    
    -- Архіватор містить: Database Layer, Embedding Service, Link Manager
    SELECT ARRAY_AGG(id) INTO module_ids
    FROM entity_nodes
    WHERE name IN ('DatabaseLayerModuleInstruction', 'EmbeddingServiceModuleInstruction', 'LinkManagerModuleInstruction')
    AND valid_to IS NULL;
    
    IF archiver_id IS NOT NULL AND module_ids IS NOT NULL THEN
        INSERT INTO entity_edges (source_id, target_id, relation_type, valid_from, valid_to)
        SELECT archiver_id, module_id, 'contains', NOW(), NULL
        FROM UNNEST(module_ids) AS module_id
        ON CONFLICT (source_id, target_id, relation_type) DO UPDATE
        SET valid_to = NULL
        WHERE entity_edges.valid_to IS NOT NULL;
    END IF;
    
    -- Аналізатор містить: Vector Search Engine, Context Builder, Rule Matcher, Protocol Detector
    SELECT ARRAY_AGG(id) INTO module_ids
    FROM entity_nodes
    WHERE name IN ('VectorSearchEngineModuleInstruction', 'ContextBuilderModuleInstruction', 'RuleMatcherModuleInstruction', 'ProtocolDetectorModuleInstruction')
    AND valid_to IS NULL;
    
    IF analyzer_id IS NOT NULL AND module_ids IS NOT NULL THEN
        INSERT INTO entity_edges (source_id, target_id, relation_type, valid_from, valid_to)
        SELECT analyzer_id, module_id, 'contains', NOW(), NULL
        FROM UNNEST(module_ids) AS module_id
        ON CONFLICT (source_id, target_id, relation_type) DO UPDATE
        SET valid_to = NULL
        WHERE entity_edges.valid_to IS NOT NULL;
    END IF;
    
    -- Генератор сумаризації містить: Summary Generator
    SELECT ARRAY_AGG(id) INTO module_ids
    FROM entity_nodes
    WHERE name = 'SummaryGeneratorModuleInstruction'
    AND valid_to IS NULL;
    
    IF summary_id IS NOT NULL AND module_ids IS NOT NULL THEN
        INSERT INTO entity_edges (source_id, target_id, relation_type, valid_from, valid_to)
        SELECT summary_id, module_id, 'contains', NOW(), NULL
        FROM UNNEST(module_ids) AS module_id
        ON CONFLICT (source_id, target_id, relation_type) DO UPDATE
        SET valid_to = NULL
        WHERE entity_edges.valid_to IS NOT NULL;
    END IF;
    
    -- Менеджер правил містить: Rule Matcher
    SELECT ARRAY_AGG(id) INTO module_ids
    FROM entity_nodes
    WHERE name = 'RuleMatcherModuleInstruction'
    AND valid_to IS NULL;
    
    IF rule_manager_id IS NOT NULL AND module_ids IS NOT NULL THEN
        INSERT INTO entity_edges (source_id, target_id, relation_type, valid_from, valid_to)
        SELECT rule_manager_id, module_id, 'contains', NOW(), NULL
        FROM UNNEST(module_ids) AS module_id
        ON CONFLICT (source_id, target_id, relation_type) DO UPDATE
        SET valid_to = NULL
        WHERE entity_edges.valid_to IS NOT NULL;
    END IF;
    
    -- Менеджер протоколів містить: Protocol Detector
    SELECT ARRAY_AGG(id) INTO module_ids
    FROM entity_nodes
    WHERE name = 'ProtocolDetectorModuleInstruction'
    AND valid_to IS NULL;
    
    IF protocol_manager_id IS NOT NULL AND module_ids IS NOT NULL THEN
        INSERT INTO entity_edges (source_id, target_id, relation_type, valid_from, valid_to)
        SELECT protocol_manager_id, module_id, 'contains', NOW(), NULL
        FROM UNNEST(module_ids) AS module_id
        ON CONFLICT (source_id, target_id, relation_type) DO UPDATE
        SET valid_to = NULL
        WHERE entity_edges.valid_to IS NOT NULL;
    END IF;
END $$;

-- 6. Створюємо детальний опис етапів роботи як окрему сутність
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'SessionArchivalWorkflowStages',
    'Instruction',
    'Етапи роботи сервису архівації:
1. Прийом запиту: Отримання запиту від AI агента, валідація формату, визначення контексту
2. Архівація (синхронна): Збереження запиту в БД (повний текст), генерація embedding, створення/оновлення сесії, зв''язки з правилами
3. Аналіз та контекст: Векторний пошук в історії, визначення релевантних правил/інструкцій/протоколів, побудова контексту з посиланнями, генерація сумаризації
4. Формування відповіді: Структура з сумаризацією історії, списком правил/інструкцій/протоколів, релевантними повідомленнями
5. Збереження відповіді: Збереження відповіді AI агента, генерація embedding, створення зв''язків, оновлення метаданих',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- 7. Зв'язуємо workflow з протоколом
DO $$
DECLARE
    v_protocol_id UUID;
    workflow_id UUID;
BEGIN
    SELECT id INTO v_protocol_id FROM entity_nodes WHERE name = 'SessionArchivalServiceProtocol' AND valid_to IS NULL;
    SELECT id INTO workflow_id FROM entity_nodes WHERE name = 'SessionArchivalWorkflowStages' AND valid_to IS NULL;
    
    IF v_protocol_id IS NOT NULL AND workflow_id IS NOT NULL THEN
        INSERT INTO entity_edges (source_id, target_id, relation_type, valid_from, valid_to)
        VALUES (v_protocol_id, workflow_id, 'contains', NOW(), NULL)
        ON CONFLICT (source_id, target_id, relation_type) DO UPDATE
        SET valid_to = NULL
        WHERE entity_edges.valid_to IS NOT NULL;
    END IF;
END $$;

-- 8. Створюємо опис структури відповіді сервису
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'SessionArchivalResponseStructure',
    'Instruction',
    'Структура відповіді сервису архівації:
{
  "session_id": "uuid",
  "summary": {
    "text": "Сумаризація історії обговорення...",
    "key_topics": ["тема1", "тема2"],
    "message_references": [{"message_id": "uuid", "role": "user", "excerpt": "фрагмент", "relevance_score": 0.95}]
  },
  "rules_to_apply": [{"rule_id": "uuid", "rule_name": "...", "description": "...", "relevance_score": 0.92}],
  "instructions_to_apply": [{"instruction_id": "uuid", "instruction_name": "...", "description": "...", "related_rules": [...], "relevance_score": 0.88}],
  "protocols_to_execute": [{"protocol_id": "uuid", "protocol_name": "...", "description": "...", "instructions": [...], "trigger_match": "..."}],
  "relevant_history": [{"message_id": "uuid", "session_id": "uuid", "role": "user|assistant", "content": "повний текст", "created_at": "timestamp", "similarity_score": 0.85}]
}',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- 9. Зв'язуємо структуру відповіді з протоколом
DO $$
DECLARE
    v_protocol_id UUID;
    response_structure_id UUID;
BEGIN
    SELECT id INTO v_protocol_id FROM entity_nodes WHERE name = 'SessionArchivalServiceProtocol' AND valid_to IS NULL;
    SELECT id INTO response_structure_id FROM entity_nodes WHERE name = 'SessionArchivalResponseStructure' AND valid_to IS NULL;
    
    IF v_protocol_id IS NOT NULL AND response_structure_id IS NOT NULL THEN
        INSERT INTO entity_edges (source_id, target_id, relation_type, valid_from, valid_to)
        VALUES (v_protocol_id, response_structure_id, 'contains', NOW(), NULL)
        ON CONFLICT (source_id, target_id, relation_type) DO UPDATE
        SET valid_to = NULL
        WHERE entity_edges.valid_to IS NOT NULL;
    END IF;
END $$;

-- 10. Створюємо опис ключових принципів
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'SessionArchivalKeyPrinciples',
    'Rule',
    'Ключові принципи сервису архівації:
1. Append-Only: Все зберігається, нічого не видаляється
2. Повнота: Зберігається весь текст, без сумаризації при збереженні
3. Референсність: Кожна сумаризація містить посилання на конкретні message_id
4. Автоматичність: Автоматичне збереження та аналіз
5. Модульність: Кожен модуль виконує одну функцію
6. Масштабованість: Підтримка великих обсягів даних',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- 11. Зв'язуємо принципи з протоколом
DO $$
DECLARE
    v_protocol_id UUID;
    principles_id UUID;
BEGIN
    SELECT id INTO v_protocol_id FROM entity_nodes WHERE name = 'SessionArchivalServiceProtocol' AND valid_to IS NULL;
    SELECT id INTO principles_id FROM entity_nodes WHERE name = 'SessionArchivalKeyPrinciples' AND valid_to IS NULL;
    
    IF v_protocol_id IS NOT NULL AND principles_id IS NOT NULL THEN
        INSERT INTO entity_edges (source_id, target_id, relation_type, valid_from, valid_to)
        VALUES (v_protocol_id, principles_id, 'uses', NOW(), NULL)
        ON CONFLICT (source_id, target_id, relation_type) DO UPDATE
        SET valid_to = NULL
        WHERE entity_edges.valid_to IS NOT NULL;
    END IF;
END $$;

-- 12. Створюємо тригер для протоколу
DO $$
DECLARE
    v_protocol_id UUID;
BEGIN
    SELECT id INTO v_protocol_id FROM entity_nodes WHERE name = 'SessionArchivalServiceProtocol' AND valid_to IS NULL;
    
    IF v_protocol_id IS NOT NULL THEN
        INSERT INTO protocol_triggers (protocol_id, trigger_examples, context_description, valid_from, valid_to)
        VALUES (
            v_protocol_id,
            ARRAY[
                'архівація сесії',
                'збереження сесії',
                'архівація',
                'session archival',
                'archive session',
                'зберегти сесію',
                'архівувати сесію',
                'сервис архівації',
                'session archival service',
                'новий сервис архівації'
            ],
            'Тригер для протоколу архівації сесій. Активується при згадці про архівацію, збереження сесій або створення нового сервису архівації.',
            NOW(),
            NULL
        )
        ON CONFLICT (protocol_id) DO UPDATE
        SET trigger_examples = EXCLUDED.trigger_examples,
            context_description = EXCLUDED.context_description,
            valid_to = NULL
        WHERE protocol_triggers.valid_to IS NOT NULL;
    END IF;
END $$;

-- 13. Записуємо міграцію
SELECT record_migration('006', 'session_archival_service_architecture', 'Збереження архітектури нового сервису архівації сесій');
