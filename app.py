from flask import Flask, render_template, redirect, url_for
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from database import db
from routes import api_bp
from models import Usuario, bcrypt
from datetime import datetime
import os

# Asegurar que Flask sirva archivos estáticos
app = Flask(__name__, static_folder='static', static_url_path='/static')

#  CONFIGURACION PARA SUPABASE 
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL no está configurada. "
        "Agrégala como variable de entorno en Railway."
    )

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tu-clave-secreta-cambia-esto')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 5,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
}

# Inicializar extensiones
db.init_app(app)
bcrypt.init_app(app)
CORS(app)

# Configurar Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Registrar rutas de API
app.register_blueprint(api_bp, url_prefix='/api')

# Rutas de páginas
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

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.es_admin:
        return redirect(url_for('dashboard'))
    return render_template('admin_panel.html')

@app.route('/admin/tiempo')
@login_required
def admin_tiempo():
    if not current_user.es_admin:
        return redirect(url_for('dashboard'))
    return render_template('admin_tiempo.html')

@app.route('/admin/ganadores')
@login_required
def admin_ganadores():
    if not current_user.es_admin:
        return redirect(url_for('dashboard'))
    return render_template('admin_ganadores.html')

# Crear tablas al iniciar
with app.app_context():
    db.create_all()
    print("✅ Base de datos conectada a Supabase")

    # Crear usuario admin si no existe
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
        print("✅ Usuario administrador creado")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)