# Holos — fase 2

Dashboard doméstico pensado para una Raspberry Pi 4B (arm64). Incluye salud, peso, objetivos, finanzas, autenticación JWT y aislamiento multiusuario.

## Estado y funciones

- Launcher oscuro «Tu Holos», con una columna en móvil, dos en tablet y cuadrículas más amplias con barra lateral a partir de 1024 px.
- Pantalla fija de solo lectura y PWA instalable en Android.
- Chat con Gemini por texto y voz, con herramientas limitadas y auditadas.

- Panel con evolución de peso, línea de objetivo, kcal diarias y últimos movimientos.
- Finanzas con ingresos/gastos de seis meses, filtros, análisis por categoría y presupuestos mensuales.
- Categorías iniciales idempotentes: Supermercado, Nómina, Transporte, Ocio, Salud, Hogar y Otros.
- Edición y borrado de pesos y movimientos desde la PWA.

## Arranque en Raspberry Pi

1. Instala Docker Engine y el complemento Docker Compose.
2. Copia `.env.example` a `.env` y asigna valores seguros a `HOLOS_SECRET_KEY` y `HOLOS_ADMIN_PASSWORD`.
   Para activar el chat, añade `GEMINI_API_KEY` y `GEMINI_MODEL`. Elige un modelo que tenga nivel gratuito en [Google AI Studio](https://aistudio.google.com/); Holos no fija un modelo por defecto.
3. Arranca el servicio:

   ```sh
   docker compose up -d --build
   ```

4. Abre `http://IP_DE_LA_RASPBERRY:8080`. El usuario inicial es `HOLOS_ADMIN_EMAIL`. El servidor también acepta `SECRET_KEY`, que tiene prioridad sobre `HOLOS_SECRET_KEY` si se configuran ambos.

Las imágenes parten de `python:3.12-slim`, Node y Nginx, disponibles para arm64. La base de datos queda en el volumen Docker `holos-data`, con SQLite en modo WAL. En cada inicio el backend aplica las migraciones y ejecuta un seed idempotente del hogar y administrador.

## Ajustes y usuarios

Un administrador puede crear, editar y desactivar cuentas de su hogar en **Ajustes → Usuarios**. Cada cuenta tiene un correo o nombre de usuario, contraseña, rol, nombre visible, color y avatar. Puedes añadir un PIN de pantalla de 4 a 8 cifras. Desactivar la cuenta conserva sus datos y revoca su acceso. Debe quedar al menos un administrador activo.

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

## Alcance de datos

- Los datos de salud y peso siempre se filtran por `user_id`.
- Las categorías pertenecen a `household_id`.
- Las transacciones personales solo las ve su creador; las compartidas las ven los miembros del mismo hogar.
- La gestión de usuarios y los cambios de ubicación requieren un administrador del hogar.
- El chat solo puede crear gastos, ingresos y pesos, o consultar datos. Cada uso de herramienta registra usuario, herramienta, argumentos y resultado en `agent_actions`; no se guarda el texto completo de la conversación.
