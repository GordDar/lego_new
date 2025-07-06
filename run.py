from app_lego import app
from app_lego import db
from app_lego import create_initial_settings


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_initial_settings()
        app.run(debug=True)