import discord
from discord import app_commands
from discord.ext import commands
import random
from database import Database
from config import Config

class CoinflipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @app_commands.command(name="coinflip", description="Apunta monedas a Cara o Cruz y prueba tu suerte al 50%.")
    @app_commands.choices(eleccion=[
        app_commands.Choice(name="Cara", value="cara"),
        app_commands.Choice(name="Cruz", value="cruz")
    ])
    @app_commands.describe(apuesta="Cantidad de monedas a apostar", eleccion="Elige Cara o Cruz")
    async def coinflip(self, interaction: discord.Interaction, apuesta: int, eleccion: str):
        if apuesta < Config.BET_MIN_AMOUNT or apuesta > Config.BET_MAX_AMOUNT:
            await interaction.response.send_message(f"❌ La apuesta debe estar entre **{Config.BET_MIN_AMOUNT}** y **{Config.BET_MAX_AMOUNT}** {Config.MONEY_SYMBOL}.", ephemeral=True)
            return

        user_data = await self.db.get_user(interaction.user.id)
        if user_data["balance"] < apuesta:
            await interaction.response.send_message(f"❌ No tienes suficiente dinero. Tu saldo es de {user_data['balance']} {Config.MONEY_SYMBOL}.", ephemeral=True)
            return

        # Tirada al 50%
        resultado = random.choice(["cara", "cruz"])
        gano = (eleccion == resultado)

        if gano:
            await self.db.update_user_balance(interaction.user.id, apuesta) # Recupera lo apostado + gana otro tanto igual
            embed = discord.Embed(
                title="🪙 ¡Moneda al Aire... Victoria!",
                description=f"Ha salido **{resultado.upper()}**. ¡Has ganado **{apuesta} {Config.MONEY_SYMBOL}**!",
                color=discord.Color.green()
            )
        else:
            await self.db.update_user_balance(interaction.user.id, -apuesta) # Pierde la apuesta
            embed = discord.Embed(
                title="🪙 ¡Moneda al Aire... Derrota!",
                description=f"Ha salido **{resultado.upper()}**. Has perdido tu apuesta de **{apuesta} {Config.MONEY_SYMBOL}**.",
                color=discord.Color.red()
            )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(CoinflipCog(bot))