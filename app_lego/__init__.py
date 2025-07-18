import csv
import io
import os
import re
import unicodedata
from functools import wraps

from flask import Flask, request, jsonify, abort, g, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
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
migrate = Migrate()
migrate.init_app(app, db)
login_manager = LoginManager(app)
CORS(app)

storage_client = storage.Client()  # Предполагается, что настроены переменные окружения или сервисный аккаунт

BUCKET_NAME = 'bucket-wanted-lists_lego-bricks-app'


from app_lego.models import Order, CatalogItem, Category, AdminUser, Settings, OrderItem, Images, MoreId


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




color_dict = {
    'Black': '11',
    'Blue': '7',
    'Bright Green': '36',
    'Bright Light Blue': '105',
    'Bright Light Orange': '110',
    'Bright Light Yellow': '103',
    'Bright Pink': '104',
    'Brown': '8',
    'Chrome Silver': '22',
    'Coral': '220',
    'Dark Azure': '153',
    'Dark Blue': '63',
    'Dark Bluish Gray': '85',
    'Dark Brown': '120',
    'Dark Gray': '10',
    'Dark Green': '80',
    'Dark Orange': '68',
    'Dark Pink': '47',
    'Dark Purple': '89',
    'Dark Red': '59',
    'Dark Tan': '69',
    'Dark Turquoise': '39',
    'Flat Dark Gold': '81',
    'Flat Silver': '95',
    'Glitter Trans-Clear': '101',
    'Glitter Trans-Light Blue': '162',
    'Glitter Trans-Purple': '102',
    'Green': '6',
    'Lavender': '154',
    'Light Aqua': '152',
    'Light Bluish Gray': '86',
    'Light Brown': '91',
    'Light Gray': '9',
    'Light Nougat': '90',
    'Lime': '34',
    'Maersk Blue': '72',
    'Magenta': '71',
    'Medium Azure': '156',
    'Medium Blue': '42',
    'Medium Lavender': '157',
    'Medium Nougat': '150',
    'Medium Orange': '31',
    'Metallic Copper': '250',
    'Metallic Gold': '65',
    'Metallic Silver': '67',
    'Nougat': '28',
    'Olive Green': '155',
    'Orange': '4',
    'Pearl Dark Gray': '77',
    'Pearl Gold': '115',
    'Pearl Light Gray': '66',
    'Red': '5',
    'Reddish Brown': '88',
    'Reddish Copper': '249',
    'Sand Blue': '55',
    'Sand Green': '48',
    'Satin Trans-Light Blue': '229',
    'Tan': '2',
    'Trans-Black': '251',
    'Trans-Bright Green': '108',
    'Trans-Brown': '13',
    'Trans-Clear': '12',
    'Trans-Dark Blue': '14',
    'Trans-Dark Pink': '50',
    'Trans-Green': '20',
    'Trans-Light Blue': '15',
    'Trans-Light Purple': '114',
    'Trans-Medium Blue': '74',
    'Trans-Neon Green': '16',
    'Trans-Neon Orange': '18',
    'Trans-Orange': '98',
    'Trans-Purple': '51',
    'Trans-Red': '17',
    'Trans-Yellow': '19',
    'Very Light Bluish Gray': '99',
    'White': '1',
    'Yellow': '3',
    'Yellowish Green': '158',
    'n/a': '0'
}






# --- 1. Каталог (GET /catalog) ---
from sqlalchemy import or_


