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
import threading

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


from app_lego.models import Order, CatalogItem, Category, AdminUser, Settings, OrderItem, Images, MoreId, TaskStatus


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
    per_page = request.args.get('per_page', 30, type=int)
    
    query = CatalogItem.query.join(Category, CatalogItem.category_id == Category.id)
        # .filter(Category.name.ilike("%Parts%"))

    if search_category and not search:
        category_ids = None
        category_obj = None
        if search_category == 'Parts':
            category_objs = Category.query.filter(
                Category.name.ilike(f"{search_category}%")
            ).all()
            category_ids = [c.id for c in category_objs]
            if category_ids:
                query = query.filter(CatalogItem.category_id.in_(category_ids))
        else:
            category_obj = Category.query.filter(
                Category.name == search_category
            ).first()
            if category_obj:
                query = query.filter(CatalogItem.category_id == category_obj.id)
        if not category_ids and not category_obj:
            return jsonify({
                'items': [],
                'total': 0,
                'pages': 0,
                'current_page': page
            })

    query = query.filter(CatalogItem.quantity > 0)

    if search:
        search_term = f"%{search}%"
        more_id_record = db.session.query(MoreId).filter(MoreId.old_id.ilike(search_term)).first()

        if more_id_record:
            ids_str = more_id_record.ids.strip()
            ids_list = [id_part.strip() for id_part in ids_str.split(',')]
            query = query.filter(CatalogItem.item_no.in_(ids_list))
        else:
            query = query.filter(
                or_(
                    CatalogItem.color.ilike(search_term),
                    CatalogItem.description.ilike(search_term),
                    CatalogItem.item_no.ilike(search_term)
                )
            )

    # Изменённая сортировка:
    query = query.order_by(CatalogItem.item_no.asc(), CatalogItem.color.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    items = [{
            'id': item.id,
            'item_no': item.item_no,
            'url': item.url or 'https://storage.googleapis.com/lego-bricks-app-frontend/default.jpg',
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
    
    
# import requests    
# DEFAULT_IMAGE_PATH = "https://storage.googleapis.com/lego-bricks-app-frontend/default.jpg"

# @app.route('/catalog', methods=['GET'])
# def get_catalog():
#     search = request.args.get('search', '', type=str)
#     search_category = request.args.get('category', '', type=str)
#     page = request.args.get('page', 1, type=int)
#     per_page = request.args.get('per_page', 30, type=int)
    
#     query = CatalogItem.query.join(Category, CatalogItem.category_id == Category.id)

#     if search_category:
#         if search_category == 'Parts':
#             category_obj = Category.query.filter(Category.name.ilike(f"{search_category}%")).first()
#         else:
#             category_obj = Category.query.filter(Category.name == search_category).first()
#         if category_obj:
#             category_id = category_obj.id
#             query = query.filter(CatalogItem.category_id == category_id)
#         else:
#             return jsonify({
#                 'items': [],
#                 'total': 0,
#                 'pages': 0,
#                 'current_page': page
#             })
        
#     query = query.filter(CatalogItem.quantity > 0)

#     if search:
#         search_term = f"%{search}%"
#         more_id_record = db.session.query(MoreId).filter(MoreId.old_id.ilike(search_term)).first()

#         if more_id_record:
#             ids_str = more_id_record.ids.strip()
#             ids_list = [id_part.strip() for id_part in ids_str.split(',')]
#             query = query.filter(CatalogItem.item_no.in_(ids_list))
#         else:
#             query = query.filter(
#                 or_(
#                     CatalogItem.color.ilike(search_term),
#                     CatalogItem.description.ilike(search_term),
#                     CatalogItem.item_no.ilike(search_term)
#                 )
#             )

#     query = query.order_by(CatalogItem.id)
#     pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
#     items = []
#     for item in pagination.items:
#         image_url = item.url
#         if image_url:
#             try:
#                 response = requests.head(image_url, timeout=5)
#                 if response.status_code != 200:
#                     image_url = DEFAULT_IMAGE_PATH
#             except requests.RequestException:
#                 image_url = DEFAULT_IMAGE_PATH
#         else:
#             image_url = DEFAULT_IMAGE_PATH

#         items.append({
#             'id': item.id,
#             'item_no': item.item_no,
#             'url': image_url,
#             'color': item.color,
#             'description': item.description,
#             'price': item.price,
#             'quantity': item.quantity,
#             'category_name': item.category.name if item.category else None,
#             'remarks': item.remarks
#         })

#     return jsonify({
#         'items': items,
#         'total': pagination.total,
#         'pages': pagination.pages,
#         'current_page': pagination.page
#     })






# --- 2.1   Обработка скачивания pdf ---
import io
from flask import request, jsonify, send_file
from weasyprint import HTML, CSS


def generate_order_pdf(order, order_details):
    """
    Формирует PDF по данным заказа и возвращает его в виде байтов.
    """
    total_price_value = sum(item['total_price'] for item in order_details)

    html_content = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: DejaVu Sans, Arial, sans-serif;
                margin: 40px;
            }}
            h1 {{
                text-align: center;
                font-size: 24px;
                margin-bottom: 20px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }}
            th, td {{
                border: 1px solid #000;
                padding: 8px;
                text-align: left;
                font-size: 14px;
            }}
            th {{
                background-color: #f0f0f0;
            }}
            img {{
                width: 90px;
            }}
            .total {{
                text-align: right;
                font-weight: bold;
                font-size: 16px;
                margin-top: 10px;
            }}
        </style>
    </head>
    <body>
        <h1>Детали заказа</h1>
        <table>
            <thead>
                <tr>
                    <th>Изображение</th>
                    <th>Описание</th>
                    <th>Кол-во</th>
                    <th>Цена</th>
                    <th>Всего</th>
                </tr>
            </thead>
            <tbody>
    """

    for item in order_details:
        html_content += f"""
                <tr>
                    <td><img src="{item['url']}" alt="image" style="max-width:100px; height:auto;"></td>
                    <td>{item['description']}</td>
                    <td>{item['quantity_in_order']}</td>
                    <td>{item['unit_price']:.2f}</td>
                    <td>{item['total_price']:.2f}</td>
                </tr>
        """

    html_content += f"""
            </tbody>
        </table>
        <div class="total">Общая сумма: {total_price_value:.2f}</div>
    </body>
    </html>
    """

    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes



@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    data = request.get_json()
    items_data = data.get('items', [])

    catalog_items_cache = {}
    order_details_for_pdf = []

    for item in items_data:
        item_id = item['id']
        quantity_requested = item.get('quantity', 1)

        if item_id not in catalog_items_cache:
            catalog_item = CatalogItem.query.get(item_id)
            if not catalog_item:
                return jsonify({'error': f'Item with id {item_id} не найден'}), 404
            catalog_items_cache[item_id] = catalog_item
        else:
            catalog_item = catalog_items_cache[item_id]

        price_per_unit = getattr(catalog_item, 'price', 0)
        total_price = price_per_unit * quantity_requested

        order_details_for_pdf.append({
            'description': getattr(catalog_item, 'description', ''),
            'url': getattr(catalog_item, 'url', ''),
            'quantity_in_order': quantity_requested,
            'unit_price': price_per_unit,
            'total_price': total_price
        })

    pdf_bytes = generate_order_pdf(order=None, order_details=order_details_for_pdf)

    buffer = io.BytesIO(pdf_bytes)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name="order_details.pdf",
        mimetype='application/pdf'
    )


# --- 2.2 Отправка почты ---
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication


logging.basicConfig(level=logging.INFO)

SMTP_SERVER = 'smtp.yandex.ru'
SMTP_PORT = 587
EMAIL_ADDRESS = 'legostorage@yandex.ru'  # ваш email
EMAIL_PASSWORD = 'dgdauqansfzzlkyz' # ваш пароль


def send_order_email(order, order_details, pdf_bytes):
    """
    Отправляет письмо с информацией о заказе и вложенным PDF.
    
    :param order: объект заказа с атрибутами (id, created_at, customer_name и т.д.)
    :param order_details: список dict с деталями заказа.
    :param pdf_bytes: байты PDF файла.
    """
    from flask import current_app as app

    with app.app_context():
        logging.info(f"Начинаю отправку письма по заказу #{order.id}")
        
        subject = f"Новый заказ #{order.id}"
        to_email = 'legobricks2025@gmail.com'
        # to_email = 'oldi2008@yandex.ru' # Замените на актуальный адрес
        
        created_at_formatted = order.created_at.strftime("%H:%M %d-%m-%Y") if hasattr(order, 'created_at') and order.created_at else ""

        table_rows = ""
        for item in order_details:
            description = item.get('description', '')
            url_img = item.get('url', '')
            quantity_in_order = item.get('quantity_in_order', '')
            unit_price = item.get('unit_price', 0)
            total_price_item = item.get('total_price', 0)
            id_ = item.get('id', '')
            color_ = item.get('color', '')
            remarks_ = item.get('remarks', '')

            table_rows += f"""
                <tr>
                    <td>{description}</td>
                    <td>{id_}</td>
                    <td>{color_}</td>
                    <td>{remarks_}</td>
                    <td style="text-align:center;">{quantity_in_order}</td>
                    <td style="text-align:right;">{unit_price:.2f}</td>
                    <td style="text-align:right;">{total_price_item:.2f}</td>
                </tr>
            """

        html_content_email=f"""
        <html>
        <body>
            <h2>Новый заказ №{order.id}</h2>
            <h4><a href="http://34.110.202.124/orders/{order.id}">Ссылка на заказ №{order.id}</a></h4>
            <p><strong>Дата:</strong> {created_at_formatted}</p>
            <p><strong>Клиент:</strong> {getattr(order,'customer_name','')}</p>
            <p><strong>Телефон:</strong> {getattr(order,'customer_telephone','')}</p>
            <p><strong>Почта:</strong> {getattr(order,'customer_email','')}</p>
            <p><strong>Доставка:</strong> {'Да' if getattr(order,'dostavka',False) else 'Нет'}</p>
            <p><strong>Общая сумма:</strong> {getattr(order,'total_price',0):.2f} долл.</p>

            <h3>Позиции заказа:</h3>
            <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
                <thead style="background-color:#f2f2f2;">
                    <tr style="text-align:left;">
                        <th style="text-align:left;">Описание</th>
                        <th style="text-align:center;">Id</th>
                        <th style="text-align:center;">Цвет</th>
                        <th style="text-align:center;">Заметки</th>
                        <th style="text-align:center;">Кол-во</th>
                        <th style="text-align:right;">Цена за ед.</th>
                        <th style="text-align:right;">Итог</th></tr></thead><tbody>{table_rows}
                </tbody></table></body></html>"""

        msg= MIMEMultipart('alternative')
        msg['Subject']=subject
        msg['From']=EMAIL_ADDRESS
        msg['To']=to_email

        part_html= MIMEText(html_content_email,'html','utf-8')
        msg.attach(part_html)

        if pdf_bytes:
            logging.info(f"pdf есть")
            attachment= MIMEApplication(pdf_bytes,'pdf')
            attachment.add_header('Content-Disposition','attachment', filename='order_details.pdf')
            msg.attach(attachment)

        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
               logging.info("Подключение к SMTP серверу")
               server.starttls()
               logging.info("Запуск TLS")
               server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
               logging.info("Логин выполнен")
               server.send_message(msg)
               logging.info("Письмо отправлено")
        except Exception as e:
            logging.error(f"Ошибка при отправке email: {e}")



# --- 2. Отправка корзины (POST /cart) ---
@app.route('/cart', methods=['POST'])
def submit_cart():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    items_data = data.get('items')
    customer_name = data.get('customer_name')
    customer_telephone = data.get('customer_telephone')
    customer_email = data.get('customer_email')
    dostavka = data.get('dostavka', False)

    # Проверка обязательных полей
    if not items_data or not customer_name or not customer_telephone:
        return jsonify({'error': 'Missing required fields'}), 400

    # Проверка типа items_data
    if not isinstance(items_data, list):
        return jsonify({'error': 'Items should be a list'}), 400

    order_details_for_email = []
    total_price = 0
    catalog_items_cache = {}

    # Предварительно собираем все уникальные id товаров
    item_ids = {item['id'] for item in items_data if 'id' in item}
    
    # Получаем все товары за один запрос
    catalog_items = CatalogItem.query.filter(CatalogItem.id.in_(item_ids)).all()
    for catalog_item in catalog_items:
        catalog_items_cache[catalog_item.id] = catalog_item

    # Обработка каждого элемента заказа
    for item in items_data:
        item_id = item.get('id')
        if not item_id:
            return jsonify({'error': 'Item id is missing'}), 400

        quantity_requested = item.get('quantity', 1)
        if not isinstance(quantity_requested, int) or quantity_requested <= 0:
            return jsonify({'error': 'Invalid quantity'}), 400

        catalog_item = catalog_items_cache.get(item_id)
        if not catalog_item:
            return jsonify({'error': f'Item with id {item_id} not found'}), 404

        if catalog_item.quantity < quantity_requested:
            return jsonify({
                'error': f'Not allowed amount "{catalog_item.description}". '
                         f'Max count: {catalog_item.quantity}, Requested: {quantity_requested}'
            }), 400

        price_per_unit = getattr(catalog_item, 'price', 0)
        total_price += price_per_unit * quantity_requested

        order_details_for_email.append({
            'description': catalog_item.description,
            'url': catalog_item.url,
            'remarks': catalog_item.remarks,
            'color': catalog_item.color,
            'id': catalog_item.lot_id,
            'quantity_in_order': quantity_requested,
            'unit_price': price_per_unit,
            'total_price': price_per_unit * quantity_requested
        })

    # Проверка минимальной суммы заказа
    settings = Settings.query.filter_by(settings_name='min').first()
    min_order_value = float(settings.settings_value) if settings else None
    
    if min_order_value is not None and total_price < min_order_value:
        return jsonify({
            'error': f'Minimum order value {min_order_value}. Your cart value {total_price}'
        }), 400

    from datetime import datetime
    
    try:
        order = Order(
            customer_name=customer_name,
            customer_telephone=customer_telephone,
            customer_email=customer_email,
            dostavka=dostavka,
            total_price=total_price,
            created_at=datetime.utcnow()
        )
        db.session.add(order)
        db.session.flush()  # чтобы получить order.id

        for item in items_data:
            item_id = item['id']
            quantity_requested = item.get('quantity', 1)
            catalog_item = catalog_items_cache[item_id]

            order_item = OrderItem(
                order=order,
                catalog_item=catalog_item,
                quantity=quantity_requested
            )
            db.session.add(order_item)

            logging.info(f"Обновление товара {catalog_item.id}: {catalog_item.quantity} -> {catalog_item.quantity - quantity_requested}")
            catalog_item.quantity -= quantity_requested

        db.session.commit()  # фиксируем изменения до отправки письма

        # Генерация PDF (синхронно, чтобы получить pdf_bytes)
        pdf_bytes = generate_order_pdf(order=order, order_details=order_details_for_email)

        # Функция-обертка для отправки письма в отдельном потоке
        def send_email_async(order, order_details, pdf):
            with app.app_context():
                try:
                    send_order_email(order, order_details, pdf_bytes=pdf)
                except Exception:
                    logging.exception("Ошибка при отправке письма")

        # Запускаем отправку письма в отдельном потоке
        threading.Thread(target=send_email_async, args=(order, order_details_for_email, pdf_bytes)).start()

        return jsonify({'message': 'Order created', 'order_id': order.id})

    except Exception as e:
        logging.exception("Ошибка при создании заказа")
        db.session.rollback()
        return jsonify({'error': 'Ошибка при обработке заказа'}), 500

    # try:
    #     # Начинаем транзакцию
    #     order = Order(
    #         customer_name=customer_name,
    #         customer_telephone=customer_telephone,
    #         customer_email=customer_email,
    #         dostavka=dostavka,
    #         total_price=total_price,
    #         created_at=datetime.utcnow()
    #     )
    #     db.session.add(order)
    #     db.session.flush()  # чтобы получить order.id

    #     for item in items_data:
    #         item_id = item['id']
    #         quantity_requested = item.get('quantity', 1)
    #         catalog_item = catalog_items_cache[item_id]

    #         # Создаем заказанный товар
    #         order_item = OrderItem(
    #             order=order,
    #             catalog_item=catalog_item,
    #             quantity=quantity_requested
    #         )
    #         db.session.add(order_item)

    #         # Уменьшаем количество товара после успешного добавления заказа
    #         logging.info(f"Обновление товара {catalog_item.id}: {catalog_item.quantity} -> {catalog_item.quantity - quantity_requested}")
    #         catalog_item.quantity -= quantity_requested

        
    #     # Генерация PDF и отправка письма могут быть выполнены асинхронно
    #     pdf_bytes = generate_order_pdf(order=order, order_details=order_details_for_email)

    #     # Отправка письма (можно вынести в очередь задач)
    #     send_order_email(order, order_details_for_email, pdf_bytes=pdf_bytes)
    #     db.session.commit()  # фиксируем все изменения только если всё прошло успешно
    #     return jsonify({'message': 'Order created', 'order_id': order.id})

    # except Exception as e:
    #     logging.exception("Ошибка при создании заказа")
    #     db.session.rollback()  # отменяем все изменения, сделанные в транзакции
    #     return jsonify({'error': 'Ошибка при обработке заказа'}), 500







# @app.route('/download_pdf', methods=['POST'])
# def download_pdf():
#     data = request.get_json()
#     items_data = data.get('items')

#     catalog_items_cache = {}
#     order_details_for_email = []
#     total_price = 0

#     for item in items_data:
#         item_id = item['id']
#         quantity_requested = item.get('quantity', 1)

#         if item_id not in catalog_items_cache:
#             catalog_item = CatalogItem.query.get(item_id)
#             if not catalog_item:
#                 return jsonify({'error': f'Item with id {item_id} не найден'}), 404
#             catalog_items_cache[item_id] = catalog_item
#         else:
#             catalog_item = catalog_items_cache[item_id]

#         price_per_unit = getattr(catalog_item, 'price', 0)
#         total_price += price_per_unit * quantity_requested

#         order_details_for_email.append({
#             'description': catalog_item.description,
#             'image': catalog_item.url,
#             'quantity_in_order': quantity_requested,
#             'unit_price': price_per_unit,
#             'total_price': price_per_unit * quantity_requested
#         })

#     total_price_value = sum(item['total_price'] for item in order_details_for_email)

#     # Создаем HTML-шаблон
#     html_content = f"""
#     <html>
#     <head>
#         <meta charset="UTF-8">
#         <style>
#             body {{
#                 font-family: DejaVu Sans, Arial, sans-serif;
#                 margin: 40px;
#             }}
#             h1 {{
#                 text-align: center;
#                 font-size: 24px;
#                 margin-bottom: 20px;
#             }}
#             table {{
#                 width: 100%;
#                 border-collapse: collapse;
#                 margin-bottom: 20px;
#             }}
#             th, td {{
#                 border: 1px solid #000;
#                 padding: 8px;
#                 text-align: left;
#                 font-size: 14px;
#             }}
#             th {{
#                 background-color: #f0f0f0;
#             }}
#             .total {{
#                 text-align: right;
#                 font-weight: bold;
#                 font-size: 16px;
#                 margin-top: 10px;
#             }}
#         </style>
#     </head>
#     <body>
#         <h1>Детали заказа</h1>
#         <table>
#             <thead>
#                 <tr>
#                     <th>Изображение</th>
#                     <th>Описание</th>
#                     <th>Кол-во</th>
#                     <th>Цена</th>
#                     <th>Всего</th>
#                 </tr>
#             </thead>
#             <tbody>
#     """

#     for item in order_details_for_email:
#         html_content += f"""
#                 <tr>
#                     <td><img src="{item['image']}" alt="image" /></td>
#                     <td>{item['description']}</td>
#                     <td>{item['quantity_in_order']}</td>
#                     <td>{item['unit_price']:.2f}</td>
#                     <td>{item['total_price']:.2f}</td>
#                 </tr>
#         """

#     html_content += f"""
#             </tbody>
#         </table>
#         <div class="total">Общая сумма: {total_price_value:.2f}</div>
#     </body>
#     </html>
#     """


#     pdf_bytes = HTML(string=html_content).write_pdf()

#     buffer = io.BytesIO(pdf_bytes)
    
#     return send_file(
#         buffer,
#         as_attachment=True,
#         download_name="order_details.pdf",
#         mimetype='application/pdf'
#     )



# --- 2.1   Обработка скачивания wanted list ---

import xml.etree.ElementTree as ET
import tempfile

def determine_item_type(item_no):
    if not item_no:
        return 'P'
    
    catalog_item = CatalogItem.query.filter_by(item_no=item_no).first()
    if not catalog_item:
        return 'P'
    
    category = Category.query.filter_by(id=catalog_item.category_id).first()
    if not category:
        return 'P'
    
    category_name_lower = category.name.lower()
    
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
        item_no = item.get('item_no')
        if not item_no:
            logging.warning(f"Пропущен элемент без item_no: {item}")
            continue

        item_type = determine_item_type(item_no)
        
        color_name = item.get('color')
        color_code_value = color_dict.get(color_name, '') if color_name else ''
        
        item_elem = ET.SubElement(INVENTORY, 'ITEM')
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
    xml_bytes_io = io.BytesIO()
    tree = ET.ElementTree(xml_element)
    tree.write(xml_bytes_io, encoding='utf-8', xml_declaration=True)
    xml_bytes_io.seek(0)
    return xml_bytes_io



@app.route('/save_as_wanted_list', methods=['POST'])
def handle_save_as_wanted_list():
    data = request.get_json()
    
    items_data = data.get('items')
    
    if not items_data:
       return jsonify({'error': 'Нет данных товаров'}), 400
    
    try:
       xml_element= create_inventory_xml(items_data=items_data, color_dict=color_dict)
       xml_bytes_io= save_xml_to_file(xml_element)
       return send_file(
            xml_bytes_io,
            download_name="wanted_list.xml",
            as_attachment=True,
            mimetype='application/xml'
        )
    
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
    status_filter = request.args.get('status')  
    date_from = request.args.get('created_at')   
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
            pass  
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
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
            'comment': order.comment,
            'status': order.status, 
            'created_at': (order.created_at or datetime.now()).isoformat(), 
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
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    if order.status != 'исполнен':
        return jsonify({'error': 'Only completed orders can be deleted'}), 400

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
        {'settings_name': 'byn', 'settings_value': 3},
        {'settings_name': 'rub', 'settings_value': 82},
        {'settings_name': 'min', 'settings_value': 15}
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
    if result == {}:
        create_initial_settings()
        settings = Settings.query.all()
        result = {setting.settings_name: setting.settings_value for setting in settings}
    return jsonify(result)

@app.route('/admin/settings', methods=['POST'])
@token_required
def update_settings():
    data = request.get_json()
    db.session.query(Settings).delete()
    

    for key, value in data.items():
        settings = Settings(settings_name=key, settings_value = value)
        db.session.merge(settings)
    try:
        db.session.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/admin/save_order_comment/<int:order_id>', methods=['POST'])
@token_required
def save_order_comment(order_id):
    data = request.get_json()

    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    order.comment = data.get('comment', '')
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
    # categories = Category.query.filter(Category.catalog_items.any()).all()
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

# category-parts
@app.get("/category-structure-parts")
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
        "comment": order.comment,
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



@app.route('/save_as_wanted_list/<int:order_id>', methods=['POST', 'GET'])
def save_order_as_wanted_list(order_id):
    order = Order.query.filter(Order.id == order_id).first()
    if not order:
        abort(404, description="Order not found")
    
    items_list = get_order_items_list(order)

    xml_element = create_inventory_xml(items_data=items_list, color_dict=color_dict)

    xml_bytes_io = save_xml_to_file(xml_element)

    return send_file(
        xml_bytes_io,
        download_name="wanted_list.xml",
        as_attachment=True,
        mimetype='application/xml'
    )
    
   
   

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
from selenium.webdriver.chrome.options import Options
import uuid
from typing import Dict
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session
import logging


results = []
results_dict = {}
results_id = {}
single_id_results = []    


# def get_old_id_for_item(driver, item_no):
#     url = f'https://www.bricklink.com/v2/catalog/catalogitem.page?P={item_no}'
#     try:
#         driver.get(url)
#         wait = WebDriverWait(driver, 15)
#         # Ждем появления блока с нужным id
#         div_main = wait.until(EC.presence_of_element_located((By.ID, 'id_divBlock_Main')))
#         # Находим первый <span> внутри этого блока
#         span_element = div_main.find_element(By.TAG_NAME, 'span')
#         text = span_element.text.strip()

#         marker = 'Alternate Item No:'
#         if marker in text:
#             parts = text.split(marker, 1)
#             if len(parts) > 1:
#                 return parts[1].strip()
#         return None
#     except Exception as e:
#         print(f"Ошибка при обработке item_no={item_no}: {e}")
#         return None

# Настройка драйвера
options = Options()
options.binary_location = "/usr/bin/chromium"
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

service = Service("/usr/bin/chromedriver")

driver = webdriver.Chrome(service=service, options=options)

def create_task_status(task_id: str, status: str, message: str):
    new_task_status = TaskStatus(task_id=task_id, status=status, message=message)
    db.session.add(new_task_status)
    db.session.commit()

def get_task_status_by_id(task_id: str):
    try:
        task_status = db.session.query(TaskStatus).filter_by(task_id=task_id).one()
        return {
            "task_id": task_status.task_id,
            "status": task_status.status,
            "message": task_status.message
        }
    except NoResultFound:
        return None 

def update_task_status(task_id: str, status: str, message: str):
    try:
        task_status = db.session.query(TaskStatus).filter_by(task_id=task_id).one()
        task_status.status = status
        task_status.message = message
        db.session.commit()
    except NoResultFound:
        create_task_status(task_id, status, message)
        
def update_task_message(task_id, message):
    status_record = get_task_status_by_id(task_id)
    if status_record:
        status_record.message = message
        db.session.commit()


def clear_task_statuses():
    db.session.query(TaskStatus).delete()
    db.session.commit()

def get_or_create(session: Session, model, defaults=None, commit_required=True, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False  # Уже существует
    else:
        params = dict(**kwargs)
        if defaults:
            params.update(defaults)
        instance = model(**params)
        session.add(instance)
        try:
            if commit_required:
                session.commit()
            return instance, True
        except IntegrityError:
            session.rollback()
            # Попытка повторно получить объект после отката
            instance = session.query(model).filter_by(**kwargs).first()
            return instance, False

# import requests

# DEFAULT_IMAGE_PATH = "https://storage.googleapis.com/lego-bricks-app-frontend/default.jpg"

       
# def check_and_update_image(image_ids, color_name, app):
#     with app.app_context():
#         session = db.create_scoped_session()
#         try:
#             image_obj = session.query(Images).filter(
#                 Images.ids == image_ids,
#                 Images.color == color_name
#             ).first()
#             if not image_obj:
#                 return
#
#             try:
#                 response = requests.head(image_obj.image_url, timeout=5)
#                 if response.status_code != 200:
#                     image_obj.image_url = DEFAULT_IMAGE_PATH
#             except requests.RequestException:
#                 image_obj.image_url = DEFAULT_IMAGE_PATH
#
#             session.commit()
#             logging.info(f"Исправлено check_and_update_image для id={image_ids}")
#         except Exception as e:
#             session.rollback()
#             logging.exception(f"Ошибка в check_and_update_image для id={image_ids}: {e}")
#         finally:
#             session.remove()
        

# from concurrent.futures import ThreadPoolExecutor


def process_db_add(file_name: str, task_id: str):
    with app.app_context():
        update_task_status(task_id, status="processing", message="Загрузка началась")
        try:
            # Читаем CSV из GCS
            bucket = storage_client.bucket(BUCKET_NAME)
            blob = bucket.blob(file_name)
            content = blob.download_as_text(encoding="utf-8")

            reader = list(csv.DictReader(io.StringIO(content)))
            total_rows = len(reader)
            processed = 0

            # Очистка базы
            db.session.query(OrderItem).delete()
            db.session.query(MoreId).delete()
            db.session.query(Images).delete()
            db.session.query(CatalogItem).delete()
            db.session.query(Category).delete()
            db.session.query(TaskStatus).delete()
            db.session.commit()
            
            update_task_status(
                task_id,
                status="delete_complete",
                message="Очистка базы данных завершена",
            )

            # Подготовим категории одним махом
            category_names = {row["Category"].strip() for row in reader}
            existing_categories = (
                db.session.query(Category)
                .filter(Category.name.in_(category_names))
                .all()
            )
            category_map = {c.name: c.id for c in existing_categories}

            new_categories = [
                {"name": name}
                for name in category_names
                if name not in category_map
            ]
            if new_categories:
                db.session.bulk_insert_mappings(Category, new_categories)
                db.session.commit()
                # перечитываем категории, чтобы получить id
                all_categories = (
                    db.session.query(Category)
                    .filter(Category.name.in_(category_names))
                    .all()
                )
                category_map = {c.name: c.id for c in all_categories}

            # executor = ThreadPoolExecutor(max_workers=3)

            batch_size = 1000
            images_batch = []
            catalog_batch = []

            def parse_float(value):
                try:
                    return (
                        float(value.replace("$", "").strip())
                        if value
                        else None
                    )
                except Exception:
                    return None

            def parse_int(value):
                try:
                    return int(value) if value else None
                except Exception:
                    return None

            def str_to_bool(val):
                return val and val.lower() in ("true", "1", "yes")

            for row in reader:
                row = {
                    k.strip() if k is not None else "": v
                    for k, v in row.items()
                }

                item_no = row.get("Item No", "").strip()
                color_name = row.get("Color", "").strip()
                category_name = row["Category"].strip()
                category_id = category_map.get(category_name)
                color_number = color_dict.get(color_name, "0")

                if "Instruction" in category_name:
                    image_url = f"http://34.160.149.248/ItemImage/IN/{color_number}/{item_no}.png"
                if "Minifigure" in category_name:
                    image_url = f"http://34.160.149.248/ItemImage/MN/{color_number}/{item_no}.png"
                if "Gear" in category_name:
                    image_url = f"http://34.160.149.248/ItemImage/GN/{color_number}/{item_no}.png"
                if "Sets" in category_name:
                    image_url = f"http://34.160.149.248/ItemImage/SN/{color_number}/{item_no}.png"
                else:
                    image_url = f"http://34.160.149.248/ItemImage/PN/{color_number}/{item_no}.png"

                images_batch.append(
                    {
                        "ids": item_no,
                        "color": color_name,
                        "image_url": image_url,
                    }
                )

                # Асинхронная проверка картинки
                # executor.submit(check_and_update_image, item_no, color_name, app)

                catalog_batch.append(
                    {
                        "lot_id": row["Lot ID"].strip(),
                        "color": color_name,
                        "category_id": category_id,
                        "condition": row.get("Condition", "").strip(),
                        "sub_condition": row.get("Sub-Condition", "").strip(),
                        "description": row.get("Description", "").strip(),
                        "remarks": row.get("Remarks", "").strip(),
                        "price": parse_float(row.get("Price")),
                        "quantity": parse_int(row.get("Quantity")),
                        "bulk": str_to_bool(row.get("Bulk", "False")),
                        "sale": str_to_bool(row.get("Sale", "False")),
                        "url": image_url,
                        "item_no": item_no,
                        "tier_qty_1": parse_int(row["Tier Qty 1"]),
                        "tier_price_1": parse_float(row["Tier Price 1"]),
                        "tier_qty_2": parse_int(row["Tier Qty 2"]),
                        "tier_price_2": parse_float(row["Tier Price 2"]),
                        "tier_qty_3": parse_int(row["Tier Qty 3"]),
                        "tier_price_3": parse_float(row["Tier Price 3"]),
                        "reserved_for": row.get("Reserved For", "").strip(),
                        "stockroom": row.get("Stockroom", "").strip(),
                        "retain": str_to_bool(row.get("Retain", "False")),
                        "super_lot_id": row.get("Super Lot ID", "").strip(),
                        "super_lot_qty": parse_int(row.get("Super Lot Qty")),
                        "weight": parse_float(row.get("Weight")),
                        "extended_description": row.get(
                            "Extended Description", ""
                        ).strip(),
                        "date_added": datetime.strptime(
                            row["Date Added"], "%m/%d/%Y"
                        )
                        if row.get("Date Added")
                        else None,
                        "date_last_sold": datetime.strptime(
                            row["Date Last Sold"], "%Y-%m-%d"
                        )
                        if row.get("Date Last Sold")
                        else None,
                        "currency": row.get("Currency", "").strip(),
                    }
                )

                processed += 1
                if processed % batch_size == 0 or processed == total_rows:
                    if images_batch:
                        db.session.bulk_insert_mappings(Images, images_batch)
                        images_batch.clear()

                    if catalog_batch:
                        db.session.bulk_insert_mappings(
                            CatalogItem, catalog_batch
                        )
                        catalog_batch.clear()

                    db.session.commit()
                    update_task_status(
                        task_id,
                        status="processing",
                        message=f"Загружено {processed} из {total_rows}",
                    )

            update_task_status(
                task_id, status="completed", message="Все действия выполнены"
            )

        except Exception as e:
            logging.exception("Ошибка при обработке файла")
            db.session.rollback()
            update_task_status(task_id, status="error", message=str(e))


@app.route("/db_add", methods=["POST"])
def db_add():
    data = request.get_json()
    if not data or 'file_name' not in data:
        return jsonify({"error": "Параметр 'file_name' обязателен"}), 400
    
    file_name = data['file_name']

    task_id = str(uuid.uuid4())
    create_task_status(task_id=task_id, status='pending', message='Задача создана')
    
    thread = threading.Thread(target=process_db_add, args=(file_name, task_id))
    thread.start()

    return jsonify({"task_id": task_id})


@app.route('/task_status/<task_id>')
def get_task_status_endpoint(task_id):
    status_record = get_task_status_by_id(task_id)
    if not status_record:
        return jsonify({"error": "Задача не найдена"}), 404
    
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
        for field in ['lot_id', 'color', 'description', 'price', 'quantity', 'url', 'category', 'condition', 'remarks']:
            value = data.get(field)
            if value is not None:
                if isinstance(value, str) and value.strip() == '':
                    continue
                if field == 'category':
                    category_name = value
                    category, _ = get_or_create(db.session, Category, name=category_name)
                    setattr(item, 'category_id', category.id)
                else:
                    setattr(item, field, value)
        
    else:
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
    nfkd_form = unicodedata.normalize('NFKD', filename)
    ascii_filename = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
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

        url = blob.generate_signed_url(
            version='v4',
            expiration=3600, 
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

        if not blob.exists():
            print(f"Файл {file_name} не найден в бакете {BUCKET_NAME}.")
            return {'error_message': f"blob {file_name} was not found in the bucket"}

        xml_bytes = blob.download_as_bytes()
        xml_content = xml_bytes.decode('utf-8')
        soup = BeautifulSoup(xml_content, 'xml')
        items = soup.find_all('ITEM')

        found_items = []
        not_found_items = []
        for item in items:
            item_id_elem = item.find('ITEMID')
            color_elem = item.find('COLOR')
            item_id_text = item_id_elem.text if item_id_elem else None
            color_value = color_elem.text if color_elem else None

            if not item_id_text:
                not_found_items.append(None)
                print("ITEMID отсутствует, элемент пропущен")
                continue

            color_key = None
            for key, value in color_dict.items():
                if value == color_value:
                    color_key = key
                    break

            query = CatalogItem.query.filter_by(item_no=item_id_text)
            if color_key:
                query = query.filter_by(color=color_key)

            existing_item = query.first()

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


# --- 14. Выгрузка таблицы TaskStatus ---
@app.route('/task_statuses', methods=['GET'])
def get_task_statuses():
    statuses = TaskStatus.query.all()
    result = []
    for status in statuses:
        result.append({
            'id': status.id,
            'task_id': status.task_id,
            'status': status.status,
            'message': status.message
        })
    return jsonify(result)





# --- Запуск приложения ---
if __name__ == '__main__':
    app.run(debug=True)