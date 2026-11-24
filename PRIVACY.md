# 🔒 Política de Privacidad de AquaPulse (Privacy Policy)

**Fecha de entrada en vigor**: 23 de noviembre de 2026  
**Versión**: 1.0 (Alineada con directrices de Google Play Store, GDPR y CCPA)

AquaPulse ("la Aplicación", "nosotros", "nuestro") respeta y protege la privacidad de sus usuarios. Esta Política de Privacidad describe de manera transparente qué datos recopilamos, cómo los procesamos, cómo los protegemos y cómo puedes ejercer tus derechos sobre tu información personal.

---

## 1. Responsable del Tratamiento de Datos

* **Responsable**: Equipo de Desarrollo AquaPulse
* **Contacto de Privacidad**: `privacy@aquapulse.io` o `paliyo995@gmail.com`
* **Sitio Web / Aplicación**: AquaPulse PWA (Arrecifes y Acuarios)

---

## 2. Información que Recopilamos

### 2.1 Datos de la Cuenta de Usuario
* **Datos recopilados**: Correo electrónico, nombre completo o alias y contraseña cifrada.
* **Finalidad**: Crear y gestionar tu cuenta de usuario, autenticar el inicio de sesión y aislar tus acuarios respecto a los de otros usuarios (Anti-IDOR).

### 2.2 Datos de Acuarios y Telemetría Química
* **Datos recopilados**: Parámetros de agua registrados por el usuario (pH, KH / Alcalinidad, Calcio, Magnesio, Nitrato, Fosfato, Salinidad, Temperatura, Amoníaco, Nitrito, elementos traza), volumen del tanque, biotipo (SPS, LPS, mixto, peces, plantado, agua dulce), bitácora de tareas mecánicas y cambios de agua.
* **Finalidad**: Evaluar la estabilidad físico-química del acuario, proyectar consumos, predecir cambios de agua y alertar sobre desviaciones biopeligrosas.

### 2.3 Procesamiento de Imágenes por Cámara (Escaneo de Tests)
* **Datos procesados**: Fotografías de viales colorimétricos, fotómetros digitales o kits de test capturadas por la cámara del dispositivo.
* **Tratamiento estricto**:
  * Las imágenes se procesan de forma efímera para la extracción de lectura visual.
  * **Eliminación de metadatos**: Se eliminan automáticamente todos los metadatos EXIF, coordenadas de GPS y marcas de dispositivo mediante sanitización en servidor antes de la inferencia.
  * **Carácter de borrador**: Toda lectura visual es un borrador no confirmado.
  * **No almacenamiento**: La imagen capturada **no se guarda permanentemente** en nuestros servidores ni en bases de datos salvo que el usuario lo solicite expresamente.

### 2.4 Notificaciones Web Push (VAPID)
* **Datos recopilados**: Endpoint del servidor push, claves criptográficas públicas de suscripción (`p256dh` y `auth`).
* **Finalidad**: Enviar recordatorios programados de mantenimiento mecánico y alertas de bioseguridad inmediata ante parámetros críticos.
* **Control**: El usuario puede activar, desactivar o revocar estas notificaciones en cualquier momento desde la configuración de la app o de su navegador/dispositivo.

---

## 3. Inteligencia Artificial y Procesamiento de Datos (Carácter Orientativo)

* **Diagnóstico Orientativo Asistido por IA**: Todos los análisis predictivos, evaluaciones de estabilidad y recomendaciones emitidas por la plataforma y sus modelos de Inteligencia Artificial son de **carácter estrictamente orientativo y preventivo**. No garantizan resultados biológicos ni reemplazan el criterio del acuarista. El usuario siempre debe contrastar cualquier alerta mediante un retest manual antes de realizar adiciones o cambios químicos.
* **Motor Predictivo (Google Gemini API)**: Los diagnósticos clínicos se asisten mediante llamadas a la API empresarial de Google Gemini. A la IA se le remiten únicamente valores químicos despersonalizados, biotipo del tanque y volúmenes métricos. **Nunca** se transmiten nombres reales, correos electrónicos ni información de geolocalización a los modelos de lenguaje.
* **Reportes de Inconsistencia y Consentimiento**: El botón *"Reportar diagnóstico incorrecto"* exige un consentimiento explícito previo del usuario (`consent_given=True`) para transferir de forma anónima los datos de una lectura y auditar la precisión del modelo.

