-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    topic TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 3. Create Messages table
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    embedding vector(1536) -- Compatible with OpenAI text-embedding-3-small
);

-- Index for vector search on messages
CREATE INDEX IF NOT EXISTS idx_messages_embedding ON messages USING hnsw (embedding vector_cosine_ops);

-- 4. Create Knowledge Graph Nodes (Temporal)
CREATE TABLE IF NOT EXISTS entity_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    type TEXT, -- e.g., 'technology', 'person', 'concept', 'SystemDocument'
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    embedding vector(1536),
    
    -- Temporal columns
    valid_from TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    valid_to TIMESTAMP WITH TIME ZONE, -- NULL means currently valid
    superseded_by UUID REFERENCES entity_nodes(id),
    
    UNIQUE(name, type)
);

-- Index for finding active nodes
CREATE INDEX IF NOT EXISTS idx_nodes_valid_to ON entity_nodes(valid_to) WHERE valid_to IS NULL;
CREATE INDEX IF NOT EXISTS idx_nodes_embedding ON entity_nodes USING hnsw (embedding vector_cosine_ops);

-- 5. Create Knowledge Graph Edges (Temporal)
CREATE TABLE IF NOT EXISTS entity_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES entity_nodes(id) ON DELETE CASCADE,
    target_id UUID REFERENCES entity_nodes(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL, -- e.g., 'uses', 'depends_on'
    weight FLOAT DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Temporal columns
    valid_from TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    valid_to TIMESTAMP WITH TIME ZONE, -- NULL means currently valid
    superseded_by UUID REFERENCES entity_edges(id),
    
    UNIQUE(source_id, target_id, relation_type)
);

-- Index for finding active edges
CREATE INDEX IF NOT EXISTS idx_edges_valid_to ON entity_edges(valid_to) WHERE valid_to IS NULL;

-- 6. Create Protocol Triggers table
CREATE TABLE IF NOT EXISTS protocol_triggers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    protocol_id UUID REFERENCES entity_nodes(id) ON DELETE CASCADE,
    trigger_examples TEXT[] NOT NULL, -- Array of example phrases for context understanding
    context_description TEXT, -- Description of when to use this protocol
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Temporal columns
    valid_from TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    valid_to TIMESTAMP WITH TIME ZONE, -- NULL means currently valid
    
    UNIQUE(protocol_id)
);

-- Index for finding active protocol triggers
CREATE INDEX IF NOT EXISTS idx_protocol_triggers_valid_to ON protocol_triggers(valid_to) WHERE valid_to IS NULL;

-- 7. Create Message-Entity Links table (for tracking rule/instruction usage in messages)
CREATE TABLE IF NOT EXISTS message_entity_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    entity_id UUID REFERENCES entity_nodes(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL, -- 'uses' (for rules), 'applies' (for instructions), 'executed_in' (for protocols)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(message_id, entity_id, relation_type)
);

-- Index for finding links by message
CREATE INDEX IF NOT EXISTS idx_message_entity_links_message ON message_entity_links(message_id);
-- Index for finding links by entity (to track usage frequency)
CREATE INDEX IF NOT EXISTS idx_message_entity_links_entity ON message_entity_links(entity_id);

-- 8. Create Session-Entity Links table (for tracking protocol execution in sessions)
CREATE TABLE IF NOT EXISTS session_entity_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    entity_id UUID REFERENCES entity_nodes(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL, -- 'executed_in' (for protocols), 'uses' (for rules/instructions)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(session_id, entity_id, relation_type)
);

-- Index for finding links by session
CREATE INDEX IF NOT EXISTS idx_session_entity_links_session ON session_entity_links(session_id);
-- Index for finding links by entity (to track usage frequency)
CREATE INDEX IF NOT EXISTS idx_session_entity_links_entity ON session_entity_links(entity_id);


