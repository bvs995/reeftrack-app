# Política de Privacidad de AquaReef

**Fecha de entrada en vigor**: 25 de noviembre de 2026
**Versión**: 1.1

<!-- NOTA PARA REVISIÓN LEGAL: borrador redactado a partir de lo que hace la app (no es asesoría legal). Revisar contra la LFPDPPP vigente (aviso de privacidad integral, derechos ARCO, transferencias), y GDPR/CCPA si habrá usuarios en la UE o California. Completar los datos marcados entre corchetes antes de publicar. -->

Esta Política de Privacidad (aviso de privacidad) explica qué datos personales trata AquaReef ("la Aplicación", "nosotros"), para qué los usamos, con quién los compartimos, cuánto tiempo los conservamos y cómo puedes ejercer tus derechos.

---

## 1. Responsable

* **Responsable**: Brandon Valadez Serrano
* **Domicilio**: Av. Guadalajara 17, Col. Vergel de Guadalupe, C.P. 57150, Nezahualcóyotl, Estado de México, México
* **Contacto de privacidad**: `privacy@aquareef.app`
* **Sitio y aplicación**: `https://www.aquareef.app` (web y app instalable)

---

## 2. Datos que tratamos

### 2.1 Datos de tu cuenta
* Correo electrónico, nombre o alias, contraseña (guardada solo como hash `bcrypt`, nunca en texto plano), preferencia de unidades, plan (Free o Premium) y si verificaste tu correo.
* **Para qué**: crear tu cuenta, iniciar sesión, enviarte el correo de verificación y de recuperación de contraseña, y separar tus datos de los de otros usuarios.

### 2.2 Datos de tus acuarios
* Nombre y volumen del acuario, tipo (arrecife, agua dulce, etc.), parámetros del agua que registras (pH, KH, calcio, magnesio, nitrato, fosfato, salinidad, temperatura, amoníaco, nitrito, elementos traza), notas, método de prueba, tareas de mantenimiento y cambios de agua.
* **Para qué**: mostrarte tendencias, calcular proyecciones, generar alertas y recordatorios.

### 2.3 Fotos de pruebas (escaneo con cámara)
* Cuando usas el escaneo, la foto de tu kit o fotómetro se envía a nuestro servidor, que **elimina sus metadatos EXIF** (incluida la ubicación GPS) y la envía a Google Gemini para leer el valor.
* La lectura obtenida es un **borrador**: no se guarda como medición hasta que tú la confirmas o corriges.
* **Las fotos no se guardan**: se procesan en memoria y se descartan.

### 2.4 Diagnósticos con IA
* Para cada diagnóstico guardamos un registro con los valores que se analizaron, las alertas de reglas y la respuesta del modelo.
* **Para qué**: revisar la calidad y seguridad de los diagnósticos y controlar el gasto del servicio.
* Si usas "Reportar diagnóstico incorrecto", guardamos tu comentario solo si das tu consentimiento en ese momento.

### 2.5 Notificaciones push
* Si las activas, guardamos la dirección de suscripción que entrega tu navegador (endpoint y claves `p256dh` y `auth`).
* **Para qué**: enviarte recordatorios de mantenimiento y alertas de parámetros críticos. Puedes desactivarlas en cualquier momento desde la app o desde tu navegador.

### 2.6 Datos técnicos y de seguridad
* **Dirección IP y correo usado en intentos de inicio de sesión**, para limitar intentos y frenar ataques de fuerza bruta.
* Cookie de sesión `HttpOnly` necesaria para mantenerte conectado. No usamos cookies de publicidad ni de rastreo.
* Nuestros proveedores de alojamiento registran datos técnicos de las conexiones (como IP, fecha y ruta solicitada) para operar y proteger el servicio.

---

## 3. Inteligencia artificial (carácter orientativo)

* Los diagnósticos, proyecciones y recomendaciones son de **carácter orientativo y preventivo**. No garantizan resultados ni sustituyen tu criterio: verifica cualquier alerta con un retest antes de añadir productos o hacer cambios.
* Usamos la **API de Google Gemini en nivel de pago**. Según las condiciones de Google para ese nivel, los datos enviados **no se usan para entrenar sus modelos**.
* A Gemini enviamos los valores de tus parámetros, el tipo y volumen del acuario y, si usas el escaneo, la foto sin metadatos. **No enviamos tu nombre, tu correo ni tu ubicación.**

---

## 4. Bases para tratar tus datos

1. **Prestación del servicio** que solicitas al crear tu cuenta (secciones 2.1 a 2.4).
2. **Tu consentimiento**, para las notificaciones push y para los reportes de diagnóstico incorrecto. Puedes retirarlo en cualquier momento.
3. **Seguridad del servicio**, para los datos técnicos de la sección 2.6.

No usamos tus datos para publicidad ni los vendemos.

---

## 5. Con quién compartimos tus datos

Solo con los proveedores necesarios para que la app funcione, que los tratan por cuenta nuestra:

