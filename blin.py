import csv

# Ваш словарь цветов
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

unique_colors = set()


csv_input = 'database.csv'  # Ваш входной файл
csv_output = 'results_links.csv'  # Выходной файл с ссылками

results = []

with open(csv_input, newline='', encoding='utf-8') as infile:
    reader = csv.DictReader(infile)
    for row in reader:
        item_no = row['Item No']
        color_name = row['Color']  # Предполагаем, что есть колонка 'Color'
        color_number = color_dict.get(color_name, '0')  # по умолчанию 0, если нет в словаре
        if color_name == 'n/a':
            image_url = f"https://img.bricklink.com/ItemImage/IN/{color_number}/{item_no}.png"
        else:
            image_url = f"https://img.bricklink.com/ItemImage/PN/{color_number}/{item_no}.png"
            print(f"Найдено изображение для {item_no} цвета {color_name}: {image_url}")
        results.append({'Item No': item_no, 'Color': color_name, 'Image URL': image_url})

# Записываем результат
with open(csv_output, 'w', newline='', encoding='utf-8') as outfile:
    writer = csv.DictWriter(outfile, fieldnames=['Item No', 'Color', 'Image URL'])
    writer.writeheader()
    writer.writerows(results)
    
    

print("Готово! Ссылки сформированы.")



