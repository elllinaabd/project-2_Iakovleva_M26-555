"""Декораторы для операций базы данных."""

import time


def _preserve_metadata(wrapper, func):
    """Сохраняет имя и описание обёрнутой функции."""
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def handle_db_errors(func):
    """Перехватывает ожидаемые ошибки при выполнении операции."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FileNotFoundError:
            print(
                "Ошибка: файл данных не найден. "
                "Возможно, база данных не инициализирована."
            )
        except KeyError as error:
            print(f"Ошибка: таблица или столбец {error} не найден.")
        except ValueError as error:
            print(f"Ошибка валидации: {error}")

        return None

    return _preserve_metadata(wrapper, func)


def confirm_action(action_name):
    """Запрашивает подтверждение перед выполнением операции."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            answer = input(
                f'Вы уверены, что хотите выполнить "{action_name}"? [y/n]: '
            )

            if answer != "y":
                print("Операция отменена.")
                return None

            return func(*args, **kwargs)

        return _preserve_metadata(wrapper, func)

    return decorator


def log_time(func):
    """Выводит время выполнения функции."""

    def wrapper(*args, **kwargs):
        start = time.monotonic()
        result = func(*args, **kwargs)
        elapsed = time.monotonic() - start

        print(
            f"Функция {func.__name__} выполнилась "
            f"за {elapsed:.3f} секунд."
        )
        return result

    return _preserve_metadata(wrapper, func)


def create_cacher():
    """Создаёт функцию для получения и сохранения результатов в кэше."""
    cache = {}

    def cache_result(key, value_func):
        """Возвращает результат из кэша или вычисляет и сохраняет его."""
        if key not in cache:
            cache[key] = value_func()

        return cache[key]

    return cache_result