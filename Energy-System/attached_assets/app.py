import os
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from itsdangerous import URLSafeTimedSerializer
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import numpy as np
from utils import generate_mock_data, get_ai_recommendations
from ml_predictor import predictor
import pandas as pd
from models import db, User, Facility, EnergyData

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_key")

# Initialize serializer for tokens
serializer = URLSafeTimedSerializer(app.secret_key)

@app.route('/signup', methods=['POST'])
def signup():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')

    if User.query.filter_by(username=username).first():
        flash('Username already exists')
        return redirect(url_for('login'))

    if User.query.filter_by(email=email).first():
        flash('Email already registered')
        return redirect(url_for('login'))

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    flash('Registration successful! Please login.')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')

        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))

        flash('Invalid credentials')
        return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            token = serializer.dumps(user.email, salt='password-reset-salt')
            user.reset_token = token
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()

            # Here you would typically send an email with the reset link
            # For this example, we'll just flash the token
            flash(f'Password reset link: /reset-password/{token}')

        return redirect(url_for('login'))

    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'POST':
        try:
            email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
            user = User.query.filter_by(email=email, reset_token=token).first()

            if user and user.reset_token_expiry > datetime.utcnow():
                user.set_password(request.form.get('password'))
                user.reset_token = None
                user.reset_token_expiry = None
                db.session.commit()
                flash('Password has been reset')
                return redirect(url_for('login'))

        except:
            flash('Invalid or expired reset link')

        return redirect(url_for('login'))

    return render_template('reset_password.html')


# Ensure instance directory exists
instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)

# Configure SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(instance_path, 'energy_management.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the app with the extension
db.init_app(app)

def update_mock_data():
    """Update mock data and store in database"""
    with app.app_context():
        new_data = generate_mock_data()

        # Get or create default facility
        from models import Facility, EnergyData
        facility = Facility.query.first()
        if not facility:
            facility = Facility(
                name="Commercial Complex A",
                location="San Francisco, CA",
                capacity=500.0,
                solar_panels=1200
            )
            db.session.add(facility)
            db.session.commit()

        # Create new energy data record
        energy_data = EnergyData(
            energy_produced=new_data['energy_produced'],
            energy_consumed=new_data['energy_consumed'],
            efficiency=new_data['efficiency'],
            current_load=new_data['current_load'],
            facility_id=facility.id
        )
        db.session.add(energy_data)
        db.session.commit()

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=update_mock_data, trigger="interval", seconds=30)
scheduler.start()



@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    if not user.profile_picture:
        return redirect(url_for('profile'))
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('profile.html', user=user)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if 'profile_picture' in request.files:
        file = request.files['profile_picture']
        if file and file.filename:
            # Save file to static/uploads
            filename = secure_filename(file.filename)
            if not os.path.exists('static/uploads'):
                os.makedirs('static/uploads')
            file_path = os.path.join('static/uploads', filename)
            file.save(file_path)
            user.profile_picture = f'/static/uploads/{filename}'

    user.username = request.form['username']
    user.email = request.form['email']
    db.session.commit()

    flash('Profile updated successfully')
    return redirect(url_for('profile'))

