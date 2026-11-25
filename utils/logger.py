import logging
import sys
from pathlib import Path

# Đảm bảo mã hóa UTF-8 trên Windows console (tránh lỗi charmap cp1258)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class CleanFormatter(logging.Formatter):
    """Định dạng log tiêu chuẩn, sạch đẹp, không chứa mã ESC làm xấu terminal Windows/VSCode"""

    def format(self, record):
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        return f"[{timestamp}] [{record.levelname:<5}] [{record.name}] {record.getMessage()}"


def setup_logging(name: str = "ClanBot") -> logging.Logger:
    """Khởi tạo Logger tập trung cho toàn bộ bot"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(CleanFormatter())
        logger.addHandler(console_handler)

    return logger
