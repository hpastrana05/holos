# Holos — fase 1

Dashboard doméstico pensado para una Raspberry Pi 4B (arm64). Esta primera fase incluye salud, peso, objetivos, finanzas, autenticación JWT y aislamiento multiusuario.

## Arranque en Raspberry Pi

1. Instala Docker Engine y el complemento Docker Compose.
2. Copia `.env.example` a `.env` y asigna valores seguros a `HOLOS_SECRET_KEY` y `HOLOS_ADMIN_PASSWORD`.
3. Arranca el servicio:

   ```sh
   docker compose up -d --build
   ```

4. Abre `http://IP_DE_LA_RASPBERRY:8080`. El usuario inicial es `HOLOS_ADMIN_EMAIL`.

Las imágenes parten de `python:3.12-slim`, Node y Nginx, disponibles para arm64. La base de datos queda en el volumen Docker `holos-data`, con SQLite en modo WAL. En cada inicio el backend aplica las migraciones y ejecuta un seed idempotente del hogar y administrador.

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
npm install
npm run dev
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
