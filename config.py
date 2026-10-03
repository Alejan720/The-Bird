import os

from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

DATABASE_PATH = os.getenv("DATABASE_PATH", "database.sqlite")
if not os.path.isabs(DATABASE_PATH):
    DATABASE_PATH = os.path.join(BASE_DIR, DATABASE_PATH)
LEGACY_ECONOMY_GUILD_ID = int(os.getenv("LEGACY_ECONOMY_GUILD_ID", "0"))


class Config:
    # Bot and application
    BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
    PREFIX = "/"

    # Files and storage
    DB_NAME = DATABASE_PATH
    ASSETS_PATH = os.path.join(BASE_DIR, "assets")
    BACKUP_PATH = os.getenv("BACKUP_PATH", os.path.join(BASE_DIR, "backups"))
    BACKUP_RETENTION_COUNT = 7
    BACKUP_INTERVAL_HOURS = 24

    # Server IDs and automatic role
    CHANNEL_WELCOME_ID = int(os.getenv("CHANNEL_WELCOME_ID", "0"))
    CHANNEL_LOGS_ID = int(os.getenv("CHANNEL_LOGS_ID", "0"))
    ROLE_DEFAULT_ID = int(os.getenv("ROLE_DEFAULT_ID", "0"))
    LEGACY_ECONOMY_GUILD_ID = int(os.getenv("LEGACY_ECONOMY_GUILD_ID", "0"))

    # Economy: currency and daily/work rewards
    MONEY_SYMBOL = "🪙"
    DAILY_REWARD_MIN = 100
    DAILY_REWARD_MAX = 250
    DAILY_COOLDOWN_HOURS = 24
    DAILY_STREAK_BONUS = 10
    DAILY_STREAK_BONUS_CAP = 100
    WORK_REWARD_MIN = 40
    WORK_REWARD_MAX = 120
    WORK_COOLDOWN_MINUTES = 60

    # Economy: shop item prices and effects
    SHIELD_PRICE = 500
    SHIELD_DURATION_HOURS = 12
    LOCKPICK_PRICE = 300
    LOTTERY_TICKET_PRICE = 150
    CAFE_PRICE = 180
    MYSTERY_CRATE_PRICE = 400
    DAILY_COUPON_PRICE = 350
    ROBBERY_INSURANCE_PRICE = 280
    CAFE_BOOST_PERCENT = 50

    # Economy: robbery rules
    ROB_COOLDOWN_MINUTES = 30
    ROB_SUCCESS_BASE_CHANCE = 45
    ROB_FINE_PERCENTAGE = 20

    # Economy: market rules
    MARKET_UPDATE_INTERVAL_MIN = 60
    MARKET_ORDER_MIN = 1
    MARKET_ORDER_MAX = 100
    MARKET_USER_HOLDING_MAX = 1000
    MARKET_BASE_CHANGE_MIN = -2.5
    MARKET_BASE_CHANGE_MAX = 2.5
    MARKET_FLOW_IMPACT_PERCENT = 3.0
    MARKET_MAX_CHANGE_PERCENT = 6.0

    # Economy: property rules
    PROPERTY_RENT_CAP_HOURS = 168

    # Levels and experience
    XP_PER_MESSAGE_MIN = 15
    XP_PER_MESSAGE_MAX = 25
    XP_COOLDOWN_SECONDS = 60
    LEVEL_UP_MULTIPLIER = 100

    # Questionnaires
    QUESTIONNAIRE_DEFAULT_TIME = 30
    QUESTIONNAIRE_MAX_OPTIONS = 5

    # General minigame betting limits
    BET_MIN_AMOUNT = 10
    BET_MAX_AMOUNT = 10000

    # Chess
    CHESS_TIME_BULLET = 1
    CHESS_TIME_BLITZ = 3
    CHESS_TIME_RAPID = 10
    CHESS_TURN_TIMEOUT_SECONDS = 60

    # Checkers
    CHECKERS_TURN_TIMEOUT_SECONDS = 60

    # Parchis
    PARCHIS_TURN_TIMEOUT_SECONDS = 45
    PARCHIS_BOT_FILL_ENABLED = True
    PARCHIS_CAPTURE_BONUS_STEPS = 20
    PARCHIS_GOAL_BONUS_STEPS = 10

    # Tic-tac-toe
    TICTACTOE_TURN_TIMEOUT_SECONDS = 45