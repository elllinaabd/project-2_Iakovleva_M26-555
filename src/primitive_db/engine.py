import shlex

import prompt
from prettytable import PrettyTable

from primitive_db.constants import ID_COLUMN, META_FILE, QUOTES
from primitive_db.core import (
    create_table,
    delete,
    drop_table,
    get_columns,
    insert,
    list_tables,
    select,
    table_exists,
    update,
    validate_clause,
)
from primitive_db.decorators import handle_db_errors
from primitive_db.parser import parse_set, parse_values, parse_where
from primitive_db.utils import (
    delete_table_data,
    load_metadata,
    load_table_data,
    save_metadata,
    save_table_data,
)


def _split_keyword(text, keyword):
    """Разделяет текст по отдельному ключевому слову вне кавычек."""
    quote = None
    keyword_length = len(keyword)

    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = None
            continue

        if char in QUOTES:
            quote = char
            continue

        if text[index:index + keyword_length].lower() != keyword:
            continue

        end = index + keyword_length
        left_boundary = index == 0 or text[index - 1].isspace()
        right_boundary = end == len(text) or text[end].isspace()

        if left_boundary and right_boundary:
            return text[:index].strip(), text[end:].strip()

    raise ValueError(f'ожидается ключевое слово "{keyword}".')


def parse_crud_command(command, user_input):
    """Разбирает структуру CRUD-команды и возвращает её аргументы."""
    parts = user_input.split(maxsplit=1)
    if len(parts) != 2:
        raise ValueError("не указаны аргументы команды.")

    body = parts[1].strip()

    if command == "insert":
        parts = body.split(maxsplit=2)
        if len(parts) != 3 or parts[0].lower() != "into":
            raise ValueError(
                "используйте: insert into <таблица> values (<значения>)."
            )

        _, table_name, values_part = parts
        keyword, separator, raw_values = values_part.partition("(")

        if (
            keyword.strip().lower() != "values"
            or not separator
            or not raw_values.endswith(")")
        ):
            raise ValueError("значения должны быть в скобках после values.")

        result = (table_name, raw_values[:-1].strip())

    elif command in ("select", "delete"):
        parts = body.split(maxsplit=2)
        if len(parts) < 2 or parts[0].lower() != "from":
            raise ValueError(f'после "{command}" ожидается from и имя таблицы.')

        table_name = parts[1]
        raw_where = None

        if len(parts) == 3:
            prefix, raw_where = _split_keyword(parts[2], "where")
            if prefix or not raw_where:
                raise ValueError("некорректное условие where.")

        if command == "delete" and raw_where is None:
            raise ValueError("для удаления записей укажите условие where.")

        result = (table_name, raw_where)

    elif command == "update":
        parts = body.split(maxsplit=2)
        if len(parts) != 3 or parts[1].lower() != "set":
            raise ValueError(
                "используйте: update <таблица> set <изменения> where <условие>."
            )

        table_name = parts[0]
        raw_set, raw_where = _split_keyword(parts[2], "where")

        if not raw_set or not raw_where:
            raise ValueError("укажите изменения после set и условие после where.")

        result = (table_name, raw_set, raw_where)

    else:
        raise ValueError(f'неизвестная CRUD-команда "{command}".')

    if not table_name.isidentifier():
        raise ValueError(f'некорректное имя таблицы "{table_name}".')

    return result

def print_help():
    """Выводит подсказки для текущего этапа"""

    print("\n***Операции с данными***")
    print("Функции:")
    print(
        "<command> insert into <имя_таблицы> values (<значение1>, <значение2>, ...)"
        " - создать запись."
    )
    print(
        "<command> select from <имя_таблицы> where <столбец> = <значение>"
        " - прочитать записи по условию."
    )
    print("<command> select from <имя_таблицы> - прочитать все записи.")
    print(
        "<command> update <имя_таблицы> set <столбец1> = <новое_значение1>"
        " where <столбец_условия> = <значение_условия> - обновить запись."
    )
    print(
        "<command> delete from <имя_таблицы> where <столбец> = <значение>"
        " - удалить запись."
    )
    print("<command> info <имя_таблицы> - вывести информацию о таблице.")

    print("\n***Процесс работы с таблицей***")
    print("<command> create_table <имя_таблицы> <столбец1:тип> .. - создать таблицу")
    print("<command> list_tables - показать список всех таблиц")
    print("<command> drop_table <имя_таблицы> - удалить таблицу")

    print("\nОбщие команды:")
    print("<command> exit - выход из программы")
    print("<command> help - справочная информация\n")


def print_records(columns, records):
    """Выводит записи с помощью PrettyTable."""
    if not records:
        print("Записи не найдены.")
        return

    table = PrettyTable()
    table.field_names = list(columns)
    for row in records:
        table.add_row([row.get(column) for column in columns])
    print(table)


def _ids_str(records):
    """Формирует строку с идентификаторами записей."""
    return ", ".join(str(row[ID_COLUMN]) for row in records)


# ---------- Обработчики CRUD-команд ----------

