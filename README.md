# Holos

Un panel privado para organizar el día a día de tu hogar. Está pensado para correr en un servidor casero, como una Raspberry Pi 4B, y abrirse desde el móvil, una tablet o el ordenador.

> [!WARNING]
> **Desarrollado con ayuda de IA.** Tus registros personales se guardan en tu propio servidor, con acceso por usuario y en una red privada. El repositorio de GitHub contiene el código. Las integraciones opcionales usan los datos que se detallan en [Privacidad y copias](#privacidad-y-copias).

[Funciones](#funciones) · [Instalación](#instalación) · [Uso diario](#uso-diario) · [Integraciones](#integraciones) · [Privacidad y copias](#privacidad-y-copias) · [Desarrollo](#desarrollo) · [Contribuciones](#contribuciones)

## Funciones

| Área | Qué puedes hacer |
| --- | --- |
| Salud y nutrición | Seguir tu peso y objetivos, y registrar comidas y macros. Gemini puede estimar nutrientes a partir de texto o fotos. |
| Finanzas | Anotar ingresos y gastos personales o compartidos, gestionar categorías y fijar presupuestos mensuales. |
| Casa | Consultar el estado y el consumo de tus dispositivos y controlarlos con Home Assistant. |
| Calendario | Ver tu agenda de Google Calendar y crear eventos. |
| Asistente | Consultar y registrar datos por texto o voz desde la web o con el bot de Telegram. |
| Pantalla fija | Usar un móvil o tablet para mostrar la hora, el tiempo y un resumen de solo lectura. |

## Instalación

Necesitas Docker Engine y Docker Compose en tu Raspberry Pi o servidor arm64.

1. Copia `.env.example` a `.env`. Define el usuario inicial en `HOLOS_ADMIN_EMAIL` y elige una contraseña fuerte para `HOLOS_ADMIN_PASSWORD`.
2. Genera una clave para `HOLOS_SECRET_KEY` con `openssl rand -hex 32`. Conserva `DATABASE_URL=sqlite:////data/holos.db` para que la API y el bot compartan la base en el volumen `holos-data`.
3. Arranca Holos.

   ```sh
   docker compose up -d --build
   ```

4. Abre el frontend en el puerto `8080` desde tu red privada. Usa Tailscale Serve para acceder por HTTPS desde fuera de casa y habilitar el micrófono del navegador. Restringe los puertos `8080` y `8000` a dispositivos de confianza y mantenlos fuera de Internet.

La API aplica las migraciones y prepara la cuenta inicial al arrancar. Si actualizas una instalación que usaba `HOLOS_DATABASE_URL`, localiza y respalda la base anterior antes de recrear el contenedor del backend.

## Uso diario

- **Usuarios.** En **Ajustes → Usuarios**, un administrador puede crear, editar y desactivar cuentas. Desactivar una cuenta revoca su acceso y conserva sus datos.
- **Categorías.** En **Finanzas → Categorías → Gestionar categorías**, puedes añadir categorías de ingreso o gasto para el hogar. Para borrar una categoría en uso, reasigna sus movimientos y elimina los presupuestos asociados.
- **Pantalla fija.** Abre `/pantalla` y elige un perfil. Configura un PIN de 4 a 8 cifras para cada perfil con datos personales. El selector muestra los nombres y avatares a quienes pueden abrir Holos, y los perfiles sin PIN permiten consultar su resumen.
- **Android.** Abre Holos por HTTPS en Chrome y elige **Instalar aplicación** o **Añadir a pantalla de inicio**. La pantalla fija alterna el resumen y el tiempo cada 20 segundos, y admite pantalla completa y Wake Lock en navegadores compatibles.

## Integraciones

Configura solo las integraciones que quieras usar.

| Servicio | Variables en `.env` |
| --- | --- |
| Gemini | `GEMINI_API_KEY` y `GEMINI_MODEL`. `GEMINI_FALLBACK_MODELS` indica modelos de respaldo separados por comas (por defecto `gemini-3.1-flash-lite`; vacío desactiva la rotación). Puedes elegir modelos disponibles en [Google AI Studio](https://aistudio.google.com/). |
| Home Assistant | `HA_URL` interna y `HA_TOKEN`. `HA_TIMEOUT_SECONDS` es opcional y vale 8 por defecto. |
| Google Calendar | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y `GOOGLE_REDIRECT_URI` con la URL HTTPS de `/api/calendar/callback`. |
| Telegram | `TELEGRAM_BOT_TOKEN`, que puedes obtener con BotFather. |

### Casa y calendario

- **Home Assistant.** En **Ajustes → Casa**, un administrador elige qué entidades puede consultar o controlar Holos y las organiza por estancia. Las cerraduras, alarmas y puertas de garaje requieren confirmación por defecto.
- **Google Calendar.** Cada persona conecta y selecciona sus calendarios en **Ajustes → Google Calendar**. Holos solicita acceso para consultar calendarios y leer o crear eventos. La agenda usa la hora de Madrid. Si cambias `HOLOS_SECRET_KEY`, tendrás que volver a autorizar Google Calendar.
- **Tiempo.** Un administrador puede cambiar la ubicación del hogar en **Ajustes → Ubicación del tiempo**.

### Bot de Telegram

1. Tras configurar el token, arranca Holos con Docker Compose. El bot usa long polling y funciona en chats privados. Si falta el token o Telegram lo rechaza, queda inactivo y deja un aviso en sus logs.
2. Abre **Ajustes → Telegram → Vincular Telegram** y envía al bot el comando que muestra Holos. El código sirve una sola vez y caduca en 10 minutos.
3. Usa `/ayuda` para consultar los comandos, `/resumen` para ver finanzas, peso y nutrición, o `/desvincular` para retirar el acceso. También puedes desvincularlo desde Ajustes.

El bot comparte el modelo Gemini del panel. Acepta fotos de comida y notas de voz compatibles de hasta 4 MiB por archivo. Las fotos enviadas juntas como álbum se analizan en una sola petición y se procesan solo en memoria. Para confirmar una acción pendiente envía `/confirmar comida`, `/confirmar evento` o `/confirmar dispositivo`, según corresponda. Las confirmaciones caducan en cinco minutos. Si Gemini agota la cuota o no está disponible, vuelve a enviar el álbum más tarde.

Ante cuota o indisponibilidad, Holos reintenta y pasa a los modelos de respaldo configurados, tanto en el chat como en el análisis de comidas. Los límites pueden ser compartidos entre modelos y la disponibilidad y el coste dependen de la cuenta de Google. Configura solo modelos compatibles con las fotos, audio y herramientas que uses.

## Privacidad y copias

- **Datos locales.** Salud, nutrición y movimientos personales se guardan por usuario. Las contraseñas se guardan como hashes y los tokens de actualización de Google Calendar se cifran.
- **Datos enviados.** Gemini recibe los mensajes y el contexto necesario, además de las fotos o notas de voz que se procesan en memoria. Telegram recibe lo que intercambias con el bot, incluido el resumen si lo pides. Google procesa las consultas y cambios del calendario, Open-Meteo recibe la ubicación del hogar y Home Assistant recibe consultas y órdenes.
- **Auditoría.** Holos registra las herramientas ejecutadas y sus resultados en `agent_actions`. El chat web también registra los argumentos. El bot guarda el resultado de ejecución sin guardar el contenido del mensaje en esa tabla.

Puedes hacer una copia de SQLite sin detener la API.

```sh
docker compose exec -T backend python -m app.backup
```

Guarda una copia fuera de la tarjeta SD. Mantén `.env`, SQLite y los respaldos fuera de Git y limita quién puede leerlos en el servidor.

## Desarrollo

El backend usa FastAPI, SQLAlchemy, Alembic y SQLite en modo WAL. El frontend usa React, Vite y Recharts. Docker Compose ejecuta el frontend, la API y el bot en servicios separados.

**Backend y pruebas**

```sh
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest
```

**Frontend**

```sh
cd frontend
npm ci
npm run dev
npm run build
```

Vite en desarrollo y Nginx en Docker redirigen `/api` al backend.

## Contribuciones

Holos está abierto a cambios y mejoras. Puedes abrir un *issue* para proponer una idea o reportar un fallo, o enviar una *pull request* con una mejora de código o documentación.

Uno de los objetivos es que Holos sea bilingüe. El proyecto busca incorporar el inglés de forma gradual a la interfaz y a la documentación, junto al español.

Si reportas un problema, indica qué esperabas, qué pasó y cómo reproducirlo. Usa datos ficticios en los ejemplos y las capturas.
