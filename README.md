# Holos

Holos es un panel privado para gestionar el día a día de un hogar desde el móvil, la tablet o el ordenador. Está pensado para instalarse en un servidor casero, como una Raspberry Pi 4B, junto a Home Assistant y Tailscale.

> **Desarrollado con ayuda de IA.** Holos guarda los registros personales en la base SQLite de tu propio servidor. Publicar el código en GitHub no publica la base de datos, las copias de seguridad ni las credenciales de tu instalación. El acceso se protege con cuentas por usuario y está pensado para una red privada. Las integraciones opcionales procesan los datos necesarios para cada función.

## Qué puedes hacer

- **Salud y nutrición.** Registra tu peso, sigue tu objetivo y lleva un diario de comidas y macros. Gemini puede estimar los nutrientes de una comida descrita por texto o fotografiada.
- **Finanzas.** Registra ingresos y gastos, analiza movimientos por categoría y configura presupuestos mensuales. Puedes registrar movimientos personales o compartirlos con el hogar.
- **Casa.** Consulta estados y consumo y controla los dispositivos de Home Assistant que hayas autorizado.
- **Calendario.** Conecta tu cuenta de Google Calendar para consultar la agenda y crear eventos.
- **Chat y Telegram.** Consulta el panel y registra datos mediante el asistente, desde la web o desde un chat privado con el bot. Telegram es opcional.
- **Pantalla fija.** Deja una tablet o un móvil en casa mostrando la hora, el tiempo y un resumen de solo lectura. Holos se puede instalar como PWA en Android.

El backend usa FastAPI, SQLAlchemy, Alembic y SQLite en modo WAL. La interfaz usa React, Vite y Recharts. Docker Compose ejecuta el frontend, la API y el bot como servicios separados.

## Arranque en Raspberry Pi

1. Instala Docker Engine y el complemento Docker Compose en tu Raspberry Pi o servidor arm64.
2. Copia `.env.example` a `.env`. Antes del primer arranque, elige un usuario en `HOLOS_ADMIN_EMAIL`, una contraseña fuerte en `HOLOS_ADMIN_PASSWORD` y una clave aleatoria larga en `HOLOS_SECRET_KEY`. Puedes generar la clave con `openssl rand -hex 32`. Conserva `DATABASE_URL=sqlite:////data/holos.db` para que la API y el bot compartan la misma base persistente.
3. Arranca Holos:

   ```sh
   docker compose up -d --build
   ```

4. Abre Holos desde tu red privada. Para acceder desde fuera de casa y usar el micrófono, sirve el frontend por HTTPS con Tailscale Serve. Docker Compose publica los puertos 8080 y 8000 en el servidor. Mantén ambos fuera de Internet y restringe el acceso a los dispositivos de confianza mediante el cortafuegos y Tailscale.

El backend aplica las migraciones al arrancar y prepara la cuenta inicial si hace falta. SQLite se guarda en el volumen `holos-data`. Si actualizas una instalación que usaba `HOLOS_DATABASE_URL`, comprueba dónde está la base antigua y haz una copia antes de recrear el backend.

### Integraciones opcionales

