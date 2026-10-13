"""Safe arithmetic calculator."""

import ast
import operator

_context = None
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _evaluate(node):
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("Exponent magnitude must not exceed 100.")
        return _OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_evaluate(node.operand))
    raise ValueError("Only numeric arithmetic expressions are supported.")


def init(context):
    global _context
    _context = context


def register_commands(registry):
    def calculate(args):
        if not args:
            return "Usage: calc <expression>"
        try:
            return str(_evaluate(ast.parse(" ".join(args), mode="eval")))
        except (SyntaxError, ArithmeticError, ValueError) as exc:
            return f"Calculator error: {exc}"
    registry.register_command("calc", calculate)


def register_menu(menu):
    menu.append(("calc", "Calculator"))


def handle_event(event):
    return None
