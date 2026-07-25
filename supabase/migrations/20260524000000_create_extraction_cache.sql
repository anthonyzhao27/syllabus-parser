-- Global content-hash cache for OCR / vision extraction results.
-- Service-role only. No RLS policies => authenticated/anon clients cannot read.

CREATE TABLE public.extraction_cache (
    content_hash TEXT PRIMARY KEY,
    extracted_text TEXT NOT NULL,
    source_mime TEXT NOT NULL,
    vision_model TEXT,
    vision_used BOOLEAN NOT NULL DEFAULT FALSE,
    byte_size INTEGER NOT NULL CHECK (byte_size >= 0),
    hit_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_hit_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_extraction_cache_created_at
    ON public.extraction_cache(created_at);

CREATE INDEX idx_extraction_cache_last_hit_at
    ON public.extraction_cache(last_hit_at);

ALTER TABLE public.extraction_cache ENABLE ROW LEVEL SECURITY;
