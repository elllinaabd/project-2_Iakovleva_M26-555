VALID_TYPES = {"int", "str", "bool"}
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