# func_style_predicate_parser.py
#
# Example:
#
#     >>> from func_style_predicate_parser import parse_predicate
#     >>> p = "or(and(greaterOrEquals(col,1),less(a,5)),  and(gt(b,7), lt(b,9)))"
#     >>> import pprint; pprint.pprint(parse_predicate(p), width=80)
#     ('OR',
#      [('AND',
#        ['greaterOrEquals(col,1)', 'less(a,5)']),
#       ('AND',
#        ['gt(b,7)', 'lt(b,9)'])])

from __future__ import annotations

op_list = [
    "equals",
    "notequals",
    "less",
    "lessorequals",
    "greater",
    "greaterorequals",
    "in",
    "ilike",
    "notilike",
    "or",
    "and"
]

class ParseError(ValueError):
    pass


# -----------------------------------------------------------------------------
# Recursive-descent parser for
#
#     expr  :=  or '(' expr_list ')'
#            |   and '(' expr_list ')'
#            |   ATOM
#
#     expr_list := expr ( ',' expr )*
#
# Everything that is not the *keyword* "or" / "and" followed immediately by '('
# is considered an ATOM and copied verbatim to the output.
# -----------------------------------------------------------------------------
def _skip_ws(s: str, i: int) -> int:
    while i < len(s) and s[i].isspace():
        i += 1
    return i


def _read_identifier(s: str, i: int) -> tuple[str, int]:
    start = i
    while i < len(s) and (s[i].isalnum() or s[i] in ['_', "'", '$', '%', '.']):
        i += 1
    if start == i:
        raise ParseError(f'identifier expected at position {i}')
    return s[start:i], i


def _parse_atom(s: str, i: int) -> tuple[str, int]:
    """
    Read everything up to the next ',' or ')' *at the current parenthesis depth*.
    Internal parentheses are respected so that e.g.
        greaterOrEquals(col, 10)
    is returned as **one** atom.
    """
    start = i
    depth = 0
    while i < len(s):
        ch = s[i]
        if ch == '(':
            depth += 1
        elif ch == ')':
            if depth == 0:
                break
            depth -= 1
        elif ch == ',' and depth == 0:
            break
        i += 1
    atom = s[start:i].strip()
    if not atom:
        raise ParseError(f'empty atom at position {start}')
    return atom, i


def _parse_expr(s: str, i: int) -> tuple[object, int]:
    i = _skip_ws(s, i)

    # ------------------------------------------------------------------ or/and
    ident, j = _read_identifier(s, i)
    ident_lc = ident.lower()

    if j < len(s) and s[j] == '(' and ident_lc in op_list:
        op = ident_lc
        i = j + 1                      # point past '('
        children: list[object] = []

        while True:
            child, i = _parse_expr(s, i)
            children.append(child)

            i = _skip_ws(s, i)
            if i >= len(s):
                raise ParseError("unexpected end of input (missing ')')")
            if s[i] == ',':
                i += 1                 # skip ','
                continue
            if s[i] == ')':
                i += 1                 # skip ')'
                break
            raise ParseError(f"expected ',' or ')' at position {i}")

        return [op, children], i

    # ------------------------------------------------------------------- ATOM
    return _parse_atom(s, i)


def parse_predicate(text: str) -> object:
    """
    Parse the *function style* predicate and return an abstract syntax tree.

    Inner nodes are ('OR', [...]) or ('AND', [...]); leaves are strings.
    A ParseError is raised on invalid input.
    """
    text = text.lower()
    tree, pos = _parse_expr(text, 0)
    pos = _skip_ws(text, pos)
    if pos != len(text):
        raise ParseError(f'trailing characters starting at position {pos}')
    return tree


# ---------------------------------------------------------------------- demo
if __name__ == '__main__':
    # EXAMPLE = """
    #     or(
    #         and(
    #             greaterOrEquals(tpch_1g_db.LINEITEM.L_QUANTITY, 6.00),
    #             lessOrEquals(tpch_1g_db.LINEITEM.L_QUANTITY, 21.00)
    #         ),
    #         and(
    #             greaterOrEquals(tpch_1g_db.LINEITEM.L_QUANTITY, 27.00),
    #             lessOrEquals(tpch_1g_db.LINEITEM.L_QUANTITY, 37.00)
    #         )
    #     )
    # """

    EXAMPLE = "and(greaterOrEquals(tpch_1g_db.LINEITEM.L_QUANTITY, 6.00), lessOrEquals(tpch_1g_db.LINEITEM.L_QUANTITY, 21.00), greaterOrEquals(tpch_1g_db.LINEITEM.L_QUANTITY, 27.00))"

    import pprint, json
    ast = parse_predicate(EXAMPLE)
    print('\nPretty-printed AST:\n')
    pprint.pprint(ast, width=100)

    print('\nJSON (to show it is plain data):\n')
    print(json.dumps(ast, indent=2))