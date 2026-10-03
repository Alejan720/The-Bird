import discord
from discord import app_commands
from discord.ext import commands

from config import Config


class CheckersPieceSelect(discord.ui.Select):
    def __init__(self, view):
        self.game_view = view
        super().__init__(placeholder="Selecciona una ficha", min_values=1, max_values=1, options=[
            discord.SelectOption(label="Cargando fichas", value="none")
        ])
        self.refresh()

    def refresh(self):
        player = 1 if self.game_view.current_player == self.game_view.player_1 else -1
        options = []
        for row in range(8):
            for col in range(8):
                piece = self.game_view.board[row][col]
                if piece * player > 0 and self.game_view.legal_moves((row, col)):
                    symbol = "Roja" if piece > 0 else "Azul"
                    if abs(piece) == 2:
                        symbol += " coronada"
                    options.append(discord.SelectOption(
                        label=f"{symbol} ({row + 1},{col + 1})",
                        value=f"{row},{col}",
                    ))
        self.options = options or [discord.SelectOption(label="Sin movimientos disponibles", value="none")]
        self.disabled = not options

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.game_view.current_player.id:
            await interaction.response.send_message("No es tu turno.", ephemeral=True)
            return
        if self.values[0] == "none":
            await interaction.response.send_message("No hay fichas con movimientos válidos.", ephemeral=True)
            return
        self.game_view.selected_piece = tuple(map(int, self.values[0].split(",")))
        self.game_view.refresh_controls()
        await interaction.response.edit_message(content=self.game_view.render(), view=self.game_view)


class CheckersMoveSelect(discord.ui.Select):
    def __init__(self, view):
        self.game_view = view
        super().__init__(placeholder="Selecciona el destino", min_values=1, max_values=1, options=[
            discord.SelectOption(label="Primero selecciona una ficha", value="none")
        ], disabled=True)

    def refresh(self):
        piece = self.game_view.selected_piece
        moves = self.game_view.legal_moves(piece) if piece is not None else []
        self.options = [
            discord.SelectOption(
                label=f"({row + 1},{col + 1})" + (" Captura" if captured else ""),
                value=f"{row},{col}",
            )
            for row, col, captured in moves
        ] or [discord.SelectOption(label="Primero selecciona una ficha", value="none")]
        self.disabled = not moves

    async def callback(self, interaction: discord.Interaction):
        view = self.game_view
        if interaction.user.id != view.current_player.id:
            await interaction.response.send_message("No es tu turno.", ephemeral=True)
            return
        if view.selected_piece is None or self.values[0] == "none":
            await interaction.response.send_message("Selecciona primero una ficha.", ephemeral=True)
            return
        start_row, start_col = view.selected_piece
        row, col = map(int, self.values[0].split(","))
        move = next((item for item in view.legal_moves(view.selected_piece) if item[:2] == (row, col)), None)
        if move is None:
            await interaction.response.send_message("Ese movimiento ya no es válido.", ephemeral=True)
            return
        piece = view.board[start_row][start_col]
        view.board[start_row][start_col] = 0
        view.board[row][col] = piece
        if move[2]:
            view.board[(start_row + row) // 2][(start_col + col) // 2] = 0
        if row == 0 and piece == 1:
            view.board[row][col] = 2
        elif row == 7 and piece == -1:
            view.board[row][col] = -2

        view.selected_piece = None
        view.current_player = view.player_2 if view.current_player == view.player_1 else view.player_1
        winner = view.get_winner()
        if winner:
            view.disable_all_items()
            await interaction.response.edit_message(
                content=f"{view.render()}\n\n🏆 {winner.mention} gana la partida.", view=view
            )
            view.stop()
            return
        view.refresh_controls()
        await interaction.response.edit_message(content=view.render(), view=view)


class CheckersView(discord.ui.View):
    def __init__(self, player_1: discord.Member, player_2: discord.Member):
        super().__init__(timeout=Config.CHECKERS_TURN_TIMEOUT_SECONDS * 20)
        self.player_1 = player_1
        self.player_2 = player_2
        self.current_player = player_1
        self.selected_piece = None
        self.board = [[0] * 8 for _ in range(8)]
        for row in range(3):
            for col in range(8):
                if (row + col) % 2:
                    self.board[row][col] = -1
        for row in range(5, 8):
            for col in range(8):
                if (row + col) % 2:
                    self.board[row][col] = 1
        self.piece_select = CheckersPieceSelect(self)
        self.move_select = CheckersMoveSelect(self)
        self.add_item(self.piece_select)
        self.add_item(self.move_select)

    def legal_moves(self, position):
        if position is None:
            return []
        row, col = position
        piece = self.board[row][col]
        if not piece:
            return []
        directions = (-1, 1) if abs(piece) == 2 else ((-1,) if piece > 0 else (1,))
        moves = []
        for direction in directions:
            for delta_col in (-1, 1):
                next_row, next_col = row + direction, col + delta_col
                if not (0 <= next_row < 8 and 0 <= next_col < 8):
                    continue
                if self.board[next_row][next_col] == 0:
                    moves.append((next_row, next_col, False))
                elif self.board[next_row][next_col] * piece < 0:
                    end_row, end_col = row + 2 * direction, col + 2 * delta_col
                    if 0 <= end_row < 8 and 0 <= end_col < 8 and self.board[end_row][end_col] == 0:
                        moves.append((end_row, end_col, True))
        if any(move[2] for move in moves):
            return [move for move in moves if move[2]]
        return moves

    def refresh_controls(self):
        self.piece_select.refresh()
        self.move_select.refresh()

    def render(self):
        symbols = {0: "·", 1: "🔴", 2: "👑", -1: "🔵", -2: "👑"}
        rows = ["  1 2 3 4 5 6 7 8"]
        rows.extend(f"{row + 1} " + " ".join(symbols[cell] for cell in line) for row, line in enumerate(self.board))
        turn = "🔴" if self.current_player == self.player_1 else "🔵"
        return f"🎯 **Damas** | {self.player_1.mention} 🔴 vs {self.player_2.mention} 🔵\n```\n" + "\n".join(rows) + f"\n```\nTurno: {turn} {self.current_player.mention}"

    def get_winner(self):
        player = 1 if self.current_player == self.player_1 else -1
        opponent_pieces = [piece for row in self.board for piece in row if piece * player < 0]
        if not opponent_pieces:
            return self.current_player
        if not any(self.legal_moves((row, col)) for row in range(8) for col in range(8) if self.board[row][col] * player > 0):
            return self.player_2 if self.current_player == self.player_1 else self.player_1
        return None

    async def on_timeout(self):
        self.disable_all_items()
        message = getattr(self, "message", None)
        if message:
            try:
                await message.edit(content=f"{self.render()}\n\n⏱️ Partida cancelada por inactividad.", view=self)
            except discord.HTTPException:
                pass


class CheckersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="damas", description="Inicia una partida de damas 8x8.")
    async def damas(self, interaction: discord.Interaction, adversario: discord.Member):
        if adversario.bot or adversario.id == interaction.user.id:
            await interaction.response.send_message("Elige a otra persona, no un bot ni a ti mismo.", ephemeral=True)
            return
        view = CheckersView(interaction.user, adversario)
        await interaction.response.send_message(view.render(), view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(CheckersCog(bot))