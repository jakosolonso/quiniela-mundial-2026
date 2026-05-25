import requests
from datetime import datetime
from database import db
from models import Partido, Pronostico
import os
import re
import random

# SportScore API (gratis, sin API key)
SPORTSCORE_API = "https://api.sportscore.io/v1"

# Modo prueba - Cambiar a False cuando empiece el Mundial
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
    Obtiene resultados SOLO de tiempo regular + extra time (NO penales)
    También determina qué equipo avanza (por resultado o penales)
    """
    # Modo prueba
    if MODO_PRUEBA:
        print("🔧 [MODO PRUEBA] Simulando resultados de partidos")
        from models import Partido
        partidos_simular = Partido.query.filter_by(jugado=False).limit(5).all()
        
        resultados_simulados = []
        
        for partido in partidos_simular:
            goles_local = random.randint(0, 3)
            goles_visitante = random.randint(0, 3)
            
            # Determinar ganador
            if goles_local > goles_visitante:
                equipo_ganador = partido.equipo_local
            elif goles_visitante > goles_local:
                equipo_ganador = partido.equipo_visitante
            else:
                # Empate: simular penales (aleatorio)
                equipo_ganador = random.choice([partido.equipo_local, partido.equipo_visitante])
            
            resultados_simulados.append({
                'local': partido.equipo_local,
                'visitante': partido.equipo_visitante,
                'goles_local': goles_local,
                'goles_visitante': goles_visitante,
                'equipo_ganador': equipo_ganador,
                'hubo_penales': goles_local == goles_visitante,
                'estado': 'FT_PEN' if goles_local == goles_visitante else 'FT',
                'finalizado': True
            })
            print(f"   📊 Simulado: {partido.equipo_local} {goles_local} - {goles_visitante} {partido.equipo_visitante} (Ganador: {equipo_ganador})")
        
        return resultados_simulados
    
    # === CÓDIGO REAL (Mundial 2026) ===
    try:
        url = f"{SPORTSCORE_API}/soccer/live"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            resultados = []
            
            matches = data.get('data', []) if isinstance(data, dict) else data
            if not matches:
                print("No hay partidos en vivo")
                return []
            
            for match in matches:
                tournament = match.get('tournament', {})
                tournament_name = tournament.get('name', '')
                
                # Filtrar Mundial 2026
                if 'World Cup' in tournament_name or 'World Cup 2026' in tournament_name:
                    
                    state = match.get('state', {}).get('name', '')
                    status = match.get('status', '')
                    
                    home_score = match.get('scores', {}).get('home', {})
                    away_score = match.get('scores', {}).get('away', {})
                    
                    goles_local = home_score.get('current', 0)
                    goles_visitante = away_score.get('current', 0)
                    
                    penalty_winners = match.get('penalty_winners', {})
                    ganador_penales = None
                    if penalty_winners:
                        ganador_penales = penalty_winners.get('name')
                    
                    home_team = match.get('home_team', {}).get('name', '')
                    away_team = match.get('away_team', {}).get('name', '')
                    
                    equipo_ganador = None
                    if goles_local > goles_visitante:
                        equipo_ganador = home_team
                    elif goles_visitante > goles_local:
                        equipo_ganador = away_team
                    elif ganador_penales:
                        equipo_ganador = ganador_penales
                    
                    finalizado = state in ['FT', 'AET', 'FT_PEN'] or status == 'FT'
                    
                    resultados.append({
                        'local': normalizar_nombre_equipo(home_team),
                        'visitante': normalizar_nombre_equipo(away_team),
                        'goles_local': goles_local,
                        'goles_visitante': goles_visitante,
                        'equipo_ganador': normalizar_nombre_equipo(equipo_ganador) if equipo_ganador else None,
                        'hubo_penales': ganador_penales is not None,
                        'estado': state,
                        'finalizado': finalizado
                    })
                    
                    print(f"📊 Partido: {home_team} {goles_local} - {goles_visitante} {away_team} ({state})")
            
            return resultados
        else:
            print(f"Error API SportScore: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error al obtener resultados: {e}")
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
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔄 Actualizando resultados...")
    
    resultados = obtener_resultados_de_api()
    
    if not resultados:
        print("⚠️ No se obtuvieron resultados")
        return
    
    partidos_actualizados = 0
    
    for res in resultados:
        partido = Partido.query.filter(
            Partido.equipo_local.ilike(f"%{res['local']}%"),
            Partido.equipo_visitante.ilike(f"%{res['visitante']}%"),
            Partido.jugado == False
        ).first()
        
        if partido and res['finalizado']:
            partido.resultado_local = res['goles_local']
            partido.resultado_visitante = res['goles_visitante']
            partido.jugado = True
            
            if res['equipo_ganador']:
                partido.equipo_ganador = res['equipo_ganador']
            
            calcular_puntos_partido(partido)
            
            partidos_actualizados += 1
            print(f"✅ Partido actualizado: {partido.equipo_local} {res['goles_local']} - {res['goles_visitante']} {partido.equipo_visitante}")
            if res['hubo_penales']:
                print(f"   🏆 Ganador por penales: {res['equipo_ganador']}")
    
    db.session.commit()
    print(f"📊 Resultados: {partidos_actualizados} partidos actualizados")