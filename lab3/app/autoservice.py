import getpass
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2 import errors, sql

CONFIG_PATH = Path(__file__).parent / "config.json"
ALLOWED_CONFIG_KEYS = {"host", "port", "dbname", "connect_timeout"}

LOG_FILE = os.environ.get("LOG_FILE")

TABLES = {
    "clients": ["id", "full_name", "phone", "email"],
    "cars": ["id", "client_id", "plate_number", "brand", "model", "release_year"],
    "services": ["id", "name", "price"],
    "work_orders": ["id", "car_id", "service_id", "order_date", "status"],
}


class InputError(Exception):
    pass


# ---------- Логи и ошибки ----------

def log(message, is_error=False, details=None):
    stream = sys.stderr if is_error else sys.stdout
    print(message, file=stream, flush=True)

    if LOG_FILE:
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}"
        if details:
            line += f" | {details}"
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as file:
                file.write(line + "\n")
        except OSError:
            print("Не удалось записать в лог-файл", file=sys.stderr, flush=True)


def technical_details(error):
    return f"{type(error).__name__}: {' '.join(str(error).split())}"


def friendly_error(error):
    if isinstance(error, errors.ForeignKeyViolation):
        return "указан id записи, которой нет в связанной таблице"
    if isinstance(error, errors.UniqueViolation):
        return "такое значение уже есть, а оно должно быть уникальным (например, госномер или телефон)"
    if isinstance(error, errors.CheckViolation):
        return "значение не прошло проверку (например, госномер не по образцу А123ВС77, неверный год выпуска или статус)"
    if isinstance(error, errors.NotNullViolation):
        return "не заполнено обязательное поле"
    if isinstance(error, psycopg2.DataError):
        return "неверный формат значения (например, буквы вместо числа или даты)"
    if isinstance(error, errors.InsufficientPrivilege):
        return "недостаточно прав для этой операции"
    if isinstance(error, (psycopg2.OperationalError, psycopg2.InterfaceError)):
        return "нет связи с базой данных"
    return "ошибка на стороне базы данных"


# ---------- Ввод от пользователя ----------

def ask(prompt):
    print(prompt, end="", flush=True)
    return input().strip()


def editable_columns(table):
    return [column for column in TABLES[table] if column != "id"]


def ask_table():
    print("Таблицы:", ", ".join(TABLES))
    table = ask("Таблица: ")
    if table not in TABLES:
        raise InputError("такой таблицы нет")
    return table


def check_column(table, column, allow_id=True):
    if column not in TABLES[table]:
        raise InputError(f"в таблице {table} нет колонки «{column}»")
    if column == "id" and not allow_id:
        raise InputError("колонку id задаёт база, менять её нельзя")
    return column


def ask_pairs(table, purpose, allow_id, many):
    shown = TABLES[table] if allow_id else editable_columns(table)
    print("Колонки:", ", ".join(shown))
    pairs = []
    while True:
        hint = " (пусто — закончить)" if many and pairs else ""
        column = ask(f"Колонка {purpose}{hint}: ")
        if not column and pairs:
            break
        check_column(table, column, allow_id)
        if column in [name for name, _ in pairs]:
            raise InputError(f"колонка {column} уже указана")
        value = ask(f"Значение для {column}: ")
        pairs.append((column, value))
        if not many:
            break
    return pairs


def ask_columns_for_insert(table):
    print("Колонки:", ", ".join(editable_columns(table)))
    text = ask("Какие колонки заполнить (через запятую): ")
    columns = [column.strip() for column in text.split(",") if column.strip()]
    if not columns:
        raise InputError("нужно указать хотя бы одну колонку")
    for column in columns:
        check_column(table, column, allow_id=False)
    if len(set(columns)) != len(columns):
        raise InputError("одна и та же колонка указана дважды")
    return columns


def print_rows(cursor):
    headers = [column.name for column in cursor.description]
    rows = [["" if value is None else str(value) for value in row] for row in cursor.fetchall()]

    widths = [len(header) for header in headers]
    for row in rows:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(value))

    print(" | ".join(header.ljust(width) for header, width in zip(headers, widths)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(value.ljust(width) for value, width in zip(row, widths)))
    return len(rows)


# ---------- Запросы к БД ----------

def select_rows(connection, table, conditions):
    """SELECT * FROM table [WHERE col1 = %s AND col2 = %s ...] ORDER BY id"""
    query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(table))
    if conditions:
        parts = [sql.SQL("{} = %s").format(sql.Identifier(column)) for column, _ in conditions]
        query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(parts)
    query += sql.SQL(" ORDER BY id")
    values = [value for _, value in conditions]

    with connection:
        with connection.cursor() as cursor:
            cursor.execute(query, values)
            count = print_rows(cursor)
    log(f"[OK] Запрос к таблице {table} выполнен, найдено строк: {count}")


