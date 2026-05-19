import requests
from datetime import datetime
from database import db
from models import Partido, Pronostico
import os
import re

# SportScore API (gratis, sin API key)
SPORTSCORE_API = "https://api.sportscore.io/v1"

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
    Obtiene resultados en vivo de partidos del Mundial 2026
    Usa SportScore API (gratis)
    """
    try:
        # SportScore API para partidos en vivo
        url = f"{SPORTSCORE_API}/soccer/live"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            partidos_actualizados = []
            
            # Procesar cada partido
            matches = data.get('data', []) if isinstance(data, dict) else data
            if not matches:
                print("No hay partidos en vivo")
                return []
            
            for match in matches:
                tournament = match.get('tournament', {})
                tournament_name = tournament.get('name', '')
                
                # Buscar partidos del Mundial 2026
                if 'World Cup' in tournament_name or 'World Cup 2026' in tournament_name:
                    home_team = match.get('home_team', {})
                    away_team = match.get('away_team', {})
                    home_score = match.get('home_score', {})
                    away_score = match.get('away_score', {})
                    status = match.get('status', '')
                    
                    partidos_actualizados.append({
                        'local': normalizar_nombre_equipo(home_team.get('name', '')),
                        'visitante': normalizar_nombre_equipo(away_team.get('name', '')),
                        'goles_local': home_score.get('current', 0),
                        'goles_visitante': away_score.get('current', 0),
                        'estado': status,  # 'LIVE', 'FINISHED', 'NOT_STARTED'
                        'match_id': match.get('id')
                    })
                    
                    print(f"📊 Partido encontrado: {home_team.get('name')} {home_score.get('current', 0)} - {away_score.get('current', 0)} {away_team.get('name')} ({status})")
            
            return partidos_actualizados
        else:
            print(f"Error API SportScore: {response.status_code}")
            return []
            
    except requests.exceptions.ConnectionError:
        print("Error de conexión con SportScore API")
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