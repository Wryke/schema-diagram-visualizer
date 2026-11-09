"""Phase 3 and 6: a recursive-descent parser from tokens to a Schema.

One method per grammar rule (see ROADMAP.md, Phase 3). Each method reads the
tokens for its rule and returns a piece of the model.

Real schemas use clauses this parser has no use for, so it skips what it doesn't
understand and records a warning. Text that can't be a table at all, like a
missing ")", is still a ParseError.
"""

from schemadiagram.model import Column, ForeignKey, Schema, Table
from schemadiagram.tokenizer import Token, TokenType, tokenize

KEYWORD = TokenType.KEYWORD
IDENTIFIER = TokenType.IDENTIFIER
SYMBOL = TokenType.SYMBOL
OPERATOR = TokenType.OPERATOR

# Keywords that start a table constraint rather than a column definition.
TABLE_CONSTRAINT_STARTS = {"CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK"}

# Keywords that can't be a table or column name. Others, like key and action, can.
RESERVED_WORDS = TABLE_CONSTRAINT_STARTS | {"CREATE", "TABLE", "REFERENCES", "DEFAULT", "NOT", "NULL"}

# Keywords that end a DEFAULT value, because the next column constraint starts there.
DEFAULT_ENDS = {"CONSTRAINT", "PRIMARY", "NOT", "NULL", "UNIQUE", "DEFAULT", "CHECK", "REFERENCES", "ON"}

# Words after a column's type that describe the column. They end the type, and a DEFAULT value.
COLUMN_ATTRIBUTES = {
    "AUTO_INCREMENT", "AUTOINCREMENT", "IDENTITY", "GENERATED", "AS", "COLLATE", "COMMENT", "CHARSET", "SRID",
}

# Words in a column definition that don't affect the diagram, so they're skipped without a warning.
IGNORED_COLUMN_WORDS = {
    "ASC", "DESC", "CLUSTERED", "NONCLUSTERED", "ENFORCED", "DEFERRABLE", "INITIALLY", "DEFERRED",
    "IMMEDIATE", "STORED", "VIRTUAL", "PERSISTED", "ROWGUIDCOL", "SPARSE", "FIRST",
}

# Words between NOT and what it applies to, other than NULL: NOT DEFERRABLE, NOT ENFORCED
AFTER_NOT = {"DEFERRABLE", "ENFORCED", "VALID", "FOR"}

# Words between CREATE and TABLE.
CREATE_TABLE_QUALIFIERS = {"OR", "REPLACE", "TEMP", "TEMPORARY", "UNLOGGED", "GLOBAL", "LOCAL", "EXTERNAL", "VIRTUAL", "FOREIGN"}

# Words after a table's name that mean its columns are defined somewhere else.
NO_COLUMN_LIST = {"AS", "LIKE", "PARTITION", "OF", "CLONE", "USING"}

# Words that start a MySQL index inside CREATE TABLE.
INDEX_WORDS = {"KEY", "INDEX", "FULLTEXT", "SPATIAL"}

# Table items that don't add a column, and aren't worth reading.
SKIPPED_TABLE_ITEMS = {"EXCLUDE", "PERIOD", "LIKE"}

# Operators spelled as words. The tokenizer sees these as identifiers, but "(" after one isn't a call.
WORD_OPERATORS = {"AND", "OR", "IN", "LIKE", "ILIKE", "BETWEEN", "IS", "ANY", "ALL", "SOME"}


class ParseError(Exception):
    def __init__(self, message: str, token: Token):
        super().__init__(f"{message} at line {token.line}, col {token.column}")
        self.token = token


def describe(token: Token) -> str:
    """How a token reads in an error message."""
    return "end of file" if token.type is TokenType.EOF else repr(token.value)


def word(token: Token) -> str:
    """A token's unquoted word in uppercase, or "" if it isn't one. [index] and "as" aren't words."""
    return token.raw.upper() if token.type in {KEYWORD, IDENTIFIER} else ""


