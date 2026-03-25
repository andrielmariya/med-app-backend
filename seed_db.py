import os
import json
from datetime import datetime, timedelta
from app import app
from models import db, User, HealthRecord, SymptomMetric, RedFlag, PossibleRisk


def seed():
    with app.app_context():
        # Recreate tables to apply schema changes
        print("Dropping and recreating all tables...")
        db.drop_all()
        db.create_all()

        # 0. Ensure root exists
        root = User(username='root', is_superuser=True)
        root.set_password('root')
        db.session.add(root)
        db.session.commit()
        print("Superuser 'root' created.")

        # 1. Ensure user 'andriel' exists
        user = User(username='andriel')
        user.set_password('andriel')
        db.session.add(user)
        db.session.commit()
        print("User 'andriel' created.")

        db.session.commit()
        print("Database reset. Ready for new functional data.")


if __name__ == '__main__':
    seed()
