from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from database import db
from models import Partido, Usuario, Pronostico
from datetime import datetime
import re

api_bp = Blueprint('api', __name__)

# ============ FUNCIÓN DE PUNTUACIÓN AVANZADA ============
def calcular_puntos(goles_local_p, goles_visitante_p, goles_local_r, goles_visitante_r, fase):
    """
    Calcula puntos según:
    - Resultado exacto: 5 pts
    - Ganador/empate acertado: 3 pts
    - Diferencia de goles exacta: +1 pt extra
    - Semifinal y Final: puntos x2
    """
    puntos = 0
    
    # Verificar si acertó el resultado exacto
    if goles_local_p == goles_local_r and goles_visitante_p == goles_visitante_r:
        puntos = 5
    # Verificar si acertó ganador o empate
    elif (goles_local_p - goles_visitante_p) == (goles_local_r - goles_visitante_r):
        puntos = 3
    
    # Bonus por diferencia de goles exacta (solo si no es resultado exacto)
    if puntos != 5:
        diferencia_p = goles_local_p - goles_visitante_p
        diferencia_r = goles_local_r - goles_visitante_r
        if diferencia_p == diferencia_r:
            puntos += 1
    
    # Bonus para Semifinales y Final (x2)
    if fase in ['semis', 'final']:
        puntos = puntos * 2
    
    return puntos


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
    
    # Crear nuevo usuario
    usuario = Usuario(
        nombre=data['nombre'],
        email=data['email'],
        seleccion_favorita=data.get('seleccion_favorita')
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


# ============ SELECCIONES ============
@api_bp.route('/selecciones', methods=['GET'])
def obtener_selecciones():
    selecciones = [
        {"codigo": "arg", "nombre": "Argentina", "bandera": "https://flagcdn.com/ar.svg"},
        {"codigo": "bra", "nombre": "Brasil", "bandera": "https://flagcdn.com/br.svg"},
        {"codigo": "fra", "nombre": "Francia", "bandera": "https://flagcdn.com/fr.svg"},
        {"codigo": "esp", "nombre": "España", "bandera": "https://flagcdn.com/es.svg"},
        {"codigo": "ger", "nombre": "Alemania", "bandera": "https://flagcdn.com/de.svg"},
        {"codigo": "eng", "nombre": "Inglaterra", "bandera": "https://flagcdn.com/gb.svg"},
        {"codigo": "ita", "nombre": "Italia", "bandera": "https://flagcdn.com/it.svg"},
        {"codigo": "ned", "nombre": "Países Bajos", "bandera": "https://flagcdn.com/nl.svg"},
        {"codigo": "por", "nombre": "Portugal", "bandera": "https://flagcdn.com/pt.svg"},
        {"codigo": "uru", "nombre": "Uruguay", "bandera": "https://flagcdn.com/uy.svg"},
        {"codigo": "col", "nombre": "Colombia", "bandera": "https://flagcdn.com/co.svg"},
        {"codigo": "mex", "nombre": "México", "bandera": "https://flagcdn.com/mx.svg"},
        {"codigo": "usa", "nombre": "Estados Unidos", "bandera": "https://flagcdn.com/us.svg"},
        {"codigo": "jpn", "nombre": "Japón", "bandera": "https://flagcdn.com/jp.svg"},
        {"codigo": "kor", "nombre": "Corea del Sur", "bandera": "https://flagcdn.com/kr.svg"},
        {"codigo": "mar", "nombre": "Marruecos", "bandera": "https://flagcdn.com/ma.svg"},
        {"codigo": "sen", "nombre": "Senegal", "bandera": "https://flagcdn.com/sn.svg"},
        {"codigo": "cro", "nombre": "Croacia", "bandera": "https://flagcdn.com/hr.svg"},
        {"codigo": "bel", "nombre": "Bélgica", "bandera": "https://flagcdn.com/be.svg"},
        {"codigo": "sui", "nombre": "Suiza", "bandera": "https://flagcdn.com/ch.svg"}
    ]
    return jsonify(selecciones)


# ============ PARTIDOS ============
@api_bp.route('/partidos', methods=['GET'])
def obtener_partidos():
    partidos = Partido.query.order_by(Partido.fecha).all()
    return jsonify([{
        'id': p.id,
        'equipo_local': p.equipo_local,
        'equipo_visitante': p.equipo_visitante,
        'fecha': p.fecha.isoformat(),
        'grupo': p.grupo,
        'fase': p.fase,
        'resultado_local': p.resultado_local,
        'resultado_visitante': p.resultado_visitante,
        'jugado': p.jugado
    } for p in partidos])


@api_bp.route('/partidos/<int:partido_id>/resultado', methods=['PUT'])
@login_required
def actualizar_resultado(partido_id):
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.json
    partido = Partido.query.get_or_404(partido_id)
    partido.resultado_local = data['goles_local']
    partido.resultado_visitante = data['goles_visitante']
    partido.jugado = True
    
    # Calcular puntos para todos los pronósticos de este partido
    pronosticos = Pronostico.query.filter_by(partido_id=partido_id).all()
    for pronostico in pronosticos:
        pronostico.puntos = calcular_puntos(
            pronostico.goles_local, pronostico.goles_visitante,
            partido.resultado_local, partido.resultado_visitante,
            partido.fase
        )
    
    db.session.commit()
    return jsonify({'mensaje': 'Resultado actualizado y puntos calculados'})


# ============ USUARIOS ============
@api_bp.route('/usuarios', methods=['GET'])
@login_required
def obtener_usuarios():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    usuarios = Usuario.query.all()
    return jsonify([u.to_dict() for u in usuarios])


# ============ PRONÓSTICOS ============
@api_bp.route('/pronosticos', methods=['POST'])
@login_required
def crear_pronostico():
    data = request.json
    
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
    if usuario_id != current_user.id and not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    pronosticos = Pronostico.query.filter_by(usuario_id=usuario_id).all()
    return jsonify([{
        'partido_id': p.partido_id,
        'goles_local': p.goles_local,
        'goles_visitante': p.goles_visitante,
        'puntos': p.puntos
    } for p in pronosticos])


# ============ TABLA DE POSICIONES AVANZADA ============
@api_bp.route('/tabla-posiciones-avanzada', methods=['GET'])
def tabla_posiciones_avanzada():
    usuarios = Usuario.query.all()
    tabla = []
    
    for usuario in usuarios:
        pronosticos = Pronostico.query.filter_by(usuario_id=usuario.id).all()
        total_puntos = 0
        aciertos_exactos = 0
        partidos_acertados = 0
        diferencia_goles_total = 0
        
        for p in pronosticos:
            partido = Partido.query.get(p.partido_id)
            if partido and partido.jugado:
                total_puntos += p.puntos
                
                # Contar aciertos exactos (5 puntos o más con bonus)
                if p.puntos >= 5:
                    aciertos_exactos += 1
                
                # Contar partidos acertados (ganador o empate)
                if (p.goles_local - p.goles_visitante) == (partido.resultado_local - partido.resultado_visitante):
                    partidos_acertados += 1
                
                # Diferencia de goles
                diff_usuario = abs(p.goles_local - p.goles_visitante)
                diff_real = abs(partido.resultado_local - partido.resultado_visitante)
                diferencia_goles_total -= abs(diff_usuario - diff_real)
        
        tabla.append({
            'usuario_id': usuario.id,
            'nombre': usuario.nombre,
            'seleccion_favorita': usuario.seleccion_favorita,
            'puntos': total_puntos,
            'aciertos_exactos': aciertos_exactos,
            'partidos_acertados': partidos_acertados,
            'diferencia_goles': diferencia_goles_total
        })
    
    # Ordenar por puntos (mayor a menor)
    tabla.sort(key=lambda x: x['puntos'], reverse=True)
    
    for i, item in enumerate(tabla):
        item['posicion'] = i + 1
    
    return jsonify(tabla)


# ============ TABLA DE POSICIONES SIMPLE ============
@api_bp.route('/tabla-posiciones', methods=['GET'])
def tabla_posiciones():
    usuarios = Usuario.query.all()
    tabla = []
    
    for usuario in usuarios:
        total_puntos = db.session.query(db.func.sum(Pronostico.puntos)).filter_by(usuario_id=usuario.id).scalar() or 0
        tabla.append({
            'usuario_id': usuario.id,
            'nombre': usuario.nombre,
            'puntos': total_puntos
        })
    
    tabla.sort(key=lambda x: x['puntos'], reverse=True)
    return jsonify(tabla)


# ============ CARGAR DATOS INICIALES ============
@api_bp.route('/cargar-datos-iniciales', methods=['POST'])
def cargar_datos_iniciales():
    if Partido.query.first():
        return jsonify({'mensaje': 'Los datos ya existen'})
    
    partidos_ejemplo = [
        # Grupo A
        {'local': 'México', 'visitante': 'Canadá', 'fecha': datetime(2026, 6, 12, 15, 0), 'grupo': 'A', 'fase': 'grupos'},
        {'local': 'Argentina', 'visitante': 'Chile', 'fecha': datetime(2026, 6, 13, 18, 0), 'grupo': 'A', 'fase': 'grupos'},
        {'local': 'México', 'visitante': 'Argentina', 'fecha': datetime(2026, 6, 18, 21, 0), 'grupo': 'A', 'fase': 'grupos'},
        {'local': 'Canadá', 'visitante': 'Chile', 'fecha': datetime(2026, 6, 19, 15, 0), 'grupo': 'A', 'fase': 'grupos'},
        {'local': 'Argentina', 'visitante': 'Canadá', 'fecha': datetime(2026, 6, 24, 15, 0), 'grupo': 'A', 'fase': 'grupos'},
        {'local': 'Chile', 'visitante': 'México', 'fecha': datetime(2026, 6, 24, 15, 0), 'grupo': 'A', 'fase': 'grupos'},
        # Grupo B
        {'local': 'España', 'visitante': 'Brasil', 'fecha': datetime(2026, 6, 12, 21, 0), 'grupo': 'B', 'fase': 'grupos'},
        {'local': 'Alemania', 'visitante': 'Japón', 'fecha': datetime(2026, 6, 13, 12, 0), 'grupo': 'B', 'fase': 'grupos'},
        {'local': 'Brasil', 'visitante': 'Alemania', 'fecha': datetime(2026, 6, 17, 18, 0), 'grupo': 'B', 'fase': 'grupos'},
        {'local': 'Japón', 'visitante': 'España', 'fecha': datetime(2026, 6, 18, 12, 0), 'grupo': 'B', 'fase': 'grupos'},
        {'local': 'España', 'visitante': 'Alemania', 'fecha': datetime(2026, 6, 23, 21, 0), 'grupo': 'B', 'fase': 'grupos'},
        {'local': 'Brasil', 'visitante': 'Japón', 'fecha': datetime(2026, 6, 23, 21, 0), 'grupo': 'B', 'fase': 'grupos'},
    ]
    
    for p in partidos_ejemplo:
        partido = Partido(
            equipo_local=p['local'],
            equipo_visitante=p['visitante'],
            fecha=p['fecha'],
            grupo=p['grupo'],
            fase=p['fase']
        )
        db.session.add(partido)
    
    # Agregar un usuario de ejemplo
    usuario = Usuario(
        nombre="Jugador Ejemplo",
        email="ejemplo@quiniela.com",
        seleccion_favorita="esp"
    )
    usuario.set_password('ejemplo123')
    db.session.add(usuario)
    
    db.session.commit()
    return jsonify({'mensaje': f'Cargados {len(partidos_ejemplo)} partidos'})