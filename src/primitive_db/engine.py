import re
import shlex

import prompt
from prettytable import PrettyTable

from primitive_db.core import (
    ID_COLUMN,
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

META_FILE = "db_meta.json"

# Шаблоны CRUD-команд. Ключевые слова — без учёта регистра.
INSERT_RE = re.compile(r"insert\s+into\s+(\w+)\s+values\s*\((.*)\)", re.IGNORECASE)
SELECT_RE = re.compile(r"select\s+from\s+(\w+)(?:\s+where\s+(.+))?", re.IGNORECASE)
UPDATE_RE = re.compile(r"update\s+(\w+)\s+set\s+(.+?)\s+where\s+(.+)", re.IGNORECASE)
DELETE_RE = re.compile(r"delete\s+from\s+(\w+)\s+where\s+(.+)", re.IGNORECASE)


def print_help():
    """Prints the help message for the current mode."""

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
    return ", ".join(str(row[ID_COLUMN]) for row in records)


# ---------- Обработчики CRUD-команд ----------

@handle_db_errors
def handle_insert(metadata, match):
    table_name, raw_values = match.groups()
    values = parse_values(raw_values)

    table_data = load_table_data(table_name)
    result = insert(metadata, table_name, values, table_data)
    if result is not None:
        save_table_data(table_name, result)


@handle_db_errors
def handle_select(metadata, match):
    table_name, raw_where = match.groups()
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
def handle_update(metadata, match):
    table_name, raw_set, raw_where = match.groups()
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
def handle_delete(metadata, match):
    table_name, raw_where = match.groups()
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
    if not table_exists(metadata, table_name):
        return

    columns = get_columns(metadata, table_name)
    columns_str = ", ".join(f"{name}:{col_type}" for name, col_type in columns.items())
    print(f"Таблица: {table_name}")
    print(f"Столбцы: {columns_str}")
    print(f"Количество записей: {len(load_table_data(table_name))}")


CRUD_COMMANDS = {
    "insert": (INSERT_RE, handle_insert),
    "select": (SELECT_RE, handle_select),
    "update": (UPDATE_RE, handle_update),
    "delete": (DELETE_RE, handle_delete),
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
                pattern, handler = CRUD_COMMANDS[command]
                match = pattern.fullmatch(user_input)
                if match is None:
                    print(f"Некорректное значение: {user_input}. Попробуйте снова.")
                    continue
                handler(metadata, match)
            elif not handle_simple_command(metadata, user_input):
                break
        except ValueError as error:
            # Бросают парсер условий и shlex (например, незакрытая кавычка).
            print(f"Некорректное значение: {error}. Попробуйте снова.")
