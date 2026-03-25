from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_superuser = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class HealthRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symptoms = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text, nullable=True)
    ai_summary = db.Column(db.Text, nullable=True)
    ai_outcomes = db.Column(db.Text, nullable=True)
    ai_severity = db.Column(db.Integer, default=0)
    ai_frequency = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('health_records', lazy=True))

class SymptomMetric(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    health_record_id = db.Column(db.Integer, db.ForeignKey('health_record.id'), nullable=False)
    metric_name = db.Column(db.String(50), nullable=False) # e.g., 'severity', 'frequency'
    value = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('metrics', lazy=True))
    health_record = db.relationship('HealthRecord', backref=db.backref('metrics', lazy=True))

class RedFlag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    health_record_id = db.Column(db.Integer, db.ForeignKey('health_record.id'), nullable=False)
    flag_name = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('red_flags', lazy=True))
    health_record = db.relationship('HealthRecord', backref=db.backref('red_flags', lazy=True))

class PossibleRisk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    health_record_id = db.Column(db.Integer, db.ForeignKey('health_record.id'), nullable=False)
    risk_name = db.Column(db.String(100), nullable=False) # e.g., 'Sugar', 'Cholesterol'
    risk_level = db.Column(db.String(50), nullable=False) # e.g., 'Normal', 'High', 'Low'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('possible_risks', lazy=True))
    health_record = db.relationship('HealthRecord', backref=db.backref('possible_risks', lazy=True))
