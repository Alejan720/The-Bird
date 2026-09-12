import discord
from discord import app_commands
from discord.ext import commands
from database import Database
from config import Config

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="‎", row=x)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view
        
        # Comprobar si es el turno del jugador correcto
        if interaction.user != view.current_player:
            await interaction.response.send_message("⏳ No es tu turno.", ephemeral=True)
            return

        if view.board[self.x][self.y] != 0:
            await interaction.response.send_message("❌ Esta casilla ya está ocupada.", ephemeral=True)
            return

        # Marcar la jugada (1 para jugador X, -1 para jugador O)
        current_val = 1 if view.current_player == view.player_x else -1
        view.board[self.x][self.y] = current_val
        
        if current_val == 1:
            self.style = discord.ButtonStyle.danger
            self.label = "X"
            self.disabled = True
        else:
            self.style = discord.ButtonStyle.primary
            self.label = "O"
            self.disabled = True

        winner = view.check_winner()
        if winner is not None:
            if winner == 1:
                content = f"🎉 ¡{view.player_x.mention} (X) ha ganado la partida!"
            elif winner == -1:
                content = f"🎉 ¡{view.player_o.mention} (O) ha ganado la partida!"
            else:
                content = "🤝 ¡Empate! Ninguno ha conseguido alinear tres."

            for child in view.children:
                child.disabled = True
            
            await interaction.response.edit_message(content=content, view=view)
            view.stop()
            return

        # Cambiar de turno
        view.current_player = view.player_o if view.current_player == view.player_x else view.player_x
        content = f"🎮 Turno de: {view.current_player.mention} (`{'X' if view.current_player == view.player_x else 'O'}`)"
        await interaction.response.edit_message(content=content, view=view)


class TicTacToeView(discord.ui.View):
    def __init__(self, player_x: discord.Member, player_o: discord.Member):
        super().__init__(timeout=Config.TICTACTOE_TURN_TIMEOUT_SECONDS)
        self.player_x = player_x
        self.player_o = player_o
        self.current_player = player_x
        self.board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]

        for x in range(3):
            for y in range(3):
                self.add_item(TicTacToeButton(x, y))

    def check_winner(self):
        # Comprobar filas y columnas
        for i in range(3):
            if abs(sum(self.board[i])) == 3:
                return self.board[i][0]
            if abs(sum(self.board[x][i] for x in range(3))) == 3:
                return self.board[0][i]

        # Diagonales
        if abs(self.board[0][0] + self.board[1][1] + self.board[2][2]) == 3:
            return self.board[1][1]
        if abs(self.board[0][2] + self.board[1][1] + self.board[2][0]) == 3:
            return self.board[1][1]

        # Empate si el tablero está lleno
        if all(self.board[x][y] != 0 for x in range(3) for y in range(3)):
            return 0

        return None

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            if self.message:
                await self.message.edit(content="⏱️ Partida cancelada por inactividad.", view=self)
        except Exception:
            pass


class TicTacToeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="tictactoe", description="Desafía a otro usuario a una partida de Tres en Raya.")
    @app_commands.describe(adversario="Usuario contra el que quieres jugar")
    async def tictactoe(self, interaction: discord.Interaction, adversario: discord.Member):
        if adversario.bot or adversario.id == interaction.user.id:
            await interaction.response.send_message("❌ No puedes jugar contra ti mismo o contra un bot.", ephemeral=True)
            return

        view = TicTacToeView(player_x=interaction.user, player_o=adversario)
        await interaction.response.send_message(
            f"🎮 **Tres en Raya**\nRetador (X): {interaction.user.mention}\nOponente (O): {adversario.mention}\n\nEs el turno de: {interaction.user.mention} (`X`)",
            view=view
        )
        view.message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(TicTacToeCog(bot))