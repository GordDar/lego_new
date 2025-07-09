import csv
import io
import os
import re
import unicodedata
from functools import wraps

from flask import Flask, request, jsonify, abort, g
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import check_password_hash, generate_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_cors import CORS
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bs4 import BeautifulSoup
from google.cloud import storage

app = Flask(__name__)

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")
INSTANCE_CONNECTION_NAME = os.getenv("INSTANCE_CONNECTION_NAME")

# app.config['SQLALCHEMY_DATABASE_URI'] = (
#     f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@/"
#     f"{DB_NAME}?host=/cloudsql/{INSTANCE_CONNECTION_NAME}"
# )
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:postgres@db:5432/mydb'
app.config['SECRET_KEY'] = 'very_secret_key'
app.secret_key = 'very_secret_key'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
CORS(app)

storage_client = storage.Client()  # Предполагается, что настроены переменные окружения или сервисный аккаунт

BUCKET_NAME = 'bucket-wanted-lists_lego-bricks-app'


from app_lego.models import Order, CatalogItem, Category, AdminUser, Settings, OrderItem


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'message': 'Token missing or invalid'}), 401

        token = auth_header.split()[1]

        if token != os.getenv("SECRET_TOKEN"):
            return jsonify({'message': 'Invalid or expired token'}), 401

        g.current_user = AdminUser.query.filter_by(username='admin').first()  # сохраняем в глобальный контекст
        return f(*args, **kwargs)
    return decorated


# --- 1. Каталог (GET /catalog) ---
@app.route('/catalog', methods=['GET'])
def get_catalog():
    search = request.args.get('search', '', type=str)
    search_category = request.args.get('category', '', type=str)
    search_id = request.args.get('search_id', '', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = CatalogItem.query

    # Добавляем фильтр для исключения товаров с количеством 0
    query = query.filter(CatalogItem.quantity > 0)

    # Поиск по общим полям
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                CatalogItem.color.ilike(search_term),
                CatalogItem.description.ilike(search_term)
            )
        )

    # Поиск по id товара
    if search_id:
        query = query.filter(CatalogItem.item_no.ilike(f"%{search_id}%"))

    # Поиск по названию категории
    if search_category:
        # Ищем категорию по имени
        category = Category.query.filter_by(name=search_category).first()
        if category:
            # Фильтруем товары по category_id
            query = query.filter(CatalogItem.category_id == category.id)
        else:
            # Если категория не найдена, возвращаем пустой результат
            return jsonify({
                'items': [],
                'total': 0,
                'pages': 0,
                'current_page': page
            })

    query = query.order_by(CatalogItem.id)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    items = [{
        'item_no': item.item_no,
        'url': item.url,
        'color': item.color,
        'description': item.description,
        'price': item.price,
        'quantity': item.quantity,
        'category_name': item.category.name if item.category else None,
        'remarks': item.remarks
    } for item in pagination.items]

    return jsonify({
        'items': items,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    })

# --- 2. Отправка корзины (POST /cart) ---
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ?????
SMTP_SERVER = 'smtp.yandex.ru'
SMTP_PORT = 587
EMAIL_ADDRESS = 'legostorage@yandex.ru'  # ваш email
EMAIL_PASSWORD = 'lego_storage_password' # ваш пароль

# Данные на почту
def send_order_email(order, order_details):
    subject = f"Новый заказ #{order.id}"
    to_email = 'legobricks2025@gmail.com'
    
    # Формируем тело письма
    body = f"Новый заказ №{order.id}\n"
    body += f"Дата: {order.created_at}\n"
    body += f"Клиент: {order.customer_name}\n"
    body += f"Телефон: {order.customer_telephone}\n"
    body += f"Почта: {order.customer_email}\n"
    body += f"Доставка: {'Да' if order.dostavka else 'Нет'}\n"
    body += f"Время создания заказа: {order.created_at}\n"
    body += f"Общая сумма: {order.total_price}\n\n"
    body += "Позиции заказа:\n"
    
    for item in order_details:
        body += (
            f"- {item['description']} | "
            f"Количество: {item['quantity_in_order']} | "
            f"Цена за единицу: {item['unit_price']} | "
            f"Итого: {item['total_price']}\n"
        )
    
    # Создаем сообщение
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    
    # Отправка письма через SMTP
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        print("Email успешно отправлен")
    except Exception as e:
        print(f"Ошибка при отправке email: {e}")

