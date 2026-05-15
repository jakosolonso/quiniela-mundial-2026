from database import db
from datetime import datetime
from flask_login import UserMixin
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    seleccion_favorita = db.Column(db.String(50), nullable=True)  # NUEVO CAMPO
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_acceso = db.Column(db.DateTime)
    es_activo = db.Column(db.Boolean, default=True)
    es_admin = db.Column(db.Boolean, default=False)
    
    pronosticos = db.relationship('Pronostico', backref='usuario', lazy=True)
    
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'email': self.email,
            'seleccion_favorita': self.seleccion_favorita,
            'fecha_registro': self.fecha_registro.isoformat(),
            'es_admin': self.es_admin
        }

# El resto de las clases (Partido, Pronostico) se mantienen igual