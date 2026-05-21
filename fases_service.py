from datetime import datetime
from database import db
from models import Partido, Pronostico
import re

# ============ CONFIGURACIÓN ============

GRUPOS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']

DIECISEISAVOS_CRUCES = [
    # Primera mitad del cuadro
    (73, ('1° Grupo A', '3° Grupo B/C/D/E/F')),
    (74, ('2° Grupo B', '2° Grupo C')),
    (75, ('1° Grupo D', '3° Grupo E/F/G/H/I')),
    (76, ('1° Grupo E', '2° Grupo F')),
    (77, ('1° Grupo G', '3° Grupo H/I/J/K/L')),
    (78, ('2° Grupo H', '2° Grupo I')),
    (79, ('1° Grupo J', '3° Grupo K/L')),
    (80, ('2° Grupo K', '2° Grupo L')),
    # Segunda mitad del cuadro
    (81, ('1° Grupo B', '3° Grupo A/C/D/E/F')),
    (82, ('2° Grupo A', '2° Grupo D')),
    (83, ('1° Grupo C', '3° Grupo D/E/F/G/H')),
    (84, ('1° Grupo F', '2° Grupo E')),
    (85, ('1° Grupo H', '3° Grupo I/J/K/L')),
    (86, ('2° Grupo G', '2° Grupo J')),
    (87, ('1° Grupo I', '3° Grupo J/K/L')),
    (88, ('2° Grupo L', '2° Grupo K')),
]

OCTAVOS_CRUCES = [
    (89, (73, 77)), (90, (74, 75)), (91, (76, 78)), (92, (79, 80)),
    (93, (81, 85)), (94, (82, 83)), (95, (84, 86)), (96, (87, 88)),
]

CUARTOS_CRUCES = [
    (97, (89, 90)), (98, (91, 92)), (99, (93, 94)), (100, (95, 96)),
]

SEMIS_CRUCES = [
    (101, (97, 98)), (102, (99, 100)),
]

FINAL_CRUCE = (104, (101, 102))

FECHAS_FASES = {
    'dieciseisavos': datetime(2026, 6, 28, 15, 0),
    'octavos': datetime(2026, 7, 4, 15, 0),
    'cuartos': datetime(2026, 7, 9, 15, 0),
    'semis': datetime(2026, 7, 14, 15, 0),
    'final': datetime(2026, 7, 19, 15, 0)
}


# ============ FUNCIONES AUXILIARES ============

def calcular_tabla_grupo(partidos):
    """Calcula la tabla de posiciones de un grupo"""
    tabla = {}
    for partido in partidos:
        for equipo in [partido.equipo_local, partido.equipo_visitante]:
            if equipo not in tabla:
                tabla[equipo] = {'puntos': 0, 'dg': 0, 'gf': 0, 'gc': 0}
        
        gl = partido.resultado_local
        gv = partido.resultado_visitante
        
        tabla[partido.equipo_local]['gf'] += gl
        tabla[partido.equipo_local]['gc'] += gv
        tabla[partido.equipo_visitante]['gf'] += gv
        tabla[partido.equipo_visitante]['gc'] += gl
        tabla[partido.equipo_local]['dg'] += (gl - gv)
        tabla[partido.equipo_visitante]['dg'] += (gv - gl)
        
        if gl > gv:
            tabla[partido.equipo_local]['puntos'] += 3
        elif gv > gl:
            tabla[partido.equipo_visitante]['puntos'] += 3
        else:
            tabla[partido.equipo_local]['puntos'] += 1
            tabla[partido.equipo_visitante]['puntos'] += 1
    
    resultado = sorted(tabla.items(), key=lambda x: (x[1]['puntos'], x[1]['dg'], x[1]['gf']), reverse=True)
    return [{'equipo': r[0], 'puntos': r[1]['puntos'], 'dg': r[1]['dg'], 'gf': r[1]['gf']} for r in resultado]


