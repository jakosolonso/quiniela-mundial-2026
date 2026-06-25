from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func, case
from database import db
from models import (
    Partido,
    Usuario,
    Pronostico,
    ConfiguracionTiempo,
    PronosticoExtra
)
from datetime import datetime
import re

api_bp = Blueprint('api', __name__)

# CONFIGURACIÓN DE FASES ELIMINATORIAS

GRUPOS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']

# Mapeo de grupos por fase (para los cruces de dieciseisavos según fixture de la FIFA)
DIECISEISAVOS_CRUCES = [
    (73, ('2° Grupo A', '2° Grupo B')),
    (74, ('1° Grupo E', '3° Grupo A/B/C/D/F')),
    (75, ('1° Grupo F', '2° Grupo C')),
    (76, ('1° Grupo C', '2° Grupo F')),
    (77, ('1° Grupo I', '3° Grupo C/D/F/G/H')),
    (78, ('2° Grupo E', '2° Grupo I')),
    (79, ('1° Grupo A', '3° Grupo C/E/F/H/I')),
    (80, ('1° Grupo L', '3° Grupo E/H/I/J/K')),
    (81, ('1° Grupo D', '3° Grupo B/E/F/I/J')),
    (82, ('1° Grupo G', '3° Grupo A/E/H/I/J')),
    (83, ('2° Grupo K', '2° Grupo L')),
    (84, ('1° Grupo H', '2° Grupo J')),
    (85, ('1° Grupo B', '3° Grupo E/F/G/I/J')),
    (86, ('1° Grupo J', '2° Grupo H')),
    (87, ('1° Grupo K', '3° Grupo D/E/I/J/L')),
    (88, ('2° Grupo D', '2° Grupo G')),
]

OCTAVOS_CRUCES = [
    (89, (74, 77)),
    (90, (73, 75)),
    (91, (76, 78)),
    (92, (79, 80)),
    (93, (83, 84)),
    (94, (81, 82)),
    (95, (86, 88)),
    (96, (85, 87)),
]

CUARTOS_CRUCES = [
    (97, (89, 90)),
    (98, (93, 94)),
    (99, (91, 92)),
    (100, (95, 96)),
]

SEMIS_CRUCES = [
    (101, (97, 98)),
    (102, (99, 100)),
]

FINAL_CRUCE = (104, (101, 102))


def calcular_puntos(goles_local_p, goles_visitante_p,
                    goles_local_r, goles_visitante_r, fase):

    # Marcador exacto
    if goles_local_p == goles_local_r and goles_visitante_p == goles_visitante_r:
        puntos = 5

    else:
        puntos = 0

        # Resultado (local gana, empate o visitante gana)
        resultado_p = (
            1 if goles_local_p > goles_visitante_p
            else -1 if goles_local_p < goles_visitante_p
            else 0
        )

        resultado_r = (
            1 if goles_local_r > goles_visitante_r
            else -1 if goles_local_r < goles_visitante_r
            else 0
        )

        # Ganador o empate acertado
        if resultado_p == resultado_r:
            puntos = 3

            # Diferencia de goles exacta
            diferencia_p = goles_local_p - goles_visitante_p
            diferencia_r = goles_local_r - goles_visitante_r

            if diferencia_p == diferencia_r:
                puntos += 1

    return puntos

####################################################################

