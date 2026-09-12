import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta
from database import Database
from config import Config

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.dynamic_market.start() # Arranca la tarea en segundo plano para el mercado de valores

    def cog_unload(self):
        self.dynamic_market.cancel()

    # Tarea en segundo plano para actualizar precios de la bolsa dinámicamente por azar/demanda
    @tasks.loop(minutes=Config.MARKET_UPDATE_INTERVAL_MIN)
    async def dynamic_market(self):
        # Aquí se actualizarían los valores de los activos en la BD según fluctuaciones
        pass

    @app_commands.command(name="balance", description="Consulta tu saldo actual o el de otro usuario.")
    @app_commands.describe(usuario="Usuario del que quieres ver el saldo (opcional)")
    async def balance(self, interaction: discord.Interaction, usuario: discord.Member = None):
        target = usuario or interaction.user
        user_data = await self.db.get_user(target.id)
        
        embed = discord.Embed(
            title=f"💰 Balance de {target.display_name}",
            description=f"**Saldo:** {user_data['balance']} {Config.MONEY_SYMBOL}",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pagar", description="Transfiere dinero de tu monedero a otro usuario.")
    @app_commands.describe(usuario="A quién quieres enviar el dinero", cantidad="Cantidad de monedas")
    async def pagar(self, interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
        if usuario.id == interaction.user.id:
            await interaction.response.send_message("No puedes hacerte una transferencia a ti mismo.", ephemeral=True)
            return
        if cantidad <= 0:
            await interaction.response.send_message("La cantidad debe ser mayor a 0.", ephemeral=True)
            return

        sender_data = await self.db.get_user(interaction.user.id)
        if sender_data["balance"] < cantidad:
            await interaction.response.send_message(f"❌ No tienes suficiente dinero. Tu saldo es de {sender_data['balance']} {Config.MONEY_SYMBOL}.", ephemeral=True)
            return

        await self.db.update_user_balance(interaction.user.id, -cantidad)
        await self.db.update_user_balance(usuario.id, cantidad)

        embed = discord.Embed(
            title="💸 Transferencia Exitosa",
            description=f"Has enviado **{cantidad} {Config.MONEY_SYMBOL}** a {usuario.mention}.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="diario", description="Reclama tu recompensa económica diaria.")
    async def diario(self, interaction: discord.Interaction):
        user_data = await self.db.get_user(interaction.user.id)
        now = datetime.utcnow()
        
        if user_data["last_daily"]:
            last_daily = datetime.fromisoformat(user_data["last_daily"])
            next_available = last_daily + timedelta(hours=Config.DAILY_COOLDOWN_HOURS)
            
            if now < next_available:
                remaining = next_available - now
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                await interaction.response.send_message(
                    f"⏳ Ya has reclamado tu recompensa diaria. Vuelve en **{hours}h {minutes}m**.",
                    ephemeral=True
                )
                return

        reward = random.randint(Config.DAILY_REWARD_MIN, Config.DAILY_REWARD_MAX)
        await self.db.update_user_balance(interaction.user.id, reward)
        
        async with self.db.connect() as db:
            await db.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (now.isoformat(), interaction.user.id))
            await db.commit()

        embed = discord.Embed(
            title="🎁 Recompensa Diaria",
            description=f"¡Has reclamado con éxito tu botín diario de **{reward} {Config.MONEY_SYMBOL}**!",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="robar", description="Intenta robarle monedas a otro usuario (con riesgo de multa).")
    @app_commands.describe(usuario="A quién quieres intentar robar")
    async def robar(self, interaction: discord.Interaction, usuario: discord.Member):
        if usuario.id == interaction.user.id:
            await interaction.response.send_message("No puedes robarte a ti mismo, lumbreras.", ephemeral=True)
            return

        thief_data = await self.db.get_user(interaction.user.id)
        victim_data = await self.db.get_user(usuario.id)
        
        now = datetime.utcnow()
        if thief_data["last_rob"]:
            last_rob = datetime.fromisoformat(thief_data["last_rob"])
            next_available = last_rob + timedelta(minutes=Config.ROB_COOLDOWN_MINUTES)
            if now < next_available:
                remaining = int((next_available - now).total_seconds() / 60)
                await interaction.response.send_message(
                    f"⏳ Estás marcado por la policía. Espera **{remaining} minutos** para volver a robar.",
                    ephemeral=True
                )
                return

        if victim_data["balance"] <= 50:
            await interaction.response.send_message("Ese usuario es demasiado pobre, no merece la pena arriesgarse.", ephemeral=True)
            return

        shield_count = await self.db.get_item_count(usuario.id, "escudo")
        if shield_count > 0:
            await interaction.response.send_message(f"🛡️ ¡El robo ha fracasado! {usuario.mention} tiene un escudo protector activo.", ephemeral=False)
            async with self.db.connect() as db:
                await db.execute("UPDATE users SET last_rob = ? WHERE user_id = ?", (now.isoformat(), interaction.user.id))
                await db.commit()
            return

        success_chance = Config.ROB_SUCCESS_BASE_CHANCE
        lockpick_count = await self.db.get_item_count(interaction.user.id, "ganzua")
        if lockpick_count > 0:
            success_chance += 20

        async with self.db.connect() as db:
            await db.execute("UPDATE users SET last_rob = ? WHERE user_id = ?", (now.isoformat(), interaction.user.id))
            await db.commit()

        if random.randint(1, 100) <= success_chance:
            stolen_amount = int(victim_data["balance"] * random.uniform(0.10, 0.30))
            await self.db.update_user_balance(usuario.id, -stolen_amount)
            await self.db.update_user_balance(interaction.user.id, stolen_amount)

            embed = discord.Embed(
                title="🥷 ¡Robo Exitoso!",
                description=f"Te has escurrido con éxito y le has robado **{stolen_amount} {Config.MONEY_SYMBOL}** a {usuario.mention}.",
                color=discord.Color.dark_purple()
            )
            await interaction.response.send_message(embed=embed)
        else:
            fine = int(thief_data["balance"] * (Config.ROB_FINE_PERCENTAGE / 100))
            if fine < 10:
                fine = 10
            if thief_data["balance"] > 0:
                await self.db.update_user_balance(interaction.user.id, -min(fine, thief_data["balance"]))

            embed = discord.Embed(
                title="🚨 ¡Te han pillado!",
                description=f"La policía te ha interceptado. Has tenido que pagar una multa de **{fine} {Config.MONEY_SYMBOL}**.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="tienda", description="Adquiere objetos competitivos y potenciadores.")
    @app_commands.choices(objeto=[
        app_commands.Choice(name="Escudo Protector (Defensa contra robos)", value="escudo"),
        app_commands.Choice(name="Ganzúa de Ladrón (+20% éxito de robo)", value="ganzua"),
        app_commands.Choice(name="Billete de Lotería (Premio aleatorio al instante)", value="loteria")
    ])
    async def tienda(self, interaction: discord.Interaction, objeto: str):
        user_data = await self.db.get_user(interaction.user.id)
        
        if objeto == "escudo":
            price, name = Config.SHIELD_PRICE, "Escudo Protector"
        elif objeto == "ganzua":
            price, name = Config.LOCKPICK_PRICE, "Ganzúa de Ladrón"
        else:
            price, name = 150, "Billete de Lotería"

        if user_data["balance"] < price:
            await interaction.response.send_message(f"❌ No tienes suficiente dinero. Este objeto cuesta **{price} {Config.MONEY_SYMBOL}**.", ephemeral=True)
            return

        await self.db.update_user_balance(interaction.user.id, -price)
        
        if objeto == "loteria":
            premio = random.choice([0, 50, 150, 400, 1000])
            if premio > 0:
                await self.db.update_user_balance(interaction.user.id, premio)
            embed = discord.Embed(
                title="🎟️ Lotería",
                description=f"Has comprado un billete y... ¡Has ganado **{premio} {Config.MONEY_SYMBOL}**!",
                color=discord.Color.magenta()
            )
        else:
            await self.db.add_item(interaction.user.id, objeto, quantity=1)
            embed = discord.Embed(
                title="🛒 Compra Realizada",
                description=f"Has adquirido un/a **{name}** por **{price} {Config.MONEY_SYMBOL}**.",
                color=discord.Color.blue()
            )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))