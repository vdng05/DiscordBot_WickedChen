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


async def get_available_clan_category(guild: discord.Guild, db: Any, config: Optional[dict] = None, needed_slots: int = 3) -> Optional[discord.CategoryChannel]:
    """Lấy Category cho băng; tự động tạo thêm Category nối tiếp nếu Category chính gần chạm trần 50 kênh của Discord."""
    max_safe = 50 - max(1, needed_slots)
    base_cat = guild.get_channel(int(config["clan_category_id"])) if (config and config.get("clan_category_id")) else None

    if not base_cat or not isinstance(base_cat, discord.CategoryChannel):
        for cat in guild.categories:
            if cat.name.startswith("🏰 BĂNG ĐẢNG") and len(cat.channels) <= max_safe:
                return cat
        try:
            base_cat = await guild.create_category("🏰 BĂNG ĐẢNG", reason="Tự phục hồi Category BĂNG ĐẢNG")
            if db and config is not None:
                await db.save_guild_config(
                    guild_id=guild.id,
                    category_id=base_cat.id,
                    log_channel_id=config.get("log_channel_id"),
                    allow_member_create=bool(config.get("allow_member_create", 1)),
                    required_role_id=config.get("required_role_id"),
                    cooldown_hours=int(config.get("leave_cooldown_hours", 0))
                )
            return base_cat
        except Exception:
            return None

    if len(base_cat.channels) <= max_safe:
        return base_cat

    # Category chính sắp đạt 50 kênh -> tìm hoặc tạo Category nối tiếp (không chỉnh sửa/xóa Category cũ)
    base_name = base_cat.name.strip()
    idx = 2
    while idx <= 10:
        cand_name = f"{base_name} {idx}"
        existing = discord.utils.get(guild.categories, name=cand_name)
        if existing:
            if len(existing.channels) <= max_safe:
                return existing
            idx += 1
            continue
        try:
            return await guild.create_category(cand_name, reason=f"Category chính đã có {len(base_cat.channels)} kênh (gần trần 50 kênh Discord)")
        except Exception:
            return base_cat
    return base_cat
