import discord
from discord import app_commands
from discord.ext import commands
import random
from config import Config

class ParchisCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_parchis = {}

    @app_commands.command(name="parchis", description="Lanza el dado y avanza en tu simulación de Parchís exprés.")
    async def parchis(self, interaction: discord.Interaction):
        user = interaction.user
        dado = random.randint(1, 6)
        
        # Simulación de avance en pista de 68 casillas
        embed = discord.Embed(
            title="🎲 Parchís Exprés",
            description=f"{user.mention} ha lanzado el dado y ha obtenido un **{dado}**.",
            color=discord.Color.gold()
        )
        
        if dado == 6:
            embed.add_field(name="¡Premio!", value="¡Has sacado un 6! Puedes repetir tirada o sacar ficha de casa.", inline=False)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(ParchisCog(bot))