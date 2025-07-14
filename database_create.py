# --- 9. Создание базы данных ---


import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager



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



# csv_input = 'database.csv'  # Ваш входной файл
# csv_output = 'results_links.csv'  # Выходной файл с ссылками

results = []
results_dict = {}

# with open(csv_input, newline='', encoding='utf-8') as infile:
#     reader = csv.DictReader(infile)
#     for row in reader:
#         item_no = row['Item No']
#         color_name = row['Color']  # Предполагаем, что есть колонка 'Color'
#         color_number = color_dict.get(color_name, '0')  # по умолчанию 0, если нет в словаре
#         if color_name == 'n/a':
#             image_url = f"https://img.bricklink.com/ItemImage/IN/{color_number}/{item_no}.png"
#         else:
       
       
       
#             image_url = f"https://img.bricklink.com/ItemImage/PN/{color_number}/{item_no}.png"
#             print(f"Найдено изображение для {item_no} цвета {color_name}: {image_url}")
            
#         results.append({'Item No': item_no, 'Color': color_name, 'Image URL': image_url})
#         results_dict[item_no] = image_url

#         # Создаем новую запись в таблице Images
#         new_image = Images(
#             ids=item_no,
#             image_url=image_url
#         )
#         db.session.add(new_image)

# try:
#     db.session.commit()
# except Exception as e:
#     db.session.rollback()
#     print(f"Ошибка при сохранении данных: {e}")

# # Записываем результат
# with open(csv_output, 'w', newline='', encoding='utf-8') as outfile:
#     writer = csv.DictWriter(outfile, fieldnames=['Item No', 'Color', 'Image URL'])
#     writer.writeheader()
#     writer.writerows(results)
    

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
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # запуск без интерфейса
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

results_id = {}



# try:
#     with open('database_copy.csv', newline='', encoding='utf-8') as csvfile:
#         reader = csv.DictReader(csvfile)
#         for idx, row in enumerate(reader, start=1):
#             item_no = row['Item No']
#             if item_no in results_id:
#                 print(f"{item_no} уже обработан. пропускаем.")
#                 continue

#             print(f"Обрабатываем {idx}: item_no={item_no}")
#             old_id_result = get_old_id_for_item(driver, item_no)
#             if old_id_result:
#                 # Разделяем по запятой и очищаем пробелы
#                 ids = [id_str.strip() for id_str in old_id_result.split(',')]
#                 results_id[item_no] = ids
#             else:
#                 results_id[item_no] = []

#             print(f"Item No: {item_no} -> Old IDs: {results_id[item_no]}")
# finally:
#     driver.quit()

# Создаем новый словарь, где каждый ID — отдельная запись
single_id_results = []

# for item_no, ids_list in results.items():
#     if ids_list:
#         for id_value in ids_list:
#             single_id_results.append({'Item No': item_no, 'Old ID': id_value})
#     else:
#         # Если ID отсутствует, добавим запись с None или 'Нет данных'
#         single_id_results.append({'Item No': item_no, 'Old ID': None})

# # Теперь можно вывести или сохранить этот список
# for entry in single_id_results:
#     new_record = MoreId(
#         ids=entry['Item No'], 
#         old_id=entry['Old ID']
#         )
#     db.session.add(new_record)


 

# # Можно сохранить в CSV файл
# with open('single_id_results.csv', 'w', newline='', encoding='utf-8') as f:
#     writer = csv.DictWriter(f, fieldnames=['Item No', 'Old ID'])
#     writer.writeheader()
#     for row in single_id_results:
#         writer.writerow(row)



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
    return 'Success', 200


