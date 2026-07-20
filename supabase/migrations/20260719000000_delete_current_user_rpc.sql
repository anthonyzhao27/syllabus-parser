-- Self-serve account deletion WITHOUT the backend holding the service-role key.
--
-- A SECURITY DEFINER function lets an authenticated caller delete their OWN
-- auth.users row. Deleting that row cascades (ON DELETE CASCADE) to profiles,
-- syllabi, events and reminders. The function only ever targets auth.uid(), so
-- a caller can never delete another user's account.

CREATE OR REPLACE FUNCTION public.delete_current_user()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    uid uuid := auth.uid();
BEGIN
    IF uid IS NULL THEN
        RAISE EXCEPTION 'Not authenticated';
    END IF;

    DELETE FROM auth.users WHERE id = uid;
END;
$$;

-- Only logged-in users may call it; it always acts on the caller (auth.uid()).
REVOKE ALL ON FUNCTION public.delete_current_user() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.delete_current_user() TO authenticated;
