\connect appdb

GRANT USAGE ON SCHEMA public TO app_user;

GRANT SELECT, INSERT ON clients, cars, services, work_orders TO app_user;

GRANT UPDATE (full_name, phone, email)                             ON clients     TO app_user;
GRANT UPDATE (client_id, plate_number, brand, model, release_year) ON cars        TO app_user;
GRANT UPDATE (name, price)                                         ON services    TO app_user;
GRANT UPDATE (car_id, service_id, status)                          ON work_orders TO app_user;
