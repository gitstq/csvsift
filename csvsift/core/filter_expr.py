"""安全行过滤表达式求值器。

设计要点：**绝不使用 eval**。基于 ast 解析 + 白名单节点遍历，
仅允许：列名变量、数字/字符串/布尔/None 字面量、比较运算、
算术运算、and/or/not、in 成员判断。

非法节点一律抛出 FilterSyntaxError，从机制上杜绝代码注入。
"""

from __future__ import annotations

import ast
import operator
from typing import Any

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}

_ALLOWED_CMPOPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

_ALLOWED_UNARYOPS = {
    ast.Not: operator.not_,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_ALLOWED_CONST_TYPES = (int, float, str, bool, type(None))


class FilterSyntaxError(ValueError):
    """过滤表达式不合法。"""


def compile_filter(expression: str):
    """编译过滤表达式为可调用 f(row_dict) -> bool。

    支持示例：
        age > 30
        name == "Alice" and score >= 60
        city in ("北京", "上海")
        price * qty > 1000
    列名既可用裸标识符（自动匹配表头），也可用 $col 形式。
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise FilterSyntaxError(f"表达式语法错误: {exc}") from exc
    _validate(tree.body)
    return _Evaluator(tree.body)


def _validate(node: ast.AST) -> None:
    """递归校验 AST 仅包含白名单节点。"""
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, _ALLOWED_CONST_TYPES):
            raise FilterSyntaxError(f"不支持的字面量类型: {type(node.value).__name__}")
        return
    if isinstance(node, ast.BoolOp):
        if not isinstance(node.op, (ast.And, ast.Or)):
            raise FilterSyntaxError("仅支持 and / or")
        for child in node.values:
            _validate(child)
        return
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        _validate(node.operand)
        return
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        _validate(node.left)
        _validate(node.right)
        return
    if isinstance(node, ast.Compare) and all(type(op) in _ALLOWED_CMPOPS for op in node.ops):
        _validate(node.left)
        for comparator in node.comparators:
            _validate(comparator)
        return
    if isinstance(node, ast.Name):
        return  # 列名，运行时绑定
    if isinstance(node, ast.Tuple):
        for elt in node.elts:
            _validate(elt)
        return
    raise FilterSyntaxError(f"表达式包含不允许的语法: {type(node).__name__}")


class _Evaluator:
    """受限求值器：把列名解析为行数据值，缺失列视为 None。"""

    def __init__(self, node: ast.AST):
        self._node = node

    def __call__(self, row: dict[str, str]) -> bool:
        return bool(self._eval(self._node, row))

    def _eval(self, node: ast.AST, row: dict[str, str]) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            name = node.id
            if name.startswith("$"):
                name = name[1:]
            return _auto_type(row.get(name))
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(self._eval(v, row) for v in node.values)
            return any(self._eval(v, row) for v in node.values)
        if isinstance(node, ast.UnaryOp):
            value = self._eval(node.operand, row)
            return _ALLOWED_UNARYOPS[type(node.op)](value)
        if isinstance(node, ast.BinOp):
            left = self._eval(node.left, row)
            right = self._eval(node.right, row)
            return _ALLOWED_BINOPS[type(node.op)](left, right)
        if isinstance(node, ast.Compare):
            left = self._eval(node.left, row)
            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval(comparator, row)
                # 缺失列(None)参与大小比较时安全短路为 False，== / != 正常执行
                if (left is None or right is None) and type(op) not in (ast.Eq, ast.NotEq):
                    return False
                try:
                    if not _ALLOWED_CMPOPS[type(op)](left, right):
                        return False
                except TypeError:
                    return False
                left = right
            return True
        if isinstance(node, ast.Tuple):
            return tuple(self._eval(elt, row) for elt in node.elts)
        raise FilterSyntaxError(f"运行时遇到不允许的节点: {type(node).__name__}")


def _auto_type(value: str | None):
    """单元格值自动类型提升：空 -> None，可解析则转 int/float。"""
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value
