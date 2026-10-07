import discord
from discord import app_commands
from discord.ext import commands
import random
import time
from config import Config

class LevelsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignorar mensajes de bots o mensajes directos (DMs)
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        current_time = time.time()
        db = self.db.for_guild(message.guild.id)

        # Obtener datos actuales del usuario desde la base de datos
        # Calcular XP aleatoria ganada por mensaje
        xp_gain = random.randint(Config.XP_PER_MESSAGE_MIN, Config.XP_PER_MESSAGE_MAX)
        levels_gained = await db.update_user_xp_level(
            user_id, xp_gain, Config.LEVEL_UP_MULTIPLIER, current_time,
            Config.XP_COOLDOWN_SECONDS,
        )
        if levels_gained < 0:
            return

        # Si ha subido de nivel, avisar en el chat
        if levels_gained:
            updated = await db.get_user(user_id)
            await message.channel.send(
                f"🎉 ¡Enhorabuena {message.author.mention}! Has subido al **nivel {updated['level']}**."
            )

    @app_commands.command(name="nivel", description="Consulta tu nivel actual y experiencia o la de otro usuario.")
    @app_commands.describe(usuario="Usuario del que quieres ver el nivel (opcional)")
    async def nivel(self, interaction: discord.Interaction, usuario: discord.Member = None):
        db = self.db.for_guild(interaction.guild.id if interaction.guild else 0)
        target = usuario or interaction.user
        user_data = await db.get_user(target.id)
        
        current_level = user_data["level"]
        current_xp = user_data["xp"]
        xp_needed = current_level * Config.LEVEL_UP_MULTIPLIER

        embed = discord.Embed(
            title=f"📊 Nivel de {target.display_name}",
            description=f"**Nivel:** {current_level}\n**Experiencia:** {current_xp} / {xp_needed} XP",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(LevelsCog(bot))