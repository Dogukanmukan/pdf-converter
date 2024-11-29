from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
import os
from werkzeug.security import generate_password_hash, check_password_hash
from pdf2image import convert_from_path
from PIL import Image
import img2pdf
import stripe
import firebase_admin
from firebase_admin import credentials, firestore, auth
import pyrebase
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Jinja2 filters
@app.template_filter('datetime')
def format_datetime(value, format='%Y-%m-%d %H:%M:%S'):
    if value is None:
        return ""
    return datetime.fromtimestamp(value).strftime(format)

@app.template_filter('max_value')
def max_value(a, b):
    return max(a, b)

@app.template_filter('min_value')
def min_value(a, b):
    return min(a, b)

# Firebase Admin SDK setup
cred = credentials.Certificate('firebase-key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Pyrebase setup for client-side operations
config = {
    "apiKey": os.getenv('FIREBASE_API_KEY'),
    "authDomain": os.getenv('FIREBASE_AUTH_DOMAIN'),
    "projectId": os.getenv('FIREBASE_PROJECT_ID'),
    "storageBucket": os.getenv('FIREBASE_STORAGE_BUCKET'),
    "messagingSenderId": os.getenv('FIREBASE_MESSAGING_SENDER_ID'),
    "appId": os.getenv('FIREBASE_APP_ID'),
    "measurementId": os.getenv('FIREBASE_MEASUREMENT_ID'),
    "databaseURL": os.getenv('FIREBASE_DATABASE_URL')
}

firebase = pyrebase.initialize_app(config)
firebase_auth = firebase.auth()

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data.get('uid')
        self.email = user_data.get('email')
        self.subscription_status = user_data.get('subscription_status', 'free')
        self.daily_conversions = user_data.get('daily_conversions', 0)
        self.last_conversion_date = user_data.get('last_conversion_date')

@login_manager.user_loader
def load_user(user_id):
    try:
        user_doc = db.collection('users').document(user_id).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            user_data['uid'] = user_id
            return User(user_data)
    except Exception as e:
        print(f"Error loading user: {e}")
    return None

def reset_daily_conversions():
    if current_user.is_authenticated:
        try:
            today = datetime.utcnow().date()
            last_conversion_date = current_user.last_conversion_date
            
            if last_conversion_date:
                last_conversion_date = datetime.fromisoformat(last_conversion_date).date()
            
            if last_conversion_date is None or last_conversion_date < today:
                # Reset conversions at the start of each day
                db.collection('users').document(current_user.id).update({
                    'daily_conversions': 0,
                    'last_conversion_date': today.isoformat()
                })
                current_user.daily_conversions = 0
                current_user.last_conversion_date = today.isoformat()
            elif current_user.daily_conversions > 5 and current_user.subscription_status != 'premium':
                # Ensure free users never go above 5 conversions
                db.collection('users').document(current_user.id).update({
                    'daily_conversions': 5
                })
                current_user.daily_conversions = 5
        except Exception as e:
            print(f"Error resetting conversions: {e}")

def can_convert():
    if not current_user.is_authenticated:
        return False
    reset_daily_conversions()
    if current_user.subscription_status == 'premium':
        return True
    return current_user.daily_conversions < 5

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_pdf_to_image(input_path, output_path):
    try:
        images = convert_from_path(input_path)
        if images:
            images[0].save(output_path, 'JPEG')
    except Exception as e:
        raise Exception(f'PDF to Image conversion failed: {str(e)}')

def convert_image_to_pdf(input_path, output_path):
    try:
        with open(output_path, "wb") as f:
            f.write(img2pdf.convert(input_path))
    except Exception as e:
        raise Exception(f'Image to PDF conversion failed: {str(e)}')

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('landing'))

@app.route('/landing')
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    # Demo kullanım sayısını kontrol et
    if 'demo_usage' not in session:
        session['demo_usage'] = 0
    return render_template('landing.html', demo_usage=session['demo_usage'])

