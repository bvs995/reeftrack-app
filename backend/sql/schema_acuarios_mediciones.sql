-- ==============================================================================
-- AquaPulse — Esquema Oficial PostgreSQL para Acuarios y Mediciones
-- ==============================================================================

-- 1. Tabla principal de Acuarios
CREATE TABLE IF NOT EXISTS acuarios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    volumen_litros NUMERIC(10, 2) NOT NULL,
    usuario_id VARCHAR(100) NOT NULL, -- Relación con el usuario (si aplica)
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabla de Mediciones relacionada con Acuarios
CREATE TABLE IF NOT EXISTS mediciones (
    id SERIAL PRIMARY KEY,
    acuario_id INTEGER NOT NULL,
    ph NUMERIC(4, 2),
    kh NUMERIC(4, 2),
    calcio NUMERIC(7, 2),
    magnesio NUMERIC(7, 2),
    nitrato NUMERIC(7, 2),
    fosfato NUMERIC(6, 4),
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Definición estricta de la Llave Foránea
    CONSTRAINT fk_acuario_medicion
        FOREIGN KEY (acuario_id) 
        REFERENCES acuarios(id) 
        ON DELETE CASCADE
);

-- 3. Índices de aceleración para consultas temporales de 48h
CREATE INDEX IF NOT EXISTS idx_mediciones_acuario_fecha 
    ON mediciones (acuario_id, fecha_registro DESC);

CREATE INDEX IF NOT EXISTS idx_acuarios_usuario 
    ON acuarios (usuario_id);
