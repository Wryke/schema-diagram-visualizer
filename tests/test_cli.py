"""Phase 4 tests: the command line, from arguments to a file on disk."""

import shutil
import subprocess
import sys
from pathlib import Path

import graphviz
import pytest

from schemadiagram import cli, render_dot
from schemadiagram.cli import main

needs_graphviz = pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz not installed")

BASIC_SQL = Path(__file__).parent.parent / "examples" / "basic.sql"
PNG_SIGNATURE = b"\x89PNG"


@pytest.fixture
def sql_file(tmp_path):
    path = tmp_path / "schema.sql"
    path.write_text("CREATE TABLE users (id INT PRIMARY KEY);", encoding="utf-8")
    return path


def assert_error(capsys, argv, message):
    """Run the CLI and check it fails with one clean line on stderr."""
    assert main([str(a) for a in argv]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert message in captured.err
    assert "Traceback" not in captured.err


# --- success ---


@needs_graphviz
def test_writes_an_svg_and_reports_it(tmp_path, capsys):
    output = tmp_path / "basic.svg"
    assert main([str(BASIC_SQL), "-o", str(output)]) == 0
    assert "<svg" in output.read_text(encoding="utf-8")
    assert capsys.readouterr().out == f"Wrote {output} (4 tables, 4 foreign keys)\n"


@needs_graphviz
def test_diagram_contains_the_parsed_tables(tmp_path):
    output = tmp_path / "basic.svg"
    main([str(BASIC_SQL), "-o", str(output)])
    svg = output.read_text(encoding="utf-8")
    for name in ["users", "employees", "projects", "project_members", "manager_id"]:
        assert name in svg


@needs_graphviz
def test_extension_picks_the_format(tmp_path, sql_file):
    output = tmp_path / "schema.png"
    assert main([str(sql_file), "-o", str(output)]) == 0
    assert output.read_bytes().startswith(PNG_SIGNATURE)


@needs_graphviz
def test_higher_dpi_makes_a_bigger_png(tmp_path, sql_file):
    low, high = tmp_path / "low.png", tmp_path / "high.png"
    main([str(sql_file), "-o", str(low), "--dpi", "72"])
    main([str(sql_file), "-o", str(high), "--dpi", "300"])
    assert high.stat().st_size > low.stat().st_size


@needs_graphviz
def test_default_output_is_named_after_the_input_in_the_out_folder(tmp_path, sql_file, monkeypatch):
    out_folder = tmp_path / "project_out"
    monkeypatch.setattr(cli, "OUT_FOLDER", out_folder)
    assert main([str(sql_file)]) == 0
    assert (out_folder / "schema.svg").exists()


@needs_graphviz
def test_default_output_keeps_dots_in_the_input_name(tmp_path, monkeypatch):
    path = tmp_path / "shop.v2.sql"
    path.write_text("CREATE TABLE t (x INT);", encoding="utf-8")
    monkeypatch.setattr(cli, "OUT_FOLDER", tmp_path / "out")
    assert main([str(path)]) == 0
    assert (tmp_path / "out" / "shop.v2.svg").exists()


@needs_graphviz
def test_default_output_ignores_the_current_folder(tmp_path, sql_file, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(cli, "OUT_FOLDER", tmp_path / "project_out")
    assert main([str(sql_file)]) == 0
    assert list(elsewhere.iterdir()) == []


def test_out_folder_is_in_the_project():
    assert cli.OUT_FOLDER == Path(__file__).resolve().parent.parent / "out"


@needs_graphviz
def test_open_flag_opens_the_written_file(tmp_path, sql_file, monkeypatch):
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda uri: opened.append(uri) or True)
    output = tmp_path / "x.svg"
    assert main([str(sql_file), "-o", str(output), "--open"]) == 0
    assert opened == [output.resolve().as_uri()]


@needs_graphviz
def test_nothing_opens_without_the_flag(tmp_path, sql_file, monkeypatch):
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda uri: opened.append(uri) or True)
    assert main([str(sql_file), "-o", str(tmp_path / "x.svg")]) == 0
    assert opened == []


