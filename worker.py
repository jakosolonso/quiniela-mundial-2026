"""
worker.py — Proceso de scheduler independiente
Corre como servicio separado en Railway (NO en el mismo proceso que gunicorn).
Requiere que app.py NO tenga APScheduler (ya eliminado).
"""

import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [WORKER] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("worker")

# Validar variables críticas antes de importar Flask
if not os.environ.get('DATABASE_URL'):
    logger.error("DATABASE_URL no está configurada. El worker no puede arrancar.")
    sys.exit(1)

# Importar app DESPUÉS de validar env vars.
# app.py ya no tiene scheduler — este import es seguro.
from app import app
from resultados_service import actualizar_resultados_en_db, MODO_PRUEBA


def run_scheduler():
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    intervalo = int(os.environ.get('SCHEDULER_INTERVAL_MINUTES', '10'))

    def job():
        with app.app_context():
            try:
                logger.info("Ejecutando actualización de resultados...")
                actualizar_resultados_en_db()
                logger.info("Actualización completada.")
            except Exception as e:
                logger.exception("Error en job de actualización: %s", e)

    scheduler = BlockingScheduler(timezone="America/Guatemala")
    scheduler.add_job(
        func=job,
        trigger=IntervalTrigger(minutes=intervalo),
        id="actualizar_resultados",
        replace_existing=True,
        misfire_grace_time=60,
    )

    logger.info("Worker iniciado. Intervalo: %d minutos.", intervalo)
    logger.info("MODO_PRUEBA = %s", MODO_PRUEBA)

    # Ejecutar una vez al arrancar para verificar conectividad
    logger.info("Ejecutando primera actualización al arrancar...")
    job()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker detenido.")
        scheduler.shutdown(wait=False)


if __name__ == '__main__':
    run_scheduler()