-- 1. Enable the pgvector extension to work with embedding vectors
create extension if not exists vector;

-- Drop existing to reset dimensions if previously run
drop table if exists zryth_knowledge;
drop function if exists match_knowledge;

-- 2. Create the knowledge base table
create table zryth_knowledge (
  id bigserial primary key,
  content text not null,
  metadata jsonb,
  embedding vector(3072) -- 3072 for gemini-embedding-2
);

-- 3. Create a function to search for matching knowledge chunks
-- This function can be called via Supabase RPC: supabase.rpc('match_knowledge', {query_embedding: ..., match_threshold: ..., match_count: ...})
create or replace function match_knowledge (
  query_embedding vector(3072),
  match_threshold float,
  match_count int
)
returns table (
  id bigint,
  content text,
  metadata jsonb,
  similarity float
)
language sql stable
as $$
  select
    zryth_knowledge.id,
    zryth_knowledge.content,
    zryth_knowledge.metadata,
    1 - (zryth_knowledge.embedding <=> query_embedding) as similarity
  from zryth_knowledge
  where 1 - (zryth_knowledge.embedding <=> query_embedding) > match_threshold
  order by zryth_knowledge.embedding <=> query_embedding
  limit match_count;
$$;
