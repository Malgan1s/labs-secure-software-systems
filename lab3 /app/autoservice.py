"""Задание 3: консольная программа для работы с базой автосервиса.

Как читать этот файл:
- строка, начинающаяся с #, — комментарий, Python её пропускает;
- текст в тройных кавычках сразу после «def имя(...):» или «class Имя:» —
  описание функции (docstring). Python его не выполняет и в базу не отправляет,
  это подсказка для человека, который читает код;
- у функций, которые обращаются к базе (раздел «Запросы к БД»), первая строка
  описания — ШАБЛОН SQL-запроса, который собирает эта функция. Подробный разбор
  шаблона — в описании функции select_rows.

Разделы файла, сверху вниз:
1. Настройки и белый список таблиц.
2. Логи и ошибки — куда и как печатать сообщения.
3. Ввод от пользователя — вопросы и проверки введённого.
4. Запросы к БД — сборка безопасного SQL и его выполнение.
5. Пункты меню — по одной функции на каждый пункт.
6. Запуск — чтение конфига, подключение к базе, главный цикл меню.
"""

import getpass                 # ввод пароля без отображения на экране
import json                    # чтение файла настроек config.json
import os                      # чтение переменных среды (LOG_FILE)
import sys                     # потоки вывода stdout / stderr и код выхода программы
from datetime import datetime  # дата и время для строк лог-файла
from pathlib import Path       # путь к config.json рядом с программой

import psycopg2                   # драйвер PostgreSQL для Python (requirements.txt)
from psycopg2 import errors, sql  # errors — классы ошибок БД, sql — безопасная сборка запросов

# Файл настроек лежит в той же папке, что и программа (/app в контейнере).
# __file__ — путь к этому файлу, .parent — его папка, / "config.json" — файл в ней.
# Внутри config.json: host (имя сервиса db из docker-compose.yml), port, dbname,
# connect_timeout (сколько секунд ждать подключения).
CONFIG_PATH = Path(__file__).parent / "config.json"
# Какие настройки разрешено держать в config.json. Если в файл допишут что-то
# ещё (например, sslmode или options), программа откажется запускаться.
# Логина и пароля здесь нет: их вводит пользователь при запуске.
ALLOWED_CONFIG_KEYS = {"host", "port", "dbname", "connect_timeout"}

# Путь к файлу, куда дублируются логи (пункт 6.7 задания).
# Значение приходит из переменной среды LOG_FILE: в Docker её задаёт app.env.
# Если переменной нет, os.environ.get вернёт None, и лог-файл просто не ведётся.
LOG_FILE = os.environ.get("LOG_FILE")

# Белый список: какие таблицы и колонки пользователь может указывать.
# Ключ словаря — имя таблицы, значение — список её колонок (как в 02_schema.sql).
# Любое имя, которого здесь нет, программа отклонит ещё до обращения к базе,
# поэтому в SQL-запрос не попадёт ни одно имя, придуманное пользователем.
TABLES = {
    "clients": ["id", "full_name", "phone", "email"],
    "cars": ["id", "client_id", "plate_number", "brand", "model", "release_year"],
    "services": ["id", "name", "price"],
    "work_orders": ["id", "car_id", "service_id", "order_date", "status"],
}


class InputError(Exception):
    """Ошибка во вводе пользователя. Её текст можно показывать как есть.

    Своё исключение нужно, чтобы отличать ошибки, которые программа создаёт сама
    (например, raise InputError("такой таблицы нет")), от ошибок базы и Python.
    Текст InputError пишем мы, деталей реализации в нём нет, поэтому его можно
    показать пользователю. Остальные ошибки переводятся в понятный текст в run_menu.
    Всё нужное класс наследует от Exception, поэтому своего кода у него нет.
    """


# ---------- Логи и ошибки ----------

