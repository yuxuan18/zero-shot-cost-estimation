# full_predicate_parser.py
#
# Usage:
#     from full_predicate_parser import parse_predicate
#     tree = parse_predicate(big_predicate_string)

import re
from typing import List, Tuple, Union

Atom  = str
Node  = Tuple[str, List["Expr"]]      # ('AND' | 'OR', [Expr, ...])
Expr  = Union[Atom, Node]             # recursive type alias


# ---------------------------------------------------------------------------
# 1.  Tokeniser
# ---------------------------------------------------------------------------
_TOKEN_AND = "AND"
_TOKEN_OR  = "OR"
_TOKEN_LP  = "("
_TOKEN_RP  = ")"


def _tokenise(text: str) -> List[str]:
    """
    Turn the input string into a flat sequence of tokens:
        'AND'  'OR'  '('  ')'  <everything-else>
    The routine is aware of SQL-style single quoted strings; a quoted string is
    *never* split, even when it contains spaces, AND, OR, or parentheses.

    White-space outside quoted strings is discarded.
    """
    tokens: List[str] = []
    i, n = 0, len(text)
    buf: List[str] = []
    in_quote = False

    def flush_buffer() -> None:
        if buf:
            token = ''.join(buf)
            if token:                       # skip empty strings
                tokens.append(token)
            buf.clear()

    while i < n:
        ch = text[i]

        # --------------------------------------------------- inside quote
        if in_quote:
            buf.append(ch)
            if ch == "'":
                # doubled quote → escaped quote, *stay* inside the string
                if i + 1 < n and text[i + 1] == "'":
                    buf.append("'")
                    i += 1
                else:
                    in_quote = False
            i += 1
            continue

        # --------------------------------------------------- outside quote
        if ch.isspace():
            flush_buffer()
            i += 1
            continue

        if ch == "'":                       # start of quoted string
            buf.append(ch)
            in_quote = True
            i += 1
            continue

        if ch in "()":                      # single-char tokens
            flush_buffer()
            tokens.append(ch)
            i += 1
            continue

        # collect part of an ordinary token
        buf.append(ch)
        i += 1

    flush_buffer()

    # Canonicalise AND / OR (case-fold) so the parser only has to compare once
    for j, t in enumerate(tokens):
        if t.upper() == _TOKEN_AND:
            tokens[j] = _TOKEN_AND
        elif t.upper() == _TOKEN_OR:
            tokens[j] = _TOKEN_OR

    return tokens


# ---------------------------------------------------------------------------
# 2.  Recursive-descent parser  (precedence:  AND > OR)
# ---------------------------------------------------------------------------
class _Parser:
    def __init__(self, tokens: List[str]) -> None:
        self.toks = tokens
        self.pos  = 0

    # ------------- helpers
    def _current(self) -> str:
        if self.pos >= len(self.toks):
            raise ValueError("unexpected end of input")
        return self.toks[self.pos]

    def _eat(self, expected: str | None = None) -> str:
        tok = self._current()
        if expected is not None and tok != expected:
            raise ValueError(f"expected '{expected}', got '{tok}'")
        self.pos += 1
        return tok

    # ------------- grammar
    #
    #   expr  := term ( OR  term )*
    #   term  := factor ( AND factor )*
    #   factor:= '(' expr ')' | atom
    #   atom  := <any token that is **not** AND, OR, '(' or ')'>
    #
    def parse_expression(self) -> Expr:
        expr = self.parse_term()
        ors: List[Expr] = [expr]

        while self.pos < len(self.toks) and self._current() == _TOKEN_OR:
            self._eat(_TOKEN_OR)
            ors.append(self.parse_term())

        if len(ors) == 1:
            return ors[0]
        return (_TOKEN_OR, ors)

    def parse_term(self) -> Expr:
        term = self.parse_factor()
        ands: List[Expr] = [term]

        while self.pos < len(self.toks) and self._current() == _TOKEN_AND:
            self._eat(_TOKEN_AND)
            ands.append(self.parse_factor())

        if len(ands) == 1:
            return ands[0]
        return (_TOKEN_AND, ands)

    def parse_factor(self) -> Expr:
        tok = self._current()

        # -------------------------------------------------------- '(' expr ')'
        if tok == _TOKEN_LP:
            self._eat(_TOKEN_LP)
            inner = self.parse_expression()
            self._eat(_TOKEN_RP)
            # print(inner)
            return inner

        # -------------------------------------------------------- atomic term
        if tok in (_TOKEN_AND, _TOKEN_OR, _TOKEN_RP):
            raise ValueError(f"unexpected token '{tok}'")

        atom_parts: List[str] = []
        depth = 0                     # depth *inside* the atom itself
        while self.pos < len(self.toks):
            tok = self._current()

            # stop criteria — only at depth 0
            if depth == 0 and tok in (_TOKEN_AND, _TOKEN_OR, _TOKEN_RP):
                break

            # maintain internal depth for parentheses that are part of the atom
            if tok == _TOKEN_LP:
                depth += 1
            elif tok == _TOKEN_RP:
                depth -= 1

            atom_parts.append(self._eat())   # consume token

        return [atom_parts[1], atom_parts[0], "".join(atom_parts[2:])]

    # -------------------------------------------------------------
    # entry point
    # -------------------------------------------------------------
    def parse(self) -> Expr:
        tree = self.parse_expression()
        if self.pos != len(self.toks):
            raise ValueError(f"trailing tokens: {self.toks[self.pos:]}")
        return tree


# ---------------------------------------------------------------------------
# 3.  Public function
# ---------------------------------------------------------------------------
_ws_re = re.compile(r'\s+')


def parse_predicate(predicate: str) -> Expr:
    """
    Return an abstract syntax tree that represents *all* parentheses
    and operator precedence in the predicate.
    """
    # optional – turn every run of white-space into one blank.
    # makes later processing / pretty printing easier, does not influence parsing
    predicate = _ws_re.sub(" ", predicate).strip()

    tokens = _tokenise(predicate)
    return _Parser(tokens).parse()


# ---------------------------------------------------------------------------
# 4.  Demo / ad-hoc test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    PREDICATE = "((tpch_1g_db.PART.P_BRAND = 'Brand#13') AND (tpch_1g_db.PART.P_CONTAINER IN ('SM BOX', 'SM CASE', 'SM PACK', 'SM PKG')) AND (tpch_1g_db.LINEITEM.L_QUANTITY >= 6.00) AND (tpch_1g_db.LINEITEM.L_QUANTITY <= 16.00) AND (tpch_1g_db.PART.P_SIZE <= 5)) OR ((tpch_1g_db.PART.P_BRAND = 'Brand#43') AND (tpch_1g_db.PART.P_CONTAINER IN ('MED BAG', 'MED BOX', 'MED PACK', 'MED PKG')) AND (tpch_1g_db.LINEITEM.L_QUANTITY >= 11.00) AND (tpch_1g_db.LINEITEM.L_QUANTITY <= 21.00) AND (tpch_1g_db.PART.P_SIZE <= 10)) OR ((tpch_1g_db.PART.P_BRAND = 'Brand#55') AND (tpch_1g_db.PART.P_CONTAINER IN ('LG BOX', 'LG CASE', 'LG PACK', 'LG PKG')) AND (tpch_1g_db.LINEITEM.L_QUANTITY >= 27.00) )"

    tree = parse_predicate(PREDICATE)
    import pprint, json
    print("Pretty printed AST:\n")
    pprint.pprint(tree, width=120)

    print("\nJSON representation (just to show it’s plain data):\n")
    print(json.dumps(tree, indent=2))