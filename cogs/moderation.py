import logging
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands
from config import Config

logger = logging.getLogger(__name__)


class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    async def _record_case(self, interaction: discord.Interaction, usuario: discord.Member,
                           action: str, reason: str):
        if interaction.guild:
            return await self.db.create_moderation_case(
                interaction.guild.id, usuario.id, interaction.user.id, action, reason,
                discord.utils.utcnow().isoformat(),
            )
        return None

    async def _send_moderation_error(self, interaction: discord.Interaction, action: str, error: Exception):
        if isinstance(error, discord.Forbidden):
            logger.warning("Discord rechazó la acción de moderación '%s': permisos o jerarquía insuficientes.", action)
            message = f"No pude completar la acción: al bot le falta permiso o su rol está por debajo del de {action}."
        elif isinstance(error, discord.HTTPException):
            logger.warning("Error HTTP de Discord durante la acción '%s': %s", action, error)
            message = f"Discord no pudo completar la acción de {action}. Inténtalo de nuevo más tarde."
        else:
            logger.error(
                "Error inesperado en moderación (%s).",
                action,
                exc_info=(type(error), error, error.__traceback__),
            )
            message = "Ocurrió un error inesperado. El incidente quedó registrado para su revisión."

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    # ==========================================
    # COMANDOS DE MODERACIÓN
    # ==========================================
    @app_commands.command(name="mute", description="Silencia temporalmente a un usuario en el servidor.")
    @app_commands.describe(usuario="Usuario a silenciar", razon="Motivo del silencio")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, usuario: discord.Member,
                   duracion_minutos: app_commands.Range[int, 1, 40320] = 60,
                   razon: str = "No especificada"):
        try:
            duration = discord.utils.utcnow() + timedelta(minutes=duracion_minutos)
            await usuario.timeout(duration, reason=razon)
        except Exception as error:
            await self._send_moderation_error(interaction, "silenciar", error)
            return

        case_id = await self._record_case(interaction, usuario, "timeout", razon)

        embed = discord.Embed(
            title="🔇 Usuario Silenciado",
            description=f"**Usuario:** {usuario.mention}\n**Duración:** {duracion_minutos} min\n**Motivo:** {razon}\n**Moderador:** {interaction.user.mention}\n**Caso:** {case_id}",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="kick", description="Expulsa a un usuario del servidor.")
    @app_commands.describe(usuario="Usuario a expulsar", razon="Motivo de la expulsión")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, usuario: discord.Member, razon: str = "No especificada"):
        try:
            await usuario.kick(reason=razon)
        except Exception as error:
            await self._send_moderation_error(interaction, "expulsar", error)
            return

        case_id = await self._record_case(interaction, usuario, "kick", razon)

        embed = discord.Embed(
            title="👢 Usuario Expulsado",
            description=f"**Usuario:** {usuario.mention}\n**Motivo:** {razon}\n**Moderador:** {interaction.user.mention}\n**Caso:** {case_id}",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ban", description="Banea permanentemente a un usuario del servidor.")
    @app_commands.describe(
        usuario="Usuario a banear",
        borrar_mensajes_dias="Días de mensajes recientes a borrar (0 a 7)",
        razon="Motivo del baneo",
    )
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, usuario: discord.Member,
                  borrar_mensajes_dias: app_commands.Range[int, 0, 7] = 0,
                  razon: str = "No especificada"):
        try:
            await usuario.ban(delete_message_seconds=borrar_mensajes_dias * 86400, reason=razon)
        except Exception as error:
            await self._send_moderation_error(interaction, "banear", error)
            return

        case_id = await self._record_case(interaction, usuario, "ban", razon)

        embed = discord.Embed(
            title="🔨 Usuario Baneado",
            description=f"**Usuario:** {usuario.mention}\n**Mensajes borrados:** {borrar_mensajes_dias} días\n**Motivo:** {razon}\n**Moderador:** {interaction.user.mention}\n**Caso:** {case_id}",
            color=discord.Color.dark_red(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="advertir", description="Registra una advertencia formal para un miembro.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def advertir(self, interaction: discord.Interaction, usuario: discord.Member, razon: str):
        case_id = await self._record_case(interaction, usuario, "warning", razon)
        await interaction.response.send_message(
            f"⚠️ {usuario.mention} recibió una advertencia. Caso **#{case_id}**. Motivo: {razon}"
        )

    @app_commands.command(name="historial_mod", description="Consulta los últimos casos de moderación de un miembro.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def historial_mod(self, interaction: discord.Interaction, usuario: discord.Member):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona dentro de un servidor.", ephemeral=True)
            return
        cases = await self.db.get_moderation_cases(interaction.guild.id, usuario.id)
        lines = [
            f"**#{case_id} {action}** · <@{moderator_id}> · {reason[:140]} · <t:{int(datetime.fromisoformat(created_at).timestamp())}:R>"
            for case_id, moderator_id, action, reason, created_at in cases
        ]
        await interaction.response.send_message(
            embed=discord.Embed(
                title=f"Historial de moderación: {usuario.display_name}",
                description="\n".join(lines) or "No hay casos registrados.",
                color=discord.Color.orange(),
            ),
            ephemeral=True,
        )

    @app_commands.command(name="limpiar", description="Elimina mensajes recientes del canal (máximo 100).")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def limpiar(self, interaction: discord.Interaction, cantidad: app_commands.Range[int, 1, 100]):
        if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Este comando solo funciona en canales de texto del servidor.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            deleted = await interaction.channel.purge(limit=cantidad)
        except discord.Forbidden:
            await interaction.followup.send("Al bot le falta el permiso para gestionar mensajes.", ephemeral=True)
            return
        except discord.HTTPException as error:
            logger.warning("Discord rechazó la limpieza del canal %s: %s", interaction.channel.id, error)
            await interaction.followup.send("No pude borrar los mensajes. Inténtalo de nuevo.", ephemeral=True)
            return
        await interaction.followup.send(f"Eliminé **{len(deleted)}** mensajes.", ephemeral=True)

    # ==========================================
    # LISTENERS DE AUDITORÍA (LOGS)
    # ==========================================
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        settings = await self.db.get_guild_settings(message.guild.id)
        logs_channel_id = Config.CHANNEL_LOGS_ID if settings[1] is None else settings[1]
        logs_channel = self.bot.get_channel(logs_channel_id)
        if not logs_channel:
            return

        embed = discord.Embed(
            title="🗑️ Mensaje Borrado",
            description=f"**Autor:** {message.author.mention}\n**Canal:** {message.channel.mention}\n**Contenido:**\n{message.content or '[Sin contenido / Embed o Imagen]'}",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        await logs_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild or before.content == after.content:
            return

        settings = await self.db.get_guild_settings(before.guild.id)
        logs_channel_id = Config.CHANNEL_LOGS_ID if settings[1] is None else settings[1]
        logs_channel = self.bot.get_channel(logs_channel_id)
        if not logs_channel:
            return

        embed = discord.Embed(
            title="✏️ Mensaje Editado",
            description=f"**Autor:** {before.author.mention} en {before.channel.mention}",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Antes", value=before.content or '[Vacío]', inline=False)
        embed.add_field(name="Después", value=after.content or '[Vacío]', inline=False)
        await logs_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))