import discord
from discord import app_commands
from discord.ext import commands
import chess
import chess.svg
import io
import cairosvg  # Opcional si prefieres enviar el tablero renderizado como imagen PNG

# Almacén temporal de partidas activas en memoria
active_games = {}

class ChessCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    chess_group = app_commands.Group(name="chess", description="Juega al ajedrez en el servidor")

    @chess_group.command(name="start", description="Inicia una partida de ajedrez contra otro usuario.")
    @app_commands.describe(adversario="Usuario contra el que quieres jugar")
    async def chess_start(self, interaction: discord.Interaction, adversario: discord.Member):
        if adversario.bot or adversario.id == interaction.user.id:
            await interaction.response.send_message("❌ No puedes jugar contra ti mismo o contra un bot.", ephemeral=True)
            return

        game_id = f"{interaction.user.id}-{adversario.id}"
        if game_id in active_games or f"{adversario.id}-{interaction.user.id}" in active_games:
            await interaction.response.send_message("❌ Ya hay una partida activa entre vosotros.", ephemeral=True)
            return

        # Crear tablero de ajedrez
        board = chess.Board()
        active_games[game_id] = {
            "board": board,
            "white": interaction.user,
            "black": adversario,
            "turn": interaction.user.id
        }

        # Generar imagen del tablero
        board_image = self.render_board(board)
        file = discord.File(board_image, filename="chessboard.png")

        await interaction.response.send_message(
            f"♟️ **Partida de Ajedrez Iniciada**\n⚪ Blancas: {interaction.user.mention}\n⚫ Negras: {adversario.mention}\n\nEs el turno de blancas: {interaction.user.mention}. Usa `/chess move [movimiento]` (ej: `e2e4`).",
            file=file
        )

    @chess_group.command(name="move", description="Realiza un movimiento en tu partida actual (Notación UCI, ej: e2e4).")
    @app_commands.describe(movimiento="Casilla de origen y destino (ej: e2e4)")
    async def chess_move(self, interaction: discord.Interaction, movimiento: str):
        user_id = interaction.user.id
        current_game = None
        game_key = None

        # Buscar la partida del usuario
        for g_id, data in active_games.items():
            if data["white"].id == user_id or data["black"].id == user_id:
                current_game = data
                game_key = g_id
                break

        if not current_game:
            await interaction.response.send_message("❌ No estás participando en ninguna partida activa.", ephemeral=True)
            return

        if current_game["turn"] != user_id:
            await interaction.response.send_message("⏳ No es tu turno.", ephemeral=True)
            return

        board = current_game["board"]
        
        try:
            move = chess.Move.from_uci(movimiento.strip().lower())
        except ValueError:
            await interaction.response.send_message("❌ Formato de movimiento inválido. Usa notación UCI de 4 letras (ej: `e2e4`).", ephemeral=True)
            return

        if move not in board.legal_moves:
            await interaction.response.send_message("❌ ¡Movimiento ilegal! Comprueba las reglas del ajedrez.", ephemeral=True)
            return

        # Ejecutar movimiento
        board.push(move)

        # Comprobar estado de la partida
        if board.is_checkmate():
            winner = interaction.user
            del active_games[game_key]
            board_image = self.render_board(board)
            file = discord.File(board_image, filename="chessboard.png")
            await interaction.response.send_message(f"🏆 ¡Jaque mate! **{winner.mention} ha ganado la partida.**", file=file)
            return
        
        if board.is_stalemate() or board.is_insufficient_material():
            del active_games[game_key]
            board_image = self.render_board(board)
            file = discord.File(board_image, filename="chessboard.png")
            await interaction.response.send_message("🤝 **Tablas / Empate** por falta de material o ahogado.", file=file)
            return

        # Cambiar turno
        next_player = current_game["black"] if current_game["white"].id == user_id else current_game["white"]
        current_game["turn"] = next_player.id

        board_image = self.render_board(board)
        file = discord.File(board_image, filename="chessboard.png")

        turno_texto = f"Turno de ⚪ {current_game['white'].mention}" if current_game["turn"] == current_game["white"].id else f"Turno de ⚫ {current_game['black'].mention}"
        
        await interaction.response.send_message(
            f"✅ Movimiento realizado: `{movimiento}`\n{turno_texto}",
            file=file
        )

    @chess_group.command(name="surrender", description="Rinde la partida de ajedrez actual.")
    async def chess_surrender(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        for g_id, data in active_games.items():
            if data["white"].id == user_id or data["black"].id == user_id:
                winner = data["black"] if data["white"].id == user_id else data["white"]
                del active_games[g_id]
                await interaction.response.send_message(f"🏳️ {interaction.user.mention} se ha rendido. ¡Gana la partida {winner.mention}!")
                return

        await interaction.response.send_message("❌ No tienes ninguna partida activa.", ephemeral=True)

    def render_board(self, board: chess.Board):
        # Generar SVG con python-chess y convertirlo a PNG con cairosvg
        svg_data = chess.svg.board(board=board, size=400)
        png_data = cairosvg.svg2png(bytestring=svg_data.encode('utf-8'))
        return io.BytesIO(png_data)

async def setup(bot):
    await bot.add_cog(ChessCog(bot))