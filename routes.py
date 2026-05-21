from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from database import db
from models import Partido, Usuario, Pronostico, ConfiguracionTiempo
from datetime import datetime
import re

api_bp = Blueprint('api', __name__)

# ============ CONFIGURACIÓN DE FASES ELIMINATORIAS ============

GRUPOS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']

# Mapeo de grupos por fase (para los cruces de dieciseisavos según fixture FIFA)
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


# ============ FUNCIÓN DE PUNTUACIÓN AVANZADA ============
def calcular_puntos(goles_local_p, goles_visitante_p, goles_local_r, goles_visitante_r, fase):
    puntos = 0
    
    if goles_local_p == goles_local_r and goles_visitante_p == goles_visitante_r:
        puntos = 5
    elif (goles_local_p - goles_visitante_p) == (goles_local_r - goles_visitante_r):
        puntos = 3
    
    if puntos != 5:
        diferencia_p = goles_local_p - goles_visitante_p
        diferencia_r = goles_local_r - goles_visitante_r
        if diferencia_p == diferencia_r:
            puntos += 1
    
    if fase in ['semis', 'final']:
        puntos = puntos * 2
    
    return puntos


# ============ FUNCIONES AUXILIARES PARA ELIMINATORIAS ============

def obtener_clasificados_grupos_reales():
    """Obtiene los equipos clasificados según resultados reales"""
    clasificados = {
        'primeros': {},
        'segundos': {},
        'terceros': {}
    }
    
    for grupo in GRUPOS:
        partidos = Partido.query.filter_by(grupo=grupo, fase='grupos', jugado=True).all()
        if not partidos:
            return None
        
        tabla = calcular_tabla_grupo(partidos)
        
        if len(tabla) >= 1:
            clasificados['primeros'][grupo] = tabla[0]['equipo']
        if len(tabla) >= 2:
            clasificados['segundos'][grupo] = tabla[1]['equipo']
        if len(tabla) >= 3:
            tercero = tabla[2]
            clasificados['terceros'][grupo] = {
                'equipo': tercero['equipo'],
                'puntos': tercero['puntos'],
                'dg': tercero['dg']
            }
    
    return clasificados


def obtener_mejores_terceros(clasificados):
    """Obtiene los 8 mejores terceros lugares"""
    terceros = [{'equipo': v['equipo'], 'puntos': v['puntos'], 'dg': v['dg'], 'grupo': k} 
                for k, v in clasificados['terceros'].items()]
    
    terceros.sort(key=lambda x: (x['puntos'], x['dg']), reverse=True)
    return terceros[:8]


def resolver_tercero(expresion, terceros_clasificados):
    """Resuelve qué equipo ocupa el 3° lugar de un grupo específico"""
    if '/' in expresion:
        grupos_mencionados = re.findall(r'[A-L]', expresion)
        mejores = sorted([t for t in terceros_clasificados if t['grupo'] in grupos_mencionados], 
                        key=lambda x: (x['puntos'], x['dg']), reverse=True)
        if mejores:
            return mejores[0]['equipo']
    
    match = re.search(r'3° Grupo ([A-L])', expresion)
    if match:
        grupo = match.group(1)
        for t in terceros_clasificados:
            if t['grupo'] == grupo:
                return t['equipo']
    
    return None