def update_one(connection, table, record_id, changes):
    """UPDATE table SET col1 = %s, col2 = %s WHERE id = %s"""
    query = sql.SQL("UPDATE {} SET {} WHERE id = %s").format(
        sql.Identifier(table),
        sql.SQL(", ").join([sql.SQL("{} = %s").format(sql.Identifier(column)) for column, _ in changes]),
    )
    values = [value for _, value in changes] + [record_id]

    with connection:
        with connection.cursor() as cursor:
            cursor.execute(query, values)
            return cursor.rowcount


def update_many(connection, table, set_column, new_value, filter_column, filter_values):
    """UPDATE table SET col = %s WHERE filter_col IN (%s, %s, ...)"""
    query = sql.SQL("UPDATE {} SET {} = %s WHERE {} IN ({})").format(
        sql.Identifier(table),
        sql.Identifier(set_column),
        sql.Identifier(filter_column),
        sql.SQL(", ").join([sql.Placeholder()] * len(filter_values)),
    )
    values = [new_value] + filter_values

    with connection:
        with connection.cursor() as cursor:
            cursor.execute(query, values)
            return cursor.rowcount


def insert_rows(connection, table, columns, rows):
    """INSERT INTO table (col1, col2) VALUES (%s, %s) RETURNING id — для каждой строки"""
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
        sql.Identifier(table),
        sql.SQL(", ").join([sql.Identifier(column) for column in columns]),
        sql.SQL(", ").join([sql.Placeholder()] * len(columns)),
    )

    new_ids = []
    with connection:
        with connection.cursor() as cursor:
            for row in rows:
                cursor.execute(query, row)
                new_ids.append(cursor.fetchone()[0])
    return new_ids


def insert_clients(connection, clients):
    """Клиенты вместе с автомобилями: clients + cars в одной транзакции"""
    client_ids = []
    car_ids = []
    with connection:
        with connection.cursor() as cursor:
            for full_name, phone, cars in clients:
                cursor.execute(
                    "INSERT INTO clients (full_name, phone) VALUES (%s, %s) RETURNING id",
                    (full_name, phone),
                )
                client_id = cursor.fetchone()[0]
                client_ids.append(client_id)

                for plate_number, brand, model, release_year in cars:
                    cursor.execute(
                        "INSERT INTO cars (client_id, plate_number, brand, model, release_year) "
                        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                        (client_id, plate_number, brand, model, release_year),
                    )
                    car_ids.append(cursor.fetchone()[0])
    return client_ids, car_ids


# ---------- Пункты меню ----------

def show_all(connection):
    table = ask_table()
    select_rows(connection, table, [])


def show_filtered_one(connection):
    table = ask_table()
    conditions = ask_pairs(table, "для фильтра", allow_id=True, many=False)
    select_rows(connection, table, conditions)


def show_filtered_many(connection):
    table = ask_table()
    conditions = ask_pairs(table, "для фильтра", allow_id=True, many=True)
    select_rows(connection, table, conditions)


def edit_one(connection):
    table = ask_table()
    record_id = ask("id записи: ")
    changes = ask_pairs(table, "для изменения", allow_id=False, many=True)
    count = update_one(connection, table, record_id, changes)
    log(f"[OK] Таблица {table}: обновлено строк: {count}")


def edit_many(connection):
    table = ask_table()
    set_column, new_value = ask_pairs(table, "для изменения", allow_id=False, many=False)[0]
    print("Какие строки изменить:")
    filter_column = check_column(table, ask("Колонка для отбора: "))
    text = ask(f"Значения {filter_column} через запятую: ")
    filter_values = [value.strip() for value in text.split(",") if value.strip()]
    if not filter_values:
        raise InputError("нужно указать хотя бы одно значение")
    count = update_many(connection, table, set_column, new_value, filter_column, filter_values)
    log(f"[OK] Таблица {table}: обновлено строк: {count}")


def add_one(connection):
    table = ask_table()
    columns = ask_columns_for_insert(table)
    row = [ask(f"{column}: ") for column in columns]
    new_ids = insert_rows(connection, table, columns, [row])
    log(f"[OK] В таблицу {table} добавлена строка, id = {new_ids[0]}")


def add_many(connection):
    table = ask_table()
    columns = ask_columns_for_insert(table)
    print("Вводите строки по одной. Пустое первое поле — закончить ввод.")
    rows = []
    while True:
        print(f"Строка {len(rows) + 1}:")
        first = ask(f"  {columns[0]}: ")
        if not first:
            break
        row = [first] + [ask(f"  {column}: ") for column in columns[1:]]
        rows.append(row)
    if not rows:
        raise InputError("не введено ни одной строки")
    new_ids = insert_rows(connection, table, columns, rows)
    log(f"[OK] В таблицу {table} добавлено строк: {len(new_ids)}, id: {', '.join(map(str, new_ids))}")


