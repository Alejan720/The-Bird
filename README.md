# Bot de Discord

Bot desarrollado con `discord.py`: economía por servidor, niveles, moderación, cuestionarios de roles y minijuegos. Usa SQLite para guardar el estado. Las dependencias de ejecución están en [requirements.txt](requirements.txt).

## Requisitos

- Python 3.11 o posterior; Docker usa Python 3.12.
- El extra `voice` de `discord.py` instala PyNaCl y davey. No hay comandos de música implementados actualmente.
- Una aplicación de bot creada en [Discord Developer Portal](https://discord.com/developers/applications).
- Los intents privilegiados **Server Members Intent** y **Message Content Intent** activados en el Developer Portal.
- El bot invitado con los scopes `bot` y `applications.commands` y los permisos necesarios para sus funciones.

Para cuestionarios y roles automáticos, el rol del bot debe estar por encima de los roles que asigna. Para moderar, necesita los permisos correspondientes y una posición superior al miembro afectado.

## Configuración

1. Copia `.env.example` como `.env`.
2. Define `DISCORD_BOT_TOKEN` en `.env` con el token vigente. No publiques ni compartas este archivo.
3. Opcionalmente configura `CHANNEL_WELCOME_ID`, `CHANNEL_LOGS_ID` y `ROLE_DEFAULT_ID`.
4. Si migras economía global de una versión antigua, configura también `LEGACY_ECONOMY_GUILD_ID` con el ID del servidor que recibirá esos datos.

La migración del estado económico antiguo se aplica una sola vez a un único servidor y conserva intactas las tablas de origen. Si se detectan filas económicas antiguas y no hay destino configurado, el bot se detiene en vez de iniciar con cuentas vacías. El valor `0` es válido para una instalación nueva sin datos antiguos.

## Instalar y ejecutar

En Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m unittest discover -s tests -v
python main.py
```

Los comandos de aplicación se sincronizan globalmente al iniciar; Discord puede tardar un poco en mostrarlos.

## Docker

El contenedor corre como usuario sin privilegios. SQLite y los respaldos se guardan bajo `/data`, que Compose monta en el volumen persistente `bot-data`.

```powershell
Copy-Item .env.example .env
```

Edita `.env` con el token real y, si corresponde, el ID de migración. Después ejecuta:

```powershell
docker compose build
docker compose up -d
docker compose logs -f discord-bot
```

Para detenerlo: `docker compose down`. No añadas `-v` si quieres conservar el volumen con la base de datos.

En un host externo configura las mismas variables de entorno y monta almacenamiento persistente en `/data`. Si vas a importar una base antigua, cópiala al volumen como `/data/database.sqlite` antes del primer arranque y establece `LEGACY_ECONOMY_GUILD_ID`.

Cuando el host define `PORT` (como Render), el bot abre un servidor HTTP pequeño en `0.0.0.0:$PORT`: `GET /` y `GET /health` devuelven `503` mientras Discord conecta y `200` cuando el bot está listo. Puedes configurar UptimeBot para consultar `/health`; no uses el ping como sustituto de un worker siempre activo.

Un plan gratuito que suspenda servicios o elimine el disco al reiniciar no garantiza operación 24/7 ni persistencia. El bot sigue dependiendo de un proceso activo y de un volumen persistente para SQLite.

## Funciones

- Economía: `/balance`, `/diario`, `/trabajar`, `/depositar`, `/retirar`, `/pagar`, `/robar`, `/tienda`, `/usar`, `/mochila` y `/top_economia`.
- Inversiones: `/mercado`, `/comprar_accion`, `/vender_accion`, `/cartera` e `/historial_inversion`. Siete activos cambian cada hora; el azar y el volumen neto de órdenes pueden moverlos al alza o a la baja.
- Propiedades: `/propiedades`, `/comprar_propiedad`, `/vender_propiedad` y `/cobrar_renta`. La renta se deposita en el banco, acumula hasta siete días por cobro y la reventa paga el 75% del precio de catálogo.
- Administración: `/dar_dinero`, `/quitar_dinero` e `/historial_dinero`. Requieren permiso de administrador, motivo obligatorio y quedan auditados por servidor.
- Configuración del servidor: `/config_bienvenida`, `/config_logs` y `/config_rol_default`.
- Moderación: `/mute`, `/kick`, `/ban`, `/advertir`, `/historial_mod` y `/limpiar`. Los timeouts permiten de 1 minuto a 28 días; el ban puede borrar hasta 7 días de mensajes y la limpieza está limitada a 100 mensajes.
- Comunidad: `/nivel`, `/encuesta`, `/recordatorio` y `/crear_cuestionario`.
- Juegos: `/coinflip`, `/tictactoe`, `/chess start`, `/chess move`, `/chess surrender`, `/damas` y `/parchis`.

La economía, XP, inventario, inversiones y propiedades están aislados por servidor. Los precios del mercado son compartidos entre servidores. Damas y Parchís Exprés son adaptaciones simplificadas. Los recordatorios y cuestionarios se guardan en SQLite y los botones de cuestionarios se restauran al reiniciar.

## Copias de seguridad

El bot crea un respaldo SQLite diario en `backups/` (o en `BACKUP_PATH`) y conserva los siete más recientes. En Docker, `BACKUP_PATH` apunta a `/data/backups`; incluye el volumen persistente en tu estrategia de copias externas. Un respaldo guardado únicamente en el mismo disco no protege frente a la pérdida de ese disco.

## Publicar en GitHub

`.gitignore` excluye `.env`, bases SQLite, respaldos, entornos virtuales y logs. Sube `.env.example`, nunca `.env`; verifica también que no haya tokens, bases de datos o respaldos ya añadidos al historial del repositorio. Si un token se expone, rótalo en Discord Developer Portal: borrarlo del archivo no lo invalida.