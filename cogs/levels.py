import discord
from discord import app_commands
from discord.ext import commands
import random
import time
from database import Database
from config import Config

class LevelsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignorar mensajes de bots o mensajes directos (DMs)
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        current_time = time.time()

        # Obtener datos actuales del usuario desde la base de datos
        user_data = await self.db.get_user(user_id)
        last_msg_time = user_data["last_message_time"]

        # Comprobar el cooldown anti-spam para la experiencia
        if current_time - last_msg_time < Config.XP_COOLDOWN_SECONDS:
            return

        # Calcular XP aleatoria ganada por mensaje
        xp_gain = random.randint(Config.XP_PER_MESSAGE_MIN, Config.XP_PER_MESSAGE_MAX)
        new_xp = user_data["xp"] + xp_gain
        current_level = user_data["level"]

        # Calcular la XP necesaria para el siguiente nivel
        xp_needed = current_level * Config.LEVEL_UP_MULTIPLIER

        new_level = current_level
        leveled_up = False

        # Comprobar si sube de nivel
        if new_xp >= xp_needed:
            new_level += 1
            leveled_up = True

        # Actualizar en la base de datos
        await self.db.update_user_xp_level(user_id, xp_gain, new_level, current_time)

        # Si ha subido de nivel, avisar en el chat
        if leveled_up:
            await message.channel.send(f"🎉 ¡Enhorabuena {message.author.mention}! Has subido al **nivel {new_level}**.")

    @app_commands.command(name="nivel", description="Consulta tu nivel actual y experiencia o la de otro usuario.")
    @app_commands.describe(usuario="Usuario del que quieres ver el nivel (opcional)")
    async def nivel(self, interaction: discord.Interaction, usuario: discord.Member = None):
        target = usuario or interaction.user
        user_data = await self.db.get_user(target.id)
        
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