@app.route('/cart', methods=['POST'])
def submit_cart():
    data = request.json
    items_data = data.get('items')
    customer_name = data.get('customer_name')
    customer_telephone = data.get('customer_telephone')
    customer_email = data.get('customer_email')
    dostavka = data.get('dostavka', False)

    if not items_data or not customer_name or not customer_telephone:
        return jsonify({'error': 'Missing required fields'}), 400

    order_details_for_email = []
    total_price = 0  # Инициализация суммы заказа

    # Проходим по товарам, чтобы посчитать сумму
    for item in items_data:
        catalog_item_id = item['item_no']
        quantity_requested = item.get('quantity', 1)
        catalog_item = CatalogItem.query.get(catalog_item_id)

        if not catalog_item:
            return jsonify({'error': f'Item with id {catalog_item_id} not found'}), 404
        if catalog_item.quantity < quantity_requested:
            return jsonify({
                'error': f'Недостаточно товара "{catalog_item.description}". '
                         f'Доступно: {catalog_item.quantity}, запрошено: {quantity_requested}'
            }), 400

        price_per_unit = getattr(catalog_item, 'price', 0)
        total_price += price_per_unit * quantity_requested  # Добавляем к общей сумме

        # Собираем данные для email
        order_details_for_email.append({
            'description': catalog_item.description,
            'quantity_in_order': quantity_requested,
            'unit_price': price_per_unit,
            'total_price': price_per_unit * quantity_requested
        })

    # Проверка минимальной суммы заказа
    settings = Settings.query.filter_by(settings_name='min').first()
    if settings and settings.settings_value is not None:
        if total_price < settings.settings_value:
            return jsonify({
                'error': f'Минимальная сумма заказа составляет {settings.settings_value}. '
                         f'Ваш заказ на сумму {total_price} не может быть принят.'
            }), 400

    # Создаем заказ с рассчитанной суммой
    order = Order(
        customer_name=customer_name,
        customer_telephone=customer_telephone,
        customer_email= customer_email,
        dostavka=dostavka,
        total_price=total_price
    )

    for item in items_data:
        catalog_item_id = item['id']
        quantity_requested = item.get('quantity', 1)
        catalog_item = CatalogItem.query.get(catalog_item_id)

        order_item = OrderItem(
            catalog_item=catalog_item,
            quantity=quantity_requested
        )
        db.session.add(order_item)
        order.order_items.append(order_item)

        # Обновляем количество на складе
        catalog_item.quantity -= quantity_requested

    db.session.add(order)
    db.session.commit()

    # Отправляем письмо с заказом
    send_order_email(order, order_details_for_email)

    return jsonify({'message': 'Order created', 'order_id': order.id})

# --- 3. Логин для админки (POST /admin/login) ---
@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = AdminUser.query.filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, password):
        return jsonify({'access_token': os.getenv("SECRET_TOKEN")})
    
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    logout_user()
    return {}

