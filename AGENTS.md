# Holos

Dashboard personal para un hogar (familia) en una Raspberry Pi 4B (8 GB, SD 64 GB).
Hoy lo usa un solo usuario, pero está preparado para varios.
Corre junto a Home Assistant y Tailscale. Acceso solo por Tailscale.
Usa HTTPS con `tailscale serve` (necesario para el micrófono del navegador).

## Estado del proyecto
- Fase 1 hecha: base, login JWT, salud y finanzas (CRUD).
- Fase 1.5 hecha: gráficos, listados, edición, presupuestos y responsive.
- Fase 1.6 hecha: rediseño launcher oscuro y modo pantalla fija.
- Fase 1.7 hecha: gestión de usuarios, pantalla sin token y tiempo.
- Fase 2 hecha: chat con IA (pendiente: pulido visual y voz).
- Fase 3 hecha: nutrición (foto, texto).
- Fase 4 hecha: Casa (Home Assistant).
- Fase 5 en curso: Google Calendar.
- Siguientes: Telegram (opcional), reloj/Health Connect.
- No implementes módulos de fases futuras sin que lo pida.

## Módulos
- Salud: perfil, peso (manual), objetivo de peso, kcal objetivo,
  gráfico de peso con línea de objetivo y fecha estimada.
- Nutrición: comidas por foto/texto/voz con estimación aproximada.
- Finanzas: ingresos y gastos, vista general y vista por categorías,
  presupuesto por categoría y categorías por defecto en el seed.
- Calendario: Google Calendar por usuario; agenda, vista mensual y
  creación de eventos desde el chat.
- Casa: Home Assistant (API REST), estado, consumo y control de dispositivos por estancia.
- Chat: texto y voz con Gemini y herramientas; chat flotante en todas las pantallas.

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

## Agente (chat y voz)
- Un único servicio de agente (`POST /agent/chat`) con herramientas tipadas
  y lista cerrada. Usa function calling de Gemini tras `LLMProvider`.
- Variables: `GEMINI_API_KEY` y `GEMINI_MODEL` en `.env`.
- Herramientas actuales: add_expense, add_income, add_weight,
  get_finance_summary, get_budget_status, get_weight_status,
  get_today_weather, add_meal, get_nutrition_status, get_home_status,
  control_device, get_energy_usage. Las nuevas fases añaden las suyas.
- El agente actúa siempre en nombre del usuario autenticado.
- Si falta un dato o hay ambigüedad, pregunta antes de guardar.
- Confirma siempre lo que ha guardado.
- Registra cada acción (tool, argumentos, resultado, usuario) en
  `agent_actions`. No guardes el historial completo del chat en disco.
- Respeta los límites de la API gratuita: reintentos con espera y
  mensaje claro si se supera la cuota.
- Voz en el navegador: Web Speech API (es-ES) para entrada y
  `speechSynthesis` para respuesta opcional.
- Canales: PWA (texto y voz) y, opcionalmente, bot de Telegram
  (long polling, `telegram_id` por usuario, solo usuarios autorizados).

## Casa (Home Assistant)
- Cliente REST con `HA_URL` y `HA_TOKEN` (token de larga duración) en `.env`.
- Timeout, reintentos y error claro si HA no responde.
- Lectura y control solo de entidades en la lista blanca (por hogar).
- Datos de casa compartidos por `household_id`.
- Agrupación por estancia configurable.
- Muestra estado, consumo por enchufe y accesos rápidos.
- Herramientas del agente: get_home_status, control_device (solo lista
  blanca) y get_energy_usage. Las acciones se registran en `agent_actions`.
- Pide confirmación en acciones sensibles.
- La pantalla `/pantalla` muestra Casa en solo lectura.

## Almacenamiento (SD)
- SQLite en modo WAL; evita escrituras innecesarias.
- Logs limitados y con rotación.
- No persistas imágenes: procesa la foto en memoria, extrae los datos
  con Gemini y descarta el archivo. No loguees imágenes ni su contenido.
- Redimensiona a ~1024 px antes de enviarla a la API.
- Prevé una copia de seguridad diaria de la base de datos.

## Nutrición
- Estimaciones orientativas de kcal y macros; el usuario puede editarlas.
- Tabla `meals`: user_id, eaten_at, meal_type, name, description, kcal,
  protein_g, carbs_g, fat_g, confidence, source.
- Las fotos no se guardan: se procesan en memoria, se reducen a ~1024 px
  y no se escriben en logs. Se descartan tras extraer los datos con Gemini.
- Objetivo de kcal con Mifflin-St Jeor y límite de déficit agresivo.
- Datos privados por `user_id`.
- Herramientas del agente: add_meal, get_nutrition_status.

## Salud
- Peso manual por ahora; `source` preparado para futuras fuentes.
- Mantén historial de peso y objetivos sin sobrescribir.
- kcal objetivo con Mifflin-St Jeor + factor de actividad.
- Limita el déficit a un máximo seguro.

## Calendario (Google Calendar)
- OAuth 2.0 por usuario con acceso offline; credenciales por `user_id`.
- Variables: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
  `GOOGLE_REDIRECT_URI` en `.env`.
- Refresh token cifrado en la base de datos; nunca en logs.
- Permisos mínimos: leer y crear eventos.
- Caché corta en memoria; si el token caduca o se revoca, marca el
  calendario como desconectado y avisa.
- Cada usuario solo ve su calendario.
- Herramientas del agente: get_calendar_events y add_calendar_event
  (con confirmación antes de crear).
