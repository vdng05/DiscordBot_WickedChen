"""
Hệ thống Lửa Streak Trên Biệt Danh (Clan Streak Nickname).
Nguyên tắc tuyệt đối:
- Opt-in mặc định (thành viên tự bật trong Hồ Sơ Băng).
- Chỉ nối hậu tố ' 🔥 {streak}' vào sau tên gốc; tuyệt đối không cắt xén, không dùng Regex xóa mù.
- Exact-Suffix Match (last_applied_suffix) để gỡ/cập nhật chính xác, tôn trọng sửa đổi thủ công.
- Khôi phục nick=None nếu trước khi gắn lửa thành viên chưa từng đặt biệt danh server.
"""

import asyncio
from typing import Any, Dict, Optional, Set, Tuple
import discord

from utils.logger import setup_logging

logger = setup_logging("StreakNick")

DISCORD_NICK_MAX_LEN = 32
_BOT_EDIT_GUARD: Set[Tuple[int, int]] = set()


def is_bot_editing_nick(guild_id: int, user_id: int) -> bool:
    return (guild_id, user_id) in _BOT_EDIT_GUARD


def compute_base_nickname(
    current_nick: Optional[str],
    display_name: str,
    last_applied_suffix: Optional[str],
) -> Tuple[str, bool, bool]:
    """
    Tách tên gốc an toàn dựa trên Exact-Suffix Match.
    Trả về (base_name, matched_old_suffix, manual_edited).
    """
    if last_applied_suffix:
        if current_nick is not None and current_nick.endswith(last_applied_suffix):
            return current_nick[: -len(last_applied_suffix)], True, False
        base = current_nick if current_nick is not None else display_name
        return base, False, True
    base = current_nick if current_nick is not None else display_name
    return base, False, False


async def _safe_edit_nick(member: discord.Member, new_nick: Optional[str], reason: str) -> str:
    """Thực hiện member.edit(nick=...) kèm guard chống tự kích hoạt on_member_update."""
    if member.nick == new_nick:
        return "UNCHANGED"
    key = (member.guild.id, member.id)
    _BOT_EDIT_GUARD.add(key)
    try:
        await member.edit(nick=new_nick, reason=reason)
        return "OK"
    except discord.Forbidden:
        return "FORBIDDEN"
    except discord.HTTPException as exc:
        logger.warning(f"Lỗi HTTP khi đổi nick {member.id}: {exc}")
        return "ERROR"
    finally:
        # Giữ guard 1.5s để gateway event on_member_update kịp đi qua mà không bị self-trigger
        async def _release():
            await asyncio.sleep(1.5)
            _BOT_EDIT_GUARD.discard(key)

        try:
            asyncio.get_running_loop().create_task(_release())
        except RuntimeError:
            _BOT_EDIT_GUARD.discard(key)


async def _send_overflow_notice(db: Any, member: discord.Member, clan_id: int, base_len: int, suffix: str):
    """Gửi thông báo 1 lần khi tổng độ dài biệt danh vượt quá 32 ký tự."""
    total_len = base_len + len(suffix)
    excess = total_len - DISCORD_NICK_MAX_LEN
    msg = (
        f"🔥 **Thông báo Lửa Streak Băng Đảng**\n"
        f"Tên hiện tại của bạn đang dài **{base_len}** ký tự; khi gắn thêm `{suffix}` sẽ thành **{total_len}/{DISCORD_NICK_MAX_LEN}** ký tự.\n"
        f"👉 Bot giữ nguyên tên gốc của bạn. Nếu muốn hiện lửa, vui lòng tự rút ngắn biệt danh đi ít nhất **{excess} ký tự** "
        f"(bot sẽ tự động gắn lại ngay khi bạn đổi tên ngắn hơn!)."
    )
    try:
        await member.send(msg)
        return
    except Exception:
        pass
    try:
        clan = await db.get_clan_by_id(clan_id)
        if clan and clan.get("text_channel_id"):
            ch = member.guild.get_channel(int(clan["text_channel_id"]))
            if ch:
                await ch.send(f"{member.mention} {msg}")
    except Exception:
        pass


async def restore_original_nick(
    db: Any,
    member: discord.Member,
    disable_opt_in: bool = False,
    reason: str = "Gỡ hậu tố Lửa Streak Băng Đảng",
) -> Dict[str, Any]:
    """Chỉ gỡ đúng last_applied_suffix nếu cuối biệt danh vẫn khớp; khôi phục nick=None nếu chưa từng có nick."""
    state = await db.get_member_streak_nick_state(member.guild.id, member.id)
    if not state:
        return {"status": "NO_STATE"}

    last_suffix = state.get("last_applied_suffix")
    had_orig = int(state.get("had_original_nick", 1))
    status = "SKIPPED"

    if last_suffix and member.nick is not None and member.nick.endswith(last_suffix):
        target_nick = None if had_orig == 0 else member.nick[: -len(last_suffix)]
        edit_res = await _safe_edit_nick(member, target_nick, reason)
        status = "FORBIDDEN" if edit_res == "FORBIDDEN" else "RESTORED"

    updates: Dict[str, Any] = {
        "last_applied_suffix": None,
        "nick_warned_len": 0,
    }
    if disable_opt_in:
        updates["streak_nick_enabled"] = 0
    await db.set_member_streak_nick_state(member.guild.id, member.id, **updates)
    return {"status": status}


