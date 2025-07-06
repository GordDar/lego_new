# import requests
# from bs4 import BeautifulSoup

# def get_main_image_url(lot_id):
#     url = f'https://www.bricklink.com/v2/catalog/catalogitem.page?P={lot_id}'
#     headers = {
#         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
#                       'AppleWebKit/537.36 (KHTML, like Gecko) '
#                       'Chrome/115.0.0.0 Safari/537.36'
#     }
#     response = requests.get(url, headers=headers)
#     response.raise_for_status()
#     soup = BeautifulSoup(response.text, 'html.parser')
    
#     # Находим td с классом 'pciMainImageHolder'
#     td = soup.find('td', class_='pciMainImageHolder')
#     if td:
#         print('td найден')
#         print(td)
#         # Ищем внутри td span
#         span = td.find('span')
#         if span:
#             print('span найден')
#             print(span)
#             # Внутри span ищем img
#             img = soup.find('img', id='_idImageMain')
#             if not img:
#                 img = soup.find('img', class_='pciImageMain')
#             if img:
#                 print('img найден')
#                 print(img)
#                 src = img.get('src')
#                 if src:
#                     print('src найден')
#                     if src.startswith('//'):
#                         src = 'https:' + src
#                     return src
#                 else:
#                     print("Атрибут src у изображения не найден.")
#             else:
#                 print("Изображение внутри span не найдено.")
#         else:
#             print("Span внутри td не найден.")
#     else:
#         print("td с классом 'pciMainImageHolder' не найден.")
#     return None




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

# Используйте функцию с нужным lot_id
lot_id = '57562pb01'
image_url = get_image_src_with_selenium(lot_id)
print(f"Главное изображение для {lot_id}: {image_url}")