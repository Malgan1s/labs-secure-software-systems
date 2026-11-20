-- Скрипт 3 из 4: права пользователя приложения app_user.
-- Принцип минимальных привилегий: только то, что нужно программе.
-- Общий вид команды: GRANT какие_права ON на_что TO кому;
-- Всё, что не выдано явно, app_user делать не может.
\connect appdb

-- Доступ к схеме public — «папке», в которой лежат таблицы.
-- USAGE разрешает обращаться к объектам схемы, но не создавать в ней новые.
GRANT USAGE ON SCHEMA public TO app_user;

-- Читать (SELECT) и добавлять строки (INSERT) можно во всех четырёх таблицах
GRANT SELECT, INSERT ON clients, cars, services, work_orders TO app_user;

-- Изменять (UPDATE) можно только колонки, перечисленные в скобках.
-- Колонку id менять нельзя нигде, а в заказ-наряде нельзя менять ещё и дату
-- приёма (order_date): её нельзя переписать задним числом даже в обход программы.
-- Программа такую попытку пропустит, а база ответит «недостаточно прав».
GRANT UPDATE (full_name, phone, email)                             ON clients     TO app_user;
GRANT UPDATE (client_id, plate_number, brand, model, release_year) ON cars        TO app_user;
GRANT UPDATE (name, price)                                         ON services    TO app_user;
GRANT UPDATE (car_id, service_id, status)                          ON work_orders TO app_user;

-- DELETE, TRUNCATE, DROP и CREATE не выдаём: удалить данные
-- или изменить структуру базы app_user не может.