async def sync_member_streak_nick(
    db: Any,
    member: discord.Member,
    clan_id: int,
    clan_streak: int,
    notify_on_overflow: bool = True,
    enable_opt_in: bool = False,
) -> Dict[str, Any]:
    """Đồng bộ hậu tố ' 🔥 {clan_streak}' cho thành viên tuân thủ quy tắc bất khả xâm phạm tên gốc."""
    if clan_streak <= 0:
        if enable_opt_in:
            await db.set_member_streak_nick_state(member.guild.id, member.id, streak_nick_enabled=1)
        await restore_original_nick(db, member, disable_opt_in=False, reason="Streak băng về 0")
        return {"status": "ZERO_STREAK"}

    me = member.guild.me
    if not me.guild_permissions.manage_nicknames or member.id == member.guild.owner_id or member.top_role >= me.top_role:
        return {"status": "FORBIDDEN"}

    state = await db.get_member_streak_nick_state(member.guild.id, member.id)
    if not state:
        return {"status": "NO_MEMBER"}

    last_suffix = state.get("last_applied_suffix")
    had_orig = int(state.get("had_original_nick", 1))
    prev_warned = int(state.get("nick_warned_len") or 0)

    base_name, matched_old, manual_edited = compute_base_nickname(
        member.nick, member.display_name, last_suffix
    )
    if manual_edited:
        had_orig = 1 if member.nick is not None else 0
        last_suffix = None
    elif not last_suffix:
        had_orig = 1 if member.nick is not None else 0

    suffix = f" 🔥 {clan_streak}"
    total_len = len(base_name) + len(suffix)

    if total_len > DISCORD_NICK_MAX_LEN:
        # Nếu trước đó đang gắn lửa cũ mà nay tăng chữ số làm tràn > 32: gỡ sạch đuôi cũ để trả về tên gốc
        if matched_old and last_suffix:
            target_clean = None if had_orig == 0 else base_name
            await _safe_edit_nick(member, target_clean, "Gỡ lửa streak cũ vì tên mới + số mới vượt 32 ký tự")

        await db.set_member_streak_nick_state(
            member.guild.id,
            member.id,
            last_applied_suffix=None,
            had_original_nick=had_orig,
            nick_warned_len=len(base_name),
        )
        if notify_on_overflow and prev_warned == 0:
            await _send_overflow_notice(db, member, clan_id, len(base_name), suffix)
        return {
            "status": "TOO_LONG",
            "base_len": len(base_name),
            "total_len": total_len,
            "excess": total_len - DISCORD_NICK_MAX_LEN,
            "suffix": suffix,
        }

    target_nick = f"{base_name}{suffix}"
    edit_res = await _safe_edit_nick(member, target_nick, f"Cập nhật Lửa Streak Băng (🔥 {clan_streak})")
    if edit_res == "FORBIDDEN":
        return {"status": "FORBIDDEN"}

    updates: Dict[str, Any] = {
        "last_applied_suffix": suffix,
        "had_original_nick": had_orig,
        "nick_warned_len": 0,
    }
    if enable_opt_in:
        updates["streak_nick_enabled"] = 1
    await db.set_member_streak_nick_state(member.guild.id, member.id, **updates)
    return {"status": "UPDATED", "nick": target_nick, "suffix": suffix}


async def sync_clan_streak_queue(bot: Any, clan_id: int):
    """Cập nhật tuần tự biệt danh các thành viên đang bật Streak Nick để tránh Rate Limit Discord."""
    clan = await bot.db.get_clan_by_id(clan_id)
    if not clan:
        return
    guild = bot.get_guild(int(clan["guild_id"]))
    if not guild:
        return
    clan_streak = int(clan.get("clan_streak") or 0)
    rows = await bot.db.get_clan_streak_nick_members(clan_id)
    for row in rows:
        member = guild.get_member(int(row["user_id"]))
        if not member:
            continue
        if int(row.get("streak_nick_enabled") or 0) == 1 and clan_streak > 0:
            await sync_member_streak_nick(bot.db, member, clan_id, clan_streak, notify_on_overflow=True)
        elif row.get("last_applied_suffix"):
            await restore_original_nick(bot.db, member, disable_opt_in=False, reason="Đồng bộ tắt/reset lửa streak băng")
        await asyncio.sleep(1.2)
