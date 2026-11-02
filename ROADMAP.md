# Schema Diagram: Roadmap

A Python program that reads a `.sql` schema file and produces a diagram showing
tables, columns, constraints, and relationships, including self-relationships.

```
schema.sql → tokenizer → parser → data model → DOT generator → Graphviz → schema.svg / .png
```

Work through the phases in order. Each one ends with something that works and
that you can test. Don't skip the "Done when" checks.

---

## 0. Tooling and setup

### What you need

| Tool | What it's for | Install |
|---|---|---|
| **Python 3.12+** | The language (you have 3.14) | already installed |
| **Graphviz** | Layout and rendering engine (the `dot` program) | `winget install graphviz`, then restart your terminal |
| **git** | Version control: commit after every working step | already installed |
| **VS Code** + Python extension | Editor, debugger, test runner | code.visualstudio.com |
| **venv** | Isolated per-project Python environment | built into Python |

### Python libraries

| Library | Why | When |
|---|---|---|
| `graphviz` | Calls Graphviz from Python | Phase 1 |
| `pytest` | Testing | Phase 1 |
| `ruff` | Linter and formatter (keeps code tidy) | Phase 1 |
| `mypy` | Optional: checks your type hints | Phase 3+ |
| `watchdog` | Re-render when the .sql file changes | Phase 7 (stretch) |
| `flask` | Small web UI | Phase 8 (stretch) |

Everything else comes from the standard library: `dataclasses`, `enum`,
`argparse`, `pathlib`, `re`, `json`.

> **Don't install a SQL parsing library** (like `sqlglot` or `sqlparse`).
> Writing the parser yourself is the main thing you'll learn. If you get badly
> stuck, `sqlglot` is a useful reference for how a real parser handles a tricky case.

### Setup steps

```bash
cd C:\TheMachine\Claude\schema-diagram
python -m venv .venv
.venv\Scripts\activate
pip install graphviz pytest ruff
pip freeze > requirements.txt
git init
dot -V          # should print a Graphviz version
```

Add a `.gitignore` containing `.venv/`, `__pycache__/`, `out/`.

### Project layout to aim for

```
schema-diagram/
├── schemadiagram/
│   ├── __init__.py
│   ├── model.py        # dataclasses: Schema, Table, Column, ForeignKey, ...
│   ├── tokenizer.py    # SQL text → list of Tokens
│   ├── parser.py       # Tokens → Schema
│   ├── render_dot.py   # Schema → DOT text
│   └── cli.py          # command-line entry point
├── tests/
│   ├── test_tokenizer.py
│   ├── test_parser.py
│   └── test_render_dot.py
├── examples/
│   └── basic.sql
├── out/                # generated diagrams (git-ignored)
├── requirements.txt
└── ROADMAP.md
```

---

## Phase 1: Data model and first diagram (no parsing yet)

**Goal:** Pin down what the parser must produce, and see a diagram on day one.

**Tasks**
1. In `model.py`, write dataclasses: `Column` (name, type, nullable, primary_key,
   unique, default, check), `ForeignKey` (from table/columns, to table/columns,
   on_delete), `Table` (name, columns, foreign keys, table-level checks), `Schema`.
2. Build a `Schema` **by hand** in Python for 2–3 tables, including one self-reference.
3. In `render_dot.py`, write `to_dot(schema) -> str` that outputs HTML-like
   table labels, one `<tr>` per column, with `port=` attributes.
4. Render it with `graphviz.Source(dot).render("out/schema", format="svg")`.

**You'll learn:** dataclasses, type hints, the DOT language, separating data from presentation.

**Done when:** you open `out/schema.svg` and see your tables with arrows between the right columns.

---

## Phase 2: Tokenizer

**Goal:** Turn raw SQL text into a flat list of tokens.

**Tasks**
1. Define a `TokenType` enum: `KEYWORD`, `IDENTIFIER`, `NUMBER`, `STRING`,
   `SYMBOL` (`( ) , ; .`), `OPERATOR` (`> < = >= <= <>`), `EOF`.
2. Define a `Token` dataclass with `type`, `value`, `line`, `column`. Keeping
   positions makes error messages useful later.
3. Write `tokenize(text) -> list[Token]`, a loop over characters that handles:
   - whitespace (skip it)
   - `-- line comments` and `/* block comments */` (skip them)
   - identifiers and keywords (case-insensitive: `create` = `CREATE`)
   - quoted identifiers: `"my table"`, `` `my_table` ``, `[my table]`
   - string literals `'it''s'`, numbers `10`, `3.14`
   - symbols and operators
4. Raise a clear error on unexpected characters: `Unexpected '@' at line 4, col 12`.

**You'll learn:** lexical analysis, state machines, writing tests first.

**Done when:** `pytest` passes 15+ small tokenizer tests, including comments and quoted names.

---

## Phase 3: Parser for `CREATE TABLE`

**Goal:** Turn tokens into your `Schema` model.

**Approach:** a **recursive-descent parser**, a class with a position pointer
and helpers like `peek()`, `advance()`, `expect("KEYWORD", "TABLE")`, `match(...)`.
Write one method per grammar rule:

