-- Extensions for PostgreSQL (runs once on first container startup)
CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector: ML embedding vectors
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- Trigram fuzzy text search
CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; -- UUID generation
CREATE EXTENSION IF NOT EXISTS citext;      -- Case-insensitive text