def log(message, is_error=False, details=None):
    """Печатает сообщение в stdout (успех) или stderr (ошибка) и дублирует в лог-файл.

    details — исходный текст ошибки. Пользователь его не видит,
    он попадает только в лог-файл.
    """
    # Выбираем поток вывода: ошибки — в stderr, всё остальное — в stdout (пункт 6.5)
    stream = sys.stderr if is_error else sys.stdout
    # flush=True — напечатать сразу, не дожидаясь заполнения буфера
    print(message, file=stream, flush=True)

    if LOG_FILE:
        # Строка лога: дата и время + то же сообщение, что видит пользователь
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}"
        if details:
            # Исходный текст ошибки добавляем только в файл, на экран он не попадает
            line += f" | {details}"
        try:
            # "a" — дописывать в конец файла, а не перезаписывать его
            with open(LOG_FILE, "a", encoding="utf-8") as file:
                file.write(line + "\n")
        except OSError:
            # Нет прав на файл или нет папки — сообщаем, но программу не роняем
            print("Не удалось записать в лог-файл", file=sys.stderr, flush=True)


def technical_details(error):
    """Исходный текст ошибки одной строкой — только для лог-файла.

    Пример результата:
    ForeignKeyViolation: insert or update on table "work_orders" violates ...
    type(error).__name__ — имя класса ошибки;
    " ".join(str(error).split()) — текст ошибки без переносов строк и лишних пробелов.
    """
    return f"{type(error).__name__}: {' '.join(str(error).split())}"


def friendly_error(error):
    """Переводит ошибку БД в понятный текст без деталей реализации.

    Для каждой ошибки PostgreSQL драйвер psycopg2 создаёт исключение своего
    класса. isinstance проверяет, к какому классу относится ошибка, и выбирает
    подходящий текст. Проверки идут сверху вниз, срабатывает первая подходящая.
    """
    # Ссылка на несуществующую запись: например, car_id = 999 в work_orders
    if isinstance(error, errors.ForeignKeyViolation):
        return "указан id записи, которой нет в связанной таблице"
    # Нарушено ограничение UNIQUE: госномер, телефон или название услуги уже заняты
    if isinstance(error, errors.UniqueViolation):
        return "такое значение уже есть, а оно должно быть уникальным (например, госномер или телефон)"
    # Не прошла проверка CHECK из 02_schema.sql (формат госномера, год, статус, цена)
    if isinstance(error, errors.CheckViolation):
        return "значение не прошло проверку (например, госномер не по образцу А123ВС77, неверный год выпуска или статус)"
    # Пустое значение в колонке с NOT NULL
    if isinstance(error, errors.NotNullViolation):
        return "не заполнено обязательное поле"
    # Значение не того типа: буквы вместо числа, неправильная дата
    if isinstance(error, psycopg2.DataError):
        return "неверный формат значения (например, буквы вместо числа или даты)"
    # Не хватает прав app_user из 03_grants.sql (например, на изменение order_date)
    if isinstance(error, errors.InsufficientPrivilege):
        return "недостаточно прав для этой операции"
    # Сервер недоступен или соединение оборвалось
    if isinstance(error, (psycopg2.OperationalError, psycopg2.InterfaceError)):
        return "нет связи с базой данных"
    # Любая другая ошибка базы — без подробностей (они будут в лог-файле)
    return "ошибка на стороне базы данных"


# ---------- Ввод от пользователя ----------

def ask(prompt):
    """Задаёт вопрос и возвращает ответ пользователя без пробелов по краям."""
    # Подсказку печатаем сами: input(prompt) в терминале выводит её в stderr,
    # а в stderr должны попадать только ошибки. end="" — без перевода строки
    print(prompt, end="", flush=True)
    # input() ждёт, пока пользователь нажмёт Enter;
    # strip() убирает пробелы и перевод строки в начале и в конце ответа
    return input().strip()


def editable_columns(table):
    """Все колонки таблицы, кроме id: id назначает сама база."""
    # Берём каждую колонку таблицы из белого списка, если это не id
    return [column for column in TABLES[table] if column != "id"]


