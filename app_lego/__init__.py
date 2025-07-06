import csv
import os

from flask import Flask, request, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import check_password_hash, generate_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# import requests
from bs4 import BeautifulSoup

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
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)
login_manager = LoginManager(app)


from app_lego.models import Order, CatalogItem, Category, AdminUser, Settings, OrderItem


# --- 1. Каталог (GET /catalog) ---
@app.route('/catalog', methods=['GET'])
def get_catalog():
    search = request.args.get('search', '', type=str)
    search_id = request.args.get('search_id', '', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = CatalogItem.query

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                CatalogItem.color.ilike(search_term),
                CatalogItem.description.ilike(search_term)
            )
        )
        
    if search_id:
        search_term_id = f"%{search_id}%"
        query = query.filter(
            db.or_(
                CatalogItem.lot_id.ilike(search_term_id),
            )
        )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    items = [{
        'lot_id': item.lot_id,
        'url': item.url,
        'color': item.color,
        'description': item.description,
        'price': item.price,
        'quantity': item.quantity,
    } for item in pagination.items]

    return jsonify({
        'items': items,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    })

# --- 2. Отправка корзины (POST /cart) ---
@app.route('/cart', methods=['POST'])
def submit_cart():
    data = request.json
    # Ожидается структура:
    # {
    #   "items": [{"id": 1, "quantity": 2}, ...],
    #   "customer_name": "...",
    #   "customer_telephone": "...",
    #   "dostavka": true/false,
    #   "total_price": ...
    # }
    
    items_data = data.get('items')
    customer_name = data.get('customer_name')
    customer_telephone = data.get('customer_telephone')
    dostavka = data.get('dostavka', False)
    total_price = data.get('total_price')
    

    if not items_data or not customer_name or not customer_telephone or total_price is None:
        return jsonify({'error': 'Missing required fields'}), 400
    
    # проверки минимальной суммы заказа
    settings = Settings.query.first()
    if settings and settings.min_order_amount is not None:
        if total_price < settings.min_order_amount:
            return jsonify({
                'error': f'Минимальная сумма заказа составляет {settings.min_order_amount}. '
                         f'Ваш заказ на сумму {total_price} не может быть принят.'
            }), 400


    order = Order(
        customer_name=customer_name,
        customer_telephone=customer_telephone,
        dostavka=dostavka,
        total_price=total_price
    )

    for item in items_data:
        catalog_item_id = item['id']
        quantity_requested = item.get('quantity', 1)
        catalog_item = CatalogItem.query.get(catalog_item_id)
        
        if not catalog_item:
            return jsonify({'error': f'Item with id {catalog_item_id} not found'}), 404
        if catalog_item.quantity < quantity_requested:
            return jsonify({
                'error': f'Недостаточно товара "{catalog_item.description}". '
                         f'Доступно: {catalog_item.quantity}, запрошено: {quantity_requested}'
            }), 400
        
        order_item = OrderItem(
            catalog_item=catalog_item,
            quantity=quantity_requested
        )
        order.order_items.append(order_item)

        # Обновляем количество на складе после подтверждения заказа
        catalog_item.quantity -= quantity_requested
    
    db.session.add(order)
    db.session.commit()

    return jsonify({'message': 'Order created', 'order_id': order.id})

# --- 3. Логин для админки (POST /admin/login) ---
@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = AdminUser.query.filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, password):
        login_user(user)
        return jsonify({'message': 'Logged in'})
    
    return jsonify({'error': 'Invalid credentials'}), 401

# --- 4. Просмотр заказов в админке (GET /admin/orders) ---
@app.route('/admin/orders', methods=['GET'])
@login_required
def get_orders():
    status_filter = request.args.get('status')  # например, 'new', 'completed'
    date_from = request.args.get('date_from')   # формат: 'YYYY-MM-DD'
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
        total_price_order = 0  # Инициализация суммы заказа
        
        for item in order.items:
            catalog_item = item.catalog_item
            price_per_unit = getattr(catalog_item, 'price', 0) 
            
            # Расчет стоимости позиции
            item_total = price_per_unit * item.quantity
            total_price_order += item_total
            
            items_list.append({
                'id': item.id,
                'lot_id': getattr(catalog_item, 'lot_id', None),
                'url': item.url,
                'color': getattr(catalog_item, 'color', None),
                'description': catalog_item.description,
                'quantity_in_order': item.quantity,
                'unit_price': price_per_unit,
                'total_price': item_total,
                'remarks': getattr(item, 'remarks', None)
            })
        
        
        order_total_price = total_price_order
        
        remarks_value = getattr(order, 'remarks', None)
        
        orders_list.append({
            'id': order.id,
            'customer_name': order.customer_name,
            'customer_telephone': order.customer_telephone,
            'dostavka': order.dostavka,
            'total_price': order_total_price,
            'items': items_list,
            'remarks': remarks_value
        })
    
    
    
    
    pagination = orders_query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'orders_list': orders_list,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    })


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
# @login_required
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
    total_price_order = 0

    for item in order.items:
        catalog_item = item.catalog_item
        price_per_unit = catalog_item.price if catalog_item else 0
        quantity = item.quantity
        item_total = price_per_unit * quantity
        total_price_order += item_total

        items_list.append({
            'id': item.catalog_item.id,
            'lot_id': catalog_item.lot_id,
            'url': catalog_item.url,
            'color': catalog_item.color,
            'description': catalog_item.description,
            'quantity_in_order': quantity,
            'unit_price': price_per_unit,
            'total_price': item_total,
            "remarks": catalog_item.remarks
        })

    response_data = {
        "id": order.id,
        "customer_name": order.customer_name,
        "customer_telephone": order.customer_telephone,
        "dostavka": order.dostavka,
        "total_price": total_price_order,
        "items": items_list,
    }

    return jsonify(response_data)




