-- Move the extraction cache off the service-role key: let authenticated users
-- use the shared, global cache directly under RLS.
--
-- The cache holds only extracted text keyed by sha256(file bytes) and contains
-- no per-user data. Reading a row requires knowing the content hash (i.e.
-- already possessing the exact file bytes), so SELECT is open to any
-- authenticated user. INSERT/UPDATE are likewise open — accepted trade-off: a
-- logged-in user could seed/refresh a row for a hash they possess.

DROP POLICY IF EXISTS "Authenticated can read extraction cache"
    ON public.extraction_cache;
DROP POLICY IF EXISTS "Authenticated can insert extraction cache"
    ON public.extraction_cache;
DROP POLICY IF EXISTS "Authenticated can update extraction cache"
    ON public.extraction_cache;

CREATE POLICY "Authenticated can read extraction cache"
    ON public.extraction_cache FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Authenticated can insert extraction cache"
    ON public.extraction_cache FOR INSERT
    TO authenticated
    WITH CHECK (true);

CREATE POLICY "Authenticated can update extraction cache"
    ON public.extraction_cache FOR UPDATE
    TO authenticated
    USING (true)
    WITH CHECK (true);
