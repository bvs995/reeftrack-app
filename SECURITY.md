# 🛡️ Política de Seguridad de AquaReef

Fecha de última actualización: 23 de noviembre de 2026  
Versión: 1.0.0 (Fases 1 a 7)

AquaReef es una plataforma progresiva (PWA) y motor analítico diseñado para el monitoreo biológico y físico-químico de ecosistemas acuáticos y arrecifes de coral. Dado que una falla de software o una recomendación errónea puede comprometer la vida de organismos vivos, la seguridad, la confidencialidad de los datos y la robustez de los cálculos metrológicos son prioritarios en nuestra arquitectura.

---

## 1. Notificación Responsable de Vulnerabilidades

Si descubres una vulnerabilidad de seguridad en AquaReef, te agradecemos que nos la comuniques de manera responsable y confidencial:

* **Correo de Seguridad**: `security@aquareef.app` o `paliyo995@gmail.com`
* **Tiempo de Respuesta Inicial**: Menos de 24 horas.
* **Proceso**:
  1. Envía un reporte detallado con los pasos para reproducir la vulnerabilidad (PoC).
  2. No divulgues públicamente la vulnerabilidad hasta que hayamos publicado una corrección oficial.
  3. No intentes acceder a datos de otros usuarios ni degradar la disponibilidad del servicio.

---

## 2. Arquitectura de Defensa en Profundidad

AquaReef implementa un modelo de seguridad por capas en todas las etapas del ciclo de vida del software:

### 2.1 Gestión Estricta de Secretos
* **Sin Secretos en el Repositorio**: El código fuente en Git está libre de credenciales, contraseñas o claves privadas. El archivo `.env.example` incluye únicamente plantillas documentadas sin valores reales.
* **Falla en el Arranque**: La aplicación rehúsa iniciar si no se provee una variable `SECRET_KEY` criptográficamente segura (mínimo 32 bytes).
* **Auditoría Continua**: Escaneo periódico con `pip-audit` y `npm audit` para prevenir dependencias vulnerables (0 vulnerabilidades conocidas).

### 2.2 Control de Propietario de Datos y Protección Anti-IDOR
* **Aislamiento por Usuario**: Todo endpoint que manipula un recurso (`tank_id`, `measurement_id`, `maintenance_task_id`, `water_change_id`, etc.) valida en base de datos que el recurso pertenezca estrictamente al `user_id` del token JWT autenticado.
* **Respuestas Neutras**: Los intentos de acceso no autorizado a recursos ajenos devuelven `404 Not Found` en lugar de `403 Forbidden` para mitigar la enumeración de identificadores.

### 2.3 Autenticación y Criptografía de Sesión
* **Hashing de Contraseñas**: Uso obligatorio de `bcrypt` con un factor de coste \(\ge 12\).
* **Tokens de Vida Corta**: Access Tokens JWT con expiración estricta de 15 minutos.
* **Refresh Tokens Rotativos**: Almacenados exclusivamente en cookies con directivas de máxima seguridad:
  `HttpOnly; Secure; SameSite=Lax; Path=/api/auth`
  Esto protege las sesiones contra ataques XSS (Cross-Site Scripting) y CSRF.
* **Rate Limiting**: Protección activa contra ataques de fuerza bruta en `/api/auth/*` mediante limitación temporal de intentos por IP.
* **Anti-Enumeración**: Mensajes de error genéricos en login y recuperación de contraseña (*"Credenciales incorrectas"*).
* **Comparación en Tiempo Constante**: Validación de tokens cron (`X-CRON-SECRET`) mediante `secrets.compare_digest` para evitar ataques de temporización (*timing attacks*).

### 2.4 Metrología de Incertidumbre y Protección Anti-Colapso
* **Tratamiento por Intervalos**: Toda medición \(v\) con kit de test se procesa como intervalo \([v - e, v + e]\), donde \(e\) es el error metrológico (Hanna, Salifert, Red Sea).
* **Alertas Confirmadas vs. Probables**:
  * *Confirmada*: Todo el intervalo cruza el umbral seguro.
  * *Probable*: Solo parte del intervalo cruza el umbral \(\to\) Severidad `watch` y retest obligatorio en 1–2 horas; nunca se oculta ni se genera pánico innecesario.
* **Regla Anti-Colapso**: Si la desviación es menor que el error de medición, el sistema prohíbe dosificar: *"Dentro del margen de error, repite la prueba"*.
* **Ajuste Diario Limitado**: El cambio diario máximo sugerido nunca supera:
  \[\Delta_{\text{máximo\_diario}} = \text{límite\_diario} - u\]

### 2.5 Verificación y Contención de la Inteligencia Artificial
* **La IA Explica, las Reglas Deciden**: Gemini analiza contexto biológico, pero las alertas determinísticas de las reglas son inapelables. La IA **nunca** puede rebajar la severidad calculada por las reglas.
* **Catálogo Cerrado de Acciones**: La IA solo puede seleccionar acciones de una lista estricta:
  `["retest_parameter", "monitor_24h", "pause_dosing", "water_change_small", "check_equipment", "consult_expert"]`.
* **Prohibición de Dosis**: Prohibido estrictamente sugerir cantidades, gramos o mililitros de productos químicos en respuestas de IA.
* **Anti-Alucinación y Doble Pasada**: Si la IA cita números que no existen en las mediciones o en sus intervalos de error, el hallazgo se descarta. Si dos evaluaciones difieren, se adopta la más conservadora y se reduce la certeza.
* **Resiliencia Operativa sin 500**: Ante caídas de red, timeouts o JSON corrupto de la IA, el sistema conmuta automáticamente a diagnóstico por reglas determinísticas con aviso legal.

### 2.6 Seguridad PWA y Almacenamiento Local
* **Aislamiento de API en Service Worker**: `sw.js` excluye expresamente `/api/*` del `CacheStorage` para garantizar que datos privados de química y tokens nunca queden cacheados en disco o dispositivos compartidos.
* **Cero `dangerouslySetInnerHTML`**: Todo el frontend en React escapa automáticamente el DOM para erradicar inyecciones de código.
* **Idempotencia Offline**: Las mediciones encoladas offline en IndexedDB portan un `client_uuid` único que previene registros duplicados en reintentos.

### 2.7 Auditoría y Presupuesto Operativo
* **Trazabilidad por Diagnóstico**: Registro en base de datos de versión de prompt, entradas, alertas de reglas, salida cruda, latencia, tokens y costo en USD.
* **Alerta de Tasa de Descarte**: Si más del 25% de las respuestas de IA son descartadas por el validador, se emite una alerta operativa.
* **Límite de Presupuesto**: Toque mensual de gasto (`GEMINI_MONTHLY_BUDGET_USD`). Al superarse, el sistema conmuta al motor determinístico sin costo y sin interrupción de servicio.

---

## 3. Conformidad y Cumplimiento Normativo
* **GDPR / CCPA**: Endpoints para descarga completa de datos (`GET /api/account/export`) y eliminación irreversible de cuenta (`DELETE /api/account/delete`).
* **Google Play Policy**: Cero almacenamiento permanente de capturas de cámara sin confirmación explícita del usuario; consentimiento explícito obligatorio en reportes de feedback.
* **Google Gemini Paid Tier (P3.19)**: En producción es obligatorio el uso de `GEMINI_TIER=pay-as-you-go` o de pago. Los datos de telemetría e imágenes de los usuarios no son utilizados por Google para entrenar sus modelos.