@handle_db_errors
def handle_insert(metadata, arguments):
    """Обрабатывает команду добавления записи."""
    table_name, raw_values = arguments
    values = parse_values(raw_values)

    table_data = load_table_data(table_name)
    result = insert(metadata, table_name, values, table_data)
    if result is not None:
        save_table_data(table_name, result)


@handle_db_errors
def handle_select(metadata, arguments):
    """Обрабатывает команду выборки записей."""
    table_name, raw_where = arguments
    if not table_exists(metadata, table_name):
        return

    columns = get_columns(metadata, table_name)
    where_clause = parse_where(raw_where) if raw_where else None
    if where_clause:
        validate_clause(columns, where_clause)

    table_data = load_table_data(table_name)
    records = select(table_data, where_clause)
    if records is None:
        return

    print_records(columns, records)


@handle_db_errors
def handle_update(metadata, arguments):
    """Обрабатывает команду обновления записей."""
    table_name, raw_set, raw_where = arguments
    if not table_exists(metadata, table_name):
        return

    columns = get_columns(metadata, table_name)
    set_clause = parse_set(raw_set)
    where_clause = parse_where(raw_where)

    if ID_COLUMN in set_clause:
        print("Ошибка: столбец ID изменять нельзя.")
        return
    
    validate_clause(columns, set_clause)
    validate_clause(columns, where_clause)

    table_data = load_table_data(table_name)
    found = select(table_data, where_clause)
    if found is None:
        return
    if not found:
        print("Записи по условию не найдены.")
        return

    ids = _ids_str(found)  # запоминаем до обновления: условие может измениться
    save_table_data(table_name, update(table_data, set_clause, where_clause))
    print(f'Запись с ID={ids} в таблице "{table_name}" успешно обновлена.')


@handle_db_errors
def handle_delete(metadata, arguments):
    """Обрабатывает команду удаления записей."""
    table_name, raw_where = arguments
    if not table_exists(metadata, table_name):
        return

    columns = get_columns(metadata, table_name)
    where_clause = parse_where(raw_where)
    validate_clause(columns, where_clause)

    table_data = load_table_data(table_name)
    found = select(table_data, where_clause)
    if found is None:
        return
    if not found:
        print("Записи по условию не найдены.")
        return

    result = delete(table_data, where_clause)
    if result is None:
        return

    save_table_data(table_name, result)
    print(f'Запись с ID={_ids_str(found)} успешно удалена из таблицы "{table_name}".')


@handle_db_errors
def handle_info(metadata, table_name):
    """Выводит схему таблицы и количество записей."""
    if not table_exists(metadata, table_name):
        return

    columns = get_columns(metadata, table_name)
    columns_str = ", ".join(f"{name}:{col_type}" for name, col_type in columns.items())
    print(f"Таблица: {table_name}")
    print(f"Столбцы: {columns_str}")
    print(f"Количество записей: {len(load_table_data(table_name))}")


CRUD_COMMANDS = {
    "insert": handle_insert,
    "select": handle_select,
    "update": handle_update,
    "delete": handle_delete,
}


# ---------- Простые команды ----------


def handle_simple_command(metadata, user_input):
    """Команды без сложного синтаксиса. Возвращает False, если нужно выйти."""
    args = shlex.split(user_input)
    command, *params = args

    match command:
        case "create_table":
            if len(params) < 2:
                print(
                    "Некорректное значение: укажите имя таблицы и столбцы. "
                    "Попробуйте снова."
                )
                return True
            result = create_table(metadata, params[0], params[1:])
            if result is not None:
                save_metadata(META_FILE, result)

        case "drop_table":
            if len(params) != 1:
                print(
                    "Некорректное значение: укажите одно имя таблицы. Попробуйте снова."
                )
                return True
            result = drop_table(metadata, params[0])
            if result is not None:
                save_metadata(META_FILE, result)
                delete_table_data(params[0])

        case "list_tables":
            list_tables(metadata)

        case "info":
            if len(params) != 1:
                print("Некорректное значение: укажите имя таблицы. Попробуйте снова.")
                return True
            handle_info(metadata, params[0])

        case "help":
            print_help()

        case "exit":
            print("Выход из программы.")
            return False

        case _:
            print(f"Функции {command} нет. Попробуйте снова.")

    return True


def run():
    """Главный цикл программы."""
    print("***База данных***")
    print_help()

    while True:
        metadata = load_metadata(META_FILE)

        try:
            user_input = prompt.string(">>>Введите команду: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nВыход из программы.")
            break

        if not user_input:
            continue

        command = user_input.split()[0].lower()

        try:
            if command in CRUD_COMMANDS:
                arguments = parse_crud_command(command, user_input)
                handler = CRUD_COMMANDS[command]
                handler(metadata, arguments)
            elif not handle_simple_command(metadata, user_input):
                break
        except ValueError as error:
            # Ошибки структуры команды, значений или незакрытых кавычек.
            print(f"Некорректное значение: {error}. Попробуйте снова.")