# --- 8. Просмотр данных по 1 детали ---
@app.route('/catalog_item/<int:item_id>', methods=['GET'])
def get_catalog_item(item_id):
    item = CatalogItem.query.get(item_id)
    if item:
        return jsonify({
            'lot_id': item.lot_id,
            'color': item.color,
            'category': item.category.name,
            'condition': item.condition,
            'description': item.description,
            'price': item.price,
            'quantity': item.quantity,
            'url': item.url,
            'currency': item.currency
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
        
        
def get_image_url(lot_id):
    return f"https://img.bricklink.com/ItemImage/PN/6/{lot_id}.png"

  
  
  # ТАКОЕ??      
# def get_image_url(lot_id):
#     # URL страницы детали на BrickLink
#     page_url = f"https://www.bricklink.com/v2/catalog/catalogitem.page?P={lot_id}"
#     response = requests.get(page_url)
#     if response.status_code != 200:
#         return None
#     soup = BeautifulSoup(response.text, 'html.parser')
#     img_tag = soup.find('img', {'id': 'itemImage'})
#     if img_tag:
#         return img_tag['src']
#     return None



@app.route('/db_add', methods=['POST'])
def db_add():
    with open('database.csv', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)

        # Обработка заголовков: убираем пробелы и делаем их нижним регистром
        rows = []
        for row in reader:
            row = {k.strip(): v for k, v in row.items()}
            rows.append(row)

        db.session.query(CatalogItem).delete()
        db.session.commit()
        
        
        lot_id = row['Lot ID'].strip()
        image_url = get_image_url(lot_id)

        for row in rows:
            # Создаем объект CatalogItem
            category, created = get_or_create(db.session, Category, name=row['Category'].strip())
            item = CatalogItem(
                lot_id=lot_id,
                color=row['Color'].strip(),
                category_id=category.id,  # предполагается, что category - это id (число)
                condition=row.get('Condition', '').strip(),
                sub_condition=row.get('Sub-Condition', '').strip(),
                description=row.get('Description', '').strip(),
                remarks=row.get('Remarks', '').strip(),
                price=float(row['Price'].replace('$', '').strip()) if row['Price'] else None,
                quantity=int(row['Quantity']) if row['Quantity'] else None,
                bulk=str_to_bool(row.get('Bulk', 'False')),
                sale=str_to_bool(row.get('Sale', 'False')),
                url= image_url,
                item_no=row.get('Item No', '').strip(),
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
                super_lot_qty=int(row['Super Lot Qty']) if row['Super Lot Qty'] else None,
                weight=float(row['Weight']) if row['Weight'] else None,
                extended_description=row.get('Extended Description', '').strip(),

                date_added=datetime.strptime(row['Date Added'], '%m/%d/%Y') if row.get('Date Added') else None,
                date_last_sold=datetime.strptime(row['Date Last Sold'], '%Y-%m-%d') if row.get(
                    'Date Last Sold') else None,

                currency=row.get('Currency', '').strip()
            )
            db.session.add(item)
    db.session.commit()
    return '', 200



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
            "lot_id": item.lot_id,
            "color": item.color,
            "description": item.description,
            "price": item.price,
            "quantity": item.quantity,
            "url": item.url,
        }
    
    return jsonify([serialize_item(item) for item in items])


# --- 11. Создание или изменение деталей ---
@app.route('/update_or_create', methods=['POST'])
def update_or_create():
    data = request.get_json()
    if not data:
        abort(400, description="Invalid JSON data")
    
    lot_id = data.get('lot_id')
    if not lot_id:
        abort(400, description="Missing 'lot_id' in request data")
    
    item = CatalogItem.query.filter_by(lot_id=lot_id).first()
    
    if item:
        # Обновляем только те поля, которые есть в данных и не пустые
        for field in ['color', 'description', 'price', 'quantity', 'url', 'category', 'remarks']:
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
            lot_id=lot_id,
            color=data.get('color'),
            description=data.get('description'),
            price=data.get('price'),
            quantity=data.get('quantity'),
            url=data.get('url'),
            category_id=category_obj.id if category_obj else None,
            remarks = data.get('remarks')
        )
        db.session.add(new_item)
    
    db.session.commit()
    return jsonify({"status": "success"}), 200




# --- 12. Загрузка wanted_list ---
def parse_xml_and_query(xml_file_path):
    with open(xml_file_path, 'r', encoding='utf-8') as file:
        xml_content = file.read()

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
            item_id = int(item_id_text)
            max_price = float(max_price_text)
            min_qty = int(min_qty_text)
        except (ValueError, AttributeError):
            print(f"Некорректные данные для ITEMID={item_id_text}")
            continue

        # Выполняем поиск в базе по ITEMID
        existing_item = CatalogItem.query.filter_by(id=item_id).first()

        if existing_item:
            print(f"Найден товар: {existing_item}")            
        else:
            print(f"Товар с ITEMID={item_id} не найден в базе.")

# вызов функции с путем к вашему XML файлу
# parse_xml_and_query('./proba.xml')







# --- Запуск приложения ---
if __name__ == '__main__':
    app.run(debug=True)