\connect appdb

GRANT USAGE ON SCHEMA public TO app_user;

GRANT SELECT, INSERT ON customers, products, orders, order_items TO app_user;

GRANT UPDATE (full_name, email, city)               ON customers   TO app_user;
GRANT UPDATE (name, category, price)                ON products    TO app_user;
GRANT UPDATE (customer_id, order_date, status)      ON orders      TO app_user;
GRANT UPDATE (order_id, product_id, quantity, price) ON order_items TO app_user;

