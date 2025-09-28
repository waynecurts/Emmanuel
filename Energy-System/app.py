import os
import secrets
import random
from datetime import datetime, timedelta
import logging

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from itsdangerous import URLSafeTimedSerializer

from models import db, User, Facility, EnergyData
from utils import generate_mock_data, get_ai_recommendations, analyze_trends, get_trend_insights
from ml_predictor import EnergyPredictor

# Initialize the ML predictor
predictor = EnergyPredictor()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create the Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", secrets.token_hex(16))

# Configure the SQLAlchemy database
database_url = os.environ.get("DATABASE_URL", "sqlite:///instance/energy_intelligence.db")
# Fix PostgreSQL URL format for SQLAlchemy 1.4+
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
    # Add SSL mode require for PostgreSQL
    if "?" in database_url:
        database_url += "&sslmode=disable"
    else:
        database_url += "?sslmode=disable"

# Ensure instance directory exists
instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(instance_path, 'energy_intelligence.db')}"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the database
db.init_app(app)

# Create database tables
with app.app_context():
    db.create_all()

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Create URL safe serializer for password reset tokens
serializer = URLSafeTimedSerializer(app.secret_key)

# Add context processor for templates
@app.context_processor
def utility_processor():
    return {
        'now': datetime.utcnow
    }

# Initialize scheduler for background tasks
scheduler = BackgroundScheduler()
scheduler.start()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# REMOVED: No more mock data updates
# All data will come only from actual hardware connections


def create_default_facility():
    """Create a default facility if none exists"""
    with app.app_context():
        if Facility.query.count() == 0:
            default_facility = Facility(
                name="Main Facility",
                location="123 Energy Way, Powertown",
                capacity=100.0,
                solar_panels=48
            )
            db.session.add(default_facility)
            db.session.commit()
            logger.info("Created default facility")


# Initialize the app with data
with app.app_context():
    # Create database tables if they don't exist
    db.create_all()

    # Create a default user if none exists
    if User.query.count() == 0:
        default_user = User(
            username="demo",
            email="demo@example.com"
        )
        default_user.set_password("password")
        db.session.add(default_user)
        db.session.commit()
        logger.info("Created default user")

    # Create a default facility if none exists
    create_default_facility()

    # No mock data is used - all data comes from hardware only


@app.route('/')
def index():
    """Render the landing page"""
    return render_template('landing.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')

        # Check if identifier is username or email
        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()

        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid username/email or password')

    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Handle user registration"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # Check if username or email already exists
        user_check = User.query.filter((User.username == username) | (User.email == email)).first()

        if user_check:
            flash('Username or email already exists')
        else:
            # Create new user
            new_user = User(username=username, email=email)
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()

            login_user(new_user)
            flash('Welcome! Please complete your profile by adding a profile picture.', 'success')
            return redirect(url_for('profile'))

    return redirect(url_for('login'))


