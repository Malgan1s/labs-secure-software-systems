\connect appdb

CREATE TABLE customers (
    id        integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name text NOT NULL,
    email     text NOT NULL UNIQUE,
    city      text
);

CREATE TABLE products (
    id       integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name     text NOT NULL,
    category text NOT NULL,
    price    numeric(10, 2) NOT NULL CHECK (price >= 0)
);

CREATE TABLE orders (
    id          integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id integer NOT NULL REFERENCES customers (id),
    order_date  date NOT NULL DEFAULT CURRENT_DATE,
    status      text NOT NULL DEFAULT 'новый'
                CHECK (status IN ('новый', 'оплачен', 'доставлен', 'отменен'))
);

CREATE TABLE order_items (
    id         integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id   integer NOT NULL REFERENCES orders (id),
    product_id integer NOT NULL REFERENCES products (id),
    quantity   integer NOT NULL CHECK (quantity > 0),
    price      numeric(10, 2) NOT NULL CHECK (price >= 0)
);
