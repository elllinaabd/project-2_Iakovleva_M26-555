"""Разбор значений и условий вида: age = 28, name = "Sergei"."""

from primitive_db.constants import QUOTES


def _split_outside_quotes(text, separator=","):
    """Делит строку по разделителю, не трогая разделители внутри кавычек"""
    parts, current, quote = [], "", None

    for char in text:
        if quote:
            if char == quote:
                quote = None
        elif char in QUOTES:
            quote = char
        elif char == separator:
            parts.append(current)
            current = ""
            continue
        current += char

    if quote:
        raise ValueError(text)  # незакрытая кавычка

    parts.append(current)
    return parts


def parse_value(raw):
    """Превращает текст в значение Python: "abc" -> str, 28 -> int, true -> bool.

    Строки обязательно должны быть в кавычках.
    """
    raw = raw.strip()

    if len(raw) >= 2 and raw[0] in QUOTES and raw[-1] == raw[0]:
        return raw[1:-1]

    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"

    try:
        return int(raw)
    except ValueError:
        raise ValueError(raw) from None


def parse_values(text):
    """'"Sergei", 28, true' -> ['Sergei', 28, True]."""
    if not text.strip():
        return []
    return [parse_value(part) for part in _split_outside_quotes(text)]


def _parse_assignment(text):
    """'age = 28' -> ('age', 28)."""
    column, sep, raw_value = text.partition("=")
    column = column.strip()
    if not sep or not column.isidentifier() or not raw_value.strip():
        raise ValueError(text.strip())
    return column, parse_value(raw_value)


def parse_where(text):
    """'age = 28' -> {'age': 28}. Поддерживается одно условие."""
    column, value = _parse_assignment(text)
    return {column: value}


def parse_set(text):
    """'age = 29, name = "Ivan"' -> {'age': 29, 'name': 'Ivan'}."""
    clause = {}
    for part in _split_outside_quotes(text):
        column, value = _parse_assignment(part)
        clause[column] = value
    return clause