import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ==========================================
    # 1. GENERAL CONFIGURATION
    # ==========================================
    BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
    PREFIX = "/"
    
    # ==========================================
    # 2. DATABASE & PATHS
    # ==========================================
    DB_NAME = "database.sqlite"
    ASSETS_PATH = "assets/"

    # ==========================================
    # 3. ECONOMY & MARKET SYSTEM
    # ==========================================
    MONEY_SYMBOL = "🪙"
    
    # /diario command
    DAILY_REWARD_MIN = 100
    DAILY_REWARD_MAX = 250
    DAILY_COOLDOWN_HOURS = 24

    # Shop & Competitive Items
    SHIELD_PRICE = 500
    SHIELD_DURATION_HOURS = 12
    LOCKPICK_PRICE = 300
    LOTTERY_TICKET_PRICE = 150

    # Robbery System (/robar)
    ROB_COOLDOWN_MINUTES = 30
    ROB_SUCCESS_BASE_CHANCE = 45
    ROB_FINE_PERCENTAGE = 20

    # Dynamic Market / Stock Exchange
    MARKET_UPDATE_INTERVAL_MIN = 60

    # ==========================================
    # 4. LEVELS & EXPERIENCE SYSTEM
    # ==========================================
    XP_PER_MESSAGE_MIN = 15
    XP_PER_MESSAGE_MAX = 25
    XP_COOLDOWN_SECONDS = 60
    LEVEL_UP_MULTIPLIER = 100  # Formula: (Nivel * LEVEL_UP_MULTIPLIER)

    # ==========================================
    # 5. CHANNELS, ROLES & SERVER UTILITIES
    # ==========================================
    CHANNEL_WELCOME_ID = 000000000000000000  # Canal para tarjetas de bienvenida/despedida
    CHANNEL_LOGS_ID = 000000000000000000     # Canal de auditoría y registros (logs)
    ROLE_DEFAULT_ID = 000000000000000000     # Rol automático al entrar

    # ==========================================
    # 6. QUESTIONNAIRES & MODALS
    # ==========================================
    QUESTIONNAIRE_DEFAULT_TIME = 30          # Tiempo por defecto en segundos para cuestionarios
    QUESTIONNAIRE_MAX_OPTIONS = 5            # Límite máximo de opciones con botones por encuesta

    # ==========================================
    # 7. MINIGAMES CONFIGURATION
    # ==========================================
    # General Bet Limits (Coinflip, TicTacToe, etc.)
    BET_MIN_AMOUNT = 10
    BET_MAX_AMOUNT = 10000

    # Chess (Times in minutes)
    CHESS_TIME_BULLET = 1
    CHESS_TIME_BLITZ = 3
    CHESS_TIME_RAPID = 10
    CHESS_TURN_TIMEOUT_SECONDS = 60

    # Checkers
    CHECKERS_TURN_TIMEOUT_SECONDS = 60

    # Parchis
    PARCHIS_TURN_TIMEOUT_SECONDS = 45
    PARCHIS_BOT_FILL_ENABLED = True
    PARCHIS_CAPTURE_BONUS_STEPS = 20  # Casillas extra al comer una ficha
    PARCHIS_GOAL_BONUS_STEPS = 10     # Casillas extra al meter una ficha a meta

    # Tic-Tac-Toe
    TICTACTOE_TURN_TIMEOUT_SECONDS = 45