# Базовый образ с Python
FROM python:3.11-slim

# Установка рабочих директорий
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта
COPY . .

# Указываем переменные окружения
ENV FLASK_APP=run.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=production

# Открываем порт
EXPOSE 8080

# Команда запуска
CMD ["python", "-m", "flask", "run", "--port=8080"]