def obtener_clasificados_grupos():
    """Obtiene los equipos clasificados (1°, 2° y mejores terceros)"""
    primeros = {}
    segundos = {}
    terceros_lista = []
    
    for grupo in GRUPOS:
        partidos = Partido.query.filter_by(grupo=grupo, fase='grupos', jugado=True).all()
        if len(partidos) == 0:
            return None
        
        tabla = calcular_tabla_grupo(partidos)
        
        if len(tabla) >= 1:
            primeros[grupo] = tabla[0]['equipo']
        if len(tabla) >= 2:
            segundos[grupo] = tabla[1]['equipo']
        if len(tabla) >= 3:
            terceros_lista.append({
                'equipo': tabla[2]['equipo'],
                'puntos': tabla[2]['puntos'],
                'dg': tabla[2]['dg'],
                'grupo': grupo
            })
    
    terceros_lista.sort(key=lambda x: (x['puntos'], x['dg']), reverse=True)
    mejores_terceros = terceros_lista[:8]
    
    return {
        'primeros': primeros,
        'segundos': segundos,
        'mejores_terceros': mejores_terceros
    }


def resolver_tercero(expresion, mejores_terceros):
    """Resuelve qué equipo ocupa el 3° lugar"""
    if '/' in expresion:
        grupos_mencionados = re.findall(r'[A-L]', expresion)
        mejores = [t for t in mejores_terceros if t['grupo'] in grupos_mencionados]
        if mejores:
            return mejores[0]['equipo']
    
    match = re.search(r'3° Grupo ([A-L])', expresion)
    if match:
        grupo = match.group(1)
        for t in mejores_terceros:
            if t['grupo'] == grupo:
                return t['equipo']
    
    return None


def generar_dieciseisavos():
    """Genera los 16 partidos de dieciseisavos - Versión simplificada"""
    
    # Verificar si ya existen
    if Partido.query.filter_by(fase='dieciseisavos').first():
        return {'success': False, 'message': 'Los dieciseisavos ya fueron generados'}
    
    # Obtener todos los equipos clasificados
    clasificados = obtener_clasificados_grupos()
    if not clasificados:
        return {'success': False, 'message': 'No hay resultados de grupos disponibles'}
    
    # Crear lista de todos los equipos clasificados
    todos_los_clasificados = []
    
    # Agregar primeros y segundos
    for grupo in GRUPOS:
        if grupo in clasificados['primeros']:
            todos_los_clasificados.append({
                'equipo': clasificados['primeros'][grupo],
                'posicion': 1,
                'grupo': grupo
            })
        if grupo in clasificados['segundos']:
            todos_los_clasificados.append({
                'equipo': clasificados['segundos'][grupo],
                'posicion': 2,
                'grupo': grupo
            })
    
    # Agregar mejores terceros
    for tercero in clasificados['mejores_terceros']:
        todos_los_clasificados.append({
            'equipo': tercero['equipo'],
            'posicion': 3,
            'grupo': tercero['grupo']
        })
    
    if len(todos_los_clasificados) != 32:
        return {'success': False, 'message': f'Se necesitan 32 equipos, solo hay {len(todos_los_clasificados)}'}
    
    # Ordenar para crear cruces equitativos
    # Agrupar por posición para mezclar
    primeros = [c for c in todos_los_clasificados if c['posicion'] == 1]
    segundos = [c for c in todos_los_clasificados if c['posicion'] == 2]
    terceros = [c for c in todos_los_clasificados if c['posicion'] == 3]
    
    # Mezclar para evitar duplicados
    import random
    random.seed(42)  # Semilla fija para resultados consistentes
    
    random.shuffle(primeros)
    random.shuffle(segundos)
    random.shuffle(terceros)
    
    # Crear cruces: 1° vs (2° o 3°)
    cruces = []
    
    # Los 8 primeros enfrentan a segundos o terceros
    for i in range(8):
        if i < len(primeros) and i < len(segundos):
            cruces.append((primeros[i]['equipo'], segundos[i]['equipo']))
    
    # Los siguientes 8 primeros enfrentan a los mejores terceros
    for i in range(8, 16):
        if i < len(primeros) and (i - 8) < len(terceros):
            cruces.append((primeros[i]['equipo'], terceros[i - 8]['equipo']))
    
    # Si faltan cruces, completar con los que tenemos
    while len(cruces) < 16 and len(terceros) > 0:
        cruces.append((primeros[len(cruces) % len(primeros)]['equipo'], 
                       terceros[len(cruces) % len(terceros)]['equipo']))
    
    # Limitar a 16 cruces
    cruces = cruces[:16]
    
    # Verificar que no haya equipos repetidos en los cruces
    equipos_usados = set()
    cruces_limpios = []
    for local, visitante in cruces:
        if local not in equipos_usados and visitante not in equipos_usados and local != visitante:
            equipos_usados.add(local)
            equipos_usados.add(visitante)
            cruces_limpios.append((local, visitante))
    
    # Crear los partidos
    partidos_generados = 0
    for local, visitante in cruces_limpios:
        partido = Partido(
            equipo_local=local,
            equipo_visitante=visitante,
            fecha=FECHAS_FASES['dieciseisavos'],
            grupo='ELIM',
            fase='dieciseisavos',
            jugado=False
        )
        db.session.add(partido)
        partidos_generados += 1
    
    db.session.commit()
    return {'success': True, 'message': f'Se generaron {partidos_generados} partidos de dieciseisavos'}


