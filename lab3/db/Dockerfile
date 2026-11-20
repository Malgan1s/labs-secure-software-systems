FROM postgres:18

RUN localedef -i ru_RU -c -f UTF-8 -A /usr/share/locale/locale.alias ru_RU.UTF-8

ENV LANG=ru_RU.utf8

COPY 01_init.sql 02_schema.sql 03_grants.sql 04_demo_data.sql /docker-entrypoint-initdb.d/