@app.route('/catalog', methods=['GET'])
def get_catalog():
    search = request.args.get('search', '', type=str)
    search_category = request.args.get('category', '', type=str)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = CatalogItem.query

    # Добавляем фильтр для исключения товаров с количеством 0
    query = query.filter(CatalogItem.quantity > 0)

    # Поиск по общим полям
    if search:
        search_term = f"%{search}%"
        # Пытаемся найти запись в MoreId по old_id
        more_id_record = db.session.query(MoreId).filter(MoreId.old_id.ilike(search_term)).first()

        if more_id_record:
            # Предположим, что в поле ids у вас строка с запятыми
            ids_str = more_id_record.ids.strip()
            # Разделяем строку на список идентификаторов
            ids_list = [id_part.strip() for id_part in ids_str.split(',')]
            # Фильтруем товары по item_no из списка
            query = query.filter(CatalogItem.item_no.in_(ids_list))
        else:
            # Если ничего не найдено, ищем по другим полям
            query = query.filter(
                or_(
                    CatalogItem.color.ilike(search_term),
                    CatalogItem.description.ilike(search_term),
                    CatalogItem.item_no.ilike(search_term)
                )
            )
            

    # TODO: check and potentially remove
    # Поиск по id товара
    # if search_id:
    #     query = query.filter(CatalogItem.item_no.ilike(f"%{search_id}%"))
    
    # if search_old_id:
    #     # Получаем запись из MoreId по old_id
    #     more_id_record = db.session.query(MoreId).filter(MoreId.old_id == search_old_id).first()
    #     if more_id_record:
    #         # Предполагаем, что ids — строка с разделителями
    #         ids_list = [id_str.strip() for id_str in more_id_record.ids.split(',')]
    #         # Фильтрация товаров по item_no из ids_list
    #         query = query.filter(CatalogItem.item_no.in_(ids_list))
    #     else:
    #         # Если ничего не найдено, делаем запрос, который вернет пустой результат
    #         query = query.filter(False)

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
        'id': item.id,
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
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


logging.basicConfig(level=logging.INFO)

SMTP_SERVER = 'smtp.yandex.ru'
SMTP_PORT = 587
EMAIL_ADDRESS = 'legostorage@yandex.ru'  # ваш email
EMAIL_PASSWORD = 'lego_storage_password' # ваш пароль

def send_order_email(order, order_details):
    subject = f"Новый заказ #{order.id}"
    to_email = 'legobricks2025@gmail.com'
    
    body = (
        f"Новый заказ №{order.id}\n"
        f"Дата: {order.created_at}\n"
        f"Клиент: {order.customer_name}\n"
        f"Телефон: {order.customer_telephone}\n"
        f"Почта: {order.customer_email}\n"
        f"Доставка: {'Да' if order.dostavka else 'Нет'}\n"
        f"Общая сумма: {order.total_price}\n\n"
        "Позиции заказа:\n"
    )
    
    for item in order_details:
        body += (
            f"- {item['description']} | "
            f"Количество: {item['quantity_in_order']} | "
            f"Цена за единицу: {item['unit_price']} | "
            f"Итого: {item['total_price']}\n"
        )
    
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        logging.info("Email успешно отправлен")
    except Exception as e:
        logging.error(f"Ошибка при отправке email: {e}")



