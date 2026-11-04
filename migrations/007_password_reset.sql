-- One-time codes for "Quên mật khẩu" (docs/ACCOUNTS.md §2c). One row per email, so asking again replaces the code.
-- user_id is NULL for an email without an account: the row (and its limits) look the same, nothing is mailed.
-- Only an HMAC of the code is kept. Unqualified names: the runner applies this in the connection's current schema.

CREATE TABLE password_resets (
    email citext PRIMARY KEY,
    user_id uuid REFERENCES users (id) ON DELETE CASCADE,
    code_hash bytea NOT NULL,
    expires_at timestamptz NOT NULL,
    tries int NOT NULL DEFAULT 0,
    sent_at timestamptz NOT NULL DEFAULT now(),
    window_start timestamptz NOT NULL DEFAULT now(),
    requests int NOT NULL DEFAULT 1
);

-- Analytics never reads secrets (same as sessions and OAuth state).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tg_analytics') THEN
        REVOKE SELECT ON password_resets FROM tg_analytics;
    END IF;
END $$;
