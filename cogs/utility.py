import discord
from discord import app_commands
from discord.ext import commands, tasks
import logging
from datetime import datetime, timedelta, timezone
from config import Config

logger = logging.getLogger(__name__)

class UtilityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.reminder_delivery.start()

    def cog_unload(self):
        self.reminder_delivery.cancel()

    async def _guild_setting(self, guild_id: int, name: str, fallback: int):
        settings = await self.db.get_guild_settings(guild_id)
        index = {"welcome": 0, "logs": 1, "role": 2}[name]
        return fallback if settings[index] is None else settings[index]

    @tasks.loop(seconds=30)
    async def reminder_delivery(self):
        due = await self.db.get_due_reminders(datetime.now(timezone.utc).isoformat())
        for reminder_id, user_id, channel_id, message in due:
            delivered = False
            user = self.bot.get_user(user_id)
            if user is None:
                try:
                    user = await self.bot.fetch_user(user_id)
                except discord.HTTPException:
                    user = None
            if user:
                try:
                    await user.send(f"🔔 **Recordatorio**\n> {message}")
                    delivered = True
                except discord.HTTPException:
                    pass
            if not delivered:
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    try:
                        channel = await self.bot.fetch_channel(channel_id)
                    except discord.HTTPException:
                        channel = None
                if channel:
                    try:
                        await channel.send(f"🔔 <@{user_id}> **Recordatorio**\n> {message}")
                        delivered = True
                    except discord.HTTPException:
                        pass
            if delivered:
                await self.db.mark_reminder_delivered(reminder_id)

    @reminder_delivery.before_loop
    async def before_reminder_delivery(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="config_bienvenida", description="Admin: configura el canal de bienvenida; sin canal lo desactiva.")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_bienvenida(self, interaction: discord.Interaction, canal: discord.TextChannel | None = None):
        if interaction.guild is None:
            await interaction.response.send_message("Usa este comando en un servidor.", ephemeral=True)
            return
        await self.db.set_guild_setting(interaction.guild.id, "welcome_channel_id", canal.id if canal else 0)
        await interaction.response.send_message(
            f"Canal de bienvenida: {canal.mention if canal else 'desactivado'}.", ephemeral=True
        )

    @app_commands.command(name="config_logs", description="Admin: configura el canal de registros; sin canal lo desactiva.")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_logs(self, interaction: discord.Interaction, canal: discord.TextChannel | None = None):
        if interaction.guild is None:
            await interaction.response.send_message("Usa este comando en un servidor.", ephemeral=True)
            return
        await self.db.set_guild_setting(interaction.guild.id, "log_channel_id", canal.id if canal else 0)
        await interaction.response.send_message(
            f"Canal de registros: {canal.mention if canal else 'desactivado'}.", ephemeral=True
        )

    @app_commands.command(name="config_rol_default", description="Admin: configura el rol automático de nuevos miembros.")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_rol_default(self, interaction: discord.Interaction, rol: discord.Role | None = None):
        if interaction.guild is None:
            await interaction.response.send_message("Usa este comando en un servidor.", ephemeral=True)
            return
        await self.db.set_guild_setting(interaction.guild.id, "default_role_id", rol.id if rol else 0)
        await interaction.response.send_message(
            f"Rol automático: {rol.mention if rol else 'desactivado'}.", ephemeral=True
        )

    # ==========================================
    # LISTENERS DE BIENVENIDA Y DESPEDIDA
    # ==========================================
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Asignar rol automático por defecto si está configurado
        role_id = await self._guild_setting(member.guild.id, "role", Config.ROLE_DEFAULT_ID)
        if role_id:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role)
                except discord.HTTPException:
                    logger.warning("No se pudo asignar el rol automático en %s", member.guild.id)

        # Enviar tarjeta / mensaje de bienvenida
        channel_id = await self._guild_setting(member.guild.id, "welcome", Config.CHANNEL_WELCOME_ID)
        welcome_channel = self.bot.get_channel(channel_id)
        if not welcome_channel:
            return

        embed = discord.Embed(
            title="👋 ¡Nuevo miembro en la comunidad!",
            description=f"¡Bienvenido/a {member.mention} al servidor! Pásatelo en grande y échale un vistazo a las normas.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Miembro #{member.guild.member_count}")
        await welcome_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        channel_id = await self._guild_setting(member.guild.id, "welcome", Config.CHANNEL_WELCOME_ID)
        welcome_channel = self.bot.get_channel(channel_id)
        if not welcome_channel:
            return

        embed = discord.Embed(
            title="📤 ¡Hasta luego!",
            description=f"**{member.display_name}** ha abandonado el servidor.",
            color=discord.Color.dark_grey(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await welcome_channel.send(embed=embed)

    # ==========================================
    # COMANDOS DE UTILIDAD
    # ==========================================
    @app_commands.command(name="encuesta", description="Crea una encuesta rápida con reacciones o votación.")
    @app_commands.describe(pregunta="Pregunta o enunciado de la encuesta")
    async def encuesta(self, interaction: discord.Interaction, pregunta: str):
        embed = discord.Embed(
            title="📊 Encuesta Oficial",
            description=pregunta,
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Encuesta creada por {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        
        await interaction.response.send_message("Encuesta publicada con éxito.", ephemeral=True)
        message = await interaction.channel.send(embed=embed)
        
        # Reacciones automáticas para votar
        await message.add_reaction("👍")
        await message.add_reaction("👎")

    @app_commands.command(name="recordatorio", description="Haz que el bot te envíe un recordatorio pasado un tiempo.")
    @app_commands.describe(tiempo_minutos="Minutos a esperar", mensaje="De qué quieres que te avise")
    async def recordatorio(self, interaction: discord.Interaction, tiempo_minutos: int, mensaje: str):
        if tiempo_minutos <= 0 or tiempo_minutos > 10080:
            await interaction.response.send_message("El tiempo debe estar entre 1 minuto y 7 días.", ephemeral=True)
            return

        due_at = datetime.now(timezone.utc) + timedelta(minutes=tiempo_minutos)
        guild_id = interaction.guild.id if interaction.guild else 0
        reminder_id = await self.db.add_reminder(
            interaction.user.id, guild_id, interaction.channel_id, mensaje, due_at.isoformat()
        )
        await interaction.response.send_message(
            f"Recordatorio **#{reminder_id}** guardado para dentro de **{tiempo_minutos} minutos**.",
            ephemeral=True,
        )

async def setup(bot):
    await bot.add_cog(UtilityCog(bot))