@app.route('/settings')
def settings():
    if not request.headers.get('X-Replit-User-Id'):
        return redirect(url_for('login'))
    return render_template('settings.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    if not user.profile_picture:
        return redirect(url_for('profile'))
    from models import Facility, EnergyData

    facility = Facility.query.first()
    if not facility:
        return "Facility not configured", 500

    # Get latest energy data
    latest_data = EnergyData.query.filter_by(facility_id=facility.id).order_by(EnergyData.timestamp.desc()).first()

    # Get historical data (last 24 points)
    historical_data = (EnergyData.query
                      .filter_by(facility_id=facility.id)
                      .order_by(EnergyData.timestamp.desc())
                      .limit(24)
                      .all())

    current_data = {
        'energy_produced': latest_data.energy_produced if latest_data else 0,
        'energy_consumed': latest_data.energy_consumed if latest_data else 0,
        'efficiency': latest_data.efficiency if latest_data else 0,
        'current_load': latest_data.current_load if latest_data else 0,
        'historical_data': [{
            'timestamp': data.timestamp.strftime('%H:%M'),
            'produced': data.energy_produced,
            'consumed': data.energy_consumed
        } for data in reversed(historical_data)]
    }

    recommendations = get_ai_recommendations(current_data)
    return render_template('dashboard.html', 
                         data=current_data,
                         recommendations=recommendations,
                         facility=facility,
                         user=user)

@app.route('/api/data')
def get_data():
    from models import Facility, EnergyData

    facility = Facility.query.first()
    if not facility:
        return jsonify({'error': 'Facility not configured'}), 500

    latest_data = EnergyData.query.filter_by(facility_id=facility.id).order_by(EnergyData.timestamp.desc()).first()
    historical_data = (EnergyData.query
                      .filter_by(facility_id=facility.id)
                      .order_by(EnergyData.timestamp.desc())
                      .limit(24)
                      .all())

    return jsonify({
        'energy_produced': latest_data.energy_produced if latest_data else 0,
        'energy_consumed': latest_data.energy_consumed if latest_data else 0,
        'efficiency': latest_data.efficiency if latest_data else 0,
        'current_load': latest_data.current_load if latest_data else 0,
        'historical_data': [{
            'timestamp': data.timestamp.strftime('%H:%M'),
            'produced': data.energy_produced,
            'consumed': data.energy_consumed
        } for data in reversed(historical_data)]
    })

@app.route('/historical')
def historical_analysis():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not User.query.get(session['user_id']).profile_picture:
        return redirect(url_for('profile'))
    from models import Facility, EnergyData
    from utils import analyze_trends, get_trend_insights

    facility = Facility.query.first()
    if not facility:
        return "Facility not configured", 500

    # Get historical data (last 7 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    historical_data = (EnergyData.query
                      .filter(EnergyData.facility_id == facility.id,
                             EnergyData.timestamp >= start_date,
                             EnergyData.timestamp <= end_date)
                      .order_by(EnergyData.timestamp.asc())
                      .all())

    # Prepare data for analysis
    data_points = [{
        'timestamp': record.timestamp,
        'energy_produced': record.energy_produced,
        'energy_consumed': record.energy_consumed
    } for record in historical_data]

    # Analyze trends
    trend_analysis = analyze_trends(data_points)
    insights = get_trend_insights(trend_analysis)

    # Prepare chart data
    chart_data = {
        'timestamps': [d['timestamp'].strftime('%Y-%m-%d %H:%M') for d in data_points],
        'production': [d['energy_produced'] for d in data_points],
        'consumption': [d['energy_consumed'] for d in data_points]
    }

    return render_template('historical.html',
                         facility=facility,
                         trend_analysis=trend_analysis,
                         insights=insights,
                         chart_data=chart_data)

@app.route('/predictions')
def get_predictions():
    """Get energy consumption predictions for the next 24 hours"""
    from models import Facility, EnergyData

    facility = Facility.query.first()
    if not facility:
        return jsonify({'error': 'Facility not configured'}), 500

    # Get historical data for training (last 30 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    historical_data = (EnergyData.query
                      .filter(EnergyData.facility_id == facility.id,
                             EnergyData.timestamp >= start_date,
                             EnergyData.timestamp <= end_date)
                      .order_by(EnergyData.timestamp.asc())
                      .all())

    if len(historical_data) < 24:  # Need at least 24 data points
        return jsonify({'error': 'Insufficient historical data'}), 400

    # Prepare data for model
    train_data = [{
        'timestamp': record.timestamp,
        'energy_produced': record.energy_produced,
        'energy_consumed': record.energy_consumed
    } for record in historical_data]

    # Train model if not already trained
    if not predictor.is_trained:
        validation_score = predictor.train(train_data)
        app.logger.info(f"Model trained with validation score: {validation_score}")

    # Get predictions
    predictions = predictor.predict_next_24h(train_data)

    return jsonify({
        'predictions': [{
            'timestamp': pred['timestamp'].strftime('%Y-%m-%d %H:%M'),
            'predicted_consumption': pred['predicted_consumption']
        } for pred in predictions]
    })

@app.route('/dashboard')
def ml_dashboard():
    """Render ML dashboard with predictions"""
    from models import Facility, EnergyData

    facility = Facility.query.first()
    if not facility:
        return "Facility not configured", 500

    return render_template('ml_dashboard.html',
                         facility=facility)

with app.app_context():
    # Make sure to import the models here or their tables won't be created
    import models  # noqa: F401
    db.create_all()
    update_mock_data()  # Initialize with first data point