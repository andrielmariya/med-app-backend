from flask import Flask
from flask_cors import CORS
from models import db, User
from routes import register_routes
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'mysql+pymysql://root:root@127.0.0.1:3306/med_app')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret')

db.init_app(app)
register_routes(app)


def setup_database():
    with app.app_context():
        try:
            db.create_all()
            if not User.query.filter_by(username='root').first():
                root_user = User(username='root', is_superuser=True)
                root_user.set_password('root')
                db.session.add(root_user)
                db.session.commit()
                print("Superuser 'root' created successfully.")
            else:
                print("Database tables and 'root' user exist.")
        except Exception as e:
            print("Failed to initialize database:", e)


if __name__ == '__main__':
    setup_database()
    app.run(debug=True, port=5000)
