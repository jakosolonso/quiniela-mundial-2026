from flask import Flask, render_template, redirect, url_for
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from database import db
from routes import api_bp
from models import Usuario, bcrypt
from datetime import datetime
import os

app = Flask(__name__)

# Configuración para producción
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'quiniela.db')

# Asegurar que la carpeta instance existe
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tu-clave-secreta-mundial-2026-cambia-esto')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar extensiones
db.init_app(app)
bcrypt.init_app(app)
CORS(app)

# Configurar Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor inicia sesión para acceder a la quiniela'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Registrar rutas de API
app.register_blueprint(api_bp, url_prefix='/api')

# ============ RUTAS DE PÁGINAS ============
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login_page'))

@app.route('/login')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register')
def register_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# Crear tablas al iniciar
with app.app_context():
    db.create_all()
    print("✅ Base de datos creada/verificada")
    
    # Crear usuario admin por defecto si no existe
    admin = Usuario.query.filter_by(email='admin@quiniela.com').first()
    if not admin:
        admin = Usuario(
            nombre='Administrador',
            email='admin@quiniela.com',
            es_admin=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("✅ Usuario administrador creado (email: admin@quiniela.com, password: admin123)")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)