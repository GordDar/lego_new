from flask import render_template, redirect, url_for, request, flash, Request, Blueprint, jsonify, session
from flask_login import current_user, login_user, logout_user, login_required
from flask_bcrypt import check_password_hash, generate_password_hash
from app_lego.models import AdminUser
from app_lego.main.forms import LoginForm
from app_lego import db
from datetime import datetime
from app_lego.models import CatalogItem, Category
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings


main = Blueprint('main', __name__)


@main.route('/')
def index():
    search = request.args.get('search')
    page = request.args.get('page', 1)
    if page:
        page = int(page)
    else:
        page = 1

    if search:
        parts_query = CatalogItem.query.filter(
            CatalogItem.description.contains(search) | CatalogItem.color.contains(search)
        )
    else:
        parts_query = CatalogItem.query.order_by(CatalogItem.lot_id)

    pages = parts_query.paginate(page=page, per_page=30)

    return render_template('catalog.html', title='Главная', pages=pages)


@main.route('/condition')
def condition():
    return render_template('condition.html', title = 'Условия покупки')
        


@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            flash(f'Вы вошли в аккаунт пользователя {user.username}', 'info')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.account'))
        else:
            flash('Войти не удалось. Пожалуйста, проверьте электронную почту или пароль.', 'danger')
    return render_template('login.html', form=form, title='Авторизация', legend='Войти')


@main.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    return render_template('account.html', title='Аккаунт', current_user=current_user)


@main.route('/logout')
def logout():
    current_user.last_seen = datetime.now()
    db.session.commit()
    logout_user()
    return redirect(url_for('main.index'))

@main.route('/details')
def details():
    return render_template('details.html', title = 'Каталог')

@main.route('/zakaz')
def zakaz():
    search = request.args.get('search')
    page = request.args.get('page')
    if page and page.isdigit():
        page = int(page)
    else:
        page = 1
    if search:
        parts = CatalogItem.query.filter(CatalogItem.description.contains(search) | CatalogItem.color.contains(search))
    else:
        parts = CatalogItem.query.order_by(CatalogItem.lot_id)
    pages = parts.paginate(page = page, per_page = 30)
    return render_template('zakaz.html', title = 'Ваша корзина', pages = pages)

@main.route('/catalog', methods=['GET'])
def catalog():
    search = request.args.get('search')
    page = request.args.get('page')
    if page and page.isdigit():
        page = int(page)
    else:
        page = 1
    if search:
        parts = CatalogItem.query.filter(CatalogItem.description.contains(search) | CatalogItem.color.contains(search))
    else:
        parts = CatalogItem.query.order_by(CatalogItem.lot_id)
    pages = parts.paginate(page = page, per_page = 30)
    return render_template('catalog.html', title='Каталог', pages = pages)


    
    
@main.route('/poisk')
def poisk():
    search = request.args.get('search')
    if search:
        parts = CatalogItem.query.filter(CatalogItem.description.contains(search) | CatalogItem.color.contains(search)).all()
    else:
        parts = CatalogItem.query.all()
    return render_template('catalog.html', data = parts)


@main.route('/poisk_id')
def poisk_id():
    search_id = request.args.get('search_id')
    if search_id:
        parts = CatalogItem.query.filter(CatalogItem.lot_id.contains(search_id)).first()
    else:
        parts = CatalogItem.query.all()
    return render_template('detail_po_id.html', data = parts)


@main.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    data = request.get_json()
    product_id = data.get('id')
    product_id_str = str(product_id)
    print(f"Adding product ID: {product_id}")  # отладка

    product = CatalogItem.query.get(product_id)
    if not product:
        return jsonify({'message': 'Товар не найден'}), 404

    cart = session.get('cart', {})
    if product_id in cart:
        cart[product_id_str]['quantity'] += 1
    else:
        cart[product_id_str] = {
            'name': product.description,
            'price': str(product.price),
            'quantity': 1,
        }
    session['cart'] = cart
    print(f"Current cart: {session['cart']}")  # отладка
    return jsonify({'message': 'Товар добавлен в корзину'})


@main.route('/zakaz')
def cart():
    items = []
    cart = session.get('cart', {})
    for product_id_str, item in cart.items():
        items.append({
            'name': item['name'],
            'price': float(item['price']),
            'quantity': item['quantity'],
            'total': float(item['price']) * item['quantity']
    })
    return render_template('zakaz.html', items=items, total_price=sum(i['total'] for i in items))


@main.route('/clear_cart')
def clear_cart():
    session.pop('cart', None)
    return redirect('/zakaz')


@main.route('/category/<int:category_id>')
def show_category(category_id):
    category = Category.query.get_or_404(category_id)
    products = CatalogItem.query.filter_by(category_id=category.id).all()
    return render_template('products.html', products=products, category=category)