| Proveedor | Para qué | Datos | Ubicación |
| :--- | :--- | :--- | :--- |
| **Supabase** | Base de datos | Todos los datos de la sección 2 | Estados Unidos |
| **Render** | Servidor de la API | Todos los datos en tránsito | Estados Unidos |
| **Vercel** | Alojamiento de la web y paso de las peticiones a la API | Datos en tránsito y registros técnicos | Estados Unidos y red global |
| **Google (Gemini API)** | Diagnósticos y lectura de fotos | Lo descrito en la sección 3 | Estados Unidos y otros |
| **Resend** | Envío de correos (verificación, recuperación) | Tu correo y el contenido de esos correos | Estados Unidos |
| **Cloudflare** | Dominio y reenvío de correos que nos escribes | Correos enviados a direcciones `@aquareef.app` | Red global |
| **Servicio push de tu navegador** (Google, Mozilla o Apple) | Entregar notificaciones | Contenido de la notificación | Según tu navegador |

Al usar estos proveedores, tus datos se almacenan y procesan **fuera de México**, principalmente en Estados Unidos. Solo compartiremos datos con autoridades cuando la ley lo exija.

<!-- NOTA PARA REVISIÓN LEGAL: confirmar si estas comunicaciones a encargados requieren mención o consentimiento adicional como transferencias internacionales bajo la LFPDPPP vigente. -->

---

## 6. Cuánto tiempo conservamos tus datos

* **Cuenta, acuarios, mediciones, tareas, diagnósticos y suscripciones push**: mientras tu cuenta exista. Al eliminarla, se borran de inmediato.
* **Sesión**: el token de sesión dura hasta 7 días; al cerrar sesión o eliminar la cuenta se invalida.
* **Enlaces de recuperación de contraseña**: caducan a los 30 minutos y solo se pueden usar una vez.
* **Registros de intentos de inicio de sesión (IP y correo)**: se eliminan automáticamente pasadas unas 2 horas.
* **Fotos de escaneo**: no se conservan.
* **Copias de seguridad y registros técnicos de proveedores**: según los plazos de cada proveedor.

<!-- NOTA PARA REVISIÓN LEGAL: confirmar el plazo de las copias de seguridad de Supabase según el plan contratado y de los registros de Vercel, Render y Resend. -->

---

## 7. Tus derechos

Tienes derecho de **acceso, rectificación, cancelación (borrado) y oposición** (derechos ARCO), y a retirar tu consentimiento:

1. **Acceso y portabilidad**: en **Ajustes → Descargar mis datos** obtienes un archivo JSON con tu cuenta, acuarios, mediciones y tareas.
2. **Rectificación**: puedes corregir tu nombre, tus acuarios y tus mediciones desde la app.
3. **Cancelación (borrado)**: en **Ajustes → Eliminar mi cuenta** borras de forma **inmediata y permanente** tu cuenta y todos tus datos asociados (acuarios, mediciones, tareas, diagnósticos, reportes, sesiones y suscripciones push). Se pide tu contraseña para confirmar. Técnicamente, la app usa la operación `DELETE /api/user/account`.
4. **Oposición y retiro del consentimiento**: puedes desactivar las notificaciones push en cualquier momento, no usar el escaneo con cámara, o escribirnos.

Para cualquier solicitud que no puedas hacer desde la app, escribe a `privacy@aquareef.app` desde el correo de tu cuenta, indicando qué derecho quieres ejercer. Te responderemos en los plazos que marca la ley.

<!-- NOTA PARA REVISIÓN LEGAL: precisar plazos de respuesta ARCO y requisitos de identificación según la LFPDPPP vigente. -->

---

## 8. Seguridad

* Conexión cifrada (HTTPS) en todo momento; el dominio `.app` no permite conexiones sin cifrar.
* Contraseñas guardadas con `bcrypt`.
* Sesiones con tokens de corta duración y cookie `HttpOnly` y `Secure`.
* Acceso a la base de datos restringido; la API pública de la base de datos no permite leer ni escribir tablas.
* Los datos privados de la API nunca se guardan en la caché de la app instalada.

Ningún sistema es 100% seguro. Si detectamos un incidente que afecte tus datos, te avisaremos según lo que exija la ley.

---

## 9. Menores de edad

AquaReef no está dirigida a menores de 13 años y no recopilamos conscientemente sus datos. Si sabemos que un menor de 13 años nos dio datos personales, los eliminaremos.

<!-- NOTA PARA REVISIÓN LEGAL: confirmar la edad mínima y si se requiere consentimiento de padre o tutor para menores de 18 años en México. -->

---

## 10. Cambios a esta política

Si cambiamos esta política, publicaremos la nueva versión en esta página con su fecha y, si el cambio es relevante, te avisaremos dentro de la app o por correo.

---

## 11. Contacto

* **Privacidad**: `privacy@aquareef.app`
* **Soporte**: `support@aquareef.app`
