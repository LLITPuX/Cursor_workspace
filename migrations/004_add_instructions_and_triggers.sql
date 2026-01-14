-- Migration: Add Instructions and Protocol Triggers
-- Date: 2026-01-14
-- Description: Creates base instructions and protocol triggers for the knowledge graph

-- 1. Create Instruction: VectorSearchInstruction
-- This instruction describes how to perform vector search for RAG
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'VectorSearchInstruction',
    'Instruction',
    'Виконай векторний пошук в Neon для знаходження релевантної інформації: 1) Генеруй embedding для запиту через embedding-service, 2) Шукай в entity_nodes (тип: Instruction, Protocol, Fact) з фільтром по типу, 3) Шукай в messages (історія сесій) з фільтром по session_id/role, 4) Використовуй similarity_threshold для фільтрації результатів, 5) Повертай топ-N найбільш релевантних результатів з similarity scores',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- 2. Create Instruction: LoadCriticalRulesInstruction
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'LoadCriticalRulesInstruction',
    'Instruction',
    'При першому запиті до бази завантаж критичні правила: 1) Знайди вузол CriticalRules (type: SystemNode), 2) Завантаж всі правила через entity_edges (relation_type: contains), 3) Кешуй правила в контексті сесії, 4) Застосовуй правила автоматично при роботі',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- 3. Create Instruction: SaveSessionInstruction
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'SaveSessionInstruction',
    'Instruction',
    'Після формування відповіді збережи сесію: 1) Створи/онови запис в sessions, 2) Збережи повідомлення в messages з embedding_v2, 3) Створи зв''язки через message_entity_links з використаними правилами/інструкціями (uses, applies), 4) Створи зв''язки через session_entity_links з протоколами (executed_in)',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- 4. Create Instruction: EntityGraphNavigationInstruction
INSERT INTO entity_nodes (name, type, description, valid_from, valid_to)
VALUES (
    'EntityGraphNavigationInstruction',
    'Instruction',
    'Для навігації по графу знань: 1) Використовуй get_entity_children для отримання дочірніх сутностей, 2) Використовуй entity_edges для знаходження зв''язків між сутностями, 3) Фільтруй по relation_type (contains, uses, depends_on, applies_to), 4) Враховуй темпоральність (valid_to IS NULL для активних)',
    NOW(),
    NULL
)
ON CONFLICT (name, type) DO UPDATE
SET description = EXCLUDED.description,
    valid_to = NULL
WHERE entity_nodes.valid_to IS NOT NULL;

-- 5. Link Instructions to Bootstrap Protocol (if exists)
-- First, find Bootstrap Protocol
DO $$
DECLARE
    bootstrap_protocol_id UUID;
    instruction_ids UUID[];
BEGIN
    -- Find Bootstrap Protocol
    SELECT id INTO bootstrap_protocol_id
    FROM entity_nodes
    WHERE (name LIKE '%Bootstrap%' OR name LIKE '%Protocol%')
    AND type = 'Protocol'
    AND valid_to IS NULL
    ORDER BY created_at DESC
    LIMIT 1;
    
    -- If protocol exists, link instructions
    IF bootstrap_protocol_id IS NOT NULL THEN
        -- Get instruction IDs
        SELECT ARRAY_AGG(id) INTO instruction_ids
        FROM entity_nodes
        WHERE type = 'Instruction'
        AND name IN ('VectorSearchInstruction', 'LoadCriticalRulesInstruction', 'SaveSessionInstruction', 'EntityGraphNavigationInstruction')
        AND valid_to IS NULL;
        
        -- Create edges
        INSERT INTO entity_edges (source_id, target_id, relation_type, valid_from, valid_to)
        SELECT bootstrap_protocol_id, instruction_id, 'contains', NOW(), NULL
        FROM UNNEST(instruction_ids) AS instruction_id
        ON CONFLICT (source_id, target_id, relation_type) DO UPDATE
        SET valid_to = NULL
        WHERE entity_edges.valid_to IS NOT NULL;
    END IF;
END $$;

-- 6. Create Protocol Triggers
-- Find Bootstrap Protocol and create trigger
DO $$
DECLARE
    bootstrap_protocol_id UUID;
BEGIN
    -- Find Bootstrap Protocol
    SELECT id INTO bootstrap_protocol_id
    FROM entity_nodes
    WHERE (name LIKE '%Bootstrap%' OR name LIKE '%Protocol%')
    AND type = 'Protocol'
    AND valid_to IS NULL
    ORDER BY created_at DESC
    LIMIT 1;
    
    -- Create trigger if protocol exists
    IF bootstrap_protocol_id IS NOT NULL THEN
        INSERT INTO protocol_triggers (protocol_id, trigger_examples, context_description, valid_from, valid_to)
        VALUES (
            bootstrap_protocol_id,
            ARRAY[
                'завантаж правила',
                'завантаж критичні правила',
                'покажи правила',
                'які правила',
                'critical rules',
                'load rules',
                'bootstrap protocol'
            ],
            'Тригер для автоматичного завантаження критичних правил при першому запиті до бази даних або при явному запиті користувача',
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

-- 7. Link Instructions to Rules (uses relation)
-- Link VectorSearchInstruction to relevant rules
INSERT INTO entity_edges (source_id, target_id, relation_type, valid_from, valid_to)
SELECT 
    i.id,
    r.id,
    'uses',
    NOW(),
    NULL
FROM entity_nodes i
CROSS JOIN entity_nodes r
WHERE i.type = 'Instruction'
AND i.name = 'VectorSearchInstruction'
AND r.type = 'Rule'
AND r.name IN ('SourcePriority', 'VerifyBeforeAct')
AND i.valid_to IS NULL
AND r.valid_to IS NULL
ON CONFLICT (source_id, target_id, relation_type) DO UPDATE
SET valid_to = NULL
WHERE entity_edges.valid_to IS NOT NULL;

-- Link SaveSessionInstruction to SessionContextSave rule
INSERT INTO entity_edges (source_id, target_id, relation_type, valid_from, valid_to)
SELECT 
    i.id,
    r.id,
    'uses',
    NOW(),
    NULL
FROM entity_nodes i
CROSS JOIN entity_nodes r
WHERE i.type = 'Instruction'
AND i.name = 'SaveSessionInstruction'
AND r.type = 'Rule'
AND r.name = 'SessionContextSave'
AND i.valid_to IS NULL
AND r.valid_to IS NULL
ON CONFLICT (source_id, target_id, relation_type) DO UPDATE
SET valid_to = NULL
WHERE entity_edges.valid_to IS NOT NULL;

-- 8. Record migration
SELECT record_migration('004', 'add_instructions_and_triggers', 'Creates base instructions and protocol triggers');
