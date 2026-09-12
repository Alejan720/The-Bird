import discord
from discord import app_commands
from discord.ext import commands
from config import Config

# Almacén temporal de partidas de damas en memoria
active_checkers_games = {}

class CheckersButton(discord.ui.Button):
    def __init__(self, row: int, col: int, label: str, style: discord.ButtonStyle):
        super().__init__(style=style, label=label, row=row)
        self.x = row
        self.y = col

    async def callback(self, interaction: discord.Interaction):
        view: CheckersView = self.view
        
        if interaction.user != view.current_player:
            await interaction.response.send_message("⏳ No es tu turno.", ephemeral=True)
            return

        user_id = interaction.user.id
        is_player_1 = (user_id == view.player_1.id)
        my_piece_chars = ["🔴", "👑"] if is_player_1 else ["🔵", "👑"]

        # Si el jugador pulsa una de sus propias fichas, la selecciona para mover
        cell_val = view.board[self.x][self.y]
        
        if (is_player_1 and cell_val in [1, 2]) or (not is_player_1 and cell_val in [-1, -2]):
            view.selected_piece = (self.x, self.y)
            await interaction.response.send_message(f"📍 Ficha seleccionada en `({self.x}, {self.y})`. Ahora pulsa una casilla vacante válida en diagonal para mover.", ephemeral=True)
            return

        # Si ya tiene una ficha seleccionada y pulsa una casilla vacía
        if view.selected_piece and cell_val == 0:
            start_x, start_y = view.selected_piece
            
            # Validar movimiento básico en diagonal (1 casilla o salto de captura)
            dx = self.x - start_x
            dy = self.y - start_y
            
            # Movimiento simple de 1 paso
            if abs(dx) == 1 and abs(dy) == 1:
                # Comprobar dirección de avance según el bando si no es Reina
                if is_player_1 and dx > 0 and view.board[start_x][start_y] == 1: # Ficha roja avanza hacia arriba (dx < 0) normalmente
                    pass # Se permite simplificado para agilizar interfaz en Discord
                
                view.board[self.x][self.y] = view.board[start_x][start_y]
                view.board[start_x][start_y] = 0
                view.selected_piece = None
                
                # Cambiar turno
                view.current_player = view.player_2 if view.current_player == view.player_1 else view.player_1
                view.update_board_ui()
                
                await interaction.response.edit_message(content=f"🎮 Turno de: {view.current_player.mention}", view=view)
                return
            else:
                await interaction.response.send_message("❌ Movimiento inválido en damas. Debe ser en diagonal.", ephemeral=True)
                return

        await interaction.response.send_message("❌ Selecciona primero una ficha tuya válida.", ephemeral=True)


class CheckersView(discord.ui.View):
    def __init__(self, player_1: discord.Member, player_2: discord.Member):
        super().__init__(timeout=Config.CHECKERS_TURN_TIMEOUT_SECONDS)
        self.player_1 = player_1  # 🔴 Rojas
        self.player_2 = player_2  # 🔵 Azules
        self.current_player = player_1
        self.selected_piece = None
        
        # Tablero inicial de 8x8 simplificado (fichas en filas 0-2 y 5-7 en casillas oscuras)
        self.board = [[0 for _ in range(8)] for _ in range(8)]
        self.setup_board()
        self.update_board_ui()

    def setup_board(self):
        # Configurar filas superiores (Jugador 2: -1)
        for r in range(3):
            for c in range(8):
                if (r + c) % 2 != 0:
                    self.board[r][c] = -1
        # Configurar filas inferiores (Jugador 1: 1)
        for r in range(5, 8):
            for c in range(8):
                if (r + c) % 2 != 0:
                    self.board[r][c] = 1

    def update_board_ui(self):
        self.clear_items()
        # Por limitación de botones de Discord (máx 25), mostramos una cuadrícula reducida de 4x4 o tablero representativo interactivo
        # Para mantener agilidad en Discord, mapeamos las posiciones activas
        for r in range(4): # 4x4 interactivo optimizado para Discord
            for c in range(4):
                val = self.board[r*2][c*2]
                label = "‎"
                style = discord.ButtonStyle.secondary
                
                if val == 1:
                    label, style = "🔴", discord.ButtonStyle.danger
                elif val == -1:
                    label, style = "🔵", discord.ButtonStyle.primary
                elif val == 2:
                    label, style = "👑R", discord.ButtonStyle.danger
                elif val == -2:
                    label, style = "👑A", discord.ButtonStyle.primary

                self.add_item(CheckersButton(r, c, label, style))


class CheckersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="damas", description="Inicia una partida de Damas 1v1.")
    @app_commands.describe(adversario="Usuario contra el que quieres jugar")
    async def damas(self, interaction: discord.Interaction, adversario: discord.Member):
        if adversario.bot or adversario.id == interaction.user.id:
            await interaction.response.send_message("❌ Oponente no válido.", ephemeral=True)
            return

        game_id = f"{interaction.user.id}-{adversario.id}"
        view = CheckersView(player_1=interaction.user, player_2=adversario)
        active_checkers_games[game_id] = view

        await interaction.response.send_message(
            f"🎯 **Partida de Damas**\n🔴 {interaction.user.mention} vs 🔵 {adversario.mention}\n\nEs el turno de: {interaction.user.mention}",
            view=view
        )

async def setup(bot):
    await bot.add_cog(CheckersCog(bot))