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
| `TRUSTED_PROXY_HOPS` | `1` | Proxies que no se pueden saltar delante de la app (en Render: su balanceador). Ver §5 |
| `PROXY_SHARED_SECRET` | `openssl rand -hex 32` | Mismo valor que `ORIGIN_SECRET` en Vercel; identifica el salto de Vercel. Ver §5 |
| `FORWARDED_ALLOW_IPS` | **no definir** | uvicorn también la lee; con `*` o la red del balanceador reescribe la IP con la primera entrada de `X-Forwarded-For` (falsificable). Ver §5 |
| `CRON_SECRET` | `openssl rand -hex 24` | Token secreto para invocar `/api/cron/send-reminders` |
| `VAPID_PUBLIC_KEY` | Clave pública VAPID | Clave pública para notificaciones Web Push |
| `VAPID_PRIVATE_KEY` | Clave privada VAPID | Clave privada del servidor para firma Web Push |
| `VAPID_CLAIMS_SUB` | `mailto:soporte@tu-dominio.com` | Correo de contacto del operador VAPID |
| `SMTP_HOST` / `SMTP_USER` | Proveedor transaccional | Resend, SendGrid o SMTP para enlaces de recuperación y verificación |

## 5. IP real del cliente detrás de Vercel y Render (rate limits y cuotas)

Los límites de login (`AUTH_RATE_LIMIT_IP_MAX`) y el burst por IP de las cuotas de IA usan
`get_client_ip` (`backend/rate_limits.py`). En producción la petición pasa por dos proxies:

```
navegador ──► Vercel (/api/* → reeftrack-api.onrender.com) ──► balanceador de Render ──► uvicorn
```

### 5.1 Qué cabeceras llegan

- **Vercel** manda al origen externo `x-forwarded-for` y `x-real-ip` con la IP pública del
  visitante, además de `x-forwarded-host` y `x-forwarded-proto`
  ([docs de rewrites](https://vercel.com/docs/rewrites)). Según sus docs sobrescribe el
  `X-Forwarded-For` del visitante para evitar spoofing.
- **Render** *añade* a la derecha de `X-Forwarded-For` la IP que se conectó a su balanceador, pero
  no limpia lo que mande el cliente. El par TCP que ve uvicorn es una IP interna del balanceador.
- Cualquiera puede llamar directo a `reeftrack-api.onrender.com` con un `X-Forwarded-For`,
  `X-Real-IP` o `x-vercel-forwarded-for` inventado, así que ninguna de esas cabeceras prueba por sí
  sola que la petición pasó por Vercel.

| Camino | `X-Forwarded-For` que ve la app | Par TCP |
| :--- | :--- | :--- |
| Vercel → Render | `<visitante>, <salida de Vercel>` | balanceador |
| Directo a Render | `<lo que invente el cliente>, <IP real del cliente>` | balanceador |

### 5.2 Estrategia

1. **Contar saltos desde la derecha, nunca tomar la primera entrada.** Con `TRUSTED_PROXY_HOPS=1`
   la app toma la entrada que añadió Render. En el camino directo eso es la IP real del atacante,
   por mucho que invente a la izquierda.
2. **Secreto compartido para el salto de Vercel.** Solo con la regla 1, todo el tráfico de Vercel
   saldría con las pocas IPs de salida de Vercel y el límite volvería a ser casi global. Vercel
   añade la cabecera `X-Proxy-Secret` con el transform `set` (que pisa cualquier valor que mande el
   visitante); si coincide con `PROXY_SHARED_SECRET` (comparación en tiempo constante), la app
   confía en un salto más y obtiene la IP del visitante. Funciona aunque Vercel anexara en vez de
   sobrescribir, porque sigue contando desde la derecha.
3. Si algo falla la app se equivoca hacia el lado seguro: sin secreto válido agrupa por IP de
   salida de Vercel (más estricto), nunca acepta una IP inventada por el cliente.

### 5.3 Variables en Render (servicio `reeftrack-api`)

| Variable | Valor |
| :--- | :--- |
| `TRUSTED_PROXY_HOPS` | `1` |
| `PROXY_SHARED_SECRET` | `openssl rand -hex 32` (el mismo valor que `ORIGIN_SECRET` en Vercel) |
| `FORWARDED_ALLOW_IPS` | Eliminarla si existe. El valor por defecto (`127.0.0.1,::1`) hace que uvicorn no reescriba la IP del par |

Para rotar el secreto: poner `PROXY_SHARED_SECRET=viejo,nuevo` en Render, cambiar
`ORIGIN_SECRET` en Vercel y redesplegar, y luego dejar solo `nuevo`.

### 5.4 Lado Vercel (lo hace quien mantenga `vercel.json`)

Un `rewrites` no admite transforms de cabeceras de petición; la forma documentada es una entrada
de `routes` con `transforms`. `routes` no se puede mezclar con `rewrites`/`headers` en el mismo
`vercel.json`, así que hay que migrar esas reglas a `routes`. Ejemplo de la regla del API:

```json
{
  "src": "/api/(.*)",
  "dest": "https://reeftrack-api.onrender.com/api/$1",
  "transforms": [
    {
      "type": "request.headers",
      "op": "set",
      "target": { "key": "x-proxy-secret" },
      "args": "$ORIGIN_SECRET",
      "env": ["ORIGIN_SECRET"]
    }
  ]
}
```

`ORIGIN_SECRET` debe existir en el proyecto de Vercel: si falta, Vercel manda el texto literal
`$ORIGIN_SECRET`, que no coincide y la app cae al modo estricto.

### 5.5 Comprobación tras desplegar

Desde dos redes distintas, fallar el login 5 veces desde una: la otra debe poder seguir
intentando. Y llamando directo a `https://reeftrack-api.onrender.com/api/auth/login` con
`X-Forwarded-For: 1.2.3.4` cambiante en cada intento, el sexto debe devolver 429.
