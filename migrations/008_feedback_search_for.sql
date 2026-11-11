-- What a user who still had to search elsewhere was looking for (after-trip form, "Bạn còn phải tìm gì?").
-- Keys from harness.dispatch.FEEDBACK_SEARCH_FOR. Unqualified names: the runner applies this in the connection's current schema.

ALTER TABLE feedback ADD COLUMN more_search_for text[] NOT NULL DEFAULT '{}';
