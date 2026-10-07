import random
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import Config


class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.market_tick.start()

    def _database(self, interaction: discord.Interaction):
        return self.db.for_guild(interaction.guild.id if interaction.guild else 0)

    def cog_unload(self):
        self.market_tick.cancel()

    @tasks.loop(minutes=Config.MARKET_UPDATE_INTERVAL_MIN)
    async def market_tick(self):
        await self.db.advance_market(datetime.now(timezone.utc))

    @market_tick.before_loop
    async def before_market_tick(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="balance", description="Consulta tu dinero, inversiones y propiedades.")
    @app_commands.describe(usuario="Usuario del que quieres consultar la economía")
    async def balance(self, interaction: discord.Interaction, usuario: discord.Member = None):
        db = self._database(interaction)
        target = usuario or interaction.user
        data = await db.get_user(target.id)
        embed = discord.Embed(title=f"Economía de {target.display_name}", color=discord.Color.gold())
        embed.add_field(name="Monedero", value=f"{data['balance']:,} {Config.MONEY_SYMBOL}")
        embed.add_field(name="Banco", value=f"{data['bank']:,} {Config.MONEY_SYMBOL}")
        cash, bank, investments, properties = await db.get_user_wealth(target.id)
        embed.add_field(
            name="Patrimonio",
            value=f"{cash + bank + investments + properties:,} {Config.MONEY_SYMBOL}",
        )
        embed.set_footer(
            text=f"Inversiones: {investments:,} | Propiedades: {properties:,} {Config.MONEY_SYMBOL}"
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pagar", description="Transfiere monedas de tu monedero a otro usuario.")
    async def pagar(self, interaction: discord.Interaction, usuario: discord.Member, cantidad: app_commands.Range[int, 1]):
        db = self._database(interaction)
        if usuario.bot or usuario.id == interaction.user.id:
            await interaction.response.send_message("Elige a otra persona, no un bot ni a ti mismo.", ephemeral=True)
            return
        if not await db.transfer(interaction.user.id, usuario.id, cantidad):
            await interaction.response.send_message("No tienes suficiente dinero en el monedero.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Transferiste **{cantidad:,} {Config.MONEY_SYMBOL}** a {usuario.mention}."
        )

    async def _admin_adjust_money(self, interaction: discord.Interaction, usuario: discord.Member,
                                  cantidad: int, motivo: str, action: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona dentro de un servidor.", ephemeral=True)
            return
        db = self._database(interaction)
        changed = await db.admin_adjust_balance(
            interaction.guild.id, interaction.user.id, usuario.id, cantidad, action,
            motivo, datetime.now(timezone.utc).isoformat(),
        )
        if not changed:
            await interaction.response.send_message(
                "No se pudo aplicar: la persona no tiene suficiente saldo para retirar esa cantidad.",
                ephemeral=True,
            )
            return
        verb = "Concediste" if action == "grant" else "Retiraste"
        await interaction.response.send_message(
            f"{verb} **{cantidad:,} {Config.MONEY_SYMBOL}** a {usuario.mention}. Motivo: {motivo}"
        )

    @app_commands.command(name="dar_dinero", description="Comando admin: concede monedas por premios o compensaciones.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(usuario="Quién recibe el premio", cantidad="Monedas a conceder", motivo="Razón del ajuste")
    async def dar_dinero(self, interaction: discord.Interaction, usuario: discord.Member,
                         cantidad: app_commands.Range[int, 1, 1000000], motivo: str):
        await self._admin_adjust_money(interaction, usuario, cantidad, motivo, "grant")

    @app_commands.command(name="quitar_dinero", description="Comando admin: retira monedas como sanción o corrección.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(usuario="A quién se le retira", cantidad="Monedas a retirar", motivo="Razón del ajuste")
    async def quitar_dinero(self, interaction: discord.Interaction, usuario: discord.Member,
                            cantidad: app_commands.Range[int, 1, 1000000], motivo: str):
        await self._admin_adjust_money(interaction, usuario, cantidad, motivo, "remove")

    @app_commands.command(name="historial_dinero", description="Comando admin: consulta los últimos ajustes manuales de saldo.")
    @app_commands.checks.has_permissions(administrator=True)
    async def historial_dinero(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona dentro de un servidor.", ephemeral=True)
            return
        entries = await self.db.get_economy_audit(interaction.guild.id)
        lines = [
            f"`{action}` <@{target}>: **{amount:,}** por <@{actor}>. {reason[:120]} · <t:{int(datetime.fromisoformat(created_at).timestamp())}:R>"
            for actor, target, amount, action, reason, created_at in entries
        ]
        embed = discord.Embed(
            title="Últimos ajustes administrativos",
            description="\n".join(lines) or "Todavía no hay ajustes registrados.",
            color=discord.Color.dark_gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="diario", description="Reclama tu recompensa diaria y aumenta tu racha.")
    async def diario(self, interaction: discord.Interaction):
        db = self._database(interaction)
        now = datetime.now(timezone.utc)
        data = await db.get_user(interaction.user.id)
        streak = data["daily_streak"]
        bonus = min(max(streak, 0) * Config.DAILY_STREAK_BONUS, Config.DAILY_STREAK_BONUS_CAP)
        reward = random.randint(Config.DAILY_REWARD_MIN, Config.DAILY_REWARD_MAX) + bonus
        claimed, value, streak = await db.claim_reward(
            interaction.user.id, "last_daily", Config.DAILY_COOLDOWN_HOURS * 3600,
            reward, now.isoformat(),
        )
        if not claimed:
            hours, remainder = divmod(value, 3600)
            minutes = remainder // 60
            await interaction.response.send_message(
                f"Ya reclamaste el diario. Vuelve en **{hours}h {minutes}m**.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"Reclamaste **{value:,} {Config.MONEY_SYMBOL}**. Racha diaria: **{streak}** días."
        )

    @app_commands.command(name="trabajar", description="Completa un trabajo para ganar monedas cada hora.")
    async def trabajar(self, interaction: discord.Interaction):
        db = self._database(interaction)
        now = datetime.now(timezone.utc)
        reward = random.randint(Config.WORK_REWARD_MIN, Config.WORK_REWARD_MAX)
        claimed, value, _ = await db.claim_reward(
            interaction.user.id, "last_work", Config.WORK_COOLDOWN_MINUTES * 60,
            reward, now.isoformat(),
        )
        if not claimed:
            minutes, seconds = divmod(value, 60)
            await interaction.response.send_message(
                f"Ya trabajaste recientemente. Vuelve en **{minutes}m {seconds}s**.", ephemeral=True
            )
            return
        jobs = ["reparaste una nave", "entregaste un paquete", "preparaste café", "arreglaste un servidor"]
        await interaction.response.send_message(
            f"{random.choice(jobs)} y ganaste **{value:,} {Config.MONEY_SYMBOL}**."
        )

    async def _bank_command(self, interaction: discord.Interaction, cantidad: int, deposit: bool):
        db = self._database(interaction)
        if cantidad <= 0:
            await interaction.response.send_message("La cantidad debe ser mayor que cero.", ephemeral=True)
            return
        if not await db.bank_transfer(interaction.user.id, cantidad, deposit):
            source = "monedero" if deposit else "banco"
            await interaction.response.send_message(f"No tienes esa cantidad en tu {source}.", ephemeral=True)
            return
        action = "depositaste en el banco" if deposit else "retiraste del banco"
        await interaction.response.send_message(f"{action} **{cantidad:,} {Config.MONEY_SYMBOL}**.")

    @app_commands.command(name="depositar", description="Guarda monedas en tu banco.")
    async def depositar(self, interaction: discord.Interaction, cantidad: app_commands.Range[int, 1]):
        await self._bank_command(interaction, cantidad, True)

    @app_commands.command(name="retirar", description="Retira monedas de tu banco al monedero.")
    async def retirar(self, interaction: discord.Interaction, cantidad: app_commands.Range[int, 1]):
        await self._bank_command(interaction, cantidad, False)

    @app_commands.command(name="robar", description="Intenta robar monedas con riesgo de multa.")
    async def robar(self, interaction: discord.Interaction, usuario: discord.Member):
        db = self._database(interaction)
        if usuario.bot or usuario.id == interaction.user.id:
            await interaction.response.send_message("No puedes robar a bots ni a ti mismo.", ephemeral=True)
            return
        result, amount, _ = await db.rob(
            interaction.user.id, usuario.id, datetime.now(timezone.utc).isoformat(),
            Config.ROB_COOLDOWN_MINUTES * 60, Config.ROB_SUCCESS_BASE_CHANCE,
            Config.ROB_FINE_PERCENTAGE, random.randint(10, 30),
        )
        if result == "cooldown":
            minutes, seconds = divmod(amount, 60)
            text = f"La policía aún te busca. Espera **{minutes}m {seconds}s**."
        elif result == "poor":
            text = "Esa persona no lleva suficiente dinero en el monedero."
        elif result == "shield":
            text = f"El escudo de {usuario.mention} bloqueó el robo y se consumió."
        elif result == "success":
            text = f"Robo exitoso: obtuviste **{amount:,} {Config.MONEY_SYMBOL}** de {usuario.mention}."
        elif result == "insured":
            text = "Te descubrieron, pero tu seguro cubrió la multa y se consumió."
        else:
            text = f"Te descubrieron y pagaste una multa de **{amount:,} {Config.MONEY_SYMBOL}**."
        await interaction.response.send_message(text)

    @app_commands.command(name="tienda", description="Compra escudos, ganzúas, café, cajas misteriosas o lotería.")
    @app_commands.choices(objeto=[
        app_commands.Choice(name="Escudo (bloquea un robo)", value="escudo"),
        app_commands.Choice(name="Ganzúa (un intento con más probabilidad)", value="ganzua"),
        app_commands.Choice(name="Café (mejora el próximo trabajo)", value="cafe"),
        app_commands.Choice(name="Caja misteriosa", value="caja"),
        app_commands.Choice(name="Cupón diario (+100% en el próximo diario)", value="cupon_diario"),
        app_commands.Choice(name="Seguro contra multa de robo", value="seguro"),
        app_commands.Choice(name="Billete de lotería", value="loteria"),
    ])
    async def tienda(self, interaction: discord.Interaction, objeto: str):
        db = self._database(interaction)
        prices = {
            "escudo": (Config.SHIELD_PRICE, "Escudo protector"),
            "ganzua": (Config.LOCKPICK_PRICE, "Ganzúa"),
            "cafe": (Config.CAFE_PRICE, "Café energético"),
            "caja": (Config.MYSTERY_CRATE_PRICE, "Caja misteriosa"),
            "cupon_diario": (Config.DAILY_COUPON_PRICE, "Cupón diario"),
            "seguro": (Config.ROBBERY_INSURANCE_PRICE, "Seguro contra multas"),
            "loteria": (Config.LOTTERY_TICKET_PRICE, "Billete de lotería"),
        }
        price, name = prices[objeto]
        if objeto == "loteria":
            prize = random.choices([0, 50, 150, 400, 1000], weights=[50, 25, 15, 8, 2])[0]
            purchased = await db.settle_lottery(interaction.user.id, price, prize)
        else:
            expiry = (datetime.now(timezone.utc) + timedelta(hours=Config.SHIELD_DURATION_HOURS)).isoformat() if objeto == "escudo" else None
            purchased = await db.purchase_item(interaction.user.id, objeto, price, expiry)
            prize = 0
        if not purchased:
            await interaction.response.send_message(
                f"No tienes suficiente dinero. Precio: **{price:,} {Config.MONEY_SYMBOL}**.", ephemeral=True
            )
            return
        if objeto == "loteria":
            net = prize - price
            outcome = "sin premio" if prize == 0 else f"premio de **{prize:,} {Config.MONEY_SYMBOL}**"
            await interaction.response.send_message(
                f"La lotería dio {outcome}. Resultado neto: **{net:+,} {Config.MONEY_SYMBOL}**."
            )
        else:
            await interaction.response.send_message(
                f"Compraste **{name}** por **{price:,} {Config.MONEY_SYMBOL}**."
            )

    @app_commands.command(name="mochila", description="Consulta tus objetos disponibles.")
    async def mochila(self, interaction: discord.Interaction):
        items = await self._database(interaction).get_inventory(interaction.user.id)
        labels = {
            "escudo": "Escudos", "ganzua": "Ganzúas", "cafe": "Cafés",
            "caja": "Cajas misteriosas", "cupon_diario": "Cupones diarios",
            "seguro": "Seguros contra multas",
        }
        description = "\n".join(f"**{labels.get(name, name)}:** {quantity}" for name, quantity, _ in items)
        embed = discord.Embed(
            title=f"Mochila de {interaction.user.display_name}",
            description=description or "No tienes objetos.", color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="usar", description="Usa un objeto consumible de tu mochila.")
    @app_commands.choices(objeto=[
        app_commands.Choice(name="Café energético", value="cafe"),
        app_commands.Choice(name="Caja misteriosa", value="caja"),
        app_commands.Choice(name="Cupón diario", value="cupon_diario"),
        app_commands.Choice(name="Seguro contra multas", value="seguro"),
    ])
    async def usar(self, interaction: discord.Interaction, objeto: str):
        db = self._database(interaction)
        if objeto == "cafe":
            used = await db.activate_work_boost(interaction.user.id, Config.CAFE_BOOST_PERCENT)
            response = (
                f"Café activado: tu próximo `/trabajar` paga +{Config.CAFE_BOOST_PERCENT}%."
                if used else "No tienes café energético."
            )
        elif objeto == "caja":
            prize = random.choices([0, 100, 300, 750, 2000], weights=[45, 30, 17, 7, 1])[0]
            used = await db.open_crate(interaction.user.id, prize)
            response = (
                f"La caja contenía **{prize:,} {Config.MONEY_SYMBOL}**."
                if used else "No tienes cajas misteriosas."
            )
        elif objeto == "cupon_diario":
            used = await db.activate_daily_coupon(interaction.user.id)
            response = "Cupón activado: tu próximo `/diario` tendrá +100%." if used else "No tienes cupones diarios."
        else:
            used = await db.activate_robbery_insurance(interaction.user.id)
            response = "Seguro activado para cubrir la próxima multa de robo." if used else "No tienes seguros contra multas."
        await interaction.response.send_message(response, ephemeral=not used)

    @app_commands.command(name="mercado", description="Consulta precios, variación y presión de compra/venta.")
    async def mercado(self, interaction: discord.Interaction):
        assets = await self.db.get_market_assets()
        embed = discord.Embed(title="Mercado de inversiones", color=discord.Color.teal())
        for symbol, name, price, change, buys, sells in assets:
            trend = "📈" if change > 0 else "📉" if change < 0 else "➖"
            embed.add_field(
                name=f"{symbol} · {name}",
                value=f"**{price:,}** {Config.MONEY_SYMBOL}  {trend} {change:+.2f}%\nCompra/Venta reciente: {buys:,}/{sells:,}",
                inline=False,
            )
        embed.set_footer(text="Precios dinámicos por hora; la actividad compradora y vendedora influye en el siguiente cambio.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="comprar_accion", description="Compra unidades de una inversión del mercado.")
    @app_commands.choices(activo=[
        app_commands.Choice(name="AUR · Aurora Energy", value="AUR"),
        app_commands.Choice(name="NEX · Nexus Robotics", value="NEX"),
        app_commands.Choice(name="VER · Verde Biotech", value="VER"),
        app_commands.Choice(name="ORB · Orbit Transport", value="ORB"),
        app_commands.Choice(name="CRY · Cryo Mining", value="CRY"),
        app_commands.Choice(name="MED · MedNova Health", value="MED"),
        app_commands.Choice(name="SOL · Solstice Water", value="SOL"),
    ])
    async def comprar_accion(self, interaction: discord.Interaction, activo: str,
                             cantidad: app_commands.Range[int, 1, Config.MARKET_ORDER_MAX]):
        success, price, total, _ = await self._database(interaction).trade_asset(interaction.user.id, activo, cantidad, True)
        text = (
            f"Compraste **{cantidad} {activo}** a {price:,} cada una. Total: **{total:,} {Config.MONEY_SYMBOL}**."
            if success else f"Compra no realizada. Revisa tu saldo o la clave del activo. Coste estimado: {total:,}."
        )
        await interaction.response.send_message(text, ephemeral=not success)

    @app_commands.command(name="vender_accion", description="Vende unidades que tengas en cartera.")
    @app_commands.choices(activo=[
        app_commands.Choice(name="AUR · Aurora Energy", value="AUR"),
        app_commands.Choice(name="NEX · Nexus Robotics", value="NEX"),
        app_commands.Choice(name="VER · Verde Biotech", value="VER"),
        app_commands.Choice(name="ORB · Orbit Transport", value="ORB"),
        app_commands.Choice(name="CRY · Cryo Mining", value="CRY"),
        app_commands.Choice(name="MED · MedNova Health", value="MED"),
        app_commands.Choice(name="SOL · Solstice Water", value="SOL"),
    ])
    async def vender_accion(self, interaction: discord.Interaction, activo: str,
                            cantidad: app_commands.Range[int, 1, Config.MARKET_ORDER_MAX]):
        success, price, total, profit = await self._database(interaction).trade_asset(interaction.user.id, activo, cantidad, False)
        text = (
            f"Vendiste **{cantidad} {activo}** a {price:,} cada una. Recibiste **{total:,} {Config.MONEY_SYMBOL}**; resultado realizado: **{profit:+,.0f} {Config.MONEY_SYMBOL}**."
            if success else "No tienes suficientes unidades de ese activo."
        )
        await interaction.response.send_message(text, ephemeral=not success)

    @app_commands.command(name="cartera", description="Consulta tus inversiones y ganancias o pérdidas actuales.")
    async def cartera(self, interaction: discord.Interaction):
        rows = await self._database(interaction).get_portfolio(interaction.user.id)
        lines = [
            f"**{symbol} · {name}** x{quantity}: valor {value:,} {Config.MONEY_SYMBOL} | P/L **{profit:+,.0f} {Config.MONEY_SYMBOL}**"
            for symbol, name, quantity, _, _, value, profit in rows
        ]
        await interaction.response.send_message(
            embed=discord.Embed(title="Tu cartera", description="\n".join(lines) or "No tienes inversiones.", color=discord.Color.teal()),
            ephemeral=True,
        )

    @app_commands.command(name="historial_inversion", description="Consulta tus últimas compras y ventas del mercado.")
    async def historial_inversion(self, interaction: discord.Interaction):
        trades = await self._database(interaction).get_market_trade_history(interaction.user.id)
        lines = [
            f"`{action.upper()}` **{quantity} {symbol}** a {price:,} · total {total:,} · P/L {profit:+,.0f} · <t:{int(datetime.fromisoformat(created_at).timestamp())}:R>"
            for symbol, action, quantity, price, total, profit, created_at in trades
        ]
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Historial de inversiones",
                description="\n".join(lines) or "Todavía no tienes operaciones.",
                color=discord.Color.teal(),
            ),
            ephemeral=True,
        )

    @app_commands.command(name="propiedades", description="Consulta propiedades, precios, rentas y las que posees.")
    async def propiedades(self, interaction: discord.Interaction):
        rows = await self._database(interaction).get_properties(interaction.user.id)
        lines = [
            f"**{name}** (`{key}`) · {price:,} {Config.MONEY_SYMBOL} · renta {rent:,}/h · tuyas: {owned}"
            for key, name, price, rent, owned in rows
        ]
        await interaction.response.send_message(
            embed=discord.Embed(title="Inmobiliaria", description="\n".join(lines), color=discord.Color.green())
        )

    @app_commands.command(name="comprar_propiedad", description="Compra una propiedad que genera renta para tu banco.")
    @app_commands.choices(propiedad=[
        app_commands.Choice(name="Casa compacta · 2.500", value="casa"),
        app_commands.Choice(name="Garaje de barrio · 8.000", value="garaje"),
        app_commands.Choice(name="Apartamento · 12.000", value="apartamento"),
        app_commands.Choice(name="Local comercial · 50.000", value="local"),
        app_commands.Choice(name="Edificio residencial · 125.000", value="edificio"),
        app_commands.Choice(name="Hotel costero · 300.000", value="hotel"),
    ])
    async def comprar_propiedad(self, interaction: discord.Interaction, propiedad: str):
        success, price = await self._database(interaction).buy_property(
            interaction.user.id, propiedad, datetime.now(timezone.utc).isoformat()
        )
        text = (
            f"Propiedad comprada por **{price:,} {Config.MONEY_SYMBOL}**. Generará renta pasiva; usa `/cobrar_renta`."
            if success else f"No tienes suficiente dinero. Precio: **{price:,} {Config.MONEY_SYMBOL}**."
        )
        await interaction.response.send_message(text, ephemeral=not success)

    @app_commands.command(name="vender_propiedad", description="Vende una propiedad por el 75% de su precio de catálogo.")
    @app_commands.choices(propiedad=[
        app_commands.Choice(name="Casa compacta", value="casa"),
        app_commands.Choice(name="Garaje de barrio", value="garaje"),
        app_commands.Choice(name="Apartamento", value="apartamento"),
        app_commands.Choice(name="Local comercial", value="local"),
        app_commands.Choice(name="Edificio residencial", value="edificio"),
        app_commands.Choice(name="Hotel costero", value="hotel"),
    ])
    async def vender_propiedad(self, interaction: discord.Interaction, propiedad: str):
        success, payout = await self._database(interaction).sell_property(interaction.user.id, propiedad)
        text = (
            f"Vendiste la propiedad y recibiste **{payout:,} {Config.MONEY_SYMBOL}** (75% del precio de catálogo)."
            if success else "No tienes una propiedad de ese tipo para vender."
        )
        await interaction.response.send_message(text, ephemeral=not success)

    @app_commands.command(name="cobrar_renta", description="Deposita en el banco la renta acumulada de tus propiedades.")
    async def cobrar_renta(self, interaction: discord.Interaction):
        payout = await self._database(interaction).collect_rent(interaction.user.id, datetime.now(timezone.utc))
        text = f"Se depositaron **{payout:,} {Config.MONEY_SYMBOL}** en tu banco." if payout else "Aún no se ha acumulado una hora de renta."
        await interaction.response.send_message(text, ephemeral=not payout)

    @app_commands.command(name="top_economia", description="Muestra a los diez usuarios con mayor patrimonio.")
    async def top_economia(self, interaction: discord.Interaction):
        rows = await self._database(interaction).get_leaderboard(10)
        lines = []
        for position, (user_id, wealth) in enumerate(rows, start=1):
            member = interaction.guild.get_member(user_id) if interaction.guild else None
            name = member.display_name if member else f"Usuario {user_id}"
            lines.append(f"**{position}.** {name}: {wealth:,} {Config.MONEY_SYMBOL}")
        await interaction.response.send_message(
            embed=discord.Embed(title="Patrimonio del servidor", description="\n".join(lines) or "Sin datos.", color=discord.Color.gold())
        )


async def setup(bot):
    await bot.add_cog(EconomyCog(bot))