import requests
from datetime import datetime
from database import db
from models import Partido, Pronostico
import os
import re
import random

# SportScore API (gratis sin API key 'tomar en cuenta')
SPORTSCORE_API = "https://api.sportscore.io/v1"

# ⚠️⚠️⚠️⚠️ *Modo prueba* Cambiar a FALSE cuando empiece el Mundial ⚠️⚠️⚠️⚠️
MODO_PRUEBA = True


def normalizar_nombre_equipo(nombre):
    """Normaliza nombres de equipos para comparar"""
    nombres_map = {
        'Mexico': 'México',
        'United States': 'Estados Unidos',
        'Korea Republic': 'Corea del Sur',
        'Iran': 'Irán',
        'Ivory Coast': 'Costa de Marfil',
        'DR Congo': 'RD Congo',
        'Bosnia-Herzegovina': 'Bosnia y Herzegovina',
        'South Africa': 'Sudáfrica',
        'Czech Republic': 'República Checa',
        'Saudi Arabia': 'Arabia Saudita',
        'Cape Verde': 'Cabo Verde',
        'New Zealand': 'Nueva Zelanda'
    }
    return nombres_map.get(nombre, nombre)


def obtener_resultados_de_api():
    """
    Obtiene resultados de la API (simplificada para pruebas)
    """
    # Por ahora, devolver lista vacía para evitar timeouts
    # Cuando el Mundial comience, cambiar MODO_PRUEBA = False
    MODO_PRUEBA = True
    
    if MODO_PRUEBA:
        print("🔧 [MODO PRUEBA] Simulación desactivada - no hay resultados")
        return []
    
    # Código real de API (se activará cuando MODO_PRUEBA = False)
    try:
        url = "https://api.sportscore.io/v1/soccer/live"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # Procesar respuesta...
            return []
        else:
            return []
    except Exception as e:
        print(f"Error API: {e}")
        return []


def calcular_puntos_partido(partido):
    """Calcula puntos para todos los pronósticos de un partido"""
    from routes import calcular_puntos
    
    pronosticos = Pronostico.query.filter_by(partido_id=partido.id).all()
    
    for pronostico in pronosticos:
        pronostico.puntos = calcular_puntos(
            pronostico.goles_local, pronostico.goles_visitante,
            partido.resultado_local, partido.resultado_visitante,
            partido.fase
        )
    
    print(f"   📈 Puntos calculados para {len(pronosticos)} usuarios")


def actualizar_resultados_en_db():
    """Actualiza los resultados en la base de datos"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔄 Ejecutando scheduler...")
    
    # Por ahora, solo registrar que se ejecutó
    # Cuando el Mundial comience, aquí irá la lógica real
    print("   ⏳ Esperando inicio del Mundial para activar API real")
    
    # Si quieres pruebas con resultados simulados, descomenta:
    # from models import Partido
    # import random
    # partidos = Partido.query.filter_by(jugado=False).limit(3).all()
    # for partido in partidos:
    #     partido.resultado_local = random.randint(0, 3)
    #     partido.resultado_visitante = random.randint(0, 3)
    #     partido.jugado = True
    # db.session.commit()
    # print(f"   ✅ Simulados {len(partidos)} resultados")