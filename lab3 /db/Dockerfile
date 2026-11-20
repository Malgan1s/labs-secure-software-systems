# Образ базы данных: официальный PostgreSQL 18 + русская локаль + наши SQL-скрипты.
# Отдельно его собирать не нужно: docker compose up собирает его сам
# (строка build: ./db в docker-compose.yml) и называет rzps-autoservice-db:1.0.

# FROM — готовый образ, от которого отталкиваемся.
# postgres:18 — официальный образ PostgreSQL версии 18 с Docker Hub.
FROM postgres:18

# RUN — выполнить команду во время сборки образа.
# В официальном образе есть только английская локаль. localedef создаёт русскую
# ru_RU.UTF-8: без неё CREATE DATABASE ... LOCALE 'ru_RU.UTF-8' в 01_init.sql
# завершится ошибкой. Локаль — это правила сортировки и сравнения текста.
RUN localedef -i ru_RU -c -f UTF-8 -A /usr/share/locale/locale.alias ru_RU.UTF-8

# ENV — переменная среды внутри контейнера. LANG — локаль по умолчанию:
# при первом запуске PostgreSQL создаёт свой кластер именно с ней.
ENV LANG=ru_RU.utf8

# COPY — скопировать файлы из папки db (рядом с этим Dockerfile) внутрь образа.
# /docker-entrypoint-initdb.d/ — особая папка официального образа PostgreSQL:
# при ПЕРВОМ запуске контейнера, когда том с данными ещё пуст, он выполняет
# все .sql-файлы из неё по алфавиту, от имени администратора postgres.
# Поэтому файлы пронумерованы: 01 -> 02 -> 03 -> 04.
# При следующих запусках данные уже есть, и скрипты не выполняются.
# Чтобы выполнить их заново, нужно удалить том: docker compose down -v.
COPY 01_init.sql 02_schema.sql 03_grants.sql 04_demo_data.sql /docker-entrypoint-initdb.d/
