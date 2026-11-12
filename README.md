# Schema Diagram

Turns a SQL schema file into a diagram of its tables, columns, constraints, and relationships, including tables that reference themselves. It reads Postgres, MySQL, SQLite, and SQL Server syntax.

## Setup

Requires Python 3.12+ and [Graphviz](https://graphviz.org/download/).

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## Usage

```bash
diagram path/to/schema.sql
```

If Windows blocks `diagram.exe`, run `python -m schemadiagram path/to/schema.sql` instead; it works the same way.

This writes `out/schema.svg`. Add `--open` to open it when it's done, or use `-o` to choose another location or format, like `-o shop.png`. Anything it has to skip is printed as a warning.

## Example

From [`examples/store.sql`](examples/store.sql):

```sql
CREATE TABLE customers (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL,
  referred_by INT REFERENCES customers(id),   -- self-reference, optional
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- One-to-one: UNIQUE means each customer has at most one profile.
CREATE TABLE customer_profiles (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL UNIQUE REFERENCES customers(id) ON DELETE CASCADE,
  bio TEXT,
  newsletter BOOLEAN DEFAULT FALSE
);
```

`diagram examples/store.sql` draws the whole 14-table file:

![Diagram of the store schema](docs/store.svg)

A crow's foot marks the "many" end of a relationship and a bar marks the "one" end. Dashed lines are optional relationships, and colored lines with a label are a foreign key spanning several columns.
