import os
from pathlib import Path

# Đường dẫn thư mục gốc của project
BASE_DIR = Path(__file__).resolve().parent

def _load_env_file(env_path: Path):
    """Tự động đọc file .env (cố định và an toàn kể cả khi thiếu python-dotenv)"""
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_path)
        return
    except ImportError:
        pass

    if not env_path.exists():
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val

_load_env_file(BASE_DIR / ".env")


class Config:
    """Quản lý tập trung mọi cấu hình của Bot"""

    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # SQLite Database Path (File đơn siêu nhẹ trên VPS)
    DB_PATH: Path = DATA_DIR / "clan_bot.db"

    # Discord Bot Settings
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "!")
    OWNER_IDS: list[int] = [
        int(uid.strip())
        for uid in os.getenv("OWNER_IDS", "").split(",")
        if uid.strip().isdigit()
    ]

    # Cơ chế Sync lệnh: Mặc định bật trong lần đầu để đăng ký Slash Commands
    SYNC_ON_STARTUP: bool = os.getenv("SYNC_ON_STARTUP", "true").lower() in ("true", "1", "yes")

    # Múi giờ mặc định (Asia/Ho_Chi_Minh cho giờ Việt Nam)
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")

    # Thời gian chờ mặc định sau khi rời / bị trục xuất khỏi băng (giờ)
    DEFAULT_LEAVE_COOLDOWN_HOURS: int = int(os.getenv("DEFAULT_LEAVE_COOLDOWN_HOURS", "24"))

    # Mức độ log (DEBUG, INFO, WARNING, ERROR)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
