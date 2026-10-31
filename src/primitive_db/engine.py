import shlex

import prompt

from primitive_db.core import create_table, drop_table, list_tables
from primitive_db.utils import load_metadata, save_metadata

META_FILE = "db_meta.json"


def print_help():

    print("\n***Процесс работы с таблицей***")
    print("Функции:")
    print("<command> create_table <имя_таблицы> <столбец1:тип> .. - создать таблицу")
    print("<command> list_tables - показать список всех таблиц")
    print("<command> drop_table <имя_таблицы> - удалить таблицу")

    print("\nОбщие команды:")
    print("<command> exit - выход из программы")
    print("<command> help - справочная информация\n")


def run():
    """Главный цикл"""
    print("***База данных***")
    print_help()

    while True:
        metadata = load_metadata(META_FILE)

        try:
            user_input = prompt.string(">>>Введите команду: ")
        except (KeyboardInterrupt, EOFError):
            print("\nВыход из программы.")
            break

        try:
            args = shlex.split(user_input)
        except ValueError:  # например, незакрытая кавычка
            print(f"Некорректное значение: {user_input}. Попробуйте снова.")
            continue

        if not args:
            continue

        command, *params = args

        match command:
            case "create_table":
                if len(params) < 2:
                    print(
                        "Некорректное значение: укажите имя таблицы и столбцы. "
                        "Попробуйте снова."
                    )
                    continue
                result = create_table(metadata, params[0], params[1:])
                if result is not None:
                    save_metadata(META_FILE, result)

            case "drop_table":
                if len(params) != 1:
                    print(
                        "Некорректное значение: укажите одно имя таблицы. "
                        "Попробуйте снова."
                    )
                    continue
                result = drop_table(metadata, params[0])
                if result is not None:
                    save_metadata(META_FILE, result)

            case "list_tables":
                list_tables(metadata)

            case "help":
                print_help()

            case "exit":
                print("Выход из программы.")
                break

            case _:
                print(f"Функции {command} нет. Попробуйте снова.")