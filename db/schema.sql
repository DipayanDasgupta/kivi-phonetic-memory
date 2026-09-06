-- Kivi word memory schema (v1, applied by app/store.py::Store.create())

CREATE TABLE IF NOT EXISTS word (
    id           TEXT PRIMARY KEY,
    word         TEXT NOT NULL UNIQUE,              -- canonical key, lowercase
    display      TEXT NOT NULL,                      -- user's preferred capitalisation
    pos          TEXT NOT NULL DEFAULT 'other',      -- person | org | thing | acronym | other
    phonetic_key TEXT NOT NULL,                      -- encoding from app/phonetics.py
    status       TEXT NOT NULL DEFAULT 'candidate',  -- candidate | confirmed | suppressed | needs_review
    source       TEXT NOT NULL,                      -- user_correction | user_confirm | user_edit | ...
    provenance   TEXT NOT NULL DEFAULT '{}',         -- JSON: origin observation
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS word_form (
    id         TEXT PRIMARY KEY,
    word_id    TEXT NOT NULL REFERENCES word(id) ON DELETE CASCADE,
    form       TEXT NOT NULL,                       -- spelling seen/accepted for this word
    source     TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    UNIQUE (word_id, form)
);

CREATE TABLE IF NOT EXISTS word_context (
    id         TEXT PRIMARY KEY,
    word_id    TEXT NOT NULL REFERENCES word(id) ON DELETE CASCADE,
    context    TEXT NOT NULL,                       -- phrase template ("call <word>") or co-occurrence token
    position   TEXT NOT NULL DEFAULT 'template',    -- template | token
    source     TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    UNIQUE (word_id, context, position)
);

CREATE TABLE IF NOT EXISTS word_event (
    id      TEXT PRIMARY KEY,
    kind    TEXT NOT NULL,                          -- learn | confirm | conflict | suppress | delete | reset | ...
    payload TEXT NOT NULL,                          -- JSON: full observation/decision
    at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS word_stat (
    word_id       TEXT PRIMARY KEY REFERENCES word(id) ON DELETE CASCADE,
    occurrences   INTEGER NOT NULL DEFAULT 0,
    interventions INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS schema_migration (
    name       TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_word_status   ON word(status);
CREATE INDEX IF NOT EXISTS idx_word_phonetic ON word(phonetic_key);
CREATE INDEX IF NOT EXISTS idx_form_form     ON word_form(form);
CREATE INDEX IF NOT EXISTS idx_context_ctx   ON word_context(context);