def generar_fase_eliminatoria(fase_anterior, fase_actual, cruces_config):
    """Genera partidos de octavos, cuartos, semis o final"""
    if Partido.query.filter_by(fase=fase_actual).first():
        return {'success': False, 'message': f'La fase {fase_actual} ya fue generada'}
    
    ganadores = {}
    partidos_anteriores = Partido.query.filter_by(fase=fase_anterior, jugado=True).all()
    
    if len(partidos_anteriores) == 0:
        return {'success': False, 'message': f'No hay resultados de {fase_anterior}'}
    
    for p in partidos_anteriores:
        if p.resultado_local > p.resultado_visitante:
            ganadores[p.id] = p.equipo_local
        else:
            ganadores[p.id] = p.equipo_visitante
    
    partidos_generados = 0
    
    for partido_id, (origen1, origen2) in cruces_config:
        local = ganadores.get(origen1)
        visitante = ganadores.get(origen2)
        
        if local and visitante:
            partido = Partido(
                equipo_local=local,
                equipo_visitante=visitante,
                fecha=FECHAS_FASES[fase_actual],
                grupo='ELIM',
                fase=fase_actual,
                jugado=False
            )
            db.session.add(partido)
            partidos_generados += 1
    
    db.session.commit()
    return {'success': True, 'message': f'Se generaron {partidos_generados} partidos de {fase_actual}'}


def generar_octavos():
    return generar_fase_eliminatoria('dieciseisavos', 'octavos', OCTAVOS_CRUCES)


def generar_cuartos():
    return generar_fase_eliminatoria('octavos', 'cuartos', CUARTOS_CRUCES)


def generar_semis():
    return generar_fase_eliminatoria('cuartos', 'semis', SEMIS_CRUCES)


def generar_final():
    return generar_fase_eliminatoria('semis', 'final', [FINAL_CRUCE])


def borrar_fase(fase):
    """Borra todos los partidos de una fase específica"""
    partidos = Partido.query.filter_by(fase=fase).all()
    if partidos:
        # Primero borrar pronósticos relacionados
        for partido in partidos:
            Pronostico.query.filter_by(partido_id=partido.id).delete()
        # Luego borrar partidos
        Partido.query.filter_by(fase=fase).delete()
        db.session.commit()
        return {'success': True, 'message': f'Se borraron {len(partidos)} partidos de {fase}'}
    return {'success': False, 'message': f'No hay partidos en {fase}'}


def reiniciar_eliminatorias():
    """Borra todas las fases eliminatorias (desde dieciseisavos hasta final)"""
    fases = ['dieciseisavos', 'octavos', 'cuartos', 'semis', 'final']
    resultados = []
    for fase in fases:
        resultado = borrar_fase(fase)
        resultados.append(resultado['message'])
    return {'success': True, 'message': ' | '.join(resultados)}


def verificar_estado_fases():
    """Verifica cuántos partidos hay por fase"""
    fases = ['grupos', 'dieciseisavos', 'octavos', 'cuartos', 'semis', 'final']
    estado = {}
    for fase in fases:
        total = Partido.query.filter_by(fase=fase).count()
        jugados = Partido.query.filter_by(fase=fase, jugado=True).count()
        estado[fase] = {'total': total, 'jugados': jugados, 'pendientes': total - jugados}
    return estado