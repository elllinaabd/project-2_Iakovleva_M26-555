VALID_TYPES = {"int": int, "str": str, "bool": bool}
ID_COLUMN = "ID"


def _parse_columns(columns):

    parsed = {ID_COLUMN: "int"}

    for column in columns:
        name, sep, col_type = column.partition(":")
        if not sep or not name.isidentifier() or col_type not in VALID_TYPES:
            print(f"Некорректное значение: {column}. Попробуйте снова.")
            return None

        if name == ID_COLUMN:
            # Пользователь сам задал ID — допускаем только тип int.
            if col_type != "int":
                print(f"Некорректное значение: {column}. Попробуйте снова.")
                return None
            continue

        if name in parsed:
            print(f'Ошибка: Столбец "{name}" указан несколько раз.')
            return None

        parsed[name] = col_type

    return parsed


def create_table(metadata, table_name, columns):
    if not table_name.isidentifier():
        print(f"Некорректное значение: {table_name}. Попробуйте снова.")
        return None

    if table_name in metadata:
        print(f'Ошибка: Таблица "{table_name}" уже существует.')
        return None

    parsed = _parse_columns(columns)
    if parsed is None:
        return None

    metadata[table_name] = {"columns": parsed}

    columns_str = ", ".join(f"{name}:{col_type}" for name, col_type in parsed.items())
    print(f'Таблица "{table_name}" успешно создана со столбцами: {columns_str}')
    return metadata


def drop_table(metadata, table_name):
    if table_name not in metadata:
        print(f'Ошибка: Таблица "{table_name}" не существует.')
        return None

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
    """Проверяет, что столбцы из условия есть в таблице и типы значений верны."""
    for column, value in clause.items():
        if column not in columns:
            print(f'Ошибка: Столбца "{column}" нет в таблице.')
            return False
        if not _type_matches(value, columns[column]):
            print(f"Некорректное значение: {value!r}. Попробуйте снова.")
            return False
    return True


# ---------- CRUD ----------


def insert(metadata, table_name, values, table_data):
    """Добавляет запись"""
    if not table_exists(metadata, table_name):
        return None

    columns = get_columns(metadata, table_name)
    user_columns = [name for name in columns if name != ID_COLUMN]

    if len(values) != len(user_columns):
        print(
            f"Ошибка: ожидается значений: {len(user_columns)}, получено: {len(values)}."
        )
        return None

    record = dict(zip(user_columns, values))
    if not validate_clause(columns, record):
        return None

    new_id = max((row[ID_COLUMN] for row in table_data), default=0) + 1
    table_data.append({ID_COLUMN: new_id, **record})

    print(f'Запись с ID={new_id} успешно добавлена в таблицу "{table_name}".')
    return table_data


def _matches(row, where_clause):
    return all(row.get(column) == value for column, value in where_clause.items())


def select(table_data, where_clause=None):
    """Возвращает все записи или только подходящие под where_clause."""
    if not where_clause:
        return table_data
    return [row for row in table_data if _matches(row, where_clause)]


def update(table_data, set_clause, where_clause):
    """Обновляет поля из set_clause у записей, подходящих под where_clause."""
    for row in table_data:
        if _matches(row, where_clause):
            row.update(set_clause)
    return table_data


def delete(table_data, where_clause):
    """Удаляет записи, подходящие под where_clause."""
    return [row for row in table_data if not _matches(row, where_clause)]
