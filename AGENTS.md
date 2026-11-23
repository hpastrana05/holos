# Holos

Dashboard personal para un hogar (familia) en una Raspberry Pi 4B (8 GB, SD 64 GB).
Hoy lo usa un solo usuario, pero está preparado para varios.
Corre junto a Home Assistant y Tailscale. Acceso solo por Tailscale.
Usa HTTPS con `tailscale serve` (necesario para el micrófono del navegador).

## Estado del proyecto
- Fase 1 hecha: base, login JWT, salud y finanzas (CRUD).
- Fase 1.5 hecha: gráficos, listados, edición, presupuestos y responsive.
- Fase 1.6 hecha: rediseño launcher oscuro y modo pantalla fija.
- Fase 1.7 hecha: ajustes de usuarios, selector con PIN opcional y tiempo en pantalla fija.
- Siguientes: chat + voz, nutrición, Home Assistant, Google Calendar,
  Telegram (opcional).
- No implementes módulos de fases futuras sin que lo pida.

## Módulos
- Salud: perfil, peso (manual), objetivo de peso, kcal objetivo,
  gráfico de peso con línea de objetivo y fecha estimada.
- Nutrición: comidas por foto/texto/voz con estimación aproximada.
- Finanzas: ingresos y gastos, vista general y vista por categorías,
  presupuesto por categoría y categorías por defecto en el seed.
- Calendario: Google Calendar.
- Casa: Home Assistant (API REST), con consumo y control de dispositivos.
- Chat: texto y voz con Gemini y herramientas.

## Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic, SQLite (WAL).
- Frontend: React + Vite + Tailwind, PWA, gráficos con Recharts.
- IA: Gemini API tras una interfaz `LLMProvider` intercambiable.
- Voz: Web Speech API del navegador (Chrome Android). Sin Whisper local.
- Despliegue: Docker Compose, imágenes arm64.

## Interfaz y estilo
- Estilo launcher de apps: tema oscuro por defecto, tarjetas redondeadas
  con efecto glass sutil y un color de acento por módulo.
- Tokens de diseño (colores, radios, sombras) centralizados en Tailwind.
- Inicio "Tu Holos": saludo según la hora, fecha en español y cuadrícula
  de módulos con icono y color. Los módulos no implementados aparecen
  deshabilitados ("Próximamente").
- Navegación: barra inferior con iconos en móvil/tablet; barra lateral o
  superior en escritorio.
- Responsive: usable en móvil (diario), tablet y escritorio.
- Textos en español; fechas dd/mm/aaaa; moneda EUR (es-ES).
- Estados vacíos, de carga y de error en cada pantalla.
- Gráficos con Recharts; editar y borrar en cada listado.
- Rendimiento ligero: debe funcionar bien en un móvil Android antiguo.

## Modo pantalla fija (`/pantalla`)
- Pensado para un móvil/tablet Android fijo en casa. Sin scroll.
- Selector del hogar con PIN opcional por usuario y sesión de solo lectura.
- Reloj grande, resumen de peso y kcal, balance del mes y últimos movimientos.
- El resumen personal y el tiempo rotan cada 20 s y se actualizan cada 60 s.
- Pantalla completa y sin apagado (Wake Lock API).
- Preparada para añadir tarjetas de Casa (consumo, dispositivos, escenas).

## PWA
- Manifest con display standalone/fullscreen e iconos instalables en Android.
- Funciona en el móvil diario (con chat) y en el móvil fijo (pantalla).

## Reglas generales
- Nunca subas secretos; usa `.env` y `.env.example`.
- El agente solo ejecuta herramientas de una lista cerrada y tipada.
- El agente actúa siempre en nombre del usuario que habla.
- Registra cada acción del agente (tool, argumentos, resultado).
- Tests con pytest. Cada feature: modelo, endpoint, test y docs breves.
- Antes de cambiar la arquitectura, propón un plan y espera aprobación.
- No instales dependencias sin justificarlo.

## Flujo de trabajo
- Propón un plan breve antes de cambios grandes y espera mi OK.
- Commits pequeños con mensajes claros.
- Ejecuta tests y lint antes de dar una tarea por terminada.
- Documenta en el README cualquier variable de entorno nueva.
- Actualiza "Estado del proyecto" al cerrar cada fase.

## Multiusuario (preparado desde la v1)
- Modelos `User` y `Household`. Un usuario pertenece a un hogar.
- Roles: admin y member.
- Datos personales (salud, peso, nutrición): `user_id`, privados por defecto.
- Datos compartidos (categorías, casa): `household_id`.
- Transacciones con `visibility`: personal o shared.
- Autenticación con login + JWT. Toda consulta filtra por el usuario actual.
- Integraciones (Google Calendar) con credenciales por usuario.
- La sesión de `/pantalla` es de solo lectura y se limita al usuario seleccionado.
- Incluye tests de aislamiento entre usuarios.

## Canales del agente
- Un único servicio de agente (`/agent/chat`) con herramientas tipadas.
- Canales: PWA (texto y voz) y, opcionalmente, bot de Telegram.
- Telegram: long polling, `telegram_id` por usuario y solo usuarios autorizados.

## Casa (Home Assistant)
- Cliente REST con token de larga duración en `.env`.
- Control de dispositivos solo mediante lista blanca de entidades.
- Muestra consumo por enchufe, estado y accesos rápidos por estancia.
- Las acciones del agente sobre dispositivos se registran.

## Almacenamiento (SD)
- SQLite en modo WAL; evita escrituras innecesarias.
- Logs limitados y con rotación.
- No persistas imágenes: procesa la foto en memoria, extrae los datos
  con Gemini y descarta el archivo. No loguees imágenes ni su contenido.
- Redimensiona a ~1024 px antes de enviarla a la API.
- Prevé una copia de seguridad diaria de la base de datos.

## Datos de nutrición
- Tabla `meals`: user_id, eaten_at, meal_type, name, description, kcal,
  protein_g, carbs_g, fat_g, confidence, source.
- Son estimaciones orientativas; no se exige precisión.

## Salud
- Peso manual por ahora; `source` preparado para futuras fuentes.
- Mantén historial de peso y objetivos sin sobrescribir.
- kcal objetivo con Mifflin-St Jeor + factor de actividad.
- Limita el déficit a un máximo seguro.