from datetime import datetime
from database import db
from models import Partido, Pronostico
import re

#  CONFIGURACIÓN 

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


#  FUNCIONES AUX

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
    """Genera los 16 partidos de dieciseisavos - Versión corregida"""
    
    # Verificar si ya existen
    if Partido.query.filter_by(fase='dieciseisavos').first():
        return {'success': False, 'message': 'Los dieciseisavos ya fueron generados'}
    
    # Obtener todos los equipos clasificados
    clasificados = obtener_clasificados_grupos()
    if not clasificados:
        return {'success': False, 'message': 'No hay resultados de grupos disponibles'}
    
    # Crear lista de todos los equipos clasificados
    lista_equipos = []
    
    # Agregar primeros (12 equipos)
    for grupo in GRUPOS:
        if grupo in clasificados['primeros']:
            lista_equipos.append({
                'equipo': clasificados['primeros'][grupo],
                'posicion': 1,
                'grupo': grupo
            })
    
    # Agregar segundos (12 equipos)
    for grupo in GRUPOS:
        if grupo in clasificados['segundos']:
            lista_equipos.append({
                'equipo': clasificados['segundos'][grupo],
                'posicion': 2,
                'grupo': grupo
            })
    
    # Agregar mejores terceros (8 equipos)
    for tercero in clasificados['mejores_terceros']:
        lista_equipos.append({
            'equipo': tercero['equipo'],
            'posicion': 3,
            'grupo': tercero['grupo']
        })
    
    if len(lista_equipos) != 32:
        return {'success': False, 'message': f'Se necesitan 32 equipos, solo hay {len(lista_equipos)}'}
    
    # Separar por posición
    primeros = [e for e in lista_equipos if e['posicion'] == 1]
    segundos = [e for e in lista_equipos if e['posicion'] == 2]
    terceros = [e for e in lista_equipos if e['posicion'] == 3]
    
    # Mezclar para variar
    import random
    random.seed(42)
    random.shuffle(primeros)
    random.shuffle(segundos)
    random.shuffle(terceros)
    
    # Crear 16 cruces
    cruces = []
    equipos_usados = set()
    
    # Regla: 1° vs (2° o 3°)
    # Se asegura que ningún equipo se repita
    
    # Primera mitad: 1° vs 2° (8 partidos)
    for i in range(min(8, len(primeros), len(segundos))):
        if primeros[i]['equipo'] not in equipos_usados and segundos[i]['equipo'] not in equipos_usados:
            cruces.append((primeros[i]['equipo'], segundos[i]['equipo']))
            equipos_usados.add(primeros[i]['equipo'])
            equipos_usados.add(segundos[i]['equipo'])
    
    # Segunda mitad: 1° vs 3° (8 partidos)
    # Usa los siguientes primeros y los terceros
    for i in range(min(8, len(primeros) - 8, len(terceros))):
        idx_primeros = 8 + i
        if idx_primeros < len(primeros) and i < len(terceros):
            if primeros[idx_primeros]['equipo'] not in equipos_usados and terceros[i]['equipo'] not in equipos_usados:
                cruces.append((primeros[idx_primeros]['equipo'], terceros[i]['equipo']))
                equipos_usados.add(primeros[idx_primeros]['equipo'])
                equipos_usados.add(terceros[i]['equipo'])
    
    # Si aun faltan cruces, usar equipos restantes
    equipos_restantes = [e for e in lista_equipos if e['equipo'] not in equipos_usados]
    
    while len(cruces) < 16 and len(equipos_restantes) >= 2:
        local = equipos_restantes.pop(0)
        visitante = equipos_restantes.pop(0)
        cruces.append((local['equipo'], visitante['equipo']))
    
    # Verifica que tenemos exactamente 16 cruces
    if len(cruces) != 16:
        return {'success': False, 'message': f'Solo se pudieron generar {len(cruces)} cruces de 16'}
    
    # Verifica que no haya equipos duplicados
    equipos_en_cruces = set()
    for local, visitante in cruces:
        equipos_en_cruces.add(local)
        equipos_en_cruces.add(visitante)
    
    if len(equipos_en_cruces) != 32:
        return {'success': False, 'message': f'Hay {len(equipos_en_cruces)} equipos únicos, deberían ser 32'}
    
    # Crear los partidos
    partidos_generados = 0
    for local, visitante in cruces:
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
    
    # Obtiene los partidos de la fase anterior en orden
    partidos_anteriores = Partido.query.filter_by(fase=fase_anterior, jugado=True).order_by(Partido.id).all()
    
    if len(partidos_anteriores) == 0:
        return {'success': False, 'message': f'No hay resultados en {fase_anterior}'}
    
    # Crea lista de ganadores en el orden de los partidos
    ganadores = []
    for partido in partidos_anteriores:
        if partido.resultado_local > partido.resultado_visitante:
            ganadores.append(partido.equipo_local)
        else:
            ganadores.append(partido.equipo_visitante)
    
    # Verifica que tenemos suficientes ganadores
    num_partidos_necesarios = len(cruces_config) * 2
    if len(ganadores) < num_partidos_necesarios:
        return {'success': False, 'message': f'Se necesitan {num_partidos_necesarios} ganadores, solo hay {len(ganadores)}'}
    
    # Crear cruces en orden (1º vs 2º, 3º vs 4º, etc...)
    cruces = []
    for i in range(0, len(ganadores), 2):
        if i + 1 < len(ganadores):
            cruces.append((ganadores[i], ganadores[i + 1]))
    
    # Limita al número de cruces esperados
    num_esperados = len(cruces_config)
    if len(cruces) > num_esperados:
        cruces = cruces[:num_esperados]
    
    # Crea los partidos
    partidos_generados = 0
    for local, visitante in cruces:
        if local and visitante and local != visitante:
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
    
    if partidos_generados == num_esperados:
        return {'success': True, 'message': f'Se generaron {partidos_generados} partidos de {fase_actual}'}
    else:
        return {'success': False, 'message': f'Solo se generaron {partidos_generados} de {num_esperados} esperados'}


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