@app.route('/cart', methods=['POST'])
def submit_cart():
    data = request.get_json()
    
    items_data = data.get('items')
    customer_name = data.get('customer_name')
    customer_telephone = data.get('customer_telephone')
    customer_email = data.get('customer_email')
    dostavka = data.get('dostavka', False)

    # Проверка обязательных полей
    if not items_data or not customer_name or not customer_telephone:
        return jsonify({'error': 'Missing required fields'}), 400

    order_details_for_email = []
    total_price = 0

    # Предварительно ищем все CatalogItem один раз для повышения эффективности
    catalog_items_cache = {}
    
    for item in items_data:
        catalog_item_number = item['item_no']
        quantity_requested = item.get('quantity', 1)
        
        if catalog_item_number not in catalog_items_cache:
            catalog_item = CatalogItem.query.filter_by(item_no=catalog_item_number).first()
            if not catalog_item:
                return jsonify({'error': f'Item with item number {catalog_item_number} не найден'}), 404
            catalog_items_cache[catalog_item_number] = catalog_item
        else:
            catalog_item = catalog_items_cache[catalog_item_number]
        
        if catalog_item.quantity < quantity_requested:
            return jsonify({
                'error': f'Недостаточно товара "{catalog_item.description}". '
                         f'Доступно: {catalog_item.quantity}, запрошено: {quantity_requested}'
            }), 400
        
        price_per_unit = getattr(catalog_item, 'price', 0)
        total_price += price_per_unit * quantity_requested
        
        # Собираем данные для email
        order_details_for_email.append({
            'description': catalog_item.description,
            'quantity_in_order': quantity_requested,
            'unit_price': price_per_unit,
            'total_price': price_per_unit * quantity_requested
        })

    # Проверка минимальной суммы заказа (если есть)
    settings = Settings.query.filter_by(settings_name='min').first()
    min_order_value = settings.settings_value if settings else None
    
    if min_order_value is not None and total_price < min_order_value:
        return jsonify({
            'error': f'Минимальная сумма заказа составляет {min_order_value}. '
                     f'Ваш заказ на сумму {total_price} не может быть принят.'
        }), 400
        
        
    from fpdf import FPDF   
    # Создаем PDF с данными заказа
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Заголовок
    pdf.cell(0, 10, txt="Детали заказа", ln=True, align='C')
    pdf.ln(10)

    # Информация о клиенте
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(0, 10, txt="Информация о клиенте:", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, txt=f"Имя: {customer_name}", ln=True)
    pdf.cell(0, 8, txt=f"Телефон: {customer_telephone}", ln=True)
    if customer_email:
        pdf.cell(0, 8, txt=f"Email: {customer_email}", ln=True)
    pdf.ln(5)

    # Информация о доставке
    if dostavka:
        pdf.set_font("Arial", style='B', size=12)
        pdf.cell(0, 10, txt="Доставка: Да", ln=True)
    else:
        pdf.set_font("Arial", style='B', size=12)
        pdf.cell(0, 10, txt="Доставка: Нет", ln=True)
    pdf.ln(10)

    # Таблица с товаром
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(80, 10, txt="Описание", border=1)
    pdf.cell(30, 10, txt="Кол-во", border=1)
    pdf.cell(30, 10, txt="Цена", border=1)
    pdf.cell(30, 10, txt="Всего", border=1)
    pdf.ln()

    pdf.set_font("Arial", size=12)
    for item in order_details_for_email:
        pdf.cell(80, 10, txt=item['description'], border=1)
        pdf.cell(30, 10, txt=str(item['quantity_in_order']), border=1)
        pdf.cell(30, 10, txt=f"{item['unit_price']:.2f}", border=1)
        pdf.cell(30, 10, txt=f"{item['total_price']:.2f}", border=1)
        pdf.ln()

    # Общая сумма
    pdf.ln(5)
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(0, 10, txt=f"Общая сумма: {total_price:.2f}", ln=True, align='R')

    # Сохраняем PDF в память
    pdf_buffer = io.BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)

         
    

    from datetime import datetime

    try:
        # Используем транзакцию для атомарности операции
        with db.session.begin():
            order = Order(
                customer_name=customer_name,
                customer_telephone=customer_telephone,
                customer_email=customer_email,
                dostavka=dostavka,
                total_price=total_price,
                created_at=datetime.utcnow()
            )
            db.session.add(order)
            db.session.flush()  # чтобы получить id заказа
            
            for item in items_data:
                catalog_item_number = item['item_no']
                quantity_requested = item.get('quantity', 1)
                catalog_item = catalog_items_cache[catalog_item_number]
                
                order_item = OrderItem(
                    order=order,
                    catalog_item=catalog_item,
                    quantity=quantity_requested
                )
                db.session.add(order_item)
                
                # Обновляем количество на складе
                catalog_item.quantity -= quantity_requested
            
            db.session.commit()

        # Отправляем письмо после успешной транзакции
        send_order_email(order, order_details_for_email)

        return jsonify({'message': 'Order created', 'order_id': order.id}), send_file(pdf_buffer, as_attachment=True, download_name='order_details.pdf', mimetype='application/pdf')    
    
    except Exception as e:
        db.session.rollback()
        logging.exception("Ошибка при создании заказа")
        return jsonify({'error': 'Ошибка при обработке заказа'}), 500




# --- 2.1   Обработка скачивания wanted list ---

import xml.etree.ElementTree as ET
import tempfile

def determine_item_type(item_no):
    catalog_item = CatalogItem.query.filter_by(item_no=item_no).first()   
    category_id = catalog_item.get('category_id')
    category_name = Category.query.filter_by(id=category_id).first()
    
    category_name_lower = category_name.lower()
    
    if category_name_lower.startswith('instructions'):
        return 'I'
    elif category_name_lower.startswith('parts'):
        return 'P'
    elif category_name_lower.startswith('minifigures'):
        return 'M'
    else:
        return 'P' 

