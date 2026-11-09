-- SQLite syntax. tests/test_dialects.py runs this through the real sqlite3 module.

PRAGMA foreign_keys = ON;

CREATE TABLE artists (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL COLLATE NOCASE,
  country                                     -- SQLite allows a column with no type
);

CREATE TABLE IF NOT EXISTS albums (
  id INTEGER PRIMARY KEY,
  artist_id INTEGER NOT NULL REFERENCES artists,   -- no column named: means the primary key
  title TEXT NOT NULL ON CONFLICT REPLACE DEFAULT 'untitled',
  score REAL DEFAULT -1.5e2,
  UNIQUE (artist_id, title)
) WITHOUT ROWID;

CREATE TEMP TABLE scratch (x INTEGER);

CREATE TABLE tracks (
  id INTEGER PRIMARY KEY DESC,
  album_id INTEGER REFERENCES albums (id) ON DELETE CASCADE,
  key TEXT,
  action TEXT,
  length_ms INTEGER CHECK (length_ms > 0)
);

CREATE VIRTUAL TABLE track_search USING fts5(title);

CREATE TABLE saved_albums AS SELECT id FROM albums;

CREATE VIEW long_tracks AS SELECT id FROM tracks WHERE length_ms > 600000;

CREATE TRIGGER no_empty_titles BEFORE INSERT ON albums BEGIN
  SELECT RAISE(ABORT, 'it''s empty; try again') WHERE NEW.title = '';
END;

CREATE UNIQUE INDEX idx_tracks_key ON tracks (key);

ALTER TABLE tracks ADD COLUMN composer TEXT;

INSERT INTO artists (name) VALUES ('O''Brien; & co');