#  AUTENTICACION 
@api_bp.route('/registro', methods=['POST'])
def registro():
    data = request.json
    
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', data['email']):
        return jsonify({'error': 'Email inválido'}), 400
    
    existe = Usuario.query.filter_by(email=data['email']).first()
    if existe:
        return jsonify({'error': 'El email ya está registrado'}), 400
    
    if len(data['password']) < 6:
        return jsonify({'error': 'La contraseña debe tener al menos 6 caracteres'}), 400
    
    # Validar código de empleado (OBLIGATORIO)
    codigo_empleado = data.get('codigo_empleado', '').strip()
    if not codigo_empleado:
        return jsonify({'error': 'El código de empleado es obligatorio'}), 400
    
    usuario = Usuario(
        nombre=data['nombre'],
        email=data['email'],
        codigo_empleado=codigo_empleado,
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
    
    usuario.ultimo_acceso = datetime.utcnow()
    db.session.commit()
    login_user(usuario, remember=data.get('remember', False))
    
    return jsonify({
        'mensaje': 'Login exitoso',
        'usuario': usuario.to_dict()
    }), 200


@api_bp.route('/logout', methods=['POST'])
def logout():
    logout_user()
    return jsonify({'mensaje': 'Sesión cerrada'}), 200


@api_bp.route('/usuario-actual', methods=['GET'])
def usuario_actual():
    if not current_user.is_authenticated:
        return jsonify({'error': 'No autenticado'}), 401

    return jsonify({
        'id': current_user.id,
        'nombre': current_user.nombre,
        'email': current_user.email,
        'seleccion_favorita': current_user.seleccion_favorita,
        'es_admin': current_user.es_admin
    }), 200


#  SELECCIONES 
@api_bp.route('/selecciones', methods=['GET'])
def obtener_selecciones():
    selecciones = [
        {"codigo": "arg", "nombre": "Argentina", "bandera": "https://flagcdn.com/ar.svg"},
        {"codigo": "bra", "nombre": "Brasil", "bandera": "https://flagcdn.com/br.svg"},
        {"codigo": "fra", "nombre": "Francia", "bandera": "https://flagcdn.com/fr.svg"},
        {"codigo": "esp", "nombre": "España", "bandera": "https://flagcdn.com/es.svg"},
        {"codigo": "ger", "nombre": "Alemania", "bandera": "https://flagcdn.com/de.svg"},
        {"codigo": "eng", "nombre": "Inglaterra", "bandera": "https://flagcdn.com/gb-eng.svg"},
        {"codigo": "ita", "nombre": "Italia", "bandera": "https://flagcdn.com/it.svg"},
        {"codigo": "ned", "nombre": "Países Bajos", "bandera": "https://flagcdn.com/nl.svg"},
        {"codigo": "por", "nombre": "Portugal", "bandera": "https://flagcdn.com/pt.svg"},
        {"codigo": "uru", "nombre": "Uruguay", "bandera": "https://flagcdn.com/uy.svg"},
        {"codigo": "col", "nombre": "Colombia", "bandera": "https://flagcdn.com/co.svg"},
        {"codigo": "mex", "nombre": "México", "bandera": "https://flagcdn.com/mx.svg"},
        {"codigo": "usa", "nombre": "Estados Unidos", "bandera": "https://flagcdn.com/us.svg"},
        {"codigo": "can", "nombre": "Canadá", "bandera": "https://flagcdn.com/ca.svg"},
        {"codigo": "jpn", "nombre": "Japón", "bandera": "https://flagcdn.com/jp.svg"},
        {"codigo": "kor", "nombre": "Corea del Sur", "bandera": "https://flagcdn.com/kr.svg"},
        {"codigo": "mar", "nombre": "Marruecos", "bandera": "https://flagcdn.com/ma.svg"},
        {"codigo": "sen", "nombre": "Senegal", "bandera": "https://flagcdn.com/sn.svg"},
        {"codigo": "cro", "nombre": "Croacia", "bandera": "https://flagcdn.com/hr.svg"},
        {"codigo": "bel", "nombre": "Bélgica", "bandera": "https://flagcdn.com/be.svg"},
        {"codigo": "sui", "nombre": "Suiza", "bandera": "https://flagcdn.com/ch.svg"},
        {"codigo": "ecu", "nombre": "Ecuador", "bandera": "https://flagcdn.com/ec.svg"},
        {"codigo": "par", "nombre": "Paraguay", "bandera": "https://flagcdn.com/py.svg"},
        {"codigo": "qat", "nombre": "Qatar", "bandera": "https://flagcdn.com/qa.svg"},
        {"codigo": "egy", "nombre": "Egipto", "bandera": "https://flagcdn.com/eg.svg"},
        {"codigo": "aus", "nombre": "Australia", "bandera": "https://flagcdn.com/au.svg"},
        {"codigo": "swe", "nombre": "Suecia", "bandera": "https://flagcdn.com/se.svg"},
        {"codigo": "tun", "nombre": "Túnez", "bandera": "https://flagcdn.com/tn.svg"},
        {"codigo": "nor", "nombre": "Noruega", "bandera": "https://flagcdn.com/no.svg"},
        {"codigo": "sco", "nombre": "Escocia", "bandera": "https://flagcdn.com/gb-sct.svg"},
        {"codigo": "gha", "nombre": "Ghana", "bandera": "https://flagcdn.com/gh.svg"},
        {"codigo": "pan", "nombre": "Panamá", "bandera": "https://flagcdn.com/pa.svg"},
        {"codigo": "alg", "nombre": "Argelia", "bandera": "https://flagcdn.com/dz.svg"},
        {"codigo": "aut", "nombre": "Austria", "bandera": "https://flagcdn.com/at.svg"},
        {"codigo": "jor", "nombre": "Jordania", "bandera": "https://flagcdn.com/jo.svg"},
        {"codigo": "irak", "nombre": "Irak", "bandera": "https://flagcdn.com/iq.svg"},
        {"codigo": "nzl", "nombre": "Nueva Zelanda", "bandera": "https://flagcdn.com/nz.svg"},
        {"codigo": "civ", "nombre": "Costa de Marfil", "bandera": "https://flagcdn.com/ci.svg"},
        {"codigo": "cam", "nombre": "Camerún", "bandera": "https://flagcdn.com/cm.svg"},
        {"codigo": "rsa", "nombre": "Sudáfrica", "bandera": "https://flagcdn.com/za.svg"},
        {"codigo": "uzb", "nombre": "Uzbekistán", "bandera": "https://flagcdn.com/uz.svg"},
        {"codigo": "cod", "nombre": "RD Congo", "bandera": "https://flagcdn.com/cd.svg"},
        {"codigo": "bih", "nombre": "Bosnia", "bandera": "https://flagcdn.com/ba.svg"},
        {"codigo": "tur", "nombre": "Turquía", "bandera": "https://flagcdn.com/tr.svg"},
        {"codigo": "cze", "nombre": "República Checa", "bandera": "https://flagcdn.com/cz.svg"},
    ]
    return jsonify(selecciones)


#  PARTIDOS 
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
    
    pronosticos = Pronostico.query.filter_by(partido_id=partido_id).all()
    for pronostico in pronosticos:
        pronostico.puntos = calcular_puntos(
            pronostico.goles_local, pronostico.goles_visitante,
            partido.resultado_local, partido.resultado_visitante,
            partido.fase
        )
    
    db.session.commit()
    return jsonify({'mensaje': 'Resultado actualizado y puntos calculados'})


#  USUARIOS 
@api_bp.route('/usuarios', methods=['GET'])
@login_required
def obtener_usuarios():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    usuarios = Usuario.query.all()
    return jsonify([u.to_dict() for u in usuarios])


#  PRONOSTICOS 
@api_bp.route('/pronosticos', methods=['POST'])
@login_required
def crear_pronostico():
    data = request.json
    
    partido = Partido.query.get(data['partido_id'])
    if not partido:
        return jsonify({'error': 'Partido no encontrado'}), 404
    
    if not puede_pronosticar(partido.fase):
        config = ConfiguracionTiempo.query.filter_by(fase=partido.fase).first()
        fecha_str = config.fecha_limite.strftime('%d/%m/%Y %H:%M')
        return jsonify({
            'error': f'El plazo para pronósticos de {partido.fase} cerró el {fecha_str}'
        }), 403
    
    if partido.jugado:
        return jsonify({'error': 'El partido ya finalizó'}), 403
    
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


#  TABLA DE POSICIONES 
@api_bp.route('/tabla-posiciones-avanzada', methods=['GET'])
def tabla_posiciones_avanzada():
    # ---------------------------------------------------------------
    # Una sola query con JOIN + agregaciones SQL.
    # Antes: 1 + N + (N*M) queries (~6000 queries con 100 usuarios).
    # Ahora: 1 query total. Tiempo: <200ms.
    # ---------------------------------------------------------------

    diff_pronostico = (Pronostico.goles_local - Pronostico.goles_visitante)
    diff_real_col   = (Partido.resultado_local - Partido.resultado_visitante)

    penalizacion_diff = func.abs(
        func.abs(Pronostico.goles_local - Pronostico.goles_visitante) -
        func.abs(Partido.resultado_local - Partido.resultado_visitante)
    )

    filas = (
        db.session.query(
            Usuario.id,
            Usuario.nombre,
            Usuario.seleccion_favorita,
            func.coalesce(
                func.sum(case((Partido.jugado == True, Pronostico.puntos), else_=0)), 0
            ).label('total_puntos'),
            func.coalesce(
                func.sum(case(
                    ((Partido.jugado == True) &
                     (Pronostico.goles_local == Partido.resultado_local) &
                     (Pronostico.goles_visitante == Partido.resultado_visitante), 1),
                    else_=0
                )), 0
            ).label('aciertos_exactos'),
            func.coalesce(
                func.sum(case(
                    ((Partido.jugado == True) & (diff_pronostico == diff_real_col), 1),
                    else_=0
                )), 0
            ).label('partidos_acertados'),
            func.coalesce(
                func.sum(case((Partido.jugado == True, -penalizacion_diff), else_=0)), 0
            ).label('diferencia_goles'),
        )
        .outerjoin(Pronostico, Pronostico.usuario_id == Usuario.id)
        .outerjoin(Partido,    Partido.id == Pronostico.partido_id)
        .filter(Usuario.es_activo == True)
        .group_by(Usuario.id, Usuario.nombre, Usuario.seleccion_favorita)
        .order_by(
            db.text('total_puntos DESC'),
            db.text('aciertos_exactos DESC'),
            db.text('partidos_acertados DESC'),
            db.text('diferencia_goles DESC'),
        )
        .all()
    )

    tabla = [
        {
            'posicion':           i + 1,
            'usuario_id':         f.id,
            'nombre':             f.nombre,
            'seleccion_favorita': f.seleccion_favorita,
            'puntos':             int(f.total_puntos),
            'aciertos_exactos':   int(f.aciertos_exactos),
            'partidos_acertados': int(f.partidos_acertados),
            'diferencia_goles':   int(f.diferencia_goles),
        }
        for i, f in enumerate(filas)
    ]

    return jsonify(tabla)


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


#  CARGAR DATOS INICIALES 
@api_bp.route('/cargar-datos-iniciales', methods=['POST'])
def cargar_datos_iniciales():
    if Partido.query.first():
        return jsonify({'mensaje': 'Los datos ya existen'})
    
    partidos = [
        {'local': 'México', 'visitante': 'Sudáfrica', 'fecha': datetime(2026, 6, 11, 15, 0), 'grupo': 'A', 'fase': 'grupos'},
        {'local': 'Corea del Sur', 'visitante': 'República Checa', 'fecha': datetime(2026, 6, 11, 22, 0), 'grupo': 'A', 'fase': 'grupos'},
        {'local': 'República Checa', 'visitante': 'Sudáfrica', 'fecha': datetime(2026, 6, 18, 12, 0), 'grupo': 'A', 'fase': 'grupos'},
        {'local': 'México', 'visitante': 'Corea del Sur', 'fecha': datetime(2026, 6, 18, 21, 0), 'grupo': 'A', 'fase': 'grupos'},
        {'local': 'México', 'visitante': 'República Checa', 'fecha': datetime(2026, 6, 24, 21, 0), 'grupo': 'A', 'fase': 'grupos'},
        {'local': 'Sudáfrica', 'visitante': 'Corea del Sur', 'fecha': datetime(2026, 6, 24, 21, 0), 'grupo': 'A', 'fase': 'grupos'},
        {'local': 'Canadá', 'visitante': 'Bosnia y Herzegovina', 'fecha': datetime(2026, 6, 12, 15, 0), 'grupo': 'B', 'fase': 'grupos'},
        {'local': 'Qatar', 'visitante': 'Suiza', 'fecha': datetime(2026, 6, 13, 14, 0), 'grupo': 'B', 'fase': 'grupos'},
        {'local': 'Suiza', 'visitante': 'Bosnia y Herzegovina', 'fecha': datetime(2026, 6, 18, 14, 0), 'grupo': 'B', 'fase': 'grupos'},
        {'local': 'Canadá', 'visitante': 'Qatar', 'fecha': datetime(2026, 6, 18, 17, 0), 'grupo': 'B', 'fase': 'grupos'},
        {'local': 'Canadá', 'visitante': 'Suiza', 'fecha': datetime(2026, 6, 24, 14, 0), 'grupo': 'B', 'fase': 'grupos'},
        {'local': 'Bosnia y Herzegovina', 'visitante': 'Qatar', 'fecha': datetime(2026, 6, 24, 14, 0), 'grupo': 'B', 'fase': 'grupos'},
        {'local': 'Brasil', 'visitante': 'Marruecos', 'fecha': datetime(2026, 6, 13, 17, 0), 'grupo': 'C', 'fase': 'grupos'},
        {'local': 'Haití', 'visitante': 'Escocia', 'fecha': datetime(2026, 6, 13, 20, 0), 'grupo': 'C', 'fase': 'grupos'},
        {'local': 'Escocia', 'visitante': 'Marruecos', 'fecha': datetime(2026, 6, 19, 17, 0), 'grupo': 'C', 'fase': 'grupos'},
        {'local': 'Brasil', 'visitante': 'Haití', 'fecha': datetime(2026, 6, 19, 20, 0), 'grupo': 'C', 'fase': 'grupos'},
        {'local': 'Escocia', 'visitante': 'Brasil', 'fecha': datetime(2026, 6, 24, 17, 0), 'grupo': 'C', 'fase': 'grupos'},
        {'local': 'Marruecos', 'visitante': 'Haití', 'fecha': datetime(2026, 6, 24, 17, 0), 'grupo': 'C', 'fase': 'grupos'},
        {'local': 'Estados Unidos', 'visitante': 'Paraguay', 'fecha': datetime(2026, 6, 12, 20, 0), 'grupo': 'D', 'fase': 'grupos'},
        {'local': 'Australia', 'visitante': 'Turquía', 'fecha': datetime(2026, 6, 13, 23, 0), 'grupo': 'D', 'fase': 'grupos'},
        {'local': 'Turquía', 'visitante': 'Paraguay', 'fecha': datetime(2026, 6, 19, 23, 0), 'grupo': 'D', 'fase': 'grupos'},
        {'local': 'Estados Unidos', 'visitante': 'Australia', 'fecha': datetime(2026, 6, 19, 14, 0), 'grupo': 'D', 'fase': 'grupos'},
        {'local': 'Estados Unidos', 'visitante': 'Turquía', 'fecha': datetime(2026, 6, 25, 21, 0), 'grupo': 'D', 'fase': 'grupos'},
        {'local': 'Paraguay', 'visitante': 'Australia', 'fecha': datetime(2026, 6, 25, 21, 0), 'grupo': 'D', 'fase': 'grupos'},
        {'local': 'Alemania', 'visitante': 'Curazao', 'fecha': datetime(2026, 6, 14, 12, 0), 'grupo': 'E', 'fase': 'grupos'},
        {'local': 'Costa de Marfil', 'visitante': 'Ecuador', 'fecha': datetime(2026, 6, 14, 18, 0), 'grupo': 'E', 'fase': 'grupos'},
        {'local': 'Alemania', 'visitante': 'Costa de Marfil', 'fecha': datetime(2026, 6, 20, 15, 0), 'grupo': 'E', 'fase': 'grupos'},
        {'local': 'Ecuador', 'visitante': 'Curazao', 'fecha': datetime(2026, 6, 20, 19, 0), 'grupo': 'E', 'fase': 'grupos'},
        {'local': 'Ecuador', 'visitante': 'Alemania', 'fecha': datetime(2026, 6, 25, 15, 0), 'grupo': 'E', 'fase': 'grupos'},
        {'local': 'Curazao', 'visitante': 'Costa de Marfil', 'fecha': datetime(2026, 6, 25, 15, 0), 'grupo': 'E', 'fase': 'grupos'},
        {'local': 'Países Bajos', 'visitante': 'Japón', 'fecha': datetime(2026, 6, 14, 15, 0), 'grupo': 'F', 'fase': 'grupos'},
        {'local': 'Suecia', 'visitante': 'Túnez', 'fecha': datetime(2026, 6, 14, 21, 0), 'grupo': 'F', 'fase': 'grupos'},
        {'local': 'Países Bajos', 'visitante': 'Suecia', 'fecha': datetime(2026, 6, 20, 12, 0), 'grupo': 'F', 'fase': 'grupos'},
        {'local': 'Túnez', 'visitante': 'Japón', 'fecha': datetime(2026, 6, 20, 23, 0), 'grupo': 'F', 'fase': 'grupos'},
        {'local': 'Japón', 'visitante': 'Suecia', 'fecha': datetime(2026, 6, 25, 18, 0), 'grupo': 'F', 'fase': 'grupos'},
        {'local': 'Túnez', 'visitante': 'Países Bajos', 'fecha': datetime(2026, 6, 25, 18, 0), 'grupo': 'F', 'fase': 'grupos'},
        {'local': 'Bélgica', 'visitante': 'Egipto', 'fecha': datetime(2026, 6, 15, 14, 0), 'grupo': 'G', 'fase': 'grupos'},
        {'local': 'Irán', 'visitante': 'Nueva Zelanda', 'fecha': datetime(2026, 6, 15, 20, 0), 'grupo': 'G', 'fase': 'grupos'},
        {'local': 'Bélgica', 'visitante': 'Irán', 'fecha': datetime(2026, 6, 21, 14, 0), 'grupo': 'G', 'fase': 'grupos'},
        {'local': 'Nueva Zelanda', 'visitante': 'Egipto', 'fecha': datetime(2026, 6, 21, 20, 0), 'grupo': 'G', 'fase': 'grupos'},
        {'local': 'Egipto', 'visitante': 'Irán', 'fecha': datetime(2026, 6, 26, 22, 0), 'grupo': 'G', 'fase': 'grupos'},
        {'local': 'Nueva Zelanda', 'visitante': 'Bélgica', 'fecha': datetime(2026, 6, 26, 22, 0), 'grupo': 'G', 'fase': 'grupos'},
        {'local': 'España', 'visitante': 'Cabo Verde', 'fecha': datetime(2026, 6, 15, 11, 0), 'grupo': 'H', 'fase': 'grupos'},
        {'local': 'Arabia Saudita', 'visitante': 'Uruguay', 'fecha': datetime(2026, 6, 15, 17, 0), 'grupo': 'H', 'fase': 'grupos'},
        {'local': 'España', 'visitante': 'Arabia Saudita', 'fecha': datetime(2026, 6, 21, 11, 0), 'grupo': 'H', 'fase': 'grupos'},
        {'local': 'Uruguay', 'visitante': 'Cabo Verde', 'fecha': datetime(2026, 6, 21, 17, 0), 'grupo': 'H', 'fase': 'grupos'},
        {'local': 'Cabo Verde', 'visitante': 'Arabia Saudita', 'fecha': datetime(2026, 6, 26, 19, 0), 'grupo': 'H', 'fase': 'grupos'},
        {'local': 'Uruguay', 'visitante': 'España', 'fecha': datetime(2026, 6, 26, 19, 0), 'grupo': 'H', 'fase': 'grupos'},
        {'local': 'Francia', 'visitante': 'Senegal', 'fecha': datetime(2026, 6, 16, 14, 0), 'grupo': 'I', 'fase': 'grupos'},
        {'local': 'Irak', 'visitante': 'Noruega', 'fecha': datetime(2026, 6, 16, 17, 0), 'grupo': 'I', 'fase': 'grupos'},
        {'local': 'Francia', 'visitante': 'Irak', 'fecha': datetime(2026, 6, 22, 17, 0), 'grupo': 'I', 'fase': 'grupos'},
        {'local': 'Noruega', 'visitante': 'Senegal', 'fecha': datetime(2026, 6, 22, 19, 0), 'grupo': 'I', 'fase': 'grupos'},
        {'local': 'Noruega', 'visitante': 'Francia', 'fecha': datetime(2026, 6, 26, 14, 0), 'grupo': 'I', 'fase': 'grupos'},
        {'local': 'Senegal', 'visitante': 'Irak', 'fecha': datetime(2026, 6, 26, 14, 0), 'grupo': 'I', 'fase': 'grupos'},
        {'local': 'Argentina', 'visitante': 'Argelia', 'fecha': datetime(2026, 6, 16, 20, 0), 'grupo': 'J', 'fase': 'grupos'},
        {'local': 'Austria', 'visitante': 'Jordania', 'fecha': datetime(2026, 6, 16, 23, 0), 'grupo': 'J', 'fase': 'grupos'},
        {'local': 'Argentina', 'visitante': 'Austria', 'fecha': datetime(2026, 6, 22, 12, 0), 'grupo': 'J', 'fase': 'grupos'},
        {'local': 'Jordania', 'visitante': 'Argelia', 'fecha': datetime(2026, 6, 22, 22, 0), 'grupo': 'J', 'fase': 'grupos'},
        {'local': 'Argelia', 'visitante': 'Austria', 'fecha': datetime(2026, 6, 27, 21, 0), 'grupo': 'J', 'fase': 'grupos'},
        {'local': 'Jordania', 'visitante': 'Argentina', 'fecha': datetime(2026, 6, 27, 21, 0), 'grupo': 'J', 'fase': 'grupos'},
        {'local': 'Portugal', 'visitante': 'RD Congo', 'fecha': datetime(2026, 6, 17, 12, 0), 'grupo': 'K', 'fase': 'grupos'},
        {'local': 'Uzbekistán', 'visitante': 'Colombia', 'fecha': datetime(2026, 6, 17, 21, 0), 'grupo': 'K', 'fase': 'grupos'},
        {'local': 'Portugal', 'visitante': 'Uzbekistán', 'fecha': datetime(2026, 6, 23, 12, 0), 'grupo': 'K', 'fase': 'grupos'},
        {'local': 'Colombia', 'visitante': 'RD Congo', 'fecha': datetime(2026, 6, 23, 21, 0), 'grupo': 'K', 'fase': 'grupos'},
        {'local': 'Colombia', 'visitante': 'Portugal', 'fecha': datetime(2026, 6, 27, 18, 30), 'grupo': 'K', 'fase': 'grupos'},
        {'local': 'RD Congo', 'visitante': 'Uzbekistán', 'fecha': datetime(2026, 6, 27, 18, 30), 'grupo': 'K', 'fase': 'grupos'},
        {'local': 'Inglaterra', 'visitante': 'Croacia', 'fecha': datetime(2026, 6, 17, 15, 0), 'grupo': 'L', 'fase': 'grupos'},
        {'local': 'Ghana', 'visitante': 'Panamá', 'fecha': datetime(2026, 6, 17, 18, 0), 'grupo': 'L', 'fase': 'grupos'},
        {'local': 'Inglaterra', 'visitante': 'Ghana', 'fecha': datetime(2026, 6, 23, 16, 0), 'grupo': 'L', 'fase': 'grupos'},
        {'local': 'Panamá', 'visitante': 'Croacia', 'fecha': datetime(2026, 6, 23, 18, 0), 'grupo': 'L', 'fase': 'grupos'},
        {'local': 'Panamá', 'visitante': 'Inglaterra', 'fecha': datetime(2026, 6, 27, 16, 0), 'grupo': 'L', 'fase': 'grupos'},
        {'local': 'Croacia', 'visitante': 'Ghana', 'fecha': datetime(2026, 6, 27, 16, 0), 'grupo': 'L', 'fase': 'grupos'},
    ]
    
    for p in partidos:
        partido = Partido(
            equipo_local=p['local'],
            equipo_visitante=p['visitante'],
            fecha=p['fecha'],
            grupo=p['grupo'],
            fase=p['fase']
        )
        db.session.add(partido)
    
    db.session.commit()
    return jsonify({'mensaje': f'Cargados {len(partidos)} partidos del Mundial 2026'})


#  ADMINISTRACION 
@api_bp.route('/admin/estado', methods=['GET'])
@login_required
def estado_sistema():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    import sys
    scheduler_info = None
    for module in sys.modules.values():
        if hasattr(module, 'scheduler'):
            scheduler_info = module.scheduler
            break
    
    jobs = []
    if scheduler_info:
        for job in scheduler_info.get_jobs():
            jobs.append({
                'id': job.id,
                'next_run': str(job.next_run_time) if job.next_run_time else None
            })
    
    return jsonify({
        'status': 'activo',
        'tareas_programadas': jobs,
        'intervalo': '10 minutos'
    })


@api_bp.route('/admin/verificar-scheduler', methods=['GET'])
@login_required
def verificar_scheduler():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    import sys
    import inspect
    
    info = {
        'scheduler_activo': False,
        'jobs': [],
        'mensaje': ''
    }
    
    for module_name, module in sys.modules.items():
        if 'app' in module_name or 'scheduler' in module_name:
            for name, obj in inspect.getmembers(module):
                if 'scheduler' in name.lower() and hasattr(obj, 'get_jobs'):
                    info['scheduler_activo'] = True
                    try:
                        for job in obj.get_jobs():
                            info['jobs'].append({
                                'id': job.id,
                                'next_run': str(job.next_run_time) if job.next_run_time else 'No programado'
                            })
                        info['mensaje'] = f"Scheduler encontrado en {module_name}"
                    except Exception as e:
                        info['mensaje'] = f"Error al obtener jobs: {str(e)}"
    
    if not info['scheduler_activo']:
        info['mensaje'] = 'No se encontró el scheduler activo'
    
    return jsonify(info)


def puede_pronosticar(fase):
    """Verifica si aún se puede hacer pronósticos para una fase"""
    config = ConfiguracionTiempo.query.filter_by(fase=fase).first()
    if not config:
        return True
    
    # Si el admin cerró manualmente, no se puede pronosticar
    if config.cerrado:
        return False
    
    # Si hay fecha límite y ya paso, no se puede
    if config.fecha_limite:
        ahora = datetime.utcnow()
        if ahora >= config.fecha_limite:
            return False
    
    return True


@api_bp.route('/admin/configurar-tiempo', methods=['GET'])
@login_required
def admin_obtener_configuracion():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    configs = ConfiguracionTiempo.query.all()
    result = []
    for c in configs:
        # Asegurar que cerrado se lea correctamente
        cerrado_valor = False
        if hasattr(c, 'cerrado') and c.cerrado is not None:
            cerrado_valor = c.cerrado
        
        result.append({
            'fase': c.fase,
            'fecha_limite': c.fecha_limite.isoformat() if c.fecha_limite else None,
            'cerrado': cerrado_valor
        })
    
    return jsonify(result)


@api_bp.route('/admin/configurar-tiempo', methods=['POST'])
@login_required
def admin_guardar_configuracion():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.json
    fase = data.get('fase')
    fecha_limite = datetime.fromisoformat(data.get('fecha_limite'))
    
    config = ConfiguracionTiempo.query.filter_by(fase=fase).first()
    if config:
        config.fecha_limite = fecha_limite
    else:
        config = ConfiguracionTiempo(fase=fase, fecha_limite=fecha_limite)
        db.session.add(config)
    
    db.session.commit()
    return jsonify({'mensaje': f'Configuración guardada para {fase}'})


@api_bp.route('/admin/verificar-tiempo', methods=['GET'])
def verificar_tiempo():
    fase = request.args.get('fase', 'grupos')
    puede = puede_pronosticar(fase)
    config = ConfiguracionTiempo.query.filter_by(fase=fase).first()
    return jsonify({
        'fase': fase,
        'puede_pronosticar': puede,
        'fecha_limite': config.fecha_limite.isoformat() if config else None
    })


@api_bp.route('/fecha-limite-activa', methods=['GET'])
def fecha_limite_activa():
    fases_orden = ['grupos', 'dieciseisavos', 'octavos', 'cuartos', 'semis', 'final']
    fases_nombres = {
        'grupos': 'Fase de Grupos',
        'dieciseisavos': 'Dieciseisavos de Final',
        'octavos': 'Octavos de Final',
        'cuartos': 'Cuartos de Final',
        'semis': 'Semifinales',
        'final': 'Final'
    }
    
    configs = ConfiguracionTiempo.query.all()
    config_dict = {c.fase: c.fecha_limite for c in configs}
    ahora = datetime.utcnow()
    
    for fase in fases_orden:
        if fase in config_dict:
            fecha_limite = config_dict[fase]
            if ahora < fecha_limite:
                dias_restantes = (fecha_limite - ahora).days
                return jsonify({
                    'fase': fase,
                    'nombre_fase': fases_nombres[fase],
                    'fecha_limite': fecha_limite.isoformat(),
                    'dias_restantes': dias_restantes,
                    'activo': True
                })
    
    return jsonify({
        'activo': False,
        'mensaje': 'Todos los plazos de pronósticos han cerrado'
    })


#  ADMIN - PARTIDOS 
@api_bp.route('/admin/stats', methods=['GET'])
@login_required
def admin_stats():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    total_usuarios = Usuario.query.count()
    total_partidos = Partido.query.count()
    partidos_jugados = Partido.query.filter_by(jugado=True).count()
    partidos_pendientes = total_partidos - partidos_jugados
    
    return jsonify({
        'total_usuarios': total_usuarios,
        'total_partidos': total_partidos,
        'partidos_jugados': partidos_jugados,
        'partidos_pendientes': partidos_pendientes
    })


@api_bp.route('/admin/partidos', methods=['GET'])
@login_required
def admin_partidos():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    partidos = Partido.query.order_by(Partido.fecha).all()
    return jsonify([{
        'id': p.id,
        'equipo_local': p.equipo_local,
        'equipo_visitante': p.equipo_visitante,
        'fecha': p.fecha.isoformat(),
        'grupo': p.grupo,
        'resultado_local': p.resultado_local,
        'resultado_visitante': p.resultado_visitante,
        'jugado': p.jugado
    } for p in partidos])


@api_bp.route('/admin/usuarios', methods=['GET'])
@login_required
def admin_usuarios():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    usuarios = Usuario.query.all()
    return jsonify([{
        'id': u.id,
        'nombre': u.nombre,
        'email': u.email,
        'seleccion_favorita': u.seleccion_favorita,
        'fecha_registro': u.fecha_registro.isoformat(),
        'es_admin': u.es_admin
    } for u in usuarios])


@api_bp.route('/admin/ejecutar-ahora', methods=['POST'])
@login_required
def admin_ejecutar_ahora():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403

    from resultados_service import actualizar_resultados_en_db
    import threading
    from flask import current_app

    app = current_app._get_current_object()

    def ejecutar_con_contexto():
        with app.app_context():
            actualizar_resultados_en_db()

    thread = threading.Thread(target=ejecutar_con_contexto)
    thread.daemon = True
    thread.start()

    return jsonify({'mensaje': 'Actualización iniciada. Revisa los logs.'})


@api_bp.route('/admin/simular-resultados', methods=['POST'])
@login_required
def admin_simular_resultados():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    import random
    
    # Simular partidos PENDIENTES (no jugados) de CUALQUIER fase
    partidos = Partido.query.filter_by(jugado=False).all()
    actualizados = 0
    
    for partido in partidos:
        goles_local = random.randint(0, 4)
        goles_visitante = random.randint(0, 4)
        
        partido.resultado_local = goles_local
        partido.resultado_visitante = goles_visitante
        partido.jugado = True
        actualizados += 1
        
        # Calcular puntos para los pronósticos
        pronosticos = Pronostico.query.filter_by(partido_id=partido.id).all()
        for pronostico in pronosticos:
            pronostico.puntos = calcular_puntos(
                pronostico.goles_local, pronostico.goles_visitante,
                goles_local, goles_visitante,
                partido.fase
            )
    
    db.session.commit()
    return jsonify({'mensaje': f'Se simularon {actualizados} resultados.'})


@api_bp.route('/admin/reiniciar-partidos', methods=['POST'])
@login_required
def admin_reiniciar_partidos():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    Pronostico.query.delete()
    
    partidos = Partido.query.all()
    for partido in partidos:
        partido.resultado_local = None
        partido.resultado_visitante = None
        partido.jugado = False
    
    db.session.commit()
    return jsonify({'mensaje': 'Todos los partidos y pronósticos han sido reiniciados.'})

#  GENERACION MANUAL DE FASES ELIMINATORIAS 

@api_bp.route('/admin/generar-dieciseisavos', methods=['POST'])
@login_required
def admin_generar_dieciseisavos():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        from fases_service import generar_dieciseisavos
        resultado = generar_dieciseisavos()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/admin/generar-octavos', methods=['POST'])
@login_required
def admin_generar_octavos():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        from fases_service import generar_octavos
        resultado = generar_octavos()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/admin/generar-cuartos', methods=['POST'])
@login_required
def admin_generar_cuartos():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        from fases_service import generar_cuartos
        resultado = generar_cuartos()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/admin/generar-semis', methods=['POST'])
@login_required
def admin_generar_semis():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        from fases_service import generar_semis
        resultado = generar_semis()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/admin/generar-final', methods=['POST'])
@login_required
def admin_generar_final():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        from fases_service import generar_final
        resultado = generar_final()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    
@api_bp.route('/admin/borrar-fase/<fase>', methods=['POST'])
@login_required
def admin_borrar_fase(fase):
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    from fases_service import borrar_fase
    resultado = borrar_fase(fase)
    return jsonify(resultado)


@api_bp.route('/admin/reiniciar-eliminatorias', methods=['POST'])
@login_required
def admin_reiniciar_eliminatorias():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    from fases_service import reiniciar_eliminatorias
    resultado = reiniciar_eliminatorias()
    return jsonify(resultado)


@api_bp.route('/admin/estado-fases', methods=['GET'])
@login_required
def admin_estado_fases():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    from fases_service import verificar_estado_fases
    estado = verificar_estado_fases()
    return jsonify(estado)    

#  PRONOSTICOS EXTRA 

@api_bp.route('/pronosticos-extra', methods=['GET'])
@login_required
def obtener_pronostico_extra():
    """Obtener pronóstico extra del usuario actual"""
    pronostico = PronosticoExtra.query.filter_by(usuario_id=current_user.id).first()
    if pronostico:
        return jsonify({
            'seleccion_mas_goleadora': pronostico.seleccion_mas_goleadora,
            'balon_de_oro': pronostico.balon_de_oro,
            'bota_de_oro': pronostico.bota_de_oro,
            'guante_de_oro': pronostico.guante_de_oro
        })
    return jsonify({}), 200


@api_bp.route('/pronosticos-extra', methods=['POST'])
@login_required
def guardar_pronostico_extra():
    """Guardar pronóstico extra del usuario (solo si no está cerrado)"""
    
    # Verificar si los pronósticos extra están cerrados
    from models import ConfiguracionCierre
    config = ConfiguracionCierre.query.first()
    if config and config.pronosticos_extra_cerrado:
        return jsonify({'error': 'Los pronósticos extra están cerrados. Ya no se pueden modificar.'}), 403
    
    data = request.json
    
    pronostico = PronosticoExtra.query.filter_by(usuario_id=current_user.id).first()
    if not pronostico:
        pronostico = PronosticoExtra(usuario_id=current_user.id)
        db.session.add(pronostico)
    
    pronostico.seleccion_mas_goleadora = data.get('seleccion_mas_goleadora')
    pronostico.balon_de_oro = data.get('balon_de_oro')
    pronostico.bota_de_oro = data.get('bota_de_oro')
    pronostico.guante_de_oro = data.get('guante_de_oro')
    
    db.session.commit()
    return jsonify({'mensaje': 'Pronóstico extra guardado correctamente'}), 200


@api_bp.route('/admin/asignar-puntos-goleadora', methods=['POST'])
@login_required
def admin_asignar_puntos_goleadora():
    """Asignar 10 puntos a los usuarios que acertaron la selección más goleadora"""
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.json
    seleccion_ganadora = data.get('seleccion')
    
    if not seleccion_ganadora:
        return jsonify({'error': 'Selección requerida'}), 400
    
    pronosticos = PronosticoExtra.query.filter_by(seleccion_mas_goleadora=seleccion_ganadora).all()
    
    # Actualizar PronosticoExtra en bulk sin N+1
    ids_usuarios = [p.usuario_id for p in pronosticos]
    for p in pronosticos:
        p.puntos_goleadora = 10

    # Un solo UPDATE en lugar de N queries .get()
    if ids_usuarios:
        db.session.query(Usuario).filter(
            Usuario.id.in_(ids_usuarios)
        ).update(
            {Usuario.puntos_extra: func.coalesce(Usuario.puntos_extra, 0) + 10},
            synchronize_session='fetch'
        )

    db.session.commit()
    
    return jsonify({
        'mensaje': f'Se asignaron 10 puntos a {len(pronosticos)} usuarios que eligieron a {seleccion_ganadora}'
    }), 200

@api_bp.route('/admin/ganadores', methods=['GET'])
@login_required
def admin_obtener_ganadores():
    """Obtener los ganadores actuales de cada categoría"""
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    # Obtener configuración de ganadores (puedes guardarlos en una tabla o variables)
    from models import ConfiguracionGanadores
    ganadores = ConfiguracionGanadores.query.first()
    if ganadores:
        return jsonify({
            'seleccion_goleadora': ganadores.seleccion_goleadora,
            'balon_de_oro': ganadores.balon_de_oro,
            'bota_de_oro': ganadores.bota_de_oro,
            'guante_de_oro': ganadores.guante_de_oro
        })
    return jsonify({}), 200


@api_bp.route('/admin/ganadores', methods=['POST'])
@login_required
def admin_guardar_ganadores():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.json
    seleccion_goleadora = data.get('seleccion_goleadora')
    
    if not seleccion_goleadora:
        return jsonify({'error': 'Selección requerida'}), 400
    
    puntos_asignados = 0
    
    # Buscar usuarios que acertaron la selección más goleadora
    pronosticos = PronosticoExtra.query.filter_by(seleccion_mas_goleadora=seleccion_goleadora).all()
    
    for p in pronosticos:
        if p.puntos_goleadora == 0:
            p.puntos_goleadora = 10
            usuario = Usuario.query.get(p.usuario_id)
            usuario.puntos_extra = (usuario.puntos_extra or 0) + 10
            puntos_asignados += 1
    
    db.session.commit()
    
    return jsonify({
        'mensaje': f'Se asignaron 10 puntos a {puntos_asignados} usuarios que eligieron a {seleccion_goleadora}'
    }), 200

@api_bp.route('/admin/cerrar-pronosticos-extra', methods=['POST'])
@login_required
def admin_cerrar_pronosticos_extra():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    # Cerrar todos los pronósticos extra (evita nuevos o modificaciones)
    from models import ConfiguracionCierre
    config = ConfiguracionCierre.query.first()
    if not config:
        config = ConfiguracionCierre()
        db.session.add(config)
    
    config.pronosticos_extra_cerrado = True
    db.session.commit()
    
    return jsonify({'mensaje': 'Pronósticos extra cerrados. Los usuarios ya no podrán modificar sus selecciones.'}), 200


@api_bp.route('/admin/abrir-pronosticos-extra', methods=['POST'])
@login_required
def admin_abrir_pronosticos_extra():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    from models import ConfiguracionCierre
    config = ConfiguracionCierre.query.first()
    if config:
        config.pronosticos_extra_cerrado = False
        db.session.commit()
    
    return jsonify({'mensaje': 'Pronósticos extra abiertos. Los usuarios pueden modificar sus selecciones.'}), 200


@api_bp.route('/admin/estado-pronosticos-extra', methods=['GET'])
@login_required
def admin_estado_pronosticos_extra():
    from models import ConfiguracionCierre
    config = ConfiguracionCierre.query.first()
    cerrado = config.pronosticos_extra_cerrado if config else False
    
    return jsonify({'cerrado': cerrado}), 200

@api_bp.route('/admin/cerrar-fase/<fase>', methods=['POST'])
@login_required
def admin_cerrar_fase(fase):
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        # Buscar o crear la configuración
        config = ConfiguracionTiempo.query.filter_by(fase=fase).first()
        
        if not config:
            config = ConfiguracionTiempo(fase=fase, fecha_limite=None)
            db.session.add(config)
        
        # Cambiar estado
        config.cerrado = True
        
        # Guardar
        db.session.commit()
        
        # Verificar que se guardo
        db.session.refresh(config)
        
        return jsonify({
            'mensaje': f'Fase {fase} cerrada correctamente.',
            'cerrado': config.cerrado
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/admin/abrir-fase/<fase>', methods=['POST'])
@login_required
def admin_abrir_fase(fase):
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    config = ConfiguracionTiempo.query.filter_by(fase=fase).first()
    if not config:
        config = ConfiguracionTiempo(fase=fase, fecha_limite=None)
        db.session.add(config)
    
    config.cerrado = False
    db.session.commit()
    
    return jsonify({'mensaje': f'Fase {fase} abierta correctamente.'}), 200

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Endpoint exclusivo para mantener la app despierta"""
    return jsonify({"status": "alive"}), 200