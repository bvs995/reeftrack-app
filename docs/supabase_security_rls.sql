-- ==============================================================================
-- AQUAPULSE - POLÍTICAS DE SEGURIDAD RLS (SUPABASE / POSTGRESQL) Y ROL SIN DDL
-- ==============================================================================
--
-- ⚠️ NO EJECUTAR TAL CUAL. Se conserva como referencia.
-- El backend se conecta como dueño de las tablas y nunca fija app.current_user_id,
-- así que el FORCE ROW LEVEL SECURITY de abajo le ocultaría todas las filas y la app
-- dejaría de funcionar. Además omite varias tablas (tokens, auditorías, cuotas).
-- La protección vigente está en la migración de Alembic
-- alembic/versions/8a9b0c1d2e3f_enable_rls_and_lock_supabase_api_roles.py
-- (RLS sin políticas en todo public + REVOKE a anon/authenticated), y
-- scripts/verify_migrations.py comprueba que siga así.

-- 1. CREACIÓN DE USUARIO DE APLICACIÓN CON PRIVILEGIOS MÍNIMOS (SIN PERMISOS DDL)
-- ------------------------------------------------------------------------------
-- Este usuario se utiliza exclusivamente para la ejecución en producción de FastAPI
-- impidiendo que cualquier vulnerabilidad web pueda ejecutar CREATE, ALTER o DROP.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'aquapulse_app') THEN
        CREATE ROLE aquapulse_app WITH LOGIN PASSWORD 'REEMPLAZAR_CON_PASSWORD_SEGURA';
    END IF;
END
$$;

-- Otorgar conexión y uso del esquema
GRANT CONNECT ON DATABASE postgres TO aquapulse_app;
GRANT USAGE ON SCHEMA public TO aquapulse_app;

-- Otorgar estrictamente permisos DML (Lectura y Escritura de datos)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aquapulse_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO aquapulse_app;

-- Configurar privilegios predeterminados para futuras tablas creadas por migraciones de Alembic
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aquapulse_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO aquapulse_app;

-- REVOCAR explícitamente cualquier permiso de creación o modificación estructural (DDL)
REVOKE CREATE ON SCHEMA public FROM aquapulse_app;


-- 2. HABILITACIÓN DE ROW LEVEL SECURITY (RLS) EN TODAS LAS TABLAS
-- ------------------------------------------------------------------------------
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE tanks ENABLE ROW LEVEL SECURITY;
ALTER TABLE measurements ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE water_changes ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_subscriptions ENABLE ROW LEVEL SECURITY;

-- Tablas legacy de interoperabilidad si existen
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'acuarios') THEN
        ALTER TABLE acuarios ENABLE ROW LEVEL SECURITY;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'mediciones') THEN
        ALTER TABLE mediciones ENABLE ROW LEVEL SECURITY;
    END IF;
END
$$;


-- 3. POLÍTICAS DE AISLAMIENTO POR PROPIETARIO DE DATOS (USER_ID)
-- ------------------------------------------------------------------------------
-- Para Supabase Auth (auth.uid()) o variables de sesión de aplicación (app.current_user_id)

-- Users: Cada usuario solo ve y modifica su propia cuenta
DROP POLICY IF EXISTS users_owner_policy ON users;
CREATE POLICY users_owner_policy ON users
    FOR ALL
    USING (
        id = NULLIF(current_setting('app.current_user_id', true), '')::integer
        OR (auth.uid() IS NOT NULL AND id = auth.uid()::text::integer)
    );

-- Tanks: Aislamiento por user_id
DROP POLICY IF EXISTS tanks_owner_policy ON tanks;
CREATE POLICY tanks_owner_policy ON tanks
    FOR ALL
    USING (
        user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
        OR (auth.uid() IS NOT NULL AND user_id = auth.uid()::text::integer)
    )
    WITH CHECK (
        user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
        OR (auth.uid() IS NOT NULL AND user_id = auth.uid()::text::integer)
    );

-- Measurements: Aislamiento por user_id
DROP POLICY IF EXISTS measurements_owner_policy ON measurements;
CREATE POLICY measurements_owner_policy ON measurements
    FOR ALL
    USING (
        user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
        OR (auth.uid() IS NOT NULL AND user_id = auth.uid()::text::integer)
    )
    WITH CHECK (
        user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
        OR (auth.uid() IS NOT NULL AND user_id = auth.uid()::text::integer)
    );

-- Maintenance Tasks: Aislamiento por user_id
DROP POLICY IF EXISTS maintenance_tasks_owner_policy ON maintenance_tasks;
CREATE POLICY maintenance_tasks_owner_policy ON maintenance_tasks
    FOR ALL
    USING (
        user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
        OR (auth.uid() IS NOT NULL AND user_id = auth.uid()::text::integer)
    )
    WITH CHECK (
        user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
        OR (auth.uid() IS NOT NULL AND user_id = auth.uid()::text::integer)
    );

-- Water Changes: Aislamiento por user_id
DROP POLICY IF EXISTS water_changes_owner_policy ON water_changes;
CREATE POLICY water_changes_owner_policy ON water_changes
    FOR ALL
    USING (
        user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
        OR (auth.uid() IS NOT NULL AND user_id = auth.uid()::text::integer)
    )
    WITH CHECK (
        user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
        OR (auth.uid() IS NOT NULL AND user_id = auth.uid()::text::integer)
    );

-- Push Subscriptions: Aislamiento por user_id
DROP POLICY IF EXISTS push_subscriptions_owner_policy ON push_subscriptions;
CREATE POLICY push_subscriptions_owner_policy ON push_subscriptions
    FOR ALL
    USING (
        user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
        OR (auth.uid() IS NOT NULL AND user_id = auth.uid()::text::integer)
    )
    WITH CHECK (
        user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
        OR (auth.uid() IS NOT NULL AND user_id = auth.uid()::text::integer)
    );

-- Bypass de RLS para el rol postgres / service_role (usado por backend en pooler y migraciones Alembic)
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE tanks FORCE ROW LEVEL SECURITY;
ALTER TABLE measurements FORCE ROW LEVEL SECURITY;
ALTER TABLE maintenance_tasks FORCE ROW LEVEL SECURITY;
ALTER TABLE water_changes FORCE ROW LEVEL SECURITY;
ALTER TABLE push_subscriptions FORCE ROW LEVEL SECURITY;