def ask_table():
    """Спрашивает имя таблицы и проверяет его по белому списку."""
    # ", ".join(TABLES) — имена таблиц через запятую: clients, cars, services, work_orders
    print("Таблицы:", ", ".join(TABLES))
    table = ask("Таблица: ")
    # Проверка по белому списку: ввод «cars; DROP TABLE clients» сюда не пройдёт
    if table not in TABLES:
        raise InputError("такой таблицы нет")
    return table


def check_column(table, column, allow_id=True):
    """Проверяет имя колонки по белому списку.

    allow_id=True — для фильтров: искать по id можно.
    allow_id=False — для изменения и вставки: id назначает база, его указывать нельзя.
    Если имя не подходит, функция выбрасывает InputError и дальше код не идёт.
    """
    # Колонки нет в списке для этой таблицы — например, «id = 1 OR 1=1 --»
    if column not in TABLES[table]:
        raise InputError(f"в таблице {table} нет колонки «{column}»")
    if column == "id" and not allow_id:
        raise InputError("колонку id задаёт база, менять её нельзя")
    return column


def ask_pairs(table, purpose, allow_id, many):
    """Спрашивает пары «колонка = значение» для фильтра или для изменения.

    many=False — ровно одна пара, many=True — сколько угодно,
    пустое имя колонки завершает ввод.

    Возвращает список пар, например [("car_id", "1"), ("status", "выдан")].
    purpose — слова для подсказки: «для фильтра» или «для изменения».
    """
    # Показываем, какие колонки можно указать (без id, если его менять нельзя)
    shown = TABLES[table] if allow_id else editable_columns(table)
    print("Колонки:", ", ".join(shown))
    pairs = []
    while True:
        # После первой пары подсказываем, что пустой ввод завершает список
        hint = " (пусто — закончить)" if many and pairs else ""
        column = ask(f"Колонка {purpose}{hint}: ")
        # Пустой ввод после хотя бы одной пары — конец списка
        if not column and pairs:
            break
        # Каждое имя колонки проверяется по белому списку
        check_column(table, column, allow_id)
        # Одна и та же колонка дважды — ошибка (например, status дважды в SET)
        if column in [name for name, _ in pairs]:
            raise InputError(f"колонка {column} уже указана")
        value = ask(f"Значение для {column}: ")
        pairs.append((column, value))
        # Если нужна только одна пара, выходим сразу
        if not many:
            break
    return pairs


def ask_columns_for_insert(table):
    """Спрашивает, какие колонки заполнить при вставке, и проверяет каждую.

    Пользователь вводит имена через запятую, например «name, price».
    Возвращает список имён: ["name", "price"].
    """
    print("Колонки:", ", ".join(editable_columns(table)))
    text = ask("Какие колонки заполнить (через запятую): ")
    # split(",") режет строку по запятым, strip() убирает пробелы вокруг имён,
    # if column.strip() отбрасывает пустые куски (например, от лишней запятой)
    columns = [column.strip() for column in text.split(",") if column.strip()]
    if not columns:
        raise InputError("нужно указать хотя бы одну колонку")
    # Каждое имя проверяется по белому списку, id указывать нельзя
    for column in columns:
        check_column(table, column, allow_id=False)
    # set() убирает повторы: если длина изменилась, какое-то имя было дважды
    if len(set(columns)) != len(columns):
        raise InputError("одна и та же колонка указана дважды")
    return columns


