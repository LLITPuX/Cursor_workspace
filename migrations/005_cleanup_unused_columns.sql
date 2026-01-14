-- Migration: Cleanup Unused Columns
-- Date: 2026-01-14
-- Description: Removes unused embedding column (1536d) since we're using embedding_v2 (768d)

-- Note: This migration is optional and can be skipped if you want to keep old columns
-- for backward compatibility or data migration purposes.

-- 1. Check if old embedding column has any data
DO $$
DECLARE
    messages_with_old_embedding INTEGER;
    nodes_with_old_embedding INTEGER;
BEGIN
    -- Count messages with old embedding
    SELECT COUNT(*) INTO messages_with_old_embedding
    FROM messages
    WHERE embedding IS NOT NULL;
    
    -- Count nodes with old embedding
    SELECT COUNT(*) INTO nodes_with_old_embedding
    FROM entity_nodes
    WHERE embedding IS NOT NULL;
    
    -- Log warning if data exists
    IF messages_with_old_embedding > 0 OR nodes_with_old_embedding > 0 THEN
        RAISE NOTICE 'Found % messages and % nodes with old embedding. Consider migrating data first.', 
            messages_with_old_embedding, nodes_with_old_embedding;
    END IF;
END $$;

-- 2. Drop old indexes on embedding column (if they exist)
DROP INDEX IF EXISTS idx_messages_embedding;
DROP INDEX IF EXISTS idx_nodes_embedding;

-- 3. Drop old embedding columns (commented out for safety - uncomment if you're sure)
-- Uncomment these lines only after verifying no data needs to be migrated:
-- ALTER TABLE messages DROP COLUMN IF EXISTS embedding;
-- ALTER TABLE entity_nodes DROP COLUMN IF EXISTS embedding;

-- 4. Record migration
SELECT record_migration('005', 'cleanup_unused_columns', 'Removes unused embedding columns (commented out for safety)');