def token_text(token: Token) -> str:
    """A token as SQL text. Strings get back the quotes the tokenizer removed."""
    if token.type is TokenType.STRING:
        return "'" + token.value.replace("'", "''") + "'"
    return token.value


def needs_space(previous: Token, token: Token) -> bool:
    """Whether a space belongs between two tokens when writing them back out."""
    if token.type is SYMBOL and token.value in {")", ",", ".", ";", "[", "]"}:
        return False
    if previous.type is SYMBOL and previous.value in {"(", ".", "["}:
        return False
    if OPERATOR in {previous.type, token.type} and "::" in {previous.value, token.value}:
        return False
    # A string prefix stays attached: N'text', E'text'
    if token.type is TokenType.STRING and previous.type is IDENTIFIER and (
        previous.line == token.line and previous.column + len(previous.raw) == token.column
    ):
        return False
    # No space in a type or function call: VARCHAR(255), lower(email). But x IN (1, 2) keeps its space.
    if token.type is SYMBOL and token.value == "(":
        if previous.type is IDENTIFIER:
            return previous.value.upper() in WORD_OPERATORS
        return not (previous.type is KEYWORD and previous.value == "SET")  # MySQL's SET('a', 'b') type
    return True


def is_unary_sign(tokens: list[Token], i: int) -> bool:
    """True if tokens[i] is a sign on a value, as in -1, rather than a subtraction."""
    token = tokens[i]
    if token.type is not OPERATOR or token.value not in {"+", "-"}:
        return False
    if i == 0:
        return True
    previous = tokens[i - 1]
    return previous.type in {OPERATOR, KEYWORD} or (previous.type is SYMBOL and previous.value in {"(", ","})