def print_rows(cursor):
    """Печатает результат SELECT ровной таблицей, возвращает число строк."""
    # cursor.description — описание колонок результата; берём их имена для заголовка
    headers = [column.name for column in cursor.description]
    # fetchall() — все строки результата; пустое значение (NULL, в Python None)
    # печатаем как пустую строку, остальное переводим в текст
    rows = [["" if value is None else str(value) for value in row] for row in cursor.fetchall()]

    # Ширина каждой колонки — по самому длинному значению в ней
    widths = [len(header) for header in headers]
    for row in rows:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(value))

    # ljust(width) дополняет текст пробелами справа до нужной ширины
    print(" | ".join(header.ljust(width) for header, width in zip(headers, widths)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(value.ljust(width) for value, width in zip(row, widths)))
    return len(rows)


# ---------- Запросы к БД ----------
# Главная часть задания: как собрать SQL, если таблицу и колонки выбирает пользователь.
#
# В тексте запроса есть два вида «пустых мест», и заполняются они по-разному:
# - {} — место для ИМЕНИ таблицы или колонки. Заполняется только через
#   sql.Identifier и только именем, прошедшим белый список TABLES.
#   Identifier берёт имя в двойные кавычки (cars -> "cars"), поэтому имя
#   не может закрыть кавычку и дописать в запрос свой SQL.
# - %s — место для ЗНАЧЕНИЯ. Его заполняет драйвер при cursor.execute(query, values):
#   значение передаётся отдельно от текста запроса и всегда остаётся данными.
#
# sql.SQL("...") — кусок запроса, который написал программист (ему можно доверять).
# .format(...) — подставить имена на места {}.
# sql.SQL(", ").join([...]) — склеить несколько кусков через запятую (или через AND).
# Склеивания строк с вводом пользователя (f-строк или +) в запросах нет нигде.
#
# «with connection:» — транзакция. Если внутри блока всё прошло успешно,
# изменения сохраняются (COMMIT), если возникла ошибка — отменяются (ROLLBACK).
# «with connection.cursor() as cursor:» — курсор, через который выполняются
# запросы; после блока он закрывается сам.

def select_rows(connection, table, conditions):
    """SELECT * FROM table [WHERE col1 = %s AND col2 = %s ...] ORDER BY id

    Первая строка — не запрос, а ШАБЛОН запроса, который собирает эта функция:
    - table, col1, col2 — таблица и колонки, которые выбрал пользователь;
    - %s — места для значений, их подставит драйвер;
    - [ ... ] — необязательная часть: WHERE появляется, только если есть фильтры;
    - ... — условий может быть сколько угодно.

    Какие запросы получаются на самом деле:
    пункт 1: SELECT * FROM "services" ORDER BY id
    пункт 2: SELECT * FROM "cars" WHERE "brand" = %s ORDER BY id
             значения: ['Toyota']
    пункт 3: SELECT * FROM "work_orders" WHERE "car_id" = %s AND "status" = %s ORDER BY id
             значения: ['1', 'выдан']

    conditions — список пар (колонка, значение), например [("brand", "Toyota")].
    Пустой список — без фильтра.
    """
    # Начало запроса: SELECT * FROM "cars" (имя таблицы — через Identifier)
    query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(table))
    # Если фильтров нет (пункт 1), WHERE не добавляем
    if conditions:
        # Для каждой пары делаем кусок "колонка" = %s.
        # Значение здесь не нужно (поэтому _): оно уйдёт отдельно, в values
        parts = [sql.SQL("{} = %s").format(sql.Identifier(column)) for column, _ in conditions]
        # Склеиваем куски через AND и добавляем в запрос:
        # WHERE "car_id" = %s AND "status" = %s
        query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(parts)
    # Сортировка по id, чтобы строки всегда шли по порядку
    query += sql.SQL(" ORDER BY id")
    # Значения в том же порядке, что и %s в запросе: ['1', 'выдан']
    values = [value for _, value in conditions]

    with connection:
        with connection.cursor() as cursor:
            # Драйвер подставляет values на места %s и отправляет запрос в базу
            cursor.execute(query, values)
            count = print_rows(cursor)
    log(f"[OK] Запрос к таблице {table} выполнен, найдено строк: {count}")


