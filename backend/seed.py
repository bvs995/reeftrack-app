from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.models import Measurement

def seed_database_if_empty(db: Session):
    count = db.query(Measurement).count()
    if count > 0:
        return

    print("🌱 Inicializando base de datos con mediciones históricas de arrecife...")
    now = datetime.utcnow()

    # 5 mediciones en los últimos 10 días para alta confianza estadística
    # Muestra consumo activo de KH y Calcio, y acumulación de nitratos
    sample_records = [
        Measurement(
            timestamp=now - timedelta(days=9, hours=2),
            alkalinity_dkh=8.8,
            calcium_ppm=440.0,
            magnesium_ppm=1360.0,
            nitrate_ppm=6.0,
            phosphate_ppm=0.03,
            salinity_ppt=35.0,
            notes="Hanna Checker HI772 + Salifert"
        ),
        Measurement(
            timestamp=now - timedelta(days=7, hours=1),
            alkalinity_dkh=8.5,
            calcium_ppm=432.0,
            magnesium_ppm=1355.0,
            nitrate_ppm=8.0,
            phosphate_ppm=0.035,
            salinity_ppt=35.0,
            notes="Rutina semanal"
        ),
        Measurement(
            timestamp=now - timedelta(days=5, hours=3),
            alkalinity_dkh=8.2,
            calcium_ppm=425.0,
            magnesium_ppm=1350.0,
            nitrate_ppm=10.2,
            phosphate_ppm=0.04,
            salinity_ppt=35.0,
            notes="Test vespertino"
        ),
        Measurement(
            timestamp=now - timedelta(days=3, hours=1),
            alkalinity_dkh=7.9,
            calcium_ppm=418.0,
            magnesium_ppm=1345.0,
            nitrate_ppm=12.1,
            phosphate_ppm=0.045,
            salinity_ppt=35.0,
            notes="Control de consumo coralino"
        ),
        Measurement(
            timestamp=now - timedelta(days=1),
            alkalinity_dkh=7.65,
            calcium_ppm=412.0,
            magnesium_ppm=1340.0,
            nitrate_ppm=14.3,
            phosphate_ppm=0.048,
            salinity_ppt=35.0,
            notes="Alerta predictiva cercana a 7.5 dKH"
        ),
    ]

    db.add_all(sample_records)
    db.commit()
    print("✅ 5 mediciones de prueba creadas con éxito.")
