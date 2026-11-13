-- kb.sql v3.0 — generated index schema for system/kb.db. Frozen contract.
PRAGMA user_version = 3;

CREATE TABLE entities (
  id TEXT PRIMARY KEY, type TEXT NOT NULL CHECK (type IN ('project','person','topic','repo','adr','proposal')),
  title TEXT, path TEXT NOT NULL, owner TEXT, status TEXT, updated TEXT
);

CREATE TABLE raw_items (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK (kind IN ('mtg','slack','conf','note','src')),
  date TEXT NOT NULL, week TEXT NOT NULL, title TEXT, path TEXT NOT NULL,
  summary_path TEXT, attendance TEXT CHECK (attendance IN ('attended','invited-absent','not-invited')),
  project TEXT, meeting_type TEXT, wiki_processed INTEGER DEFAULT 0, redact_content INTEGER DEFAULT 0
);

CREATE TABLE people (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT, tier TEXT, manager TEXT REFERENCES people(id),
  email TEXT, slack_id TEXT, page_path TEXT
);

CREATE TABLE project_members (
  project TEXT NOT NULL REFERENCES entities(id), person TEXT NOT NULL REFERENCES people(id),
  role TEXT, is_owner INTEGER DEFAULT 0, is_decision_maker INTEGER DEFAULT 0,
  PRIMARY KEY (project, person)
);

CREATE TABLE meeting_attendees (
  raw_id TEXT NOT NULL REFERENCES raw_items(id), person TEXT NOT NULL REFERENCES people(id),
  attendance TEXT NOT NULL, PRIMARY KEY (raw_id, person)
);

CREATE TABLE entries (
  key TEXT NOT NULL,                 -- <project>/<ID>
  project TEXT NOT NULL, facet TEXT NOT NULL, id TEXT NOT NULL,
  date TEXT NOT NULL, state TEXT NOT NULL, by TEXT NOT NULL CHECK (by IN ('human','ai','ai-confirmed')),
  trust TEXT CHECK (trust IN ('high','medium','low')), source TEXT, owner TEXT, due TEXT, rag TEXT,
  body TEXT, path TEXT NOT NULL, line INTEGER NOT NULL,
  PRIMARY KEY (key, date, line)
);
CREATE INDEX entries_project ON entries(project, facet);
CREATE INDEX entries_state ON entries(state);

-- latest state per ID
CREATE VIEW current_entries AS
  SELECT e.* FROM entries e
  WHERE (e.date, e.line) = (SELECT date, line FROM entries x WHERE x.key = e.key ORDER BY date DESC, line DESC LIMIT 1);

CREATE TABLE decisions (
  id TEXT PRIMARY KEY, project TEXT NOT NULL, date TEXT NOT NULL, title TEXT,
  status TEXT NOT NULL CHECK (status IN ('proposed','accepted','superseded','rejected')),
  by TEXT NOT NULL CHECK (by IN ('human','ai','ai-confirmed')), trust TEXT, source TEXT,
  owner TEXT, supersedes TEXT, path TEXT NOT NULL
);

CREATE TABLE links (src TEXT NOT NULL, dst TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'cite', path TEXT, line INTEGER);
CREATE INDEX links_dst ON links(dst);

CREATE TABLE sessions (
  id TEXT PRIMARY KEY, date TEXT NOT NULL, model TEXT, summary TEXT, files_touched TEXT, path TEXT
);

CREATE TABLE proposals (
  id TEXT PRIMARY KEY, audience TEXT CHECK (audience IN ('system','owner')), date TEXT,
  state TEXT CHECK (state IN ('open','accepted','rejected')), title TEXT, source TEXT, path TEXT
);

CREATE TABLE attention_queries (name TEXT PRIMARY KEY, sql TEXT NOT NULL, description TEXT);

-- full-text search over everything readable
CREATE VIRTUAL TABLE fts USING fts5(id UNINDEXED, kind UNINDEXED, path UNINDEXED, title, body, tokenize='porter unicode61');

CREATE TABLE _build (key TEXT PRIMARY KEY, value TEXT);  -- schema_version, source_hash (deterministic, makes rebuild a no-op diff)
