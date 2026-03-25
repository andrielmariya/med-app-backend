import jwt
from functools import wraps
from flask import request, jsonify, current_app
from sqlalchemy import func
from datetime import datetime, timedelta
from models import db, User, HealthRecord, SymptomMetric, RedFlag, PossibleRisk
from llm import analyze_symptoms

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            token = token.split(" ")[1]
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.filter_by(id=data['user_id']).first()
        except Exception as e:
            return jsonify({'message': 'Token is invalid!'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

def register_routes(app):
    @app.route('/api/login', methods=['POST'])
    def login():
        data = request.get_json()
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({'message': 'Could not verify'}), 401

        user = User.query.filter_by(username=data['username']).first()
        if not user or not user.check_password(data['password']):
            return jsonify({'message': 'Login invalid'}), 401

        token = jwt.encode({'user_id': user.id, 'exp': datetime.utcnow() + timedelta(hours=24)}, app.config['SECRET_KEY'], algorithm="HS256")
        return jsonify({'token': token, 'is_superuser': user.is_superuser, 'username': user.username})

    @app.route('/api/register', methods=['POST'])
    def register():
        data = request.get_json()
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'message': 'User already exists'}), 400
        new_user = User(username=data['username'])
        new_user.set_password(data['password'])
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'User created successfully'})

    @app.route('/api/user/change_password', methods=['POST'])
    @token_required
    def change_password(current_user):
        data = request.get_json()
        if not data or not data.get('new_password'):
            return jsonify({'message': 'New password is required'}), 400
        
        current_user.set_password(data['new_password'])
        db.session.commit()
        return jsonify({'message': 'Your password has been successfully updated'})

    @app.route('/api/health', methods=['POST'])
    @token_required
    def create_health_record(current_user):
        from models import SymptomMetric, RedFlag, PossibleRisk
        try:
            data = request.get_json()
            symptoms = data.get('symptoms')
            details = data.get('details')
            model_type = data.get('model_type', 'local')
            if not symptoms:
                return jsonify({'message': 'Symptoms are required'}), 400
                
            print(f"User {current_user.username} (Model: {model_type}) submitting symptoms: {symptoms}")
            # Unified Call: Gets summary, metrics, flags, and risks in one go
            summary, outcomes, metrics, red_flags, risks = analyze_symptoms(symptoms, details, model_type)
            
            new_record = HealthRecord(
                user_id=current_user.id,
                symptoms=symptoms,
                details=details,
                ai_summary=summary,
                ai_outcomes=outcomes,
                ai_severity=int(metrics.get('severity', 0)),
                ai_frequency=int(metrics.get('frequency', 0))
            )
            db.session.add(new_record)
            db.session.flush() # Get the record ID

            # Save Metrics
            for name, val in metrics.items():
                db.session.add(SymptomMetric(
                    user_id=current_user.id,
                    health_record_id=new_record.id,
                    metric_name=name,
                    value=float(val)
                ))

            # Save Red Flags (Already extracted in unified call)
            if red_flags:
                print(f"Adding {len(red_flags)} red flags for record {new_record.id}...")
                for flag in red_flags:
                    db.session.add(RedFlag(
                        user_id=current_user.id,
                        health_record_id=new_record.id,
                        flag_name=flag.get('name', 'General Flag'),
                        details=flag.get('details', '')
                    ))

            # Save Possible Risks (Already extracted in unified call)
            if risks:
                print(f"Adding {len(risks)} risks for record {new_record.id}...")
                for risk in risks:
                    db.session.add(PossibleRisk(
                        user_id=current_user.id,
                        health_record_id=new_record.id,
                        risk_name=risk.get('name', 'General Risk'),
                        risk_level=risk.get('level', 'Normal')
                    ))

            db.session.commit()
            print(f"Record {new_record.id} and associated data saved successfully.")
            print(f"Record saved successfully for {current_user.username}")
            
            return jsonify({
                'message': 'Record saved!',
                'record': {
                    'id': new_record.id,
                    'ai_summary': new_record.ai_summary,
                    'ai_severity': new_record.ai_severity
                }
            }), 201
        except Exception as e:
            db.session.rollback()
            print(f"Error in create_health_record: {e}")
            return jsonify({'message': f'Server error: {str(e)}'}), 500


    @app.route('/api/health/metrics', methods=['GET'])
    @token_required
    def get_metrics(current_user):
        # 1. Get data from the last 30 days, grouped by date, taking MAX value correctly
        thirty_days_ago = (datetime.utcnow() - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # We need to cast the created_at to date for grouping
        metrics_query = db.session.query(
            SymptomMetric.metric_name,
            func.date(SymptomMetric.created_at).label('metric_date'),
            func.max(SymptomMetric.value).label('max_value')
        ).filter(
            SymptomMetric.user_id == current_user.id,
            SymptomMetric.created_at >= thirty_days_ago
        ).group_by(
            SymptomMetric.metric_name,
            'metric_date'
        ).all()

        # 2. Organize raw data into a map for easy lookup
        data_map = {}
        for m_name, m_date, m_val in metrics_query:
            if m_name not in data_map:
                data_map[m_name] = {}
            data_map[m_name][str(m_date)] = m_val

        # 3. Generate a complete 30-day timeline with zero-filling
        output = {}
        # Ensure 'severity' exists in output even if no data
        metric_names = list(data_map.keys())
        if 'severity' not in metric_names:
            metric_names.append('severity')

        for name in metric_names:
            output[name] = []
            for i in range(30):
                current_date = (thirty_days_ago + timedelta(days=i)).date()
                date_str = str(current_date)
                val = data_map.get(name, {}).get(date_str, 0)
                output[name].append({
                    'value': val,
                    'date': date_str
                })

        return jsonify(output)

    @app.route('/api/health/redflags', methods=['GET'])
    @token_required
    def get_redflags(current_user):
        time_range = request.args.get('range', '7d')
        now = datetime.utcnow()
        
        counts_dict = {}
        if time_range == '7d':
            start_date = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
            for i in range(7):
                day = (start_date + timedelta(days=i)).date()
                counts_dict[str(day)] = 0
            
            results = db.session.query(
                func.date(RedFlag.created_at).label('label'),
                func.count(RedFlag.id).label('count')
            ).filter(RedFlag.user_id == current_user.id, RedFlag.created_at >= start_date)\
             .group_by('label').all()
            
            for r in results:
                counts_dict[str(r.label)] = r.count
        else:
            # Yearly padding
            for i in range(12):
                month_date = (now.replace(day=1) - timedelta(days=i*30))
                month_key = month_date.strftime('%Y-%m')
                counts_dict[month_key] = 0
            
            start_date = now - timedelta(days=365)
            results = db.session.query(
                func.date_format(RedFlag.created_at, '%Y-%m').label('label'),
                func.count(RedFlag.id).label('count')
            ).filter(RedFlag.user_id == current_user.id, RedFlag.created_at >= start_date)\
             .group_by('label').all()
            
            for r in results:
                counts_dict[str(r.label)] = r.count

        final_counts = [{'label': k, 'count': v} for k, v in sorted(counts_dict.items())]
        flags = RedFlag.query.filter_by(user_id=current_user.id).order_by(RedFlag.created_at.desc()).limit(20).all()
        
        return jsonify({
            'counts': final_counts,
            'recent_flags': [{'name': f.flag_name, 'details': f.details, 'date': f.created_at.isoformat()} for f in flags]
        })

    @app.route('/api/health/risks', methods=['GET'])
    @token_required
    def get_risks(current_user):
        time_range = request.args.get('range', '7d')
        now = datetime.utcnow()
        
        counts_dict = {}
        if time_range == '7d':
            start_date = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
            for i in range(7):
                day = (start_date + timedelta(days=i)).date()
                counts_dict[str(day)] = 0
                
            results = db.session.query(
                func.date(PossibleRisk.created_at).label('label'),
                func.count(PossibleRisk.id).label('count')
            ).filter(PossibleRisk.user_id == current_user.id, PossibleRisk.created_at >= start_date)\
             .group_by('label').all()
            
            for r in results:
                counts_dict[str(r.label)] = r.count
        else:
            for i in range(12):
                month_date = (now.replace(day=1) - timedelta(days=i*30))
                month_key = month_date.strftime('%Y-%m')
                counts_dict[month_key] = 0

            start_date = now - timedelta(days=365)
            results = db.session.query(
                func.date_format(PossibleRisk.created_at, '%Y-%m').label('label'),
                func.count(PossibleRisk.id).label('count')
            ).filter(PossibleRisk.user_id == current_user.id, PossibleRisk.created_at >= start_date)\
             .group_by('label').all()
             
            for r in results:
                counts_dict[str(r.label)] = r.count

        final_counts = [{'label': k, 'count': v} for k, v in sorted(counts_dict.items())]
             
        latest_risks = db.session.query(PossibleRisk).filter(
            PossibleRisk.user_id == current_user.id
        ).order_by(PossibleRisk.created_at.desc()).all()
        
        seen = set()
        unique_risks = []
        for r in latest_risks:
            if r.risk_name not in seen:
                unique_risks.append({
                    'name': r.risk_name,
                    'level': r.risk_level,
                    'date': r.created_at.isoformat()
                })
                seen.add(r.risk_name)
        
        return jsonify({
            'counts': final_counts,
            'unique_risks': unique_risks
        })


    @app.route('/api/dashboard', methods=['GET'])
    @token_required
    def get_dashboard(current_user):
        records = HealthRecord.query.filter_by(user_id=current_user.id).order_by(HealthRecord.created_at.desc()).all()
        output = []
        for r in records:
            output.append({
                'id': r.id,
                'symptoms': r.symptoms,
                'details': r.details,
                'ai_summary': r.ai_summary,
                'ai_outcomes': r.ai_outcomes,
                'ai_severity': r.ai_severity,
                'ai_frequency': r.ai_frequency,
                'created_at': r.created_at.isoformat()
            })
        return jsonify({'records': output})

    @app.route('/api/admin/users', methods=['GET'])
    @token_required
    def get_users(current_user):
        if not current_user.is_superuser:
            return jsonify({'message': 'Unauthorized'}), 403
        users = User.query.all()
        return jsonify([{'id': u.id, 'username': u.username, 'is_superuser': u.is_superuser, 'created_at': u.created_at.isoformat()} for u in users])

    @app.route('/api/admin/generate_reset_link', methods=['POST'])
    @token_required
    def generate_reset_link(current_user):
        if not current_user.is_superuser:
            return jsonify({'message': 'Unauthorized'}), 403
        
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'message': 'User ID is required'}), 400
            
        user = User.query.get(user_id)
        if not user:
            return jsonify({'message': 'User not found'}), 404
            
        # Generate a short-lived token (1 hour) for password reset
        token = jwt.encode({
            'reset_user_id': user.id,
            'exp': datetime.utcnow() + timedelta(hours=1)
        }, current_app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({
            'message': 'Reset token generated',
            'token': token,
            'username': user.username
        })

    @app.route('/api/user/reset_password_with_token', methods=['POST'])
    def reset_password_with_token():
        data = request.get_json()
        token = data.get('token')
        new_password = data.get('new_password')
        
        if not token or not new_password:
            return jsonify({'message': 'Token and new password are required'}), 400
            
        try:
            decoded = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            user_id = decoded['reset_user_id']
            user = User.query.get(user_id)
            if not user:
                return jsonify({'message': 'User not found'}), 404
                
            user.set_password(new_password)
            db.session.commit()
            return jsonify({'message': 'Password has been reset successfully'})
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Reset link has expired'}), 400
        except Exception:
            return jsonify({'message': 'Invalid reset link'}), 400
