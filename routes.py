from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from database import db
from models import Partido, Usuario, Pronostico
from datetime import datetime
import re

api_bp = Blueprint('api', __name__)

@api_bp.route('/selecciones', methods=['GET'])
def obtener_selecciones():
    selecciones = [
        {"codigo": "arg", "nombre": "Argentina", "url": "https://flagcdn.com/ar.svg"},
        {"codigo": "bra", "nombre": "Brasil", "url": "https://flagcdn.com/br.svg"},
        {"codigo": "fra", "nombre": "Francia", "url": "https://flagcdn.com/fr.svg"},
        {"codigo": "esp", "nombre": "España", "url": "https://flagcdn.com/es.svg"},
        {"codigo": "ger", "nombre": "Alemania", "url": "https://flagcdn.com/de.svg"},
        {"codigo": "eng", "nombre": "Inglaterra", "url": "https://flagcdn.com/gb.svg"},
        {"codigo": "ita", "nombre": "Italia", "url": "https://flagcdn.com/it.svg"},
        {"codigo": "ned", "nombre": "Países Bajos", "url": "https://flagcdn.com/nl.svg"},
        {"codigo": "por", "nombre": "Portugal", "url": "https://flagcdn.com/pt.svg"},
        {"codigo": "uru", "nombre": "Uruguay", "url": "https://flagcdn.com/uy.svg"},
        {"codigo": "col", "nombre": "Colombia", "url": "https://flagcdn.com/co.svg"},
        {"codigo": "mex", "nombre": "México", "url": "https://flagcdn.com/mx.svg"},
        {"codigo": "usa", "nombre": "Estados Unidos", "url": "https://flagcdn.com/us.svg"},
        {"codigo": "jpn", "nombre": "Japón", "url": "https://flagcdn.com/jp.svg"},
        {"codigo": "kor", "nombre": "Corea del Sur", "url": "https://flagcdn.com/kr.svg"},
        {"codigo": "mar", "nombre": "Marruecos", "url": "https://flagcdn.com/ma.svg"},
        {"codigo": "sen", "nombre": "Senegal", "url": "https://flagcdn.com/sn.svg"},
        {"codigo": "cro", "nombre": "Croacia", "url": "https://flagcdn.com/hr.svg"},
        {"codigo": "bel", "nombre": "Bélgica", "url": "https://flagcdn.com/be.svg"},
        {"codigo": "sui", "nombre": "Suiza", "url": "https://flagcdn.com/ch.svg"},
    ]
    return jsonify(selecciones)

# ============ AUTENTICACIÓN ============
@api_bp.route('/registro', methods=['POST'])
def registro():
    data = request.json
    
    # Validar email
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', data['email']):
        return jsonify({'error': 'Email inválido'}), 400
    
    # Verificar si el usuario existe
    existe = Usuario.query.filter_by(email=data['email']).first()
    if existe:
        return jsonify({'error': 'El email ya está registrado'}), 400
    
    # Validar contraseña
    if len(data['password']) < 6:
        return jsonify({'error': 'La contraseña debe tener al menos 6 caracteres'}), 400
    
    # Crear nuevo usuario (con selección favorita)
    usuario = Usuario(
        nombre=data['nombre'],
        email=data['email'],
        seleccion_favorita=data.get('seleccion_favorita')  # NUEVO
    )
    usuario.set_password(data['password'])
    
    db.session.add(usuario)
    db.session.commit()
    
    login_user(usuario)
    
    return jsonify({
        'mensaje': 'Usuario registrado exitosamente',
        'usuario': usuario.to_dict()
    }), 201

@api_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    usuario = Usuario.query.filter_by(email=data['email']).first()
    
    if not usuario or not usuario.check_password(data['password']):
        return jsonify({'error': 'Email o contraseña incorrectos'}), 401
    
    if not usuario.es_activo:
        return jsonify({'error': 'Cuenta desactivada'}), 401
    
    # Actualizar último acceso
    usuario.ultimo_acceso = datetime.utcnow()
    db.session.commit()
    
    # Iniciar sesión
    login_user(usuario, remember=data.get('remember', False))
    
    return jsonify({
        'mensaje': 'Login exitoso',
        'usuario': usuario.to_dict()
    }), 200

@api_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'mensaje': 'Sesión cerrada'}), 200

@api_bp.route('/usuario-actual', methods=['GET'])
@login_required
def usuario_actual():
    return jsonify({
        'id': current_user.id,
        'nombre': current_user.nombre,
        'email': current_user.email,
        'seleccion_favorita': current_user.seleccion_favorita,
        'es_admin': current_user.es_admin
    }), 200

# ============ VERIFICAR AUTENTICACIÓN EN ENDPOINTS EXISTENTES ============
@api_bp.route('/pronosticos', methods=['POST'])
@login_required
def crear_pronostico():
    data = request.json
    
    # Asegurar que el usuario solo haga pronósticos para sí mismo
    if data['usuario_id'] != current_user.id and not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    existe = Pronostico.query.filter_by(
        usuario_id=data['usuario_id'],
        partido_id=data['partido_id']
    ).first()
    
    if existe:
        existe.goles_local = data['goles_local']
        existe.goles_visitante = data['goles_visitante']
        db.session.commit()
        return jsonify({'mensaje': 'Pronóstico actualizado'}), 200
    
    pronostico = Pronostico(
        usuario_id=data['usuario_id'],
        partido_id=data['partido_id'],
        goles_local=data['goles_local'],
        goles_visitante=data['goles_visitante']
    )
    db.session.add(pronostico)
    db.session.commit()
    return jsonify({'mensaje': 'Pronóstico guardado'}), 201

@api_bp.route('/pronosticos/usuario/<int:usuario_id>', methods=['GET'])
@login_required
def obtener_pronosticos_usuario(usuario_id):
    # Verificar permisos
    if usuario_id != current_user.id and not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    pronosticos = Pronostico.query.filter_by(usuario_id=usuario_id).all()
    return jsonify([{
        'partido_id': p.partido_id,
        'goles_local': p.goles_local,
        'goles_visitante': p.goles_visitante,
        'puntos': p.puntos
    } for p in pronosticos])

# Mantener el resto de funciones existentes...
# (obtener_partidos, tabla_posiciones, cargar_datos_iniciales, etc.)