@app.route('/demo-pdf-to-image', methods=['POST'])
def demo_pdf_to_image():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if 'demo_usage' not in session:
        session['demo_usage'] = 0
    
    if session['demo_usage'] >= 2:
        flash('Demo kullanım hakkınız dolmuştur. Devam etmek için lütfen kayıt olun.', 'warning')
        return redirect(url_for('register'))
    
    if 'file' not in request.files:
        flash('Dosya seçilmedi', 'error')
        return redirect(url_for('landing'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Dosya seçilmedi', 'error')
        return redirect(url_for('landing'))
    
    if file and file.filename.lower().endswith('.pdf'):
        try:
            filename = secure_filename(file.filename)
            temp_folder = os.path.join(app.root_path, 'temp')
            
            if not os.path.exists(temp_folder):
                os.makedirs(temp_folder)
            
            input_path = os.path.join(temp_folder, filename)
            file.save(input_path)
            
            output_path = os.path.join(temp_folder, f"converted_{filename.rsplit('.', 1)[0]}.jpg")
            
            convert_pdf_to_image(input_path, output_path)
            
            session['demo_usage'] += 1
            
            return send_file(
                output_path,
                as_attachment=True,
                download_name=f"converted_{filename.rsplit('.', 1)[0]}.jpg"
            )
            
        except Exception as e:
            flash(f'Dönüştürme işlemi sırasında bir hata oluştu: {str(e)}', 'error')
            return redirect(url_for('landing'))
        
        finally:
            try:
                if os.path.exists(input_path):
                    os.remove(input_path)
                if os.path.exists(output_path):
                    os.remove(output_path)
            except:
                pass
    
    flash('Geçersiz dosya formatı. Lütfen PDF dosyası seçin.', 'error')
    return redirect(url_for('landing'))

@app.route('/demo-image-to-pdf', methods=['POST'])
def demo_image_to_pdf():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if 'demo_usage' not in session:
        session['demo_usage'] = 0
    
    if session['demo_usage'] >= 2:
        flash('Demo kullanım hakkınız dolmuştur. Devam etmek için lütfen kayıt olun.', 'warning')
        return redirect(url_for('register'))
    
    if 'file' not in request.files:
        flash('Dosya seçilmedi', 'error')
        return redirect(url_for('landing'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Dosya seçilmedi', 'error')
        return redirect(url_for('landing'))
    
    if file and file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        try:
            filename = secure_filename(file.filename)
            temp_folder = os.path.join(app.root_path, 'temp')
            
            if not os.path.exists(temp_folder):
                os.makedirs(temp_folder)
            
            input_path = os.path.join(temp_folder, filename)
            file.save(input_path)
            
            output_path = os.path.join(temp_folder, f"converted_{filename.rsplit('.', 1)[0]}.pdf")
            
            convert_image_to_pdf(input_path, output_path)
            
            session['demo_usage'] += 1
            
            return send_file(
                output_path,
                as_attachment=True,
                download_name=f"converted_{filename.rsplit('.', 1)[0]}.pdf"
            )
            
        except Exception as e:
            flash(f'Dönüştürme işlemi sırasında bir hata oluştu: {str(e)}', 'error')
            return redirect(url_for('landing'))
        
        finally:
            try:
                if os.path.exists(input_path):
                    os.remove(input_path)
                if os.path.exists(output_path):
                    os.remove(output_path)
            except:
                pass
    
    flash('Geçersiz dosya formatı. Lütfen JPG, JPEG veya PNG dosyası seçin.', 'error')
    return redirect(url_for('landing'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # Sign in with Firebase Authentication
            user = firebase_auth.sign_in_with_email_and_password(email, password)
            
            # Get user data from Firestore
            user_doc = db.collection('users').document(user['localId']).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                user_data['uid'] = user['localId']
                login_user(User(user_data))
                flash('Giriş başarılı!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Kullanıcı bilgileri bulunamadı.', 'error')
                
        except Exception as e:
            flash('Email veya şifre hatalı.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    try:
        firebase_auth.current_user = None
        logout_user()
        flash('Successfully logged out.', 'success')
    except Exception as e:
        flash(f'Error logging out: {str(e)}', 'error')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Reset daily conversions if needed
    reset_daily_conversions()
    
    # Get user's last 10 conversions
    conversions_ref = db.collection('conversions').where('user_id', '==', current_user.id).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10)
    conversions = conversions_ref.stream()
    conversions_list = []
    for conversion in conversions:
        conversion_data = conversion.to_dict()
        conversions_list.append(conversion_data)
    
    return render_template('dashboard.html', conversions=conversions_list)

@app.route('/convert', methods=['POST'])
def convert():
    # Demo kullanıcıları için kontrol
    if not current_user.is_authenticated:
        if 'demo_usage' not in session:
            session['demo_usage'] = 0
        if session['demo_usage'] >= 2:
            flash('Demo kullanım hakkınız dolmuştur. Devam etmek için lütfen kayıt olun.', 'warning')
            return redirect(url_for('register'))

    # Giriş yapmış kullanıcılar için kontrol
    elif not can_convert():
        flash('Günlük dönüştürme limitinize ulaştınız.', 'warning')
        return redirect(url_for('dashboard'))

    if 'file' not in request.files:
        flash('Dosya seçilmedi', 'error')
        return redirect(url_for('landing') if not current_user.is_authenticated else url_for('dashboard'))

    file = request.files['file']
    if file.filename == '':
        flash('Dosya seçilmedi', 'error')
        return redirect(url_for('landing') if not current_user.is_authenticated else url_for('dashboard'))

    conversion_type = request.form.get('conversion_type')
    if not conversion_type:
        flash('Dönüştürme tipi belirtilmedi', 'error')
        return redirect(url_for('landing') if not current_user.is_authenticated else url_for('dashboard'))

    try:
        filename = secure_filename(file.filename)
        temp_folder = os.path.join(app.root_path, 'temp')
        
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)
        
        input_path = os.path.join(temp_folder, filename)
        file.save(input_path)

        if conversion_type == 'pdf_to_image':
            if not filename.lower().endswith('.pdf'):
                raise Exception('PDF dosyası seçmelisiniz')
            output_path = os.path.join(temp_folder, f"converted_{filename.rsplit('.', 1)[0]}.jpg")
            convert_pdf_to_image(input_path, output_path)
        
        elif conversion_type == 'image_to_pdf':
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                raise Exception('Resim dosyası seçmelisiniz (JPG, JPEG veya PNG)')
            output_path = os.path.join(temp_folder, f"converted_{filename.rsplit('.', 1)[0]}.pdf")
            convert_image_to_pdf(input_path, output_path)
        
        else:
            raise Exception('Geçersiz dönüştürme tipi')

        # Kullanım sayısını güncelle
        if current_user.is_authenticated:
            user_ref = db.collection('users').document(current_user.id)
            user_ref.update({
                'daily_conversions': firestore.Increment(1),
                'last_conversion_date': datetime.now().timestamp()
            })
        else:
            session['demo_usage'] = session.get('demo_usage', 0) + 1

        return send_file(
            output_path,
            as_attachment=True,
            download_name=os.path.basename(output_path)
        )

    except Exception as e:
        flash(f'Dönüştürme işlemi sırasında bir hata oluştu: {str(e)}', 'error')
        return redirect(url_for('landing') if not current_user.is_authenticated else url_for('dashboard'))

    finally:
        try:
            if os.path.exists(input_path):
                os.remove(input_path)
            if os.path.exists(output_path):
                os.remove(output_path)
        except:
            pass

@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        response = send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )

        # Clean up the output file after sending
        @response.call_on_close
        def cleanup():
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error cleaning up output file: {str(e)}")

        return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/subscribe')
@login_required
def subscribe():
    return render_template('subscribe.html')

@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': os.getenv('STRIPE_PRICE_ID'),
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('payment_success', _external=True),
            cancel_url=url_for('subscribe', _external=True),
            client_reference_id=str(current_user.id)
        )
        return jsonify({'id': checkout_session.id})
    except Exception as e:
        return jsonify({'error': str(e)}), 403

@app.route('/payment-success')
@login_required
def payment_success():
    try:
        # Update user to premium
        db.collection('users').document(current_user.id).update({
            'subscription_status': 'premium'
        })
        flash('Successfully upgraded to premium!')
    except Exception as e:
        flash(f'Error upgrading account: {str(e)}')
    
    return render_template('payment_success.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # Create user in Firebase Authentication
            user = firebase_auth.create_user_with_email_and_password(email, password)
            
            # Create user document in Firestore
            user_data = {
                'email': email,
                'subscription_status': 'free',
                'daily_conversions': 0,
                'last_conversion_date': None
            }
            db.collection('users').document(user['localId']).set(user_data)
            
            # Log the user in
            user_data['uid'] = user['localId']
            login_user(User(user_data))
            flash('Kayıt başarılı!', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            flash(f'Kayıt sırasında bir hata oluştu: {str(e)}', 'error')
            
    return render_template('register.html')

if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(debug=True)