def update_one(connection, table, record_id, changes):
    """UPDATE table SET col1 = %s, col2 = %s WHERE id = %s

    Шаблон запроса для пункта 4: изменить одну запись по её id.
    changes — список пар (колонка, новое значение), например
    [("phone", "+79003330000"), ("email", "sidorov@example.com")].

    Получится: UPDATE "clients" SET "phone" = %s, "email" = %s WHERE id = %s
    значения:  ['+79003330000', 'sidorov@example.com', '3']
    Возвращает, сколько строк изменилось (0, если записи с таким id нет).
    """
    # SET "phone" = %s, "email" = %s — по куску на каждую изменяемую колонку
    query = sql.SQL("UPDATE {} SET {} WHERE id = %s").format(
        sql.Identifier(table),
        sql.SQL(", ").join([sql.SQL("{} = %s").format(sql.Identifier(column)) for column, _ in changes]),
    )
    # Сначала новые значения, в конце id — в том же порядке, что и %s в запросе
    values = [value for _, value in changes] + [record_id]

    with connection:
        with connection.cursor() as cursor:
            cursor.execute(query, values)
            # rowcount — сколько строк затронул UPDATE
            return cursor.rowcount


def update_many(connection, table, set_column, new_value, filter_column, filter_values):
    """UPDATE table SET col = %s WHERE filter_col IN (%s, %s, ...)

    Шаблон запроса для пункта 5: одно новое значение сразу для нескольких строк.
    Пример — статус «готов» для заказ-нарядов 4 и 7:
    UPDATE "work_orders" SET "status" = %s WHERE "id" IN (%s, %s)
    значения: ['готов', '4', '7']

    Количество %s внутри IN равно количеству значений, которые ввёл пользователь.
    Сам текст значений в запрос не попадает, поэтому ввод «1) OR (1=1» безопасен.
    """
    query = sql.SQL("UPDATE {} SET {} = %s WHERE {} IN ({})").format(
        sql.Identifier(table),
        sql.Identifier(set_column),
        sql.Identifier(filter_column),
        # [sql.Placeholder()] * 2 — список из двух %s; join склеивает их через запятую
        sql.SQL(", ").join([sql.Placeholder()] * len(filter_values)),
    )
    # Новое значение для SET, затем значения для IN — в порядке %s в запросе
    values = [new_value] + filter_values

    with connection:
        with connection.cursor() as cursor:
            cursor.execute(query, values)
            return cursor.rowcount


def insert_rows(connection, table, columns, rows):
    """INSERT INTO table (col1, col2) VALUES (%s, %s) RETURNING id — для каждой строки.

    Все строки вставляются в одной транзакции: либо все, либо ни одной.

    Шаблон запроса для пунктов 6 и 8. Пример для услуг:
    INSERT INTO "services" ("name", "price") VALUES (%s, %s) RETURNING id
    значения одной строки: ['Замена антифриза', '3500']

    columns — какие колонки заполняем, например ["name", "price"].
    rows — список строк, каждая строка — список значений в том же порядке, что columns.
    RETURNING id — база в ответ на вставку сообщает id новой строки.
    Возвращает список новых id.
    """
    # Имена таблицы и колонок — через Identifier, по одному %s на каждую колонку
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
        sql.Identifier(table),
        sql.SQL(", ").join([sql.Identifier(column) for column in columns]),
        sql.SQL(", ").join([sql.Placeholder()] * len(columns)),
    )

    new_ids = []
    with connection:
        with connection.cursor() as cursor:
            # Один и тот же запрос выполняется для каждой строки со своими значениями
            for row in rows:
                cursor.execute(query, row)
                # fetchone() — первая строка ответа, [0] — первое поле в ней, то есть id
                new_ids.append(cursor.fetchone()[0])
    return new_ids