def generar_dieciseisavos(clasificados):
    """Genera los 16 partidos de dieciseisavos según fixture FIFA"""
    mejores_terceros = obtener_mejores_terceros(clasificados)
    partidos_generados = []
    
    for partido_id, (local_exp, visitante_exp) in DIECISEISAVOS_CRUCES:
        if '1°' in local_exp:
            grupo = local_exp.split(' ')[-1]
            local = clasificados['primeros'].get(grupo)
        elif '2°' in local_exp:
            grupo = local_exp.split(' ')[-1]
            local = clasificados['segundos'].get(grupo)
        else:
            local = resolver_tercero(local_exp, mejores_terceros)
        
        if '1°' in visitante_exp:
            grupo = visitante_exp.split(' ')[-1]
            visitante = clasificados['primeros'].get(grupo)
        elif '2°' in visitante_exp:
            grupo = visitante_exp.split(' ')[-1]
            visitante = clasificados['segundos'].get(grupo)
        else:
            visitante = resolver_tercero(visitante_exp, mejores_terceros)
        
        if local and visitante:
            partido = Partido(
                equipo_local=local,
                equipo_visitante=visitante,
                fecha=datetime(2026, 6, 28 + (partido_id - 73) // 2, 15, 0),
                grupo='ELIM',
                fase='dieciseisavos',
                jugado=False
            )
            db.session.add(partido)
            partidos_generados.append({'id': partido_id, 'local': local, 'visitante': visitante})
    
    db.session.commit()
    return partidos_generados


def generar_fase_eliminatoria(fase_anterior, fase_actual, cruces_config):
    """Genera partidos de octavos, cuartos, semis o final"""
    ganadores = {}
    partidos_anteriores = Partido.query.filter_by(fase=fase_anterior, jugado=True).all()
    
    for p in partidos_anteriores:
        if p.resultado_local > p.resultado_visitante:
            ganadores[p.id] = p.equipo_local
        else:
            ganadores[p.id] = p.equipo_visitante
    
    fechas = {
        'octavos': datetime(2026, 7, 4, 15, 0),
        'cuartos': datetime(2026, 7, 9, 15, 0),
        'semis': datetime(2026, 7, 14, 15, 0),
        'final': datetime(2026, 7, 19, 15, 0)
    }
    
    partidos_generados = []
    
    for partido_id, (origen1, origen2) in cruces_config:
        local = ganadores.get(origen1)
        visitante = ganadores.get(origen2)
        
        if local and visitante:
            partido = Partido(
                equipo_local=local,
                equipo_visitante=visitante,
                fecha=fechas[fase_actual],
                grupo='ELIM',
                fase=fase_actual,
                jugado=False
            )
            db.session.add(partido)
            partidos_generados.append({'id': partido_id, 'local': local, 'visitante': visitante})
    
    db.session.commit()
    return partidos_generados


def generar_siguiente_fase(fase_actual, fase_siguiente):
    """Genera la siguiente fase según el fixture real"""
    if fase_actual == 'grupos' and fase_siguiente == 'dieciseisavos':
        clasificados = obtener_clasificados_grupos_reales()
        if not clasificados:
            print("❌ No hay resultados de grupos disponibles")
            return False
        return generar_dieciseisavos(clasificados)
    
    elif fase_actual == 'dieciseisavos' and fase_siguiente == 'octavos':
        return generar_fase_eliminatoria('dieciseisavos', 'octavos', OCTAVOS_CRUCES)
    
    elif fase_actual == 'octavos' and fase_siguiente == 'cuartos':
        return generar_fase_eliminatoria('octavos', 'cuartos', CUARTOS_CRUCES)
    
    elif fase_actual == 'cuartos' and fase_siguiente == 'semis':
        return generar_fase_eliminatoria('cuartos', 'semis', SEMIS_CRUCES)
    
    elif fase_actual == 'semis' and fase_siguiente == 'final':
        return generar_fase_eliminatoria('semis', 'final', [FINAL_CRUCE])
    
    return False


def obtener_clasificados_grupos():
    """Obtiene los 32 equipos clasificados (1°, 2° y mejores terceros)"""
    grupos = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
    
    primeros = []
    segundos = []
    terceros = []
    
    for grupo in grupos:
        partidos_grupo = Partido.query.filter_by(grupo=grupo, fase='grupos', jugado=True).all()
        
        if len(partidos_grupo) == 0:
            continue
            
        tabla_grupo = {}
        for partido in partidos_grupo:
            for equipo in [partido.equipo_local, partido.equipo_visitante]:
                if equipo not in tabla_grupo:
                    tabla_grupo[equipo] = {'puntos': 0, 'dg': 0, 'gf': 0}
            
            local = partido.equipo_local
            visitante = partido.equipo_visitante
            gl = partido.resultado_local
            gv = partido.resultado_visitante
            
            tabla_grupo[local]['gf'] += gl
            tabla_grupo[visitante]['gf'] += gv
            tabla_grupo[local]['dg'] += (gl - gv)
            tabla_grupo[visitante]['dg'] += (gv - gl)
            
            if gl > gv:
                tabla_grupo[local]['puntos'] += 3
            elif gv > gl:
                tabla_grupo[visitante]['puntos'] += 3
            else:
                tabla_grupo[local]['puntos'] += 1
                tabla_grupo[visitante]['puntos'] += 1
        
        clasificados = sorted(tabla_grupo.items(), key=lambda x: (x[1]['puntos'], x[1]['dg'], x[1]['gf']), reverse=True)
        
        if len(clasificados) >= 1:
            primeros.append(clasificados[0][0])
        if len(clasificados) >= 2:
            segundos.append(clasificados[1][0])
        if len(clasificados) >= 3:
            terceros.append({'equipo': clasificados[2][0], 'puntos': clasificados[2][1]['puntos'], 'dg': clasificados[2][1]['dg']})
    
    terceros.sort(key=lambda x: (x['puntos'], x['dg']), reverse=True)
    mejores_terceros = [t['equipo'] for t in terceros[:8]]
    
    return {
        'primeros': primeros,
        'segundos': segundos,
        'mejores_terceros': mejores_terceros
    }


def calcular_tabla_grupo(partidos):
    """Calcula la tabla de posiciones de un grupo"""
    tabla = {}
    for partido in partidos:
        for equipo in [partido.equipo_local, partido.equipo_visitante]:
            if equipo not in tabla:
                tabla[equipo] = {'puntos': 0, 'dg': 0, 'gf': 0, 'gc': 0}
        
        local = partido.equipo_local
        visitante = partido.equipo_visitante
        gl = partido.resultado_local
        gv = partido.resultado_visitante
        
        tabla[local]['gf'] += gl
        tabla[local]['gc'] += gv
        tabla[visitante]['gf'] += gv
        tabla[visitante]['gc'] += gl
        tabla[local]['dg'] += (gl - gv)
        tabla[visitante]['dg'] += (gv - gl)
        
        if gl > gv:
            tabla[local]['puntos'] += 3
        elif gv > gl:
            tabla[visitante]['puntos'] += 3
        else:
            tabla[local]['puntos'] += 1
            tabla[visitante]['puntos'] += 1
    
    resultado = sorted(tabla.items(), key=lambda x: (x[1]['puntos'], x[1]['dg'], x[1]['gf']), reverse=True)
    return [{'equipo': r[0], 'puntos': r[1]['puntos'], 'dg': r[1]['dg'], 'gf': r[1]['gf']} for r in resultado]


def generar_cruces_dieciseisavos(clasificados):
    """Genera los 16 cruces de dieciseisavos según formato FIFA 2026"""
    cruces = []
    primeros = clasificados['primeros']
    segundos = clasificados['segundos']
    terceros = clasificados['mejores_terceros']
    
    for i in range(8):
        if i < len(primeros) and i < len(terceros):
            cruces.append((primeros[i], terceros[i]))
    
    for i in range(8):
        if i + 8 < len(segundos) and i + 8 < len(segundos):
            cruces.append((segundos[i + 8], segundos[i]))
    
    return cruces


def generar_cruces_eliminatorias(fase_actual):
    """Genera cruces para fases eliminatorias basado en ganadores"""
    partidos_actual = Partido.query.filter_by(fase=fase_actual, jugado=True).all()
    
    ganadores = []
    for partido in partidos_actual:
        if partido.resultado_local > partido.resultado_visitante:
            ganadores.append(partido.equipo_local)
        else:
            ganadores.append(partido.equipo_visitante)
    
    cruces = []
    for i in range(0, len(ganadores), 2):
        if i + 1 < len(ganadores):
            cruces.append((ganadores[i], ganadores[i + 1]))
    
    return cruces


# ============ AUTENTICACIÓN ============
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
    
    usuario.ultimo_acceso = datetime.utcnow()
    db.session.commit()
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


# ============ TABLA DE POSICIONES ============
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
                
                if p.puntos >= 5:
                    aciertos_exactos += 1
                
                if (p.goles_local - p.goles_visitante) == (partido.resultado_local - partido.resultado_visitante):
                    partidos_acertados += 1
                
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
    
    tabla.sort(key=lambda x: x['puntos'], reverse=True)
    
    for i, item in enumerate(tabla):
        item['posicion'] = i + 1
    
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


# ============ CARGAR DATOS INICIALES ============
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


# ============ ADMINISTRACIÓN ============
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
    ahora = datetime.utcnow()
    return ahora < config.fecha_limite


@api_bp.route('/admin/configurar-tiempo', methods=['GET'])
@login_required
def admin_obtener_configuracion():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    configs = ConfiguracionTiempo.query.all()
    return jsonify([c.to_dict() for c in configs])


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


# ============ ADMIN - PARTIDOS ============
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
    
    thread = threading.Thread(target=actualizar_resultados_en_db)
    thread.start()
    
    return jsonify({'mensaje': 'Actualización iniciada. Revisa los logs.'})


@api_bp.route('/admin/simular-resultados', methods=['POST'])
@login_required
def admin_simular_resultados():
    if not current_user.es_admin:
        return jsonify({'error': 'No autorizado'}), 403
    
    import random
    
    partidos = Partido.query.filter_by(jugado=False).all()
    actualizados = 0
    
    for partido in partidos:
        goles_local = random.randint(0, 4)
        goles_visitante = random.randint(0, 4)
        
        partido.resultado_local = goles_local
        partido.resultado_visitante = goles_visitante
        partido.jugado = True
        actualizados += 1
        
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