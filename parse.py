import csv
import os

from flask import Flask, request, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import check_password_hash, generate_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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

def get_image_src_with_selenium(lot_id):
    url = f'https://www.bricklink.com/v2/catalog/catalogitem.page?P={lot_id}'
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # запуск без графического интерфейса
    
    # Используем ChromeDriverManager для автоматической установки драйвера
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        img = wait.until(EC.presence_of_element_located((By.ID, '_idImageMain')))
        src = img.get_attribute('src')
        return src
    finally:
        driver.quit()

def str_to_bool(s):
    return s.strip().lower() in ['true', '1', 'yes']

@app.route('/db_add', methods=['POST'])
def db_add():
    with open('database_copy.csv', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)

        # Обработка заголовков: убираем пробелы и делаем их нижним регистром
        rows = []
        for row in reader:
            row = {k.strip(): v for k, v in row.items()}
            rows.append(row)

        db.session.query(CatalogItem).delete()
        db.session.commit()
        
        
        lot_id = row['Lot ID'].strip()
        image_url = get_image_src_with_selenium(lot_id)

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





# lot_id = '57562pb01'
# image_url = get_image_src_with_selenium(lot_id)
# print(f"Главное изображение для {lot_id}: {image_url}")