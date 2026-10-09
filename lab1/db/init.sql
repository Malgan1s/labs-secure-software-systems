CREATE DATABASE appdb
    TEMPLATE template0
    ENCODING 'UTF8'
    LOCALE 'ru_RU.UTF-8';

CREATE USER app_user WITH PASSWORD 'app_demo_password';

REVOKE ALL ON DATABASE appdb FROM PUBLIC;
GRANT CONNECT ON DATABASE appdb TO app_user;

\connect appdb
GRANT USAGE ON SCHEMA public TO app_user;