def create_inventory_xml(items_data, color_dict):
    INVENTORY = ET.Element('INVENTORY')
    
    for item in items_data:
        item_elem = ET.SubElement(INVENTORY, 'ITEM')
        
        item_no = item.get('item_no')
        
        item_type = determine_item_type(item_no)
        
        color_name = item.get('color_name')
        color_code_value = ''
        
        if color_name and color_name in color_dict:
            color_code_value = color_dict[color_name]
        
        ET.SubElement(item_elem, 'ITEMTYPE').text = item_type
        ET.SubElement(item_elem, 'ITEMID').text = str(item_no)
        
        if color_code_value:
            ET.SubElement(item_elem, 'COLOR').text = str(color_code_value)
        
        ET.SubElement(item_elem, 'MAXPRICE').text = '-1.0000'
        ET.SubElement(item_elem, 'MINQTY').text = str(item.get('quantity', 1))
        ET.SubElement(item_elem, 'CONDITION').text = 'X'
        ET.SubElement(item_elem, 'NOTIFY').text = 'N'
    
    return INVENTORY

def save_xml_to_file(xml_element):
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as tmp_file:
        tree = ET.ElementTree(xml_element)
        tree.write(tmp_file.name, encoding='utf-8', xml_declaration=True)
        return tmp_file.name



