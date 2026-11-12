"""
Script de simulación de prueba para Verificación de Calidad:
Inserta 5 registros con caída gradual de alcalinidad (de 9.0 dKH a 8.1 dKH en 4 días)
y evalúa las alertas predictivas de estabilización y la proyección del motor.
"""

from datetime import datetime, timedelta
from backend.database import get_db, init_db
from backend.models import Measurement
from backend.analytics import calculate_predictions

def run_simulation():
    init_db()
    db = next(get_db())
    
    try:
        # 1. Limpiar mediciones previas para aislar el escenario de prueba
        deleted = db.query(Measurement).delete()
        db.commit()
        print(f"🧹 Registros anteriores eliminados: {deleted}")

        # 2. Generar 5 registros simulados de caída gradual en 4 días
        now = datetime.utcnow()
        # Día -4: 9.0 dKH
        # Día -3: 8.78 dKH
        # Día -2: 8.55 dKH
        # Día -1: 8.32 dKH
        # Día  0 (hoy): 8.10 dKH
        simulation_data = [
            {"days_ago": 4, "dkh": 9.00, "ca": 440.0, "no3": 5.0, "notes": "Simulación Día 0: Nivel inicial alto"},
            {"days_ago": 3, "dkh": 8.78, "ca": 435.0, "no3": 6.2, "notes": "Simulación Día 1: Inicio de consumo"},
            {"days_ago": 2, "dkh": 8.55, "ca": 430.0, "no3": 7.4, "notes": "Simulación Día 2: Caída constante"},
            {"days_ago": 1, "dkh": 8.32, "ca": 425.0, "no3": 8.6, "notes": "Simulación Día 3: Descenso sostenido"},
            {"days_ago": 0, "dkh": 8.10, "ca": 420.0, "no3": 9.8, "notes": "Simulación Día 4: Lectura actual cerca de umbral"},
        ]

        inserted = []
        for record in simulation_data:
            m = Measurement(
                timestamp=now - timedelta(days=record["days_ago"]),
                alkalinity_dkh=record["dkh"],
                calcium_ppm=record["ca"],
                magnesium_ppm=1350.0,
                nitrate_ppm=record["no3"],
                phosphate_ppm=0.04,
                salinity_ppt=35.0,
                notes=record["notes"]
            )
            db.add(m)
            inserted.append(m)

        db.commit()
        print(f"✅ 5 registros simulados insertados con éxito:")
        for r in inserted:
            print(f"   • Fecha: {r.timestamp.strftime('%Y-%m-%d %H:%M')} | dKH: {r.alkalinity_dkh} | Ca: {r.calcium_ppm} ppm")

        # 3. Ejecutar motor analítico sobre la serie
        all_measurements = db.query(Measurement).order_by(Measurement.timestamp.asc()).all()
        predictions = calculate_predictions(all_measurements)

        print("\n=======================================================")
        print("📊 RESULTADOS DEL MOTOR PREDICTIVO (CALIDAD)")
        print("=======================================================")
        alk = predictions.alkalinity
        print(f"• Parámetro: {alk.parameter}")
        print(f"• Último Valor: {alk.latest_value} {alk.unit}")
        print(f"• Tasa Diaria (Pendiente): {alk.daily_slope} {alk.unit}/día")
        print(f"• Consumo Diario Reportado: {alk.daily_consumption_rate} {alk.unit}/día")
        print(f"• Días Restantes en Rango Seguro (7.5 - 9.0 dKH): {alk.days_remaining_safe} días")
        print(f"• Fecha Estimada de Salida de Rango Seguro: {alk.estimated_exit_date}")
        print(f"• Estado de Alerta: {alk.status}")
        print(f"• Mensaje de Alerta: {alk.alert_message}")

        # Proyección calculada a 3 días:
        proj_3d = alk.latest_value + (alk.daily_slope * 3)
        print(f"\n🔮 PROYECCIÓN A 3 DÍAS:")
        print(f"• Día +1: {alk.latest_value + alk.daily_slope * 1:.3f} dKH")
        print(f"• Día +2: {alk.latest_value + alk.daily_slope * 2:.3f} dKH")
        print(f"• Día +3: {proj_3d:.3f} dKH -> {'⚠️ CRUZA EL LÍMITE INFERIOR (7.5 dKH)' if proj_3d < 7.5 else 'En rango'}")

        # 4. Aserciones de verificación
        assert abs(alk.daily_consumption_rate - 0.225) < 0.05, f"Tasa de consumo inesperada: {alk.daily_consumption_rate}"
        assert alk.days_remaining_safe is not None and abs(alk.days_remaining_safe - 2.7) < 0.5, f"Días restantes inesperados: {alk.days_remaining_safe}"
        assert alk.status == "warning_approaching" or "alerta" in alk.alert_message.lower() or "caerá" in alk.alert_message.lower()
        print("\n🎉 ¡TODAS LAS VALIDACIONES MATEMÁTICAS SUPERADAS CON ÉXITO!")

    finally:
        db.close()

if __name__ == "__main__":
    run_simulation()
