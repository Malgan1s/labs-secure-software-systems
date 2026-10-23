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
    "customers": ["id", "full_name", "email", "city"],
    "products": ["id", "name", "category", "price"],
    "orders": ["id", "customer_id", "order_date", "status"],
    "order_items": ["id", "order_id", "product_id", "quantity", "price"],
}


class InputError(Exception):

# ---------- логи и ошибки ----------

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
        return "такое значение уже есть, а оно должно быть уникальным"
    if isinstance(error, errors.CheckViolation):
        return "значение не прошло проверку (например, отрицательная цена или неизвестный статус)"
    if isinstance(error, errors.NotNullViolation):
        return "не заполнено обязательное поле"
    if isinstance(error, psycopg2.DataError):
        return "неверный формат значения (например, буквы вместо числа или даты)"
    if isinstance(error, errors.InsufficientPrivilege):
        return "недостаточно прав для этой операции"
    if isinstance(error, (psycopg2.OperationalError, psycopg2.InterfaceError)):
        return "нет связи с базой данных"
    return "запрос не выполнен"


# ---------- ввод пользователя ----------

def ask(prompt):
    print(prompt, end="", flush=True)
    return input().strip()


def editable_columns(table):
    """Все колонки таблицы, кроме id: id назначает сама база."""
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
    """INSERT INTO table (col1, col2) VALUES (%s, %s) RETURNING id - для каждой строки"""
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


def insert_orders(connection, orders):
    """Заказы вместе с позициями

    orders — список вида [(customer_id, [(product_id, quantity), ...]), ...]
    """
    new_ids = []
    with connection:
        with connection.cursor() as cursor:
            for customer_id, items in orders:
                cursor.execute(
                    "INSERT INTO orders (customer_id) VALUES (%s) RETURNING id",
                    (customer_id,),
                )
                order_id = cursor.fetchone()[0]   

                for product_id, quantity in items:
                    cursor.execute("SELECT price FROM products WHERE id = %s", (product_id,))
                    product = cursor.fetchone()
                    if product is None:
                        raise InputError(f"товара с id {product_id} нет")

                    cursor.execute(
                        "INSERT INTO order_items (order_id, product_id, quantity, price) "
                        "VALUES (%s, %s, %s, %s)",
                        (order_id, product_id, quantity, product[0]),
                    )
                new_ids.append(order_id)
    return new_ids


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


def add_order(connection):
    customer_id = ask("id покупателя: ")
    product_id = ask("id товара: ")
    quantity = ask("Количество: ")
    new_ids = insert_orders(connection, [(customer_id, [(product_id, quantity)])])
    log(f"[OK] Создан заказ id = {new_ids[0]}: строка в orders и строка в order_items")


def add_orders(connection):
    print("Вводите заказы по одному.")
    orders = []
    while True:
        customer_id = ask("id покупателя (пусто — закончить ввод заказов): ")
        if not customer_id:
            break
        items = []
        while True:
            product_id = ask("  id товара (пусто — закончить этот заказ): ")
            if not product_id:
                break
            quantity = ask("  Количество: ")
            items.append((product_id, quantity))
        if not items:
            raise InputError("в заказе должен быть хотя бы один товар")
        orders.append((customer_id, items))
    if not orders:
        raise InputError("не введено ни одного заказа")
    new_ids = insert_orders(connection, orders)
    log(f"[OK] Создано заказов: {len(new_ids)}, id: {', '.join(map(str, new_ids))}")


MENU = {
    "1": ("Показать таблицу целиком", show_all),
    "2": ("Показать с фильтром по одной колонке", show_filtered_one),
    "3": ("Показать с фильтром по нескольким колонкам", show_filtered_many),
    "4": ("Изменить одну запись по id", edit_one),
    "5": ("Изменить несколько записей (общее новое значение)", edit_many),
    "6": ("Добавить одну строку в таблицу", add_one),
    "7": ("Добавить заказ с одним товаром (две связанные таблицы)", add_order),
    "8": ("Добавить несколько строк в таблицу", add_many),
    "9": ("Добавить несколько заказов с товарами (две связанные таблицы)", add_orders),
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
