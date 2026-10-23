# Задание 3 – база интернет-магазина и консольная программа

PostgreSQL 18 и программа на Python работают в одной сети Docker Compose.
Программа позволяет просматривать, изменять и добавлять данные, а имена таблиц
и колонок проверяет по белому списку, поэтому SQL-инъекция через них невозможна.

## Состав

```
lab3/
├── db/
│   ├── Dockerfile          PostgreSQL 18 + русская локаль
│   ├── 01_init.sql         база appdb и пользователь app_user
│   ├── 02_schema.sql       4 связанные таблицы
│   ├── 03_grants.sql       права app_user
│   └── 04_demo_data.sql    демонстрационные данные
├── app/
│   ├── shop.py             программа
│   ├── config.json         настройки подключения
│   ├── requirements.txt    зависимости Python
│   └── Dockerfile          упаковка программы
├── app.env                 переменные среды (LOG_FILE)
├── docker-compose.yml      PostgreSQL + программа
└── README.md
```

## Таблицы

- `customers` – покупатели
- `products` – товары
- `orders` – заказы, `customer_id` → `customers.id`
- `order_items` – позиции заказов, `order_id` → `orders.id`, `product_id` → `products.id`

## Запуск

```bash
cd lab3
docker build -t rzps-shop:1.0 ./app     # тегированный образ программы
docker compose up -d db                 # PostgreSQL; при первом запуске выполняются SQL-скрипты
docker compose ps                       # ждём статус (healthy)
docker compose run --rm app             # программа в интерактивном режиме
```

Логин `app_user`, пароль `app_demo_password`.

Лог-файл: `docker compose run --rm --no-deps app cat /logs/shop.log`

Остановить: `docker compose down`. Удалить данные и начать с чистой базы: `docker compose down -v`.

## Права app_user

- может: подключаться только к `appdb`, читать и добавлять строки во все 4 таблицы, изменять все колонки, кроме `id`;
- не может: удалять строки, менять `id`, создавать и удалять таблицы, подключаться к другим базам.
