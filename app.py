from flask import Flask, render_template, redirect, url_for
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from database import db
from routes import api_bp
from models import Usuario, bcrypt
from datetime import datetime
import os
from apscheduler.schedulers.background import BackgroundScheduler
from resultados_service import actualizar_resultados_en_db
import atexit

# ============ TAREAS PROGRAMADAS ============
scheduler = BackgroundScheduler()

# Programar la tarea (cada 10 minutos para evitar límites de API)
scheduler.add_job(
    func=actualizar_resultados_en_db,
    trigger="interval",
    minutes=10,  # Cada 10 minutos
    id="actualizar_resultados",
    replace_existing=True
)

# Iniciar el scheduler
scheduler.start()
print("🔄 Scheduler iniciado - Resultados se actualizarán cada 10 minutos")

# Detener scheduler al cerrar
atexit.register(lambda: scheduler.shutdown())

# Asegurar que Flask sirva archivos estáticos
app = Flask(__name__, static_folder='static', static_url_path='/static')
# ============ CONFIGURACIÓN SUPABASE ============
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    # ⚠️ REEMPLAZA 'TU_CONTRASEÑA' con tu contraseña real de Supabase
    DATABASE_URL = "postgresql://postgres.zuvokcpvywofmdnlcojw:F1n9k1l2%2364@aws-1-sa-east-1.pooler.supabase.com:5432/postgres"

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

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.es_admin:
        return redirect(url_for('dashboard'))
    return render_template('admin_panel.html')