def insert_clients(connection, clients):
    """Клиенты вместе с автомобилями: clients + cars в одной транзакции.

    clients — список вида [(full_name, phone, [(plate_number, brand, model, release_year), ...]), ...]

    Используется в пунктах 7 и 9 (вставка в две связанные таблицы). Для каждого клиента:
    1. INSERT INTO clients (full_name, phone) VALUES (%s, %s) RETURNING id
       — база создаёт клиента и возвращает его новый id;
    2. для каждого его автомобиля:
       INSERT INTO cars (client_id, plate_number, brand, model, release_year)
       VALUES (%s, %s, %s, %s, %s) RETURNING id
       — client_id берётся из шага 1.
    Если любая вставка не прошла (например, госномер уже занят), транзакция
    отменяется целиком: не сохранится ни клиент, ни его автомобили.
    Возвращает два списка: id новых клиентов и id новых автомобилей.
    """
    client_ids = []
    car_ids = []
    with connection:
        with connection.cursor() as cursor:
            # Здесь имена таблиц и колонок написаны прямо в тексте запроса:
            # пользователь их не выбирает, поэтому Identifier не нужен.
            # Значения по-прежнему передаются только через %s
            for full_name, phone, cars in clients:
                cursor.execute(
                    "INSERT INTO clients (full_name, phone) VALUES (%s, %s) RETURNING id",
                    (full_name, phone),
                )
                client_id = cursor.fetchone()[0]  # id только что созданного клиента
                client_ids.append(client_id)

                for plate_number, brand, model, release_year in cars:
                    # client_id берём из предыдущей вставки — так автомобиль связывается с клиентом
                    cursor.execute(
                        "INSERT INTO cars (client_id, plate_number, brand, model, release_year) "
                        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                        (client_id, plate_number, brand, model, release_year),
                    )
                    car_ids.append(cursor.fetchone()[0])
    return client_ids, car_ids


# ---------- Пункты меню ----------
# Каждая функция ниже — один пункт меню: спросить пользователя,
# вызвать функцию-запрос из раздела выше, напечатать результат.
# Все функции получают connection — открытое подключение к базе.

def show_all(connection):
    """Пункт 1: показать таблицу целиком."""
    table = ask_table()
    # Пустой список условий — запрос без WHERE
    select_rows(connection, table, [])


def show_filtered_one(connection):
    """Пункт 2: показать строки с фильтром по одной колонке."""
    table = ask_table()
    # many=False — спрашиваем ровно одну пару «колонка = значение»
    conditions = ask_pairs(table, "для фильтра", allow_id=True, many=False)
    select_rows(connection, table, conditions)


def show_filtered_many(connection):
    """Пункт 3: показать строки с фильтром по нескольким колонкам (через AND)."""
    table = ask_table()
    # many=True — пар может быть несколько, пустой ввод завершает список
    conditions = ask_pairs(table, "для фильтра", allow_id=True, many=True)
    select_rows(connection, table, conditions)


def edit_one(connection):
    """Пункт 4: изменить любые поля одной записи, кроме id."""
    table = ask_table()
    record_id = ask("id записи: ")
    # allow_id=False — колонку id выбрать нельзя
    changes = ask_pairs(table, "для изменения", allow_id=False, many=True)
    count = update_one(connection, table, record_id, changes)
    log(f"[OK] Таблица {table}: обновлено строк: {count}")


def edit_many(connection):
    """Пункт 5: одно новое значение для нескольких записей (WHERE ... IN)."""
    table = ask_table()
    # ask_pairs с many=False возвращает список из одной пары; [0] — берём её,
    # а запись «a, b = пара» раскладывает пару на две переменные
    set_column, new_value = ask_pairs(table, "для изменения", allow_id=False, many=False)[0]
    print("Какие строки изменить:")
    # Колонка для отбора тоже проверяется по белому списку
    filter_column = check_column(table, ask("Колонка для отбора: "))
    text = ask(f"Значения {filter_column} через запятую: ")
    # «4, 7» -> ["4", "7"]: режем по запятым и убираем пробелы
    filter_values = [value.strip() for value in text.split(",") if value.strip()]
    if not filter_values:
        raise InputError("нужно указать хотя бы одно значение")
    count = update_many(connection, table, set_column, new_value, filter_column, filter_values)
    log(f"[OK] Таблица {table}: обновлено строк: {count}")


