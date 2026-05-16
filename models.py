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
    seleccion_favorita = db.Column(db.String(50), nullable=True)
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


class Partido(db.Model):
    __tablename__ = 'partidos'
    
    id = db.Column(db.Integer, primary_key=True)
    equipo_local = db.Column(db.String(50), nullable=False)
    equipo_visitante = db.Column(db.String(50), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False)
    grupo = db.Column(db.String(1), nullable=False)
    fase = db.Column(db.String(20), default='grupos')  # grupos, octavos, cuartos, semis, final
    resultado_local = db.Column(db.Integer, nullable=True)
    resultado_visitante = db.Column(db.Integer, nullable=True)
    jugado = db.Column(db.Boolean, default=False)
    
    pronosticos = db.relationship('Pronostico', backref='partido', lazy=True)


class Pronostico(db.Model):
    __tablename__ = 'pronosticos'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    partido_id = db.Column(db.Integer, db.ForeignKey('partidos.id'), nullable=False)
    goles_local = db.Column(db.Integer, nullable=False)
    goles_visitante = db.Column(db.Integer, nullable=False)
    puntos = db.Column(db.Integer, default=0)
    fecha_pronostico = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('usuario_id', 'partido_id', name='unique_pronostico'),)