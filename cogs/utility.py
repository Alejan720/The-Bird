import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from config import Config

class UtilityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==========================================
    # LISTENERS DE BIENVENIDA Y DESPEDIDA
    # ==========================================
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Asignar rol automático por defecto si está configurado
        if Config.ROLE_DEFAULT_ID != 000000000000000000:
            role = member.guild.get_role(Config.ROLE_DEFAULT_ID)
            if role:
                try:
                    await member.add_roles(role)
                except Exception:
                    pass

        # Enviar tarjeta / mensaje de bienvenida
        welcome_channel = self.bot.get_channel(Config.CHANNEL_WELCOME_ID)
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
        welcome_channel = self.bot.get_channel(Config.CHANNEL_WELCOME_ID)
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
        if tiempo_minutos <= 0:
            await interaction.response.send_message("El tiempo debe ser mayor a 0 minutos.", ephemeral=True)
            return

        await interaction.response.send_message(f"⏰ Entendido. Te recordaré: *'{mensaje}'* en **{tiempo_minutos} minutos**.", ephemeral=True)
        
        # Esperar en segundo plano el tiempo indicado
        await asyncio.sleep(tiempo_minutos * 60)
        
        try:
            await interaction.user.send(f"🔔 **¡RECORDATORIO!**\nHan pasado {tiempo_minutos} minutos. Dijiste:\n> {mensaje}")
        except Exception:
            # Si tiene los DMs cerrados, intenta avisar en el canal donde lo pidió
            await interaction.channel.send(f"🔔 {interaction.user.mention} ¡Tu recordatorio de hace {tiempo_minutos} minutos:\n> {mensaje}")

async def setup(bot):
    await bot.add_cog(UtilityCog(bot))