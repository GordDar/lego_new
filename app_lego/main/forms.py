from flask import flash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, EqualTo, Length, Email, ValidationError


class LoginForm(FlaskForm):
    email = StringField('Емейл', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')
    
class OrderForm(FlaskForm):
    details = StringField('Детали', validators=[DataRequired()])
    fio = StringField('ФИО', validators=[DataRequired()])
    phone = StringField('Телефон', validators=[DataRequired()])
    send = BooleanField('Нужна ли отправка')
    submit = SubmitField('Оформить заказ')