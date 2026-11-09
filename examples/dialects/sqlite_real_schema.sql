CREATE TABLE artists (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL COLLATE NOCASE,
  country                                     -- SQLite allows a column with no type
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE albums (
  id INTEGER PRIMARY KEY,
  artist_id INTEGER NOT NULL REFERENCES artists,   -- no column named: means the primary key
  title TEXT NOT NULL ON CONFLICT REPLACE DEFAULT 'untitled',
  score REAL DEFAULT -1.5e2,
  UNIQUE (artist_id, title)
) WITHOUT ROWID;
CREATE TABLE tracks (
  id INTEGER PRIMARY KEY DESC,
  album_id INTEGER REFERENCES albums (id) ON DELETE CASCADE,
  key TEXT,
  action TEXT,
  length_ms INTEGER CHECK (length_ms > 0)
, composer TEXT);
CREATE VIRTUAL TABLE track_search USING fts5(title)
/* track_search(title) */;
CREATE TABLE 'track_search_data'(id INTEGER PRIMARY KEY, block BLOB);
CREATE TABLE 'track_search_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;
CREATE TABLE 'track_search_content'(id INTEGER PRIMARY KEY, c0);
CREATE TABLE 'track_search_docsize'(id INTEGER PRIMARY KEY, sz BLOB);
CREATE TABLE 'track_search_config'(k PRIMARY KEY, v) WITHOUT ROWID;
CREATE TABLE saved_albums(id INT);
CREATE VIEW long_tracks AS SELECT id FROM tracks WHERE length_ms > 600000
/* long_tracks(id) */;
CREATE TRIGGER no_empty_titles BEFORE INSERT ON albums BEGIN
  SELECT RAISE(ABORT, 'it''s empty; try again') WHERE NEW.title = '';
END;
CREATE UNIQUE INDEX idx_tracks_key ON tracks (key);
