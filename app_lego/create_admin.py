from app_lego import db, app, AdminUser
from flask_bcrypt import generate_password_hash
with app.app_context():
    hashed_password = generate_password_hash('Test1234').decode('utf-8')
    user = AdminUser(username='admin', password_hash=hashed_password)
    db.session.add(user)
    db.session.commit()
