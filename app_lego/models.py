from app_lego import db, login_manager

# Таблица связи "многие ко многим" с дополнительными полями
class OrderItem(db.Model):
    __tablename__ = 'order_items'
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), primary_key=True)
    catalog_item_id = db.Column(db.Integer, db.ForeignKey('catalog_items.id'), primary_key=True)
    quantity = db.Column(db.Integer, nullable=False)

    order = db.relationship('Order', back_populates='order_items')
    catalog_item = db.relationship('CatalogItem', back_populates='order_items')


# Модель "Заказы"
class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100))
    customer_telephone = db.Column(db.String(50))
    dostavka = db.Column(db.Boolean, default=False)
    total_price = db.Column(db.Float)

    # Связь с OrderItem
    order_items = db.relationship(
        'OrderItem',
        back_populates='order',
        cascade='all, delete-orphan'
    )


class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    settings_name = db.Column(db.String(30))
    settings_value = db.Column(db.Float)


@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))


# Модель "Админ пользователи"
class AdminUser(db.Model):
    __tablename__ = 'admin_user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password_hash = db.Column(db.String(128))


class Category(db.Model):
    __tablename__ = 'category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    # Связь с товарами
    catalog_items = db.relationship('CatalogItem', backref='category', lazy=True)


class CatalogItem(db.Model):
    __tablename__ = 'catalog_items'
    __searchable__ = ['color', 'description']

    id = db.Column(db.Integer, primary_key=True)

    lot_id = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(50), nullable=False)

    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)

    condition = db.Column(db.String(50))
    sub_condition = db.Column(db.String(50))

    description = db.Column(db.Text, nullable=False)
    remarks = db.Column(db.Text)

    price = db.Column(db.Float)
    quantity = db.Column(db.Integer)

    bulk = db.Column(db.Boolean)
    sale = db.Column(db.Boolean)

    url = db.Column(db.String(255))
    item_no = db.Column(db.String(50))

    tier_qty_1 = db.Column(db.Integer)
    tier_price_1 = db.Column(db.Float)

    tier_qty_2 = db.Column(db.Integer)
    tier_price_2 = db.Column(db.Float)

    tier_qty_3 = db.Column(db.Integer)
    tier_price_3 = db.Column(db.Float)

    reserved_for = db.Column(db.String(100))
    stockroom = db.Column(db.String(100))

    retain = db.Column(db.Boolean)

    super_lot_id = db.Column(db.String(50))
    super_lot_qty = db.Column(db.Integer)

    weight = db.Column(db.Float)

    extended_description = db.Column(db.Text)

    date_added = db.Column(db.DateTime)
    date_last_sold = db.Column(db.DateTime)

    currency = db.Column(db.String(10))

    # Связь с OrderItem
    order_items = db.relationship(
        'OrderItem',
        back_populates='catalog_item',
        cascade='all, delete-orphan'
    )
