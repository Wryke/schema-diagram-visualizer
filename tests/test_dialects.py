"""Phase 6 tests: whole files in each database's own style.

postgres_real_*.sql and sqlite_real_schema.sql are unedited output from the real
pg_dump and sqlite3 tools. mysql_dump.sql and sqlserver.sql are written by hand
in the format those tools produce, and sqlite.sql is the source of the real file.
"""

import shutil
import sqlite3
from pathlib import Path

import graphviz
import pytest

from schemadiagram.cli import main
from schemadiagram.parser import parse
from schemadiagram.render_dot import to_dot

needs_graphviz = pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz not installed")

DIALECTS = Path(__file__).parent.parent / "examples" / "dialects"


def load(name):
    return parse((DIALECTS / name).read_text(encoding="utf-8"))


def edges(schema):
    """Every foreign key as (from table, from columns, to table, to columns)."""
    return {
        (fk.from_table, tuple(fk.from_columns), fk.to_table, tuple(fk.to_columns))
        for fk in schema.foreign_keys
    }


def column(schema, table, name):
    return schema.table(table).column(name)


# --- real pg_dump output ---


@pytest.fixture(scope="module")
def postgres():
    return load("postgres_real_schema.sql")


def test_postgres_tables(postgres):
    assert {t.name for t in postgres.tables} == {
        "customers", "Order Items", "node", "graph", "line_items", "shipments", "profiles", "events", "events_2026",
    }


def test_postgres_has_nothing_to_warn_about(postgres):
    assert postgres.warnings == []


def test_postgres_foreign_keys_from_alter_table(postgres):
    assert edges(postgres) == {
        ("customers", ("referred_by",), "customers", ("id",)),
        ("Order Items", ("Customer Id",), "customers", ("id",)),
        ("graph", ("node_key",), "node", ("key",)),
        ("graph", ("parent_id",), "graph", ("id",)),
        ("line_items", ("order_id",), "Order Items", ("id",)),
        ("shipments", ("order_id", "line_no"), "line_items", ("order_id", "line_no")),
        ("profiles", ("customer_id",), "customers", ("id",)),
    }


def test_postgres_primary_keys_from_alter_table(postgres):
    assert postgres.table("customers").primary_key == ["id"]
    assert postgres.table("line_items").primary_key == ["order_id", "line_no"]


def test_postgres_identity_and_serial_are_auto_increment(postgres):
    assert column(postgres, "customers", "id").auto_increment
    assert column(postgres, "Order Items", "id").auto_increment
    assert column(postgres, "Order Items", "id").default is None
    assert not column(postgres, "line_items", "order_id").auto_increment


def test_postgres_unique_constraints_from_alter_table(postgres):
    assert column(postgres, "profiles", "customer_id").unique
    assert postgres.table("Order Items").unique_sets == [["Customer Id", "status"]]


def test_postgres_types_and_defaults(postgres):
    assert column(postgres, "customers", "tags").type == "text[]"
    assert column(postgres, "customers", "scores").type == "integer[]"
    assert column(postgres, "customers", "created_at").type == "timestamp with time zone"
    assert column(postgres, "customers", "created_at").default == "now()"
    assert column(postgres, "customers", "note").default == "'it''s new'::text"
    assert column(postgres, "Order Items", "status").type == "shop.order_status"


def test_postgres_keyword_names_keep_their_spelling(postgres):
    assert [c.name for c in postgres.table("node").columns] == ["key", "action", "edge"]


def test_postgres_dump_with_data_reads_the_same_as_schema_only(postgres):
    # This dump has COPY rows holding apostrophes and semicolons, and foreign keys after them.
    assert load("postgres_real_with_data.sql") == postgres


# --- real sqlite3 output ---


def test_sqlite_real_schema():
    schema = load("sqlite_real_schema.sql")
    assert {"artists", "albums", "tracks", "saved_albums", "track_search_data"} <= {t.name for t in schema.tables}
    assert edges(schema) == {
        ("albums", ("artist_id",), "artists", ("id",)),
        ("tracks", ("album_id",), "albums", ("id",)),
    }
    assert column(schema, "tracks", "composer").type == "TEXT"  # from ALTER TABLE ... ADD COLUMN


# --- SQLite source ---


def test_sqlite_sample_is_valid_sqlite():
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript((DIALECTS / "sqlite.sql").read_text(encoding="utf-8"))
    finally:
        connection.close()


