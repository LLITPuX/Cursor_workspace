-- Migration: Support for multiple embedding models and dimensions
-- Date: 2025-12-13
-- Description: Adds support for different embedding models (embeddinggemma 768d, OpenAI 1536d, etc.)

-- 1. Create table for embedding model metadata
CREATE TABLE IF NOT EXISTS embedding_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE, -- 'embeddinggemma', 'openai-text-embedding-3-small', etc.
    dimension INTEGER NOT NULL, -- 768 for embeddinggemma, 1536 for OpenAI
    provider TEXT NOT NULL, -- 'ollama', 'openai', 'local'
    model_config JSONB DEFAULT '{}'::jsonb, -- Additional parameters (model name, API key, etc.)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    
    CONSTRAINT valid_dimension CHECK (dimension > 0)
);

-- Index for active models
CREATE INDEX IF NOT EXISTS idx_embedding_models_active 
ON embedding_models(is_active) WHERE is_active = TRUE;

-- 2. Add model_id columns to messages and entity_nodes
ALTER TABLE messages 
ADD COLUMN IF NOT EXISTS embedding_model_id UUID REFERENCES embedding_models(id);

ALTER TABLE entity_nodes 
ADD COLUMN IF NOT EXISTS embedding_model_id UUID REFERENCES embedding_models(id);

-- 3. Soft migration: Create new columns with flexible dimension
-- We'll use a function to handle different dimensions dynamically
-- For now, create a new column for embeddinggemma (768d)

ALTER TABLE messages 
ADD COLUMN IF NOT EXISTS embedding_v2 vector(768);

ALTER TABLE entity_nodes 
ADD COLUMN IF NOT EXISTS embedding_v2 vector(768);

-- 4. Create indexes for new embedding columns
CREATE INDEX IF NOT EXISTS idx_messages_embedding_v2 
ON messages USING hnsw (embedding_v2 vector_cosine_ops) 
WHERE embedding_v2 IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_nodes_embedding_v2 
ON entity_nodes USING hnsw (embedding_v2 vector_cosine_ops) 
WHERE embedding_v2 IS NOT NULL;

-- 5. Insert default embedding models
INSERT INTO embedding_models (name, dimension, provider, model_config, is_active)
VALUES 
    ('embeddinggemma', 768, 'ollama', '{"model": "embeddinggemma:latest", "base_url": "http://localhost:11434"}'::jsonb, TRUE),
    ('openai-text-embedding-3-small', 1536, 'openai', '{"model": "text-embedding-3-small"}'::jsonb, FALSE)
ON CONFLICT (name) DO UPDATE 
SET dimension = EXCLUDED.dimension,
    provider = EXCLUDED.provider,
    model_config = EXCLUDED.model_config;

-- 6. Create function to get active embedding model
CREATE OR REPLACE FUNCTION get_active_embedding_model()
RETURNS TABLE (
    id UUID,
    name TEXT,
    dimension INTEGER,
    provider TEXT,
    model_config JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        em.id,
        em.name,
        em.dimension,
        em.provider,
        em.model_config
    FROM embedding_models em
    WHERE em.is_active = TRUE
    ORDER BY em.created_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- 7. Add comments for documentation
COMMENT ON TABLE embedding_models IS 'Metadata for different embedding models';
COMMENT ON COLUMN messages.embedding_model_id IS 'Reference to embedding model used for this message';
COMMENT ON COLUMN entity_nodes.embedding_model_id IS 'Reference to embedding model used for this entity';
COMMENT ON COLUMN messages.embedding_v2 IS 'Embedding vector (768d for embeddinggemma)';
COMMENT ON COLUMN entity_nodes.embedding_v2 IS 'Embedding vector (768d for embeddinggemma)';

