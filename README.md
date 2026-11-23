# Holos — fase 1.6

Dashboard doméstico pensado para una Raspberry Pi 4B (arm64). Incluye salud, peso, objetivos, finanzas, autenticación JWT y aislamiento multiusuario.

## Estado y funciones

- Launcher oscuro «Tu Holos», con una columna en móvil, dos en tablet y cuadrículas más amplias con barra lateral a partir de 1024 px.
- Pantalla fija de solo lectura y PWA instalable en Android.

- Panel con evolución de peso, línea de objetivo, kcal diarias y últimos movimientos.
- Finanzas con ingresos/gastos de seis meses, filtros, análisis por categoría y presupuestos mensuales.
- Categorías iniciales idempotentes: Supermercado, Nómina, Transporte, Ocio, Salud, Hogar y Otros.
- Edición y borrado de pesos y movimientos desde la PWA.

## Arranque en Raspberry Pi

1. Instala Docker Engine y el complemento Docker Compose.
2. Copia `.env.example` a `.env` y asigna valores seguros a `HOLOS_SECRET_KEY` y `HOLOS_ADMIN_PASSWORD`.
3. Arranca el servicio:

   ```sh
   docker compose up -d --build
   ```

4. Abre `http://IP_DE_LA_RASPBERRY:8080`. El usuario inicial es `HOLOS_ADMIN_EMAIL`.

Las imágenes parten de `python:3.12-slim`, Node y Nginx, disponibles para arm64. La base de datos queda en el volumen Docker `holos-data`, con SQLite en modo WAL. En cada inicio el backend aplica las migraciones y ejecuta un seed idempotente del hogar y administrador.

## Pantalla fija y PWA

En el `.env` de Compose (o en `backend/.env` para desarrollo) configura:

- `SCREEN_TOKEN` es un secreto exclusivo de la pantalla. Genera uno con `openssl rand -hex 32`.
- `SCREEN_USER_EMAIL` es el correo de un usuario activo de Holos. Su pantalla muestra su peso, objetivo diario y balance del mes, además de los tres últimos movimientos visibles para él. Se incluyen sus movimientos y los compartidos por su hogar. Las notas quedan fuera del resumen.

Si falta algún valor, la pantalla queda desactivada. Tras editar el `.env`, aplica los cambios con `docker compose up -d backend`. Abre `/pantalla` en el dispositivo e introduce el token una vez. Holos lo guarda en ese navegador y lo envía en la cabecera `X-Screen-Token` al endpoint `GET /api/screen/summary`. Usa «Olvidar token» para quitarlo de ese dispositivo o cambia el secreto del servidor para revocarlo. El token solo sirve para consultar ese resumen.

Accede al frontend por HTTPS con `tailscale serve`. En `/pantalla`, toca «Pantalla completa». Holos solicita Wake Lock mientras la página está visible y vuelve a solicitarlo al regresar a ella, si el navegador lo permite. La pantalla se adapta al móvil en vertical y a la tablet en horizontal. El resumen se consulta cada 60 segundos. El reloj y el mes de referencia usan la zona horaria de Madrid.

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
- El API no ofrece todavía gestión de usuarios, chat, voz, nutrición, Calendar ni Home Assistant.
