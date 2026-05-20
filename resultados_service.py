import requests
from datetime import datetime
from database import db
from models import Partido, Pronostico
import os
import re

# SportScore API (gratis, sin API key)
SPORTSCORE_API = "https://api.sportscore.io/v1"

def actualizar_resultados_en_db():
    """Actualiza los resultados en la base de datos"""
    ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ahora}] 🔄 EJECUTANDO SCHEDULER - Actualizando resultados...")
    
    resultados = obtener_resultados_de_api()
    
    if not resultados:
        print(f"[{ahora}] ⚠️ No se obtuvieron resultados de la API")
        return
    
    print(f"[{ahora}] 📊 Se obtuvieron {len(resultados)} partidos")
    
    # Resto del código...

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

# Modo prueba - Cambiar a False cuando empiece el Mundial
MODO_PRUEBA = True

def obtener_resultados_de_api():
    """Obtiene resultados en vivo de partidos del Mundial 2026"""
    
    # === MODO PRUEBA ===
    if MODO_PRUEBA:
        print("🔧 [MODO PRUEBA] Simulando resultados de partidos")
        
        # Obtener partidos de la base de datos que aún no se han jugado
        from models import Partido
        partidos_simular = Partido.query.filter_by(jugado=False).limit(5).all()
        
        resultados_simulados = []
        import random
        
        for partido in partidos_simular:
            # Generar resultados aleatorios para pruebas
            goles_local = random.randint(0, 3)
            goles_visitante = random.randint(0, 3)
            
            resultados_simulados.append({
                'local': partido.equipo_local,
                'visitante': partido.equipo_visitante,
                'goles_local': goles_local,
                'goles_visitante': goles_visitante,
                'estado': 'FINISHED',
                'match_id': partido.id
            })
            print(f"   📊 Simulado: {partido.equipo_local} {goles_local} - {goles_visitante} {partido.equipo_visitante}")
        
        return resultados_simulados
    
    # === CÓDIGO REAL (Mundial 2026) ===
    try:
        import requests
        url = "https://api.sportscore.io/v1/soccer/live"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            partidos_actualizados = []
            
            matches = data.get('data', []) if isinstance(data, dict) else data
            if not matches:
                print("No hay partidos en vivo")
                return []
            
            for match in matches:
                tournament = match.get('tournament', {})
                tournament_name = tournament.get('name', '')
                
                if 'World Cup' in tournament_name or 'World Cup 2026' in tournament_name:
                    home_team = match.get('home_team', {})
                    away_team = match.get('away_team', {})
                    home_score = match.get('home_score', {})
                    away_score = match.get('away_score', {})
                    status = match.get('status', '')
                    
                    partidos_actualizados.append({
                        'local': home_team.get('name', ''),
                        'visitante': away_team.get('name', ''),
                        'goles_local': home_score.get('current', 0),
                        'goles_visitante': away_score.get('current', 0),
                        'estado': status,
                        'match_id': match.get('id')
                    })
            
            return partidos_actualizados
        else:
            print(f"Error API SportScore: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error al obtener resultados: {e}")
        return []

def actualizar_resultados_en_db():
    """Actualiza los resultados en la base de datos"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔄 Actualizando resultados...")
    
    resultados = obtener_resultados_de_api()
    
    if not resultados:
        print("⚠️ No se obtuvieron resultados")
        return
    
    partidos_actualizados = 0
    partidos_verificados = 0
    
    for res in resultados:
        # Buscar el partido en tu base de datos
        partido = Partido.query.filter(
            Partido.equipo_local.ilike(f"%{res['local']}%"),
            Partido.equipo_visitante.ilike(f"%{res['visitante']}%"),
            Partido.jugado == False
        ).first()
        
        if partido:
            partidos_verificados += 1
            
            # Si el partido terminó, guardar resultado
            if res['estado'] in ['FINISHED', 'FT', 'FULL_TIME']:
                partido.resultado_local = res['goles_local']
                partido.resultado_visitante = res['goles_visitante']
                partido.jugado = True
                partidos_actualizados += 1
                
                # Calcular puntos para todos los usuarios
                calcular_puntos_para_partido(partido)
                print(f"✅ Partido finalizado: {partido.equipo_local} {partido.resultado_local} - {partido.resultado_visitante} {partido.equipo_visitante}")
    
    if partidos_verificados == 0:
        print("⚠️ No se encontraron partidos coincidentes en la base de datos")
    
    db.session.commit()
    print(f"📊 Resultados: {partidos_actualizados} partidos actualizados, {partidos_verificados} verificados")

def calcular_puntos_para_partido(partido):
    """
    Calcula los puntos para todos los pronósticos de este partido
    """
    from routes import calcular_puntos
    
    pronosticos = Pronostico.query.filter_by(partido_id=partido.id).all()
    
    for pronostico in pronosticos:
        pronostico.puntos = calcular_puntos(
            pronostico.goles_local, 
            pronostico.goles_visitante,
            partido.resultado_local, 
            partido.resultado_visitante,
            partido.fase
        )
    
    print(f"   📈 Puntos calculados para {len(pronosticos)} usuarios")