def add_client_with_car(connection):
    full_name = ask("ФИО клиента: ")
    phone = ask("Телефон: ")
    plate_number = ask("Госномер (русские буквы, например А123ВС77): ")
    brand = ask("Марка: ")
    model = ask("Модель: ")
    release_year = ask("Год выпуска: ")
    car = (plate_number, brand, model, release_year)
    client_ids, car_ids = insert_clients(connection, [(full_name, phone, [car])])
    log(f"[OK] Добавлен клиент id = {client_ids[0]} и его автомобиль id = {car_ids[0]}")


def add_clients_with_cars(connection):
    print("Вводите клиентов по одному.")
    clients = []
    while True:
        full_name = ask("ФИО клиента (пусто — закончить ввод клиентов): ")
        if not full_name:
            break
        phone = ask("  Телефон: ")
        cars = []
        while True:
            plate_number = ask("  Госномер автомобиля (пусто — закончить с этим клиентом): ")
            if not plate_number:
                break
            brand = ask("    Марка: ")
            model = ask("    Модель: ")
            release_year = ask("    Год выпуска: ")
            cars.append((plate_number, brand, model, release_year))
        if not cars:
            raise InputError("у клиента должен быть хотя бы один автомобиль")
        clients.append((full_name, phone, cars))
    if not clients:
        raise InputError("не введено ни одного клиента")
    client_ids, car_ids = insert_clients(connection, clients)
    log(f"[OK] Добавлено клиентов: {len(client_ids)}, id: {', '.join(map(str, client_ids))}; "
        f"автомобилей: {len(car_ids)}, id: {', '.join(map(str, car_ids))}")


MENU = {
    "1": ("Показать таблицу целиком", show_all),
    "2": ("Показать с фильтром по одной колонке", show_filtered_one),
    "3": ("Показать с фильтром по нескольким колонкам", show_filtered_many),
    "4": ("Изменить одну запись по id", edit_one),
    "5": ("Изменить несколько записей (общее новое значение)", edit_many),
    "6": ("Добавить одну строку в таблицу", add_one),
    "7": ("Добавить клиента с автомобилем (две связанные таблицы)", add_client_with_car),
    "8": ("Добавить несколько строк в таблицу", add_many),
    "9": ("Добавить несколько клиентов с автомобилями (две связанные таблицы)", add_clients_with_cars),
}


# ---------- Запуск ----------

def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as file:
        config = json.load(file)

    for key in config:
        if key not in ALLOWED_CONFIG_KEYS:
            raise ValueError(f"недопустимая настройка: {key}")
    return config


def connect():
    try:
        config = load_config()
    except (OSError, ValueError) as error:
        log("[ERROR] Не удалось прочитать файл настроек", is_error=True,
            details=technical_details(error))
        return None

    user = ask("Логин: ")
    password = getpass.getpass("Пароль: ")
    if not user or not password:
        log("[ERROR] Логин и пароль не должны быть пустыми", is_error=True)
        return None

    try:
        connection = psycopg2.connect(**config, user=user, password=password)
    except psycopg2.Error as error:
        log("[ERROR] Не удалось подключиться к БД: проверьте логин, пароль и доступность сервера",
            is_error=True, details=technical_details(error))
        return None

    log(f"[OK] Подключение к БД выполнено, пользователь {user}")
    return connection


def run_menu(connection):
    while True:
        print()
        for key, (title, _) in MENU.items():
            print(f"{key}. {title}")
        print("0. Выход")

        choice = ask("Выберите пункт: ")
        if choice == "0":
            return
        if choice not in MENU:
            print("Нет такого пункта меню", file=sys.stderr)
            continue

        title, action = MENU[choice]
        try:
            action(connection)
        except InputError as error:
            log(f"[ERROR] {error}", is_error=True)
        except psycopg2.Error as error:
            log(f"[ERROR] Запрос не выполнен: {friendly_error(error)}", is_error=True,
                details=technical_details(error))
        except EOFError:
            raise
        except Exception as error:
            log("[ERROR] Непредвиденная ошибка", is_error=True, details=technical_details(error))


def main():
    connection = connect()
    if connection is None:
        return 1
    try:
        run_menu(connection)
    finally:
        connection.close()
        log("[INFO] Соединение закрыто, работа завершена")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (EOFError, KeyboardInterrupt):
        print("\nВвод прерван", file=sys.stderr)
        sys.exit(1)