@needs_graphviz
def test_open_failure_is_a_warning_not_an_error(tmp_path, sql_file, monkeypatch, capsys):
    monkeypatch.setattr(cli.webbrowser, "open", lambda uri: False)
    assert main([str(sql_file), "-o", str(tmp_path / "x.svg"), "--open"]) == 0
    assert "couldn't open" in capsys.readouterr().err


def test_nothing_opens_when_the_diagram_fails(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda uri: opened.append(uri) or True)
    assert main([str(tmp_path / "nope.sql"), "--open"]) == 1
    assert opened == []


@needs_graphviz
def test_summary_uses_singular_for_one(tmp_path, sql_file, capsys):
    main([str(sql_file), "-o", str(tmp_path / "x.svg")])
    assert "(1 table, 0 foreign keys)" in capsys.readouterr().out


@needs_graphviz
def test_file_with_byte_order_mark(tmp_path):
    path = tmp_path / "bom.sql"
    path.write_text("CREATE TABLE t (x INT);", encoding="utf-8-sig")
    assert main([str(path), "-o", str(tmp_path / "bom.svg")]) == 0


@needs_graphviz
def test_python_dash_m_runs_the_tool(tmp_path):
    output = tmp_path / "basic.svg"
    result = subprocess.run(
        [sys.executable, "-m", "schemadiagram", str(BASIC_SQL), "-o", str(output)],
        check=False, capture_output=True, text=True, cwd=Path(__file__).parent.parent,
    )
    assert result.returncode == 0, result.stderr
    assert output.exists()


@needs_graphviz
@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-be", "utf-16-le"])
def test_utf16_file_with_byte_order_mark(tmp_path, encoding):
    path = tmp_path / "ssms.sql"
    text = "CREATE TABLE t (x INT);"
    bom = {"utf-16": b"", "utf-16-be": b"\xfe\xff", "utf-16-le": b"\xff\xfe"}[encoding]
    path.write_bytes(bom + text.encode(encoding))
    assert main([str(path), "-o", str(tmp_path / "x.svg")]) == 0


@needs_graphviz
def test_warnings_go_to_stderr_and_still_succeed(tmp_path, capsys):
    path = tmp_path / "w.sql"
    path.write_text("CREATE TABLE t (x INT REFERENCES missing(id));", encoding="utf-8")
    output = tmp_path / "w.svg"
    assert main([str(path), "-o", str(output)]) == 0
    captured = capsys.readouterr()
    assert captured.err == "warning: t.x references missing, which isn't in this file\n"
    assert captured.out.startswith("Wrote ")
    assert output.exists()


@needs_graphviz
def test_clean_file_prints_no_warnings(tmp_path, capsys):
    main([str(BASIC_SQL), "-o", str(tmp_path / "x.svg")])
    assert capsys.readouterr().err == ""


# --- input errors ---


def test_missing_input_file(tmp_path, capsys):
    assert_error(capsys, [tmp_path / "nope.sql"], "File not found")


def test_input_is_a_directory(tmp_path, capsys):
    assert_error(capsys, [tmp_path], "Can't read")


def test_input_is_not_utf8(tmp_path, capsys):
    path = tmp_path / "latin1.sql"
    path.write_bytes(b"CREATE TABLE caf\xe9 (x INT);")
    assert_error(capsys, [path], "isn't UTF-8")


def test_tokenizer_error_names_the_file_and_position(tmp_path, capsys):
    path = tmp_path / "bad.sql"
    path.write_text("CREATE TABLE t (\n  x INT DEFAULT 'oops\n);", encoding="utf-8")
    assert_error(capsys, [path], f"{path}: Unterminated quote starting at line 2, col 17")


def test_unknown_character_in_a_table_names_the_position(tmp_path, capsys):
    path = tmp_path / "bad.sql"
    path.write_text("CREATE TABLE t (\n  x @ INT\n);", encoding="utf-8")
    assert_error(capsys, [path], f"{path}: Expected a column constraint but found '@' at line 2, col 5")