```
schema         := statement* EOF
statement      := create_table ";" | skip_unknown_statement
create_table   := CREATE TABLE [IF NOT EXISTS] name "(" table_item ("," table_item)* ")"
table_item     := column_def | table_constraint
column_def     := name type column_constraint*
type           := word ["(" number ["," number] ")"]          -- VARCHAR(255), NUMERIC(10,2)
column_constraint := PRIMARY KEY | NOT NULL | NULL | UNIQUE
                   | DEFAULT expr | CHECK "(" expr ")"
                   | REFERENCES name ["(" name ")"] [ON DELETE action]
table_constraint  := [CONSTRAINT name] ( PRIMARY KEY "(" names ")"
                   | UNIQUE "(" names ")"
                   | FOREIGN KEY "(" names ")" REFERENCES name "(" names ")"
                   | CHECK "(" expr ")" )
```

**Tips**
- For `CHECK (...)` and `DEFAULT`, don't parse full expressions. Collect tokens
  until the parentheses balance and keep the result as text.
- **Skip statements you don't understand** (`CREATE INDEX`, `INSERT`, ...) by
  reading to the next `;`. Real schema files are full of them.
- Do it in small steps: columns only → inline constraints → table constraints → foreign keys.

**You'll learn:** grammars, recursion, parser error handling and recovery.

**Done when:** the parser reads `examples/basic.sql` into the same `Schema` you built by hand in Phase 1. Write a test that asserts exactly that.

---

## Phase 4: End-to-end CLI

**Goal:** A real command-line tool.

```bash
python -m schemadiagram examples/basic.sql -o out/basic.svg
python -m schemadiagram examples/basic.sql -o out/basic.png --dpi 200
```

**Tasks**
1. `cli.py` with `argparse`: input path, `-o` output path (format taken from the extension), `--dpi`.
2. Add `__main__.py` so `python -m schemadiagram` works.
3. Friendly errors: missing file, parse error with line/col, Graphviz not installed.

**You'll learn:** argparse, packaging basics, user-facing error handling.

**Done when:** a single command takes a `.sql` file and produces a PNG/SVG.

---

## Phase 5: Make the diagram good

**Goal:** A diagram you'd actually want to use.

**Tasks**
- Mark columns: 🔑 PK, FK, `NOT NULL`, `UNIQUE`, defaults; show `CHECK` rules in a footer row.
- Show **cardinality** with arrowheads: `arrowhead=crow` / `arrowtail=tee`
  (one-to-many). Infer one-to-one when the FK column is also `UNIQUE`.
- Draw nullable FKs (optional relationships) as dashed lines.
- Make self-relationships readable (`headport`/`tailport` on the east/west side).
- Try options: `rankdir=LR`, `splines=ortho`, `nodesep`, `ranksep`, colors.
- Escape `<`, `>`, `&` in labels (your `CHECK (salary > 0)` will break otherwise).

**You'll learn:** Graphviz attributes, ER-diagram conventions, careful escaping.

**Done when:** a 10+ table schema renders cleanly and you can understand the relationships at a glance.

---

## Phase 6: Real-world SQL

**Goal:** Handle schemas you didn't write.

**Tasks**
- `ALTER TABLE x ADD [CONSTRAINT n] FOREIGN KEY ...` (very common in exported dumps).
- Composite primary and foreign keys `(a, b)`.
- Schema-qualified names: `public.users`, `dbo.Orders`.
- Dialect quirks: MySQL `AUTO_INCREMENT`, `ENGINE=InnoDB`; Postgres `SERIAL`,
  `GENERATED ... AS IDENTITY`; SQLite `INTEGER PRIMARY KEY AUTOINCREMENT`.
- Collect **warnings** (e.g. "FK references unknown table `foo`") instead of crashing.

**Test data:** export real schemas, e.g. `pg_dump --schema-only`, `sqlite3 db .schema`,
or sample databases like *Sakila* (MySQL), *Chinook*, and *Northwind*.

**Done when:** you can render a real sample database schema without editing it by hand.

---

## Phase 7: Polish (pick any)

- `--format json` to dump the parsed model (good for debugging).
- `--watch` mode with `watchdog`: re-render whenever the .sql changes.
- Filter options: `--only users,orders`, `--hide-columns` (relationships only).
- Group tables into clusters by schema name (`subgraph cluster_public`).
- Package it with a `pyproject.toml` so `pip install -e .` gives you a `schemadiagram` command.

---

## Phase 8: Stretch goals

- **Web UI:** a Flask app where you paste or upload SQL and see the SVG instantly.
- **Interactivity:** hover a table to highlight its relationships (JavaScript on the SVG).
- **Reverse direction:** connect to a live SQLite/Postgres database and read the
  schema from it instead of a file.
- **Diff mode:** compare two schema files and color added/removed tables and columns.

---

## Habits for the whole project

- **Commit after every working step.** Small commits make experiments safe.
- **Write the test first** for each new SQL feature: add the SQL snippet, add
  the expected model, then make it pass.
- **Keep the stages independent.** The parser must never import Graphviz, and the
  renderer must never look at tokens. If you ever want a different renderer
  (Mermaid, web), only one file changes.
- When stuck on Graphviz output, paste the generated DOT into an online viewer
  and adjust it by hand until it looks right, then update your generator.

## Reference links

- Graphviz docs: https://graphviz.org/documentation/
- DOT HTML-like labels: https://graphviz.org/doc/info/shapes.html#html
- Graphviz attributes: https://graphviz.org/doc/info/attrs.html
- `graphviz` Python package: https://graphviz.readthedocs.io/
- *Crafting Interpreters* (free online), chapters 4–6 explain tokenizers and
  recursive-descent parsers well: https://craftinginterpreters.com/
- SQLite `CREATE TABLE` syntax diagrams (a clear grammar reference): https://www.sqlite.org/lang_createtable.html
