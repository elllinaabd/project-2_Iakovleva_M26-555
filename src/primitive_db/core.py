import json
from copy import deepcopy

from primitive_db.decorators import (
    confirm_action,
    create_cacher,
    handle_db_errors,
    log_time,
)

VALID_TYPES = {"int": int, "str": str, "bool": bool}
ID_COLUMN = "ID"


_cache_select = create_cacher()


def _parse_columns(columns):
    """Проверяет описание столбцов и возвращает схему таблицы"""
    parsed = {ID_COLUMN: "int"}

    for column in columns:
        name, sep, col_type = column.partition(":")

        if not sep or not name.isidentifier() or col_type not in VALID_TYPES:
            raise ValueError(
                f'некорректное описание столбца "{column}". '
                "Используйте формат имя:тип; допустимые типы: int, str, bool."
            )

        if name == ID_COLUMN:
            if col_type != "int":
                raise ValueError("столбец ID должен иметь тип int.")
            continue

        if name in parsed:
            raise ValueError(f'столбец "{name}" указан несколько раз.')

        parsed[name] = col_type

    return parsed


@handle_db_errors
def create_table(metadata, table_name, columns):
    """Создаёт таблицу с указанными столбцами."""
    if not table_name.isidentifier():
        raise ValueError(f'некорректное имя таблицы "{table_name}".')

    if table_name in metadata:
        raise ValueError(f'таблица "{table_name}" уже существует.')

    parsed = _parse_columns(columns)
    metadata[table_name] = {"columns": parsed}

    columns_str = ", ".join(
        f"{name}:{col_type}" for name, col_type in parsed.items()
    )
    print(f'Таблица "{table_name}" успешно создана со столбцами: {columns_str}')
    return metadata


@handle_db_errors
@confirm_action("удаление таблицы")
def drop_table(metadata, table_name):
    """Удаляет таблицу из метаданных."""
    if table_name not in metadata:
        raise KeyError(table_name)

    del metadata[table_name]
    print(f'Таблица "{table_name}" успешно удалена.')
    return metadata


def list_tables(metadata):
    if not metadata:
        print("Таблиц пока нет.")
        return

    for table_name in metadata:
        print(f"- {table_name}")

def table_exists(metadata, table_name):
    """Проверяет, что таблица есть"""
    if table_name not in metadata:
        print(f'Ошибка: Таблица "{table_name}" не существует.')
        return False
    return True


def get_columns(metadata, table_name):
    """Возвращает схему таблицы"""
    return metadata[table_name]["columns"]


def _type_matches(value, col_type):
    return type(value) is VALID_TYPES[col_type]


def validate_clause(columns, clause):
    """Проверяет наличие столбцов и соответствие типов значений"""
    for column, value in clause.items():
        if column not in columns:
            raise KeyError(column)

        if not _type_matches(value, columns[column]):
            raise ValueError(
                f'для столбца "{column}" ожидается тип '
                f'{columns[column]}, получено значение {value!r}.'
            )

    return True


# ---------- CRUD ----------

@handle_db_errors
@log_time
def insert(metadata, table_name, values, table_data):
    """Добавляет запись в таблицу."""
    if table_name not in metadata:
        raise KeyError(table_name)

    columns = get_columns(metadata, table_name)
    user_columns = [name for name in columns if name != ID_COLUMN]

    if len(values) != len(user_columns):
        raise ValueError(
            f"ожидается значений: {len(user_columns)}, "
            f"получено: {len(values)}."
        )

    record = dict(zip(user_columns, values))
    validate_clause(columns, record)

    new_id = max((row[ID_COLUMN] for row in table_data), default=0) + 1
    table_data.append({ID_COLUMN: new_id, **record})

    print(f'Запись с ID={new_id} успешно добавлена в таблицу "{table_name}".')
    return table_data


def _matches(row, where_clause):
    return all(row.get(column) == value for column, value in where_clause.items())

@handle_db_errors
@log_time
def select(table_data, where_clause=None):
    """Возвращает записи, используя кэш одинаковых запросов."""
    key = json.dumps(
        [table_data, where_clause],
        ensure_ascii=False,
        sort_keys=True,
    )

    def get_records():
        if not where_clause:
            records = table_data
        else:
            records = [
                row
                for row in table_data
                if _matches(row, where_clause)
            ]

        return deepcopy(records)

    cached_records = _cache_select(key, get_records)
    return deepcopy(cached_records)


def update(table_data, set_clause, where_clause):
    """Обновляет поля из set_clause у записей, подходящих под where_clause."""
    for row in table_data:
        if _matches(row, where_clause):
            row.update(set_clause)
    return table_data

@handle_db_errors
@confirm_action("удаление записей")
def delete(table_data, where_clause):
    """Удаляет записи, подходящие под where_clause."""
    return [row for row in table_data if not _matches(row, where_clause)]