def test_parse_error_names_the_file_and_position(tmp_path, capsys):
    path = tmp_path / "bad.sql"
    path.write_text("CREATE TABLE t (x INT NOT);", encoding="utf-8")
    assert_error(capsys, [path], f"{path}: Expected NULL but found ')' at line 1, col 26")


def test_file_with_no_tables(tmp_path, capsys):
    path = tmp_path / "empty.sql"
    path.write_text("-- nothing here\nCREATE INDEX i ON t(x);", encoding="utf-8")
    assert_error(capsys, [path], "no CREATE TABLE statements")


def test_no_output_is_written_when_parsing_fails(tmp_path):
    path = tmp_path / "bad.sql"
    path.write_text("CREATE TABLE", encoding="utf-8")
    output = tmp_path / "bad.svg"
    assert main([str(path), "-o", str(output)]) == 1
    assert not output.exists()


# --- output errors ---


@needs_graphviz
def test_unknown_output_format(tmp_path, sql_file, capsys):
    assert_error(capsys, [sql_file, "-o", tmp_path / "x.nope"], "Unknown output format '.nope'")


@needs_graphviz
def test_output_path_is_a_directory(tmp_path, sql_file, capsys):
    folder = tmp_path / "taken.svg"
    folder.mkdir()
    assert_error(capsys, [sql_file, "-o", folder], "Can't write")


def test_graphviz_not_installed(sql_file, tmp_path, capsys, monkeypatch):
    def not_found(*args):
        raise graphviz.ExecutableNotFound(["dot"])

    monkeypatch.setattr(render_dot, "render", not_found)
    assert_error(capsys, [sql_file, "-o", tmp_path / "x.svg"], "Graphviz isn't installed")


def test_graphviz_rejects_the_diagram(sql_file, tmp_path, capsys, monkeypatch):
    def rejected(*args):
        raise graphviz.CalledProcessError(1, ["dot"])

    monkeypatch.setattr(render_dot, "render", rejected)
    assert_error(capsys, [sql_file, "-o", tmp_path / "x.svg"], "Graphviz couldn't draw")


# --- arguments ---


@pytest.mark.parametrize("dpi", ["0", "-5", "abc", "1.5"])
def test_bad_dpi_is_rejected(sql_file, dpi, capsys):
    with pytest.raises(SystemExit) as exit_info:
        main([str(sql_file), f"--dpi={dpi}"])
    assert exit_info.value.code == 2
    assert "must be a whole number" in capsys.readouterr().err


def test_missing_input_argument():
    with pytest.raises(SystemExit) as exit_info:
        main([])
    assert exit_info.value.code == 2


# --- render() ---


@needs_graphviz
def test_render_leaves_neighboring_files_alone(tmp_path):
    # Source.render() used to overwrite and delete schema.sql here.
    neighbor = tmp_path / "schema.sql"
    neighbor.write_text("keep me", encoding="utf-8")
    render_dot.render("digraph { a -> b }", tmp_path / "schema.sql.svg")
    assert neighbor.read_text(encoding="utf-8") == "keep me"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["schema.sql", "schema.sql.svg"]


@needs_graphviz
def test_render_overwrites_its_own_output(tmp_path):
    output = tmp_path / "x.svg"
    output.write_text("old", encoding="utf-8")
    render_dot.render("digraph { a -> b }", output)
    assert "<svg" in output.read_text(encoding="utf-8")


@needs_graphviz
def test_render_creates_missing_folders(tmp_path):
    output = tmp_path / "a" / "b" / "x.svg"
    assert render_dot.render("digraph { a -> b }", output) == output
    assert output.exists()


@needs_graphviz
def test_render_without_extension_uses_svg(tmp_path):
    assert render_dot.render("digraph { a -> b }", tmp_path / "x") == tmp_path / "x.svg"


@needs_graphviz
def test_render_extension_is_case_insensitive(tmp_path):
    output = tmp_path / "x.PNG"
    render_dot.render("digraph { a -> b }", output)
    assert output.read_bytes().startswith(PNG_SIGNATURE)
