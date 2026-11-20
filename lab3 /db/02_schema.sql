-- Скрипт 2 из 4: четыре таблицы автосервиса.
-- Таблицы создаются от имени администратора (postgres),
-- поэтому владелец таблиц — администратор, а не app_user.

-- \connect — команда psql «перейти в другую базу». Скрипты первого запуска
-- выполняются в служебной базе postgres, а таблицы нужны в appdb.
\connect appdb

-- Расшифровка того, что встречается в описаниях колонок:
--   integer, text, date, numeric(10, 2) — тип данных: целое число, текст, дата,
--     число до 10 цифр, из них 2 после запятой (рубли и копейки);
--   GENERATED ALWAYS AS IDENTITY — база сама выдаёт номера 1, 2, 3...,
--     вставить или изменить номер вручную нельзя;
--   PRIMARY KEY — первичный ключ: уникальный номер строки, по нему её находят;
--   NOT NULL — значение обязательно;
--   UNIQUE — два одинаковых значения в колонке быть не может;
--   REFERENCES таблица (id) — внешний ключ: значение должно совпадать с id
--     существующей строки в другой таблице, так таблицы и связаны;
--   CHECK (...) — условие, которое база проверяет при каждой вставке и изменении;
--   DEFAULT — значение, если при вставке колонку не указали.

-- Клиенты
CREATE TABLE clients (
    id        integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name text NOT NULL,
    phone     text NOT NULL UNIQUE,
    email     text
);

-- Автомобили: у каждого автомобиля есть владелец (связь с clients).
-- Госномер — по образцу А123ВС77: буква, три цифры, две буквы, регион.
-- Буквы только русские заглавные, как на настоящих номерах.
-- Проверка написана регулярным выражением (оператор ~):
--   ^ — начало строки, $ — конец строки;
--   [АВЕКМНОРСТУХ] — одна из этих 12 букв;
--   [0-9]{3} — ровно три цифры, [АВЕКМНОРСТУХ]{2} — ровно две буквы;
--   [0-9]{2,3} — код региона из двух или трёх цифр.
CREATE TABLE cars (
    id           integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_id    integer NOT NULL REFERENCES clients (id),
    plate_number text NOT NULL UNIQUE
                 CHECK (plate_number ~ '^[АВЕКМНОРСТУХ][0-9]{3}[АВЕКМНОРСТУХ]{2}[0-9]{2,3}$'),
    brand        text NOT NULL,
    model        text NOT NULL,
    release_year integer NOT NULL CHECK (release_year BETWEEN 1950 AND 2100)
);

-- Услуги автосервиса (прайс-лист)
CREATE TABLE services (
    id    integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name  text NOT NULL UNIQUE,
    price numeric(10, 2) NOT NULL CHECK (price >= 0)
);

-- Заказ-наряды: какую услугу делаем какому автомобилю
-- (связь с cars и с services).
-- order_date по умолчанию — сегодняшняя дата (CURRENT_DATE),
-- status по умолчанию — «принят», допустимы только четыре значения.
CREATE TABLE work_orders (
    id         integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    car_id     integer NOT NULL REFERENCES cars (id),
    service_id integer NOT NULL REFERENCES services (id),
    order_date date NOT NULL DEFAULT CURRENT_DATE,
    status     text NOT NULL DEFAULT 'принят'
               CHECK (status IN ('принят', 'в работе', 'готов', 'выдан'))
);