def tokens_to_text(tokens: list[Token]) -> str:
    """Write tokens back out as tidy SQL text, e.g. for a type or a CHECK expression."""
    parts: list[str] = []
    for i, token in enumerate(tokens):
        if i > 0 and not is_unary_sign(tokens, i - 1) and needs_space(tokens[i - 1], token):
            parts.append(" ")
        parts.append(token_text(token))
    return "".join(parts)


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0
        self.warnings: list[str] = []

    # --- helpers ---------------------------------------------------------

    def peek(self, offset: int = 0) -> Token:
        """The token `offset` places ahead, without consuming it. Stops at EOF."""
        return self.tokens[min(self.pos + offset, len(self.tokens) - 1)]

    def advance(self) -> Token:
        """Consume the current token and return it."""
        token = self.tokens[self.pos]
        if token.type is not TokenType.EOF:
            self.pos += 1
        return token

    def check(self, type_: TokenType, value: str | None = None) -> bool:
        """True if the current token matches. Consumes nothing."""
        token = self.peek()
        return token.type is type_ and (value is None or token.value.upper() == value.upper())

    def match(self, type_: TokenType, value: str | None = None) -> bool:
        """If the current token matches, consume it and return True."""
        if self.check(type_, value):
            self.advance()
            return True
        return False

    def expect(self, type_: TokenType, value: str | None = None) -> Token:
        """Consume a token that must match, or raise ParseError."""
        if self.check(type_, value):
            return self.advance()
        token = self.peek()
        raise ParseError(f"Expected {value or type_.name} but found {describe(token)}", token)

    def warn(self, message: str, token: Token) -> None:
        self.warnings.append(f"{message} (line {token.line})")

    def at_create_table(self) -> bool:
        """True at CREATE [TEMP, OR REPLACE, ...] TABLE."""
        if not self.check(KEYWORD, "CREATE"):
            return False
        offset = 1
        while word(self.peek(offset)) in CREATE_TABLE_QUALIFIERS:
            offset += 1
        return word(self.peek(offset)) == "TABLE"

    def at_alter_table(self) -> bool:
        return self.check(KEYWORD, "ALTER") and word(self.peek(1)) == "TABLE"

    def at_new_statement(self) -> bool:
        """True at a table statement that starts a line. It ends whatever came before,
        even if a ";" is missing, so one unfinished statement can't swallow a table.
        """
        if self.peek().column != 1:
            return False
        return self.at_create_table() or self.at_alter_table() or word(self.peek()) == "DELIMITER"

    def at_delimiter_reset(self) -> bool:
        """True at DELIMITER ; which puts statement endings back to normal. DELIMITER ;; doesn't."""
        if word(self.peek()) != "DELIMITER" or self.peek(1).value != ";":
            return False
        return not (self.peek(2).value == ";" and self.peek(2).line == self.peek(1).line)

    def skip_delimiter_block(self) -> None:
        """Consume a MySQL DELIMITER block, up to the DELIMITER ; that ends it.

        The blocks exist to hold routines, whose bodies have statements of their own.
        A CREATE TEMPORARY TABLE in one of those isn't part of the schema.
        """
        first = self.peek()
        while not self.at_delimiter_reset():
            if self.check(TokenType.EOF):
                self.warn("DELIMITER is never set back to ;, so the rest of the file was skipped", first)
                return
            self.advance()

    def skip_statement(self) -> None:
        """Consume everything up to and including the next ';', or up to the next table statement."""
        while not self.check(TokenType.EOF) and not self.at_new_statement():
            if self.match(SYMBOL, ";"):
                return
            self.advance()

    def skip_item_rest(self) -> None:
        """Consume the rest of a table item, up to the "," or ")" or ";" that ends it."""
        while not self.check(TokenType.EOF) and not any(self.check(SYMBOL, end) for end in (",", ")", ";")):
            self.skip_one()

    def skip_one(self) -> None:
        """Consume one token, or one whole "(" ... ")"."""
        if self.check(SYMBOL, "("):
            self.read_parenthesized()
        else:
            self.advance()

    def read_parenthesized(self) -> list[Token]:
        """Consume a balanced "(" ... ")" and return its tokens, parentheses included."""
        opening = self.expect(SYMBOL, "(")
        tokens = [opening]
        depth = 1

        while depth > 0:
            if self.check(TokenType.EOF):
                raise ParseError("Unclosed '('", opening)
            token = self.advance()
            if token.type is SYMBOL and token.value == "(":
                depth += 1
            elif token.type is SYMBOL and token.value == ")":
                depth -= 1
            tokens.append(token)

        return tokens

    def read_brackets(self) -> list[Token]:
        """Consume a "[" ... "]" and return its tokens, brackets included."""
        opening = self.expect(SYMBOL, "[")
        tokens = [opening]

        while not self.check(SYMBOL, "]"):
            if self.check(TokenType.EOF):
                raise ParseError("Unclosed '['", opening)
            tokens.append(self.advance())

        tokens.append(self.advance())
        return tokens

    # --- statements ------------------------------------------------------

    def parse_schema(self) -> Schema:
        """schema := statement* EOF"""
        schema = Schema()

        while not self.check(TokenType.EOF):
            if self.at_create_table():
                first = self.peek()
                table = self.parse_create_table()
                if table is not None:
                    if schema.table(table.name) is not None:
                        self.warn(f"Table {table.name} is defined more than once", first)
                    schema.tables.append(table)
            elif self.at_alter_table():
                self.parse_alter_table(schema)
            elif word(self.peek()) == "DELIMITER":
                self.skip_delimiter_block()
                self.advance()  # the DELIMITER of DELIMITER ; so the skip below can't stop on it
            # After a table this skips options like ENGINE=InnoDB; otherwise the whole statement.
            self.skip_statement()

        self.resolve_references(schema)
        schema.warnings = self.warnings
        return schema

    def resolve_references(self, schema: Schema) -> None:
        """Check every foreign key against the finished schema, and fill in REFERENCES users,
        which means users' primary key. This waits until every table is parsed, because a
        foreign key can name a table that comes later in the file.
        """
        for table in schema.tables:
            for fk in table.foreign_keys:
                label = f"{table.name}.{', '.join(fk.from_columns)}"

                for name in fk.from_columns:
                    if table.column(name) is None:
                        self.warnings.append(f"Foreign key on {table.name} uses unknown column {name}")

                target = schema.table(fk.to_table)
                if target is None:
                    self.warnings.append(f"{label} references {fk.to_table}, which isn't in this file")
                    continue

                if not fk.to_columns:
                    fk.to_columns = list(target.primary_key)
                    if not fk.to_columns:
                        self.warnings.append(f"{label} references {fk.to_table}, which has no primary key")
                        continue

                for name in fk.to_columns:
                    if target.column(name) is None:
                        self.warnings.append(f"{label} references unknown column {fk.to_table}.{name}")
                if len(fk.to_columns) != len(fk.from_columns):
                    self.warnings.append(f"{label} doesn't match the number of columns in {fk.to_table}")

    def parse_create_table(self) -> Table | None:
        """create_table := CREATE [qualifiers] TABLE [IF NOT EXISTS] qualified_name
                           "(" table_item ("," table_item)* ")"

        Returns None for a table with no column list, like CREATE TABLE a AS SELECT ...
        """
        self.expect(KEYWORD, "CREATE")
        while word(self.peek()) in CREATE_TABLE_QUALIFIERS:
            self.advance()
        self.expect(KEYWORD, "TABLE")
        if self.match(KEYWORD, "IF"):
            self.expect(KEYWORD, "NOT")
            self.expect(KEYWORD, "EXISTS")

        table = Table(self.parse_qualified_name())

        if word(self.peek()) in NO_COLUMN_LIST:
            self.warn(f"Skipped table {table.name}, which has no column list", self.peek())
            return None

        self.expect(SYMBOL, "(")
        self.parse_table_item(table)
        while self.match(SYMBOL, ","):
            self.parse_table_item(table)
        self.expect(SYMBOL, ")")

        self.apply_single_column_uniques(table)
        return table

    def parse_alter_table(self, schema: Schema) -> None:
        """alter_table := ALTER TABLE [IF EXISTS] [ONLY] qualified_name action ("," action)*

        Only ADD changes the diagram. An action it can't read becomes a warning, since
        ALTER TABLE has far more forms than matter here.
        """
        first = self.expect(KEYWORD, "ALTER")
        self.expect(KEYWORD, "TABLE")
        if self.match(KEYWORD, "IF"):
            self.expect(KEYWORD, "EXISTS")
        if word(self.peek()) == "ONLY":
            self.advance()

        name = self.parse_qualified_name()
        table = schema.table(name)
        if table is None:
            self.warn(f"ALTER TABLE names {name}, which isn't defined before this point", first)
            return

        while not self.check(TokenType.EOF) and not self.check(SYMBOL, ";") and not self.at_new_statement():
            try:
                if self.match(KEYWORD, "ADD"):
                    self.parse_alter_add(table)
                elif self.match(KEYWORD, "ALTER"):
                    self.parse_alter_column(table)
                else:
                    self.skip_one()
            except ParseError as e:
                self.warnings.append(f"Skipped part of ALTER TABLE {table.name}: {e}")

    def parse_alter_column(self, table: Table) -> None:
        """alter_column := ALTER [COLUMN] name (ADD generated | SET NOT NULL | SET DEFAULT value)

        pg_dump creates a table first and adds these afterward. ALTER has already been consumed.
        """
        if word(self.peek()) == "COLUMN":
            self.advance()
        column = table.column(self.parse_name())
        if column is None:
            return

        if self.check(KEYWORD, "ADD") and word(self.peek(1)) == "GENERATED":
            self.advance()
            self.parse_generated(column)
        elif self.match(KEYWORD, "SET"):
            if self.match(KEYWORD, "NOT"):
                self.expect(KEYWORD, "NULL")
                column.nullable = False
            elif self.match(KEYWORD, "DEFAULT"):
                self.set_default(column, self.parse_default())

    def parse_alter_add(self, table: Table) -> None:
        """alter_add := [COLUMN [IF NOT EXISTS]] table_item"""
        if word(self.peek()) == "COLUMN":
            self.advance()
            if self.match(KEYWORD, "IF"):
                self.expect(KEYWORD, "NOT")
                self.expect(KEYWORD, "EXISTS")
        self.parse_table_item(table, in_alter=True)
        self.apply_single_column_uniques(table)

    def apply_single_column_uniques(self, table: Table) -> None:
        """Move one-column UNIQUE constraints onto their columns. This waits until the
        whole table is read, because a constraint can come before the column it names.
        """
        for names in list(table.unique_sets):
            column = table.column(names[0])
            if len(names) == 1 and column is not None:
                column.unique = True
                table.unique_sets.remove(names)

    # --- table items -----------------------------------------------------

    def parse_table_item(self, table: Table, in_alter: bool = False) -> None:
        """table_item := index | column_def | table_constraint"""
        token = self.peek()
        if self.at_index_definition():
            self.skip_item_rest()
        elif token.type is KEYWORD and token.value in TABLE_CONSTRAINT_STARTS:
            self.parse_table_constraint(table)
        elif word(token) in SKIPPED_TABLE_ITEMS:
            self.warn(f"Skipped {token.value} in table {table.name}", token)
            self.skip_item_rest()
        else:
            table.columns.append(self.parse_column(table, in_alter))

    def at_index_definition(self) -> bool:
        """True at a MySQL index: [FULLTEXT | SPATIAL] (KEY | INDEX) [name] "(" column ...

        `key VARCHAR(10)` looks the same up to the "(". What follows tells them
        apart: an index lists column names, and a type holds numbers or strings.
        """
        first = word(self.peek())
        if first not in INDEX_WORDS:
            return False
        offset = 1
        if first in {"FULLTEXT", "SPATIAL"} and word(self.peek(1)) in {"KEY", "INDEX"}:
            offset = 2
        if self.peek(offset).type is IDENTIFIER:
            offset += 1
        inside = self.peek(offset + 1)
        is_open = self.peek(offset).type is SYMBOL and self.peek(offset).value == "("
        return is_open and inside.type is IDENTIFIER and word(inside) != "MAX"

    def parse_name(self) -> str:
        """name := IDENTIFIER | STRING | a keyword that isn't reserved, spelled as written

        SQLite accepts a string as a name, and writes some of its own tables that way.
        """
        token = self.peek()
        if token.type in {IDENTIFIER, TokenType.STRING}:
            return self.advance().value
        if token.type is KEYWORD and token.value not in RESERVED_WORDS:
            return self.advance().raw
        raise ParseError(f"Expected a name but found {describe(token)}", token)

    def parse_qualified_name(self) -> str:
        """qualified_name := name ("." name)*, keeping only the last part: dbo.Orders is Orders"""
        name = self.parse_name()
        while self.match(SYMBOL, "."):
            name = self.parse_name()
        return name

    def parse_name_list(self) -> list[str]:
        """name_list := "(" indexed_name ("," indexed_name)* ")" """
        self.expect(SYMBOL, "(")
        names = [self.parse_indexed_name()]
        while self.match(SYMBOL, ","):
            names.append(self.parse_indexed_name())
        self.expect(SYMBOL, ")")
        return names

    def parse_indexed_name(self) -> str:
        """indexed_name := name ["(" length ")"] [ASC | DESC], as in MySQL's a(10) or SQL Server's a ASC"""
        name = self.parse_name()
        if self.check(SYMBOL, "("):
            self.read_parenthesized()
        if word(self.peek()) in {"ASC", "DESC"}:
            self.advance()
        return name

    # --- columns ---------------------------------------------------------

    def parse_column(self, table: Table, in_alter: bool = False) -> Column:
        """column_def := name [type] column_constraint*

        Inline PRIMARY KEY and REFERENCES are recorded on the table, the same
        place their table-level forms go. A column in ALTER TABLE ends at ";".
        """
        column = Column(self.parse_name(), self.parse_type())
        while not self.check(SYMBOL, ",") and not self.check(SYMBOL, ")"):
            if in_alter and (self.check(SYMBOL, ";") or self.check(TokenType.EOF)):
                break
            self.parse_column_constraint(table, column)
        return column

    def at_type_word(self) -> bool:
        """True at a word that can be part of a type."""
        token = self.peek()
        if token.type is not IDENTIFIER or word(token) in COLUMN_ATTRIBUTES or word(token) in IGNORED_COLUMN_WORDS:
            return False
        # CHARACTER VARYING is a type, but CHARACTER SET utf8 describes the column.
        return not (word(token) == "CHARACTER" and word(self.peek(1)) == "SET")

    def parse_type(self) -> str:
        """type := word+ ["(" ... ")"] word* ["[" ... "]"]*, e.g. VARCHAR(255), TEXT[],
        TIMESTAMP(3) WITH TIME ZONE, public.citext. Empty for a SQLite column with no type.
        """
        tokens: list[Token] = []

        # SET is a keyword, but SET('a', 'b') is also a MySQL type.
        if self.check(KEYWORD, "SET") and self.peek(1).value == "(":
            tokens.append(self.advance())
        elif not self.at_type_word():
            return ""

        while True:
            if tokens and self.check(SYMBOL, "("):
                tokens.extend(self.read_parenthesized())
            elif self.check(SYMBOL, "["):
                tokens.extend(self.read_brackets())
            elif tokens and self.check(SYMBOL, ".") and self.peek(1).type is IDENTIFIER:
                tokens.append(self.advance())
                tokens.append(self.advance())
            elif self.at_type_word():
                tokens.append(self.advance())
            else:
                return tokens_to_text(tokens)

    def parse_column_constraint(self, table: Table, column: Column) -> None:
        """column_constraint := [CONSTRAINT name] ( PRIMARY KEY | KEY | NOT NULL | NULL | UNIQUE [KEY]
                                | DEFAULT value | CHECK "(" expr ")" | references | column_attribute )
        """
        constraint_name = self.parse_name() if self.match(KEYWORD, "CONSTRAINT") else None

        if self.match(KEYWORD, "PRIMARY"):
            self.expect(KEYWORD, "KEY")
            table.primary_key.append(column.name)
        elif self.match(KEYWORD, "KEY"):
            table.primary_key.append(column.name)  # MySQL: KEY alone on a column means PRIMARY KEY
        elif self.match(KEYWORD, "NOT"):
            if word(self.peek()) in AFTER_NOT:
                self.advance()
            else:
                self.expect(KEYWORD, "NULL")
                column.nullable = False
        elif self.match(KEYWORD, "NULL"):
            column.nullable = True
        elif self.match(KEYWORD, "UNIQUE"):
            self.match(KEYWORD, "KEY")
            column.unique = True
        elif self.match(KEYWORD, "DEFAULT"):
            self.set_default(column, self.parse_default())
        elif self.match(KEYWORD, "CHECK"):
            check = self.parse_check()
            # A column holds one check, so any further ones go on the table.
            if column.check is None:
                column.check = check
            else:
                table.checks.append(check)
        elif self.match(KEYWORD, "REFERENCES"):
            table.foreign_keys.append(self.parse_references(table.name, [column.name], constraint_name))
        else:
            self.parse_column_attribute(table, column)

    def parse_column_attribute(self, table: Table, column: Column) -> None:
        """column_attribute := a dialect's extra clause on a column, or anything else that's a word."""
        token = self.peek()
        name = word(token)

        if name in {"AUTO_INCREMENT", "AUTOINCREMENT"}:
            self.advance()
            column.auto_increment = True
        elif name == "IDENTITY":
            self.advance()
            column.auto_increment = True
            if self.check(SYMBOL, "("):
                self.read_parenthesized()  # IDENTITY(1, 1)
        elif name == "GENERATED":
            self.parse_generated(column)
        elif name == "AS":
            self.advance()  # a computed column: AS (price * 2)
            self.skip_one()
        elif name in {"COMMENT", "CHARSET", "SRID"}:
            self.advance()
            self.advance()
        elif name == "COLLATE":
            self.advance()
            self.parse_collation()
        elif name == "CHARACTER":
            self.advance()
            self.expect(KEYWORD, "SET")
            self.advance()
        elif name == "ON" and word(self.peek(1)) == "UPDATE":
            self.advance()
            self.advance()
            self.parse_default()  # MySQL: ON UPDATE CURRENT_TIMESTAMP
        elif name == "ON" and word(self.peek(1)) == "CONFLICT":
            self.advance()
            self.advance()
            self.advance()  # SQLite: ON CONFLICT REPLACE
        elif name in IGNORED_COLUMN_WORDS or name == "REPLICATION":
            self.advance()
        elif name:
            self.warn(f"Ignored {token.value} on column {table.name}.{column.name}", token)
            self.advance()
            if self.check(SYMBOL, "("):
                self.read_parenthesized()
        else:
            raise ParseError(f"Expected a column constraint but found {describe(token)}", token)

    def parse_generated(self, column: Column) -> None:
        """generated := GENERATED [ALWAYS | BY DEFAULT] AS (IDENTITY ["(" ... ")"] | "(" expr ")")"""
        self.advance()
        if word(self.peek()) == "ALWAYS":
            self.advance()
        elif word(self.peek()) == "BY":
            self.advance()
            self.expect(KEYWORD, "DEFAULT")

        if word(self.peek()) == "AS":
            self.advance()
        if word(self.peek()) == "IDENTITY":
            self.advance()
            column.auto_increment = True
        if self.check(SYMBOL, "("):
            self.read_parenthesized()

    def parse_collation(self) -> None:
        """collation := word ("." word)*, as in utf8mb4_bin or pg_catalog."default" """
        self.advance()
        while self.match(SYMBOL, "."):
            self.advance()

    def parse_default(self) -> str:
        """value := any tokens up to the next column constraint, "," or ")" """
        tokens: list[Token] = []

        while True:
            token = self.peek()
            if token.type is TokenType.EOF or (token.type is SYMBOL and token.value in {",", ")", ";"}):
                break
            # The first token is always the value itself, so DEFAULT NULL works.
            if tokens and token.type is KEYWORD and token.value in DEFAULT_ENDS:
                break
            if tokens and word(token) in COLUMN_ATTRIBUTES:
                break
            if self.check(SYMBOL, "("):
                tokens.extend(self.read_parenthesized())
            elif self.check(SYMBOL, "["):
                tokens.extend(self.read_brackets())
            else:
                tokens.append(self.advance())

        if not tokens:
            token = self.peek()
            raise ParseError(f"Expected a default value but found {describe(token)}", token)
        return tokens_to_text(tokens)

    def set_default(self, column: Column, value: str) -> None:
        """Store a DEFAULT. Postgres writes SERIAL as a default from a sequence, which means auto-increment."""
        if value.lower().startswith("nextval("):
            column.auto_increment = True
        else:
            column.default = value

    def parse_check(self) -> str:
        """"(" expr ")", kept as text without the outer parentheses."""
        return tokens_to_text(self.read_parenthesized()[1:-1])

    def parse_references(self, from_table: str, from_columns: list[str], name: str | None) -> ForeignKey:
        """references := REFERENCES qualified_name [name_list] (ON (DELETE | UPDATE) action | MATCH word)*

        REFERENCES has already been consumed by the caller.
        """
        to_table = self.parse_qualified_name()
        to_columns = self.parse_name_list() if self.check(SYMBOL, "(") else []
        on_delete = None

        while True:
            if word(self.peek()) == "MATCH":
                self.advance()
                self.advance()
            elif self.check(KEYWORD, "ON") and word(self.peek(1)) in {"DELETE", "UPDATE"}:
                self.advance()
                if self.match(KEYWORD, "DELETE"):
                    on_delete = self.parse_action()
                else:
                    self.expect(KEYWORD, "UPDATE")
                    self.parse_action()  # the model doesn't store ON UPDATE
            else:
                break

        return ForeignKey(from_table, from_columns, to_table, to_columns, name=name, on_delete=on_delete)

    def parse_action(self) -> str:
        """action := CASCADE | RESTRICT | SET NULL | SET DEFAULT | NO ACTION"""
        if self.match(KEYWORD, "CASCADE"):
            return "CASCADE"
        if self.match(KEYWORD, "RESTRICT"):
            return "RESTRICT"
        if self.match(KEYWORD, "SET"):
            if self.match(KEYWORD, "NULL"):
                return "SET NULL"
            self.expect(KEYWORD, "DEFAULT")
            return "SET DEFAULT"
        if self.match(KEYWORD, "NO"):
            self.expect(KEYWORD, "ACTION")
            return "NO ACTION"

        token = self.peek()
        raise ParseError(f"Expected a foreign key action but found {describe(token)}", token)

    # --- table constraints -----------------------------------------------

    def skip_words_before_list(self) -> None:
        """Skip what a dialect allows before a column list: USING BTREE, CLUSTERED, an index name."""
        while self.peek().type in {KEYWORD, IDENTIFIER} and not self.check(KEYWORD, "REFERENCES"):
            self.advance()

    def parse_table_constraint(self, table: Table) -> None:
        """table_constraint := [CONSTRAINT name] ( PRIMARY KEY name_list | UNIQUE name_list
                               | FOREIGN KEY name_list references | CHECK "(" expr ")" ) trailing_clauses
        """
        constraint_name = self.parse_name() if self.match(KEYWORD, "CONSTRAINT") else None

        if self.match(KEYWORD, "PRIMARY"):
            self.expect(KEYWORD, "KEY")
            self.skip_words_before_list()
            if self.check(SYMBOL, "("):
                for name in self.parse_name_list():
                    if not table.is_primary_key(name):
                        table.primary_key.append(name)
        elif self.match(KEYWORD, "UNIQUE"):
            self.skip_words_before_list()
            if self.check(SYMBOL, "("):
                table.unique_sets.append(self.parse_name_list())
        elif self.match(KEYWORD, "FOREIGN"):
            self.expect(KEYWORD, "KEY")
            self.skip_words_before_list()
            from_columns = self.parse_name_list()
            self.expect(KEYWORD, "REFERENCES")
            table.foreign_keys.append(self.parse_references(table.name, from_columns, constraint_name))
        elif self.match(KEYWORD, "CHECK"):
            table.checks.append(self.parse_check())
        elif self.check(KEYWORD, "DEFAULT"):
            pass  # SQL Server: ADD CONSTRAINT df_x DEFAULT 0 FOR x
        else:
            token = self.peek()
            self.warn(f"Skipped constraint {describe(token)} in table {table.name}", token)

        # NOT VALID, DEFERRABLE, ON [PRIMARY], WITH (...), and so on.
        self.skip_item_rest()


def parse(text: str) -> Schema:
    """Convenience entry point: SQL text in, Schema out. Anything skipped is in schema.warnings."""
    return Parser(tokenize(text)).parse_schema()