# --- 4. Просмотр заказов в админке (GET /admin/orders) ---
@app.route('/admin/orders', methods=['GET'])
@token_required
def get_orders():
    status_filter = request.args.get('status')  # например, 'new', 'completed'
    date_from = request.args.get('created_at')   # формат: 'YYYY-MM-DD'
    date_to = request.args.get('date_to')  
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    orders_query = Order.query

    if status_filter:
        orders_query = orders_query.filter(Order.status == status_filter)
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            orders_query = orders_query.filter(Order.created_at >= date_from_obj)
        except ValueError:
            pass  # некорректный формат даты, можно обработать ошибку
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            # добавляем один день, чтобы включить дату окончания
            date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
            orders_query = orders_query.filter(Order.created_at <= date_to_obj)
        except ValueError:
            pass

    orders_query = orders_query.order_by(Order.id.desc())
    orders_list = []
    
    for order in orders_query:
        items_list = []
        
        for item in order.order_items:
            catalog_item = item.catalog_item
            price_per_unit = getattr(catalog_item, 'price', 0)

            
            items_list.append({
                'item_no': getattr(catalog_item, 'item_no', None),
                'url': item.url,
                'color': getattr(catalog_item, 'color', None),
                'quantity_in_order': item.quantity,
                'unit_price': price_per_unit,
                'total_price': item.quantity*price_per_unit,
                'remarks': getattr(item, 'remarks', None)
            })
        
        orders_list.append({
            'customer_name': order.customer_name,
            'customer_telephone': order.customer_telephone,
            'customer_email': order.customer_email,
            'dostavka': order.dostavka,
            'total_price': order.total_price,
            'status': order.status,  # добавлено
            'created_at': (order.created_at or datetime.now()).isoformat(),  # добавлено
            'items': items_list,
            'remarks': getattr(order, 'remarks', None)
        })
        
       
    
    pagination = orders_query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'orders_list': orders_list,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    })
    
    
# --- 4.1. Удаление выполненных заказов в админке (DELETE /admin/orders/{order_id}) --- 
@app.route('/admin/orders/<int:order_id>', methods=['DELETE'])
@token_required
def delete_order(order_id):
    # Ищем заказ по ID
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    # Проверяем статус заказа
    # TODO: uncomment
    # if order.status != 'исполнен':
    #     return jsonify({'error': 'Only completed orders can be deleted'}), 400

    try:
        db.session.delete(order)
        db.session.commit()
        return jsonify({'message': f'Order {order_id} has been deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete order', 'details': str(e)}), 500


# --- 5. Установка курса валют в админке (POST /admin/set_currency) ---
# создание строчек изначально
def create_initial_settings():
    initial_settings = [
        {'settings_name': 'byn', 'settings_value': 0},
        {'settings_name': 'rub', 'settings_value': 0},
        {'settings_name': 'min', 'settings_value': 0}
    ]

    for setting in initial_settings:
        # Проверяем, есть ли уже такая запись, чтобы не дублировать
        existing = Settings.query.filter_by(settings_name=setting['settings_name']).first()
        if not existing:
            new_setting = Settings(
                settings_name=setting['settings_name'],
                settings_value=setting['settings_value']
            )
            db.session.add(new_setting)
    db.session.commit()
      

@app.route('/admin/set_currency', methods=['POST'])
@token_required
def update_settings():
    data = request.get_json()
    
 # Значение приходит как множество, например {2.11}, !!!! {'курс белорусского рубля': {2.11}, 'курс российского рубля': {3.15}, 'минимальная сумма заказа': {15}}
 #    for key, value_set in data.items():
 #        # Получим первое (и единственное) значение из множества
 #        value = next(iter(value_set), None)
 #
 #        if value is not None:
 #            # Найти настройку по имени
 #            setting = Settings.query.filter_by(settings_name=key).first()
 #            if setting:
 #                # Обновляем только если значение не пустое
 #                if value != '' and value is not None:
 #                    setting.settings_value = float(value)
 #    try:
 #        db.session.commit()
 #        return jsonify({"status": "success"}), 200
 #    except Exception as e:
 #        db.session.rollback()
 #        return jsonify({"status": "error", "message": str(e)}), 500
    
    # Если настройки приходят как float, !!!!{'byn': 2.11, 'rub': 3.15, 'min': 15}
    for key, value in data.items():
        # Ищем настройку по имени
        setting = Settings.query.filter_by(settings_name=key).first()
        if setting:
            # Обновляем только если значение не пустое
            if value is not None and value != '':
                setting.settings_value = float(value)
    try:
        db.session.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500



