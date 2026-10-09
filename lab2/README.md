# Задание 2. Сервис pinger для PostgreSQL 18

## содержание

| Файл | Назначение |
| --- | --- |
| `app/pinger.py` | Код сервиса |
| `app/config.json` | Настройки подключения и таймауты |
| `app/Dockerfile` | Упаковка сервиса в образ |
| `pinger.env` | Переменные среды для сервиса |
| `docker-compose.yml` | PostgreSQL и сервис вместе |
| `db/Dockerfile`, `db/init.sql` | База данных из задания 1 |

## Переменные среды

| Переменная | Обязательная | Назначение |
| --- | --- | --- |
| `DB_USER` | да | Логин пользователя БД |
| `DB_PASSWORD` | да | Пароль пользователя БД |
| `PING_INTERVAL_SECONDS` | нет | Интервал между проверками в секундах, по умолчанию 300 |
| `LOG_FILE` | нет | Путь к файлу, куда дублируются логи |

## Сборка и запуск

```
docker build -t rzps-pinger:1.0 ./app
docker compose up -d
docker compose logs -f pinger
```

## Проверка: сначала ошибка, потом успех

```
docker compose stop db
docker compose start db
```

Пока база остановлена, в логах появляются строки `[ERROR]`. После запуска базы следующая проверка даёт `[OK]`.

## Просмотр потоков по отдельности

```
docker logs rzps-pinger 2>/dev/null      # только stdout (Linux, macOS)
docker logs rzps-pinger 1>/dev/null      # только stderr (Linux, macOS)
docker logs rzps-pinger 2>$null          # только stdout (PowerShell)
docker logs rzps-pinger 1>$null          # только stderr (PowerShell)
docker exec rzps-pinger cat /logs/pinger.log
```

## Остановка и удаление

```
docker compose down -v
```
