"""对已通过 Form 表达式语法校验的 data 参数推导结果类型，不读取数据或求值。"""

from __future__ import annotations

from services.template_generation.engine.a2ui_expression import _tokenize

_PRECEDENCE = {
    "||": 1,
    "&&": 2,
    "==": 3,
    "!=": 3,
    "<": 4,
    ">": 4,
    "<=": 4,
    ">=": 4,
    "+": 5,
    "-": 5,
    "*": 6,
    "/": 6,
    "%": 6,
}


def expression_result_types(body: str, paths: dict[str, str]) -> set[str]:
    """调用前必须通过 normalize_tersel_expression 的语法和复杂度校验。"""
    tokens = _tokenize(body)
    index = 0

    def expression(minimum: int = 0) -> set[str]:
        nonlocal index
        token = tokens[index]
        index += 1
        result: set[str]
        if token.kind == "binding":
            data_type = paths.get(token.value)
            if data_type is None:
                raise ValueError("Expression type references an undeclared path")
            result = {data_type}
        elif token.kind == "literal":
            result = {"string"}
        elif token.kind == "number":
            result = {"number"}
        elif token.kind == "atom":
            result = {"boolean"}
        elif token.kind == "function":
            index += 1  # 已校验的 size( 参数。
            expression()
            index += 1
            result = {"number"}
        elif token.value == "(":
            result = expression()
            index += 1
        elif token.value in {"!", "-"}:
            expression(7)
            result = {"boolean" if token.value == "!" else "number"}
        else:
            raise ValueError("Expression type contains an unsupported operand")
        while index < len(tokens):
            operator = tokens[index].value
            priority = _PRECEDENCE.get(operator, -1)
            if priority < minimum:
                break
            index += 1
            right = expression(priority + 1)
            if operator == "+":
                combined: set[str] = set()
                for left_type in result:
                    for right_type in right:
                        combined.add("string" if "string" in {left_type, right_type} else "number")
                result = combined
            elif operator in {"-", "*", "/", "%"}:
                result = {"number"}
            elif operator in {"&&", "||"}:
                result = result | right
            else:
                result = {"boolean"}
        if minimum == 0 and index < len(tokens):
            if tokens[index].value == "?":
                index += 1
                present = expression()
                index += 1
                result = present | expression()
        return result

    result = expression()
    if index != len(tokens):
        raise ValueError("Expression type parser did not consume the validated expression")
    return result
