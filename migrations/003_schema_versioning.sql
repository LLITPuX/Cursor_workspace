-- Migration: Schema Versioning System
-- Date: 2026-01-14
-- Description: Adds schema versioning system to track applied migrations

-- 1. Create schema_migrations table
CREATE TABLE IF NOT EXISTS schema_migrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version TEXT NOT NULL UNIQUE, -- Migration version/name (e.g., '001', '002', '003')
    name TEXT NOT NULL, -- Human-readable migration name
    description TEXT, -- Migration description
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    checksum TEXT, -- Optional: SHA256 checksum of migration SQL
    execution_time_ms INTEGER, -- Time taken to execute migration
    
    CONSTRAINT valid_version CHECK (version ~ '^[0-9]{3}$')
);

-- Index for version lookup
CREATE INDEX IF NOT EXISTS idx_schema_migrations_version ON schema_migrations(version);
CREATE INDEX IF NOT EXISTS idx_schema_migrations_applied_at ON schema_migrations(applied_at DESC);

-- 2. Insert initial migration records (if they were applied manually)
-- Note: These are for migrations that were already applied before versioning system
INSERT INTO schema_migrations (version, name, description)
VALUES 
    ('001', 'init', 'Initial schema creation'),
    ('002', 'update_embedding_dimension', 'Support for multiple embedding models and dimensions')
ON CONFLICT (version) DO NOTHING;

-- 3. Create function to check if migration was applied
CREATE OR REPLACE FUNCTION migration_applied(version_text TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM schema_migrations WHERE version = version_text
    );
END;
$$ LANGUAGE plpgsql;

-- 4. Create function to record migration
CREATE OR REPLACE FUNCTION record_migration(
    version_text TEXT,
    name_text TEXT,
    description_text TEXT DEFAULT NULL,
    checksum_text TEXT DEFAULT NULL,
    execution_time_ms INTEGER DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    migration_id UUID;
BEGIN
    INSERT INTO schema_migrations (version, name, description, checksum, execution_time_ms)
    VALUES (version_text, name_text, description_text, checksum_text, execution_time_ms)
    ON CONFLICT (version) DO UPDATE
    SET 
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        checksum = EXCLUDED.checksum,
        execution_time_ms = EXCLUDED.execution_time_ms
    RETURNING id INTO migration_id;
    
    RETURN migration_id;
END;
$$ LANGUAGE plpgsql;

-- 5. Add comments
COMMENT ON TABLE schema_migrations IS 'Tracks applied database schema migrations';
COMMENT ON FUNCTION migration_applied IS 'Check if a migration version was applied';
COMMENT ON FUNCTION record_migration IS 'Record a migration application';
