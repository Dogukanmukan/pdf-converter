from functools import wraps
from flask import redirect, url_for, flash, session
from flask_login import current_user
from datetime import datetime, timedelta

def check_conversion_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow anonymous users 5 conversions
        if not current_user.is_authenticated:
            session.setdefault('anonymous_conversions', 0)
            session.setdefault('anonymous_reset_time', datetime.utcnow().isoformat())
            
            # Reset daily count if needed
            reset_time = datetime.fromisoformat(session['anonymous_reset_time'])
            if reset_time.date() < datetime.utcnow().date():
                session['anonymous_conversions'] = 0
                session['anonymous_reset_time'] = datetime.utcnow().isoformat()
            
            if session['anonymous_conversions'] >= 5:
                flash('Daily conversion limit reached. Please sign up for more conversions.')
                return redirect(url_for('register'))
            
            session['anonymous_conversions'] += 1
            return f(*args, **kwargs)
        
        # Check authenticated user limits
        if current_user.is_premium:
            return f(*args, **kwargs)
        
        # Reset daily count if needed
        if (current_user.last_conversion_reset is None or 
            current_user.last_conversion_reset.date() < datetime.utcnow().date()):
            current_user.daily_conversions = 0
            current_user.last_conversion_reset = datetime.utcnow()
            
        if current_user.daily_conversions >= 5:
            flash('Daily conversion limit reached. Please upgrade to Pro for unlimited conversions.')
            return redirect(url_for('subscribe'))
        
        return f(*args, **kwargs)
    return decorated_function

def requires_premium(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_premium:
            flash('This feature requires a Pro subscription.')
            return redirect(url_for('subscribe'))
        return f(*args, **kwargs)
    return decorated_function
