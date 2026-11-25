# 🚀 Guía de Despliegue y Operación en Producción (AquaPulse)

**Versión**: 1.0 (Hardening para Play Store y SaaS Multi-usuario)

---

## 1. Requisitos Críticos de Hosting (Sin Pausa por Inactividad)

> [!IMPORTANT]
> **Plan de Hosting Sin Pausa Obligatorio**: AquaPulse **no debe** desplegarse en planes gratuitos con suspensión por inactividad (como Render Free Web Service).

### 1.1 Razón Técnica y de Bioseguridad
* **Arranques en frío (Cold Starts)**: Los planes gratuitos pausan los contenedores tras 15 minutos sin tráfico, ocasionando retardos de arranque de más de 50 segundos. Esto provoca errores de timeout en la cola offline de la PWA móvil y degradación del servicio.
* **Cron Jobs y Recordatorios Diarios**: La ejecución programada de `/api/cron/send-reminders` requiere que el backend esté disponible para despachar alertas de mantenimiento y desvíos biológicos críticos a los dispositivos de los usuarios.

### 1.2 Proveedores Recomendados
* **Render**: Plan `Starter` o superior (garantiza `minInstances: 1`, sin auto-sleep).
* **Railway / Fly.io / VPS**: Configurado con un mínimo de 1 réplica siempre activa y 512 MB a 1 GB de RAM.
* **Workers Uvicorn**: Configurar variable `WORKERS=2` para 512 MB de RAM o `WORKERS=4` para 1 GB de RAM.

---

## 2. Base de Datos en Producción (PostgreSQL)

* **Proveedor**: Supabase PostgreSQL o Render Managed PostgreSQL.
* **Conexión Cifrada**: Usar siempre cadena de conexión con SSL obligatorio (`sslmode=require`).
* **Migraciones Automáticas**: El arranque del contenedor ejecuta automáticamente `alembic upgrade head` para sincronizar el esquema sin pérdida de datos.

---

## 3. Backups Automáticos y Recuperación ante Desastres (Disaster Recovery)

AquaPulse implementa un protocolo riguroso de respaldos con paridad comprobada al 100%:

### 3.1 Backups Diarios Automatizados
* El workflow `.github/workflows/backup.yml` se ejecuta diariamente a las **03:00 UTC**.
* Ejecuta un volcado completo de la base de datos y realiza un simulacro de restauración en base de datos aislada temporal para certificar paridad de filas (`COUNT(*)` idéntico en todas las tablas críticas).

### 3.2 CLI de Respaldo y Restauración
El módulo `backend/backup.py` provee una interfaz de línea de comandos para operaciones de contingencia:

```bash
# 1. Ejecutar simulacro completo de respaldo, restauración y paridad:
python -m backend.backup --drill

# 2. Generar un respaldo SQL manual:
python -m backend.backup --backup /ruta/segura/respaldo_manual.sql

# 3. Restaurar un respaldo en una base de datos de contingencia:
python -m backend.backup --restore /ruta/segura/respaldo_manual.sql --target postgresql://usuario:pass@host:5432/aquapulse_db
```

---

## 4. Configuración de Variables de Entorno en Producción

Configurar estrictamente las siguientes variables en el panel del proveedor:

| Variable | Valor Requerido | Descripción |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Desactiva `/docs`, activa CSP estricta, HSTS y validaciones de seguridad |
| `DATABASE_URL` | `postgresql://...` | Cadena de conexión PostgreSQL con SSL |
| `SECRET_KEY` | `openssl rand -hex 32` | Llave criptográfica para firmas JWT y tokens |
| `GEMINI_API_KEY` | `AIzaSy...` | Clave de Google Gemini vinculada a cuenta de facturación |
| `GEMINI_TIER` | `pay-as-you-go` | **Obligatorio**: Nivel de pago para impedir uso de datos de usuarios en entrenamiento de modelos |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Modelo multimodal de alta velocidad y precisión |
| `ALLOWED_ORIGINS` | `https://tu-dominio.com` | Lista blanca estricta de dominios permitidos para CORS (nunca `*`) |
| `FORWARDED_ALLOW_IPS` | `10.0.0.0/8,172.16.0.0/12` | IPs de balanceadores de carga / proxies de confianza para Anti-Spoofing |
| `CRON_SECRET` | `openssl rand -hex 24` | Token secreto para invocar `/api/cron/send-reminders` |
| `VAPID_PUBLIC_KEY` | Clave pública VAPID | Clave pública para notificaciones Web Push |
| `VAPID_PRIVATE_KEY` | Clave privada VAPID | Clave privada del servidor para firma Web Push |
| `VAPID_CLAIMS_SUB` | `mailto:soporte@tu-dominio.com` | Correo de contacto del operador VAPID |
| `SMTP_HOST` / `SMTP_USER` | Proveedor transaccional | Resend, SendGrid o SMTP para enlaces de recuperación y verificación |
