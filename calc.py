"""Безопасный калькулятор для команды «счёт»: разбирает выражение само, без eval."""
import ast
import operator
from i18n import tr

OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError(tr("слишком большая степень"))
        return OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.operand))
    raise ValueError(tr("можно только числа и + - * / // % ** и скобки"))


def calculate(text):
    """'2+2*3' -> '8'. Ошибки: ValueError, ZeroDivisionError, SyntaxError, OverflowError."""
    expr = text.replace(",", ".").replace("^", "**").replace("×", "*").replace("÷", "/")
    result = _eval(ast.parse(expr.strip(), mode="eval").body)
    if isinstance(result, float) and result.is_integer() and abs(result) < 1e15:
        result = int(result)
    return f"{result:.10g}" if isinstance(result, float) else str(result)