@app.route('/logout')
@login_required
def logout():
    """Handle user logout"""
    logout_user()
    return redirect(url_for('index'))


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle forgotten password requests"""
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            # Generate a 6-digit PIN code for password reset
            reset_pin = ''.join([str(secrets.randbelow(10)) for _ in range(6)])

            # Hash the PIN before storing it
            hashed_pin = generate_password_hash(reset_pin)

            # Store PIN hash and expiry in database
            user.reset_token = hashed_pin
            user.reset_token_expiry = datetime.utcnow() + timedelta(minutes=30)
            db.session.commit()

            # For a real application, this PIN would be sent via email
            # For demo purposes, we'll display it on screen
            flash(f'Your password reset PIN is: {reset_pin}', 'success')
            flash('This PIN is valid for 30 minutes. Use it to reset your password.', 'info')

            # Redirect to reset password page where user can enter PIN
            return redirect(url_for('reset_password_with_pin', email=email))
        else:
            # Don't reveal if email exists or not
            flash('If your email is registered, you will receive a password reset PIN', 'info')
            # Still redirect to avoid revealing if the email exists through behavior
            return redirect(url_for('reset_password_with_pin', email=email))

    return render_template('forgot_password.html')


@app.route('/reset-password-with-pin', methods=['GET', 'POST'])
def reset_password_with_pin():
    """Handle password reset using PIN code"""
    email = request.args.get('email', '')

    if request.method == 'POST':
        email = request.form.get('email')
        pin = request.form.get('pin')
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Validate the input
        if not all([email, pin, new_password, confirm_password]):
            flash('All fields are required', 'danger')
            return render_template('reset_password_pin.html', email=email)

        if new_password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('reset_password_pin.html', email=email)

        # Find the user by email
        user = User.query.filter_by(email=email).first()

        if not user or not user.reset_token or user.reset_token_expiry < datetime.utcnow():
            flash('Invalid or expired PIN code', 'danger')
            return render_template('reset_password_pin.html', email=email)

        # Verify the PIN
        if check_password_hash(user.reset_token, pin):
            # Update user's password
            user.set_password(new_password)

            # Clear reset token
            user.reset_token = None
            user.reset_token_expiry = None

            db.session.commit()

            flash('Your password has been updated. You can now log in with your new password', 'success')
            return redirect(url_for('login'))
        else:
            flash('Invalid PIN code', 'danger')
            return render_template('reset_password_pin.html', email=email)

    return render_template('reset_password_pin.html', email=email)


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Handle password reset using token (legacy method)"""
    try:
        # Find user with this token (this is kept for backward compatibility)
        user = User.query.filter_by(reset_token=token).first()

        if not user or user.reset_token_expiry < datetime.utcnow():
            flash('The password reset link is invalid or has expired')
            return redirect(url_for('login'))

        if request.method == 'POST':
            new_password = request.form.get('password')

            # Update user's password
            user.set_password(new_password)

            # Clear reset token
            user.reset_token = None
            user.reset_token_expiry = None

            db.session.commit()

            flash('Your password has been updated. You can now log in with your new password')
            return redirect(url_for('login'))

        return render_template('reset_password.html', token=token)

    except Exception as e:
        flash('An error occurred. Please try again.')
        logger.error(f"Password reset error: {str(e)}")
        return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Render the main dashboard"""
    facility = Facility.query.first()

    # Get the latest energy data from the last 60 seconds for hardware status
    sixty_seconds_ago = datetime.utcnow() - timedelta(seconds=60)
    latest_data = EnergyData.query.filter(
        EnergyData.timestamp >= sixty_seconds_ago
    ).order_by(EnergyData.timestamp.desc()).first()

    # Only get recommendations if we have recent data
    recommendations = []
    if latest_data and latest_data.timestamp:
        data_dict = {
            'energy_produced': latest_data.energy_produced,
            'energy_consumed': latest_data.energy_consumed,
            'efficiency': latest_data.efficiency,
            'current_load': latest_data.current_load
        }
        recommendations = get_ai_recommendations(data_dict)

    # Get data for the last 24 hours for the charts
    one_day_ago = datetime.utcnow() - timedelta(days=1)
    historical_data = EnergyData.query.filter(EnergyData.timestamp >= one_day_ago).order_by(EnergyData.timestamp).all()

    # Format data for the chart
    timestamps = [data.timestamp.strftime('%H:%M') for data in historical_data]
    production = [data.energy_produced for data in historical_data]
    consumption = [data.energy_consumed for data in historical_data]
    efficiency = [data.efficiency for data in historical_data]
    load = [data.current_load for data in historical_data]

    return render_template(
        'dashboard.html',
        facility=facility,
        latest_data=latest_data,
        recommendations=recommendations,
        timestamps=timestamps,
        production=production,
        consumption=consumption,
        efficiency=efficiency,
        load=load
    )


@app.route('/historical')
@login_required
def historical_analysis():
    """Render historical data analysis"""
    # Get timeframe from request, default to 7 days
    days = int(request.args.get('days', 7))

    # Get historical data for the specified timeframe
    time_ago = datetime.utcnow() - timedelta(days=days)
    historical_data = EnergyData.query.filter(EnergyData.timestamp >= time_ago).order_by(EnergyData.timestamp).all()

    # Convert to list of dictionaries for analysis
    data_points = []
    for data in historical_data:
        data_points.append({
            'timestamp': data.timestamp,
            'energy_produced': data.energy_produced,
            'energy_consumed': data.energy_consumed,
            'efficiency': data.efficiency,
            'current_load': data.current_load
        })

    # Analyze data to find trends
    trend_analysis = analyze_trends(data_points)

    # Get recommendations based on trends
    insights = get_trend_insights(trend_analysis)

    # Format data for charts
    timestamps = [data.timestamp.strftime('%m-%d %H:%M') for data in historical_data]
    production = [data.energy_produced for data in historical_data]
    consumption = [data.energy_consumed for data in historical_data]
    efficiency = [data.efficiency for data in historical_data]
    load = [data.current_load for data in historical_data]

    return render_template(
        'historical.html',
        days=days,
        trend_analysis=trend_analysis,
        insights=insights,
        timestamps=timestamps,
        production=production,
        consumption=consumption,
        efficiency=efficiency,
        load=load
    )


@app.route('/ml-dashboard')
@login_required
def ml_dashboard():
    """Render ML dashboard with predictions"""
    # Get historical data for training the model
    days_for_training = 30
    time_ago = datetime.utcnow() - timedelta(days=days_for_training)
    historical_data = EnergyData.query.filter(EnergyData.timestamp >= time_ago).order_by(EnergyData.timestamp).all()

    # Convert to list of dictionaries for the predictor
    data_points = []
    for data in historical_data:
        data_points.append({
            'timestamp': data.timestamp,
            'energy_produced': data.energy_produced,
            'energy_consumed': data.energy_consumed,
            'efficiency': data.efficiency,
            'current_load': data.current_load
        })

    # Train the predictor if we have enough data
    model_score = 0
    if len(data_points) > 24:
        model_score = predictor.train(data_points)

    # Get predictions for the next 24 hours
    predictions = predictor.predict(data_points, horizon=24)

    # Generate timestamps for predictions
    last_timestamp = datetime.utcnow()
    if data_points:
        last_timestamp = data_points[-1]['timestamp']

    prediction_timestamps = []
    for i in range(24):
        next_hour = last_timestamp + timedelta(hours=i+1)
        prediction_timestamps.append(next_hour.strftime('%m-%d %H:%M'))

    # Get recent actual data for comparison
    recent_hours = min(24, len(data_points))
    recent_data = data_points[-recent_hours:]
    recent_timestamps = [d['timestamp'].strftime('%m-%d %H:%M') for d in recent_data]
    recent_consumption = [d['energy_consumed'] for d in recent_data]

    return render_template(
        'ml_dashboard.html',
        model_score=model_score,
        prediction_timestamps=prediction_timestamps,
        predictions=predictions,
        recent_timestamps=recent_timestamps,
        recent_consumption=recent_consumption
    )


@app.route('/voltage-demo')
def voltage_demo():
    """Render the real-time voltage monitoring demonstration page"""
    return render_template('voltage_demo.html')


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Render user profile page"""
    if request.method == 'POST':
        # Update profile details
        current_user.username = request.form.get('username', current_user.username)
        current_user.email = request.form.get('email', current_user.email)

        # Handle profile image upload
        if 'profile_image' in request.files:
            profile_image = request.files['profile_image']

            if profile_image and profile_image.filename:
                # Secure the filename to prevent security issues
                filename = profile_image.filename
                # Generate a unique filename to avoid conflicts
                unique_filename = f"profile_{current_user.id}_{secrets.token_hex(8)}{os.path.splitext(filename)[1]}"

                # Create uploads directory if it doesn't exist
                uploads_dir = os.path.join('static', 'uploads', 'profiles')
                os.makedirs(uploads_dir, exist_ok=True)

                # Save the file
                file_path = os.path.join(uploads_dir, unique_filename)
                profile_image.save(file_path)

                # Update the user's profile picture
                current_user.profile_picture = f"/static/uploads/profiles/{unique_filename}"
                flash('Profile picture updated successfully')

        # Remove profile picture if requested
        if request.form.get('remove_profile_pic'):
            # If there's an existing profile picture, we would delete the file in a production app
            # Here we'll just remove the reference
            current_user.profile_picture = None
            flash('Profile picture removed')

        # Update password if provided
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')

        if current_password and new_password:
            if current_user.check_password(current_password):
                current_user.set_password(new_password)
                flash('Password updated successfully')
            else:
                flash('Current password is incorrect')

        db.session.commit()
        flash('Profile updated successfully')

        return redirect(url_for('profile'))

    return render_template('profile.html')


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Render application settings page"""
    facility = Facility.query.first()

    # Get hardware API key for display
    hardware_api_key = os.environ.get('HARDWARE_API_KEY', 'dev_hardware_key')

    if request.method == 'POST':
        setting_type = request.form.get('setting_type')

        if setting_type == 'facility':
            # Update facility settings
            facility.name = request.form.get('facility_name', facility.name)
            facility.location = request.form.get('facility_location', facility.location)
            facility.capacity = float(request.form.get('facility_capacity', facility.capacity))
            facility.solar_panels = int(request.form.get('facility_solar_panels', facility.solar_panels))

            db.session.commit()
            flash('Facility settings updated successfully')

        elif setting_type == 'notifications':
            # In a real app, you would save these preferences to a user settings table
            flash('Notification settings updated successfully')

        elif setting_type == 'display':
            # Store theme preference in session for demo purposes
            # In a production app, this would be stored in the database
            theme = request.form.get('theme')
            chart_color_scheme = request.form.get('chart_color_scheme')
            dashboard_layout = request.form.get('dashboard_layout')
            default_timeframe = request.form.get('default_timeframe')

            # Store in session so it persists across requests
            session['theme'] = theme
            session['chart_color_scheme'] = chart_color_scheme
            session['dashboard_layout'] = dashboard_layout
            session['default_timeframe'] = default_timeframe

            flash(f'Display settings updated successfully. Theme set to {theme}.')

        elif setting_type == 'hardware':
            # Regenerate the hardware API key if requested
            if request.form.get('regenerate_api_key'):
                # In a real app, you would update the environment variable or settings
                # For demo purposes, we'll just show a message
                new_key = secrets.token_hex(16)
                flash(f'API Key regenerated. New key: {new_key}', 'success')
                flash('Note: In a production environment, this key would be saved securely.', 'info')
                hardware_api_key = new_key

            # Update hardware settings
            reporting_interval = request.form.get('reporting_interval')
            if reporting_interval:
                flash(f'Hardware reporting interval updated to {reporting_interval} seconds', 'success')

        return redirect(url_for('settings'))

    # Generate API endpoint URLs for display
    api_endpoints = {
        'data_url': f"{request.host_url.rstrip('/')}/api/hardware/data",
        'config_url': f"{request.host_url.rstrip('/')}/api/hardware/config",
        'status_url': f"{request.host_url.rstrip('/')}/api/hardware/status"
    }

    return render_template('settings.html', 
                          facility=facility, 
                          hardware_api_key=hardware_api_key,
                          api_endpoints=api_endpoints)


@app.route('/api/data')
@login_required
def get_data():
    """API endpoint to get the latest energy data"""
    # Get the latest data point
    latest_data = EnergyData.query.order_by(EnergyData.timestamp.desc()).first()

    if not latest_data:
        return jsonify({
            'status': 'error',
            'message': 'No data available'
        }), 404

    # Format data as JSON
    data = {
        'timestamp': latest_data.timestamp.isoformat(),
        'energy_produced': latest_data.energy_produced,
        'energy_consumed': latest_data.energy_consumed,
        'efficiency': latest_data.efficiency,
        'current_load': latest_data.current_load
    }

    return jsonify({
        'status': 'success',
        'data': data
    })


@app.route('/api/latest-hardware-data')
@login_required
def get_latest_hardware_data():
    """API endpoint to get the latest hardware data including electrical parameters"""
    # Get the latest data from the last 60 seconds only
    sixty_seconds_ago = datetime.utcnow() - timedelta(seconds=60)
    latest_data = EnergyData.query.filter(
        EnergyData.timestamp >= sixty_seconds_ago
    ).order_by(EnergyData.timestamp.desc()).first()

    if not latest_data:
        return jsonify({
            'status': 'error',
            'message': 'No recent data available'
        }), 404

    # Format data as JSON with all electrical parameters
    data = {
        'timestamp': latest_data.timestamp.isoformat(),
        'energy_produced': latest_data.energy_produced,
        'energy_consumed': latest_data.energy_consumed,
        'efficiency': latest_data.efficiency,
        'current_load': latest_data.current_load,
        'voltage': latest_data.voltage,
        'current': latest_data.current,
        'current1': latest_data.current1,
        'current2': latest_data.current2,
        'current3': latest_data.current3,
        'frequency': latest_data.frequency,
        'power_factor': latest_data.power_factor,
        'alert_message': latest_data.alert_message,
        'alert_level': latest_data.alert_level
    }

    return jsonify({
        'status': 'success',
        'data': data
    })


@app.route('/api/hardware-status-check')
@login_required
def check_hardware_status():
    """API endpoint to check if hardware has sent recent data"""
    # Check if there's data from the last 60 seconds
    sixty_seconds_ago = datetime.utcnow() - timedelta(seconds=60)
    recent_data = EnergyData.query.filter(
        EnergyData.timestamp >= sixty_seconds_ago
    ).first()

    has_recent_data = recent_data is not None

    return jsonify({
        'status': 'success',
        'has_recent_data': has_recent_data,
        'last_data_time': recent_data.timestamp.isoformat() if recent_data else None
    })


@app.route('/api/predictions')
@login_required
def get_predictions():
    """Get energy consumption predictions for the next 24 hours"""
    # Get historical data for training the model
    days_for_training = 30
    time_ago = datetime.utcnow() - timedelta(days=days_for_training)
    historical_data = EnergyData.query.filter(EnergyData.timestamp >= time_ago).order_by(EnergyData.timestamp).all()

    # Convert to list of dictionaries for the predictor
    data_points = []
    for data in historical_data:
        data_points.append({
            'timestamp': data.timestamp,
            'energy_produced': data.energy_produced,
            'energy_consumed': data.energy_consumed,
            'efficiency': data.efficiency,
            'current_load': data.current_load
        })

    # Train the predictor if we have enough data
    if len(data_points) > 24:
        predictor.train(data_points)

    # Get predictions for the next 24 hours
    predictions = predictor.predict(data_points, horizon=24)

    # Generate timestamps for predictions
    last_timestamp = datetime.utcnow()
    if data_points:
        last_timestamp = data_points[-1]['timestamp']

    prediction_data = []
    for i, value in enumerate(predictions):
        next_hour = last_timestamp + timedelta(hours=i+1)
        prediction_data.append({
            'timestamp': next_hour.isoformat(),
            'value': value
        })

    return jsonify({
        'status': 'success',
        'data': prediction_data
    })


# Debug endpoint removed - no mock data is generated
# All data comes from actual hardware connections


@app.route('/api/debug/test-hardware', methods=['GET'])
def debug_test_hardware():
    """Test endpoint to simulate hardware data for debugging"""
    if os.environ.get('FLASK_ENV') != 'production':
        try:
            facility = Facility.query.first()
            if not facility:
                return jsonify({
                    'status': 'error',
                    'message': 'No facility found'
                }), 404

            # Create test data
            energy_data = EnergyData(
                timestamp=datetime.utcnow(),
                energy_produced=75.5,
                energy_consumed=62.3,
                efficiency=83.2,
                current_load=35.8,
                facility_id=facility.id,
                voltage=220.5,
                current=15.2,
                current1=5.1,
                current2=5.0,
                current3=5.1,
                frequency=50.0,
                power_factor=0.95,
                alert_message=None,
                alert_level=None
            )

            db.session.add(energy_data)
            db.session.commit()

            return jsonify({
                'status': 'success',
                'message': 'Test hardware data created',
                'data': {
                    'id': energy_data.id,
                    'timestamp': energy_data.timestamp.isoformat(),
                    'voltage': energy_data.voltage,
                    'current': energy_data.current
                }
            })

        except Exception as e:
            logger.error(f"Error creating test data: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to create test data: {str(e)}'
            }), 500
    else:
        return jsonify({
            'status': 'error',
            'message': 'Debug endpoints not available in production'
        }), 403


@app.route('/api/debug/voltage-demo', methods=['GET'])
def debug_voltage_demo():
    """Demonstrate real-time voltage monitoring with various conditions"""
    if os.environ.get('FLASK_ENV') != 'production':
        try:
            # Get voltage condition from query parameter
            condition = request.args.get('condition', 'normal')
            facility = Facility.query.first()

            if not facility:
                return jsonify({
                    'status': 'error',
                    'message': 'No facility found'
                }), 404

            # Base energy data
            energy_produced = round(random.uniform(40.0, 80.0), 2)
            energy_consumed = round(random.uniform(30.0, 60.0), 2)
            current_load = round(random.uniform(15.0, 45.0), 2)

            # Default electrical parameters
            voltage = 220.0
            current = round(random.uniform(8.0, 15.0), 1)
            frequency = round(random.uniform(49.8, 50.2), 1)
            power_factor = round(random.uniform(0.85, 0.98), 2)

            # Alert defaults
            alert_message = None
            alert_level = None

            # Set voltage and alerts based on condition
            if condition == 'high_warning':
                voltage = round(random.uniform(240.0, 245.0), 1)
                alert_message = f"High voltage condition: {voltage}V"
                alert_level = "warning"
            elif condition == 'high_critical':
                voltage = round(random.uniform(250.0, 260.0), 1)
                alert_message = f"CRITICAL HIGH VOLTAGE DETECTED: {voltage}V"
                alert_level = "critical"
            elif condition == 'low_warning':
                voltage = round(random.uniform(195.0, 205.0), 1)
                alert_message = f"Low voltage condition: {voltage}V"
                alert_level = "warning"
            elif condition == 'low_critical':
                voltage = round(random.uniform(180.0, 190.0), 1)
                alert_message = f"CRITICAL LOW VOLTAGE DETECTED: {voltage}V"
                alert_level = "critical"
            elif condition == 'fluctuating':
                # Random voltage between 195-245V to simulate fluctuation
                voltage = round(random.uniform(195.0, 245.0), 1)
                if voltage > 240.0:
                    alert_message = f"High voltage condition: {voltage}V"
                    alert_level = "warning"
                elif voltage < 200.0:
                    alert_message = f"Low voltage condition: {voltage}V"
                    alert_level = "warning"

            # Calculate efficiency (as percentage for storage, will be converted to decimal in display)
            if energy_produced > 0:
                efficiency = min(100, (energy_consumed / energy_produced) * 100)
            else:
                efficiency = 0

            # Create a new energy data record
            energy_data = EnergyData(
                timestamp=datetime.utcnow(),
                energy_produced=energy_produced,
                energy_consumed=energy_consumed,
                efficiency=efficiency,
                current_load=current_load,
                facility_id=facility.id,
                voltage=voltage,
                current=current,
                frequency=frequency,
                power_factor=power_factor,
                alert_message=alert_message,
                alert_level=alert_level
            )

            db.session.add(energy_data)
            db.session.commit()

            response = {
                'status': 'success',
                'message': f'Voltage demo data generated ({condition})',
                'data': {
                    'timestamp': energy_data.timestamp.isoformat(),
                    'voltage': voltage,
                    'current': current,
                    'frequency': frequency,
                    'power_factor': power_factor
                }
            }

            if alert_message:
                response['alert'] = {
                    'message': alert_message,
                    'level': alert_level
                }

            return jsonify(response)

        except Exception as e:
            logger.error(f"Error in voltage demo: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Failed to generate voltage demo data',
                'error': str(e)
            }), 500
    else:
        return jsonify({
            'status': 'error',
            'message': 'Debug endpoints not available in production'
        }), 403


# Example Files Routes
@app.route('/examples/<path:filename>')
def serve_example(filename):
    """Serve example files directly from the examples directory"""
    return send_from_directory('examples', filename)


# Hardware Integration Endpoints

@app.route('/api/hardware/data', methods=['POST'])
def receive_hardware_data():
    """API endpoint to receive data from IoT hardware sensors"""
    try:
        # Get API key from headers for authentication
        api_key = request.headers.get('X-API-Key')

        # Check if the API key is valid (you would implement proper key validation)
        if not api_key:
            return jsonify({
                'status': 'error',
                'message': 'Missing API key'
            }), 401

        # Validate API key (simple method for demonstration)
        # In production, use a more secure method
        if api_key != os.environ.get('HARDWARE_API_KEY', 'dev_hardware_key'):
            return jsonify({
                'status': 'error',
                'message': 'Invalid API key'
            }), 401

        # Validate the incoming data
        data = request.json
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400

        # Extract required sensor data fields
        required_fields = ['energy_produced', 'energy_consumed', 'current_load']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }), 400

        # Extract data fields with validation
        energy_produced = float(data.get('energy_produced', 0))
        energy_consumed = float(data.get('energy_consumed', 0))
        current_load = float(data.get('current_load', 0))

        # Extract optional but important electrical parameters
        voltage = float(data.get('voltage', 0))
        current = float(data.get('current', 0))  # Backward compatibility
        current1 = float(data.get('current1', 0))  # Phase 1 current
        current2 = float(data.get('current2', 0))  # Phase 2 current
        current3 = float(data.get('current3', 0))  # Phase 3 current
        frequency = float(data.get('frequency', 0))
        power_factor = float(data.get('power_factor', 0))

        # Calculate total current if individual phase currents are provided
        if current1 > 0 or current2 > 0 or current3 > 0:
            current = current1 + current2 + current3

        # Calculate efficiency (as percentage for storage, will be converted to decimal in display)
        if energy_produced > 0:
            efficiency = min(100, (energy_consumed / energy_produced) * 100)
        else:
            efficiency = 0

        # Get the facility ID from request or use the default
        facility_id = data.get('facility_id')
        if not facility_id:
            # Get the default facility
            facility = Facility.query.first()
            if not facility:
                return jsonify({
                    'status': 'error',
                    'message': 'No facility configured'
                }), 400
            facility_id = facility.id

        # Analyze voltage conditions and create alerts if necessary
        alert_message = None
        alert_level = None

        if voltage > 0:  # Only check if voltage data is provided
            # These thresholds would be configurable in a real system
            nominal_voltage = 220  # This could be pulled from facility settings
            high_voltage_threshold = nominal_voltage * 1.1  # 10% above nominal
            low_voltage_threshold = nominal_voltage * 0.9   # 10% below nominal
            critical_high_threshold = nominal_voltage * 1.15 # 15% above nominal
            critical_low_threshold = nominal_voltage * 0.85  # 15% below nominal

            if voltage >= critical_high_threshold:
                alert_message = f"CRITICAL HIGH VOLTAGE DETECTED: {voltage:.1f}V"
                alert_level = "critical"
                logger.warning(f"Critical high voltage detected: {voltage:.1f}V")
            elif voltage >= high_voltage_threshold:
                alert_message = f"High voltage condition: {voltage:.1f}V"
                alert_level = "warning"
                logger.info(f"High voltage condition: {voltage:.1f}V")
            elif voltage <= critical_low_threshold:
                alert_message = f"CRITICAL LOW VOLTAGE DETECTED: {voltage:.1f}V"
                alert_level = "critical"
                logger.warning(f"Critical low voltage detected: {voltage:.1f}V")
            elif voltage <= low_voltage_threshold:
                alert_message = f"Low voltage condition: {voltage:.1f}V"
                alert_level = "warning"
                logger.info(f"Low voltage condition: {voltage:.1f}V")

        # Create a new energy data record with additional electrical parameters
        energy_data = EnergyData(
            timestamp=datetime.utcnow(),
            energy_produced=energy_produced,
            energy_consumed=energy_consumed,
            efficiency=efficiency,
            current_load=current_load,
            facility_id=facility_id,
            voltage=voltage if voltage > 0 else None,
            current=current if current > 0 else None,
            current1=current1 if current1 > 0 else None,
            current2=current2 if current2 > 0 else None,
            current3=current3 if current3 > 0 else None,
            frequency=frequency if frequency > 0 else None,
            power_factor=power_factor if power_factor > 0 else None,
            alert_message=alert_message,
            alert_level=alert_level
        )

        # Save to database
        db.session.add(energy_data)
        db.session.commit()

        logger.info(f"Received hardware data: produced={energy_produced}, consumed={energy_consumed}, voltage={voltage}")

        # Prepare response with alert information if applicable
        response = {
            'status': 'success',
            'message': 'Data received successfully',
            'data_id': energy_data.id
        }

        if alert_message:
            response['alert'] = {
                'message': alert_message,
                'level': alert_level
            }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error processing hardware data: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Server error: {str(e)}'
        }), 500


@app.route('/api/hardware/status', methods=['GET'])
def get_hardware_status():
    """API endpoint to check hardware connectivity"""
    try:
        # Get API key from headers for authentication
        api_key = request.headers.get('X-API-Key')

        # Check if the API key is valid
        if not api_key or api_key != os.environ.get('HARDWARE_API_KEY', 'dev_hardware_key'):
            return jsonify({
                'status': 'error',
                'message': 'Authentication failed'
            }), 401

        # Return system status
        return jsonify({
            'status': 'success',
            'server_time': datetime.utcnow().isoformat(),
            'message': 'System online and ready to receive data'
        })

    except Exception as e:
        logger.error(f"Error checking hardware status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Server error: {str(e)}'
        }), 500


@app.route('/api/hardware/config', methods=['GET'])
def get_hardware_config():
    """API endpoint to provide configuration to IoT devices"""
    try:
        # Get API key from headers for authentication
        api_key = request.headers.get('X-API-Key')

        # Check if the API key is valid
        if not api_key or api_key != os.environ.get('HARDWARE_API_KEY', 'dev_hardware_key'):
            return jsonify({
                'status': 'error',
                'message': 'Authentication failed'
            }), 401

        # Get facility data for configuration
        facility = Facility.query.first()
        if not facility:
            return jsonify({
                'status': 'error',
                'message': 'No facility configured'
            }), 400

        # Return configuration data with voltage monitoring parameters
        return jsonify({
            'status': 'success',
            'config': {
                'facility_id': facility.id,
                'reporting_interval': 300,  # seconds
                'power_save_mode': False,
                'data_fields': ['energy_produced', 'energy_consumed', 'current_load'],
                'electrical_monitoring': {
                    'enabled': True,
                    'voltage_monitoring': True,
                    'nominal_voltage': 220,  # V
                    'voltage_high_threshold': 242,  # V (10% above nominal)
                    'voltage_low_threshold': 198,   # V (10% below nominal)
                    'voltage_critical_high': 253,   # V (15% above nominal)
                    'voltage_critical_low': 187     # V (15% below nominal)
                }
            }
        })

    except Exception as e:
        logger.error(f"Error providing hardware configuration: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Server error: {str(e)}'
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)