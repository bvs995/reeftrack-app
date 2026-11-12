"""
Catálogo de parámetros estándar para acuarios de arrecife y agua dulce,
con rangos óptimos de seguridad, unidades y umbrales predictivos.
"""

PARAM_CATALOG = {
    # ------------------ ACUARIOS DE ARRECIFE (REEF) ------------------
    "reef": [
        {
            "code": "dkh",
            "name": "Alcalinidad / KH",
            "unit": "dKH",
            "min_safe": 7.0,
            "max_safe": 10.5,
            "optimal_target": 8.3,
            "is_critical": True,
            "daily_consumption_tracked": True,
            "default_test_frequency_days": 2,
            "description": "Fundamental para la calcificación de corales duros (SPS/LPS). Las caídas bruscas causan RTN/STN."
        },
        {
            "code": "ca",
            "name": "Calcio (Ca)",
            "unit": "ppm",
            "min_safe": 380,
            "max_safe": 470,
            "optimal_target": 430,
            "is_critical": True,
            "daily_consumption_tracked": True,
            "default_test_frequency_days": 5,
            "description": "Elemento estructural consumido por corales junto con el KH a ratio balanceado."
        },
        {
            "code": "mg",
            "name": "Magnesio (Mg)",
            "unit": "ppm",
            "min_safe": 1250,
            "max_safe": 1450,
            "optimal_target": 1350,
            "is_critical": False,
            "daily_consumption_tracked": True,
            "default_test_frequency_days": 10,
            "description": "Evita la precipitación prematura de carbonato de calcio."
        },
        {
            "code": "salinity",
            "name": "Salinidad (Gravedad Esp.)",
            "unit": "SG",
            "min_safe": 1.023,
            "max_safe": 1.027,
            "optimal_target": 1.025,
            "is_critical": True,
            "daily_consumption_tracked": False,
            "default_test_frequency_days": 3,
            "description": "Gravedad específica. La estabilidad evita estrés osmótico en peces e invertebrados."
        },
        {
            "code": "temp",
            "name": "Temperatura",
            "unit": "°C",
            "min_safe": 24.0,
            "max_safe": 26.5,
            "optimal_target": 25.2,
            "is_critical": True,
            "daily_consumption_tracked": False,
            "default_test_frequency_days": 1,
            "description": "Rango ideal para arrecifes tropicales."
        },
        {
            "code": "ph",
            "name": "pH",
            "unit": "pH",
            "min_safe": 7.8,
            "max_safe": 8.5,
            "optimal_target": 8.2,
            "is_critical": False,
            "daily_consumption_tracked": False,
            "default_test_frequency_days": 2,
            "description": "Un pH nocturno bajo inhibe el crecimiento de coral. Aumentar con scrubber o aire exterior."
        },
        {
            "code": "no3",
            "name": "Nitrato (NO3)",
            "unit": "ppm",
            "min_safe": 1.0,
            "max_safe": 15.0,
            "optimal_target": 5.0,
            "is_critical": True,
            "daily_consumption_tracked": True,
            "default_test_frequency_days": 7,
            "description": "Nutriente mayor. Evitar cero absoluto (provoca dinoflagelados) y niveles > 20 ppm."
        },
        {
            "code": "po4",
            "name": "Fosfato (PO4)",
            "unit": "ppm",
            "min_safe": 0.02,
            "max_safe": 0.10,
            "optimal_target": 0.05,
            "is_critical": True,
            "daily_consumption_tracked": True,
            "default_test_frequency_days": 7,
            "description": "Nutriente crítico para el color de corales. Debe mantener relación balanceada con NO3."
        }
    ],

    # ------------------ ACUARIOS DE AGUA DULCE PLANTADO (PLANTED) ------------------
    "freshwater_planted": [
        {
            "code": "ph",
            "name": "pH",
            "unit": "pH",
            "min_safe": 6.0,
            "max_safe": 7.2,
            "optimal_target": 6.6,
            "is_critical": True,
            "daily_consumption_tracked": False,
            "default_test_frequency_days": 3,
            "description": "En acuarios con inyección de CO2, un delta de 1.0 unidad respecto al agua desgasificada indica ~30 ppm de CO2."
        },
        {
            "code": "kh",
            "name": "Dureza de Carbonatos (KH)",
            "unit": "dKH",
            "min_safe": 1.0,
            "max_safe": 5.0,
            "optimal_target": 2.5,
            "is_critical": False,
            "daily_consumption_tracked": False,
            "default_test_frequency_days": 7,
            "description": "Buffer para estabilizar el pH contra caídas ácidas."
        },
        {
            "code": "gh",
            "name": "Dureza General (GH)",
            "unit": "dGH",
            "min_safe": 4.0,
            "max_safe": 9.0,
            "optimal_target": 6.0,
            "is_critical": False,
            "daily_consumption_tracked": False,
            "default_test_frequency_days": 10,
            "description": "Calcio y Magnesio disueltos indispensables para la salud celular de plantas y peces."
        },
        {
            "code": "tds",
            "name": "TDS (Sólidos Disueltos)",
            "unit": "ppm",
            "min_safe": 90,
            "max_safe": 220,
            "optimal_target": 140,
            "is_critical": True,
            "daily_consumption_tracked": True,
            "default_test_frequency_days": 2,
            "description": "Indicador global de mineralización y acumulación de abonos o sales."
        },
        {
            "code": "no3",
            "name": "Nitrato (NO3)",
            "unit": "ppm",
            "min_safe": 5.0,
            "max_safe": 25.0,
            "optimal_target": 15.0,
            "is_critical": True,
            "daily_consumption_tracked": True,
            "default_test_frequency_days": 5,
            "description": "Macronutriente N para acuarios plantados (Estimative Index o Lean Dosing)."
        },
        {
            "code": "po4",
            "name": "Fosfato (PO4)",
            "unit": "ppm",
            "min_safe": 0.5,
            "max_safe": 2.5,
            "optimal_target": 1.2,
            "is_critical": True,
            "daily_consumption_tracked": True,
            "default_test_frequency_days": 5,
            "description": "Macronutriente P. Previene alga punto verde si se mantiene en ratio 10:1 respecto al NO3."
        },
        {
            "code": "k",
            "name": "Potasio (K)",
            "unit": "ppm",
            "min_safe": 10.0,
            "max_safe": 25.0,
            "optimal_target": 18.0,
            "is_critical": False,
            "daily_consumption_tracked": True,
            "default_test_frequency_days": 7,
            "description": "Macronutriente esencial. Previene agujeros necrosados en hojas viejas."
        },
        {
            "code": "temp",
            "name": "Temperatura",
            "unit": "°C",
            "min_safe": 22.0,
            "max_safe": 26.0,
            "optimal_target": 24.0,
            "is_critical": True,
            "daily_consumption_tracked": False,
            "default_test_frequency_days": 1,
            "description": "Temperaturas más altas (>27°C) aumentan el metabolismo y aceleran la formación de algas."
        }
    ],

    # ------------------ AGUA DULCE COMUNITARIO ------------------
    "freshwater_community": [
        {
            "code": "ph",
            "name": "pH",
            "unit": "pH",
            "min_safe": 6.5,
            "max_safe": 7.8,
            "optimal_target": 7.2,
            "is_critical": True,
            "daily_consumption_tracked": False,
            "default_test_frequency_days": 7,
            "description": "Rango neutro para peces tropicales comunitarios."
        },
        {
            "code": "temp",
            "name": "Temperatura",
            "unit": "°C",
            "min_safe": 24.0,
            "max_safe": 27.0,
            "optimal_target": 25.5,
            "is_critical": True,
            "daily_consumption_tracked": False,
            "default_test_frequency_days": 1,
            "description": "Temperatura óptima tropical comunitaria."
        },
        {
            "code": "nh3",
            "name": "Amonio / Amoníaco (NH3/NH4+)",
            "unit": "ppm",
            "min_safe": 0.0,
            "max_safe": 0.25,
            "optimal_target": 0.0,
            "is_critical": True,
            "daily_consumption_tracked": False,
            "default_test_frequency_days": 7,
            "description": "Tóxico. Debe mantenerse siempre indetectable en un acuario ciclado."
        },
        {
            "code": "no2",
            "name": "Nitrito (NO2)",
            "unit": "ppm",
            "min_safe": 0.0,
            "max_safe": 0.1,
            "optimal_target": 0.0,
            "is_critical": True,
            "daily_consumption_tracked": False,
            "default_test_frequency_days": 7,
            "description": "Tóxico para el transporte de oxígeno en peces. Cero en acuarios maduros."
        },
        {
            "code": "no3",
            "name": "Nitrato (NO3)",
            "unit": "ppm",
            "min_safe": 0.0,
            "max_safe": 30.0,
            "optimal_target": 10.0,
            "is_critical": True,
            "daily_consumption_tracked": True,
            "default_test_frequency_days": 7,
            "description": "Subproducto final del ciclo del nitrógeno. Su tasa de acumulación define la frecuencia de cambios de agua."
        }
    ]
}

def get_parameters_for_type(tank_type: str):
    if tank_type in PARAM_CATALOG:
        return PARAM_CATALOG[tank_type]
    return PARAM_CATALOG["reef"]
