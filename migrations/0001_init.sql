-- Links and clicks. The private key is stored only as a SHA-256 hash.
CREATE TABLE links (
    code        TEXT PRIMARY KEY,
    url         TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    key_hash    TEXT NOT NULL
);

CREATE TABLE clicks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL REFERENCES links(code) ON DELETE CASCADE,
    clicked_at  TEXT NOT NULL,
    country     TEXT NOT NULL DEFAULT 'XX',
    referer     TEXT
);

CREATE INDEX clicks_code_time ON clicks (code, clicked_at);
