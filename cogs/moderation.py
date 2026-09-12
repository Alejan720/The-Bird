import discord
from discord import app_commands
from discord.ext import commands
from config import Config

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==========================================
    # COMANDOS DE MODERACIÓN
    # ==========================================
    @app_commands.command(name="mute", description="Silencia temporalmente a un usuario en el servidor.")
    @app_commands.describe(usuario="Usuario a silenciar", razon="Motivo del silencio")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, usuario: discord.Member, razon: str = "No especificada"):
        # Nota: En un bot real se puede usar timeout de Discord. Aquí aplicamos rol o timeout nativo.
        try:
            # Discord permite timeouts nativos mediante delta de tiempo, por ejemplo 1 hora por defecto si no se especifica
            duration = discord.utils.utcnow() + discord.utils.timedelta(hours=1)
            await usuario.timeout(duration, reason=razon)
            
            embed = discord.Embed(
                title="🔇 Usuario Silenciado",
                description=f"**Usuario:** {usuario.mention}\n**Motivo:** {razon}\n**Moderador:** {interaction.user.mention}",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ No se pudo silenciar al usuario. Comprueba permisos.", ephemeral=True)

    @app_commands.command(name="kick", description="Expulsa a un usuario del servidor.")
    @app_commands.describe(usuario="Usuario a expulsar", razon="Motivo de la expulsión")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, usuario: discord.Member, razon: str = "No especificada"):
        try:
            await usuario.kick(reason=razon)
            embed = discord.Embed(
                title="👢 Usuario Expulsado",
                description=f"**Usuario:** {usuario.mention}\n**Motivo:** {razon}\n**Moderador:** {interaction.user.mention}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ No se pudo expulsar al usuario.", ephemeral=True)

    @app_commands.command(name="ban", description="Banea permanentemente a un usuario del servidor.")
    @app_commands.describe(usuario="Usuario a banear", razon="Motivo del baneo")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, usuario: discord.Member, razon: str = "No especificada"):
        try:
            await usuario.ban(reason=razon)
            embed = discord.Embed(
                title="🔨 Usuario Baneado",
                description=f"**Usuario:** {usuario.mention}\n**Motivo:** {razon}\n**Moderador:** {interaction.user.mention}",
                color=discord.Color.dark_red()
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ No se pudo banear al usuario.", ephemeral=True)

    # ==========================================
    # LISTENERS DE AUDITORÍA (LOGS)
    # ==========================================
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        logs_channel = self.bot.get_channel(Config.CHANNEL_LOGS_ID)
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

        logs_channel = self.bot.get_channel(Config.CHANNEL_LOGS_ID)
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