---

## 4. Finalidad y Bases Legales del Tratamiento

Tratamos tus datos bajo las siguientes bases legales:
1. **Ejecución de un contrato**: Prestación del servicio de gestión de acuarios y cálculo de intervalos de seguridad.
2. **Consentimiento explícito**: Procesamiento de escaneos de cámara, notificaciones push y reportes de auditoría de IA.
3. **Interés legítimo**: Prevención de colapso de biomas acuáticos, auditoría de seguridad del servicio y detección de abusos o ataques de fuerza bruta.

---

## 5. Divulgación y Transferencia a Terceros

**No vendemos, alquilamos ni comercializamos tus datos personales con terceros para fines publicitarios o comerciales.**

Compartimos datos únicamente con los siguientes proveedores de infraestructura necesarios para la operatividad:
* **Alojamiento y Base de Datos**: Servidores de PostgreSQL seguros (Supabase / Render) con cifrado en tránsito (TLS 1.3) y en reposo.
* **Inferencia de IA**: Google Cloud / Google Gemini API (Nivel Comercial de Pago / Pay-As-You-Go). De acuerdo con las condiciones contractuales de Google Cloud para cuentas de pago, los datos de los usuarios (prompts de telemetría e imágenes) **no se utilizan para entrenar ni mejorar los modelos de Google**.

---

## 6. Seguridad de la Información

Implementamos medidas técnicas y organizativas de nivel de producción:
* Cifrado en tránsito mediante HTTPS/TLS obligatorio y políticas estrictas de cabeceras de seguridad (HSTS, CSP, X-Content-Type-Options, Frame Deny).
* Cifrado de contraseñas con `bcrypt` (coste \(\ge 12\)).
* Sesiones autenticadas mediante tokens JWT de 15 minutos y cookies de refresco `HttpOnly`, `Secure` y `SameSite=Lax`.
* Aislamiento estricto de rutas `/api/*` respecto a la caché local del Service Worker (`sw.js`).
* Verificación periódica contra dependencias vulnerables (0 vulnerabilidades reportadas en `pip-audit` y `npm audit`).

---

## 7. Derechos del Usuario (Acceso, Rectificación y Borrado - GDPR / CCPA)

Como usuario de AquaPulse, tienes derecho a:
1. **Acceso y Portabilidad**: Puedes solicitar y descargar una copia completa de tus acuarios, mediciones y configuraciones en formato estructurado JSON en cualquier momento mediante las opciones de perfil o exportación.
2. **Rectificación**: Puedes editar o corregir cualquier medición o acuario directamente desde la interfaz.
3. **Borrado y Eliminación Total ("Derecho al Olvido")**: Puedes solicitar en cualquier momento la supresión completa, inmediata e irreversible de tu cuenta y todos tus datos asociados mediante el endpoint seguro `/api/user/account` (con confirmación de contraseña y periodo de gracia opcional de 7 días).
4. **Revocación del Consentimiento**: Puedes revocar el permiso de notificaciones push o de escaneo por cámara en cualquier momento en las preferencias de tu perfil.

---

## 8. Privacidad de Menores (COPPA)

AquaPulse no está dirigida a menores de 13 años. No recopilamos conscientemente información personal de niños. Si detectamos que un menor de 13 años nos ha proporcionado información personal, procederemos a eliminarla de inmediato.

---

## 9. Cambios a esta Política de Privacidad

Nos reservamos el derecho de actualizar esta Política de Privacidad para reflejar cambios normativos o nuevas funcionalidades de la aplicación. Te notificaremos cualquier modificación relevante mediante un aviso visible dentro de la aplicación.

---

## 10. Contacto

Para ejercer tus derechos o realizar cualquier consulta relacionada con el tratamiento de tus datos, contáctanos en:
* **Correo electrónico**: `privacy@aquapulse.io`
* **Soporte técnico**: `paliyo995@gmail.com`
