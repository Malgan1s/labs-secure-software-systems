# Задание 1. PostgreSQL 18 в Docker и приложение с запросом версии

## содержание

| Файл | Назначение |
| --- | --- |
| `db/Dockerfile` | Образ PostgreSQL 18 с локалью `ru_RU.UTF-8` |
| `db/init.sql` | Создание базы `appdb` и пользователя `app_user` |
| `app/main.py` | Приложение: подключается к БД и выполняет `SELECT VERSION();` |
| `app/config.json` | Настройки подключения (хост, порт, имя базы, таймаут) |
| `app/requirements.txt` | Зависимости Python |

## Запуск базы данных

```
docker build -t rzps-postgres:18 ./db
docker run -d --name rzps-task1-db -e POSTGRES_PASSWORD=postgres_demo_password -p 127.0.0.1:5432:5432 rzps-postgres:18
```

## Запуск приложения (Linux):

```
cd app
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

логин и пароль: `app_user` / `app_demo_password`

## Остановка и удаление

```
docker rm -f -v rzps-task1-db
```