def test_sqlite_details():
    schema = load("sqlite.sql")
    assert [t.name for t in schema.tables] == ["artists", "albums", "scratch", "tracks"]
    assert column(schema, "artists", "id").auto_increment
    assert column(schema, "artists", "country").type == ""
    assert column(schema, "albums", "score").default == "-1.5e2"
    assert column(schema, "albums", "title").nullable is False
    assert schema.table("albums").foreign_keys[0].to_columns == ["id"]
    assert schema.table("tracks").primary_key == ["id"]
    assert column(schema, "tracks", "composer") is not None


def test_sqlite_warns_about_tables_it_cannot_read():
    warnings = load("sqlite.sql").warnings
    assert any("track_search" in w for w in warnings)
    assert any("saved_albums" in w for w in warnings)
    assert len(warnings) == 2


# --- MySQL format ---


@pytest.fixture(scope="module")
def mysql():
    return load("mysql_dump.sql")


def test_mysql_tables_and_no_warnings(mysql):
    assert [t.name for t in mysql.tables] == ["country", "city", "staff", "rental"]
    assert mysql.warnings == []


def test_mysql_foreign_keys(mysql):
    assert edges(mysql) == {
        ("city", ("country_id",), "country", ("country_id",)),
        ("staff", ("city_id",), "city", ("city_id",)),
        ("staff", ("manager_id",), "staff", ("staff_id",)),
        ("rental", ("staff_id",), "staff", ("staff_id",)),
    }


def test_mysql_indexes_do_not_become_columns(mysql):
    assert [c.name for c in mysql.table("rental").columns] == ["rental_id", "staff_id"]
    assert "idx_city" not in [c.name for c in mysql.table("city").columns]


def test_mysql_column_details(mysql):
    assert column(mysql, "country", "country_id").type == "smallint unsigned"
    assert column(mysql, "country", "country_id").auto_increment
    assert column(mysql, "country", "country").type == "varchar(50)"
    assert column(mysql, "country", "last_update").default == "CURRENT_TIMESTAMP"
    assert column(mysql, "city", "key").unique  # from UNIQUE KEY `uq_city_key` (`key`(10))
    assert column(mysql, "city", "kind").type == "enum('big', 'small')"
    assert column(mysql, "city", "flags").type == "SET('a', 'b', 'c')"
    assert column(mysql, "staff", "salary").type == "decimal(10, 2) unsigned"
    assert mysql.table("staff").checks == ["(salary < 1000000)"]


# --- SQL Server format ---


@pytest.fixture(scope="module")
def sqlserver():
    return load("sqlserver.sql")


def test_sqlserver_tables_and_no_warnings(sqlserver):
    assert [t.name for t in sqlserver.tables] == ["Customers", "Order Header", "OrderLine"]
    assert sqlserver.warnings == []


def test_sqlserver_foreign_keys(sqlserver):
    assert edges(sqlserver) == {
        ("Order Header", ("CustomerID",), "Customers", ("CustomerID",)),
        ("OrderLine", ("OrderID",), "Order Header", ("OrderID",)),
    }


def test_sqlserver_column_details(sqlserver):
    assert column(sqlserver, "Customers", "CustomerID").auto_increment
    assert column(sqlserver, "Customers", "Notes").type == "nvarchar(max)"
    assert column(sqlserver, "Customers", "Name").unique
    assert column(sqlserver, "Customers", "key").type == "varchar(max)"
    assert column(sqlserver, "Customers", "index").type == "int"
    assert column(sqlserver, "Customers", "Greeting").default == "(N'it''s me')"
    assert column(sqlserver, "Order Header", "Doubled").type == ""
    assert sqlserver.table("Order Header").checks == ["(Total >= (0))"]
    assert sqlserver.table("OrderLine").primary_key == ["OrderID", "LineNo"]


# --- drawing them ---


@needs_graphviz
@pytest.mark.parametrize(
    "name",
    ["postgres_real_schema.sql", "postgres_real_with_data.sql", "sqlite_real_schema.sql",
     "sqlite.sql", "mysql_dump.sql", "sqlserver.sql"],
)
def test_every_sample_draws_all_its_tables_and_arrows(name):
    schema = load(name)
    svg = graphviz.Source(to_dot(schema)).pipe(format="svg", encoding="utf-8")
    assert svg.count('class="node"') == len(schema.tables)
    assert svg.count('class="edge"') == sum(len(fk.from_columns) for fk in schema.foreign_keys)


@needs_graphviz
def test_sql_server_file_saved_as_utf16_draws_through_the_cli(tmp_path, capsys):
    path = tmp_path / "ssms.sql"
    path.write_bytes(b"\xff\xfe" + (DIALECTS / "sqlserver.sql").read_text(encoding="utf-8").encode("utf-16-le"))
    assert main([str(path), "-o", str(tmp_path / "x.svg")]) == 0
    assert "(3 tables, 2 foreign keys)" in capsys.readouterr().out
