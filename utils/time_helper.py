"""
Helper xử lý ngày giờ, múi giờ Việt Nam (Asia/Ho_Chi_Minh) & chu kỳ tuần ISO
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re
from typing import Optional

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

def get_vietnam_now() -> datetime:
    """Lấy thời điểm hiện tại theo múi giờ Việt Nam"""
    return datetime.now(VN_TZ)

def get_today_vn_string() -> str:
    """Trả về ngày hôm nay định dạng YYYY-MM-DD (giờ VN)"""
    return get_vietnam_now().strftime("%Y-%m-%d")

def get_yesterday_vn_string() -> str:
    """Trả về ngày hôm qua định dạng YYYY-MM-DD (giờ VN)"""
    yesterday = get_vietnam_now() - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")

def get_current_week_key() -> str:
    """Trả về mã tuần ISO hiện tại, ví dụ: '2026-W48'"""
    vn_now = get_vietnam_now()
    year, week, _ = vn_now.isocalendar()
    return f"{year}-W{week:02d}"

def parse_scheduled_time(time_input: Optional[str]) -> Optional[int]:
    """
    Phân tích chuỗi nhập thời gian thành Discord epoch timestamp (seconds)
    Hỗ trợ các dạng: '21:00', '20h30', '9:30', hoặc unix timestamp số
    """
    if not time_input:
        return None

    cleaned = time_input.strip().lower()

    # Kiểm tra nếu là epoch timestamp thuần túy
    if cleaned.isdigit():
        val = int(cleaned)
        return val // 1000 if val > 10_000_000_000 else val

    now_vn = get_vietnam_now()
    match = re.match(r"^(\d{1,2})[:h](\d{2})?$", cleaned)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2)) if match.group(2) else 0

        if 0 <= hours < 24 and 0 <= minutes < 60:
            scheduled_vn = now_vn.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            if scheduled_vn <= now_vn:
                # Nếu giờ đã qua trong ngày, dời sang ngày mai
                scheduled_vn += timedelta(days=1)
            return int(scheduled_vn.timestamp())

    return None
