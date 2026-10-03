import random

import discord
from discord import app_commands
from discord.ext import commands

from config import Config


class ParchisRollButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Lanzar dado", style=discord.ButtonStyle.primary, emoji="🎲")

    async def callback(self, interaction: discord.Interaction):
        view: ParchisView = self.view
        if interaction.user.id != view.current_player.id:
            await interaction.response.send_message("No es tu turno.", ephemeral=True)
            return
        if view.roll is not None:
            await interaction.response.send_message("Elige una ficha para usar tu tirada.", ephemeral=True)
            return
        view.roll = random.randint(1, 6)
        view.refresh_controls()
        if not view.pawn_select.options or view.pawn_select.options[0].value == "none":
            view.roll = None
            view.pass_turn()
            view.refresh_controls()
            text = "No tienes movimientos posibles. Turno del siguiente jugador."
        else:
            text = f"{interaction.user.mention} sacó **{view.roll}**. Selecciona una ficha."
        await interaction.response.edit_message(content=f"{view.render()}\n\n{text}", view=view)


class ParchisPawnSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Lanza el dado para elegir una ficha",
            min_values=1,
            max_values=1,
            options=[discord.SelectOption(label="Esperando tirada", value="none")],
            disabled=True,
        )

    def refresh(self, view):
        options = []
        if view.roll is not None:
            for index, progress in enumerate(view.pawns[view.current_index]):
                if progress == -1 and view.roll == 6:
                    options.append(discord.SelectOption(label=f"Ficha {index + 1}: salir de casa", value=str(index)))
                elif 0 <= progress < 68 and progress + view.roll <= 68:
                    destination = progress + view.roll
                    action = "llegar a meta" if destination == 68 else f"avanzar a casilla {destination}"
                    options.append(discord.SelectOption(label=f"Ficha {index + 1}: {action}", value=str(index)))
        self.options = options or [discord.SelectOption(label="Sin movimientos", value="none")]
        self.disabled = not options
        self.placeholder = "Selecciona una ficha para mover" if options else "Lanza el dado para elegir una ficha"

    async def callback(self, interaction: discord.Interaction):
        view: ParchisView = self.view
        if interaction.user.id != view.current_player.id:
            await interaction.response.send_message("No es tu turno.", ephemeral=True)
            return
        if view.roll is None or self.values[0] == "none":
            await interaction.response.send_message("Lanza el dado primero.", ephemeral=True)
            return
        index = int(self.values[0])
        progress = view.pawns[view.current_index][index]
        if progress == -1:
            destination = 0
        else:
            destination = progress + view.roll
        view.pawns[view.current_index][index] = destination

        captured = False
        if destination < 68 and destination % 8 != 0:
            absolute_position = (destination + view.current_index * 34) % 68
            opponent_index = 1 - view.current_index
            for opponent_pawn, opponent_progress in enumerate(view.pawns[opponent_index]):
                if opponent_progress < 0 or opponent_progress >= 68:
                    continue
                opponent_position = (opponent_progress + opponent_index * 34) % 68
                if opponent_position == absolute_position:
                    view.pawns[opponent_index][opponent_pawn] = -1
                    captured = True
                    break

        rolled_six = view.roll == 6
        view.roll = None
        if all(progress == 68 for progress in view.pawns[view.current_index]):
            view.disable_all_items()
            await interaction.response.edit_message(
                content=f"{view.render()}\n\n🏆 ¡{interaction.user.mention} ganó la partida!", view=view
            )
            view.stop()
            return

        if not rolled_six and not captured:
            view.pass_turn()
        view.refresh_controls()
        result = " ¡Capturaste una ficha!" if captured else ""
        if rolled_six and not captured:
            result += " Sacaste seis: vuelves a tirar."
        await interaction.response.edit_message(content=f"{view.render()}\n\n{result}", view=view)


class ParchisView(discord.ui.View):
    def __init__(self, players):
        super().__init__(timeout=Config.PARCHIS_TURN_TIMEOUT_SECONDS * 20)
        self.players = players
        self.pawns = [[-1, -1, -1, -1] for _ in players]
        self.current_index = 0
        self.roll = None
        self.current_player = players[0]
        self.pawn_select = ParchisPawnSelect()
        self.add_item(ParchisRollButton())
        self.add_item(self.pawn_select)

    def pass_turn(self):
        self.current_index = (self.current_index + 1) % len(self.players)
        self.current_player = self.players[self.current_index]

    def refresh_controls(self):
        self.pawn_select.refresh(self)

    def render(self):
        lines = ["🎲 **Parchís Exprés**"]
        for player_index, player in enumerate(self.players):
            pieces = []
            for progress in self.pawns[player_index]:
                if progress == -1:
                    pieces.append("Casa")
                elif progress == 68:
                    pieces.append("Meta")
                else:
                    pieces.append(f"{progress}/68")
            lines.append(f"{player.mention}: " + " · ".join(pieces))
        lines.append(f"Turno: {self.current_player.mention}")
        if self.roll is not None:
            lines.append(f"Tirada: {self.roll}")
        return "\n".join(lines)

    async def on_timeout(self):
        self.disable_all_items()
        message = getattr(self, "message", None)
        if message:
            try:
                await message.edit(content=f"{self.render()}\n\n⏱️ Partida cancelada por inactividad.", view=self)
            except discord.HTTPException:
                pass


class ParchisCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="parchis", description="Juega una carrera de Parchís Exprés 1 contra 1.")
    @app_commands.describe(adversario="Usuario contra el que quieres jugar")
    async def parchis(self, interaction: discord.Interaction, adversario: discord.Member):
        if adversario.bot or adversario.id == interaction.user.id:
            await interaction.response.send_message("Elige a otra persona, no un bot ni a ti mismo.", ephemeral=True)
            return
        view = ParchisView([interaction.user, adversario])
        await interaction.response.send_message(view.render(), view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(ParchisCog(bot))