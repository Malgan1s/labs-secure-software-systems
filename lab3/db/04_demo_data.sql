\connect appdb

INSERT INTO clients (full_name, phone, email) VALUES
    ('Иванов Иван',     '+79001112233', 'ivanov@example.com'),
    ('Петрова Анна',    '+79002223344', 'petrova@example.com'),
    ('Сидоров Пётр',    '+79003334455', NULL),
    ('Кузнецова Мария', '+79004445566', 'kuz@example.com'),
    ('Смирнов Олег',    '+79005556677', 'smirnov@example.com');

INSERT INTO cars (client_id, plate_number, brand, model, release_year) VALUES
    (1, 'А123ВС77',  'Toyota',     'Camry',   2018),
    (1, 'В456ОР177', 'Kia',        'Rio',     2020),
    (2, 'Е789КМ50',  'Lada',       'Vesta',   2021),
    (3, 'К321МН77',  'Toyota',     'RAV4',    2019),
    (4, 'М654ТХ199', 'Hyundai',    'Solaris', 2017),
    (5, 'Н987СУ77',  'Volkswagen', 'Polo',    2016);

INSERT INTO services (name, price) VALUES
    ('Замена масла',             2500.00),
    ('Диагностика',              1500.00),
    ('Замена тормозных колодок', 4000.00),
    ('Шиномонтаж',               2000.00),
    ('Развал-схождение',         3000.00),
    ('Замена свечей зажигания',  1800.00);

INSERT INTO work_orders (car_id, service_id, order_date, status) VALUES
    (1, 1, '2026-10-01', 'выдан'),
    (1, 2, '2026-10-01', 'выдан'),
    (3, 4, '2026-10-10', 'готов'),
    (4, 3, '2026-10-15', 'в работе'),
    (2, 5, '2026-11-02', 'принят'),
    (5, 1, '2026-11-05', 'принят'),
    (6, 2, '2026-11-10', 'в работе');
