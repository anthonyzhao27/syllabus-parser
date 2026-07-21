-- Make the extraction cache PER-USER to close a cross-user cache-poisoning hole.
--
-- The previous global table + USING(true) policies let any authenticated user
-- INSERT/UPDATE the extracted_text for a content_hash that another user would
-- later fetch (the cached text is fed to the victim's LLM extraction). Scoping
-- every row to auth.uid() means a user can only read/write their OWN cache, so
-- tampering only ever affects the tamperer. Same-user repeat uploads still hit
-- the cache; cross-user dedup (the attack surface) is intentionally dropped.
--
-- Safe to restructure in place: the table is empty on this project.

ALTER TABLE public.extraction_cache
    ADD COLUMN user_id uuid NOT NULL DEFAULT auth.uid()
        REFERENCES auth.users(id) ON DELETE CASCADE;

-- content_hash alone was the PK; a file is now cached once PER user.
ALTER TABLE public.extraction_cache DROP CONSTRAINT extraction_cache_pkey;
ALTER TABLE public.extraction_cache
    ADD PRIMARY KEY (user_id, content_hash);

-- Replace the global (poisonable) policies with per-user ones.
DROP POLICY IF EXISTS "Authenticated can read extraction cache"
    ON public.extraction_cache;
DROP POLICY IF EXISTS "Authenticated can insert extraction cache"
    ON public.extraction_cache;
DROP POLICY IF EXISTS "Authenticated can update extraction cache"
    ON public.extraction_cache;

CREATE POLICY "Users read own extraction cache"
    ON public.extraction_cache FOR SELECT
    TO authenticated
    USING ((SELECT auth.uid()) = user_id);

CREATE POLICY "Users insert own extraction cache"
    ON public.extraction_cache FOR INSERT
    TO authenticated
    WITH CHECK ((SELECT auth.uid()) = user_id);

CREATE POLICY "Users update own extraction cache"
    ON public.extraction_cache FOR UPDATE
    TO authenticated
    USING ((SELECT auth.uid()) = user_id)
    WITH CHECK ((SELECT auth.uid()) = user_id);
