\connect appdb

INSERT INTO customers (full_name, email, city) VALUES
    ('Иванов Иван',     'ivanov@example.com',  'Москва'),
    ('Петрова Анна',    'petrova@example.com', 'Санкт-Петербург'),
    ('Сидоров Пётр',    'sidorov@example.com', 'Москва'),
    ('Кузнецова Мария', 'kuz@example.com',     'Казань'),
    ('Смирнов Олег',    'smirnov@example.com', 'Новосибирск');

INSERT INTO products (name, category, price) VALUES
    ('Ноутбук',            'Электроника', 75000.00),
    ('Мышь',               'Электроника',  1200.00),
    ('Клавиатура',         'Электроника',  3500.00),
    ('Книга «Python»',     'Книги',         900.00),
    ('Книга «PostgreSQL»', 'Книги',        1100.00),
    ('Кружка',             'Посуда',        450.00);

INSERT INTO orders (customer_id, order_date, status) VALUES
    (1, '2026-10-01', 'доставлен'),
    (2, '2026-10-05', 'оплачен'),
    (1, '2026-10-12', 'новый'),
    (3, '2026-10-15', 'отменен');

INSERT INTO order_items (order_id, product_id, quantity, price) VALUES
    (1, 1, 1, 75000.00),
    (1, 2, 1,  1200.00),
    (2, 4, 2,   900.00),
    (2, 5, 1,  1100.00),
    (3, 6, 4,   450.00),
    (3, 3, 1,  3500.00),
    (4, 2, 2,  1200.00);
