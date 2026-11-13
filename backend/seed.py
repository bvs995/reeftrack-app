from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.models import User, Tank, Measurement
from backend.auth import hash_password

def seed_database_if_empty(db: Session):
    # 1. Asegurar usuario demo para pruebas iniciales
    demo_user = db.query(User).filter(User.email == "demo@aquapulse.io").first()
    if not demo_user:
        print("👤 Creando usuario demo por defecto: demo@aquapulse.io (clave: demo123)...")
        demo_user = User(
            email="demo@aquapulse.io",
            hashed_password=hash_password("demo123"),
            full_name="Acuarista Arrecifal",
            unit_preference="liters",
            subscription_tier="free",
            created_at=datetime.utcnow()
        )
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)

    # 2. Asegurar al menos un acuario para el usuario demo
    demo_tank = db.query(Tank).filter(Tank.user_id == demo_user.id).first()
    if not demo_tank:
        demo_tank = Tank(
            user_id=demo_user.id,
            name="Arrecife Mixto SPS/LPS",
            tank_type="reef",
            volume_liters=280.0,
            notes="Tanque principal con Acroporas y corales blandos"
        )
        db.add(demo_tank)
        db.commit()
        db.refresh(demo_tank)

    # 3. Vincular mediciones huérfanas al usuario demo
    orphans = db.query(Measurement).filter(Measurement.user_id.is_(None)).all()
    if orphans:
        for m in orphans:
            m.user_id = demo_user.id
            m.tank_id = demo_tank.id
        db.commit()

    # 4. Si no hay mediciones, agregar mediciones de muestra
    count = db.query(Measurement).filter(Measurement.user_id == demo_user.id).count()
    if count == 0:
        print("🌱 Agregando 5 mediciones históricas iniciales...")
        now = datetime.utcnow()
        sample_records = [
            Measurement(
                user_id=demo_user.id,
                tank_id=demo_tank.id,
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
                user_id=demo_user.id,
                tank_id=demo_tank.id,
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
                user_id=demo_user.id,
                tank_id=demo_tank.id,
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
                user_id=demo_user.id,
                tank_id=demo_tank.id,
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
                user_id=demo_user.id,
                tank_id=demo_tank.id,
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
        print("✅ 5 mediciones de prueba creadas para el usuario demo.")