| Integración | Variables en `.env` |
| --- | --- |
| Gemini | `GEMINI_API_KEY` y `GEMINI_MODEL`. Elige un modelo en [Google AI Studio](https://aistudio.google.com/). |
| Home Assistant | `HA_URL` interna, `HA_TOKEN` y, opcionalmente, `HA_TIMEOUT_SECONDS` (8 por defecto). |
| Google Calendar | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y `GOOGLE_REDIRECT_URI`. Configura la URL HTTPS del callback `/api/calendar/callback` que usará el navegador. |
| Telegram | `TELEGRAM_BOT_TOKEN`. Si falta o Telegram lo rechaza, el bot queda inactivo. |

## Ajustes y usuarios

Un administrador puede crear, editar y desactivar cuentas de su hogar en **Ajustes → Usuarios**. Cada cuenta tiene un correo o nombre de usuario, contraseña, rol, nombre visible, color y avatar. Puedes añadir un PIN de pantalla de 4 a 8 cifras. Desactivar la cuenta conserva sus datos y revoca su acceso. Debe quedar al menos un administrador activo.

## Casa · Home Assistant

En **Ajustes → Casa**, un administrador descubre entidades y decide cuáles se autorizan para el hogar; ninguna entidad se lee ni se controla antes de incluirla en esa lista. Allí se asignan nombre visible, estancia y si exige confirmación. Cerraduras, paneles de alarma y puertas de garaje se marcan sensibles por defecto. Las lecturas aplican reintentos cortos ante una caída de HA; las órdenes de control no se reintentan para evitar duplicar una acción.

La vista **Casa** agrupa los elementos autorizados por estancia, muestra estado y sensores de potencia/energía compatibles, y ofrece interruptores para los dominios controlables. La tarjeta de `/pantalla` es solo lectura, se actualiza junto al resumen cada 60 segundos y el backend reutiliza brevemente los estados en memoria para reducir carga en la Pi.

## Google Calendar

Cada usuario conecta su propia cuenta desde **Ajustes → Google Calendar**. Holos solicita solo permisos para consultar calendarios y leer/crear eventos. Desde ese mismo ajuste puede elegir qué calendarios visibles incluir; los eventos conservan el color de origen. El refresh token se cifra antes de guardarse y no se registra en logs. **No cambies `HOLOS_SECRET_KEY` una vez conectes Google:** se usa para cifrar esos tokens; si cambia, Holos desconecta el calendario de forma segura y tendrás que volver a autorizarlo. La agenda usa siempre `Europe/Madrid`; `/pantalla` solo muestra título y hora de los próximos eventos de la persona seleccionada.

## Pantalla fija, tiempo y PWA

Abre `/pantalla` por HTTPS con Tailscale y elige un perfil. Si tiene PIN, introdúcelo para iniciar la sesión. Los nombres, los avatares y los colores de los perfiles activos del hogar configurado se muestran a cualquiera que tenga acceso a Holos. **Si un perfil carece de PIN, esas personas también pueden abrir su resumen de pantalla.**

La sesión dura 30 días y se recuerda en el navegador. «Cambiar de usuario» vuelve al selector. El resumen de solo lectura muestra el peso, las kcal y el balance y movimientos registrados por la persona seleccionada. El cambio de PIN y la desactivación de la cuenta invalidan sus sesiones de pantalla. Tras actualizar desde la fase 1.6, basta con volver a `/pantalla` y elegir un perfil.

El resumen y el tiempo alternan cada 20 segundos. También puedes deslizar o tocar los indicadores. Los datos se consultan cada 60 segundos. «Pantalla completa» y Wake Lock siguen disponibles en navegadores compatibles.

Un administrador puede cambiar el nombre, la latitud y la longitud desde **Ajustes → Ubicación del tiempo**. La ubicación se guarda por hogar y parte de Toledo. El pronóstico horario de [Open-Meteo](https://open-meteo.com/) usa la zona Europe/Madrid y una caché en memoria de 30 minutos. Si el servicio falla, Holos muestra el último pronóstico disponible de esa ubicación con un aviso.

Para instalar Holos, abre la dirección HTTPS en Chrome para Android y usa «Instalar aplicación» o «Añadir a pantalla de inicio» en el menú. La aplicación abre en modo independiente y el acceso directo «Pantalla fija» abre `/pantalla` desde los launchers compatibles.

## Desarrollo y pruebas

```sh
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest
```

Para el frontend:

```sh
cd frontend
npm ci
npm run dev
# Comprobación de tipos y compilación de producción
npm run build
```

Vite redirige `/api` al backend local. En Compose, Nginx hace esa misma redirección al contenedor `backend`.

## Copia de seguridad

La base se conserva en el volumen `holos-data`. Programa una copia diaria consistente usando SQLite:

```sh
docker compose exec -T backend python -m app.backup
```

Crea y conserva el directorio de backups en un volumen distinto o sincronízalo fuera de la SD. No se guardan imágenes ni se incluyen secretos en el repositorio.

## Privacidad y datos personales

- **En tu servidor.** Los registros de salud y nutrición y los movimientos personales se filtran por usuario. Los movimientos compartidos, las categorías y los dispositivos autorizados pertenecen al hogar. Las contraseñas se guardan como hashes y los tokens de actualización de Google Calendar se guardan cifrados.
- **En una pantalla compartida.** Asigna un PIN a cada perfil que tenga datos personales. Cualquiera que pueda abrir Holos puede ver el selector de perfiles y consultar el resumen de los perfiles que carecen de PIN.
- **Con Gemini.** Al usar el asistente, Gemini recibe los mensajes y el contexto que necesita para responder. Al analizar fotos de comida o notas de voz compatibles, Holos prepara los archivos en memoria y los descarta al terminar. El chat web registra las herramientas ejecutadas, sus argumentos y el resultado en `agent_actions`. El bot registra la herramienta y el resultado de ejecución sin guardar el contenido del mensaje en esa tabla.
- **Con otros servicios.** Google procesa las consultas y cambios del calendario. Telegram recibe los mensajes y las respuestas que intercambias con el bot, incluido el resumen si lo solicitas. Open-Meteo recibe la ubicación configurada para consultar el tiempo. Home Assistant recibe las consultas y órdenes de los dispositivos autorizados.
- **Al compartir el código.** Mantén `.env`, el volumen de SQLite, los respaldos y cualquier exportación de datos fuera del repositorio. Restringe también quién puede leerlos en el servidor.

## Bot de Telegram

1. Crea el bot con BotFather y configura `TELEGRAM_BOT_TOKEN` en `.env`. Si falta o Telegram lo rechaza, el servicio queda inactivo y deja un aviso en sus logs.
2. Comprueba que ambos servicios usan la misma base persistente. La variable es `DATABASE_URL=sqlite:////data/holos.db`. Si un despliegue anterior solo definía `HOLOS_DATABASE_URL`, comprueba dónde está la base actual y migra los datos al volumen antes de recrear el API.
3. Ejecuta `docker compose up -d --build`. El servicio `telegram` espera al API, usa long polling sin publicar puertos y tiene un límite de 256 MiB.
4. En Holos, abre **Ajustes → Telegram → Vincular Telegram** y envía el comando mostrado al bot en un chat privado. El código caduca en 10 minutos y solo se puede usar una vez. Si agotas los intentos, espera 10 minutos. Usa `/resumen` para ver finanzas, peso y nutrición, `/ayuda` para ver los comandos y `/desvincular` para retirar el acceso. También se puede desvincular desde Ajustes.

El bot comparte `GEMINI_API_KEY` y `GEMINI_MODEL` con Holos. Las notas de voz y las fotos de comida se procesan en memoria cuando el modelo admite el formato, con un máximo de 4 MiB por archivo. Holos conserva brevemente la conversación en memoria y registra el usuario, la herramienta y el resultado de ejecución en `agent_actions`. Las confirmaciones de comidas, eventos y controles sensibles caducan en cinco minutos y se aplican a la acción que muestra el bot.
