from app_lego import db
from datetime import datetime
from app_lego.models import CatalogItem, Category
from bs4 import BeautifulSoup


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
parse_xml_and_query('./proba.xml')