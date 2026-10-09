import getpass
import json
import sys
from pathlib import Path

import psycopg2

CONFIG_PATH = Path(__file__).parent / "config.json"

ALLOWED_KEYS = {"host", "port", "dbname", "connect_timeout"}


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as file:
        config = json.load(file)

    for key in config:
        if key not in ALLOWED_KEYS:
            raise ValueError(f"недопустимая настройка: {key}")
    return config


def main():
    try:
        config = load_config()
    except (OSError, ValueError) as error:
        print(f"Ошибка в файле настроек: {error}", file=sys.stderr)
        return 1

    user = input("Логин: ")
    password = getpass.getpass("Пароль: ")
    if not user or not password:
        print("Логин и пароль не должны быть пустыми", file=sys.stderr)
        return 1

    connection = None
    try:
        connection = psycopg2.connect(**config, user=user, password=password)
        cursor = connection.cursor()
        cursor.execute("SELECT VERSION();")
        version = cursor.fetchone()[0]
        print(f"Версия БД: {version}")
    except psycopg2.Error as error:
        print(f"Ошибка работы с БД: {str(error).strip()}", file=sys.stderr)
        return 1
    finally:
        if connection is not None:
            connection.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
