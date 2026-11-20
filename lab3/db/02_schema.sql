\connect appdb

CREATE TABLE clients (
    id        integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name text NOT NULL,
    phone     text NOT NULL UNIQUE,
    email     text
);

CREATE TABLE cars (
    id           integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_id    integer NOT NULL REFERENCES clients (id),
    plate_number text NOT NULL UNIQUE
                 CHECK (plate_number ~ '^[АВЕКМНОРСТУХ][0-9]{3}[АВЕКМНОРСТУХ]{2}[0-9]{2,3}$'),
    brand        text NOT NULL,
    model        text NOT NULL,
    release_year integer NOT NULL CHECK (release_year BETWEEN 1950 AND 2100)
);

CREATE TABLE services (
    id    integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name  text NOT NULL UNIQUE,
    price numeric(10, 2) NOT NULL CHECK (price >= 0)
);

CREATE TABLE work_orders (
    id         integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    car_id     integer NOT NULL REFERENCES cars (id),
    service_id integer NOT NULL REFERENCES services (id),
    order_date date NOT NULL DEFAULT CURRENT_DATE,
    status     text NOT NULL DEFAULT 'принят'
               CHECK (status IN ('принят', 'в работе', 'готов', 'выдан'))
);
