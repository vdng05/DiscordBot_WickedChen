"""
Helper xử lý văn bản, chuyển đổi tiếng Việt có dấu sang không dấu chuẩn cho Discord
và quản lý các thông báo tự động dismiss (tự hủy) tránh làm đầy kênh chat.
"""

import asyncio
import re
import unicodedata
from typing import Optional, Any
import discord
from utils.logger import setup_logging

logger = setup_logging("TextHelper")


def to_channel_slug(text: str) -> str:
    """Chuyển đổi chuỗi tiếng Việt có dấu sang slug không dấu chuẩn cho kênh Discord.
    Ví dụ: 'Chó Điên' -> 'cho-dien', 'nhật-ký-băng' -> 'nhat-ky-bang'
    """
    if not text:
        return "clan"
    # Xử lý ký tự đ/Đ trước vì NFKD không phân tách đ thành d + dấu
    text = text.replace("đ", "d").replace("Đ", "d")
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", ascii_text).lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    cleaned = re.sub(r"-+", "-", slug).strip("-")
    return cleaned or "clan"


async def auto_dismiss_notice(interaction: discord.Interaction, content: Optional[str] = None,
                              embed: Optional[discord.Embed] = None, delay: int = 6):
    """Gửi thông báo tạm thời và tự động dismiss sau `delay` giây để tránh làm đầy chat."""
    try:
        if interaction.response.is_done():
            msg = await interaction.followup.send(content=content, embed=embed, ephemeral=True)
            if delay > 0 and msg:
                asyncio.create_task(_safe_delete_msg(msg, delay))
        else:
            await interaction.response.send_message(content=content, embed=embed, ephemeral=True)
            if delay > 0:
                asyncio.create_task(_safe_delete_interaction(interaction, delay))
    except Exception as e:
        logger.debug(f"Không thể gửi hoặc lên lịch dismiss notice: {e}")


async def _safe_delete_msg(msg: Any, delay: int):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


async def _safe_delete_interaction(interaction: discord.Interaction, delay: int):
    await asyncio.sleep(delay)
    try:
        await interaction.delete_original_response()
    except Exception:
        pass