@main.route('/parse')
def parse_xml_and_query():
    # Используйте сырую строку для пути
    xml_file_path = r'D:\lego_store\proba.xml'
    items_list = []
    noitems_list = []

    with open(xml_file_path, 'r', encoding='utf-8') as file:
        xml_content = file.read()
        
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

    soup = BeautifulSoup(xml_content, 'lxml-xml')
    items = soup.find_all('ITEM')

    for item in items:
        def get_text(tag_name):
            tag = item.find(tag_name)
            return tag.text if tag else None

        item_id_text = get_text('ITEMID')
        item_type = get_text('ITEMTYPE')
        color = get_text('COLOR')
        max_price_text = get_text('MAXPRICE')
        min_qty_text = get_text('MINQTY')
        condition = get_text('CONDITION')
        notify = get_text('NOTIFY')

        try:
            item_id = int(item_id_text)
            max_price = float(max_price_text)
            min_qty = int(min_qty_text)
        except (ValueError, AttributeError):
            # Можно добавить лог или сообщение
            continue  # пропускаем некорректные данные

        # Проверка в базе
        existing_item = CatalogItem.query.filter_by(lot_id=item_id).first()
        
        db_condition = existing_item.condition if existing_item else None
        db_color = existing_item.color if existing_item else None
        db_description = existing_item.description if existing_item else None
        db_price = existing_item.price if existing_item else None
        db_quantity = existing_item.quantity if existing_item else None
        db_url = existing_item.url if existing_item else None
        db_currency = existing_item.currency if existing_item else None
        
        item_dict = {
            'id': str(item_id),
            'color': db_color,
            'condition': db_condition,
            'description': db_description,
            'price': db_price,
            'quantity': db_quantity,
            'url': db_url,
            'currency': db_currency,
        }

        
        if existing_item:
            items_list.append(item_dict)
        else:
            noitems_list.append(item_id)
        
        

    # Возвращаем JSON с данными
    return jsonify({
    'found_items': items_list,
    'not_found_items': noitems_list
})







# @main.route('/wanted_list')
# def parse_xml_and_query(xml_file_path):
#     with open(xml_file_path, 'r', encoding='utf-8') as file:
#         xml_content = file.read()

#     soup = BeautifulSoup(xml_content, 'xml')
#     items = soup.find_all('ITEM')

#     for item in items:
#         item_id_text = item.find('ITEMID').text
#         item_type = item.find('ITEMTYPE').text
#         color = item.find('COLOR').text
#         max_price_text = item.find('MAXPRICE').text
#         min_qty_text = item.find('MINQTY').text
#         condition = item.find('CONDITION').text
#         notify = item.find('NOTIFY').text

#         # Преобразуем числовые значения
#         try:
#             item_id = int(item_id_text)
#             max_price = float(max_price_text)
#             min_qty = int(min_qty_text)
#         except (ValueError, AttributeError):
#             print(f"Некорректные данные для ITEMID={item_id_text}")
#             continue

#         # Выполняем поиск в базе по ITEMID
#         existing_item = CatalogItem.query.filter_by(id=item_id).first()

#         if existing_item:
#             print(f"Найден товар: {existing_item}")            
#         else:
#             print(f"Товар с ITEMID={item_id} не найден в базе.")

# # вызов функции с путем к вашему XML файлу
# parse_xml_and_query('path/to/your/file.xml')






            
            
    
# @app.route('/.')
# def home():
    # categories = Category.query.all()
    # parts = CatalogItem.query.all()
    # return render_template('index.html', categories=categories, parts=parts)

# @app.route('/product/<int:part_id>')
# def product_detail(part_id):
#     part = CatalogItem.query.get_or_404(part_id)
#     return render_template('product.html', part=part)

# @app.route('/add_to_cart/<int:part_id>')
# def add_to_cart(part_id):
#     cart = session.get('cart', {})
#     cart[str(part_id)] = cart.get(str(part_id), 0) + 1
#     session['cart'] = cart
#     return redirect(url_for('index'))

# @app.route('/cart')
# def view_cart():
#     cart = session.get('cart', {})
#     parts_in_cart = []
#     total_price = 0

#     for part_id_str, quantity in cart.items():
#         part = CatalogItem.query.get(int(part_id_str))
#         if part:
#             item_total = part.price * quantity
#             total_price += item_total
#             parts_in_cart.append({'part': part, 'quantity': quantity, 'total': item_total})

#     return render_template('cart.html', cart=parts_in_cart, total_price=total_price)

# @app.route('/clear_cart')
# def clear_cart():
#     session.pop('cart', None)
#     return redirect(url_for('view_cart'))