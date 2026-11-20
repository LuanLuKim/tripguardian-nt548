-- Guests made before users.kind existed carry role 'guest' on a kind 'user' row; prod's users_role_check had been
-- widened by hand to allow it, so purge_guests (kind = 'guest') never removed them. Make them the guests they are,
-- so the next purge drops them like any expired guest (trips go; journeys, events, feedback stay with user_id NULL),
-- then put the role check back to what 001_init.sql says.
-- Unqualified names: the runner applies this in the connection's current schema.

UPDATE users SET kind = 'guest', role = 'user' WHERE role = 'guest';
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('user', 'admin'));