@app.route('/save_as_wanted_list', methods=['POST'])
def handle_save_as_wanted_list():
    data = request.get_json()
    
    items_data = data.get('items')
    
    if not items_data:
       return jsonify({'error': 'Нет данных товаров'}), 400
    
    try:
       xml_element= create_inventory_xml(items_data=items_data, color_dict=color_dict)
       xml_filename= save_xml_to_file(xml_element)
       return jsonify({'status': 'success', 'file_path': xml_filename}), 200
    
    except Exception as e:
       logging.exception("Ошибка при создании XML")
       return jsonify({'error':'Ошибка при создании файла'}),500
   
   




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
                'url': getattr(catalog_item, 'url', None),
                'color': getattr(catalog_item, 'color', None),
                'quantity_in_order': item.quantity,
                'unit_price': price_per_unit,
                'total_price': item.quantity*price_per_unit,
                'remarks': getattr(item, 'remarks', None)
            })
        
        orders_list.append({
            'id': order.id,
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

@app.route('/settings', methods=['GET'])
def get_settings():
    settings = Settings.query.all()
    result = {setting.settings_name: setting.settings_value for setting in settings}
    return jsonify(result)

@app.route('/admin/settings', methods=['POST'])
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





# --- 6.1 Структура категорий Part---
def get_parts_subcategories(categories):
    parts_subcategories = {}
    for category in categories:
        parts = [part.strip() for part in category.name.split('/')]
        if parts[0] == "Parts":
            current_level = parts[1:]  # все после "Parts"
            current_dict = parts_subcategories
            for part in current_level:
                if part not in current_dict:
                    current_dict[part] = {}
                current_dict = current_dict[part]
    return parts_subcategories

@app.get("/category-parts")
def get_category_structure_parts():
    categories = Category.query.all()
    subcategories_list = get_parts_subcategories(categories)
    return jsonify(subcategories_list)




# --- 7. Просмотр одного заказа из админки ---
def get_order_items_list(order):
    items_list = []
    for item in order.order_items:
        catalog_item = item.catalog_item
        price_per_unit = catalog_item.price if catalog_item else 0
        quantity_in_order = item.quantity

        items_list.append({
            'item_no': catalog_item.item_no,
            'url': catalog_item.url,
            'color': catalog_item.color,
            'description': catalog_item.description,
            'quantity_in_order': quantity_in_order,
            'unit_price': price_per_unit,
            'total_price': quantity_in_order * price_per_unit,
            "remarks": catalog_item.remarks,
            "quantity": catalog_item.quantity
        })
    return items_list


@app.route('/admin/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    order = Order.query.filter(Order.id == order_id).first()
    if not order:
        abort(404, description="Order not found")
    
    items_list = get_order_items_list(order)

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




# --- 7.1 Скачать один заказ как wanted list ---
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders


def send_email_with_attachment(subject, body_text, filename):
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = 'legobricks2025@gmail.com'

    msg.attach(MIMEText(body_text, 'plain', 'utf-8'))

    with open(filename, 'rb') as f:
        part = MIMEBase('application', 'xml')
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{filename.split("/")[-1]}"')
        msg.attach(part)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        print("Письмо успешно отправлено")
    except Exception as e:
        print(f"Ошибка при отправке: {e}")



@app.route('/save_<int:order_id>', methods=['POST', 'GET'])
def save_order_as_wanted_list(order_id):
    order = Order.query.filter(Order.id == order_id).first()
    if not order:
        abort(404, description="Order not found")
    
    items_list = get_order_items_list(order)

    xml_element = create_inventory_xml(items_data=items_list, color_dict=color_dict)
    
    xml_filename = save_xml_to_file(xml_element)
    
    body_text = f'Здравствуйте,\n\nПрикреплен XML-файл с информацией о товарах заказа.\n\nНомер заказа: {order_id}'
    
    send_email_with_attachment('Заказ - информация о товарах', body_text, xml_filename)
    
    return {'status': 'success'}, 200






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


import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


service = Service('/usr/local/bin/chromedriver')  # путь к chromedriver
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # запуск в headless-режиме
driver = webdriver.Chrome(service=service, options=options)




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
        
        


color_dict = {
    'Black': '11',
    'Blue': '7',
    'Bright Green': '36',
    'Bright Light Blue': '105',
    'Bright Light Orange': '110',
    'Bright Light Yellow': '103',
    'Bright Pink': '104',
    'Brown': '8',
    'Chrome Silver': '22',
    'Coral': '220',
    'Dark Azure': '153',
    'Dark Blue': '63',
    'Dark Bluish Gray': '85',
    'Dark Brown': '120',
    'Dark Gray': '10',
    'Dark Green': '80',
    'Dark Orange': '68',
    'Dark Pink': '47',
    'Dark Purple': '89',
    'Dark Red': '59',
    'Dark Tan': '69',
    'Dark Turquoise': '39',
    'Flat Dark Gold': '81',
    'Flat Silver': '95',
    'Glitter Trans-Clear': '101',
    'Glitter Trans-Light Blue': '162',
    'Glitter Trans-Purple': '102',
    'Green': '6',
    'Lavender': '154',
    'Light Aqua': '152',
    'Light Bluish Gray': '86',
    'Light Brown': '91',
    'Light Gray': '9',
    'Light Nougat': '90',
    'Lime': '34',
    'Maersk Blue': '72',
    'Magenta': '71',
    'Medium Azure': '156',
    'Medium Blue': '42',
    'Medium Lavender': '157',
    'Medium Nougat': '150',
    'Medium Orange': '31',
    'Metallic Copper': '250',
    'Metallic Gold': '65',
    'Metallic Silver': '67',
    'Nougat': '28',
    'Olive Green': '155',
    'Orange': '4',
    'Pearl Dark Gray': '77',
    'Pearl Gold': '115',
    'Pearl Light Gray': '66',
    'Red': '5',
    'Reddish Brown': '88',
    'Reddish Copper': '249',
    'Sand Blue': '55',
    'Sand Green': '48',
    'Satin Trans-Light Blue': '229',
    'Tan': '2',
    'Trans-Black': '251',
    'Trans-Bright Green': '108',
    'Trans-Brown': '13',
    'Trans-Clear': '12',
    'Trans-Dark Blue': '14',
    'Trans-Dark Pink': '50',
    'Trans-Green': '20',
    'Trans-Light Blue': '15',
    'Trans-Light Purple': '114',
    'Trans-Medium Blue': '74',
    'Trans-Neon Green': '16',
    'Trans-Neon Orange': '18',
    'Trans-Orange': '98',
    'Trans-Purple': '51',
    'Trans-Red': '17',
    'Trans-Yellow': '19',
    'Very Light Bluish Gray': '99',
    'White': '1',
    'Yellow': '3',
    'Yellowish Green': '158',
    'n/a': '0'
}


results = []
results_dict = {}
    

def get_old_id_for_item(driver, item_no):
    url = f'https://www.bricklink.com/v2/catalog/catalogitem.page?P={item_no}'
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        # Ждем появления блока с нужным id
        div_main = wait.until(EC.presence_of_element_located((By.ID, 'id_divBlock_Main')))
        # Находим первый <span> внутри этого блока
        span_element = div_main.find_element(By.TAG_NAME, 'span')
        text = span_element.text.strip()

        marker = 'Alternate Item No:'
        if marker in text:
            parts = text.split(marker, 1)
            if len(parts) > 1:
                return parts[1].strip()
        return None
    except Exception as e:
        print(f"Ошибка при обработке item_no={item_no}: {e}")
        return None

# Настройка драйвера
from selenium.webdriver.chrome.options import Options

options = Options()
options.binary_location = "/usr/bin/chromium"
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

service = Service("/usr/bin/chromedriver")

driver = webdriver.Chrome(service=service, options=options)

results_id = {}
single_id_results = []





# !!!!!!!!!!!!!!!!!!  Всё по фоновой работе загрузки бьазы данных
# pip install fastapi uvicorn sqlalchemy psycopg2-binary????
import uuid
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from typing import Dict



task_statuses: Dict[str, Dict[str, str]] = {}

def create_task_status(task_id: str, status: str, message: str):
    task_statuses[task_id] = {
        "status": status,
        "message": message
    }

def get_task_status_by_id(task_id: str):
    return task_statuses.get(task_id)

def update_task_status(task_id: str, status: str, message: str):
    if task_id in task_statuses:
        task_statuses[task_id]["status"] = status
        task_statuses[task_id]["message"] = message



def process_db_add(file_name: str, task_id: str):
    # Обновляем статус на "processing"
    task_status = get_task_status_by_id(task_id)
    if task_status:
        update_task_status(task_id, status='processing', message='Загрузка началась')
    else:
        return

    try:
        print("Код начал загружаться")
        
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
                image_url = ''
                color_name = row['Color']  
                color_number = color_dict.get(color_name, '0')  
                if color_name == 'n/a':
                    image_url = f"https://img.bricklink.com/ItemImage/IN/{color_number}/{item_no}.png"
                else:        
                    image_url = f"https://img.bricklink.com/ItemImage/PN/{color_number}/{item_no}.png"
                    
                results.append({'Item No': item_no, 'Color': color_name, 'Image URL': image_url})
                results_dict[item_no] = image_url

                # Создаем новую запись в таблице Images
                new_image = Images(
                    ids=item_no,
                    color=color_name,
                    image_url=image_url
                )
                db.session.add(new_image)
                
                
                if item_no in results_id:
                    continue

                old_id_result = get_old_id_for_item(driver, item_no)
                if old_id_result:
                    # Разделяем по запятой и очищаем пробелы
                    ids = [id_str.strip() for id_str in old_id_result.split(',')]
                    results_id[item_no] = ids
                else:
                    results_id[item_no] = []

                for item_no, ids_list in results_id.items():
                    if ids_list:
                        for id_value in ids_list:
                            single_id_results.append({'Item No': item_no, 'Old ID': id_value})
                    else:
                        # Если ID отсутствует, добавим запись с None или 'Нет данных'
                        single_id_results.append({'Item No': item_no, 'Old ID': None})

                # Теперь можно вывести или сохранить этот список
                for entry in single_id_results:
                    new_record = MoreId(
                        ids=entry['Item No'], 
                        old_id=entry['Old ID']
                        )
                    db.session.add(new_record)

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
        finally:
            driver.quit()
            
            
        import time
        time.sleep(5)  # имитация длительной операции

        # После успешной обработки обновляем статус
        update_task_status(task_id, status='completed', message='Все действия выполнены')
    except Exception as e:
        # В случае ошибки обновляем статус на "error"
        update_task_status(task_id, status='error', message=str(e))




# @app.route("/db_add", methods=["GET", "POST"])
# async def db_add_endpoint(request: Request, background_tasks: BackgroundTasks):
#     data = await request.json()
#     file_name = data.get('file_name')
    
#     if not file_name:
#         return JSONResponse(status_code=400, content={"error": "file_name обязательное поле"})

#     # Создаем уникальный ID задачи
#     task_id = str(uuid.uuid4())

#     # Создаем запись о задаче со статусом "pending"
#     create_task_status(task_id=task_id, status='pending', message='Задача создана')

#     # Запускаем фоновую задачу с передачей task_id
#     background_tasks.add_task(process_db_add, file_name, task_id)

#     return {"task_id": task_id}
import threading

@app.route("/db_add", methods=["GET", "POST"])
def db_add():
    file_name = request.args.get('file_name')
    if not file_name:
        return jsonify({"error": "file_name обязательное поле"}), 400

    raw_csv = request.data.decode('utf-8')
    if not raw_csv:
        return jsonify({"error": "Нет данных"}), 400
    
    # Создаем уникальный ID задачи
    task_id = str(uuid.uuid4())

    # Создаем запись о задаче со статусом "pending"
    create_task_status(task_id=task_id, status='pending', message='Задача создана')

    # Запускаем фоновую задачу в отдельном потоке
    thread = threading.Thread(target=process_db_add, args=(file_name, task_id))
    thread.start()

    return jsonify({"task_id": task_id})



@app.get('/task_status/{task_id}')
def get_task_status_endpoint(task_id: str):
    status_record = get_task_status_by_id(task_id)
    if not status_record:
        return JSONResponse(status_code=404, content={"error": "Задача не найдена"})
    
    return {
        "task_id": task_id,
        "status": status_record.status,
        "message": status_record.message
    }





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
            url=data.get('url') if data else results_dict.get(item_no, ''),
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


@app.route('/wanted_list', methods=['POST'])
# --- 13. Загрузка wanted_list ---
def parse_xml_from_gcs():
    data = request.get_json()
    file_name = data.get('file_name')
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(file_name)

        # Проверка существования файла
        if not blob.exists():
            print(f"Файл {file_name} не найден в бакете {BUCKET_NAME}.")
            return {'error_message': f"blob {file_name} was not found in the bucket"}

        # Получение содержимого файла как байтов
        xml_bytes = blob.download_as_bytes()

        # Декодируем байты в строку
        xml_content = xml_bytes.decode('utf-8')

        # Парсим XML из строки
        soup = BeautifulSoup(xml_content, 'xml')
        items = soup.find_all('ITEM')

        found_items = []
        not_found_items = []
        for item in items:
            item_id_text = item.find('ITEMID').text
            # item_type = item.find('ITEMTYPE').text
            # color = item.find('COLOR').text
            # max_price_text = item.find('MAXPRICE').text
            # min_qty_text = item.find('MINQTY').text
            # condition = item.find('CONDITION').text
            # notify = item.find('NOTIFY').text

            # Преобразуем числовые значения
            # try:
            #     max_price = float(max_price_text)
            #     min_qty = int(min_qty_text)
            # except (ValueError, AttributeError):
            #     print(f"Некорректные данные для ITEMID={item_id_text}")
            #     continue

            existing_item = CatalogItem.query.filter_by(item_no=item_id_text).first()

            if existing_item:
                found_items.append({
                    'id': existing_item.id,
                    'item_no': existing_item.item_no,
                    'url': existing_item.url,
                    'color': existing_item.color,
                    'description': existing_item.description,
                    'price': existing_item.price,
                    'quantity': existing_item.quantity,
                    'category_name': existing_item.category.name if existing_item.category else None,
                    'remarks': existing_item.remarks
                })
                print(f"Найден товар: {existing_item}")            
            else:
                not_found_items.append(item_id_text)
                print(f"Товар с ITEMID={item_id_text} не найден в базе.")

        return {
            'found_items': found_items,
            'not_found_items': not_found_items
        }
    except Exception as e:
        print(f"Ошибка при получении файла из GCS: {e}")
        return {
            'error_message': f'{e}'
        }, 400

# вызов функции с именем файла в GCS
# parse_xml_from_gcs('путь/к/вашему.xml')?????







# --- Запуск приложения ---
if __name__ == '__main__':
    app.run(debug=True)