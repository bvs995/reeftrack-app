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

-- ==============================================================================
-- 4. Consulta de Auditoría y Verificación de Llaves Foráneas (PostgreSQL)
-- ==============================================================================
-- Ejecuta esta consulta en psql o tu cliente SQL para verificar la restricción:
/*
SELECT
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name 
FROM 
    information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.schema_name = tc.table_schema
WHERE 
    tc.constraint_type = 'FOREIGN KEY' 
    AND tc.table_name='mediciones';
*/
