-- Migration 001: initial schema. Applied by app/store.py::Store.create();
-- recorded in schema_migration. Re-running is a no-op (IF NOT EXISTS).
CREATE TABLE IF NOT EXISTS word (
    id           TEXT PRIMARY KEY,
    word         TEXT NOT NULL UNIQUE,
    display      TEXT NOT NULL,
    pos          TEXT NOT NULL DEFAULT 'other',
    phonetic_key TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'candidate',
    source       TEXT NOT NULL,
    provenance   TEXT NOT NULL DEFAULT '{}',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS word_form (
    id         TEXT PRIMARY KEY,
    word_id    TEXT NOT NULL REFERENCES word(id) ON DELETE CASCADE,
    form       TEXT NOT NULL,
    source     TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    UNIQUE (word_id, form)
);
CREATE TABLE IF NOT EXISTS word_context (
    id         TEXT PRIMARY KEY,
    word_id    TEXT NOT NULL REFERENCES word(id) ON DELETE CASCADE,
    context    TEXT NOT NULL,
    position   TEXT NOT NULL DEFAULT 'template',
    source     TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    UNIQUE (word_id, context, position)
);
CREATE TABLE IF NOT EXISTS word_event (
    id      TEXT PRIMARY KEY,
    kind    TEXT NOT NULL,
    payload TEXT NOT NULL,
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