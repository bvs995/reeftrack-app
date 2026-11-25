"""Regresión: las fechas que devuelve la base de datos son 'naive' (sin zona horaria) y el motor
de proyecciones las comparaba con datetime.now(timezone.utc), lo que lanzaba TypeError."""
from datetime import datetime, timedelta, timezone

from backend.analytics import _as_utc, calculate_predictions
from backend.models import Measurement


def test_as_utc_acepta_fechas_naive_y_aware():
    naive = datetime(2026, 11, 20, 12, 0, 0)
    aware = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
    assert _as_utc(naive) == aware
    assert _as_utc(aware) == aware
    assert _as_utc(naive) < datetime.now(timezone.utc)  # antes lanzaba TypeError


def test_calculate_predictions_con_fechas_naive_no_falla():
    base = datetime.utcnow().replace(tzinfo=None)  # igual que las devuelve la BD
    mediciones = [
        Measurement(timestamp=base - timedelta(days=d), kh=8.0 - 0.1 * (6 - d), calcium=420.0 - 2 * (6 - d))
        for d in range(6, -1, -1)
    ]
    resultado = calculate_predictions(mediciones)
    assert resultado is not None
