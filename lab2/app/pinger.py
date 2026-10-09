import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import psycopg2

CONFIG_PATH = Path(__file__).parent / "config.json"

ALLOWED_KEYS = {
    "host",
    "port",
    "dbname",
    "connect_timeout",
    "keepalives",
    "keepalives_idle",
    "keepalives_interval",
    "keepalives_count",
    "tcp_user_timeout",
}

EXPECTED_PREFIX = "PostgreSQL 18"

DEFAULT_INTERVAL = 300

LOG_FILE = os.environ.get("LOG_FILE")


def log(message, is_error=False):

    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}"

    stream = sys.stderr if is_error else sys.stdout
    print(line, file=stream, flush=True)

    if LOG_FILE:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as file:
                file.write(line + "\n")
        except OSError as error:
            print(f"Не удалось записать в лог-файл: {error}", file=sys.stderr, flush=True)


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as file:
        config = json.load(file)

    for key in config:
        if key not in ALLOWED_KEYS:
            raise ValueError(f"недопустимая настройка: {key}")
    return config


def check_database(config, user, password):
    connection = None
    try:
        connection = psycopg2.connect(**config, user=user, password=password)
        cursor = connection.cursor()
        cursor.execute("SELECT VERSION();")
        version = str(cursor.fetchone()[0])
    except psycopg2.Error as error:
        text = " ".join(str(error).split())
        log(f"[ERROR] Не удалось получить версию БД: {text}", is_error=True)
        return
    finally:
        if connection is not None:
            connection.close()

    if version.startswith(EXPECTED_PREFIX):
        log(f"[OK] Подключение успешно. Версия БД: {version}")
    else:
        log(f"[WARNING] Подключение успешно, но ответ нетипичный: {version}")


def main():
    user = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")
    if not user or not password:
        log("[ERROR] Не заданы переменные среды DB_USER и DB_PASSWORD", is_error=True)
        return 1

    try:
        interval = int(os.environ.get("PING_INTERVAL_SECONDS", DEFAULT_INTERVAL))
        if interval <= 0:
            raise ValueError
    except ValueError:
        log("[ERROR] PING_INTERVAL_SECONDS должно быть целым числом больше нуля", is_error=True)
        return 1

    try:
        config = load_config()
    except (OSError, ValueError) as error:
        log(f"[ERROR] Ошибка в файле настроек: {error}", is_error=True)
        return 1

    log(f"[INFO] Сервис запущен. Интервал между проверками: {interval} с")

    try:
        while True:
            try:
                check_database(config, user, password)
            except Exception as error:
                log(f"[ERROR] Непредвиденная ошибка: {error}", is_error=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        log("[INFO] Сервис остановлен")

    return 0


if __name__ == "__main__":
    sys.exit(main())