def add_one(connection):
    """Пункт 6: добавить одну строку в выбранную таблицу."""
    table = ask_table()
    columns = ask_columns_for_insert(table)
    # Спрашиваем значение для каждой выбранной колонки по порядку
    row = [ask(f"{column}: ") for column in columns]
    # Одна строка — это список из одного элемента [row]
    new_ids = insert_rows(connection, table, columns, [row])
    log(f"[OK] В таблицу {table} добавлена строка, id = {new_ids[0]}")


def add_many(connection):
    """Пункт 8: добавить несколько строк в одну таблицу (одной транзакцией)."""
    table = ask_table()
    columns = ask_columns_for_insert(table)
    print("Вводите строки по одной. Пустое первое поле — закончить ввод.")
    rows = []
    while True:
        print(f"Строка {len(rows) + 1}:")
        first = ask(f"  {columns[0]}: ")
        # Пустое первое поле — сигнал, что строки закончились
        if not first:
            break
        # Первое значение уже есть, спрашиваем остальные колонки
        row = [first] + [ask(f"  {column}: ") for column in columns[1:]]
        rows.append(row)
    if not rows:
        raise InputError("не введено ни одной строки")
    new_ids = insert_rows(connection, table, columns, rows)
    # map(str, new_ids) переводит числа в текст, чтобы склеить их через запятую
    log(f"[OK] В таблицу {table} добавлено строк: {len(new_ids)}, id: {', '.join(map(str, new_ids))}")


def add_client_with_car(connection):
    """Пункт 7: один клиент и один его автомобиль — две связанные таблицы."""
    full_name = ask("ФИО клиента: ")
    phone = ask("Телефон: ")
    plate_number = ask("Госномер (русские буквы, например А123ВС77): ")
    brand = ask("Марка: ")
    model = ask("Модель: ")
    release_year = ask("Год выпуска: ")
    car = (plate_number, brand, model, release_year)
    # Передаём список из одного клиента, у которого один автомобиль
    client_ids, car_ids = insert_clients(connection, [(full_name, phone, [car])])
    log(f"[OK] Добавлен клиент id = {client_ids[0]} и его автомобиль id = {car_ids[0]}")


def add_clients_with_cars(connection):
    """Пункт 9 (повышенная сложность): несколько клиентов, у каждого несколько автомобилей."""
    print("Вводите клиентов по одному.")
    clients = []
    # Внешний цикл — клиенты, пустое ФИО заканчивает ввод клиентов
    while True:
        full_name = ask("ФИО клиента (пусто — закончить ввод клиентов): ")
        if not full_name:
            break
        phone = ask("  Телефон: ")
        cars = []
        # Внутренний цикл — автомобили этого клиента, пустой госномер заканчивает список
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
    # Все клиенты и все их автомобили вставляются одной транзакцией
    client_ids, car_ids = insert_clients(connection, clients)
    log(f"[OK] Добавлено клиентов: {len(client_ids)}, id: {', '.join(map(str, client_ids))}; "
        f"автомобилей: {len(car_ids)}, id: {', '.join(map(str, car_ids))}")


# Меню: номер пункта -> (название, функция).
# Функции записаны без скобок: это ссылка на функцию, вызывается она позже, в run_menu.
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
    """Читает config.json и проверяет, что в нём только разрешённые настройки."""
    # json.load превращает содержимое файла в словарь Python:
    # {"host": "db", "port": 5432, "dbname": "appdb", "connect_timeout": 5}
    with open(CONFIG_PATH, encoding="utf-8") as file:
        config = json.load(file)

    for key in config:
        if key not in ALLOWED_CONFIG_KEYS:
            raise ValueError(f"недопустимая настройка: {key}")
    return config