# --- 6. Структура категорий ---
def build_nested_structure(categories):
    structure = {}
    for category in categories:
        parts = [part.strip() for part in category.name.split('/')]
        current_level = structure
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current_level[part] = current_level.get(part, {})
            else:
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]
    return structure

@app.get("/category-structure")
def get_category_structure():
    categories = Category.query.all()
    nested_structure = build_nested_structure(categories)
    
    return jsonify(nested_structure)



# --- 7. Просмотр одного заказа из админки ---
@app.route('/admin/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    order = Order.query.filter(Order.id == order_id).first()
    if not order:
        abort(404, description="Order not found")
    
    items_list = []


    for item in order.order_items:
        catalog_item = item.catalog_item
        price_per_unit = catalog_item.price if catalog_item else 0
        quantity = item.quantity

        items_list.append({
            'item_no': catalog_item.item_no,
            'url': catalog_item.url,
            'color': catalog_item.color,
            'description': catalog_item.description,
            'quantity_in_order': quantity,
            'unit_price': price_per_unit,
            'total_price': quantity*price_per_unit,
            "remarks": catalog_item.remarks,
            "quantity": catalog_item.quantity
        })

    response_data = {
        "id": order.id,
        "customer_name": order.customer_name,
        "customer_telephone": order.customer_telephone,
        "customer_email": order.customer_email,
        "dostavka": order.dostavka,
        "total_price": order.total_price,
        "items": items_list,
    }

    return jsonify(response_data)




# --- 8. Просмотр данных по 1 детали ---
@app.route('/catalog_item/<int:item_id>', methods=['GET'])
def get_catalog_item(item_id):
    item = CatalogItem.query.get(item_id)
    if item:
        return jsonify({
            'item_no': item.item_no,
            'color': item.color,
            'category': item.category.name,
            'condition': item.condition,
            'description': item.description,
            'price': item.price,
            'quantity': item.quantity,
            'url': item.url,
            'currency': item.currency,
            'remarks': item.remarks
        })
    else:
        abort(404, description="Item not found")


def str_to_bool(s):
    return s.strip().lower() in ['true', '1', 'yes']



# --- 9. Создание базы данных ---
def get_or_create(session: Session, model, defaults=None, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False  # False = not created
    else:
        params = dict(**kwargs)
        if defaults:
            params.update(defaults)
        instance = model(**params)
        session.add(instance)
        try:
            session.commit()
            return instance, True  # True = created
        except IntegrityError:
            session.rollback()
            return session.query(model).filter_by(**kwargs).first(), False
        
        
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def get_image_src_with_selenium(item_no):
    url = f'https://www.bricklink.com/v2/catalog/catalogitem.page?P={item_no}'
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # запуск без графического интерфейса

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        img = wait.until(EC.presence_of_element_located((By.ID, '_idImageMain')))
        src = img.get_attribute('src')
        return src
    finally:
        driver.quit()



@app.route('/db_add', methods=['POST'])
def db_add():
    data = request.get_json()
    file_name = data.get('file_name')
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(file_name)

        content = blob.download_as_text(encoding='utf-8')

        reader = csv.DictReader(io.StringIO(content))

        # Обработка заголовков
        rows = []
        for row in reader:
            row = {(k or '').strip(): v for k, v in row.items()}
            rows.append(row)

        db.session.query(Category).delete()
        db.session.query(OrderItem).delete()
        db.session.query(CatalogItem).delete()
        db.session.commit()

        image_cache = {}

        for row in rows:
            item_no = row.get('Item No', '').strip()

            # Получение изображения по item_no
            if item_no:
                if item_no in image_cache:
                    image_url = image_cache[item_no]
                else:
                    try:
                        image_url = get_image_src_with_selenium(item_no)
                        image_cache[item_no] = image_url
                    except Exception as e:
                        print(f"Ошибка при получении изображения для Item No {item_no}: {e}")
                        image_url = None
            else:
                image_url = None

            # Обработка категории
            category_name = row['Category'].strip()
            category, created = get_or_create(db.session, Category, name=category_name)

            # Создаем объект CatalogItem
            item = CatalogItem(
                lot_id=row['Lot ID'].strip(),
                color=row['Color'].strip(),
                category_id=category.id,
                condition=row.get('Condition', '').strip(),
                sub_condition=row.get('Sub-Condition', '').strip(),
                description=row.get('Description', '').strip(),
                remarks=row.get('Remarks', '').strip(),
                price=float(row['Price'].replace('$', '').strip()) if row.get('Price') else None,
                quantity=int(row['Quantity']) if row.get('Quantity') else None,
                bulk=str_to_bool(row.get('Bulk', 'False')),
                sale=str_to_bool(row.get('Sale', 'False')),
                url= image_url,
                item_no=item_no,
                tier_qty_1=int(row['Tier Qty 1']) if row['Tier Qty 1'] else None,
                tier_price_1=float(row['Tier Price 1'].replace('$', '').strip()) if row['Tier Price 1'] else None,
                tier_qty_2=int(row['Tier Qty 2']) if row['Tier Qty 2'] else None,
                tier_price_2=float(row['Tier Price 2'].replace('$', '').strip()) if row['Tier Price 2'] else None,
                tier_qty_3=int(row['Tier Qty 3']) if row['Tier Qty 3'] else None,
                tier_price_3=float(row['Tier Price 3'].replace('$', '').strip()) if row['Tier Price 3'] else None,
                reserved_for=row.get('Reserved For', '').strip(),
                stockroom=row.get('Stockroom', '').strip(),
                retain=str_to_bool(row.get('Retain', 'False')),
                super_lot_id=row.get('Super Lot ID', '').strip(),
                super_lot_qty=int(row['Super Lot Qty']) if row.get('Super Lot Qty') else None,
                weight=float(row['Weight']) if row.get('Weight') else None,
                extended_description=row.get('Extended Description', '').strip(),

                date_added=datetime.strptime(row['Date Added'], '%m/%d/%Y') if row.get('Date Added') else None,
                date_last_sold=datetime.strptime(row['Date Last Sold'], '%Y-%m-%d') if row.get(
                    'Date Last Sold') else None,

                currency=row.get('Currency', '').strip()
            )
            db.session.add(item)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    return 'Success', 200



# --- 10. Просмотр деталей по категории ---
@app.get("/categories/<category_part>")
def get_items_by_category_part(category_part):
    categories = Category.query.filter(Category.name.ilike(f"%{category_part}%")).all()
    
    if not categories:
        abort(404, description="No matching categories found")
    
    category_ids = [cat.id for cat in categories]
    
    # ищем товары по этим категориям
    items = CatalogItem.query.filter(CatalogItem.category_id.in_(category_ids)).all()
    
    def serialize_item(item):
        return {
            "item_no": item.item_no,
            "color": item.color,
            "description": item.description,
            "price": item.price,
            "quantity": item.quantity,
            "url": item.url,
        }
    
    return jsonify([serialize_item(item) for item in items])


# --- 11. Создание или изменение деталей ---
@app.route('/catalog_item/<int:item_id>', methods=['POST'])
def update_or_create(item_id):
    data = request.get_json()
    if not data:
        abort(400, description="Invalid JSON data")
    
    item_no = data.get('item_no')
    if not item_no:
        abort(400, description="Missing 'item_no' in request data")

    if item_id == 0:
        item = None
    else:
        item = CatalogItem.query.filter_by(id=item_id).first()
    
    if item:
        # Обновляем только те поля, которые есть в данных и не пустые
        for field in ['lot_id', 'color', 'description', 'price', 'quantity', 'url', 'category', 'condition', 'remarks']:
            value = data.get(field)
            if value is not None:
                # Для строковых полей можно дополнительно проверить на пустую строку
                if isinstance(value, str) and value.strip() == '':
                    continue  # пропускаем пустые строки
                # Обновляем поле
                if field == 'category':
                    # Обработка категории отдельно
                    category_name = value
                    category, _ = get_or_create(db.session, Category, name=category_name)
                    setattr(item, 'category_id', category.id)
                else:
                    setattr(item, field, value)
        
    else:
        # Создаем новую запись
        category_obj = None
        category_name = data.get('category')
        if category_name:
            category_obj, _ = get_or_create(db.session, Category, name=category_name)
        
        new_item = CatalogItem(
            item_no=item_no,
            color=data.get('color'),
            description=data.get('description'),
            price=data.get('price'),
            quantity=data.get('quantity'),
            url=data.get('url') if data else get_image_src_with_selenium(item_no),
            category_id=category_obj.id if category_obj else None,
            remarks = data.get('remarks')
        )
        db.session.add(new_item)
    
    db.session.commit()
    return jsonify({"status": "success"}), 200




# --- 12. presigned_url ---

def sanitize_filename(filename):
    # Приводим к ASCII
    nfkd_form = unicodedata.normalize('NFKD', filename)
    ascii_filename = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
    # Удаляем любые недопустимые символы
    ascii_filename = re.sub(r'[^A-Za-z0-9_.-]', '_', ascii_filename)
    return ascii_filename

@app.route('/presigned_url', methods=['POST'])
def presigned_url():
    data = request.get_json()
    if not data or 'file_name' not in data:
        abort(400, description="Missing 'file_name' in request data")
    
    original_file_name = data['file_name']
    file_name = sanitize_filename(original_file_name)

    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(file_name)

        # Генерация предподписанного URL для загрузки (PUT)
        url = blob.generate_signed_url(
            version='v4',
            expiration=3600,  # Время действия URL в секундах
            method='PUT'
        )

        return jsonify({'url': url, 'file_name': file_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    
    
# --- 13. Загрузка wanted_list ---
def parse_xml_from_gcs(file_name):
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(file_name)

        # Проверка существования файла
        if not blob.exists():
            print(f"Файл {file_name} не найден в бакете {BUCKET_NAME}.")
            return

        # Получение содержимого файла как байтов
        xml_bytes = blob.download_as_bytes()

        # Декодируем байты в строку
        xml_content = xml_bytes.decode('utf-8')

        # Парсим XML из строки
        soup = BeautifulSoup(xml_content, 'xml')
        items = soup.find_all('ITEM')

        for item in items:
            item_id_text = item.find('ITEMID').text
            item_type = item.find('ITEMTYPE').text
            color = item.find('COLOR').text
            max_price_text = item.find('MAXPRICE').text
            min_qty_text = item.find('MINQTY').text
            condition = item.find('CONDITION').text
            notify = item.find('NOTIFY').text

            # Преобразуем числовые значения
            try:
                max_price = float(max_price_text)
                min_qty = int(min_qty_text)
            except (ValueError, AttributeError):
                print(f"Некорректные данные для ITEMID={item_id_text}")
                continue

            existing_item = CatalogItem.query.filter_by(item_no=item_id_text).first()

            if existing_item:
                print(f"Найден товар: {existing_item}")            
            else:
                print(f"Товар с ITEMID={item_id_text} не найден в базе.")
    except Exception as e:
        print(f"Ошибка при получении файла из GCS: {e}")

# вызов функции с именем файла в GCS
# parse_xml_from_gcs('путь/к/вашему.xml')?????







# --- Запуск приложения ---
if __name__ == '__main__':
    app.run(debug=True)