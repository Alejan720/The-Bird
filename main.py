import os
import logging
import discord
from discord.ext import commands, tasks
from config import Config
from database import Database

# Configuración avanzada de logging profesional
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot_runtime.log", encoding="utf-8")
    ]
)
logger = logging.logger if hasattr(logging, 'logger') else logging.getLogger("BotPrincipal")

class BotPrincipal(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.emojis = True
        
        super().__init__(
            command_prefix=Config.PREFIX,
            intents=intents,
            help_command=None
        )
        self.db = Database()

    async def setup_hook(self):
        logger.info("Iniciando secuencia de arranque del bot...")

        # 1. Inicialización de la base de datos asíncrona
        try:
            await self.db.setup()
            logger.info("Base de datos SQLite y tablas estructurales verificadas/inicializadas.")
        except Exception as e:
            logger.critical(f"Error crítico al inicializar la base de datos: {e}")
            raise

        # 2. Carga integral de Cogs (Funcionalidades, Utilidades, Economía, Niveles y Miniguegos)
        cogs_a_cargar = [
            "cogs.economy",
            "cogs.levels",
            "cogs.moderation",
            "cogs.utility",
            "cogs.questionnaires",
            "cogs.games.tictactoe",
            "cogs.games.coinflip",
            "cogs.games.chess",
            "cogs.games.checkers",
            "cogs.games.parchis"
        ]

        for cog in cogs_a_cargar:
            try:
                await self.load_extension(cog)
                logger.info(f"Módulo cargado correctamente: {cog}")
            except Exception as e:
                logger.error(f"Error al cargar el módulo {cog}: {e}")

        # 3. Sincronización global de comandos de barra (Slash Commands)
        try:
            synced = await self.tree.sync()
            logger.info(f"Sincronización de comandos de barra completada. Total: {len(synced)} comandos.")
        except Exception as e:
            logger.error(f"Error durante la sincronización de comandos de barra: {e}")

        # 4. Inicio de tareas en segundo plano
        self.background_maintenance.start()

    @tasks.loop(minutes=30)
    async def background_maintenance(self):
        """Tarea periódica de mantenimiento general del sistema y economía."""
        logger.debug("Ejecutando rutina de mantenimiento en segundo plano...")
        try:
            # Aquí se pueden actualizar mercados dinámicos, limpiar cachés temporales, etc.
            pass
        except Exception as e:
            logger.error(f"Error en la tarea de mantenimiento en segundo plano: {e}")

    @background_maintenance.before_loop
    async def before_background_maintenance(self):
        await self.wait_until_ready()

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Manejador centralizado de errores para todos los slash commands."""
        logger.error(f"Excepción en comando de barra [{interaction.command.name if interaction.command else 'Desconocido'}]: {error}")
        
        error_msg = "❌ Ha ocurrido un error inesperado al procesar este comando."
        if isinstance(error, discord.app_commands.MissingPermissions):
            error_msg = "❌ No tienes los permisos necesarios para ejecutar este comando."
        elif isinstance(error, discord.app_commands.CommandOnCooldown):
            error_msg = f"⏳ Este comando está en enfriamiento. Inténtalo de nuevo en `{error.retry_after:.1f}` segundos."
        
        if interaction.response.is_done():
            await interaction.followup.send(error_msg, ephemeral=True)
        else:
            await interaction.response.send_message(error_msg, ephemeral=True)

    async def on_ready(self):
        logger.info(f"Conexión establecida con éxito. Identidad: {self.user} (ID: {self.user.id})")
        logger.info(f"Desplegado en {len(self.guilds)} servidores activos.")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="Gestión de Servidor & Minijuegos 🎮"
            )
        )

    async def on_guild_join(self, guild: discord.Guild):
        logger.info(f"El bot se ha añadido a un nuevo servidor: {guild.name} (ID: {guild.id}) - Miembros: {guild.member_count}")

    async def on_guild_remove(self, guild: discord.Guild):
        logger.info(f"El bot ha sido eliminado del servidor: {guild.name} (ID: {guild.id})")


if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN") or Config.BOT_TOKEN
    
    if not token or token == "":
        logger.critical("No se ha detectado el token de Discord en las variables de entorno o en la configuración.")
    else:
        bot = BotPrincipal()
        try:
            bot.run(token, log_handler=None)  # Usamos nuestro propio sistema de logging configurado
        except Exception as e:
            logger.critical(f"Fallo crítico al ejecutar la instancia del bot: {e}")