def connect():
    """Спрашивает логин и пароль и подключается к БД. При ошибке возвращает None."""
    try:
        config = load_config()
    except (OSError, ValueError) as error:
        # OSError — файла нет или его не прочитать, ValueError — лишняя настройка или битый JSON
        log("[ERROR] Не удалось прочитать файл настроек", is_error=True,
            details=technical_details(error))
        return None

    user = ask("Логин: ")
    # getpass не показывает вводимые символы на экране
    password = getpass.getpass("Пароль: ")
    if not user or not password:
        log("[ERROR] Логин и пароль не должны быть пустыми", is_error=True)
        return None

    try:
        # **config раскладывает словарь в именованные параметры:
        # host="db", port=5432, dbname="appdb", connect_timeout=5.
        # Логин и пароль идут отдельными параметрами, строку подключения мы не склеиваем,
        # поэтому через пароль нельзя подсунуть свои настройки (как в задании 1)
        connection = psycopg2.connect(**config, user=user, password=password)
    except psycopg2.Error as error:
        # Пользователю — общий текст, причина (неверный пароль, нет сервера) — в лог-файл
        log("[ERROR] Не удалось подключиться к БД: проверьте логин, пароль и доступность сервера",
            is_error=True, details=technical_details(error))
        return None

    log(f"[OK] Подключение к БД выполнено, пользователь {user}")
    return connection


def run_menu(connection):
    """Главный цикл: показать меню, выполнить выбранный пункт, повторить."""
    while True:
        print()
        # MENU.items() даёт пары (номер, (название, функция)); функция здесь не нужна
        for key, (title, _) in MENU.items():
            print(f"{key}. {title}")
        print("0. Выход")

        choice = ask("Выберите пункт: ")
        if choice == "0":
            return
        if choice not in MENU:
            print("Нет такого пункта меню", file=sys.stderr)
            # continue — сразу к следующему кругу цикла, то есть снова показать меню
            continue

        title, action = MENU[choice]
        # Ошибка в одном пункте не должна закрывать программу: ловим её,
        # сообщаем и возвращаемся в меню. Порядок except важен — сверху вниз
        try:
            action(connection)
        except InputError as error:
            # Наша ошибка ввода: текст писали мы сами, показываем как есть
            log(f"[ERROR] {error}", is_error=True)
        except psycopg2.Error as error:
            # Ошибка базы: пользователю — понятный текст, в лог — исходный
            log(f"[ERROR] Запрос не выполнен: {friendly_error(error)}", is_error=True,
                details=technical_details(error))
        except EOFError:
            raise  # Ctrl+D — выходим из программы
        except Exception as error:
            # Любая другая ошибка Python — без подробностей на экране
            log("[ERROR] Непредвиденная ошибка", is_error=True, details=technical_details(error))


def main():
    """Подключиться к базе и запустить меню. Возвращает код выхода: 0 — успех, 1 — ошибка."""
    connection = connect()
    if connection is None:
        return 1
    # finally выполняется всегда — и при обычном выходе, и при ошибке,
    # поэтому соединение с базой закрывается в любом случае
    try:
        run_menu(connection)
    finally:
        connection.close()
        log("[INFO] Соединение закрыто, работа завершена")
    return 0


# Этот блок выполняется, только когда файл запущен напрямую (python autoservice.py),
# а не подключён из другого файла через import
if __name__ == "__main__":
    try:
        # sys.exit передаёт код выхода из main() операционной системе
        sys.exit(main())
    except (EOFError, KeyboardInterrupt):
        # Ctrl+D (EOFError) или Ctrl+C (KeyboardInterrupt) — завершаем аккуратно, без трассировки
        print("\nВвод прерван", file=sys.stderr)
        sys.exit(1)
