"""
Discord UI Components: Views, Buttons, Select Menus và Modals
"""

import discord
from discord import ui
from datetime import datetime
import asyncio
import re
import time
import aiosqlite
from typing import Optional, Dict, Any, List, Tuple
from utils.constants import (
    Ranks,
    JoinModes,
    Cooldowns,
    EXP_REWARDS,
    RANK_WEIGHTS,
    RANK_NAMES,
    RANK_LIMITS,
    DailyQuestTypes,
    PET_SPECIES,
    PET_STAGES,
    PET_SLOT_NAMES,
    PET_STYLE_NAMES,
    PET_CATALOG,
    PET_CATALOG_MAP,
    PET_DAILY_EXP_CAP,
    PET_ACTION_COOLDOWNS,
    get_pet_level_info,
)
from utils.embeds import (
    build_clan_info_embed,
    build_clan_list_embed,
    build_leaderboard_embed,
    build_members_embed,
    build_logs_embed,
    build_party_embed,
    build_challenge_embed,
    build_role_setup_embed,
    build_image_settings_embed,
    build_bot_access_embed,
    get_level_info,
    parse_hex_color,
    send_dm_notification
)
from utils.logger import setup_logging
from utils.time_helper import get_current_week_key, get_today_vn_string, get_yesterday_vn_string
from utils.text_helper import (
    to_channel_slug,
    auto_dismiss_notice,
    get_available_clan_category,
    get_or_create_recruit_channel
)
from utils.image_storage import (
    save_clan_attachment,
    delete_local_asset,
    resolve_clan_logo,
    resolve_clan_banner
)

logger = setup_logging("UIComponents")

_WALLPAPER_COOLDOWNS: Dict[int, float] = {}
WALLPAPER_COOLDOWN_SECONDS = 45
GLOBAL_CHALLENGE_COOLDOWN_SECONDS = 12 * 3600

DANGEROUS_ROLE_PERMS = (
    "administrator",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "kick_members",
    "ban_members",
    "moderate_members",
    "mention_everyone",
    "manage_webhooks",
    "manage_messages",
    "manage_threads",
)


def validate_linkable_role(
    guild: discord.Guild,
    actor: discord.Member,
    role: discord.Role,
    current_clan: Dict[str, Any],
    all_clans: List[Dict[str, Any]],
    clan_members: List[Dict[str, Any]],
) -> Optional[str]:
    """Kiểm tra an toàn chống leo thang đặc quyền trước khi liên kết Role có sẵn làm Role Băng."""
    if role.is_default():
        return "❌ Không thể chọn Role `@everyone` làm Role Băng!"
    if role.managed:
        return "❌ Không thể chọn Role tích hợp / tự động của Bot khác!"
    if role >= guild.me.top_role:
        return (
            f"⚠️ Role {role.mention} đang nằm **cao hơn hoặc bằng** vị trí Role của Bot trong máy chủ!\n"
            "Vui lòng vào **Server Settings -> Roles** kéo Role của Bot lên cao hơn."
        )

    # Không cho chiếm Role đang gắn với băng đảng khác
    for other in all_clans:
        if other.get("clan_id") != current_clan.get("clan_id") and str(other.get("role_id") or "") == str(role.id):
            return f"❌ Role {role.mention} hiện đang thuộc về băng **[{other['tag']}] {other['name']}**!"

    # Chặn các Role mang quyền quản trị / điều hành nhạy cảm để chống leo thang đặc quyền
    elevated = [perm for perm in DANGEROUS_ROLE_PERMS if getattr(role.permissions, perm, False)]
    if elevated:
        return (
            f"🛡️ **Từ chối liên kết Role {role.mention} vì lý do bảo mật!**\n"
            f"Role này đang sở hữu quyền nhạy cảm (`{', '.join(elevated[:4])}`), không thể dùng làm Role Băng để tránh leo thang đặc quyền."
        )

    # Nếu không phải Admin server, chặn chọn Role đã có người ngoài băng sở hữu
    if not actor.guild_permissions.administrator:
        clan_member_ids = {str(m["user_id"]) for m in clan_members}
        non_clan_holders = [mem for mem in role.members if not mem.bot and str(mem.id) not in clan_member_ids]
        if non_clan_holders:
            return (
                f"🛡️ **Không thể liên kết Role {role.mention}!**\n"
                f"Hiện đang có **{len(non_clan_holders)}** thành viên ngoài băng sở hữu Role này (ví dụ Role VIP/Booster/Event).\n"
                "Chỉ **Quản Trị Viên Server** mới có quyền gắn Role đang được người ngoài sở hữu."
            )
    return None


async def link_role_to_clan(
    guild: discord.Guild,
    clan: Dict[str, Any],
    new_role: discord.Role,
    actor: discord.Member,
    db: Any,
) -> str:
    """Chuyển quyền các kênh của băng sang Role mới, cấp Role cho thành viên và lưu DB."""
    old_role_id = clan.get("role_id")
    old_role = guild.get_role(int(old_role_id)) if old_role_id else None

    for ch_key in ("text_channel_id", "log_channel_id", "voice_channel_id", "extra_voice_channel_id"):
        ch_id = clan.get(ch_key)
        if not ch_id:
            continue
        ch = guild.get_channel(int(ch_id))
        if not ch:
            continue
        try:
            if old_role and old_role.id != new_role.id:
                await ch.set_permissions(old_role, overwrite=None, reason="Đổi role clan")
            if ch_key == "log_channel_id":
                await ch.set_permissions(
                    new_role,
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True,
                    reason="Gán role mới cho kênh nhật ký clan",
                )
            elif ch_key in ("voice_channel_id", "extra_voice_channel_id"):
                await ch.set_permissions(
                    new_role,
                    view_channel=True,
                    connect=True,
                    speak=True,
                    use_voice_activation=True,
                    reason="Gán role mới cho kênh voice clan",
                )
            else:
                await ch.set_permissions(
                    new_role,
                    view_channel=True,
                    send_messages=True,
                    embed_links=True,
                    attach_files=True,
                    read_message_history=True,
                    reason="Gán role mới cho kênh chat clan",
                )
        except Exception as ch_err:
            logger.warning(f"Lỗi cập nhật quyền kênh {ch_key}: {ch_err}")

    members = await db.get_clan_members(clan["clan_id"])
    for m in members:
        try:
            target_mem = guild.get_member(int(m["user_id"])) or await guild.fetch_member(int(m["user_id"]))
            if target_mem and new_role not in target_mem.roles:
                await target_mem.add_roles(new_role, reason="Gán role mới cho clan")
        except Exception:
            pass

    hex_color = f"#{new_role.color.value:06X}" if new_role.color.value else "#5865F2"
    await db.update_clan(clan["clan_id"], role_id=str(new_role.id), color_hex=hex_color, secondary_color_hex=None)
    await db.add_clan_log(
        clan_id=clan["clan_id"],
        actor_id=actor.id,
        action="LINK_ROLE",
        details=f"Liên kết role mới {new_role.name} ({new_role.id})."
    )
    return hex_color


async def perform_daily_checkin(db: Any, guild_id: int, user_id: int, expected_clan_id: Optional[int] = None) -> Dict[str, Any]:
    """Xử lý điểm danh hằng ngày thống nhất, chống farm qua nhiều băng trong cùng 1 ngày."""
    clan = await db.get_clan_by_member(guild_id, user_id)
    if not clan:
        return {"ok": False, "error": "❌ Bạn chưa tham gia bất kỳ băng đảng nào!"}
    if expected_clan_id is not None and clan["clan_id"] != expected_clan_id:
        return {"ok": False, "error": "❌ Bạn không thuộc băng này!"}

    today = get_today_vn_string()
    yesterday = get_yesterday_vn_string()
    status = await db.get_user_checkin_status(guild_id, user_id)
    last_date = status.get("last_checkin_date") or clan.get("last_checkin_date")
    if last_date == today:
        return {"ok": False, "error": "ℹ️ Hôm nay bạn đã điểm danh rồi! Hãy quay lại sau 00:00 (giờ Việt Nam)."}

    prev_streak = status.get("checkin_streak") or clan.get("checkin_streak") or 0
    new_streak = (prev_streak + 1) if last_date == yesterday else 1

    clan_exp_to_add = EXP_REWARDS.CHECKIN_EXP
    is_streak_7 = (new_streak % 7 == 0)
    if is_streak_7:
        clan_exp_to_add += EXP_REWARDS.CHECKIN_STREAK_7_BONUS_EXP

    # Buff thụ động từ Linh Thú Băng (nếu không bị đói/buồn về 0)
    pet = await db.get_clan_pet(clan["clan_id"])
    pet_bonus_exp = 0
    if pet and int(pet.get("hunger", 0)) > 0 and int(pet.get("mood", 0)) > 0:
        pet_info = get_pet_level_info(int(pet.get("exp", 0)))
        bonus_pct = pet_info.get("checkin_bonus_pct", 0)
        if bonus_pct > 0:
            pet_bonus_exp = max(1, int(round(clan_exp_to_add * bonus_pct / 100)))
            clan_exp_to_add += pet_bonus_exp

    updated = await db.update_checkin(guild_id, user_id, today, new_streak)
    if updated == 0:
        return {"ok": False, "error": "ℹ️ Hôm nay bạn đã điểm danh rồi! Hãy quay lại sau 00:00 (giờ Việt Nam)."}

    await db.add_clan_exp(clan["clan_id"], clan_exp_to_add, clan_exp_to_add)
    if pet:
        await db.add_pet_coins(clan["clan_id"], 15)

    week_key = get_current_week_key()
    quest_res = await db.increment_quest_progress(clan["clan_id"], week_key, "CHECKIN_COUNT", 1)
    if quest_res["completed_now"]:
        await db.add_clan_exp(clan["clan_id"], quest_res["reward_exp"], quest_res["reward_exp"])
        if pet:
            await db.add_pet_coins(clan["clan_id"], 100)

    daily_res = await db.increment_daily_quest_progress(clan["clan_id"], today, DailyQuestTypes.DAILY_CHECKIN, 1)
    if daily_res["completed_now"]:
        await db.add_clan_exp(clan["clan_id"], daily_res["reward_exp"], daily_res["reward_exp"])
        if pet:
            await db.add_pet_coins(clan["clan_id"], daily_res["reward_coins"])

    clan_streak_res = await db.record_clan_daily_checkin_streak(clan["clan_id"], today, yesterday, min_members=2)

    return {
        "ok": True,
        "clan": clan,
        "new_streak": new_streak,
        "is_streak_7": is_streak_7,
        "pet_bonus_exp": pet_bonus_exp,
        "clan_exp_to_add": clan_exp_to_add,
        "contribution": EXP_REWARDS.CHECKIN_CONTRIBUTION,
        "clan_streak_updated": clan_streak_res["streak_updated"],
        "clan_streak": clan_streak_res["clan_streak"],
    }


class SafeView(ui.View):
    """Base View tự động kiểm tra quyền dùng bot và bắt mọi lỗi ngoại lệ để không bao giờ bị treo."""
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if hasattr(interaction.client, "check_user_bot_access"):
            return await interaction.client.check_user_bot_access(interaction)
        return True

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item) -> None:
        logger.error(f"Lỗi tương tác trên {self.__class__.__name__} ({item}): {error}", exc_info=True)
        await auto_dismiss_notice(
            interaction,
            content="❌ Đã xảy ra lỗi khi xử lý thao tác này! Vui lòng mở lại `/clan hub` hoặc thử lại sau.",
            delay=6
        )


class SafeModal(ui.Modal):
    """Base Modal tự động bắt mọi lỗi ngoại lệ khi người dùng bấm Gửi."""
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Lỗi Modal {self.__class__.__name__}: {error}", exc_info=True)
        await auto_dismiss_notice(
            interaction,
            content="❌ Đã xảy ra lỗi khi xử lý biểu mẫu này! Vui lòng kiểm tra lại thông tin và thử lại.",
            delay=6
        )


# =============================================================================
# MODALS
# =============================================================================

class CreateClanModal(SafeModal, title="🏰 Thành Lập Băng Đảng Mới"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    clan_name = ui.TextInput(
        label="Tên Băng Đảng (3 - 25 ký tự)",
        placeholder="Ví dụ: Hoàng Gia, Xích Long, Thiên Thần...",
        min_length=3,
        max_length=25,
        required=True
    )

    clan_tag = ui.TextInput(
        label="Tag Băng Viết Tắt (2 - 5 ký tự viết hoa)",
        placeholder="Ví dụ: HG, XL, VIP, TLU...",
        min_length=2,
        max_length=5,
        required=True
    )

    clan_slogan = ui.TextInput(
        label="Khẩu Hiệu Băng (Tối đa 100 ký tự)",
        placeholder="Phương châm hoạt động, mục tiêu gắn kết...",
        style=discord.TextStyle.paragraph,
        max_length=100,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild = interaction.guild
        user = interaction.user
        name = self.clan_name.value.strip()
        tag = self.clan_tag.value.strip().upper()
        slogan = self.clan_slogan.value.strip() or "Chưa có khẩu hiệu."

        if not re.match(r"^[A-Z0-9]+$", tag):
            await interaction.followup.send("❌ Tag băng chỉ được chứa chữ cái in hoa hoặc số (ví dụ: TLU, NRO)!", ephemeral=True)
            return

        config = await self.bot.db.get_guild_config(guild.id)
        is_admin = interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild

        # TỰ ĐỘNG KHỞI TẠO ĐỘNG: Nếu server chưa setup, Admin tạo băng thì bot tự tạo duy nhất 1 Category BĂNG ĐẢNG
        if not config:
            if is_admin:
                try:
                    category = await guild.create_category("🏰 BĂNG ĐẢNG", reason="Tự động khởi tạo hệ thống Băng Đảng")
                    await self.bot.db.save_guild_config(
                        guild_id=guild.id,
                        category_id=category.id,
                        log_channel_id=None,
                        allow_member_create=True,
                        required_role_id=None,
                        cooldown_hours=24
                    )
                    config = await self.bot.db.get_guild_config(guild.id)
                    logger.info(f"Đã tự động khởi tạo Category BĂNG ĐẢNG cho server {guild.name} ({guild.id})")
                except Exception as auto_err:
                    await interaction.followup.send(f"❌ Không thể tự động tạo Category: `{auto_err}`. Vui lòng kiểm tra quyền của Bot!", ephemeral=True)
                    return
            else:
                await interaction.followup.send("❌ Server chưa được thiết lập hệ thống Băng! Admin vui lòng gõ `/clan-admin setup` hoặc tự lập băng đầu tiên để bot tự động thiết lập.", ephemeral=True)
                return

        # Kiểm tra điều kiện tạo
        if not config["allow_member_create"] and not is_admin:
            await interaction.followup.send("❌ Server hiện tại chỉ cho phép Quản Trị Viên (Admin) thành lập băng!", ephemeral=True)
            return

        if config.get("required_role_id") and not is_admin:
            req_role = guild.get_role(int(config["required_role_id"]))
            if req_role and req_role not in user.roles:
                await interaction.followup.send(f"❌ Bạn cần sở hữu Role {req_role.mention} mới có thể lập băng!", ephemeral=True)
                return

        # Kiểm tra người dùng đã có băng chưa
        existing = await self.bot.db.get_clan_by_member(guild.id, user.id)
        if existing:
            await interaction.followup.send(f"❌ Bạn đã tham gia băng **{existing['name']}** rồi! Mỗi người chỉ được ở trong 1 băng.", ephemeral=True)
            return

        # Kiểm tra trùng tên / tag
        if await self.bot.db.get_clan_by_name(guild.id, name):
            await interaction.followup.send(f"❌ Tên băng **{name}** đã được sử dụng trong server!", ephemeral=True)
            return
        if await self.bot.db.get_clan_by_tag(guild.id, tag):
            await interaction.followup.send(f"❌ Tag băng **{tag}** đã được sử dụng trong server!", ephemeral=True)
            return

        # Kiểm tra trần giới hạn tài nguyên của Discord Server (250 roles & 500 channels)
        if len(guild.roles) >= 245:
            await interaction.followup.send(
                "❌ **Máy chủ Discord sắp đạt giới hạn trần 250 Roles của Discord!**\n"
                "👉 Quản trị viên vui lòng dọn dẹp các role không dùng để có thể tạo thêm băng.",
                ephemeral=True
            )
            return

        if len(guild.channels) >= 490:
            await interaction.followup.send(
                "❌ **Máy chủ Discord sắp đạt giới hạn trần 500 Kênh của Discord!**\n"
                "👉 Quản trị viên vui lòng dọn dẹp các kênh không dùng để có thể tạo thêm băng.",
                ephemeral=True
            )
            return

        # Kiểm tra quyền bot
        me = guild.me
        if not me.guild_permissions.manage_roles or not me.guild_permissions.manage_channels:
            await interaction.followup.send("❌ Bot thiếu quyền `Manage Roles` hoặc `Manage Channels` để tạo băng!", ephemeral=True)
            return

        try:
            # 1. Tạo Discord Role
            role_name = f"[{tag}] {name}"
            clan_role = await guild.create_role(
                name=role_name,
                color=discord.Color.from_str("#5865F2"),
                hoist=True,
                mentionable=True,
                reason=f"Tạo băng mới bởi {user.name}"
            )

            # 2. Lấy Category an toàn (tự mở rộng Category nối tiếp nếu gần chạm trần 50 kênh Discord)
            category = await get_available_clan_category(guild, self.bot.db, config, needed_slots=3)

            from utils.text_helper import to_channel_slug
            clean_channel_slug = to_channel_slug(name)[:30]
            text_channel_name = f"💬・{clean_channel_slug}"
            log_channel_name = f"📜・nhat-ky-{clean_channel_slug}"[:35]
            voice_channel_name = f"🔊・[{tag}] Phòng Sinh Hoạt"

            # Kênh chat của băng: chỉ thành viên băng mới nhìn thấy & nhắn tin
            text_overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False, send_messages=False),
                clan_role: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, embed_links=True, attach_files=True,
                    read_message_history=True
                ),
                me: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, manage_messages=True, manage_channels=True,
                    manage_roles=True, read_message_history=True
                )
            }

            # Kênh nhật ký của băng: chỉ thành viên băng mới nhìn thấy (chỉ đọc, bot ghi log)
            log_overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False, send_messages=False),
                clan_role: discord.PermissionOverwrite(
                    view_channel=True, send_messages=False, read_message_history=True
                ),
                me: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, embed_links=True, attach_files=True,
                    read_message_history=True, manage_channels=True
                )
            }

            # Kênh voice của băng: PUBLIC cho toàn thể thành viên server
            voice_overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, use_voice_activation=True),
                clan_role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, use_voice_activation=True),
                me: discord.PermissionOverwrite(view_channel=True, connect=True, move_members=True, manage_channels=True)
            }

            text_channel = await guild.create_text_channel(
                name=text_channel_name,
                category=category,
                topic=f"Kênh sinh hoạt chính thức của Băng [{tag}] {name} | Khẩu hiệu: {slogan}",
                overwrites=text_overwrites
            )

            log_channel = await guild.create_text_channel(
                name=log_channel_name,
                category=category,
                topic=f"Nhật ký hoạt động nội bộ của Băng [{tag}] {name}",
                overwrites=log_overwrites
            )

            voice_channel = await guild.create_voice_channel(
                name=voice_channel_name,
                category=category,
                overwrites=voice_overwrites
            )

            # 3. Gán Role cho người tạo
            await user.add_roles(clan_role, reason="Chủ Băng thành lập")

            # 4. Lưu vào Database
            clan_id = await self.bot.db.create_clan(
                guild_id=guild.id,
                name=name,
                tag=tag,
                description=slogan,
                role_id=clan_role.id,
                text_channel_id=text_channel.id,
                voice_channel_id=voice_channel.id,
                leader_id=user.id,
                color_hex="#5865F2",
                log_channel_id=log_channel.id
            )

            await self.bot.db.add_member(
                guild_id=guild.id,
                user_id=user.id,
                clan_id=clan_id,
                rank=Ranks.LEADER
            )

            await self.bot.db.add_clan_log(
                clan_id=clan_id,
                actor_id=user.id,
                action="CREATE_CLAN",
                details=f"Băng [{tag}] {name} được thành lập bởi Chủ Băng <@{user.id}>."
            )

            # Ghi nhận Cột mốc lịch sử thành lập băng
            await self.bot.db.add_milestone(
                clan_id=clan_id,
                title="🏰 Khai Sinh Băng Đảng",
                description=f"Băng [{tag}] {name} chính thức được thành lập bởi Chủ Băng {user.name}."
            )

            # 5. Gửi Embed Chào Mừng trong kênh chat riêng
            welcome_embed = discord.Embed(
                title=f"🏰 CHÀO MỪNG ĐẾN VỚI BĂNG [{tag}] {name}!",
                description=f"Chúc mừng **{user.display_name}** đã thành lập băng thành công! Đây là không gian riêng tư dành riêng cho các thành viên của băng.",
                color=clan_role.color,
                timestamp=datetime.now()
            )
            welcome_embed.add_field(name="👑 Chủ Băng", value=f"<@{user.id}>", inline=True)
            welcome_embed.add_field(name="🏷️ Tag Băng", value=f"`{tag}`", inline=True)
            welcome_embed.add_field(name="🛡️ Role Băng", value=clan_role.mention, inline=True)
            welcome_embed.add_field(name="📜 Khẩu Hiệu", value=slogan, inline=False)
            welcome_embed.add_field(
                name="🚀 Hướng Dẫn Nhanh",
                value="• Mời thành viên: `/clan invite [@user]`\n• Điểm danh mỗi ngày: `/clan checkin`\n• Nhiệm vụ tuần: `/clan quests`\n• Trung tâm điều khiển: `/clan hub`",
                inline=False
            )
            await text_channel.send(embed=welcome_embed)

            # 6. Thông báo thành công
            success_embed = discord.Embed(
                title="🏰 THÀNH LẬP BĂNG THÀNH CÔNG!",
                description=f"Băng **[{tag}] {name}** đã được khởi tạo hoàn tất!",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            success_embed.add_field(name="Kênh Chat", value=text_channel.mention, inline=True)
            success_embed.add_field(name="Kênh Voice", value=voice_channel.mention, inline=True)
            success_embed.add_field(name="Role Băng", value=clan_role.mention, inline=True)

            await interaction.followup.send(embed=success_embed)

        except discord.Forbidden:
            await interaction.followup.send(
                "⚠️ **Bot bị Discord chặn quyền thao tác Role hoặc Kênh!**\n\n"
                "👉 **Cách khắc phục đơn giản trong 5 giây:**\n"
                "1. Vào **Cài đặt Máy chủ (Server Settings)** -> chọn mục **Vai trò (Roles)**.\n"
                "2. Tìm vai trò của Bot và **kéo lên vị trí cao hơn** các vai trò khác.\n"
                "3. Đảm bảo Bot đã được tích chọn quyền `Quản lý Vai trò (Manage Roles)` và `Quản lý Kênh (Manage Channels)`.",
                ephemeral=True
            )
        except Exception as err:
            logger.error(f"Lỗi khi tạo băng: {err}", exc_info=True)
            await interaction.followup.send(f"❌ Đã xảy ra lỗi khi tạo băng: `{err}`", ephemeral=True)


class RenameClanModal(SafeModal):
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__(title=f"✏️ Đổi Thông Tin: {clan['name']}"[:45])
        self.clan = clan
        self.bot = bot

        self.new_name = ui.TextInput(
            label="Tên Băng Mới (3 - 25 ký tự)",
            default=clan["name"],
            min_length=3,
            max_length=25,
            required=True
        )
        self.new_tag = ui.TextInput(
            label="Tag Băng Mới (2 - 5 ký tự viết hoa)",
            default=clan["tag"],
            min_length=2,
            max_length=5,
            required=True
        )
        self.new_slogan = ui.TextInput(
            label="Khẩu Hiệu Mới (Tối đa 100 ký tự)",
            default=clan.get("description", ""),
            style=discord.TextStyle.paragraph,
            max_length=100,
            required=False
        )
        self.add_item(self.new_name)
        self.add_item(self.new_tag)
        self.add_item(self.new_slogan)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        now = int(time.time())
        clan_id = self.clan["clan_id"]

        # Kiểm tra cooldown 7 ngày
        last_renamed = self.clan.get("last_renamed_at", 0)
        cooldown_seconds = Cooldowns.RENAME_COOLDOWN_DAYS * 86400
        if last_renamed and (now - last_renamed < cooldown_seconds) and not interaction.user.guild_permissions.administrator:
            can_rename_at = last_renamed + cooldown_seconds
            await interaction.followup.send(f"❌ Bạn chỉ được đổi tên sau mỗi 7 ngày để tránh vi phạm Rate Limit của Discord! Có thể đổi lại vào: <t:{can_rename_at}:R>.", ephemeral=True)
            return

        name = self.new_name.value.strip()
        tag = self.new_tag.value.strip().upper()
        slogan = self.new_slogan.value.strip() or "Chưa có khẩu hiệu."

        if not re.match(r"^[A-Z0-9]+$", tag):
            await interaction.followup.send("❌ Tag băng chỉ được chứa chữ in hoa hoặc số!", ephemeral=True)
            return

        # Kiểm tra trùng tên / tag
        existing_name = await self.bot.db.get_clan_by_name(guild.id, name)
        if existing_name and existing_name["clan_id"] != clan_id:
            await interaction.followup.send(f"❌ Tên băng **{name}** đã bị trùng!", ephemeral=True)
            return

        existing_tag = await self.bot.db.get_clan_by_tag(guild.id, tag)
        if existing_tag and existing_tag["clan_id"] != clan_id:
            await interaction.followup.send(f"❌ Tag băng **{tag}** đã bị trùng!", ephemeral=True)
            return

        # Cập nhật Role Discord
        role = guild.get_role(int(self.clan["role_id"])) if self.clan.get("role_id") else None
        if role:
            try:
                await role.edit(name=f"[{tag}] {name}")
            except Exception as e:
                logger.warn(f"Không thể đổi tên role: {e}")

        # Cập nhật Tên Kênh Chat & Voice Không Dấu
        from utils.text_helper import to_channel_slug
        clean_slug = to_channel_slug(name)[:30]
        text_ch = guild.get_channel(int(self.clan["text_channel_id"])) if self.clan.get("text_channel_id") else None
        if text_ch:
            try:
                await text_ch.edit(name=f"💬・{clean_slug}", topic=f"Kênh sinh hoạt chính thức của Băng [{tag}] {name} | Khẩu hiệu: {slogan}")
            except Exception as e:
                logger.warn(f"Không thể đổi tên text channel: {e}")

        voice_ch = guild.get_channel(int(self.clan["voice_channel_id"])) if self.clan.get("voice_channel_id") else None
        if voice_ch:
            try:
                await voice_ch.edit(name=f"🔊・[{tag}] Phòng Sinh Hoạt")
            except Exception as e:
                logger.warn(f"Không thể đổi tên voice channel: {e}")

        # Cập nhật DB
        await self.bot.db.update_clan(
            clan_id,
            name=name,
            tag=tag,
            description=slogan,
            last_renamed_at=now
        )

        await self.bot.db.add_clan_log(
            clan_id=clan_id,
            actor_id=interaction.user.id,
            action="UPDATE_SETTINGS",
            details=f"Đổi tên thành [{tag}] {name}."
        )

        await interaction.followup.send(f"✅ Đã đổi tên và khẩu hiệu thành công sang: **[{tag}] {name}**!", ephemeral=True)


class ColorClanModal(SafeModal, title="🎨 Đổi Màu Sắc Role Băng"):
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__()
        self.clan = clan
        self.bot = bot

        self.color_hex = ui.TextInput(
            label="Mã màu Hex (Ví dụ: #FF5733 hoặc #5865F2)",
            default=clan.get("color_hex", "#5865F2"),
            min_length=4,
            max_length=7,
            required=True
        )
        self.add_item(self.color_hex)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        hex_val = self.color_hex.value.strip()
        if not hex_val.startswith("#"):
            hex_val = "#" + hex_val

        if not re.match(r"^#[0-9A-Fa-f]{6}$", hex_val):
            await interaction.followup.send("❌ Mã màu Hex không hợp lệ! Ví dụ đúng: `#FF5733` hoặc `#5865F2`.", ephemeral=True)
            return

        role = interaction.guild.get_role(int(self.clan["role_id"])) if self.clan.get("role_id") else None
        if role:
            try:
                await role.edit(color=parse_hex_color(hex_val), secondary_color=None, reason=f"Chủ Băng đổi màu role đơn sắc: {interaction.user.name}")
            except Exception as e:
                logger.warning(f"Lỗi đổi màu role: {e}")

        clean_hex = hex_val.upper()
        await self.bot.db.update_clan(self.clan["clan_id"], color_hex=clean_hex, secondary_color_hex=None)
        self.clan["color_hex"] = clean_hex
        self.clan["secondary_color_hex"] = None
        await self.bot.db.add_clan_log(
            clan_id=self.clan["clan_id"],
            actor_id=interaction.user.id,
            action="UPDATE_COLOR",
            details=f"Đổi màu Role sang đơn sắc {clean_hex}."
        )

        await interaction.followup.send(f"✅ Đã cập nhật màu Role thành công sang mã màu: **{clean_hex}**!", ephemeral=True)


class RoleNameModal(SafeModal, title="✏️ Đổi Tên Hiển Thị Role Băng"):
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__()
        self.clan = clan
        self.bot = bot

        self.new_role_name = ui.TextInput(
            label="Tên Role Hiển Thị Mới (tối đa 100 ký tự)",
            placeholder=f"[{clan['tag']}] {clan['name']}",
            max_length=100,
            required=True
        )
        self.add_item(self.new_role_name)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        role = guild.get_role(int(self.clan["role_id"])) if self.clan.get("role_id") else None
        if not role:
            await interaction.followup.send("❌ Không tìm thấy Role của băng trên server!", ephemeral=True)
            return

        if role >= guild.me.top_role:
            await interaction.followup.send(
                "⚠️ **Bot không đủ quyền chỉnh sửa Role này!**\n"
                "👉 Hãy vào **Server Settings -> Roles**, kéo Role của Bot lên cao hơn Role của Clan.",
                ephemeral=True
            )
            return

        new_name = self.new_role_name.value.strip()
        try:
            await role.edit(name=new_name, reason=f"Chủ Băng đổi tên role: {interaction.user.name}")
            await self.bot.db.add_clan_log(
                clan_id=self.clan["clan_id"],
                actor_id=interaction.user.id,
                action="UPDATE_ROLE_NAME",
                details=f"Đổi tên role thành '{new_name}'."
            )
            await interaction.followup.send(f"✅ Đã đổi tên Role thành công sang: **{new_name}**!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Bot bị thiếu quyền `Manage Roles` hoặc Role nằm cao hơn Role của Bot!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi đổi tên role: `{e}`", ephemeral=True)



class ImagesClanModal(SafeModal, title="🖼️ Dán Link URL Logo & Banner"):
    def __init__(self, clan: Dict[str, Any], bot, parent_view: Optional[Any] = None):
        super().__init__()
        self.clan = clan
        self.bot = bot
        self.parent_view = parent_view

        self.logo_url = ui.TextInput(
            label="Link Ảnh Logo (Bắt đầu bằng http/https)",
            default=clan.get("logo_url") if (clan.get("logo_url") or "").startswith(("http://", "https://")) else "",
            required=False
        )
        self.banner_url = ui.TextInput(
            label="Link Ảnh Banner (Bắt đầu bằng http/https)",
            default=clan.get("banner_url") if (clan.get("banner_url") or "").startswith(("http://", "https://")) else "",
            required=False
        )
        self.add_item(self.logo_url)
        self.add_item(self.banner_url)

    async def on_submit(self, interaction: discord.Interaction):
        logo = self.logo_url.value.strip() or None
        banner = self.banner_url.value.strip() or None

        if logo and not logo.startswith(("http://", "https://")):
            await auto_dismiss_notice(interaction, content="❌ Link Logo phải bắt đầu bằng `http://` hoặc `https://`!", delay=5)
            return

        if banner and not banner.startswith(("http://", "https://")):
            await auto_dismiss_notice(interaction, content="❌ Link Banner phải bắt đầu bằng `http://` hoặc `https://`!", delay=5)
            return

        # Giữ lại ảnh local nếu người dùng để trống ô link trong modal URL
        final_logo = logo if logo is not None else (self.clan.get("logo_url") if (self.clan.get("logo_url") or "").startswith("local://") else None)
        final_banner = banner if banner is not None else (self.clan.get("banner_url") if (self.clan.get("banner_url") or "").startswith("local://") else None)

        if logo and (self.clan.get("logo_url") or "").startswith("local://"):
            delete_local_asset(self.clan.get("logo_url"))
        if banner and (self.clan.get("banner_url") or "").startswith("local://"):
            delete_local_asset(self.clan.get("banner_url"))

        await self.bot.db.update_clan(self.clan["clan_id"], logo_url=final_logo, banner_url=final_banner)
        self.clan["logo_url"] = final_logo
        self.clan["banner_url"] = final_banner

        await self.bot.db.add_clan_log(
            clan_id=self.clan["clan_id"],
            actor_id=interaction.user.id,
            action="UPDATE_IMAGES",
            details="Cập nhật Logo hoặc Banner qua link URL."
        )

        if self.parent_view:
            self.parent_view.clan["logo_url"] = final_logo
            self.parent_view.clan["banner_url"] = final_banner
            try:
                new_embed, files = await _build_image_settings_payload(self.parent_view.clan, interaction.guild, self.bot.db)
                await interaction.response.edit_message(embed=new_embed, attachments=files, view=self.parent_view)
            except Exception:
                pass
            await auto_dismiss_notice(interaction, content="✅ Đã cập nhật Logo và Banner hồ sơ thành công!", delay=5)
        else:
            await auto_dismiss_notice(interaction, content="✅ Đã cập nhật Logo và Banner hồ sơ thành công!", delay=5)


class GradientColorModal(SafeModal, title="🌈 Nhập Dải Màu Gradient Tùy Chọn"):
    """Modal nhập dải màu 2 màu chuyển sắc Gradient cho Role Băng (Yêu cầu Server Boost)"""
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__()
        self.clan = clan
        self.bot = bot

        self.start_hex = ui.TextInput(
            label="Mã Màu Bắt Đầu (#HEX)",
            placeholder="Ví dụ: #FF512F hoặc #00F2FE",
            default=clan.get("color_hex", "#FF512F"),
            min_length=4,
            max_length=7,
            required=True
        )
        self.end_hex = ui.TextInput(
            label="Mã Màu Kết Thúc (#HEX)",
            placeholder="Ví dụ: #DD2476 hoặc #4FACFE",
            default=clan.get("secondary_color_hex") or "#DD2476",
            min_length=4,
            max_length=7,
            required=True
        )
        self.add_item(self.start_hex)
        self.add_item(self.end_hex)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        start_raw = self.start_hex.value.strip()
        end_raw = self.end_hex.value.strip()

        if not start_raw.startswith("#"):
            start_raw = f"#{start_raw}"
        if not end_raw.startswith("#"):
            end_raw = f"#{end_raw}"

        if not re.match(r"^#[0-9a-fA-F]{6}$", start_raw) or not re.match(r"^#[0-9a-fA-F]{6}$", end_raw):
            await interaction.followup.send("❌ Mã màu không hợp lệ! Vui lòng nhập đúng định dạng Hex 6 ký tự (ví dụ: `#FF512F` và `#DD2476`).", ephemeral=True)
            return

        guild = interaction.guild
        role = guild.get_role(int(self.clan["role_id"])) if self.clan.get("role_id") else None
        if not role:
            await interaction.followup.send("❌ Không tìm thấy Role của băng trên máy chủ!", ephemeral=True)
            return

        if role >= guild.me.top_role:
            await interaction.followup.send("⚠️ Role này đang nằm cao hơn hoặc bằng Role của Bot!", ephemeral=True)
            return

        start_color = parse_hex_color(start_raw)
        end_color = parse_hex_color(end_raw)
        start_clean = start_raw.upper()
        end_clean = end_raw.upper()

        try:
            # Thử áp dụng màu Gradient 2 màu (secondary_color)
            await role.edit(
                color=start_color,
                secondary_color=end_color,
                reason=f"Chủ Băng cài màu Gradient tùy chọn: {interaction.user.name}"
            )
            await self.bot.db.update_clan(
                self.clan["clan_id"],
                color_hex=start_clean,
                secondary_color_hex=end_clean
            )
            await self.bot.db.add_clan_log(
                clan_id=self.clan["clan_id"],
                actor_id=interaction.user.id,
                action="UPDATE_COLOR",
                details=f"Đổi màu Role sang Gradient {start_clean} ➔ {end_clean}."
            )
            self.clan["color_hex"] = start_clean
            self.clan["secondary_color_hex"] = end_clean

            await interaction.followup.send(
                f"🌈 **Đã áp dụng màu Gradient tùy chọn thành công!**\n"
                f"• Dải màu: **{start_clean}** ➔ **{end_clean}**\n"
                f"*(Màu sắc chuyển sắc tuyệt đẹp trên danh sách thành viên!)*",
                ephemeral=True
            )
        except (discord.HTTPException, discord.InvalidArgument) as err:
            logger.warning(f"Lỗi đặt gradient role (có thể server thiếu boost): {err}")
            # Fallback sang màu đơn sắc chính nếu server chưa đủ boost
            try:
                await role.edit(color=start_color, secondary_color=None, reason=f"Fallback sang màu đơn sắc: {interaction.user.name}")
                await self.bot.db.update_clan(self.clan["clan_id"], color_hex=start_clean, secondary_color_hex=None)
                self.clan["color_hex"] = start_clean
                self.clan["secondary_color_hex"] = None

                await interaction.followup.send(
                    f"⚠️ **Server của bạn chưa mở tính năng màu Gradient 2 màu (Yêu cầu Server Boost)!**\n"
                    f"👉 Bot đã tự động áp dụng **màu đơn sắc chính {start_clean}** cho Role của bạn để đảm bảo hiển thị đẹp nhất.",
                    ephemeral=True
                )
            except Exception as fb_err:
                await interaction.followup.send(f"❌ Lỗi khi đổi màu role: `{fb_err}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi đổi màu role: `{e}`", ephemeral=True)


class ApplyClanModal(SafeModal):
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__(title=f"📝 Đơn Xin Vào: {clan['name']}"[:45])
        self.clan = clan
        self.bot = bot

        self.note = ui.TextInput(
            label="Lời Nhắn Giới Thiệu Bản Thân",
            placeholder="Game hay chơi, thời gian online, mong muốn gắn kết...",
            style=discord.TextStyle.paragraph,
            max_length=300,
            required=False
        )
        self.add_item(self.note)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user = interaction.user
        guild = interaction.guild
        clan = self.clan

        # Kiểm tra điều kiện
        existing = await self.bot.db.get_clan_by_member(guild.id, user.id)
        if existing:
            await interaction.followup.send(f"❌ Bạn đã là thành viên của băng **{existing['name']}** rồi!", ephemeral=True)
            return

        cur_members = await self.bot.db.get_member_count(clan["clan_id"])
        if cur_members >= clan["max_members"]:
            await interaction.followup.send(f"❌ Băng **{clan['name']}** đã đầy sĩ số ({cur_members}/{clan['max_members']})!", ephemeral=True)
            return

        if clan["join_mode"] == JoinModes.INVITE_ONLY:
            await interaction.followup.send(f"❌ Băng **{clan['name']}** hiện để chế độ **Chỉ Nhận Lời Mời**! Bạn cần được cán bộ mời trực tiếp.", ephemeral=True)
            return

        # Chế độ MỞ TỰ DO (OPEN): Vào thẳng!
        if clan["join_mode"] == JoinModes.OPEN:
            role = guild.get_role(int(clan["role_id"])) if clan.get("role_id") else None
            if role:
                await user.add_roles(role, reason="Gia nhập băng mở tự do")

            await self.bot.db.add_member(guild.id, user.id, clan["clan_id"], Ranks.MEMBER)
            await self.bot.db.add_clan_log(
                clan_id=clan["clan_id"],
                actor_id=user.id,
                action="JOIN",
                details=f"<@{user.id}> tự do gia nhập băng."
            )

            # Chào mừng trong kênh chat riêng
            text_ch = guild.get_channel(int(clan["text_channel_id"])) if clan.get("text_channel_id") else None
            if text_ch:
                welcome_embed = discord.Embed(
                    title="👋 THÀNH VIÊN MỚI GIA NHẬP!",
                    description=f"Nhiệt liệt chào mừng <@{user.id}> đã chính thức trở thành thành viên của băng **{clan['name']}**!",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                welcome_view = WelcomeGreetingView(user.id)
                await text_ch.send(content=f"<@{user.id}>", embed=welcome_embed, view=welcome_view)

            # Gửi DM thông báo gia nhập thành công
            dm_welcome = discord.Embed(
                title="🎉 CHÀO MỪNG GIA NHẬP BĂNG!",
                description=f"Chúc mừng bạn đã chính thức gia nhập băng **[{clan['tag']}] {clan['name']}** tại máy chủ **{guild.name}**!",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            dm_welcome.add_field(name="🏰 Băng Đảng", value=f"[{clan['tag']}] {clan['name']}", inline=True)
            dm_welcome.add_field(name="👑 Chủ Băng", value=f"<@{clan['leader_id']}>", inline=True)
            dm_welcome.add_field(name="💬 Kênh Riêng", value="Role băng đã được cấp cho bạn. Hãy vào kênh chat và voice của băng để giao lưu cùng đồng đội ngay nhé!", inline=False)
            dm_welcome.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
            await send_dm_notification(user, dm_welcome)

            await interaction.followup.send(f"🎉 Chúc mừng bạn đã gia nhập thành công băng **[{clan['tag']}] {clan['name']}**!", ephemeral=True)
            return

        # Chế độ CẦN DUYỆT (APPROVAL)
        note_text = self.note.value.strip() or "Không có lời nhắn."
        req_id = await self.bot.db.create_request(
            clan_id=clan["clan_id"],
            guild_id=guild.id,
            user_id=user.id,
            actor_id=user.id,
            request_type="APPLY",
            note=note_text,
            expire_minutes=1440
        )

        text_ch = guild.get_channel(int(clan["text_channel_id"]))
        if text_ch:
            apply_embed = discord.Embed(
                title="📬 ĐƠN XIN GIA NHẬP BĂNG MỚI!",
                description=f"Ứng viên: <@{user.id}> ({user.name})\nThời gian nộp: <t:{int(time.time())}:R>",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            apply_embed.add_field(name="📝 Lời Nhắn", value=note_text, inline=False)
            apply_embed.set_footer(text="Các Cán Bộ / Phó Băng vui lòng duyệt đơn bên dưới")

            view = RequestView(request_id=req_id, bot=self.bot, is_invite=False)
            msg = await text_ch.send(content=f"<@&{clan['role_id']}>", embed=apply_embed, view=view)
            # Cập nhật message_id để tự dọn dẹp nếu hết hạn
            await self.bot.db.update_request_message_id(req_id, msg.id)

        # Gửi DM xác nhận cho người nộp đơn
        dm_applicant = discord.Embed(
            title="📨 ĐÃ GỬI ĐƠN XIN GIA NHẬP BĂNG",
            description=f"Đơn xin gia nhập băng **[{clan['tag']}] {clan['name']}** tại máy chủ **{guild.name}** của bạn đã được gửi thành công!",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        dm_applicant.add_field(name="💬 Lời nhắn của bạn", value=note_text, inline=False)
        dm_applicant.add_field(name="⏳ Trạng thái", value="Đang chờ Ban Quản Trị băng xét duyệt. Bạn sẽ nhận được thông báo ngay khi có kết quả!", inline=False)
        dm_applicant.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
        await send_dm_notification(user, dm_applicant)

        # Gửi DM thông báo cho Chủ Băng
        leader_mem = guild.get_member(int(clan["leader_id"]))
        if not leader_mem:
            try:
                leader_mem = await self.bot.fetch_user(int(clan["leader_id"]))
            except Exception:
                leader_mem = None
        if leader_mem:
            dm_leader = discord.Embed(
                title="📬 CÓ ĐƠN XIN GIA NHẬP BĂNG MỚI",
                description=f"Thành viên <@{user.id}> (**{user.display_name}**) vừa nộp đơn xin gia nhập băng **[{clan['tag']}] {clan['name']}** tại máy chủ **{guild.name}**!",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            dm_leader.add_field(name="💬 Lời nhắn", value=note_text, inline=False)
            dm_leader.add_field(name="👉 Thao tác", value="Hãy kiểm tra kênh chat riêng của băng để bấm nút **[✅ Duyệt Đơn]** hoặc **[❌ Từ Chối]**!", inline=False)
            dm_leader.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
            await send_dm_notification(leader_mem, dm_leader)

        await interaction.followup.send(f"✅ Đơn xin gia nhập của bạn đã được gửi đến ban cán bộ băng **[{clan['tag']}] {clan['name']}**!", ephemeral=True)


class DisbandClanModal(SafeModal):
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__(title=f"⚠️ Giải Tán Băng: {clan['name']}"[:45])
        self.clan = clan
        self.bot = bot

        self.confirm_name = ui.TextInput(
            label=f'Gõ tên băng: "{clan["name"]}"'[:45],
            placeholder=clan["name"],
            required=True
        )
        self.add_item(self.confirm_name)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.confirm_name.value.strip() != self.clan["name"]:
            await interaction.followup.send(f"❌ Tên nhập vào không khớp với tên băng (\"{self.clan['name']}\"). Thao tác giải tán đã bị hủy bỏ!", ephemeral=True)
            return

        clan_id = self.clan["clan_id"]
        guild = interaction.guild

        # 1. Xóa dữ liệu trong DB trước để tránh kích hoạt cảnh báo sai từ Gateway
        await self.bot.db.delete_clan(clan_id)

        # 2. Xóa các kênh
        for ch_key in ("text_channel_id", "log_channel_id", "voice_channel_id", "extra_voice_channel_id"):
            ch_id = self.clan.get(ch_key)
            if ch_id:
                ch = guild.get_channel(int(ch_id))
                if ch:
                    try:
                        await ch.delete(reason="Giải tán băng")
                    except Exception:
                        pass

        # 3. Xóa Role
        role_id = self.clan.get("role_id")
        if role_id:
            role = guild.get_role(int(role_id))
            if role:
                try:
                    await role.delete(reason="Giải tán băng")
                except Exception:
                    pass

        # Gửi log server nếu có
        cfg = await self.bot.db.get_guild_config(guild.id)
        if cfg and cfg.get("log_channel_id"):
            log_ch = guild.get_channel(int(cfg["log_channel_id"]))
            if log_ch:
                embed = discord.Embed(
                    title="⚠️ Băng Đã Giải Tán",
                    description=f"Băng **[{self.clan['tag']}] {self.clan['name']}** đã bị giải tán bởi Chủ Băng <@{interaction.user.id}>.",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                await log_ch.send(embed=embed)

        await interaction.followup.send(f"⚠️ Băng **[{self.clan['tag']}] {self.clan['name']}** đã chính thức bị giải tán và dọn dẹp sạch sẽ.", ephemeral=True)


# =============================================================================
# MODAL TẠO KÈO PARTY NHANH 1-CLICK CHO MEMBER
# =============================================================================

class ClanQuickPartyModal(SafeModal, title="🎮 Tạo Kèo Rủ Chơi Game Nhanh"):
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__()
        self.clan = clan
        self.bot = bot

    party_title = ui.TextInput(
        label="Tên Kèo Game",
        placeholder="Ví dụ: Leo rank Valorant 5 stack, ARAM vui vẻ...",
        min_length=2,
        max_length=50,
        required=True
    )
    party_slots = ui.TextInput(
        label="Số Người Đội Hình Chính (2 - 50)",
        default="5",
        min_length=1,
        max_length=2,
        required=True
    )
    party_time = ui.TextInput(
        label="Thời Gian Bắt Đầu (21:00 hoặc để trống)",
        placeholder="Để trống để chơi ngay khi đủ người!",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from utils.time_helper import parse_scheduled_time

        try:
            slots = int(self.party_slots.value.strip())
            if slots < 2 or slots > 50:
                await interaction.followup.send("❌ Số người phải từ 2 đến 50!", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Số người phải là một con số hợp lệ!", ephemeral=True)
            return

        scheduled_at = parse_scheduled_time(self.party_time.value)
        text_ch = interaction.guild.get_channel(int(self.clan["text_channel_id"])) if self.clan.get("text_channel_id") else None
        if not text_ch:
            await interaction.followup.send("❌ Không tìm thấy kênh chat của băng!", ephemeral=True)
            return

        embed = build_party_embed(
            title=self.party_title.value.strip(),
            creator_id=interaction.user.id,
            max_slots=slots,
            scheduled_at=scheduled_at,
            main_users=[interaction.user.id],
            reserve_users=[],
            status="OPEN"
        )

        msg = await text_ch.send(embed=embed)

        party_id = await self.bot.db.create_party(
            clan_id=self.clan["clan_id"],
            creator_id=interaction.user.id,
            channel_id=text_ch.id,
            message_id=msg.id,
            title=self.party_title.value.strip(),
            max_slots=slots,
            scheduled_at=scheduled_at
        )

        await self.bot.db.add_party_participant(party_id, interaction.user.id, "MAIN")
        view = PartyView(party_id=party_id, bot=self.bot)
        await msg.edit(view=view)

        await interaction.followup.send(f"✅ Đã tạo kèo game thành công tại kênh {text_ch.mention}!", ephemeral=True)


class ClanChallengeModal(SafeModal, title="⚔️ Soạn Thư Thách Đấu Băng Đảng"):
    """Modal nhập thông tin thư thách đấu gửi tới 1 băng cụ thể hoặc toàn thể các băng"""
    def __init__(self, source_clan: Dict[str, Any], target_clan: Optional[Dict[str, Any]], bot):
        super().__init__()
        self.source_clan = source_clan
        self.target_clan = target_clan  # None = gửi tới TẤT CẢ các băng khác
        self.bot = bot

    game_title = ui.TextInput(
        label="Tựa Game Muốn Thách Đấu",
        placeholder="Ví dụ: Valorant, Liên Quân, CS2, LMHT, PUBG...",
        min_length=2,
        max_length=60,
        required=True
    )
    match_format = ui.TextInput(
        label="Thể Thức & Quy Mô (Số người / BO)",
        placeholder="Ví dụ: 5v5 • BO3 • Giao hữu vui vẻ / Cược danh dự",
        default="5v5 • BO3 • Giao hữu vui vẻ",
        max_length=80,
        required=True
    )
    match_time = ui.TextInput(
        label="Thời Gian Thi Đấu Dự Kiến",
        placeholder="Ví dụ: 21:00 tối nay (hoặc để trống để hẹn sau)",
        max_length=60,
        required=False
    )
    challenge_message = ui.TextInput(
        label="Nội Dung Thư Khiêu Chiến",
        style=discord.TextStyle.paragraph,
        placeholder="Viết lời thách đấu gửi tới băng đối thủ...",
        min_length=3,
        max_length=500,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        game = self.game_title.value.strip()
        fmt = self.match_format.value.strip()
        mtime = self.match_time.value.strip() or "Thỏa thuận sau"
        msg_body = self.challenge_message.value.strip()

        if self.target_clan:
            targets = [self.target_clan]
        else:
            # Gửi toàn server: xác minh lại chức vụ + cooldown chống spam ping
            member_info = await self.bot.db.get_clan_by_member(guild.id, interaction.user.id)
            rank = member_info.get("rank") if member_info else None
            if rank not in (Ranks.LEADER, Ranks.CO_LEADER) and not interaction.user.guild_permissions.administrator:
                await auto_dismiss_notice(
                    interaction,
                    content="❌ Chỉ **Chủ Băng** hoặc **Phó Băng** mới có quyền phát Thư Thách Đấu tới **tất cả các băng** trong server!",
                    delay=6
                )
                return
            rem = await self.bot.db.get_global_challenge_remaining(
                self.source_clan["clan_id"], GLOBAL_CHALLENGE_COOLDOWN_SECONDS
            )
            if rem > 0:
                ready_ts = int(time.time()) + rem
                await auto_dismiss_notice(
                    interaction,
                    content=f"⏳ Băng bạn vừa gửi Thư Thách Đấu toàn server gần đây! Vui lòng đợi <t:{ready_ts}:R> nữa.",
                    delay=6
                )
                return
            all_clans = await self.bot.db.get_all_clans_in_guild(guild.id)
            targets = [c for c in all_clans if c["clan_id"] != self.source_clan["clan_id"]]

        if not targets:
            await auto_dismiss_notice(interaction, content="❌ Hiện chưa có băng đảng nào khác trong server để gửi thư thách đấu!", delay=5)
            return

        sent_names = []
        for t_clan in targets:
            ch_id = t_clan.get("text_channel_id")
            if not ch_id:
                continue
            target_ch = guild.get_channel(int(ch_id))
            if not target_ch:
                continue

            files: List[discord.File] = []
            logo_ref = await resolve_clan_logo(self.source_clan, files, fallback_to_default=True)
            embed = build_challenge_embed(
                source_clan=self.source_clan,
                sender_id=interaction.user.id,
                game_title=game,
                match_format=fmt,
                match_time=mtime,
                challenge_message=msg_body,
                target_clan=t_clan if self.target_clan else None,
                logo_filename=logo_ref,
                status="PENDING"
            )
            view = ClanChallengeResponseView(
                source_clan=self.source_clan,
                target_clan=t_clan,
                game_title=game,
                match_format=fmt,
                match_time=mtime,
                challenge_message=msg_body,
                sender_id=interaction.user.id,
                bot=self.bot
            )
            ping_role = f"<@&{t_clan['role_id']}>" if t_clan.get("role_id") else ""
            try:
                await target_ch.send(content=ping_role, embed=embed, files=files, view=view)
                sent_names.append(f"**[{t_clan['tag']}] {t_clan['name']}**")
            except Exception as send_err:
                logger.warning(f"Không thể gửi thư thách đấu tới băng {t_clan['name']}: {send_err}")

        if not sent_names:
            await auto_dismiss_notice(interaction, content="❌ Không tìm thấy kênh chat hợp lệ của băng đối thủ để gửi thư!", delay=5)
            return

        if not self.target_clan:
            await self.bot.db.mark_global_challenge_sent(self.source_clan["clan_id"])

        # Ghi nhận log & thông báo vào kênh băng mình
        target_summary = ", ".join(sent_names[:5]) + (f" và {len(sent_names) - 5} băng khác" if len(sent_names) > 5 else "")
        await self.bot.db.add_clan_log(
            clan_id=self.source_clan["clan_id"],
            actor_id=interaction.user.id,
            action="SEND_CHALLENGE",
            details=f"Gửi thư thách đấu tựa game {game} tới {target_summary}."
        )

        src_ch = guild.get_channel(int(self.source_clan["text_channel_id"])) if self.source_clan.get("text_channel_id") else None
        if src_ch:
            try:
                src_files: List[discord.File] = []
                src_logo = await resolve_clan_logo(self.source_clan, src_files, fallback_to_default=True)
                src_embed = build_challenge_embed(
                    source_clan=self.source_clan,
                    sender_id=interaction.user.id,
                    game_title=game,
                    match_format=fmt,
                    match_time=mtime,
                    challenge_message=msg_body,
                    target_clan=self.target_clan,
                    logo_filename=src_logo,
                    status="PENDING"
                )
                await src_ch.send(content=f"📣 <@{interaction.user.id}> vừa phát đi **Thư Thách Đấu** tới {target_summary}!", embed=src_embed, files=src_files)
            except Exception:
                pass

        await auto_dismiss_notice(interaction, content=f"⚔️ **Đã gửi Thư Thách Đấu ({game}) thành công tới:** {target_summary}!", delay=6)


class ClanChallengeResponseView(SafeView):
    """Nút bấm Chấp Nhận / Từ Chối trên Thư Thách Đấu tại kênh băng đối thủ"""
    def __init__(
        self,
        source_clan: Dict[str, Any],
        target_clan: Dict[str, Any],
        game_title: str,
        match_format: str,
        match_time: str,
        challenge_message: str,
        sender_id: int,
        bot
    ):
        super().__init__(timeout=86400)
        self.source_clan = source_clan
        self.target_clan = target_clan
        self.game_title = game_title
        self.match_format = match_format
        self.match_time = match_time
        self.challenge_message = challenge_message
        self.sender_id = sender_id
        self.bot = bot

    async def _respond_challenge(self, interaction: discord.Interaction, accepted: bool):
        user_clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not user_clan or user_clan["clan_id"] != self.target_clan["clan_id"]:
            await auto_dismiss_notice(interaction, content="❌ Chỉ thành viên của băng nhận thư mới có thể phản hồi thách đấu này!", delay=5)
            return
        if user_clan.get("rank") not in (Ranks.LEADER, Ranks.CO_LEADER, Ranks.OFFICER) and not interaction.user.guild_permissions.administrator:
            await auto_dismiss_notice(interaction, content="❌ Chỉ Chủ Băng, Phó Băng hoặc Cán Bộ mới có quyền quyết định nhận kèo thách đấu!", delay=5)
            return

        await interaction.response.defer()
        new_status = "ACCEPTED" if accepted else "DECLINED"
        for item in self.children:
            item.disabled = True

        new_embed = build_challenge_embed(
            source_clan=self.source_clan,
            sender_id=self.sender_id,
            game_title=self.game_title,
            match_format=self.match_format,
            match_time=self.match_time,
            challenge_message=self.challenge_message,
            target_clan=self.target_clan,
            status=new_status
        )
        await interaction.edit_original_response(embed=new_embed, view=self)

        # Báo tin về kênh băng gửi thư
        src_ch = interaction.guild.get_channel(int(self.source_clan["text_channel_id"])) if self.source_clan.get("text_channel_id") else None
        if src_ch:
            if accepted:
                notify_embed = discord.Embed(
                    title="⚔️ KÈO THÁCH ĐẤU ĐÃ ĐƯỢC CHẤP NHẬN!",
                    description=(
                        f"Băng **[{self.target_clan['tag']}] {self.target_clan['name']}** (Đại diện: <@{interaction.user.id}>) "
                        f"đã chính thức **CHẤP NHẬN** lời thách đấu tựa game **{self.game_title}** ({self.match_format})!\n"
                        f"👉 Hãy mau chóng tập hợp đội hình chuẩn bị giao tranh!"
                    ),
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
            else:
                notify_embed = discord.Embed(
                    title="🛡️ THƯ THÁCH ĐẤU ĐÃ BỊ TỪ CHỐI",
                    description=(
                        f"Băng **[{self.target_clan['tag']}] {self.target_clan['name']}** (Đại diện: <@{interaction.user.id}>) "
                        f"đã từ chối lời thách đấu tựa game **{self.game_title}** ở thời điểm hiện tại."
                    ),
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
            try:
                await src_ch.send(content=f"<@{self.sender_id}>", embed=notify_embed)
            except Exception:
                pass

    @ui.button(label="Chấp Nhận Thách Đấu", emoji="⚔️", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._respond_challenge(interaction, accepted=True)

    @ui.button(label="Từ Chối Lịch Sự", emoji="🛡️", style=discord.ButtonStyle.danger)
    async def decline_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._respond_challenge(interaction, accepted=False)


class ClanChallengeTargetSelect(ui.Select):
    """Dropdown chọn đối thủ thách đấu (1 băng cụ thể hoặc Tất cả các băng)"""
    def __init__(self, source_clan: Dict[str, Any], other_clans: List[Dict[str, Any]], bot):
        self.source_clan = source_clan
        self.clans_map = {str(c["clan_id"]): c for c in other_clans}
        self.bot = bot

        options = [
            discord.SelectOption(
                label="📢 GỬI TỚI TẤT CẢ CÁC BĂNG TRONG SERVER",
                value="ALL",
                description="Phát thư thách đấu tới toàn bộ các băng khác!",
                emoji="🔥"
            )
        ]
        for c in other_clans[:24]:
            options.append(
                discord.SelectOption(
                    label=f"[{c['tag']}] {c['name']} (Lv.{c.get('level', 1)})"[:100],
                    value=str(c["clan_id"]),
                    description=f"Gửi thư thách đấu tới băng {c['name']}"[:100],
                    emoji="⚔️"
                )
            )

        super().__init__(
            placeholder="⚔️ Chọn Băng muốn thách đấu (hoặc chọn Tất cả)...",
            options=options,
            min_values=1,
            max_values=1,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if val == "ALL":
            mem = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
            rank = mem.get("rank") if mem else None
            if rank not in (Ranks.LEADER, Ranks.CO_LEADER) and not interaction.user.guild_permissions.administrator:
                await auto_dismiss_notice(
                    interaction,
                    content="❌ Chỉ **Chủ Băng** hoặc **Phó Băng** mới có quyền gửi Thư Thách Đấu tới **tất cả các băng** trong server!\n*(Thành viên vẫn có thể gửi thách đấu riêng tới từng băng cụ thể)*.",
                    delay=6
                )
                return
            rem = await self.bot.db.get_global_challenge_remaining(
                self.source_clan["clan_id"], GLOBAL_CHALLENGE_COOLDOWN_SECONDS
            )
            if rem > 0:
                ready_ts = int(time.time()) + rem
                await auto_dismiss_notice(
                    interaction,
                    content=f"⏳ Mỗi băng chỉ được gửi Thư Thách Đấu toàn server mỗi **12 giờ** một lần để tránh spam ping!\n👉 Có thể gửi lại <t:{ready_ts}:R>.",
                    delay=6
                )
                return
            target_clan = None
        else:
            target_clan = self.clans_map.get(val)
        modal = ClanChallengeModal(source_clan=self.source_clan, target_clan=target_clan, bot=self.bot)
        await interaction.response.send_modal(modal)


def build_challenge_target_embed(other_clans: List[Dict[str, Any]]) -> discord.Embed:
    """Tạo Embed cho Trung Tâm Thách Đấu & Lập Kèo (tự động báo nếu là băng duy nhất trên server)."""
    if other_clans:
        desc = (
            "Chọn hình thức bạn muốn thực hiện bên dưới:\n\n"
            f"• **⚔️ Gửi Thư Thách Đấu:** Chọn 1 trong **{len(other_clans)}** băng đối thủ (hoặc **Tất cả các băng**) từ menu thả xuống để nhập Tựa Game, Thể Thức và Nội Dung khiêu chiến!\n"
            "• **🎮 Lập Kèo Nội Bộ:** Bấm nút bên dưới để rủ anh em cùng băng lập team chơi game."
        )
    else:
        desc = (
            "ℹ️ **Lưu ý:** Băng của bạn hiện đang là **băng đảng duy nhất** trong máy chủ này nên chưa có băng đối thủ để gửi thư thách đấu!\n\n"
            "👉 Bạn có thể bấm nút **[🎮 Lập Kèo Nội Bộ Băng Mình]** bên dưới để rủ anh em cùng băng lập team chiến game nhé."
        )
    return discord.Embed(
        title="⚔️ TRUNG TÂM THÁCH ĐẤU & LẬP KÈO BĂNG ĐẢNG",
        description=desc,
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )


class ClanChallengeTargetView(SafeView):
    """Bảng chọn hình thức: Gửi Thư Thách Đấu (1 băng / Tất cả băng) hoặc Lập Kèo Nội Bộ"""
    def __init__(self, source_clan: Dict[str, Any], other_clans: List[Dict[str, Any]], bot):
        super().__init__(timeout=600)
        self.source_clan = source_clan
        self.bot = bot

        if other_clans:
            self.add_item(ClanChallengeTargetSelect(source_clan=source_clan, other_clans=other_clans, bot=bot))

    @ui.button(label="Lập Kèo Nội Bộ Băng Mình", emoji="🎮", style=discord.ButtonStyle.primary, row=1)
    async def internal_party_btn(self, interaction: discord.Interaction, button: ui.Button):
        modal = ClanQuickPartyModal(clan=self.source_clan, bot=self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, interaction.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=1)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


# =============================================================================
# VIEWS & BUTTONS
# =============================================================================

class ClanInfoView(SafeView):
    """View tương tác động dưới /clan info tùy theo vai trò của người xem"""
    def __init__(
        self,
        clan_id: int,
        can_apply: bool = False,
        is_member: bool = False,
        is_leader: bool = False,
        bot: Any = None,
        streak_nick_enabled: bool = False,
    ):
        super().__init__(timeout=None)
        self.clan_id = clan_id
        self.bot = bot

        if streak_nick_enabled:
            self.streak_nick_btn.label = "Lửa Streak: Đang Bật"
            self.streak_nick_btn.style = discord.ButtonStyle.success

        if not can_apply:
            self.remove_item(self.apply_button)

        if not is_member:
            self.remove_item(self.checkin_btn)
            self.remove_item(self.wallpaper_info_btn)
            self.remove_item(self.leave_info_btn)
            self.remove_item(self.streak_nick_btn)

        if not is_leader:
            self.remove_item(self.settings_btn)

    @ui.button(label="Xem Thành Viên", emoji="👥", style=discord.ButtonStyle.primary, custom_id="clan_view_members_btn")
    async def view_members(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        clan = await self.bot.db.get_clan_by_id(self.clan_id)
        if not clan:
            await interaction.followup.send("❌ Không tìm thấy thông tin băng!", ephemeral=True)
            return

        members = await self.bot.db.get_clan_members(self.clan_id)
        embed, total_pages = build_members_embed(clan, members, page=1, page_size=10)
        view = MembersPaginationView(clan_id=self.clan_id, current_page=1, total_pages=total_pages, current_filter="ALL", bot=self.bot)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @ui.button(label="Xin Gia Nhập", emoji="📝", style=discord.ButtonStyle.success, custom_id="clan_apply_modal_btn")
    async def apply_button(self, interaction: discord.Interaction, button: ui.Button):
        clan = await self.bot.db.get_clan_by_id(self.clan_id)
        if not clan:
            await interaction.response.send_message("❌ Băng không tồn tại!", ephemeral=True)
            return
        modal = ApplyClanModal(clan=clan, bot=self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(label="Điểm Danh Nhanh", emoji="📅", style=discord.ButtonStyle.success, custom_id="clan_quick_checkin_btn")
    async def checkin_btn(self, interaction: discord.Interaction, button: ui.Button):
        from utils.text_helper import auto_dismiss_notice
        res = await perform_daily_checkin(self.bot.db, interaction.guild_id, interaction.user.id, expected_clan_id=self.clan_id)
        if not res["ok"]:
            await auto_dismiss_notice(interaction, content=res["error"], delay=5)
            return

        streak_note = "🎁 *(Thưởng thêm +50 EXP mốc 7 ngày!)*" if res["is_streak_7"] else ""
        if res.get("clan_streak_updated") and self.bot:
            from utils.streak_nick import sync_clan_streak_queue
            asyncio.create_task(sync_clan_streak_queue(self.bot, self.clan_id))
        await auto_dismiss_notice(
            interaction,
            content=(
                f"🎉 **Điểm danh thành công!**\n"
                f"• Chuỗi streak: **{res['new_streak']} ngày** {streak_note}\n"
                f"• Băng nhận: **+{res['clan_exp_to_add']} EXP** • Cá nhân nhận: **+{res['contribution']} Điểm cống hiến**"
            ),
            delay=6
        )

    @ui.button(label="Cài Đặt", emoji="⚙️", style=discord.ButtonStyle.secondary, custom_id="clan_quick_settings_btn")
    async def settings_btn(self, interaction: discord.Interaction, button: ui.Button):
        clan = await self.bot.db.get_clan_by_id(self.clan_id)
        if not clan or (int(clan["leader_id"]) != interaction.user.id and not interaction.user.guild_permissions.administrator):
            await auto_dismiss_notice(interaction, content="❌ Chỉ Chủ Băng mới có quyền truy cập cài đặt!", delay=5)
            return
        await interaction.response.defer()
        view = SettingsDashboardView(clan=clan, bot=self.bot)
        await interaction.edit_original_response(content="⚙️ **BẢNG ĐIỀU KHIỂN CÀI ĐẶT BĂNG:**", embed=None, attachments=[], view=view)

    @ui.button(label="Xem Banner Băng", emoji="🚩", style=discord.ButtonStyle.secondary, custom_id="clan_quick_banner_btn", row=1)
    async def view_banner_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        clan = await self.bot.db.get_clan_by_id(self.clan_id)
        if not clan:
            await interaction.followup.send("❌ Băng không tồn tại!", ephemeral=True)
            return
        members = await self.bot.db.get_clan_members(self.clan_id)
        embed, files = await _build_banner_preview_payload(clan, len(members), interaction.guild)
        await interaction.followup.send(embed=embed, files=files, ephemeral=True)

    @ui.button(label="Ảnh Nền Băng", emoji="🖼️", style=discord.ButtonStyle.secondary, custom_id="clan_info_wallpaper_btn", row=1)
    async def wallpaper_info_btn(self, interaction: discord.Interaction, button: ui.Button):
        clan = await self.bot.db.get_clan_by_id(self.clan_id)
        if not clan:
            await auto_dismiss_notice(interaction, content="❌ Băng không tồn tại!", delay=5)
            return
        now = time.time()
        last_ts = _WALLPAPER_COOLDOWNS.get(clan["clan_id"], 0.0)
        rem = int(WALLPAPER_COOLDOWN_SECONDS - (now - last_ts))
        if rem > 0:
            await auto_dismiss_notice(
                interaction,
                content=f"⏳ Ảnh nền Full HD vừa được xuất gần đây! Vui lòng đợi **{rem} giây** nữa.",
                delay=5
            )
            return
        _WALLPAPER_COOLDOWNS[clan["clan_id"]] = now
        await interaction.response.defer(ephemeral=True)
        from utils.canvas import generate_clan_wallpaper
        members = await self.bot.db.get_clan_members(clan["clan_id"])
        milestones = await self.bot.db.get_clan_milestones(clan["clan_id"], limit=5)
        pet = await self.bot.db.get_clan_pet(clan["clan_id"])
        member_names = {
            str(m["user_id"]): mem.display_name
            for m in members[:8]
            if (mem := interaction.guild.get_member(int(m["user_id"])))
        }
        buf = await asyncio.to_thread(generate_clan_wallpaper, clan, members, milestones, member_names, pet)
        file = discord.File(fp=buf, filename="clan_wallpaper.png")
        embed = discord.Embed(
            title=f"🖼️ HÌNH NỀN DESKTOP BĂNG [{clan['tag']}] {clan['name']}",
            description="Tác phẩm đồ họa Full HD 1920x1080 ghi lại dấu ấn, thành viên chủ chốt và biên niên sử của băng!\n*(Nhấn vào ảnh → 'Open in Browser' để tải về ảnh gốc)*",
            color=parse_hex_color(clan.get("color_hex")),
            timestamp=datetime.now()
        )
        embed.set_image(url="attachment://clan_wallpaper.png")
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)

    @ui.button(label="Rời Băng", emoji="🚪", style=discord.ButtonStyle.danger, custom_id="clan_info_leave_btn", row=1)
    async def leave_info_btn(self, interaction: discord.Interaction, button: ui.Button):
        clan = await self.bot.db.get_clan_by_id(self.clan_id)
        if not clan:
            await auto_dismiss_notice(interaction, content="❌ Băng không tồn tại!", delay=5)
            return
        if int(clan["leader_id"]) == interaction.user.id:
            await interaction.response.send_message(
                "❌ **Bạn đang là Chủ Băng!** Hãy chuyển giao quyền Chủ Băng (trong **Quản Lý Thành Viên**) hoặc **Giải Tán Băng** (trong **Cài Đặt Băng**).",
                ephemeral=True
            )
            return
        view = LeaveClanConfirmView(clan=clan, bot=self.bot)
        await interaction.response.send_message(
            f"⚠️ Bạn có chắc chắn muốn rời khỏi băng **[{clan['tag']}] {clan['name']}** không?\n*(Bạn có thể tự do gia nhập hoặc tạo băng khác bất cứ lúc nào!)*",
            view=view,
            ephemeral=True
        )

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, custom_id="clan_info_back_hub_btn", row=1)
    async def back_to_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, interaction.user, self.bot)

    @ui.button(label="Lửa Streak: Đang Tắt", emoji="🔥", style=discord.ButtonStyle.secondary, custom_id="clan_info_streak_nick_btn", row=2)
    async def streak_nick_btn(self, interaction: discord.Interaction, button: ui.Button):
        from utils.streak_nick import restore_original_nick, sync_member_streak_nick
        state = await self.bot.db.get_member_streak_nick_state(interaction.guild_id, interaction.user.id)
        if not state or int(state.get("clan_id") or 0) != self.clan_id:
            await auto_dismiss_notice(interaction, content="❌ Bạn không phải thành viên của băng này!", delay=5)
            return

        currently_on = int(state.get("streak_nick_enabled") or 0) == 1
        if currently_on:
            await interaction.response.defer()
            await restore_original_nick(self.bot.db, interaction.user, disable_opt_in=True, reason="Thành viên tắt Lửa Streak")
            button.label = "Lửa Streak: Đang Tắt"
            button.style = discord.ButtonStyle.secondary
            await interaction.edit_original_response(view=self)
            await auto_dismiss_notice(interaction, content="🔥 Đã **tắt** Lửa Streak trên biệt danh và khôi phục tên gốc của bạn!", delay=5)
            return

        clan = await self.bot.db.get_clan_by_id(self.clan_id)
        clan_streak = int((clan or {}).get("clan_streak") or 0)
        res = await sync_member_streak_nick(
            self.bot.db,
            interaction.user,
            self.clan_id,
            clan_streak,
            notify_on_overflow=False,
            enable_opt_in=True,
        )
        status = res.get("status")
        if status == "TOO_LONG":
            await auto_dismiss_notice(
                interaction,
                content=(
                    f"❌ Tên bạn đang dài **{res['base_len']}** ký tự, thêm `{res['suffix']}` sẽ thành **{res['total_len']}/32** ký tự.\n"
                    f"Vui lòng tự rút ngắn bớt ít nhất **{res['excess']} ký tự** rồi bấm bật lại!"
                ),
                delay=8,
            )
            return
        if status == "FORBIDDEN":
            await auto_dismiss_notice(
                interaction,
                content="⚠️ Discord chặn mọi bot đổi biệt danh của **Chủ Server** hoặc người có Role cao hơn Bot (hoặc Bot thiếu quyền `Manage Nicknames`).",
                delay=7,
            )
            return

        await interaction.response.defer()
        button.label = "Lửa Streak: Đang Bật"
        button.style = discord.ButtonStyle.success
        await interaction.edit_original_response(view=self)
        note = (
            f"🔥 Đã **bật** Lửa Streak (` 🔥 {clan_streak}`) lên biệt danh của bạn!"
            if clan_streak > 0
            else "🔥 Đã **bật** Lửa Streak! Khi băng đạt ≥ 2 người điểm danh/ngày, lửa sẽ tự động hiện lên tên bạn."
        )
        await auto_dismiss_notice(interaction, content=note, delay=6)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, custom_id="clan_info_close_btn", row=1)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


class WelcomeGreetingView(SafeView):
    """Nút bấm tương tác chào đón thành viên mới vào kênh chat băng"""
    def __init__(self, new_member_id: int):
        super().__init__(timeout=86400)  # 24 giờ
        self.new_member_id = new_member_id
        self.greeted_users: set[int] = set()

    @ui.button(label="Chào Mừng! 👋", style=discord.ButtonStyle.success, emoji="🎉", custom_id="welcome_greet_btn")
    async def greet_btn(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id == self.new_member_id:
            await interaction.response.send_message("😄 Bạn là thành viên vừa mới gia nhập mà!", ephemeral=True)
            return

        if interaction.user.id in self.greeted_users:
            await interaction.response.send_message("👋 Bạn đã gửi lời chào mừng thành viên này rồi!", ephemeral=True)
            return

        self.greeted_users.add(interaction.user.id)
        button.label = f"Chào Mừng! ({len(self.greeted_users)})"
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass

        import random
        greetings = [
            f"🎉 <@{interaction.user.id}> vừa vỗ vai chào mừng <@{self.new_member_id}> gia nhập băng!",
            f"🔥 <@{interaction.user.id}> hú hét nồng nhiệt: Chào mừng <@{self.new_member_id}> về chung một nhà!",
            f"🍻 <@{interaction.user.id}> mời <@{self.new_member_id}> một ly mừng ngày kết nạp!",
            f"🎮 <@{interaction.user.id}> bắt tay <@{self.new_member_id}>: Chuẩn bị vào game gánh team nhé!"
        ]
        await interaction.response.send_message(random.choice(greetings))


class CustomTitleModal(SafeModal):
    """Modal đặt hoặc gỡ danh hiệu tùy chỉnh nội bộ cho thành viên"""
    def __init__(self, target_member: discord.Member, clan: Dict[str, Any], bot):
        super().__init__(title=f"🎖️ Danh Hiệu: {target_member.display_name[:15]}")
        self.target_member = target_member
        self.clan = clan
        self.bot = bot

        self.title_input = ui.TextInput(
            label="Danh Hiệu / Biệt Danh (Tối đa 25 ký tự)",
            placeholder="Ví dụ: Gánh Team 👑, Chúa Hề 🤡, Cú Đêm 🌙 (để trống để gỡ)",
            max_length=25,
            required=False
        )
        self.add_item(self.title_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        new_title = self.title_input.value.strip() or None

        await self.bot.db.update_member_custom_title(
            interaction.guild_id,
            self.target_member.id,
            new_title
        )

        action_desc = f"đặt danh hiệu **【 {new_title} 】** cho" if new_title else "gỡ danh hiệu của"
        await self.bot.db.add_clan_log(
            clan_id=self.clan["clan_id"],
            actor_id=interaction.user.id,
            target_id=self.target_member.id,
            action="UPDATE_TITLE",
            details=f"<@{interaction.user.id}> đã {action_desc} <@{self.target_member.id}>."
        )

        msg = f"✅ Đã {action_desc} <@{self.target_member.id}> thành công!"
        await interaction.followup.send(msg, ephemeral=True)


class ClanCustomTitleMemberSelect(ui.Select):
    """Menu chọn thành viên để trao / gỡ danh hiệu nội bộ"""
    def __init__(self, clan: Dict[str, Any], members: List[Dict[str, Any]], guild: discord.Guild, bot):
        self.clan = clan
        self.bot = bot
        options = []
        for m in members[:25]:
            uid = int(m["user_id"])
            discord_member = guild.get_member(uid)
            display_name = discord_member.display_name if discord_member else f"User {uid}"
            current_title = f" [{m['custom_title']}]" if m.get("custom_title") else ""
            options.append(
                discord.SelectOption(
                    label=f"{display_name} ({m.get('rank', 'MEMBER')})"[:100],
                    value=str(uid),
                    description=(f"Danh hiệu hiện tại:{current_title}"[:100]) if current_title else "Chưa có danh hiệu",
                    emoji="🎖️"
                )
            )
        super().__init__(placeholder="Chọn thành viên để trao hoặc sửa danh hiệu...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        target_uid = int(self.values[0])
        member = interaction.guild.get_member(target_uid)
        if not member:
            try:
                member = await interaction.guild.fetch_member(target_uid)
            except Exception:
                member = None
        if not member:
            await interaction.response.send_message("❌ Không tìm thấy thành viên trong máy chủ Discord!", ephemeral=True)
            return

        modal = CustomTitleModal(target_member=member, clan=self.clan, bot=self.bot)
        await interaction.response.send_modal(modal)


class ClanCustomTitleMemberSelectView(SafeView):
    """View bọc Menu chọn thành viên trao danh hiệu"""
    def __init__(self, clan: Dict[str, Any], members: List[Dict[str, Any]], guild: discord.Guild, bot):
        super().__init__(timeout=120)
        self.add_item(ClanCustomTitleMemberSelect(clan, members, guild, bot))


# =============================================================================
# DANH SÁCH BĂNG ĐẢNG & XIN GIA NHẬP (INTERACTIVE CLAN LIST)
# =============================================================================

class ClanSelectDropdown(ui.Select):
    """Menu chọn 1 băng trong danh sách để xem hồ sơ và xin vào"""
    def __init__(self, clans: List[Dict[str, Any]], bot):
        self.bot = bot
        options = []
        for c in clans[:25]:
            mode_str = {
                JoinModes.OPEN: "Mở Tự Do",
                JoinModes.APPROVAL: "Cần Duyệt",
                JoinModes.INVITE_ONLY: "Chỉ Nhận Lời Mời"
            }.get(c.get("join_mode", "APPROVAL"), "Cần Duyệt")
            options.append(
                discord.SelectOption(
                    label=f"[{c['tag']}] {c['name']} (Lv.{c.get('level', 1)})"[:100],
                    value=str(c["clan_id"]),
                    description=f"{c.get('member_count', 1)}/{c.get('max_members', 15)} TV • {mode_str}"[:100],
                    emoji="🏰"
                )
            )
        super().__init__(placeholder="🔍 Chọn một băng để xem thông tin & gia nhập...", options=options, min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        clan_id = int(self.values[0])
        clan = await self.bot.db.get_clan_by_id(clan_id)
        if not clan:
            await interaction.followup.send("❌ Băng không tồn tại hoặc vừa bị giải tán!", ephemeral=True)
            return

        members = await self.bot.db.get_clan_members(clan_id)
        level_info = get_level_info(clan["exp"])
        viewer_clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        can_apply = (viewer_clan is None) and (clan["join_mode"] != JoinModes.INVITE_ONLY)
        is_member = (viewer_clan is not None and viewer_clan["clan_id"] == clan["clan_id"])
        is_leader = (int(clan["leader_id"]) == interaction.user.id)

        embed, files = await build_clan_profile_payload(clan, members, level_info, interaction.guild)

        view = ClanDetailView(clan=clan, can_apply=can_apply, is_member=is_member, is_leader=is_leader, bot=self.bot)
        await interaction.followup.send(embed=embed, files=files, view=view, ephemeral=True)


class ClanDetailView(SafeView):
    """View hiển thị hồ sơ chi tiết của băng được chọn từ danh sách"""
    def __init__(self, clan: Dict[str, Any], can_apply: bool, is_member: bool, is_leader: bool, bot):
        super().__init__(timeout=600)
        self.clan = clan
        self.bot = bot

        if not can_apply:
            self.remove_item(self.apply_btn)

    @ui.button(label="Nộp Đơn / Gia Nhập", emoji="📩", style=discord.ButtonStyle.success)
    async def apply_btn(self, interaction: discord.Interaction, button: ui.Button):
        clan = await self.bot.db.get_clan_by_id(self.clan["clan_id"])
        if not clan:
            await interaction.response.send_message("❌ Băng không tồn tại!", ephemeral=True)
            return
        modal = ApplyClanModal(clan=clan, bot=self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(label="Xem Thành Viên", emoji="👥", style=discord.ButtonStyle.primary)
    async def members_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        members = await self.bot.db.get_clan_members(self.clan["clan_id"])
        files = []
        logo_ref = await resolve_clan_logo(self.clan, files, fallback_to_default=True)
        embed, total_pages = build_members_embed(self.clan, members, page=1, page_size=10, logo_filename=logo_ref)
        view = MembersPaginationView(clan_id=self.clan["clan_id"], current_page=1, total_pages=total_pages, current_filter="ALL", bot=self.bot)
        await interaction.followup.send(embed=embed, files=files, view=view, ephemeral=True)

    @ui.button(label="Xem Banner Băng", emoji="🚩", style=discord.ButtonStyle.secondary)
    async def banner_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        clan = await self.bot.db.get_clan_by_id(self.clan["clan_id"])
        if not clan:
            await interaction.followup.send("❌ Băng không tồn tại!", ephemeral=True)
            return
        members = await self.bot.db.get_clan_members(clan["clan_id"])
        embed, files = await _build_banner_preview_payload(clan, len(members), interaction.guild)
        await interaction.followup.send(embed=embed, files=files, ephemeral=True)

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary)
    async def back_to_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, interaction.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


class QuickApplyDropdown(ui.Select):
    """Dropdown chọn nhanh băng để mở Modal nộp đơn trực tiếp"""
    def __init__(self, clans: List[Dict[str, Any]], bot):
        self.clans = clans
        self.bot = bot
        options = []
        for c in clans[:25]:
            mode_str = {
                JoinModes.OPEN: "Mở Tự Do",
                JoinModes.APPROVAL: "Cần Duyệt",
                JoinModes.INVITE_ONLY: "Chỉ Nhận Lời Mời"
            }.get(c.get("join_mode", "APPROVAL"), "Cần Duyệt")
            options.append(
                discord.SelectOption(
                    label=f"[{c['tag']}] {c['name']} (Lv.{c.get('level', 1)})"[:100],
                    value=str(c["clan_id"]),
                    description=f"{c.get('member_count', 1)}/{c.get('max_members', 15)} TV • {mode_str}"[:100],
                    emoji="📩"
                )
            )
        super().__init__(
            placeholder="📩 Chọn băng muốn nộp đơn xin gia nhập...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        clan_id = int(self.values[0])
        clan = await self.bot.db.get_clan_by_id(clan_id)
        if not clan:
            await interaction.response.send_message("❌ Băng không tồn tại hoặc vừa bị giải tán!", ephemeral=True)
            return
        modal = ApplyClanModal(clan=clan, bot=self.bot)
        await interaction.response.send_modal(modal)


class QuickApplySelectView(SafeView):
    """View phụ chứa Dropdown nộp đơn nhanh"""
    def __init__(self, clans: List[Dict[str, Any]], bot):
        super().__init__(timeout=120)
        self.add_item(QuickApplyDropdown(clans=clans, bot=bot))


class ClanListInteractiveView(SafeView):
    """View tương tác cho Bảng danh mục Băng Đảng kèm Dropdown và Nút Lập Băng Mới"""
    def __init__(self, clans: List[Dict[str, Any]], bot):
        super().__init__(timeout=600)
        self.clans = clans
        self.bot = bot

        if clans:
            self.add_item(ClanSelectDropdown(clans=clans, bot=bot))

    @ui.button(label="Nộp Đơn Vào Băng", emoji="📩", style=discord.ButtonStyle.primary, row=1)
    async def apply_direct_btn(self, interaction: discord.Interaction, button: ui.Button):
        existing = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if existing:
            await interaction.response.send_message(f"❌ Bạn đã là thành viên của băng **{existing['name']}** rồi!", ephemeral=True)
            return
        if not self.clans:
            await interaction.response.send_message("❌ Máy chủ hiện chưa có băng nào đang hoạt động!", ephemeral=True)
            return

        if len(self.clans) == 1:
            clan = await self.bot.db.get_clan_by_id(self.clans[0]["clan_id"])
            if not clan:
                await interaction.response.send_message("❌ Băng không tồn tại hoặc vừa bị giải tán!", ephemeral=True)
                return
            modal = ApplyClanModal(clan=clan, bot=self.bot)
            await interaction.response.send_modal(modal)
        else:
            view = QuickApplySelectView(clans=self.clans, bot=self.bot)
            await interaction.response.send_message("📩 **Hãy chọn băng bạn muốn nộp đơn gia nhập bên dưới:**", view=view, ephemeral=True)

    @ui.button(label="Thành Lập Băng Mới", emoji="✨", style=discord.ButtonStyle.success, row=1)
    async def create_btn(self, interaction: discord.Interaction, button: ui.Button):
        modal = CreateClanModal(bot=self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(label="Bảng Xếp Hạng Server", emoji="🏆", style=discord.ButtonStyle.secondary, row=1)
    async def leaderboard_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        from utils.canvas import generate_leaderboard_image
        clans = await self.bot.db.get_leaderboard(interaction.guild_id, criteria="level", limit=10)
        buf = await asyncio.to_thread(generate_leaderboard_image, interaction.guild.name, clans, "level")
        file = discord.File(fp=buf, filename="leaderboard.png")
        embed = build_leaderboard_embed(interaction.guild.name, clans, criteria="level", attachment_filename="leaderboard.png")
        view = LeaderboardInteractiveView(guild_name=interaction.guild.name, bot=self.bot, initial_criteria="level")
        await interaction.edit_original_response(embed=embed, attachments=[file], view=view)

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, interaction.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=1)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


# =============================================================================
# BẢNG XẾP HẠNG TƯƠNG TÁC (LEADERBOARD INTERACTIVE VIEW)
# =============================================================================

class LeaderboardInteractiveView(SafeView):
    """View tương tác động chuyển đổi giữa các tiêu chí Bảng Xếp Hạng Server"""
    def __init__(self, guild_name: str, bot, initial_criteria: str = "level"):
        super().__init__(timeout=600)
        self.guild_name = guild_name
        self.bot = bot
        self.current_criteria = initial_criteria
        self._update_button_styles()

    def _update_button_styles(self):
        self.level_btn.style = discord.ButtonStyle.primary if self.current_criteria == "level" else discord.ButtonStyle.secondary
        self.weekly_btn.style = discord.ButtonStyle.primary if self.current_criteria == "weekly" else discord.ButtonStyle.secondary
        self.members_btn.style = discord.ButtonStyle.primary if self.current_criteria == "members" else discord.ButtonStyle.secondary

    async def _update_leaderboard(self, interaction: discord.Interaction, criteria: str):
        await interaction.response.defer()
        self.current_criteria = criteria
        self._update_button_styles()
        from utils.canvas import generate_leaderboard_image
        clans = await self.bot.db.get_leaderboard(interaction.guild_id, criteria=criteria, limit=10)
        buf = await asyncio.to_thread(generate_leaderboard_image, self.guild_name, clans, criteria)
        file = discord.File(fp=buf, filename="leaderboard.png")
        embed = build_leaderboard_embed(self.guild_name, clans, criteria=criteria, attachment_filename="leaderboard.png")
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    @ui.button(label="Cấp Độ & EXP", emoji="🌟", style=discord.ButtonStyle.primary)
    async def level_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._update_leaderboard(interaction, "level")

    @ui.button(label="Năng Động Tuần", emoji="🔥", style=discord.ButtonStyle.secondary)
    async def weekly_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._update_leaderboard(interaction, "weekly")

    @ui.button(label="Sĩ Số Thành Viên", emoji="👥", style=discord.ButtonStyle.secondary)
    async def members_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._update_leaderboard(interaction, "members")

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, interaction.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=1)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


# =============================================================================
# RỜI BĂNG TỰ NGUYỆN (LEAVE CLAN CONFIRM VIEW)
# =============================================================================

class LeaveClanConfirmView(SafeView):
    """View xác nhận 2 lớp cho việc tự nguyện rời băng"""
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__(timeout=900)
        self.clan = clan
        self.bot = bot

    @ui.button(label="Xác Nhận Rời Băng", emoji="🚪", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user
        clan = self.clan

        # Xóa role
        if clan.get("role_id"):
            role = guild.get_role(int(clan["role_id"]))
            if role and role in user.roles:
                try:
                    await user.remove_roles(role, reason="Tự nguyện rời băng")
                except Exception:
                    pass

        # Gỡ hậu tố Lửa Streak nếu đang gắn trước khi rời băng
        from utils.streak_nick import restore_original_nick
        await restore_original_nick(self.bot.db, user, disable_opt_in=True, reason="Rời băng")

        # Xóa khỏi DB (Bỏ cooldown theo yêu cầu)
        await self.bot.db.remove_member(guild.id, user.id)

        # Ghi log
        await self.bot.db.add_clan_log(
            clan_id=clan["clan_id"],
            actor_id=user.id,
            action="LEAVE",
            details=f"<@{user.id}> đã tự nguyện rời khỏi băng."
        )

        # Thông báo vào kênh riêng của clan
        if clan.get("text_channel_id"):
            ch = guild.get_channel(int(clan["text_channel_id"]))
            if ch:
                embed = discord.Embed(
                    title="🚪 THÀNH VIÊN RỜI BĂNG",
                    description=f"<@{user.id}> (**{user.display_name}**) đã tự nguyện rời khỏi băng **{clan['name']}**.",
                    color=discord.Color.light_grey(),
                    timestamp=datetime.now()
                )
                await ch.send(embed=embed)

        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(
            content=f"✅ Bạn đã rời khỏi băng **[{clan['tag']}] {clan['name']}** thành công.\n✨ Bạn không bị áp dụng thời gian chờ và có thể tự do gia nhập hoặc thành lập băng mới ngay!",
            view=self
        )

    @ui.button(label="Hủy Bỏ", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ Đã hủy thao tác rời băng.", view=self)


# =============================================================================
# QUẢN LÝ THÀNH VIÊN & NHÂN SỰ (MEMBER MANAGEMENT)
# =============================================================================

class KickMemberModal(SafeModal):
    """Modal nhập lý do trục xuất thành viên"""
    def __init__(self, target_member: discord.Member, clan: Dict[str, Any], bot):
        super().__init__(title=f"👢 Trục Xuất: {target_member.display_name[:15]}")
        self.target_member = target_member
        self.clan = clan
        self.bot = bot

        self.reason_input = ui.TextInput(
            label="Lý Do Trục Xuất (Tùy chọn)",
            placeholder="Vi phạm nội quy, không hoạt động, toxic...",
            max_length=100,
            required=False
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        reason = self.reason_input.value.strip() or "Không nêu lý do"

        # Thu hồi Role
        if self.clan.get("role_id"):
            role = guild.get_role(int(self.clan["role_id"]))
            if role and role in self.target_member.roles:
                try:
                    await self.target_member.remove_roles(role, reason=f"Bị trục xuất: {reason}")
                except Exception:
                    pass

        # Gỡ hậu tố Lửa Streak nếu đang gắn trước khi trục xuất
        from utils.streak_nick import restore_original_nick
        await restore_original_nick(self.bot.db, self.target_member, disable_opt_in=True, reason="Bị trục xuất khỏi băng")

        # Xóa khỏi DB (Bỏ cooldown theo yêu cầu)
        await self.bot.db.remove_member(guild.id, self.target_member.id)

        # Ghi log
        await self.bot.db.add_clan_log(
            clan_id=self.clan["clan_id"],
            actor_id=interaction.user.id,
            target_id=self.target_member.id,
            action="KICK",
            details=f"<@{interaction.user.id}> đã trục xuất <@{self.target_member.id}>. Lý do: {reason}"
        )

        # Gửi DM thông báo lý do trục xuất cho thành viên
        dm_embed = discord.Embed(
            title="👢 BẠN ĐÃ BỊ TRỤC XUẤT KHỎI BĂNG",
            description=f"Bạn đã bị trục xuất khỏi băng **[{self.clan['tag']}] {self.clan['name']}** tại máy chủ **{guild.name}**.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        dm_embed.add_field(name="👮 Người thực hiện", value=f"<@{interaction.user.id}> ({interaction.user.display_name})", inline=True)
        dm_embed.add_field(name="💬 Lý do trục xuất", value=reason, inline=False)
        dm_embed.add_field(name="✨ Lưu ý", value="Bạn không bị áp dụng thời gian chờ (cooldown) và có thể tự do gia nhập hoặc tạo băng khác ngay lập tức!", inline=False)
        dm_embed.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
        await send_dm_notification(self.target_member, dm_embed)

        # Thông báo trong kênh chat riêng
        if self.clan.get("text_channel_id"):
            ch = guild.get_channel(int(self.clan["text_channel_id"]))
            if ch:
                embed = discord.Embed(
                    title="👢 THÀNH VIÊN BỊ TRỤC XUẤT",
                    description=f"<@{self.target_member.id}> đã bị trục xuất khỏi băng bởi <@{interaction.user.id}>.\n💬 **Lý do:** {reason}",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                await ch.send(embed=embed)

        await interaction.followup.send(f"✅ Đã trục xuất <@{self.target_member.id}> thành công và gửi thông báo lý do qua DM!", ephemeral=True)


class KickSelectDropdown(ui.Select):
    def __init__(self, clan: Dict[str, Any], eligible_members: List[Dict[str, Any]], guild: discord.Guild, bot):
        self.clan = clan
        self.bot = bot
        options = []
        for m in eligible_members[:25]:
            uid = int(m["user_id"])
            d_mem = guild.get_member(uid)
            d_name = d_mem.display_name if d_mem else f"User {uid}"
            r_name = RANK_NAMES.get(m["rank"], m["rank"])
            options.append(
                discord.SelectOption(
                    label=f"{d_name} ({r_name})"[:100],
                    value=str(uid),
                    description=f"Điểm cống hiến: {m.get('contribution_points', 0)}"[:100],
                    emoji="👢"
                )
            )
        super().__init__(placeholder="Chọn thành viên muốn trục xuất...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        target_uid = int(self.values[0])
        member = interaction.guild.get_member(target_uid)
        if not member:
            try:
                member = await interaction.guild.fetch_member(target_uid)
            except Exception:
                member = None
        if not member:
            await interaction.response.send_message("❌ Không tìm thấy thành viên trong máy chủ Discord!", ephemeral=True)
            return

        modal = KickMemberModal(target_member=member, clan=self.clan, bot=self.bot)
        await interaction.response.send_modal(modal)


class KickSelectView(SafeView):
    def __init__(self, clan: Dict[str, Any], eligible_members: List[Dict[str, Any]], guild: discord.Guild, bot):
        super().__init__(timeout=120)
        self.add_item(KickSelectDropdown(clan, eligible_members, guild, bot))


class PromoteSelectDropdown(ui.Select):
    def __init__(self, clan: Dict[str, Any], eligible_members: List[Dict[str, Any]], guild: discord.Guild, bot):
        self.clan = clan
        self.bot = bot
        options = []
        for m in eligible_members[:25]:
            uid = int(m["user_id"])
            d_mem = guild.get_member(uid)
            d_name = d_mem.display_name if d_mem else f"User {uid}"
            r_name = RANK_NAMES.get(m["rank"], m["rank"])
            next_rank = RANK_NAMES.get(Ranks.OFFICER if m["rank"] == Ranks.MEMBER else Ranks.CO_LEADER)
            options.append(
                discord.SelectOption(
                    label=f"{d_name} ({r_name})"[:100],
                    value=str(uid),
                    description=f"Thăng lên: {next_rank}"[:100],
                    emoji="⬆️"
                )
            )
        super().__init__(placeholder="Chọn thành viên muốn thăng chức...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        target_uid = int(self.values[0])
        guild = interaction.guild
        target_rec = await self.bot.db.get_clan_by_member(guild.id, target_uid)
        if not target_rec or target_rec["clan_id"] != self.clan["clan_id"]:
            await interaction.followup.send("❌ Thành viên này không còn ở trong băng!", ephemeral=True)
            return

        actor_rec = await self.bot.db.get_clan_by_member(guild.id, interaction.user.id)
        new_rank = None
        if target_rec["rank"] == Ranks.MEMBER:
            officer_count = await self.bot.db.get_rank_count(self.clan["clan_id"], Ranks.OFFICER)
            if officer_count >= RANK_LIMITS[Ranks.OFFICER]:
                await interaction.followup.send(f"❌ Băng đã đạt tối đa **{RANK_LIMITS[Ranks.OFFICER]}** Cán Bộ! Hãy giáng chức bớt trước.", ephemeral=True)
                return
            new_rank = Ranks.OFFICER
        elif target_rec["rank"] == Ranks.OFFICER:
            if actor_rec["rank"] != Ranks.LEADER and not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ Chỉ có Chủ Băng mới có quyền bổ nhiệm Phó Băng!", ephemeral=True)
                return
            co_count = await self.bot.db.get_rank_count(self.clan["clan_id"], Ranks.CO_LEADER)
            if co_count >= RANK_LIMITS[Ranks.CO_LEADER]:
                await interaction.followup.send(f"❌ Băng đã đạt tối đa **{RANK_LIMITS[Ranks.CO_LEADER]}** Phó Băng!", ephemeral=True)
                return
            new_rank = Ranks.CO_LEADER
        else:
            await interaction.followup.send("❌ Thành viên này đã ở cấp bậc cao nhất có thể thăng chức!", ephemeral=True)
            return

        await self.bot.db.update_member_rank(guild.id, target_uid, new_rank)
        await self.bot.db.add_clan_log(
            clan_id=self.clan["clan_id"],
            actor_id=interaction.user.id,
            target_id=target_uid,
            action="PROMOTE",
            details=f"<@{interaction.user.id}> đã thăng chức cho <@{target_uid}> lên {RANK_NAMES[new_rank]}."
        )

        if self.clan.get("text_channel_id"):
            ch = guild.get_channel(int(self.clan["text_channel_id"]))
            if ch:
                embed = discord.Embed(
                    title="🎉 THĂNG CHỨC THÀNH VIÊN",
                    description=f"Chúc mừng <@{target_uid}> đã được thăng chức lên **{RANK_NAMES[new_rank]}** bởi <@{interaction.user.id}>!",
                    color=discord.Color.gold(),
                    timestamp=datetime.now()
                )
                await ch.send(embed=embed)

        # Gửi DM thông báo thăng chức cho thành viên
        target_mem = guild.get_member(target_uid)
        if target_mem:
            dm_promote = discord.Embed(
                title="⭐ BẠN ĐÃ ĐƯỢC THĂNG CHỨC!",
                description=f"Chúc mừng bạn! Bạn đã được <@{interaction.user.id}> thăng cấp lên chức vụ **{RANK_NAMES[new_rank]}** trong băng **[{self.clan['tag']}] {self.clan['name']}** tại máy chủ **{guild.name}**!",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            dm_promote.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
            await send_dm_notification(target_mem, dm_promote)

        await interaction.followup.send(f"🎉 Đã thăng chức cho <@{target_uid}> lên **{RANK_NAMES[new_rank]}** thành công!", ephemeral=True)


class PromoteSelectView(SafeView):
    def __init__(self, clan: Dict[str, Any], eligible_members: List[Dict[str, Any]], guild: discord.Guild, bot):
        super().__init__(timeout=120)
        self.add_item(PromoteSelectDropdown(clan, eligible_members, guild, bot))


class DemoteSelectDropdown(ui.Select):
    def __init__(self, clan: Dict[str, Any], eligible_members: List[Dict[str, Any]], guild: discord.Guild, bot):
        self.clan = clan
        self.bot = bot
        options = []
        for m in eligible_members[:25]:
            uid = int(m["user_id"])
            d_mem = guild.get_member(uid)
            d_name = d_mem.display_name if d_mem else f"User {uid}"
            r_name = RANK_NAMES.get(m["rank"], m["rank"])
            next_rank = RANK_NAMES.get(Ranks.OFFICER if m["rank"] == Ranks.CO_LEADER else Ranks.MEMBER)
            options.append(
                discord.SelectOption(
                    label=f"{d_name} ({r_name})"[:100],
                    value=str(uid),
                    description=f"Giáng xuống: {next_rank}"[:100],
                    emoji="⬇️"
                )
            )
        super().__init__(placeholder="Chọn cán bộ muốn giáng chức...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        target_uid = int(self.values[0])
        guild = interaction.guild
        target_rec = await self.bot.db.get_clan_by_member(guild.id, target_uid)
        if not target_rec or target_rec["clan_id"] != self.clan["clan_id"]:
            await interaction.followup.send("❌ Thành viên này không còn ở trong băng!", ephemeral=True)
            return

        actor_rec = await self.bot.db.get_clan_by_member(guild.id, interaction.user.id)
        if target_rec["rank"] == Ranks.CO_LEADER and actor_rec["rank"] != Ranks.LEADER and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Chỉ có Chủ Băng mới có quyền giáng chức Phó Băng!", ephemeral=True)
            return

        new_rank = None
        if target_rec["rank"] == Ranks.CO_LEADER:
            new_rank = Ranks.OFFICER
        elif target_rec["rank"] == Ranks.OFFICER:
            new_rank = Ranks.MEMBER
        else:
            await interaction.followup.send("❌ Thành viên này đã ở cấp bậc cơ bản, không thể giáng thêm!", ephemeral=True)
            return

        await self.bot.db.update_member_rank(guild.id, target_uid, new_rank)
        await self.bot.db.add_clan_log(
            clan_id=self.clan["clan_id"],
            actor_id=interaction.user.id,
            target_id=target_uid,
            action="DEMOTE",
            details=f"<@{interaction.user.id}> đã giáng chức <@{target_uid}> xuống {RANK_NAMES[new_rank]}."
        )

        if self.clan.get("text_channel_id"):
            ch = guild.get_channel(int(self.clan["text_channel_id"]))
            if ch:
                embed = discord.Embed(
                    title="📉 GIÁNG CHỨC THÀNH VIÊN",
                    description=f"<@{target_uid}> đã bị giáng chức xuống **{RANK_NAMES[new_rank]}** bởi <@{interaction.user.id}>.",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                await ch.send(embed=embed)

        # Gửi DM thông báo giáng chức cho thành viên
        target_mem = guild.get_member(target_uid)
        if target_mem:
            dm_demote = discord.Embed(
                title="⬇️ ĐIỀU CHỈNH CHỨC VỤ BĂNG ĐẢNG",
                description=f"Chức vụ của bạn trong băng **[{self.clan['tag']}] {self.clan['name']}** tại máy chủ **{guild.name}** đã được điều chỉnh thành **{RANK_NAMES[new_rank]}** bởi <@{interaction.user.id}>.",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            dm_demote.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
            await send_dm_notification(target_mem, dm_demote)

        await interaction.followup.send(f"📉 Đã giáng chức <@{target_uid}> xuống **{RANK_NAMES[new_rank]}** thành công!", ephemeral=True)


class DemoteSelectView(SafeView):
    def __init__(self, clan: Dict[str, Any], eligible_members: List[Dict[str, Any]], guild: discord.Guild, bot):
        super().__init__(timeout=120)
        self.add_item(DemoteSelectDropdown(clan, eligible_members, guild, bot))


class TransferLeaderSelectDropdown(ui.Select):
    def __init__(self, clan: Dict[str, Any], members: List[Dict[str, Any]], guild: discord.Guild, bot):
        self.clan = clan
        self.bot = bot
        options = []
        for m in members[:25]:
            uid = int(m["user_id"])
            if uid == int(clan["leader_id"]):
                continue
            d_mem = guild.get_member(uid)
            d_name = d_mem.display_name if d_mem else f"User {uid}"
            r_name = RANK_NAMES.get(m["rank"], m["rank"])
            options.append(
                discord.SelectOption(
                    label=f"{d_name} ({r_name})"[:100],
                    value=str(uid),
                    description=f"Điểm cống hiến: {m.get('contribution_points', 0)}"[:100],
                    emoji="👑"
                )
            )
        super().__init__(placeholder="Chọn người muốn trao quyền Chủ Băng...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        successor_id = int(self.values[0])
        view = TransferConfirmView(clan=self.clan, old_leader_id=interaction.user.id, new_leader_id=successor_id, bot=self.bot)
        embed = discord.Embed(
            title="⚠️ XÁC NHẬN CHUYỂN GIAO QUYỀN CHỦ BĂNG",
            description=(
                f"Bạn có chắc chắn muốn chuyển giao quyền **Chủ Băng (LEADER)** của **[{self.clan['tag']}] {self.clan['name']}** cho <@{successor_id}> không?\n\n"
                "👉 Sau khi chuyển giao, bạn sẽ trở thành **Phó Băng (CO-LEADER)**."
            ),
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class TransferLeaderSelectView(SafeView):
    def __init__(self, clan: Dict[str, Any], members: List[Dict[str, Any]], guild: discord.Guild, bot):
        super().__init__(timeout=120)
        self.add_item(TransferLeaderSelectDropdown(clan, members, guild, bot))


class MemberInviteUserSelect(ui.UserSelect):
    """Dropdown chọn người dùng Discord để gửi lời mời gia nhập băng"""
    def __init__(self, clan: Dict[str, Any], bot):
        self.clan = clan
        self.bot = bot
        super().__init__(placeholder="➕ Chọn người dùng trong server để mời vào băng...", min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        target_user: discord.Member = self.values[0]
        guild = interaction.guild
        inviter = interaction.user

        if target_user.bot:
            await interaction.followup.send("❌ Không thể mời Bot Discord vào băng!", ephemeral=True)
            return

        if target_user.id == inviter.id:
            await interaction.followup.send("❌ Bạn không thể tự mời chính mình!", ephemeral=True)
            return

        clan = await self.bot.db.get_clan_by_id(self.clan["clan_id"])
        cur_count = await self.bot.db.get_member_count(clan["clan_id"])
        if cur_count >= clan["max_members"]:
            await interaction.followup.send(f"❌ Băng đã đạt sĩ số tối đa ({cur_count}/{clan['max_members']})! Hãy nâng cấp Level băng để mở thêm slot.", ephemeral=True)
            return

        existing = await self.bot.db.get_clan_by_member(guild.id, target_user.id)
        if existing:
            await interaction.followup.send(f"❌ Người này đã tham gia băng **{existing['name']}** rồi!", ephemeral=True)
            return

        # Tạo request trong DB (15 phút)
        expires_at = int(time.time()) + (15 * 60)
        req_id = await self.bot.db.create_request(
            clan_id=clan["clan_id"],
            guild_id=guild.id,
            user_id=target_user.id,
            actor_id=inviter.id,
            request_type="INVITE",
            expire_minutes=15
        )

        embed = discord.Embed(
            title="💌 BẠN NHẬN ĐƯỢC LỜI MỜI GIA NHẬP BĂNG ĐẢNG",
            description=f"Chào {target_user.mention}!\nCán Bộ <@{inviter.id}> đã gửi lời mời bạn gia nhập băng **[{clan['tag']}] {clan['name']}** tại máy chủ **{guild.name}**!",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="🏰 Tên Băng", value=f"[{clan['tag']}] {clan['name']}", inline=True)
        embed.add_field(name="👑 Chủ Băng", value=f"<@{clan['leader_id']}>", inline=True)
        embed.add_field(name="⏳ Hạn Lời Mời", value=f"<t:{expires_at}:R>", inline=True)
        embed.add_field(name="📜 Khẩu Hiệu", value=clan.get("description") or "Chưa có khẩu hiệu.", inline=False)
        embed.set_footer(text=f"{guild.name} • Bấm nút bên dưới để Chấp Nhận hoặc Từ Chối", icon_url=guild.icon.url if guild.icon else None)

        view = RequestView(request_id=req_id, bot=self.bot, is_invite=True)
        sent_where = None
        msg = None

        # Ưu tiên gửi trực tiếp kèm nút bấm qua DM để người được mời bấm ngay (không bị kẹt kênh riêng)
        try:
            msg = await target_user.send(embed=embed, view=view)
            sent_where = "DM"
        except (discord.Forbidden, discord.HTTPException):
            # Nếu người dùng khóa DM, tìm kênh công khai mà họ có quyền xem (tuyệt đối không gửi vào kênh riêng của băng)
            private_ids = {
                int(x) for x in (clan.get("text_channel_id"), clan.get("log_channel_id")) if x
            }
            candidate_ch = None
            if interaction.channel and interaction.channel.id not in private_ids:
                perms = interaction.channel.permissions_for(target_user)
                bot_perms = interaction.channel.permissions_for(guild.me)
                if perms.view_channel and bot_perms.send_messages:
                    candidate_ch = interaction.channel

            if not candidate_ch:
                for ch in [guild.system_channel, *guild.text_channels]:
                    if ch and ch.id not in private_ids:
                        if ch.permissions_for(target_user).view_channel and ch.permissions_for(guild.me).send_messages:
                            candidate_ch = ch
                            break

            if candidate_ch:
                msg = await candidate_ch.send(content=target_user.mention, embed=embed, view=view)
                sent_where = f"<#{candidate_ch.id}>"

        if not msg:
            await self.bot.db.update_request_status(req_id, "EXPIRED")
            await interaction.followup.send(
                f"❌ Không thể gửi lời mời tới {target_user.mention} vì họ đã **khóa tin nhắn riêng (DM)** và không có kênh công khai phù hợp để nhận lời mời!",
                ephemeral=True
            )
            return

        await self.bot.db.update_request_message_id(req_id, msg.id)
        where_note = "qua tin nhắn riêng (DM)" if sent_where == "DM" else f"tại kênh {sent_where} (do người này khóa DM)"
        await interaction.followup.send(f"✅ Đã gửi lời mời tham gia băng tới {target_user.mention} {where_note} thành công!", ephemeral=True)


class ClanMemberManagementView(SafeView):
    """Trung Tâm Điều Khiển Quản Lý Thành Viên & Nhân Sự 1-Click"""
    def __init__(self, clan: Dict[str, Any], user: discord.Member, bot):
        super().__init__(timeout=600)
        self.clan = clan
        self.user = user
        self.bot = bot

        self.add_item(MemberInviteUserSelect(clan=clan, bot=bot))
        is_leader = int(clan["leader_id"]) == user.id
        if not is_leader:
            self.remove_item(self.transfer_btn)
            self.remove_item(self.disband_btn)

    @ui.button(label="Thăng Chức", emoji="⬆️", style=discord.ButtonStyle.success, row=1)
    async def promote_btn(self, interaction: discord.Interaction, button: ui.Button):
        members = await self.bot.db.get_clan_members(self.clan["clan_id"])
        is_leader = int(self.clan["leader_id"]) == interaction.user.id
        eligible = [
            m for m in members
            if m["rank"] == Ranks.MEMBER or (m["rank"] == Ranks.OFFICER and is_leader)
        ]
        if not eligible:
            await interaction.response.send_message("❌ Không có thành viên nào trong băng đủ điều kiện thăng chức!", ephemeral=True)
            return
        view = PromoteSelectView(clan=self.clan, eligible_members=eligible, guild=interaction.guild, bot=self.bot)
        await interaction.response.send_message("⬆️ **Chọn thành viên muốn thăng chức:**", view=view, ephemeral=True)

    @ui.button(label="Giáng Chức", emoji="⬇️", style=discord.ButtonStyle.secondary, row=1)
    async def demote_btn(self, interaction: discord.Interaction, button: ui.Button):
        members = await self.bot.db.get_clan_members(self.clan["clan_id"])
        is_leader = int(self.clan["leader_id"]) == interaction.user.id
        eligible = [
            m for m in members
            if (m["rank"] == Ranks.OFFICER) or (m["rank"] == Ranks.CO_LEADER and is_leader)
        ]
        if not eligible:
            await interaction.response.send_message("❌ Không có cán bộ nào trong băng để giáng chức!", ephemeral=True)
            return
        view = DemoteSelectView(clan=self.clan, eligible_members=eligible, guild=interaction.guild, bot=self.bot)
        await interaction.response.send_message("⬇️ **Chọn cán bộ muốn giáng chức:**", view=view, ephemeral=True)

    @ui.button(label="Trục Xuất", emoji="👢", style=discord.ButtonStyle.danger, row=1)
    async def kick_btn(self, interaction: discord.Interaction, button: ui.Button):
        members = await self.bot.db.get_clan_members(self.clan["clan_id"])
        is_leader = int(self.clan["leader_id"]) == interaction.user.id
        actor_rec = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        actor_rank = actor_rec.get("rank") if actor_rec else Ranks.MEMBER

        eligible = []
        for m in members:
            uid = int(m["user_id"])
            if uid == interaction.user.id or uid == int(self.clan["leader_id"]):
                continue
            if is_leader:
                eligible.append(m)
            elif actor_rank == Ranks.CO_LEADER and m["rank"] in (Ranks.OFFICER, Ranks.MEMBER):
                eligible.append(m)
            elif actor_rank == Ranks.OFFICER and m["rank"] == Ranks.MEMBER:
                eligible.append(m)

        if not eligible:
            await interaction.response.send_message("❌ Không có thành viên nào bạn có thẩm quyền trục xuất!", ephemeral=True)
            return

        view = KickSelectView(clan=self.clan, eligible_members=eligible, guild=interaction.guild, bot=self.bot)
        await interaction.response.send_message("👢 **Chọn thành viên muốn trục xuất khỏi băng:**", view=view, ephemeral=True)

    @ui.button(label="Đăng Tin Tuyển", emoji="📢", style=discord.ButtonStyle.primary, row=1)
    async def recruit_btn(self, interaction: discord.Interaction, button: ui.Button):
        cur_clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        cnt = await self.bot.db.get_member_count(cur_clan["clan_id"]) if cur_clan else 0
        err = validate_recruit_publisher(cur_clan, interaction.user, cnt)
        if err:
            await auto_dismiss_notice(interaction, content=err, delay=6)
            return
        await interaction.response.send_modal(RecruitPostModal(clan=cur_clan, bot=self.bot))

    @ui.button(label="Trao Danh Hiệu", emoji="🎖️", style=discord.ButtonStyle.primary, row=1)
    async def titles_mgmt_btn(self, interaction: discord.Interaction, button: ui.Button):
        cur_clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not cur_clan:
            await auto_dismiss_notice(interaction, content="❌ Bạn chưa tham gia băng nào!", delay=5)
            return
        is_leader = int(cur_clan["leader_id"]) == interaction.user.id
        is_officer = is_leader or cur_clan.get("rank") in (Ranks.CO_LEADER, Ranks.OFFICER)
        if not is_officer and not interaction.user.guild_permissions.administrator:
            await auto_dismiss_notice(interaction, content="❌ Chỉ Cán Bộ, Phó Băng hoặc Chủ Băng mới có quyền trao danh hiệu!", delay=5)
            return
        members = await self.bot.db.get_clan_members(cur_clan["clan_id"])
        if not members:
            await auto_dismiss_notice(interaction, content="❌ Băng chưa có thành viên!", delay=5)
            return
        view = ClanCustomTitleMemberSelectView(clan=cur_clan, members=members, guild=interaction.guild, bot=self.bot)
        await interaction.response.send_message("🎖️ **Chọn thành viên để trao hoặc chỉnh sửa danh hiệu nội bộ:**", view=view, ephemeral=True)

    @ui.button(label="Chuyển Quyền Chủ Băng", emoji="👑", style=discord.ButtonStyle.primary, row=2)
    async def transfer_btn(self, interaction: discord.Interaction, button: ui.Button):
        if int(self.clan["leader_id"]) != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Chỉ có Chủ Băng mới có quyền chuyển giao quyền lực!", ephemeral=True)
            return
        members = await self.bot.db.get_clan_members(self.clan["clan_id"])
        other_members = [m for m in members if int(m["user_id"]) != interaction.user.id]
        if not other_members:
            await interaction.response.send_message("❌ Băng chưa có thành viên khác để chuyển giao quyền Chủ Băng!", ephemeral=True)
            return
        view = TransferLeaderSelectView(clan=self.clan, members=other_members, guild=interaction.guild, bot=self.bot)
        await interaction.response.send_message("👑 **Chọn thành viên muốn trao quyền Chủ Băng:**", view=view, ephemeral=True)

    @ui.button(label="Giải Tán Băng", emoji="💥", style=discord.ButtonStyle.danger, row=2)
    async def disband_btn(self, interaction: discord.Interaction, button: ui.Button):
        if int(self.clan["leader_id"]) != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Chỉ có Chủ Băng mới có quyền giải tán băng!", ephemeral=True)
            return
        modal = DisbandClanModal(clan=self.clan, bot=self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, row=2)
    async def back_to_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, interaction.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=2)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


# =============================================================================
# ĐIỀU HƯỚNG TẠI CHỖ & TIỆN ÍCH QUAY LẠI HUB (IN-PLACE NAVIGATION HELPERS)
# =============================================================================

async def return_to_hub(interaction: discord.Interaction, user: Any, bot: Any):
    """Cập nhật trực tiếp tin nhắn hiện tại thành Clan Hub để tránh làm đầy chat"""
    if not interaction.response.is_done():
        await interaction.response.defer()

    clan = await bot.db.get_clan_by_member(interaction.guild_id, user.id)
    member_count = 0
    if clan:
        member_count = await bot.db.get_member_count(clan["clan_id"])
        desc = (
            f"Xin chào <@{user.id}>!\n\n"
            f"🏰 Băng đảng: **[{clan['tag']}] {clan['name']}**\n"
            f"🎖️ Chức vụ: **{RANK_NAMES.get(clan.get('rank'), clan.get('rank', 'Thành viên'))}**\n"
            f"⭐ Điểm cống hiến: **{clan.get('contribution_points', 0)}** • Chuỗi điểm danh: **{clan.get('checkin_streak', 0)} ngày**\n\n"
            "👉 *Bấm các nút bên dưới để thao tác nhanh bằng 1-click mà không cần nhớ lệnh:*"
        )
        color = discord.Color.gold()
    else:
        desc = (
            f"Xin chào <@{user.id}>!\n\n"
            "Bạn hiện **chưa gia nhập** băng đảng nào trong server.\n\n"
            "👉 *Bấm các nút bên dưới để xem danh sách băng đang mở tuyển hoặc tự lập băng mới:*"
        )
        color = discord.Color.blue()

    from utils.canvas import generate_clan_hub_image
    buf = await asyncio.to_thread(generate_clan_hub_image, clan, user.display_name, member_count)
    file = discord.File(fp=buf, filename="clan_hub.png")

    embed = discord.Embed(
        title="🎮 TRUNG TÂM ĐIỀU KHIỂN BĂNG ĐẢNG (CLAN HUB)",
        description=desc,
        color=color,
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_image(url="attachment://clan_hub.png")
    view = ClanHubView(user=user, clan=clan, bot=bot)
    await interaction.edit_original_response(content=None, embed=embed, attachments=[file], view=view)


class ClanQuestsView(SafeView):
    """View hiển thị Bảng Nhiệm Vụ Tuần hỗ trợ quay lại Hub và đóng bảng"""
    def __init__(self, clan: Dict[str, Any], user: Any, bot: Any):
        super().__init__(timeout=600)
        self.clan = clan
        self.user = user
        self.bot = bot

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, row=0)
    async def back_to_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, self.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=0)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


class ClanMilestonesView(SafeView):
    """View hiển thị Cột Mốc Lịch Sử hỗ trợ quay lại Hub và đóng bảng"""
    def __init__(self, clan: Dict[str, Any], user: Any, bot: Any):
        super().__init__(timeout=600)
        self.clan = clan
        self.user = user
        self.bot = bot

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, row=0)
    async def back_to_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, self.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=0)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


class ClanWallpaperView(SafeView):
    """View hiển thị Wallpaper Full HD hỗ trợ quay lại Hub và đóng bảng"""
    def __init__(self, clan: Dict[str, Any], user: Any, bot: Any):
        super().__init__(timeout=600)
        self.clan = clan
        self.user = user
        self.bot = bot

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, row=0)
    async def back_to_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, self.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=0)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


# =============================================================================
# TRUNG TÂM ĐIỀU KHIỂN BĂNG ĐẢNG (CLAN HUB)
# =============================================================================

class ClanHubView(SafeView):
    """Trung Tâm Điều Khiển Băng Đảng Tinh Gọn 1-Click"""
    def __init__(self, user: discord.Member, clan: Optional[Dict[str, Any]], bot):
        super().__init__(timeout=600)
        self.user = user
        self.clan = clan
        self.bot = bot

        if clan:
            self.remove_item(self.list_clans_btn)
            self.remove_item(self.create_clan_btn)
            self.remove_item(self.apply_hub_btn)
            is_leader = int(clan["leader_id"]) == user.id
            is_officer = is_leader or clan.get("rank") in (Ranks.CO_LEADER, Ranks.OFFICER)
            if not is_officer and not user.guild_permissions.administrator:
                self.remove_item(self.members_mgmt_btn)
                self.remove_item(self.recruit_hub_btn)
            if not is_leader and not user.guild_permissions.administrator:
                self.remove_item(self.manage_btn)
        else:
            self.remove_item(self.missions_hub_btn)
            self.remove_item(self.my_clan_btn)
            self.remove_item(self.pet_hub_btn)
            self.remove_item(self.party_hub_btn)
            self.remove_item(self.milestones_btn)
            self.remove_item(self.members_mgmt_btn)
            self.remove_item(self.recruit_hub_btn)
            self.remove_item(self.manage_btn)

    @ui.button(label="Nhiệm Vụ & Điểm Danh", emoji="🎯", style=discord.ButtonStyle.success, row=0)
    async def missions_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not self.clan:
            await auto_dismiss_notice(interaction, content="❌ Bạn chưa tham gia băng nào!", delay=5)
            return
        await interaction.response.defer()
        await _render_mission_hub(interaction, self.clan, self.bot, mode="daily")

    @ui.button(label="Hồ Sơ Băng Của Bạn", emoji="🏰", style=discord.ButtonStyle.primary, row=0)
    async def my_clan_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not clan:
            await auto_dismiss_notice(interaction, content="❌ Bạn chưa tham gia băng nào!", delay=5)
            return

        members = await self.bot.db.get_clan_members(clan["clan_id"])
        level_info = get_level_info(clan["exp"])
        embed, files = await build_clan_profile_payload(clan, members, level_info, interaction.guild)
        st_state = await self.bot.db.get_member_streak_nick_state(interaction.guild_id, interaction.user.id)
        streak_on = bool(st_state and int(st_state.get("streak_nick_enabled") or 0) == 1)
        view = ClanInfoView(clan_id=clan["clan_id"], can_apply=False, is_member=True, is_leader=(int(clan["leader_id"]) == interaction.user.id), bot=self.bot, streak_nick_enabled=streak_on)
        await interaction.edit_original_response(content=None, embed=embed, attachments=files, view=view)

    @ui.button(label="Linh Thú Băng", emoji="🐾", style=discord.ButtonStyle.primary, row=0)
    async def pet_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not self.clan:
            await auto_dismiss_notice(interaction, content="❌ Bạn chưa tham gia băng nào!", delay=5)
            return
        await interaction.response.defer()
        await open_clan_pet_screen(interaction, self.clan, self.bot, edit_original=True)

    @ui.button(label="Thách Đấu / Tạo Kèo", emoji="⚔️", style=discord.ButtonStyle.primary, row=0)
    async def party_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not self.clan:
            await auto_dismiss_notice(interaction, content="❌ Bạn chưa tham gia băng nào!", delay=5)
            return
        await interaction.response.defer()
        all_clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        other_clans = [c for c in all_clans if c["clan_id"] != self.clan["clan_id"]]
        embed = build_challenge_target_embed(other_clans)
        view = ClanChallengeTargetView(source_clan=self.clan, other_clans=other_clans, bot=self.bot)
        await interaction.edit_original_response(content=None, embed=embed, attachments=[], view=view)

    @ui.button(label="Bảng Xếp Hạng Server", emoji="🏆", style=discord.ButtonStyle.secondary, row=1)
    async def leaderboard_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        from utils.canvas import generate_leaderboard_image
        clans = await self.bot.db.get_leaderboard(interaction.guild_id, criteria="level", limit=10)
        buf = await asyncio.to_thread(generate_leaderboard_image, interaction.guild.name, clans, "level")
        file = discord.File(fp=buf, filename="leaderboard.png")
        embed = build_leaderboard_embed(interaction.guild.name, clans, criteria="level", attachment_filename="leaderboard.png")
        view = LeaderboardInteractiveView(guild_name=interaction.guild.name, bot=self.bot, initial_criteria="level")
        await interaction.edit_original_response(content=None, embed=embed, attachments=[file], view=view)

    @ui.button(label="Cột Mốc Lịch Sử", emoji="📜", style=discord.ButtonStyle.secondary, row=1)
    async def milestones_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        if not self.clan:
            await auto_dismiss_notice(interaction, content="❌ Bạn chưa tham gia băng nào!", delay=5)
            return
        from utils.embeds import build_milestones_embed
        milestones = await self.bot.db.get_clan_milestones(self.clan["clan_id"], limit=10)
        files = []
        logo_ref = await resolve_clan_logo(self.clan, files, fallback_to_default=True)
        embed = build_milestones_embed(self.clan, milestones, logo_filename=logo_ref)
        view = ClanMilestonesView(clan=self.clan, user=interaction.user, bot=self.bot)
        await interaction.edit_original_response(content=None, embed=embed, attachments=files, view=view)

    @ui.button(label="Quản Lý Thành Viên", emoji="👥", style=discord.ButtonStyle.primary, row=1)
    async def members_mgmt_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not self.clan:
            await auto_dismiss_notice(interaction, content="❌ Bạn chưa tham gia băng nào!", delay=5)
            return
        is_leader = int(self.clan["leader_id"]) == interaction.user.id
        is_officer = is_leader or self.clan.get("rank") in (Ranks.CO_LEADER, Ranks.OFFICER)
        if not is_officer and not interaction.user.guild_permissions.administrator:
            await auto_dismiss_notice(interaction, content="❌ Chỉ Cán Bộ hoặc Chủ Băng mới có quyền truy cập Quản Lý Thành Viên!", delay=5)
            return
        await interaction.response.defer()
        view = ClanMemberManagementView(clan=self.clan, user=interaction.user, bot=self.bot)
        await interaction.edit_original_response(content="👥 **BẢNG ĐIỀU KHIỂN QUẢN LÝ THÀNH VIÊN & NHÂN SỰ BĂNG:**", embed=None, attachments=[], view=view)

    @ui.button(label="Đăng Tin Tuyển", emoji="📢", style=discord.ButtonStyle.success, row=1)
    async def recruit_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        cur_clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        cnt = await self.bot.db.get_member_count(cur_clan["clan_id"]) if cur_clan else 0
        err = validate_recruit_publisher(cur_clan, interaction.user, cnt)
        if err:
            await auto_dismiss_notice(interaction, content=err, delay=6)
            return
        await interaction.response.send_modal(RecruitPostModal(clan=cur_clan, bot=self.bot))

    @ui.button(label="Cài Đặt Băng", emoji="⚙️", style=discord.ButtonStyle.secondary, row=1)
    async def manage_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not self.clan:
            return
        is_leader = int(self.clan["leader_id"]) == interaction.user.id
        if not is_leader and not interaction.user.guild_permissions.administrator:
            await auto_dismiss_notice(interaction, content="❌ Chỉ Chủ Băng hoặc Quản Trị Viên mới có quyền cài đặt băng!", delay=5)
            return
        await interaction.response.defer()
        view = SettingsDashboardView(clan=self.clan, bot=self.bot)
        await interaction.edit_original_response(content="⚙️ **BẢNG ĐIỀU KHIỂN CÀI ĐẶT BĂNG:**", embed=None, attachments=[], view=view)

    @ui.button(label="Xem Danh Sách Băng Mở Tuyển", emoji="📜", style=discord.ButtonStyle.primary, row=2)
    async def list_clans_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        from utils.embeds import build_clan_list_embed
        clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        embed = build_clan_list_embed(interaction.guild.name, clans)
        view = ClanListInteractiveView(clans=clans, bot=self.bot)
        await interaction.edit_original_response(content=None, embed=embed, attachments=[], view=view)

    @ui.button(label="Thành Lập Băng Mới", emoji="✨", style=discord.ButtonStyle.success, row=2)
    async def create_clan_btn(self, interaction: discord.Interaction, button: ui.Button):
        modal = CreateClanModal(bot=self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(label="Nộp Đơn Vào Băng", emoji="📩", style=discord.ButtonStyle.primary, row=2)
    async def apply_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        existing = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if existing:
            await auto_dismiss_notice(interaction, content=f"❌ Bạn đã là thành viên của băng **{existing['name']}** rồi!", delay=5)
            return

        clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        if not clans:
            await auto_dismiss_notice(interaction, content="❌ Máy chủ hiện chưa có băng nào đang hoạt động!", delay=5)
            return

        if len(clans) == 1:
            clan = await self.bot.db.get_clan_by_id(clans[0]["clan_id"])
            if not clan:
                await auto_dismiss_notice(interaction, content="❌ Băng không tồn tại hoặc vừa bị giải tán!", delay=5)
                return
            modal = ApplyClanModal(clan=clan, bot=self.bot)
            await interaction.response.send_modal(modal)
        else:
            view = QuickApplySelectView(clans=clans, bot=self.bot)
            await interaction.response.send_message("📩 **Hãy chọn băng bạn muốn nộp đơn gia nhập bên dưới:**", view=view, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item) -> None:
        logger.error(f"Lỗi tương tác trên ClanHubView ({item}): {error}", exc_info=True)
        await auto_dismiss_notice(interaction, content="❌ Đã xảy ra lỗi khi xử lý thao tác này! Vui lòng mở lại `/clan hub` hoặc thử lại sau.", delay=6)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=2)
    async def close_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


class RejectRequestModal(SafeModal):
    """Modal nhập lý do từ chối đơn gia nhập băng để gửi DM cho người nộp đơn"""
    def __init__(self, req_view: "RequestView", bot):
        super().__init__(title="❌ Từ Chối Đơn Xin Vào Băng")
        self.req_view = req_view
        self.bot = bot

        self.reason_input = ui.TextInput(
            label="Lý Do Từ Chối (Sẽ gửi DM cho người nộp)",
            placeholder="Chưa đủ điều kiện, băng tạm đầy slot, chưa phù hợp...",
            default="Chưa phù hợp ở thời điểm hiện tại",
            max_length=150,
            required=False
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value.strip() or "Chưa phù hợp ở thời điểm hiện tại"
        await self.req_view._handle_decision(interaction, "REJECTED", reason=reason)


class RequestView(SafeView):
    """View duyệt đơn hoặc phản hồi lời mời với điều kiện changes == 1 chống race condition"""
    def __init__(self, request_id: int, bot, is_invite: bool = False):
        super().__init__(timeout=None)
        self.request_id = request_id
        self.bot = bot
        self.is_invite = is_invite

        self.accept_btn.label = "Chấp Nhận Lời Mời" if is_invite else "Duyệt Đơn"
        self.reject_btn.label = "Từ Chối Lời Mời" if is_invite else "Từ Chối"

    @ui.button(label="Chấp Nhận", emoji="✅", style=discord.ButtonStyle.success, custom_id="req_accept_btn")
    async def accept_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle_decision(interaction, "ACCEPTED")

    @ui.button(label="Từ Chối", emoji="❌", style=discord.ButtonStyle.danger, custom_id="req_reject_btn")
    async def reject_btn(self, interaction: discord.Interaction, button: ui.Button):
        if self.is_invite:
            await self._handle_decision(interaction, "REJECTED")
        else:
            modal = RejectRequestModal(req_view=self, bot=self.bot)
            await interaction.response.send_modal(modal)

    async def _handle_decision(self, interaction: discord.Interaction, decision: str, reason: Optional[str] = None):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        req = await self.bot.db.get_request_by_id(self.request_id)
        if not req:
            await interaction.followup.send("❌ Yêu cầu này không còn tồn tại!", ephemeral=True)
            return

        if req["status"] != "PENDING":
            await interaction.followup.send(f"ℹ️ Yêu cầu này đã được xử lý trước đó với kết quả: **{req['status']}**!", ephemeral=True)
            return

        # Kiểm tra thẩm quyền người bấm
        if req["request_type"] == "INVITE":
            if interaction.user.id != int(req["user_id"]):
                await interaction.followup.send("❌ Lời mời này không dành cho bạn!", ephemeral=True)
                return
        else:
            # APPLY: Cần là Cán Bộ trở lên của băng
            mem = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
            if not mem or mem["clan_id"] != req["clan_id"]:
                await interaction.followup.send("❌ Bạn không thuộc băng này!", ephemeral=True)
                return
            if mem["rank"] not in (Ranks.LEADER, Ranks.CO_LEADER, Ranks.OFFICER) and not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ Chỉ Cán Bộ trở lên mới có quyền duyệt đơn!", ephemeral=True)
                return

        # Cập nhật trạng thái nguyên tử (WHERE status = 'PENDING')
        changes = await self.bot.db.update_request_status(self.request_id, decision)
        if changes != 1:
            await interaction.followup.send("⚠️ Yêu cầu này vừa được xử lý bởi một người khác hoặc đã hết hạn!", ephemeral=True)
            return

        clan = await self.bot.db.get_clan_by_id(req["clan_id"])
        guild = interaction.guild or self.bot.get_guild(int(req["guild_id"]))
        if not guild:
            await interaction.followup.send("❌ Không tìm thấy máy chủ của yêu cầu này!", ephemeral=True)
            return

        if decision == "ACCEPTED":
            existing_clan = await self.bot.db.get_clan_by_member(guild.id, int(req["user_id"]))
            if existing_clan:
                await interaction.followup.send(f"❌ Người này đã tham gia băng **{existing_clan['name']}** rồi!", ephemeral=True)
                return

            # Kiểm tra sĩ số
            count = await self.bot.db.get_member_count(clan["clan_id"])
            if count >= clan["max_members"]:
                await interaction.followup.send("❌ Băng đã đầy chỗ, không thể thêm thành viên!", ephemeral=True)
                return

            target_user = guild.get_member(int(req["user_id"]))
            if not target_user:
                try:
                    target_user = await guild.fetch_member(int(req["user_id"]))
                except Exception:
                    try:
                        target_user = await self.bot.fetch_user(int(req["user_id"]))
                    except Exception:
                        target_user = None

            if target_user and isinstance(target_user, discord.Member):
                role = guild.get_role(int(clan["role_id"]))
                if role:
                    try:
                        await target_user.add_roles(role, reason="Duyệt vào băng")
                    except Exception as r_err:
                        logger.error(f"Lỗi khi thêm role cho thành viên: {r_err}")

            await self.bot.db.add_member(guild.id, int(req["user_id"]), clan["clan_id"], Ranks.MEMBER)
            await self.bot.db.add_clan_log(
                clan_id=clan["clan_id"],
                actor_id=interaction.user.id,
                target_id=int(req["user_id"]),
                action="JOIN",
                details=f"<@{req['user_id']}> gia nhập băng."
            )

            # Chào mừng trong kênh chat
            text_ch = guild.get_channel(int(clan["text_channel_id"]))
            if text_ch:
                welcome_embed = discord.Embed(
                    title="👋 THÀNH VIÊN MỚI GIA NHẬP!",
                    description=f"Nhiệt liệt chào mừng <@{req['user_id']}> đã chính thức trở thành thành viên của băng **{clan['name']}**!",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                welcome_view = WelcomeGreetingView(int(req["user_id"]))
                await text_ch.send(content=f"<@{req['user_id']}>", embed=welcome_embed, view=welcome_view)

            # Gửi DM thông báo duyệt đơn thành công cho người nộp đơn (hoặc thông báo cho người mời)
            if not self.is_invite and target_user:
                dm_accepted = discord.Embed(
                    title="🎉 ĐƠN GIA NHẬP BĂNG ĐÃ ĐƯỢC DUYỆT!",
                    description=f"Chúc mừng bạn! Đơn xin gia nhập băng **[{clan['tag']}] {clan['name']}** tại máy chủ **{guild.name}** đã được Cán Bộ <@{interaction.user.id}> phê duyệt thành công!",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                dm_accepted.add_field(name="🏰 Băng Đảng", value=f"[{clan['tag']}] {clan['name']}", inline=True)
                dm_accepted.add_field(name="👮 Người duyệt", value=f"<@{interaction.user.id}>", inline=True)
                dm_accepted.add_field(name="💬 Bắt đầu", value="Role băng đã được cấp cho bạn. Hãy vào kênh chat riêng của băng để giao lưu cùng mọi người ngay nhé!", inline=False)
                dm_accepted.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
                await send_dm_notification(target_user, dm_accepted)
            elif self.is_invite:
                inviter = guild.get_member(int(req["actor_id"])) or self.bot.get_user(int(req["actor_id"]))
                if inviter:
                    dm_inv_acc = discord.Embed(
                        title="✅ LỜI MỜI ĐÃ ĐƯỢC CHẤP NHẬN",
                        description=f"<@{req['user_id']}> đã chấp nhận lời mời gia nhập băng **[{clan['tag']}] {clan['name']}** của bạn!",
                        color=discord.Color.green(),
                        timestamp=datetime.now()
                    )
                    dm_inv_acc.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
                    await send_dm_notification(inviter, dm_inv_acc)

        elif decision == "REJECTED":
            if not self.is_invite:
                # Gửi DM từ chối đơn kèm lý do
                target_user = guild.get_member(int(req["user_id"]))
                if not target_user:
                    try:
                        target_user = await self.bot.fetch_user(int(req["user_id"]))
                    except Exception:
                        target_user = None
                if target_user:
                    reject_reason = reason or "Chưa phù hợp ở thời điểm hiện tại"
                    dm_reject = discord.Embed(
                        title="❌ THÔNG BÁO TỪ CHỐI ĐƠN VÀO BĂNG",
                        description=f"Rất tiếc, đơn xin gia nhập băng **[{clan['tag']}] {clan['name']}** tại máy chủ **{guild.name}** của bạn đã bị từ chối bởi Cán Bộ <@{interaction.user.id}>.",
                        color=discord.Color.red(),
                        timestamp=datetime.now()
                    )
                    dm_reject.add_field(name="💬 Lý do từ chối", value=reject_reason, inline=False)
                    dm_reject.add_field(name="✨ Lưu ý", value="Bạn không bị áp dụng thời gian chờ (cooldown) và có thể tự do nộp đơn vào các băng khác ngay lập tức!", inline=False)
                    dm_reject.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
                    await send_dm_notification(target_user, dm_reject)
            else:
                inviter = guild.get_member(int(req["actor_id"])) or self.bot.get_user(int(req["actor_id"]))
                if inviter:
                    dm_inv_rej = discord.Embed(
                        title="❌ LỜI MỜI ĐÃ BỊ TỪ CHỐI",
                        description=f"<@{req['user_id']}> đã từ chối lời mời gia nhập băng **[{clan['tag']}] {clan['name']}** của bạn.",
                        color=discord.Color.orange(),
                        timestamp=datetime.now()
                    )
                    dm_inv_rej.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
                    await send_dm_notification(inviter, dm_inv_rej)

        # Vô hiệu hóa nút trên tin nhắn gốc
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass

        if decision == "ACCEPTED":
            res_msg = f"🎉 Bạn đã gia nhập băng **[{clan['tag']}] {clan['name']}** thành công!" if self.is_invite else f"✅ Đã chấp nhận <@{req['user_id']}> vào băng **{clan['name']}**!"
        else:
            res_msg = f"❌ Bạn đã từ chối lời mời gia nhập băng **{clan['name']}**." if self.is_invite else f"❌ Đã từ chối yêu cầu của <@{req['user_id']}>."
        await interaction.followup.send(res_msg, ephemeral=True)


class PartyView(SafeView):
    """View điều khiển kèo Party LFG nội bộ"""
    def __init__(self, party_id: int, bot):
        super().__init__(timeout=None)
        self.party_id = party_id
        self.bot = bot

    @ui.button(label="Tham Gia", emoji="⚔️", style=discord.ButtonStyle.success, custom_id="party_join_btn")
    async def join_main(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle_party_action(interaction, "MAIN")

    @ui.button(label="Dự Bị", emoji="🛡️", style=discord.ButtonStyle.secondary, custom_id="party_reserve_btn")
    async def join_reserve(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle_party_action(interaction, "RESERVE")

    @ui.button(label="Rút Lui", emoji="🚪", style=discord.ButtonStyle.danger, custom_id="party_leave_btn")
    async def leave_party(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle_party_action(interaction, "LEAVE")

    @ui.button(label="Chốt / Đóng Kèo", emoji="🔒", style=discord.ButtonStyle.primary, custom_id="party_close_btn")
    async def close_party(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle_party_action(interaction, "CLOSE")

    async def _handle_party_action(self, interaction: discord.Interaction, action: str):
        party = await self.bot.db.get_party_by_id(self.party_id)
        if not party:
            await interaction.response.send_message("❌ Kèo không còn tồn tại!", ephemeral=True)
            return

        # Kiểm tra thành viên cùng băng
        user_clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not user_clan or user_clan["clan_id"] != party["clan_id"]:
            await interaction.response.send_message("❌ Bạn không thuộc băng này!", ephemeral=True)
            return

        if action == "CLOSE":
            # Chỉ Creator hoặc Cán Bộ+ mới được đóng
            is_creator = int(party["creator_id"]) == interaction.user.id
            is_officer = user_clan["rank"] in (Ranks.LEADER, Ranks.CO_LEADER, Ranks.OFFICER)
            if not is_creator and not is_officer and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ Chỉ người tạo kèo hoặc Cán Bộ trở lên mới có quyền Chốt / Đóng kèo!", ephemeral=True)
                return

            if party["status"] == "CLOSED":
                await interaction.response.send_message("ℹ️ Kèo này đã đóng trước đó rồi!", ephemeral=True)
                return

            await self.bot.db.update_party_status(self.party_id, "CLOSED")

            # Tiến độ nhiệm vụ tuần PARTY_COMPLETED
            week_key = get_current_week_key()
            quest_res = await self.bot.db.increment_quest_progress(party["clan_id"], week_key, "PARTY_COMPLETED", 1)
            if quest_res["completed_now"]:
                await self.bot.db.add_clan_exp(party["clan_id"], quest_res["reward_exp"], quest_res["reward_exp"])

            # Cập nhật view & embed
            participants = await self.bot.db.get_party_participants(self.party_id)
            main_users = [int(p["user_id"]) for p in participants if p["slot_type"] == "MAIN"]
            reserve_users = [int(p["user_id"]) for p in participants if p["slot_type"] == "RESERVE"]

            embed = build_party_embed(
                title=party["title"],
                creator_id=int(party["creator_id"]),
                max_slots=party["max_slots"],
                scheduled_at=party["scheduled_at"],
                main_users=main_users,
                reserve_users=reserve_users,
                status="CLOSED"
            )

            for item in self.children:
                item.disabled = True

            await interaction.response.edit_message(embed=embed, view=self)

            if main_users:
                pings = " ".join(f"<@{uid}>" for uid in main_users)
                await interaction.channel.send(f"🎮 **Kèo đã chốt:** {party['title']}!\nCác thành viên chính chuẩn bị vào trận: {pings}")
            return

        if party["status"] == "CLOSED":
            await interaction.response.send_message("❌ Kèo đã đóng, không thể thao tác thêm!", ephemeral=True)
            return

        user_id = interaction.user.id
        participants = await self.bot.db.get_party_participants(self.party_id)
        main_users = [int(p["user_id"]) for p in participants if p["slot_type"] == "MAIN"]

        if action == "MAIN":
            if user_id in main_users:
                await interaction.response.send_message("ℹ️ Bạn đã ở trong đội hình chính rồi!", ephemeral=True)
                return
            if len(main_users) >= party["max_slots"]:
                # Tự động đưa vào dự bị
                await self.bot.db.add_party_participant(self.party_id, user_id, "RESERVE")
                await interaction.response.send_message("⚠️ Đội hình chính đã đủ người! Bạn được chuyển vào danh sách **Dự Bị**.", ephemeral=True)
            else:
                await self.bot.db.add_party_participant(self.party_id, user_id, "MAIN")
                await interaction.response.send_message("✅ Bạn đã tham gia thành công vào **Đội Hình Chính**!", ephemeral=True)
        elif action == "RESERVE":
            await self.bot.db.add_party_participant(self.party_id, user_id, "RESERVE")
            await interaction.response.send_message("✅ Bạn đã đăng ký vào danh sách **Dự Bị** thành công!", ephemeral=True)
        elif action == "LEAVE":
            await self.bot.db.remove_party_participant(self.party_id, user_id)
            await interaction.response.send_message("👋 Bạn đã rút lui khỏi kèo chơi này.", ephemeral=True)

        # Cập nhật Embed trên tin nhắn
        updated_participants = await self.bot.db.get_party_participants(self.party_id)
        m_users = [int(p["user_id"]) for p in updated_participants if p["slot_type"] == "MAIN"]
        r_users = [int(p["user_id"]) for p in updated_participants if p["slot_type"] == "RESERVE"]

        new_embed = build_party_embed(
            title=party["title"],
            creator_id=int(party["creator_id"]),
            max_slots=party["max_slots"],
            scheduled_at=party["scheduled_at"],
            main_users=m_users,
            reserve_users=r_users,
            status=party["status"]
        )
        try:
            await interaction.message.edit(embed=new_embed)
        except Exception:
            pass


async def build_clan_profile_payload(
    clan: Dict[str, Any],
    members: List[Dict[str, Any]],
    level_info: Dict[str, Any],
    guild: Optional[discord.Guild]
) -> tuple[discord.Embed, list[discord.File]]:
    """Tạo Embed & file đính kèm cho Hồ Sơ Băng (ưu tiên hiển thị Banner đã upload nếu có, nếu chưa có thì hiển thị Thẻ Hồ Sơ Canvas)."""
    from utils.canvas import generate_clan_profile_image
    files: List[discord.File] = []
    leader_mem = guild.get_member(int(clan["leader_id"])) if (guild and clan.get("leader_id")) else None
    leader_name = leader_mem.display_name if leader_mem else None

    logo_ref = await resolve_clan_logo(clan, files, fallback_to_default=True)
    custom_banner_ref = await resolve_clan_banner(clan, files, member_count=len(members), leader_name=leader_name, fallback_to_default=False)

    if custom_banner_ref:
        embed = build_clan_info_embed(clan, members, level_info, attachment_filename=None, logo_filename=logo_ref, banner_filename=custom_banner_ref)
    else:
        buf = await asyncio.to_thread(generate_clan_profile_image, clan, len(members), level_info, leader_name)
        files.append(discord.File(fp=buf, filename="clan_profile.png"))
        embed = build_clan_info_embed(clan, members, level_info, attachment_filename="clan_profile.png", logo_filename=logo_ref)

    return embed, files


async def _build_banner_preview_payload(clan: Dict[str, Any], member_count: int, guild: Optional[discord.Guild]) -> tuple[discord.Embed, list[discord.File]]:
    """Tạo Embed & file đính kèm xem Banner (luôn kèm Logo tùy chỉnh/mặc định và Banner tùy chỉnh/mặc định)."""
    from utils.embeds import parse_hex_color
    files: List[discord.File] = []
    leader_mem = guild.get_member(int(clan["leader_id"])) if (guild and clan.get("leader_id")) else None
    leader_name = leader_mem.display_name if leader_mem else None

    logo_ref = await resolve_clan_logo(clan, files, fallback_to_default=True)
    banner_ref = await resolve_clan_banner(clan, files, member_count=member_count, leader_name=leader_name, fallback_to_default=True)

    is_custom_banner = bool(clan.get("banner_url")) and (banner_ref != "attachment://default_banner.png")
    if is_custom_banner:
        embed = discord.Embed(
            title=f"🚩 BANNER BĂNG: [{clan['tag']}] {clan['name']}",
            color=parse_hex_color(clan.get("color_hex")),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Banner chính thức của băng [{clan['tag']}] {clan['name']}")
    else:
        embed = discord.Embed(
            title=f"🚩 BANNER BĂNG ĐẢNG (MẶC ĐỊNH): [{clan['tag']}] {clan['name']}",
            description="✨ *Chủ băng chưa tải lên banner tùy chỉnh. Hệ thống đã tự động kiến tạo Banner đồ họa Hoàng Gia Gaming cực chất!*",
            color=parse_hex_color(clan.get("color_hex")),
            timestamp=datetime.now()
        )
        embed.set_footer(text="Đồ họa kiến tạo tự động bởi Hệ Thống Discord Bot Gaming")

    if banner_ref:
        embed.set_image(url=banner_ref)
    if logo_ref:
        embed.set_thumbnail(url=logo_ref)
    return embed, files


async def _build_image_settings_payload(clan: Dict[str, Any], guild: Optional[discord.Guild], db: Any) -> tuple[discord.Embed, list[discord.File]]:
    """Tạo Embed & danh sách file đính kèm (luôn chèn đồ họa mặc định hoặc ảnh local cho Logo & Banner)"""
    files: List[discord.File] = []
    member_count = await db.get_member_count(clan["clan_id"])
    leader_mem = guild.get_member(int(clan["leader_id"])) if (guild and clan.get("leader_id")) else None
    leader_name = leader_mem.display_name if leader_mem else None

    logo_ref = await resolve_clan_logo(clan, files, fallback_to_default=True)
    banner_ref = await resolve_clan_banner(clan, files, member_count=member_count, leader_name=leader_name, fallback_to_default=True)

    embed = build_image_settings_embed(
        clan,
        default_logo_filename=logo_ref,
        default_banner_filename=banner_ref
    )
    return embed, files


async def _build_role_setup_payload(clan: Dict[str, Any], role: Optional[discord.Role]) -> tuple[discord.Embed, list[discord.File]]:
    """Tạo Embed & file ảnh xem trước Role + Logo (hỗ trợ local:// và ảnh mặc định)."""
    from utils.canvas import generate_role_setup_image
    role_name = role.name if role else f"[{clan['tag']}] {clan['name']}"
    color_hex = clan.get("color_hex") or "#5865F2"
    sec_hex = clan.get("secondary_color_hex")
    hoist = role.hoist if role else True
    mentionable = role.mentionable if role else True

    buf = await asyncio.to_thread(generate_role_setup_image, clan, role_name, color_hex, sec_hex, hoist, mentionable)
    files: List[discord.File] = [discord.File(fp=buf, filename="role_setup.png")]
    logo_ref = await resolve_clan_logo(clan, files, fallback_to_default=True)
    embed = build_role_setup_embed(clan, role, attachment_filename="role_setup.png", logo_filename=logo_ref)
    return embed, files


class ClanImageUploadDashboardView(SafeView):
    """Bảng điều khiển trực quan quản lý và tải ảnh trực tiếp cho Logo & Banner Băng"""
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__(timeout=600)
        self.clan = clan
        self.bot = bot

    @ui.button(label="Gửi Tệp Logo", emoji="📤", style=discord.ButtonStyle.primary, row=0)
    async def upload_logo_btn(self, interaction: discord.Interaction, button: ui.Button):
        is_leader = int(self.clan["leader_id"]) == interaction.user.id
        is_officer = is_leader or self.clan.get("rank") in (Ranks.CO_LEADER, Ranks.OFFICER)
        if not is_officer and not interaction.user.guild_permissions.administrator:
            await auto_dismiss_notice(interaction, content="❌ Chỉ Cán Bộ, Phó Băng hoặc Chủ Băng mới có quyền tải ảnh!", delay=5)
            return
        await self._start_upload_listener(interaction, "logo")

    @ui.button(label="Gửi Tệp Banner", emoji="🎨", style=discord.ButtonStyle.primary, row=0)
    async def upload_banner_btn(self, interaction: discord.Interaction, button: ui.Button):
        is_leader = int(self.clan["leader_id"]) == interaction.user.id
        is_officer = is_leader or self.clan.get("rank") in (Ranks.CO_LEADER, Ranks.OFFICER)
        if not is_officer and not interaction.user.guild_permissions.administrator:
            await auto_dismiss_notice(interaction, content="❌ Chỉ Cán Bộ, Phó Băng hoặc Chủ Băng mới có quyền tải ảnh!", delay=5)
            return
        await self._start_upload_listener(interaction, "banner")

    @ui.button(label="Dán Link URL", emoji="🔗", style=discord.ButtonStyle.secondary, row=0)
    async def link_modal_btn(self, interaction: discord.Interaction, button: ui.Button):
        is_leader = int(self.clan["leader_id"]) == interaction.user.id
        is_officer = is_leader or self.clan.get("rank") in (Ranks.CO_LEADER, Ranks.OFFICER)
        if not is_officer and not interaction.user.guild_permissions.administrator:
            await auto_dismiss_notice(interaction, content="❌ Chỉ Cán Bộ, Phó Băng hoặc Chủ Băng mới có quyền thay đổi link ảnh!", delay=5)
            return
        modal = ImagesClanModal(clan=self.clan, bot=self.bot, parent_view=self)
        await interaction.response.send_modal(modal)

    @ui.button(label="Về Logo Mặc Định", emoji="🔄", style=discord.ButtonStyle.secondary, row=1)
    async def reset_logo_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        delete_local_asset(self.clan.get("logo_url"))
        await self.bot.db.update_clan(self.clan["clan_id"], logo_url=None)
        self.clan["logo_url"] = None
        await self.bot.db.add_clan_log(
            clan_id=self.clan["clan_id"],
            actor_id=interaction.user.id,
            action="RESET_LOGO",
            details="Đặt lại Logo về đồ họa Bát Giác Canvas mặc định."
        )
        new_embed, files = await _build_image_settings_payload(self.clan, interaction.guild, self.bot.db)
        await interaction.edit_original_response(embed=new_embed, attachments=files, view=self)
        await auto_dismiss_notice(interaction, content="✨ Đã chuyển về Logo Bát Giác Hoàng Gia Canvas mặc định!", delay=5)

    @ui.button(label="Về Banner Mặc Định", emoji="🔄", style=discord.ButtonStyle.secondary, row=1)
    async def reset_banner_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        delete_local_asset(self.clan.get("banner_url"))
        await self.bot.db.update_clan(self.clan["clan_id"], banner_url=None)
        self.clan["banner_url"] = None
        await self.bot.db.add_clan_log(
            clan_id=self.clan["clan_id"],
            actor_id=interaction.user.id,
            action="RESET_BANNER",
            details="Đặt lại Banner về đồ họa Cyber Gaming Canvas mặc định."
        )
        new_embed, files = await _build_image_settings_payload(self.clan, interaction.guild, self.bot.db)
        await interaction.edit_original_response(embed=new_embed, attachments=files, view=self)
        await auto_dismiss_notice(interaction, content="✨ Đã chuyển về Banner Cyber Gaming Canvas mặc định!", delay=5)

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, row=2)
    async def back_to_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, interaction.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=2)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)

    async def _start_upload_listener(self, interaction: discord.Interaction, image_type: str):
        label = "Logo Bát Giác" if image_type == "logo" else "Banner Băng"
        await interaction.response.defer()
        prompt_msg = await interaction.followup.send(
            f"📸 **BƯỚC TIẾP THEO — HÃY GỬI ẢNH {label.upper()} VÀO KHUNG CHAT!**\n"
            f"👉 Bạn chỉ cần **kéo thả hoặc bấm nút `+` gửi 1 tấm ảnh vào kênh này ngay bây giờ** *(như gửi ảnh bình thường, trong 15 phút)*.\n"
            f"*(Bot sẽ tự động nhận ảnh, thu hồi tin nhắn của bạn để giữ sạch phòng chat và cập nhật ngay cho Băng!)*",
            ephemeral=True,
            wait=True
        )

        def check(m: discord.Message):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id and len(m.attachments) > 0

        try:
            msg = await self.bot.wait_for("message", timeout=900.0, check=check)
        except asyncio.TimeoutError:
            try:
                await prompt_msg.edit(content="⏱️ **Hết thời gian chờ gửi ảnh (15 phút).** Bạn có thể bấm nút thử lại bất kỳ lúc nào!")
                await asyncio.sleep(5)
                await prompt_msg.delete()
            except Exception:
                pass
            return

        att = msg.attachments[0]
        content_type = att.content_type or ""
        valid_types = ("image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif")
        if not any(content_type.startswith(t) for t in valid_types) and not any(att.filename.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
            try:
                await msg.delete()
            except Exception:
                pass
            try:
                await prompt_msg.edit(content="❌ **Tệp bạn vừa gửi không phải hình ảnh hợp lệ (PNG, JPG, WEBP, GIF)!** Hãy thử lại nhé.")
                await asyncio.sleep(5)
                await prompt_msg.delete()
            except Exception:
                pass
            return

        # Tải và lưu ảnh bền vững vào thư mục data/clan_assets/ trước khi xóa tin nhắn của user
        try:
            saved_uri = await save_clan_attachment(self.clan["clan_id"], image_type, att)
        except Exception as save_err:
            try:
                await prompt_msg.edit(content=f"❌ **Không thể lưu ảnh:** `{save_err}`")
                await asyncio.sleep(5)
                await prompt_msg.delete()
            except Exception:
                pass
            return

        # Không tự ý xóa tin nhắn của user trong Discord; chỉ thả reaction xác nhận đã nhận ảnh
        try:
            await msg.add_reaction("✅")
        except Exception:
            pass

        # Cập nhật DB
        if image_type == "logo":
            await self.bot.db.update_clan(self.clan["clan_id"], logo_url=saved_uri)
            self.clan["logo_url"] = saved_uri
            action = "UPDATE_LOGO"
            details = "Tải lên ảnh Logo mới trực tiếp từ thiết bị."
        else:
            await self.bot.db.update_clan(self.clan["clan_id"], banner_url=saved_uri)
            self.clan["banner_url"] = saved_uri
            action = "UPDATE_BANNER"
            details = "Tải lên ảnh Banner mới trực tiếp từ thiết bị."

        await self.bot.db.add_clan_log(
            clan_id=self.clan["clan_id"],
            actor_id=interaction.user.id,
            action=action,
            details=details
        )

        # Cập nhật lại giao diện bảng cài đặt (luôn kèm ảnh mặc định nếu phần còn lại chưa upload)
        new_embed, files = await _build_image_settings_payload(self.clan, interaction.guild, self.bot.db)
        await interaction.edit_original_response(content=None, embed=new_embed, attachments=files, view=self)

        try:
            await prompt_msg.edit(content=f"🎉 **Đã tải lên và cập nhật {label} thành công!**")
            await asyncio.sleep(5)
            await prompt_msg.delete()
        except Exception:
            pass


class SettingsDashboardView(SafeView):
    """Bảng điều khiển Ephemeral cài đặt băng"""
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__(timeout=600)
        self.clan = clan
        self.bot = bot

    @ui.select(
        placeholder="⚙️ Chọn mục cài đặt bạn muốn chỉnh sửa...",
        options=[
            discord.SelectOption(label="Quản Lý Thành Viên & Nhân Sự", value="member_mgmt", emoji="👥", description="Mời người mới, thăng chức, giáng chức, trục xuất, chuyển quyền"),
            discord.SelectOption(label="Đổi Tên / Tag / Khẩu Hiệu", value="rename", emoji="✏️", description="Chỉnh sửa thông tin định danh (cooldown 7 ngày)"),
            discord.SelectOption(label="Cài Đặt Role Băng (Màu sắc, Tên, Hoist...)", value="role_setup", emoji="🛡️", description="Đổi màu, đổi tên, bật tách nhóm hoist hoặc chọn role server"),
            discord.SelectOption(label="Cập Nhật Logo & Banner", value="images", emoji="🖼️", description="Tải ảnh lên trực tiếp từ thiết bị hoặc dán link online"),
            discord.SelectOption(label="Chế Độ Tuyển Quân", value="join_mode", emoji="🚪", description="Mở Tự Do / Cần Duyệt / Chỉ Nhận Lời Mời"),
            discord.SelectOption(label="Giải Tán Băng Đảng", value="disband", emoji="💥", description="Giải tán băng vĩnh viễn (Chỉ Chủ Băng, bảo mật 2 lớp)")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: ui.Select):
        val = select.values[0]
        if val == "member_mgmt":
            await interaction.response.defer()
            view = ClanMemberManagementView(clan=self.clan, user=interaction.user, bot=self.bot)
            await interaction.edit_original_response(content="👥 **BẢNG QUẢN LÝ NHÂN SỰ & THÀNH VIÊN BĂNG:**", embed=None, attachments=[], view=view)
        elif val == "rename":
            modal = RenameClanModal(clan=self.clan, bot=self.bot)
            await interaction.response.send_modal(modal)
        elif val in ("color", "role_setup"):
            await interaction.response.defer()
            role = interaction.guild.get_role(int(self.clan["role_id"])) if self.clan.get("role_id") else None
            embed, files = await _build_role_setup_payload(self.clan, role)
            view = ClanRoleSetupView(clan=self.clan, bot=self.bot)
            await interaction.edit_original_response(content=None, embed=embed, attachments=files, view=view)
        elif val == "images":
            await interaction.response.defer()
            embed, files = await _build_image_settings_payload(self.clan, interaction.guild, self.bot.db)
            view = ClanImageUploadDashboardView(clan=self.clan, bot=self.bot)
            await interaction.edit_original_response(content=None, embed=embed, attachments=files, view=view)
        elif val == "join_mode":
            await interaction.response.defer()
            view = JoinModeSelectView(clan_id=self.clan["clan_id"], current_mode=self.clan["join_mode"], bot=self.bot)
            await interaction.edit_original_response(content="🚪 **CHỌN CHẾ ĐỘ TUYỂN QUÂN MỚI CHO BĂNG:**", embed=None, attachments=[], view=view)
        elif val == "disband":
            if int(self.clan["leader_id"]) != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ Chỉ có Chủ Băng mới có quyền giải tán băng!", ephemeral=True)
                return
            modal = DisbandClanModal(clan=self.clan, bot=self.bot)
            await interaction.response.send_modal(modal)

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, interaction.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=1)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


PRESET_COLORS = [
    ("🔴 Đỏ Ruby", "#E74C3C", "Màu đỏ rực rỡ nhiệt huyết"),
    ("🔵 Xanh Sapphire", "#3498DB", "Màu xanh dương điềm tĩnh"),
    ("🟢 Xanh Lục Bảo", "#2ECC71", "Màu xanh lá tươi mát"),
    ("🟡 Vàng Hoàng Kim", "#F1C40F", "Màu vàng quý phái đẳng cấp"),
    ("🟣 Tím Huyền Bí", "#9B59B6", "Màu tím ma mị bí ẩn"),
    ("🌸 Hồng Neon", "#E91E63", "Màu hồng nổi bật cá tính"),
    ("🟠 Cam Lửa", "#E67E22", "Màu cam bùng cháy năng động"),
    ("🌊 Xanh Biển Ngọc", "#1ABC9C", "Màu xanh ngọc bích êm dịu"),
    ("⚡ Vàng Chanh", "#FEE75C", "Màu vàng chanh chói sáng"),
    ("🖤 Đen Huyền Bí", "#2C2F33", "Màu đen thanh lịch mạnh mẽ"),
    ("⚪ Trắng Tinh Khôi", "#FFFFFF", "Màu trắng tinh khiết nổi bật"),
    ("🔷 Xanh Discord", "#5865F2", "Màu xanh truyền thống Discord"),
]

GRADIENT_PRESETS = [
    ("🌅 Sunset Fire", "#FF512F", "#DD2476", "Hoàng hôn Cam sang Hồng Ruby"),
    ("⚡ Cyberpunk Neon", "#00F2FE", "#4FACFE", "Xanh Cyan Neon Cyberpunk tương lai"),
    ("🔮 Magic Violet", "#7F00FF", "#E100FF", "Tím ma pháp huyền bí sang Hồng tím"),
    ("🌿 Emerald Forest", "#00B09B", "#96C93D", "Lục bảo xanh thẳm sang Xanh lục non"),
    ("🔥 Dragon Flame", "#F857A6", "#FF5858", "Lửa rồng đỏ hồng rực cháy"),
    ("👑 Golden Luxury", "#F7971E", "#FFD200", "Hoàng kim vương giả Vàng kim sang Hổ phách"),
    ("🌊 Deep Ocean", "#2193B0", "#6DD5ED", "Đại dương sâu thẳm Xanh thẫm sang Xanh ngọc"),
    ("🌌 Dark Phantom", "#232526", "#414345", "Bóng đêm hắc ám Đen xám kim loại"),
]


class ExistingRoleSelect(ui.RoleSelect):
    """Dropdown chọn 1 role có sẵn trên server làm Role Băng"""
    def __init__(self):
        super().__init__(
            placeholder="🔗 Chọn 1 Role có sẵn trong Server làm Role Băng...",
            min_values=1,
            max_values=1,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_role: discord.Role = self.values[0]
        view: "ClanRoleSetupView" = self.view
        guild = interaction.guild

        all_clans = await view.bot.db.get_all_clans_in_guild(guild.id)
        clan_members = await view.bot.db.get_clan_members(view.clan["clan_id"])
        err_msg = validate_linkable_role(guild, interaction.user, selected_role, view.clan, all_clans, clan_members)
        if err_msg:
            await auto_dismiss_notice(interaction, content=err_msg, delay=6)
            return

        hex_color = await link_role_to_clan(guild, view.clan, selected_role, interaction.user, view.bot.db)

        view.clan["role_id"] = str(selected_role.id)
        view.clan["color_hex"] = hex_color
        view.clan["secondary_color_hex"] = None

        new_embed, files = await _build_role_setup_payload(view.clan, selected_role)
        await interaction.edit_original_response(embed=new_embed, attachments=files, view=view)

        await auto_dismiss_notice(
            interaction,
            content=(
                f"✅ **Đã liên kết thành công Role mới cho Băng:** {selected_role.mention}!\n"
                f"• Toàn bộ quyền truy cập kênh riêng đã được chuyển giao cho Role mới.\n"
                f"• Role mới đã được tự động cấp cho các thành viên trong băng."
            ),
            delay=6
        )


class GradientPaletteSelect(ui.Select):
    """Dropdown chọn nhanh dải màu Gradient 2 màu từ bộ sưu tập đẹp mắt"""
    def __init__(self):
        options = [
            discord.SelectOption(label=label, value=f"{start}:{end}", description=desc)
            for label, start, end, desc in GRADIENT_PRESETS
        ]
        super().__init__(
            placeholder="🌈 Chọn Bộ Màu Gradient Sẵn (Yêu cầu Server Boost)...",
            options=options,
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        chosen_pair = self.values[0]
        start_hex, end_hex = chosen_pair.split(":")
        view: "ClanRoleSetupView" = self.view
        guild = interaction.guild

        role = guild.get_role(int(view.clan["role_id"])) if view.clan.get("role_id") else None
        if not role:
            await auto_dismiss_notice(interaction, content="❌ Không tìm thấy Role của băng trên máy chủ!", delay=5)
            return

        if role >= guild.me.top_role:
            await auto_dismiss_notice(
                interaction,
                content=(
                    f"⚠️ Role {role.mention} đang nằm cao hơn hoặc bằng Role của Bot!\n"
                    "Vui lòng vào **Server Settings -> Roles** kéo Role của Bot lên cao hơn."
                ),
                delay=6
            )
            return

        start_color = parse_hex_color(start_hex)
        end_color = parse_hex_color(end_hex)

        try:
            # Thử áp dụng màu Gradient 2 màu (secondary_color)
            await role.edit(
                color=start_color,
                secondary_color=end_color,
                reason=f"Chủ Băng đổi màu Gradient: {interaction.user.name}"
            )
            await view.bot.db.update_clan(
                view.clan["clan_id"],
                color_hex=start_hex,
                secondary_color_hex=end_hex
            )
            await view.bot.db.add_clan_log(
                clan_id=view.clan["clan_id"],
                actor_id=interaction.user.id,
                action="UPDATE_COLOR",
                details=f"Đổi màu Role sang Gradient {start_hex} ➔ {end_hex}."
            )
            view.clan["color_hex"] = start_hex
            view.clan["secondary_color_hex"] = end_hex

            new_embed, files = await _build_role_setup_payload(view.clan, role)
            await interaction.edit_original_response(embed=new_embed, attachments=files, view=view)

            await auto_dismiss_notice(
                interaction,
                content=(
                    f"🌈 **Đã áp dụng màu Gradient thành công!**\n"
                    f"• Dải màu: **{start_hex}** ➔ **{end_hex}**\n"
                    f"*(Màu gradient hiển thị chuyển sắc tuyệt đẹp trên danh sách thành viên!)*"
                ),
                delay=6
            )
        except (discord.HTTPException, discord.InvalidArgument) as err:
            logger.warning(f"Không thể áp dụng gradient (server có thể chưa đủ boost): {err}")
            # Fallback sang màu đơn sắc chính nếu server chưa đủ boost
            try:
                await role.edit(color=start_color, secondary_color=None, reason=f"Đổi màu Role đơn sắc (fallback): {interaction.user.name}")
                await view.bot.db.update_clan(view.clan["clan_id"], color_hex=start_hex, secondary_color_hex=None)
                view.clan["color_hex"] = start_hex
                view.clan["secondary_color_hex"] = None
                new_embed, files = await _build_role_setup_payload(view.clan, role)
                await interaction.edit_original_response(embed=new_embed, attachments=files, view=view)

                await auto_dismiss_notice(
                    interaction,
                    content=(
                        f"⚠️ **Server của bạn chưa mở tính năng màu Gradient 2 màu (Yêu cầu Server Boost)!**\n"
                        f"👉 Bot đã tự động áp dụng **màu đơn sắc chính {start_hex}** cho Role của bạn."
                    ),
                    delay=6
                )
            except Exception as fb_err:
                await auto_dismiss_notice(interaction, content=f"❌ Lỗi khi đổi màu role: `{fb_err}`", delay=5)
        except Exception as e:
            await auto_dismiss_notice(interaction, content=f"❌ Lỗi khi đổi màu role: `{e}`", delay=5)


class ColorPaletteSelect(ui.Select):
    """Dropdown chọn nhanh màu sắc từ bảng màu có sẵn"""
    def __init__(self):
        options = [
            discord.SelectOption(label=label, value=hex_code, description=desc)
            for label, hex_code, desc in PRESET_COLORS
        ]
        super().__init__(
            placeholder="🎨 Hoặc chọn nhanh màu từ Bảng Màu Đơn Sắc Có Sẵn...",
            options=options,
            row=2
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        chosen_hex = self.values[0]
        view: "ClanRoleSetupView" = self.view
        guild = interaction.guild

        role = guild.get_role(int(view.clan["role_id"])) if view.clan.get("role_id") else None
        if not role:
            await interaction.followup.send("❌ Không tìm thấy Role của băng trên máy chủ!", ephemeral=True)
            return

        if role >= guild.me.top_role:
            await interaction.followup.send(
                f"⚠️ Role {role.mention} đang nằm cao hơn hoặc bằng Role của Bot!\n"
                "Vui lòng vào **Server Settings -> Roles** kéo Role của Bot lên cao hơn.",
                ephemeral=True
            )
            return

        try:
            new_color = parse_hex_color(chosen_hex)
            await role.edit(color=new_color, secondary_color=None, reason=f"Chủ Băng đổi màu role: {interaction.user.name}")
            await view.bot.db.update_clan(view.clan["clan_id"], color_hex=chosen_hex, secondary_color_hex=None)
            await view.bot.db.add_clan_log(
                clan_id=view.clan["clan_id"],
                actor_id=interaction.user.id,
                action="UPDATE_COLOR",
                details=f"Đổi màu Role sang đơn sắc {chosen_hex}."
            )
            view.clan["color_hex"] = chosen_hex
            view.clan["secondary_color_hex"] = None

            new_embed, files = await _build_role_setup_payload(view.clan, role)
            await interaction.edit_original_response(embed=new_embed, attachments=files, view=view)

            await auto_dismiss_notice(interaction, content=f"🎨 Đã đổi màu Role thành công sang mã màu: **{chosen_hex}**!", delay=5)
        except discord.Forbidden:
            await interaction.followup.send("❌ Bot bị thiếu quyền `Manage Roles` để đổi màu role!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi đổi màu role: `{e}`", ephemeral=True)


class ClanRoleSetupView(SafeView):
    """Bảng điều khiển tương tác toàn diện cài đặt & tùy biến Role Băng"""
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__(timeout=600)
        self.clan = clan
        self.bot = bot

        self.add_item(ExistingRoleSelect())
        self.add_item(GradientPaletteSelect())
        self.add_item(ColorPaletteSelect())

    @ui.button(label="Nhập Màu Gradient", emoji="🌈", style=discord.ButtonStyle.success, row=3)
    async def custom_gradient_btn(self, interaction: discord.Interaction, button: ui.Button):
        modal = GradientColorModal(clan=self.clan, bot=self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(label="Nhập Màu Đơn", emoji="🎨", style=discord.ButtonStyle.primary, row=3)
    async def custom_hex_btn(self, interaction: discord.Interaction, button: ui.Button):
        modal = ColorClanModal(clan=self.clan, bot=self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(label="Đổi Tên Role", emoji="✏️", style=discord.ButtonStyle.secondary, row=3)
    async def rename_role_btn(self, interaction: discord.Interaction, button: ui.Button):
        modal = RoleNameModal(clan=self.clan, bot=self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(label="Tách Nhóm (Hoist)", emoji="📌", style=discord.ButtonStyle.secondary, row=4)
    async def toggle_hoist_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        role = interaction.guild.get_role(int(self.clan["role_id"])) if self.clan.get("role_id") else None
        if not role:
            await auto_dismiss_notice(interaction, content="❌ Không tìm thấy Role của băng trên server!", delay=5)
            return

        if role >= interaction.guild.me.top_role:
            await auto_dismiss_notice(interaction, content="⚠️ Role này nằm cao hơn hoặc bằng Role của Bot!", delay=5)
            return

        try:
            new_hoist = not role.hoist
            await role.edit(hoist=new_hoist, reason=f"Chủ Băng bật/tắt hoist: {interaction.user.name}")
            new_embed, files = await _build_role_setup_payload(self.clan, role)
            await interaction.edit_original_response(embed=new_embed, attachments=files, view=self)
            status_text = "**BẬT** (Hiển thị riêng trên danh sách thành viên)" if new_hoist else "**TẮT** (Gộp chung với nhóm thông thường)"
            await auto_dismiss_notice(interaction, content=f"📌 Đã chuyển trạng thái Tách nhóm (Hoist) sang: {status_text}!", delay=5)
        except Exception as e:
            await auto_dismiss_notice(interaction, content=f"❌ Lỗi khi đổi trạng thái Hoist: `{e}`", delay=5)

    @ui.button(label="Cho Phép Tag", emoji="🔔", style=discord.ButtonStyle.secondary, row=4)
    async def toggle_mention_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        role = interaction.guild.get_role(int(self.clan["role_id"])) if self.clan.get("role_id") else None
        if not role:
            await auto_dismiss_notice(interaction, content="❌ Không tìm thấy Role của băng trên server!", delay=5)
            return

        if role >= interaction.guild.me.top_role:
            await auto_dismiss_notice(interaction, content="⚠️ Role này nằm cao hơn hoặc bằng Role của Bot!", delay=5)
            return

        try:
            new_mention = not role.mentionable
            await role.edit(mentionable=new_mention, reason=f"Chủ Băng bật/tắt mention: {interaction.user.name}")
            new_embed, files = await _build_role_setup_payload(self.clan, role)
            await interaction.edit_original_response(embed=new_embed, attachments=files, view=self)
            status_text = "**BẬT** (Bất kỳ ai cũng có thể tag role này)" if new_mention else "**TẮT** (Chỉ ai có quyền đặc biệt mới tag được)"
            await auto_dismiss_notice(interaction, content=f"🔔 Đã chuyển trạng thái Cho phép Tag sang: {status_text}!", delay=5)
        except Exception as e:
            await auto_dismiss_notice(interaction, content=f"❌ Lỗi khi đổi trạng thái Cho phép Tag: `{e}`", delay=5)

    @ui.button(label="Tải Icon Role", emoji="🖼️", style=discord.ButtonStyle.primary, row=4)
    async def upload_icon_guide_btn(self, interaction: discord.Interaction, button: ui.Button):
        role = interaction.guild.get_role(int(self.clan["role_id"])) if self.clan.get("role_id") else None
        if not role:
            await auto_dismiss_notice(interaction, content="❌ Không tìm thấy Role của băng trên server!", delay=5)
            return
        if role >= interaction.guild.me.top_role:
            await auto_dismiss_notice(interaction, content="⚠️ Role này nằm cao hơn hoặc bằng Role của Bot!", delay=5)
            return

        await interaction.response.defer()
        prompt_msg = await interaction.followup.send(
            "🌟 **HÃY GỬI ẢNH ICON ROLE VÀO KHUNG CHAT (15 PHÚT)**\n"
            "👉 Bạn chỉ cần **gửi 1 ảnh vuông (PNG/JPG, dưới 256KB)** vào kênh này ngay bây giờ *(như gửi ảnh bình thường)*.\n"
            "*(Lưu ý: Discord yêu cầu máy chủ đạt **Boost Cấp 2** mới có thể gắn Icon cho Role)*",
            ephemeral=True,
            wait=True
        )

        def check(m: discord.Message):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id and len(m.attachments) > 0

        try:
            msg = await self.bot.wait_for("message", timeout=900.0, check=check)
        except asyncio.TimeoutError:
            try:
                await prompt_msg.edit(content="⏱️ **Hết thời gian chờ gửi ảnh Icon Role (15 phút).** Bạn có thể bấm nút thử lại bất kỳ lúc nào!")
                await asyncio.sleep(5)
                await prompt_msg.delete()
            except Exception:
                pass
            return

        att = msg.attachments[0]
        try:
            img_bytes = await att.read()
            await msg.add_reaction("✅")
        except Exception:
            img_bytes = await att.read()

        try:
            await role.edit(display_icon=img_bytes, reason=f"Chủ Băng tải Icon Role: {interaction.user.name}")
            new_embed, files = await _build_role_setup_payload(self.clan, role)
            await interaction.edit_original_response(embed=new_embed, attachments=files, view=self)
            await prompt_msg.edit(content="🌟 **Đã cập nhật Icon Role thành công!**")
        except discord.HTTPException:
            await prompt_msg.edit(content="⚠️ **Server của bạn chưa đạt Boost Cấp 2** nên Discord chưa cho phép gắn Icon Role!")
        except Exception as e:
            await prompt_msg.edit(content=f"❌ Lỗi khi cập nhật Icon Role: `{e}`")
        await asyncio.sleep(5)
        try:
            await prompt_msg.delete()
        except Exception:
            pass

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, row=4)
    async def back_to_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, interaction.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=4)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


class JoinModeSelectView(SafeView):
    """View chọn chế độ tuyển quân"""
    def __init__(self, clan_id: int, current_mode: str, bot):
        super().__init__(timeout=900)
        self.clan_id = clan_id
        self.bot = bot

        options = [
            discord.SelectOption(label="🟢 Mở Tự Do (OPEN)", value="OPEN", default=(current_mode == "OPEN"), description="Ai xin vào cũng được duyệt ngay lập tức"),
            discord.SelectOption(label="🟡 Cần Duyệt (APPROVAL - Mặc định)", value="APPROVAL", default=(current_mode == "APPROVAL"), description="Gửi đơn vào kênh riêng để cán bộ xem xét"),
            discord.SelectOption(label="🔒 Chỉ Nhận Lời Mời (INVITE_ONLY)", value="INVITE_ONLY", default=(current_mode == "INVITE_ONLY"), description="Khóa nộp đơn, chỉ cán bộ mời mới vào được")
        ]
        self.select_menu.options = options

    @ui.select(placeholder="Chọn chế độ tuyển...", row=0)
    async def select_menu(self, interaction: discord.Interaction, select: ui.Select):
        chosen = select.values[0]
        await self.bot.db.update_clan(self.clan_id, join_mode=chosen)
        await self.bot.db.add_clan_log(
            clan_id=self.clan_id,
            actor_id=interaction.user.id,
            action="UPDATE_JOIN_MODE",
            details=f"Đổi chế độ tuyển quân sang {chosen}."
        )
        for opt in self.select_menu.options:
            opt.default = (opt.value == chosen)
        await interaction.response.edit_message(view=self)
        await auto_dismiss_notice(interaction, content=f"✅ Đã đổi chế độ tuyển quân thành: **{chosen}**!", delay=5)

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, interaction.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=1)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


class MembersPaginationView(SafeView):
    """View phân trang và lọc thành viên"""
    def __init__(self, clan_id: int, current_page: int, total_pages: int, current_filter: str, bot):
        super().__init__(timeout=120)
        self.clan_id = clan_id
        self.current_page = current_page
        self.total_pages = total_pages
        self.current_filter = current_filter
        self.bot = bot

        self.prev_btn.disabled = current_page <= 1
        self.page_indicator.label = f"{current_page} / {total_pages}"
        self.next_btn.disabled = current_page >= total_pages

        options = [
            discord.SelectOption(label="Tất cả chức vụ", value="ALL", default=(current_filter == "ALL")),
            discord.SelectOption(label=f"👑 {Ranks.NAMES[Ranks.LEADER]}", value=Ranks.LEADER, default=(current_filter == Ranks.LEADER)),
            discord.SelectOption(label=f"⭐ {Ranks.NAMES[Ranks.CO_LEADER]}", value=Ranks.CO_LEADER, default=(current_filter == Ranks.CO_LEADER)),
            discord.SelectOption(label=f"🛡️ {Ranks.NAMES[Ranks.OFFICER]}", value=Ranks.OFFICER, default=(current_filter == Ranks.OFFICER)),
            discord.SelectOption(label=f"👤 {Ranks.NAMES[Ranks.MEMBER]}", value=Ranks.MEMBER, default=(current_filter == Ranks.MEMBER))
        ]
        self.rank_select.options = options

    @ui.select(placeholder="Lọc danh sách theo chức vụ...", row=0)
    async def rank_select(self, interaction: discord.Interaction, select: ui.Select):
        await interaction.response.defer()
        chosen = select.values[0]
        rank_filter = None if chosen == "ALL" else chosen
        clan = await self.bot.db.get_clan_by_id(self.clan_id)
        members = await self.bot.db.get_clan_members(self.clan_id, rank_filter=rank_filter)
        embed, total_pages = build_members_embed(clan, members, page=1, page_size=10, rank_filter=rank_filter)
        view = MembersPaginationView(self.clan_id, 1, total_pages, chosen, self.bot)
        await interaction.edit_original_response(embed=embed, view=view)

    @ui.button(label="Trang Trước", emoji="◀️", style=discord.ButtonStyle.secondary, row=1)
    async def prev_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._change_page(interaction, self.current_page - 1)

    @ui.button(label="1 / 1", style=discord.ButtonStyle.primary, disabled=True, row=1)
    async def page_indicator(self, interaction: discord.Interaction, button: ui.Button):
        pass

    @ui.button(label="Trang Sau", emoji="▶️", style=discord.ButtonStyle.secondary, row=1)
    async def next_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._change_page(interaction, self.current_page + 1)

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, interaction.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=1)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)

    async def _change_page(self, interaction: discord.Interaction, new_page: int):
        await interaction.response.defer()
        rank_filter = None if self.current_filter == "ALL" else self.current_filter
        clan = await self.bot.db.get_clan_by_id(self.clan_id)
        members = await self.bot.db.get_clan_members(self.clan_id, rank_filter=rank_filter)
        embed, total_pages = build_members_embed(clan, members, page=new_page, page_size=10, rank_filter=rank_filter)
        view = MembersPaginationView(self.clan_id, new_page, total_pages, self.current_filter, self.bot)
        await interaction.edit_original_response(embed=embed, view=view)


class LogsPaginationView(SafeView):
    """View phân trang nhật ký hoạt động"""
    def __init__(self, clan_id: int, current_page: int, total_pages: int, bot):
        super().__init__(timeout=120)
        self.clan_id = clan_id
        self.current_page = current_page
        self.total_pages = total_pages
        self.bot = bot

        self.prev_btn.disabled = current_page <= 1
        self.page_indicator.label = f"{current_page} / {total_pages}"
        self.next_btn.disabled = current_page >= total_pages

    @ui.button(label="Trước", emoji="◀️", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._change_page(interaction, self.current_page - 1)

    @ui.button(label="1 / 1", style=discord.ButtonStyle.primary, disabled=True)
    async def page_indicator(self, interaction: discord.Interaction, button: ui.Button):
        pass

    @ui.button(label="Sau", emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._change_page(interaction, self.current_page + 1)

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary)
    async def back_to_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, interaction.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)

    async def _change_page(self, interaction: discord.Interaction, new_page: int):
        await interaction.response.defer()
        clan = await self.bot.db.get_clan_by_id(self.clan_id)
        data = await self.bot.db.get_clan_logs(self.clan_id, page=new_page, page_size=10)
        embed = build_logs_embed(clan, data["logs"], page=new_page, total_pages=self.total_pages)
        view = LogsPaginationView(self.clan_id, new_page, self.total_pages, self.bot)
        await interaction.edit_original_response(embed=embed, view=view)


class TransferConfirmView(SafeView):
    """View xác nhận chuyển giao quyền Chủ Băng (15 phút)"""
    def __init__(self, clan: Dict[str, Any], old_leader_id: int, new_leader_id: int, bot):
        super().__init__(timeout=900)
        self.clan = clan
        self.old_leader_id = old_leader_id
        self.new_leader_id = new_leader_id
        self.bot = bot

    @ui.button(label="Xác Nhận Chuyển Giao", emoji="👑", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.old_leader_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Bạn không có quyền xác nhận hành động này!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await self.bot.db.transfer_leadership(self.clan["clan_id"], interaction.guild_id, self.old_leader_id, self.new_leader_id)
        await self.bot.db.add_clan_log(
            clan_id=self.clan["clan_id"],
            actor_id=self.old_leader_id,
            target_id=self.new_leader_id,
            action="TRANSFER_LEADER",
            details=f"<@{self.old_leader_id}> đã trao quyền Chủ Băng cho <@{self.new_leader_id}>."
        )

        # Thông báo vào kênh chat băng
        text_ch = interaction.guild.get_channel(int(self.clan["text_channel_id"]))
        if text_ch:
            embed = discord.Embed(
                title="👑 CHUYỂN GIAO QUYỀN LỰC BĂNG ĐẢNG",
                description=f"Chủ Băng cũ <@{self.old_leader_id}> đã chính thức trao quyền **Chủ Băng (LEADER)** cho <@{self.new_leader_id}>!",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            await text_ch.send(embed=embed)

        # Gửi DM thông báo quyền Chủ Băng cho người nhận
        new_leader_mem = interaction.guild.get_member(self.new_leader_id)
        if not new_leader_mem:
            try:
                new_leader_mem = await self.bot.fetch_user(self.new_leader_id)
            except Exception:
                new_leader_mem = None
        if new_leader_mem:
            dm_leader = discord.Embed(
                title="👑 BẠN ĐÃ TRỞ THÀNH CHỦ BĂNG!",
                description=f"<@{self.old_leader_id}> đã chính thức trao quyền **Chủ Băng (LEADER)** của băng **[{self.clan['tag']}] {self.clan['name']}** tại máy chủ **{interaction.guild.name}** cho bạn!",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            dm_leader.add_field(name="Trách nhiệm", value="Hãy dẫn dắt anh em phát triển băng đảng ngày một vững mạnh nhé!", inline=False)
            dm_leader.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
            await send_dm_notification(new_leader_mem, dm_leader)

        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
        await interaction.followup.send(f"👑 Bạn đã chuyển giao quyền Chủ Băng thành công cho <@{self.new_leader_id}>!", ephemeral=True)

    @ui.button(label="Hủy Bỏ", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ Đã hủy thao tác chuyển giao quyền Chủ Băng.", view=self)


class ForceDeleteConfirmView(SafeView):
    """View xác nhận 2 lớp cho lệnh /clan-admin force-delete"""
    def __init__(self, clan: Dict[str, Any], reason: str, bot):
        super().__init__(timeout=900)
        self.clan = clan
        self.reason = reason
        self.bot = bot

    @ui.button(label="Xác Nhận Xóa Bắt Buộc", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        clan = self.clan

        # 1. Xóa DB trước để tránh kích hoạt cảnh báo sai từ Gateway
        await self.bot.db.delete_clan(clan["clan_id"])

        # 2. Xóa các kênh
        for ch_key in ("text_channel_id", "log_channel_id", "voice_channel_id", "extra_voice_channel_id"):
            ch_id = clan.get(ch_key)
            if ch_id:
                ch = guild.get_channel(int(ch_id))
                if ch:
                    try:
                        await ch.delete(reason="Admin buộc xóa")
                    except Exception:
                        pass

        # 3. Xóa Role
        role_id = clan.get("role_id")
        if role_id:
            role = guild.get_role(int(role_id))
            if role:
                try:
                    await role.delete(reason="Admin buộc xóa")
                except Exception:
                    pass

        # Gửi log server
        cfg = await self.bot.db.get_guild_config(guild.id)
        if cfg and cfg.get("log_channel_id"):
            log_ch = guild.get_channel(int(cfg["log_channel_id"]))
            if log_ch:
                embed = discord.Embed(
                    title="🚨 Quản Trị Viên Buộc Xóa Băng (Force Delete)",
                    description=f"Admin <@{interaction.user.id}> đã xóa bắt buộc băng **[{clan['tag']}] {clan['name']}**.",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="Lý do", value=self.reason)
                await log_ch.send(embed=embed)

        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
        await interaction.followup.send(f"🚨 Đã xóa bắt buộc và dọn sạch băng **[{clan['tag']}] {clan['name']}**!", ephemeral=True)

    @ui.button(label="Hủy Bỏ", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ Đã hủy lệnh xóa bắt buộc.", view=self)


# =============================================================================
# PHÂN QUYỀN ROLE SỬ DỤNG BOT (DÀNH CHO CHỦ BOT - BOT OWNER)
# =============================================================================

class BotAccessRoleSelect(ui.RoleSelect):
    """Menu tìm & thêm nhiều Role được phép sử dụng bot trong server (gõ tên để tìm trong 190+ Role)."""
    def __init__(self):
        super().__init__(
            placeholder="🔍 Gõ tên Role để tìm & thêm (hỗ trợ 190+ Role)...",
            min_values=1,
            max_values=25,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view: "BotAccessControlView" = self.view
        valid_roles = [r for r in self.values if not r.is_default() and not r.managed]
        if not valid_roles:
            await auto_dismiss_notice(interaction, content="❌ Vui lòng chọn ít nhất 1 Role hợp lệ (không chọn `@everyone` hoặc Role của Bot)!", delay=5)
            return

        new_ids = [str(r.id) for r in valid_roles]
        merged_ids = list(dict.fromkeys([*view.role_ids, *new_ids]))
        await view.bot.db.set_bot_access_config(interaction.guild_id, mode="ROLES", role_ids=merged_ids)
        if hasattr(view.bot, "update_bot_access_cache"):
            view.bot.update_bot_access_cache(interaction.guild_id, "ROLES", merged_ids)
        view.mode = "ROLES"
        view.role_ids = merged_ids

        embed = build_bot_access_embed(interaction.guild.name, view.mode, view.role_ids)
        await interaction.edit_original_response(embed=embed, view=view)
        await auto_dismiss_notice(interaction, content=f"🎯 Đã thêm **{len(new_ids)} Role**! Tổng cộng hiện có **{len(merged_ids)} Role** được phép dùng bot.", delay=5)


class BotAccessRolePageSelect(ui.Select):
    """Dropdown hiển thị 25 Role của trang hiện tại để bật/tắt (toggle) quyền dùng bot."""
    def __init__(self, page_roles: List[discord.Role], allowed_ids: List[str], page: int, total_pages: int, total_roles: int):
        allowed_set = set(allowed_ids)
        options = []
        for r in page_roles[:25]:
            is_allowed = str(r.id) in allowed_set
            options.append(
                discord.SelectOption(
                    label=f"{'✅ ' if is_allowed else ''}{r.name}"[:100],
                    value=str(r.id),
                    description=f"{'Đang BẬT — Bấm để gỡ' if is_allowed else 'Đang TẮT — Bấm để thêm'} • {len(r.members)} thành viên"[:100],
                    emoji="✅" if is_allowed else "⬜"
                )
            )
        super().__init__(
            placeholder=f"📋 Trang {page}/{total_pages} ({total_roles} Role) — Chọn để Bật/Tắt Role...",
            options=options,
            min_values=1,
            max_values=len(options),
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view: "BotAccessRoleBrowserView" = self.view
        current_set = set(view.role_ids)
        toggled_on = 0
        toggled_off = 0
        for rid in self.values:
            if rid in current_set:
                current_set.remove(rid)
                toggled_off += 1
            else:
                current_set.add(rid)
                toggled_on += 1

        new_role_ids = [str(r.id) for r in view.all_roles if str(r.id) in current_set]
        new_mode = "ROLES" if new_role_ids else view.mode
        await view.bot.db.set_bot_access_config(interaction.guild_id, mode=new_mode, role_ids=new_role_ids)
        if hasattr(view.bot, "update_bot_access_cache"):
            view.bot.update_bot_access_cache(interaction.guild_id, new_mode, new_role_ids)

        new_view = BotAccessRoleBrowserView(
            guild=interaction.guild,
            mode=new_mode,
            role_ids=new_role_ids,
            page=view.page,
            bot=view.bot
        )
        embed = build_bot_access_embed(interaction.guild.name, new_mode, new_role_ids)
        await interaction.edit_original_response(embed=embed, view=new_view)
        await auto_dismiss_notice(
            interaction,
            content=f"✅ Đã cập nhật: **+{toggled_on} Role bật**, **-{toggled_off} Role tắt** (Tổng: **{len(new_role_ids)} Role**).",
            delay=5
        )


class BotAccessRoleBrowserView(SafeView):
    """Trình duyệt toàn bộ Role của Server theo từng trang (25 Role/trang, hỗ trợ 190-250 Role)."""
    def __init__(self, guild: discord.Guild, mode: str, role_ids: List[str], page: int, bot):
        super().__init__(timeout=600)
        self.guild = guild
        self.mode = mode
        self.role_ids = role_ids
        self.bot = bot

        self.all_roles = [r for r in reversed(guild.roles) if not r.is_default() and not r.managed]
        self.total_pages = max(1, (len(self.all_roles) + 24) // 25)
        self.page = max(1, min(page, self.total_pages))

        start = (self.page - 1) * 25
        page_roles = self.all_roles[start:start + 25]
        if page_roles:
            self.add_item(BotAccessRolePageSelect(page_roles, role_ids, self.page, self.total_pages, len(self.all_roles)))

        self.prev_btn.disabled = self.page <= 1
        self.page_indicator.label = f"{self.page} / {self.total_pages}"
        self.next_btn.disabled = self.page >= self.total_pages

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if hasattr(self.bot, "is_bot_owner") and await self.bot.is_bot_owner(interaction.user):
            return True
        await auto_dismiss_notice(interaction, content="🔒 Chỉ **Chủ Bot (Bot Owner)** mới có quyền thay đổi cài đặt này!", delay=5)
        return False

    async def _go_page(self, interaction: discord.Interaction, new_page: int):
        await interaction.response.defer()
        new_view = BotAccessRoleBrowserView(self.guild, self.mode, self.role_ids, new_page, self.bot)
        embed = build_bot_access_embed(self.guild.name, self.mode, self.role_ids)
        await interaction.edit_original_response(embed=embed, view=new_view)

    @ui.button(label="Trang Trước", emoji="◀️", style=discord.ButtonStyle.secondary, row=1)
    async def prev_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._go_page(interaction, self.page - 1)

    @ui.button(label="1 / 1", style=discord.ButtonStyle.primary, disabled=True, row=1)
    async def page_indicator(self, interaction: discord.Interaction, button: ui.Button):
        pass

    @ui.button(label="Trang Sau", emoji="▶️", style=discord.ButtonStyle.secondary, row=1)
    async def next_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._go_page(interaction, self.page + 1)

    @ui.button(label="Quay Lại", emoji="🔙", style=discord.ButtonStyle.secondary, row=1)
    async def back_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        main_view = BotAccessControlView(self.guild.name, self.mode, self.role_ids, self.bot)
        embed = build_bot_access_embed(self.guild.name, self.mode, self.role_ids)
        await interaction.edit_original_response(embed=embed, view=main_view)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=1)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


class BotAccessControlView(SafeView):
    """Bảng điều khiển Phân Quyền Sử Dụng Bot dành riêng cho Chủ Bot."""
    def __init__(self, guild_name: str, mode: str, role_ids: List[str], bot):
        super().__init__(timeout=600)
        self.guild_name = guild_name
        self.mode = mode
        self.role_ids = role_ids
        self.bot = bot
        self.add_item(BotAccessRoleSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if hasattr(self.bot, "is_bot_owner") and await self.bot.is_bot_owner(interaction.user):
            return True
        await auto_dismiss_notice(interaction, content="🔒 Chỉ **Chủ Bot (Bot Owner)** mới có quyền thay đổi cài đặt này!", delay=5)
        return False

    async def _set_mode(self, interaction: discord.Interaction, new_mode: str, notice_text: str):
        await interaction.response.defer()
        await self.bot.db.set_bot_access_config(interaction.guild_id, mode=new_mode, role_ids=self.role_ids)
        if hasattr(self.bot, "update_bot_access_cache"):
            self.bot.update_bot_access_cache(interaction.guild_id, new_mode, self.role_ids)
        self.mode = new_mode
        embed = build_bot_access_embed(self.guild_name, self.mode, self.role_ids)
        await interaction.edit_original_response(embed=embed, view=self)
        await auto_dismiss_notice(interaction, content=notice_text, delay=5)

    @ui.button(label="Duyệt Toàn Bộ Role", emoji="📋", style=discord.ButtonStyle.primary, row=1)
    async def browse_roles_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        browser_view = BotAccessRoleBrowserView(interaction.guild, self.mode, self.role_ids, page=1, bot=self.bot)
        embed = build_bot_access_embed(self.guild_name, self.mode, self.role_ids)
        await interaction.edit_original_response(embed=embed, view=browser_view)

    @ui.button(label="Bật Tất Cả (Mặc Định)", emoji="🟢", style=discord.ButtonStyle.success, row=1)
    async def enable_all_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._set_mode(interaction, "ALL", "🟢 Đã **BẬT TẤT CẢ** — Mọi thành viên trong server đều có thể sử dụng bot!")

    @ui.button(label="Tắt Tất Cả", emoji="🔴", style=discord.ButtonStyle.danger, row=1)
    async def disable_all_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._set_mode(interaction, "NONE", "🔴 Đã **TẮT TẤT CẢ** — Chỉ Chủ Bot mới có thể sử dụng bot trên máy chủ này!")

    @ui.button(label="Quản Lý & Buff (Chủ Bot)", emoji="👑", style=discord.ButtonStyle.primary, row=2)
    async def owner_panel_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        embed = await build_bot_owner_panel_embed(interaction.guild, clans, None, self.bot.db)
        view = BotOwnerSystemPanelView(interaction.guild, clans, selected_clan=None, mode=self.mode, role_ids=self.role_ids, bot=self.bot)
        await interaction.edit_original_response(embed=embed, view=view)

    @ui.button(label="Xóa Hết Role Đã Chọn", emoji="🧹", style=discord.ButtonStyle.secondary, row=2)
    async def clear_roles_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        self.role_ids = []
        await self.bot.db.set_bot_access_config(interaction.guild_id, mode=self.mode, role_ids=[])
        if hasattr(self.bot, "update_bot_access_cache"):
            self.bot.update_bot_access_cache(interaction.guild_id, self.mode, [])
        embed = build_bot_access_embed(self.guild_name, self.mode, self.role_ids)
        await interaction.edit_original_response(embed=embed, view=self)
        await auto_dismiss_notice(interaction, content="🧹 Đã xóa sạch danh sách Role đã chọn!", delay=5)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=2)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


# =============================================================================
# BẢNG QUẢN LÝ & BUFF TOÀN HỆ THỐNG DÀNH CHO CHỦ BOT (/bot-access)
# =============================================================================

async def build_bot_owner_panel_embed(
    guild: discord.Guild,
    clans: List[Dict[str, Any]],
    selected_clan: Optional[Dict[str, Any]],
    db: Any,
) -> discord.Embed:
    if not selected_clan:
        return discord.Embed(
            title=f"👑 BẢNG QUẢN LÝ & BUFF HỆ THỐNG — {guild.name}",
            description=(
                f"Hiện có **{len(clans)}** băng đảng đang hoạt động trong máy chủ.\n\n"
                "👉 Hãy **chọn một băng đảng** ở menu bên dưới để:\n"
                "• **⚡ Buff EXP Băng** (tự động lên cấp & mở slot)\n"
                "• **🐾 Đổi Loài Pet, Chọn Stage (1–5), Buff Pet EXP & Xu**\n"
                "• **🎁 Mở Full Tủ Đồ & Random Style** để test trực tiếp ảnh Pet\n"
                "• **✏️ Sửa Tên, Tag, Sĩ Số Tối Đa hoặc Đổi Role**\n"
                "• **🧹 Xóa Pet** hoặc **🗑️ Xóa Sạch Băng & Toàn Bộ Dữ Liệu**"
            ),
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )

    mem_count = await db.get_member_count(selected_clan["clan_id"])
    pet = await db.get_clan_pet(selected_clan["clan_id"])
    sp_name = PET_SPECIES.get(pet["species"], {}).get("name", pet["species"]) if pet else ""
    pet_txt = (
        f"🐾 **{pet['name']}** ({sp_name}) • Lv.**{pet['level']}** (Stage {pet['stage']})\n"
        f"┗ Pet EXP: **{pet['exp']:,}** • Xu: **{pet['pet_coins']:,}** 🪙 • No: **{pet['hunger']}%** • Vui: **{pet['mood']}%**"
        if pet else "_Chưa nhận Linh Thú (chọn Loài / Stage bên dưới để tạo & test ngay)_"
    )
    role_mention = f"<@&{selected_clan['role_id']}>" if selected_clan.get("role_id") else "_Không có_"
    embed = discord.Embed(
        title=f"👑 QUẢN LÝ BĂNG: [{selected_clan['tag']}] {selected_clan['name']}",
        description=f"📜 Khẩu hiệu: *{selected_clan.get('description') or 'Chưa có'}*",
        color=parse_hex_color(selected_clan.get("color_hex")),
        timestamp=datetime.now()
    )
    embed.add_field(name="👑 Chủ Băng", value=f"<@{selected_clan['leader_id']}>", inline=True)
    embed.add_field(name="📈 Cấp & EXP", value=f"Lv.**{selected_clan['level']}** (`{selected_clan['exp']:,}` EXP)", inline=True)
    embed.add_field(name="👥 Sĩ Số & Role", value=f"**{mem_count}/{selected_clan['max_members']}** • {role_mention}", inline=True)
    embed.add_field(name="🐾 Linh Thú & Quỹ Xu", value=pet_txt, inline=False)
    embed.set_footer(text="Chỉ Chủ Bot (Bot Owner) mới có quyền thao tác bảng này")
    return embed


async def build_owner_panel_message(
    guild: discord.Guild,
    clans: List[Dict[str, Any]],
    selected_clan: Optional[Dict[str, Any]],
    db: Any,
) -> Tuple[discord.Embed, List[discord.File]]:
    """Tạo Embed + ảnh Pet trực tiếp (nếu băng có Pet) cho bảng Chủ Bot."""
    embed = await build_bot_owner_panel_embed(guild, clans, selected_clan, db)
    files: List[discord.File] = []
    if selected_clan:
        pet = await db.get_clan_pet(selected_clan["clan_id"])
        if pet:
            from utils.pet_canvas import generate_clan_pet_image
            buf = await asyncio.to_thread(generate_clan_pet_image, pet, selected_clan)
            files.append(discord.File(buf, filename="owner_pet_preview.png"))
            embed.set_image(url="attachment://owner_pet_preview.png")
    return embed, files


class BotOwnerBuffClanModal(SafeModal, title="⚡ Buff / Điều Chỉnh EXP Băng"):
    def __init__(self, clan: Dict[str, Any], mode: str, role_ids: List[str], bot: Any):
        super().__init__()
        self.clan = clan
        self.mode = mode
        self.role_ids = role_ids
        self.bot = bot
        self.exp_input = ui.TextInput(
            label="Số EXP Băng Cộng/Trừ (VD: 1000 hoặc -500)",
            placeholder="Nhập số nguyên, ví dụ 2500",
            default="1000",
            max_length=12,
            required=True
        )
        self.add_item(self.exp_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            delta = int(self.exp_input.value.strip())
        except ValueError:
            await auto_dismiss_notice(interaction, content="❌ Vui lòng nhập số nguyên hợp lệ!", delay=5)
            return
        await interaction.response.defer()
        updated = await self.bot.db.owner_buff_clan_exp(self.clan["clan_id"], delta)
        clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        embed, files = await build_owner_panel_message(interaction.guild, clans, updated, self.bot.db)
        view = BotOwnerSystemPanelView(interaction.guild, clans, updated, self.mode, self.role_ids, self.bot)
        await interaction.edit_original_response(embed=embed, view=view, attachments=files)
        await auto_dismiss_notice(interaction, content=f"⚡ Đã điều chỉnh **{delta:+,} EXP** cho băng **[{updated['tag']}] {updated['name']}** (Lv.{updated['level']})!", delay=5)


class BotOwnerBuffPetModal(SafeModal, title="🐾 Buff Pet EXP & Xu Linh Thú"):
    def __init__(self, clan: Dict[str, Any], mode: str, role_ids: List[str], bot: Any):
        super().__init__()
        self.clan = clan
        self.mode = mode
        self.role_ids = role_ids
        self.bot = bot
        self.pet_exp = ui.TextInput(label="Cộng/Trừ Pet EXP", default="500", max_length=12, required=True)
        self.pet_coins = ui.TextInput(label="Cộng/Trừ Xu Linh Thú", default="500", max_length=12, required=True)
        self.hunger_delta = ui.TextInput(label="Cộng Độ No (0-100)", default="100", max_length=6, required=False)
        self.mood_delta = ui.TextInput(label="Cộng Độ Vui (0-100)", default="100", max_length=6, required=False)
        self.add_item(self.pet_exp)
        self.add_item(self.pet_coins)
        self.add_item(self.hunger_delta)
        self.add_item(self.mood_delta)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            d_exp = int(self.pet_exp.value.strip() or "0")
            d_coins = int(self.pet_coins.value.strip() or "0")
            d_hun = int(self.hunger_delta.value.strip() or "0")
            d_mood = int(self.mood_delta.value.strip() or "0")
        except ValueError:
            await auto_dismiss_notice(interaction, content="❌ Giá trị nhập vào phải là số nguyên!", delay=5)
            return
        await interaction.response.defer()
        pet = await self.bot.db.get_clan_pet(self.clan["clan_id"])
        if not pet:
            pet = await self.bot.db.create_clan_pet(self.clan["clan_id"], "cyber_cat", "Bé Mèo Cyber")
        updated_pet = await self.bot.db.owner_buff_pet(self.clan["clan_id"], d_exp, d_coins, d_hun, d_mood)
        clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        clan_obj = await self.bot.db.get_clan_by_id(self.clan["clan_id"])
        embed, files = await build_owner_panel_message(interaction.guild, clans, clan_obj, self.bot.db)
        view = BotOwnerSystemPanelView(interaction.guild, clans, clan_obj, self.mode, self.role_ids, self.bot)
        await interaction.edit_original_response(embed=embed, view=view, attachments=files)
        await auto_dismiss_notice(
            interaction,
            content=f"🐾 Đã buff Pet **{updated_pet['name']}**: Lv.**{updated_pet['level']}** (Stage {updated_pet['stage']}), Xu: **{updated_pet['pet_coins']:,}** 🪙!",
            delay=6
        )


class BotOwnerEditClanModal(SafeModal, title="✏️ Chỉnh Sửa Thông Tin Băng"):
    def __init__(self, clan: Dict[str, Any], mode: str, role_ids: List[str], bot: Any):
        super().__init__()
        self.clan = clan
        self.mode = mode
        self.role_ids = role_ids
        self.bot = bot
        self.clan_name = ui.TextInput(label="Tên Băng Mới", default=clan["name"][:25], min_length=3, max_length=25, required=True)
        self.clan_tag = ui.TextInput(label="Tag Mới (2-5 ký tự)", default=clan["tag"][:5], min_length=2, max_length=5, required=True)
        self.clan_desc = ui.TextInput(label="Khẩu Hiệu", default=(clan.get("description") or "")[:100], max_length=100, required=False)
        self.max_mem = ui.TextInput(label="Sĩ Số Tối Đa", default=str(clan.get("max_members", 15)), max_length=4, required=True)
        self.add_item(self.clan_name)
        self.add_item(self.clan_tag)
        self.add_item(self.clan_desc)
        self.add_item(self.max_mem)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_max = max(1, min(500, int(self.max_mem.value.strip())))
        except ValueError:
            await auto_dismiss_notice(interaction, content="❌ Sĩ số tối đa phải là số nguyên!", delay=5)
            return
        await interaction.response.defer()
        new_name = self.clan_name.value.strip()
        new_tag = self.clan_tag.value.strip().upper()
        new_desc = self.clan_desc.value.strip()
        await self.bot.db.update_clan(
            self.clan["clan_id"],
            name=new_name,
            tag=new_tag,
            description=new_desc,
            max_members=new_max
        )
        role = interaction.guild.get_role(int(self.clan["role_id"])) if self.clan.get("role_id") else None
        if role:
            try:
                await role.edit(name=f"[{new_tag}] {new_name}", reason="Chủ Bot chỉnh sửa thông tin băng")
            except Exception:
                pass
        clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        updated = await self.bot.db.get_clan_by_id(self.clan["clan_id"])
        embed, files = await build_owner_panel_message(interaction.guild, clans, updated, self.bot.db)
        view = BotOwnerSystemPanelView(interaction.guild, clans, updated, self.mode, self.role_ids, self.bot)
        await interaction.edit_original_response(embed=embed, view=view, attachments=files)
        await auto_dismiss_notice(interaction, content=f"✅ Đã cập nhật thông tin băng **[{new_tag}] {new_name}**!", delay=5)


class BotOwnerDeleteClanConfirmView(SafeView):
    """Xác nhận xóa sạch băng đảng, Role, Kênh, Pet và toàn bộ dữ liệu liên quan."""
    def __init__(self, clan: Dict[str, Any], mode: str, role_ids: List[str], bot: Any):
        super().__init__(timeout=120)
        self.clan = clan
        self.mode = mode
        self.role_ids = role_ids
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return hasattr(self.bot, "is_bot_owner") and await self.bot.is_bot_owner(interaction.user)

    @ui.button(label="Xác Nhận Xóa Toàn Bộ", emoji="💥", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        guild = interaction.guild
        clan = self.clan
        await self.bot.db.delete_clan_pet(clan["clan_id"])
        await self.bot.db.delete_clan(clan["clan_id"])

        for ch_key in ("text_channel_id", "log_channel_id", "voice_channel_id", "extra_voice_channel_id"):
            ch_id = clan.get(ch_key)
            if ch_id:
                ch = guild.get_channel(int(ch_id))
                if ch:
                    try:
                        await ch.delete(reason="Chủ Bot xóa toàn bộ băng & dữ liệu")
                    except Exception:
                        pass
        if clan.get("role_id"):
            role = guild.get_role(int(clan["role_id"]))
            if role:
                try:
                    await role.delete(reason="Chủ Bot xóa toàn bộ băng & dữ liệu")
                except Exception:
                    pass
        from utils.pet_canvas import PET_CACHE_DIR
        for f in PET_CACHE_DIR.glob(f"{clan['clan_id']}_*.png"):
            try:
                f.unlink()
            except Exception:
                pass

        clans = await self.bot.db.get_all_clans_in_guild(guild.id)
        embed, files = await build_owner_panel_message(guild, clans, None, self.bot.db)
        view = BotOwnerSystemPanelView(guild, clans, None, self.mode, self.role_ids, self.bot)
        await interaction.edit_original_response(embed=embed, view=view, attachments=files)
        await auto_dismiss_notice(interaction, content=f"💥 Đã xóa sạch băng **[{clan['tag']}] {clan['name']}**, Role, Kênh và toàn bộ Pet!", delay=6)

    @ui.button(label="Hủy Bỏ", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        embed, files = await build_owner_panel_message(interaction.guild, clans, self.clan, self.bot.db)
        view = BotOwnerSystemPanelView(interaction.guild, clans, self.clan, self.mode, self.role_ids, self.bot)
        await interaction.edit_original_response(embed=embed, view=view, attachments=files)


class BotOwnerSystemPanelView(SafeView):
    """Bảng quản lý, chỉnh sửa, xóa băng/Pet/Role và Buff/Test nhanh dành riêng cho Chủ Bot."""
    def __init__(
        self,
        guild: discord.Guild,
        clans: List[Dict[str, Any]],
        selected_clan: Optional[Dict[str, Any]],
        mode: str,
        role_ids: List[str],
        bot: Any,
        pending_species: Optional[str] = None,
        pending_stage: Optional[int] = None,
    ):
        super().__init__(timeout=600)
        self.guild = guild
        self.clans_map = {str(c["clan_id"]): c for c in clans}
        self.selected_clan = selected_clan
        self.mode = mode
        self.role_ids = role_ids
        self.bot = bot
        self.pending_species = pending_species
        self.pending_stage = pending_stage

        opts = [
            discord.SelectOption(
                label=f"[{c['tag']}] {c['name']} (Lv.{c.get('level', 1)})"[:100],
                value=str(c["clan_id"]),
                default=(selected_clan is not None and str(c["clan_id"]) == str(selected_clan["clan_id"])),
                description=f"EXP: {c.get('exp', 0):,} • Chủ băng ID: {c['leader_id']}"[:100]
            )
            for c in clans[:25]
        ]
        if not opts:
            opts.append(discord.SelectOption(label="Chưa có băng nào trong server", value="NONE"))
            self.clan_select.disabled = True
        self.clan_select.options = opts

        self.species_select.options = [
            discord.SelectOption(
                label=f"{sp_info['name']} ({sp_id})",
                value=sp_id,
                emoji=sp_info.get("emoji"),
                default=(pending_species == sp_id),
                description=sp_info.get("desc", "")[:100],
            )
            for sp_id, sp_info in PET_SPECIES.items()
        ]
        self.stage_select.options = [
            discord.SelectOption(
                label=f"Stage {st['stage']}: {st['name']} (Lv.{st['min_level']}+)",
                value=str(st["stage"]),
                default=(pending_stage == st["stage"]),
                description=st.get("perk", "")[:100],
            )
            for st in PET_STAGES
        ]

        if not selected_clan:
            for item in (
                self.species_select,
                self.stage_select,
                self.apply_pet_btn,
                self.buff_clan_btn,
                self.buff_pet_btn,
                self.unlock_all_items_btn,
                self.random_style_btn,
                self.edit_clan_btn,
                self.delete_pet_btn,
                self.delete_clan_btn,
            ):
                self.remove_item(item)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if hasattr(self.bot, "is_bot_owner") and await self.bot.is_bot_owner(interaction.user):
            return True
        await auto_dismiss_notice(interaction, content="🔒 Chỉ **Chủ Bot** mới có quyền sử dụng bảng này!", delay=5)
        return False

    @ui.select(placeholder="🏰 Chọn Băng Đảng muốn quản lý / buff...", row=0)
    async def clan_select(self, interaction: discord.Interaction, select: ui.Select):
        val = select.values[0]
        if val == "NONE":
            return
        await interaction.response.defer()
        clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        chosen = await self.bot.db.get_clan_by_id(int(val))
        pet = await self.bot.db.get_clan_pet(chosen["clan_id"]) if chosen else None
        p_sp = pet["species"] if pet else None
        p_st = pet["stage"] if pet else None
        embed, files = await build_owner_panel_message(interaction.guild, clans, chosen, self.bot.db)
        view = BotOwnerSystemPanelView(interaction.guild, clans, chosen, self.mode, self.role_ids, self.bot, p_sp, p_st)
        await interaction.edit_original_response(embed=embed, view=view, attachments=files)

    @ui.select(placeholder="🧬 1. Chọn Chủng Loài Pet (sau đó bấm Áp Dụng)...", row=1)
    async def species_select(self, interaction: discord.Interaction, select: ui.Select):
        self.pending_species = select.values[0]
        for opt in self.species_select.options:
            opt.default = (opt.value == self.pending_species)
        await interaction.response.edit_message(view=self)

    @ui.select(placeholder="🚀 2. Chọn Giai Đoạn Stage 1→5 (sau đó bấm Áp Dụng)...", row=2)
    async def stage_select(self, interaction: discord.Interaction, select: ui.Select):
        self.pending_stage = int(select.values[0])
        for opt in self.stage_select.options:
            opt.default = (opt.value == str(self.pending_stage))
        await interaction.response.edit_message(view=self)

    @ui.button(label="Áp Dụng Pet", emoji="✅", style=discord.ButtonStyle.success, row=3)
    async def apply_pet_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        pet = await self.bot.db.owner_set_pet_state(
            self.selected_clan["clan_id"],
            species=self.pending_species,
            stage=self.pending_stage,
        )
        clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        chosen = await self.bot.db.get_clan_by_id(self.selected_clan["clan_id"])
        embed, files = await build_owner_panel_message(interaction.guild, clans, chosen, self.bot.db)
        view = BotOwnerSystemPanelView(
            interaction.guild, clans, chosen, self.mode, self.role_ids, self.bot,
            pending_species=pet["species"], pending_stage=pet["stage"],
        )
        await interaction.edit_original_response(embed=embed, view=view, attachments=files)
        sp_name = PET_SPECIES.get(pet["species"], {}).get("name", pet["species"])
        await auto_dismiss_notice(interaction, content=f"✅ Đã áp dụng: **{sp_name}** • **Stage {pet['stage']} (Lv.{pet['level']})**!", delay=4)

    @ui.button(label="Buff EXP", emoji="⚡", style=discord.ButtonStyle.success, row=3)
    async def buff_clan_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(BotOwnerBuffClanModal(self.selected_clan, self.mode, self.role_ids, self.bot))

    @ui.button(label="Buff Pet & Xu", emoji="🐾", style=discord.ButtonStyle.success, row=3)
    async def buff_pet_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(BotOwnerBuffPetModal(self.selected_clan, self.mode, self.role_ids, self.bot))

    @ui.button(label="Full Tủ Đồ", emoji="🎁", style=discord.ButtonStyle.primary, row=3)
    async def unlock_all_items_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        all_ids = [item["item_id"] for item in PET_CATALOG]
        pet = await self.bot.db.owner_unlock_all_pet_items(self.selected_clan["clan_id"], all_ids, bonus_coins=10000)
        clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        chosen = await self.bot.db.get_clan_by_id(self.selected_clan["clan_id"])
        embed, files = await build_owner_panel_message(interaction.guild, clans, chosen, self.bot.db)
        view = BotOwnerSystemPanelView(interaction.guild, clans, chosen, self.mode, self.role_ids, self.bot, pet["species"], pet["stage"])
        await interaction.edit_original_response(embed=embed, view=view, attachments=files)
        await auto_dismiss_notice(interaction, content=f"🎁 Đã mở khóa toàn bộ **{len(all_ids)} món đồ** & tặng **+10,000 Xu** (Tổng: {pet['pet_coins']:,} 🪙)!", delay=5)

    @ui.button(label="Random Style", emoji="🎲", style=discord.ButtonStyle.primary, row=3)
    async def random_style_btn(self, interaction: discord.Interaction, button: ui.Button):
        import random
        await interaction.response.defer()
        pet = await self.bot.db.get_clan_pet(self.selected_clan["clan_id"])
        if not pet:
            pet = await self.bot.db.create_clan_pet(self.selected_clan["clan_id"], self.pending_species or "cyber_cat", "Bé Mèo Cyber")
        info = get_pet_level_info(int(pet.get("exp", 0)))
        unlocked_slots = info["unlocked_slots"]
        new_eq: Dict[str, str] = {}
        for slot in unlocked_slots:
            cands = [i["item_id"] for i in PET_CATALOG if i["slot"] == slot and i["min_stage"] <= info["stage"]]
            if cands:
                new_eq[slot] = random.choice(cands)
        updated_pet = await self.bot.db.owner_set_pet_state(self.selected_clan["clan_id"], equipped=new_eq)
        clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        chosen = await self.bot.db.get_clan_by_id(self.selected_clan["clan_id"])
        embed, files = await build_owner_panel_message(interaction.guild, clans, chosen, self.bot.db)
        view = BotOwnerSystemPanelView(interaction.guild, clans, chosen, self.mode, self.role_ids, self.bot, updated_pet["species"], updated_pet["stage"])
        await interaction.edit_original_response(embed=embed, view=view, attachments=files)
        await auto_dismiss_notice(interaction, content=f"🎲 Đã phối ngẫu nhiên **{len(new_eq)} món đồ** cho Stage {info['stage']}!", delay=4)

    @ui.button(label="Sửa Băng", emoji="✏️", style=discord.ButtonStyle.secondary, row=4)
    async def edit_clan_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(BotOwnerEditClanModal(self.selected_clan, self.mode, self.role_ids, self.bot))

    @ui.button(label="Xóa Pet", emoji="🧹", style=discord.ButtonStyle.danger, row=4)
    async def delete_pet_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        await self.bot.db.delete_clan_pet(self.selected_clan["clan_id"])
        from utils.pet_canvas import PET_CACHE_DIR
        for f in PET_CACHE_DIR.glob(f"{self.selected_clan['clan_id']}_*.png"):
            try:
                f.unlink()
            except Exception:
                pass
        clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        chosen = await self.bot.db.get_clan_by_id(self.selected_clan["clan_id"])
        embed, files = await build_owner_panel_message(interaction.guild, clans, chosen, self.bot.db)
        view = BotOwnerSystemPanelView(interaction.guild, clans, chosen, self.mode, self.role_ids, self.bot)
        await interaction.edit_original_response(embed=embed, view=view, attachments=files)
        await auto_dismiss_notice(interaction, content=f"🧹 Đã xóa toàn bộ dữ liệu Linh Thú của băng **[{chosen['tag']}] {chosen['name']}**!", delay=5)

    @ui.button(label="Xóa Băng", emoji="🗑️", style=discord.ButtonStyle.danger, row=4)
    async def delete_clan_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        embed = discord.Embed(
            title=f"⚠️ XÁC NHẬN XÓA TOÀN BỘ: [{self.selected_clan['tag']}] {self.selected_clan['name']}",
            description="Hành động này sẽ xóa **Role Discord**, **các Kênh của băng**, **Linh Thú**, **Tủ đồ Pet** và **toàn bộ dữ liệu** không thể khôi phục!",
            color=discord.Color.red()
        )
        view = BotOwnerDeleteClanConfirmView(self.selected_clan, self.mode, self.role_ids, self.bot)
        await interaction.edit_original_response(embed=embed, view=view, attachments=[])

    @ui.button(label="Phân Quyền", emoji="🔐", style=discord.ButtonStyle.secondary, row=4)
    async def back_access_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        embed = build_bot_access_embed(interaction.guild.name, self.mode, self.role_ids)
        view = BotAccessControlView(interaction.guild.name, self.mode, self.role_ids, bot=self.bot)
        await interaction.edit_original_response(embed=embed, view=view, attachments=[])


# =============================================================================
# TUYỂN THÀNH VIÊN CÔNG KHAI (CATEGORY BOT CLAN -> #tuyen-thanh-vien)
# =============================================================================

_RECRUIT_COOLDOWNS: Dict[int, float] = {}
RECRUIT_COOLDOWN_SECONDS = 600


def validate_recruit_publisher(clan: Optional[Dict[str, Any]], user: discord.Member, member_count: int) -> Optional[str]:
    """Kiểm tra toàn bộ điều kiện & ngoại lệ trước khi cho phép đăng tin tuyển thành viên."""
    if not clan:
        return "❌ Bạn chưa tham gia băng đảng nào nên không thể đăng tin tuyển thành viên! Hãy tạo băng (`/clan create`) hoặc gia nhập một băng trước."

    is_leader = int(clan["leader_id"]) == user.id
    rank = clan.get("rank")
    if not is_leader and rank not in (Ranks.CO_LEADER, Ranks.OFFICER) and not user.guild_permissions.administrator:
        return "❌ Chỉ **Chủ Băng**, **Phó Băng** hoặc **Cán Bộ** mới có quyền đăng tin tuyển thành viên!"

    max_members = int(clan.get("max_members", 15))
    if member_count >= max_members:
        return f"❌ Băng **[{clan['tag']}] {clan['name']}** đã đạt sĩ số tối đa (**{member_count}/{max_members}**)! Hãy nâng cấp Level băng hoặc dọn slot trước khi đăng tin tuyển."

    if clan.get("join_mode") == JoinModes.INVITE_ONLY:
        return (
            "🔒 Băng của bạn đang bật chế độ **Chỉ Nhận Lời Mời (`INVITE_ONLY`)**!\n"
            "👉 Hãy vào `/clan settings` ➔ **Chế Độ Tuyển Quân** chuyển sang **Mở Tự Do** hoặc **Cần Duyệt** trước khi đăng tin tuyển công khai."
        )

    now = time.time()
    last_ts = _RECRUIT_COOLDOWNS.get(int(clan["clan_id"]), 0.0)
    rem = int(RECRUIT_COOLDOWN_SECONDS - (now - last_ts))
    if rem > 0:
        mins = max(1, (rem + 59) // 60)
        return f"⏳ Băng bạn vừa đăng tin tuyển thành viên gần đây! Vui lòng đợi khoảng **{mins} phút** nữa để tránh spam kênh tuyển quân."

    return None


class RecruitApplyButton(ui.DynamicItem[ui.Button], template=r"clan_recruit:apply:(?P<clan_id>[0-9]+)"):
    """Nút Xin Gia Nhập Băng bền vững (hoạt động cả sau khi bot khởi động lại)."""
    def __init__(self, clan_id: int):
        super().__init__(
            ui.Button(
                label="Xin Gia Nhập Băng",
                emoji="📩",
                style=discord.ButtonStyle.success,
                custom_id=f"clan_recruit:apply:{clan_id}"
            )
        )
        self.clan_id = clan_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: ui.Button, match: re.Match[str]):
        return cls(int(match.group("clan_id")))

    async def callback(self, interaction: discord.Interaction):
        bot = interaction.client
        if hasattr(bot, "check_user_bot_access") and not await bot.check_user_bot_access(interaction):
            return

        guild = interaction.guild
        if not guild:
            await auto_dismiss_notice(interaction, content="❌ Thao tác này chỉ thực hiện được trong máy chủ Discord!", delay=5)
            return

        clan = await bot.db.get_clan_by_id(self.clan_id)
        if not clan:
            await auto_dismiss_notice(interaction, content="❌ Băng đảng này đã giải tán hoặc không còn tồn tại!", delay=5)
            return

        existing = await bot.db.get_clan_by_member(guild.id, interaction.user.id)
        if existing:
            if existing["clan_id"] == clan["clan_id"]:
                await auto_dismiss_notice(interaction, content="ℹ️ Bạn đã là thành viên của băng này rồi!", delay=5)
            else:
                await auto_dismiss_notice(
                    interaction,
                    content=f"❌ Bạn đang là thành viên của băng **[{existing['tag']}] {existing['name']}**. Hãy rời băng cũ trước khi xin vào băng mới!",
                    delay=6
                )
            return

        cur_count = await bot.db.get_member_count(clan["clan_id"])
        if cur_count >= clan["max_members"]:
            await auto_dismiss_notice(
                interaction,
                content=f"❌ Rất tiếc, băng **{clan['name']}** hiện đã đủ sĩ số (**{cur_count}/{clan['max_members']}**)!",
                delay=6
            )
            return

        if clan.get("join_mode") == JoinModes.INVITE_ONLY:
            await auto_dismiss_notice(
                interaction,
                content=f"🔒 Băng **{clan['name']}** hiện đã chuyển sang chế độ **Chỉ Nhận Lời Mời**!",
                delay=6
            )
            return

        if await bot.db.has_pending_request(clan["clan_id"], interaction.user.id):
            await auto_dismiss_notice(
                interaction,
                content=f"⏳ Bạn đã có một đơn/lời mời đang chờ xử lý với băng **{clan['name']}** rồi!",
                delay=6
            )
            return

        if clan.get("join_mode") == JoinModes.OPEN:
            await interaction.response.defer(ephemeral=True)
            role = guild.get_role(int(clan["role_id"])) if clan.get("role_id") else None
            if role:
                try:
                    await interaction.user.add_roles(role, reason="Gia nhập băng (Open mode từ bảng tuyển thành viên)")
                except Exception:
                    pass
            await bot.db.add_member(guild.id, interaction.user.id, clan["clan_id"], Ranks.MEMBER)
            await bot.db.add_clan_log(
                clan_id=clan["clan_id"],
                actor_id=interaction.user.id,
                target_id=interaction.user.id,
                action="JOIN",
                details=f"{interaction.user.display_name} gia nhập băng từ bảng tuyển thành viên (Mở Tự Do)."
            )
            text_ch = guild.get_channel(int(clan["text_channel_id"])) if clan.get("text_channel_id") else None
            if text_ch:
                try:
                    welcome_embed = discord.Embed(
                        title="👋 THÀNH VIÊN MỚI GIA NHẬP!",
                        description=f"Nhiệt liệt chào mừng {interaction.user.mention} đã gia nhập băng **{clan['name']}** từ bảng tuyển thành viên!",
                        color=discord.Color.green(),
                        timestamp=datetime.now()
                    )
                    await text_ch.send(content=interaction.user.mention, embed=welcome_embed, view=WelcomeGreetingView(interaction.user.id))
                except Exception:
                    pass
            await interaction.followup.send(f"🎉 Chúc mừng bạn đã gia nhập băng **[{clan['tag']}] {clan['name']}** thành công!", ephemeral=True)
            return

        await interaction.response.send_modal(ApplyClanModal(clan=clan, bot=bot))


class RecruitMembersButton(ui.DynamicItem[ui.Button], template=r"clan_recruit:members:(?P<clan_id>[0-9]+)"):
    """Nút Xem Thành Viên bền vững trên bài đăng tuyển thành viên."""
    def __init__(self, clan_id: int):
        super().__init__(
            ui.Button(
                label="Xem Thành Viên",
                emoji="👥",
                style=discord.ButtonStyle.primary,
                custom_id=f"clan_recruit:members:{clan_id}"
            )
        )
        self.clan_id = clan_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: ui.Button, match: re.Match[str]):
        return cls(int(match.group("clan_id")))

    async def callback(self, interaction: discord.Interaction):
        bot = interaction.client
        if hasattr(bot, "check_user_bot_access") and not await bot.check_user_bot_access(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        clan = await bot.db.get_clan_by_id(self.clan_id)
        if not clan:
            await interaction.followup.send("❌ Băng đảng này đã giải tán hoặc không còn tồn tại!", ephemeral=True)
            return

        members = await bot.db.get_clan_members(self.clan_id)
        files: List[discord.File] = []
        logo_ref = await resolve_clan_logo(clan, files, fallback_to_default=True)
        logo_filename = logo_ref.replace("attachment://", "") if (logo_ref and logo_ref.startswith("attachment://")) else None
        embed, total_pages = build_members_embed(clan, members, page=1, page_size=10, logo_filename=logo_filename)
        if logo_ref and not logo_filename:
            embed.set_thumbnail(url=logo_ref)
        view = MembersPaginationView(
            clan_id=self.clan_id,
            current_page=1,
            total_pages=total_pages,
            current_filter="ALL",
            bot=bot
        )
        await interaction.followup.send(embed=embed, files=files, view=view, ephemeral=True)


class RecruitPublicView(SafeView):
    """View công khai gắn dưới bài đăng tuyển thành viên trong #tuyen-thanh-vien."""
    def __init__(self, clan_id: int):
        super().__init__(timeout=None)
        self.add_item(RecruitApplyButton(clan_id))
        self.add_item(RecruitMembersButton(clan_id))


class RecruitPostModal(SafeModal, title="📢 Đăng Tin Tuyển Thành Viên"):
    """Modal nhập nội dung tuyển thành viên của Chủ Băng / Cán Bộ."""
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__()
        self.clan = clan
        self.bot = bot

    game_focus = ui.TextInput(
        label="Tựa Game / Hoạt Động Chính",
        placeholder="VD: Valorant, Liên Quân, CS2, Giao lưu nói chuyện...",
        default="Đa dạng tựa game & Giao lưu cộng đồng",
        max_length=80,
        required=False
    )
    requirements = ui.TextInput(
        label="Yêu Cầu Gia Nhập (Nếu Có)",
        placeholder="VD: Hòa đồng, có mic, online tối từ 20h...",
        max_length=120,
        required=False
    )
    recruit_content = ui.TextInput(
        label="Nội Dung Chiêu Mộ Thành Viên",
        style=discord.TextStyle.paragraph,
        placeholder="Giới thiệu điểm nổi bật của băng, quyền lợi và lời mời gọi anh em...",
        min_length=10,
        max_length=600,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        clan = await self.bot.db.get_clan_by_member(guild.id, interaction.user.id)
        cur_count = await self.bot.db.get_member_count(clan["clan_id"]) if clan else 0
        err = validate_recruit_publisher(clan, interaction.user, cur_count)
        if err:
            await interaction.followup.send(err, ephemeral=True)
            return

        recruit_ch, ch_err = await get_or_create_recruit_channel(guild)
        if ch_err or not recruit_ch:
            await interaction.followup.send(ch_err or "❌ Không thể truy cập kênh `#tuyen-thanh-vien`!", ephemeral=True)
            return

        join_mode_labels = {
            JoinModes.OPEN: "🟢 Mở Tự Do (Vào Thẳng)",
            JoinModes.APPROVAL: "🟡 Cần Duyệt Đơn",
            JoinModes.INVITE_ONLY: "🔒 Chỉ Nhận Lời Mời"
        }
        game_txt = self.game_focus.value.strip() or "Đa dạng tựa game & Giao lưu cộng đồng"
        req_txt = self.requirements.value.strip() or "Hòa đồng, vui vẻ, tôn trọng mọi người"
        body_txt = self.recruit_content.value.strip()

        files: List[discord.File] = []
        logo_ref = await resolve_clan_logo(clan, files, fallback_to_default=True)
        leader_mem = guild.get_member(int(clan["leader_id"])) if clan.get("leader_id") else None
        leader_name = leader_mem.display_name if leader_mem else None
        banner_ref = await resolve_clan_banner(clan, files, member_count=cur_count, leader_name=leader_name, fallback_to_default=True)

        embed = discord.Embed(
            title=f"📢 CHIÊU MỘ THÀNH VIÊN — [{clan['tag']}] {clan['name']}",
            description=f"📜 **Khẩu hiệu:** *{clan.get('description') or 'Chưa cập nhật khẩu hiệu.'}*\n\n💬 **Lời Ngỏ Tuyển Quân:**\n{body_txt}",
            color=parse_hex_color(clan.get("color_hex")),
            timestamp=datetime.now()
        )
        embed.add_field(name="👑 Chủ Băng", value=f"<@{clan['leader_id']}>", inline=True)
        embed.add_field(name="📈 Cấp Độ", value=f"Level **{clan.get('level', 1)}** ({clan.get('exp', 0):,} EXP)", inline=True)
        embed.add_field(name="👥 Sĩ Số", value=f"**{cur_count}/{clan.get('max_members', 15)}** thành viên", inline=True)
        embed.add_field(name="🎮 Hoạt Động Chính", value=game_txt, inline=True)
        embed.add_field(name="🚪 Chế Độ Tuyển", value=join_mode_labels.get(clan.get("join_mode"), "🟡 Cần Duyệt"), inline=True)
        embed.add_field(name="📋 Yêu Cầu", value=req_txt, inline=False)
        if logo_ref:
            embed.set_thumbnail(url=logo_ref)
        if banner_ref:
            embed.set_image(url=banner_ref)
        embed.set_footer(
            text=f"Đăng bởi {interaction.user.display_name} • Bấm nút bên dưới để Xin Gia Nhập hoặc Xem Thành Viên",
            icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
        )

        view = RecruitPublicView(clan_id=clan["clan_id"])
        try:
            post_msg = await recruit_ch.send(embed=embed, files=files, view=view)
        except Exception as send_err:
            await interaction.followup.send(f"❌ Không thể đăng tin vào {recruit_ch.mention}: `{send_err}`", ephemeral=True)
            return

        _RECRUIT_COOLDOWNS[int(clan["clan_id"])] = time.time()
        await self.bot.db.add_clan_log(
            clan_id=clan["clan_id"],
            actor_id=interaction.user.id,
            action="RECRUIT_POST",
            details=f"Đăng tin tuyển thành viên công khai tại #{recruit_ch.name}."
        )
        await interaction.followup.send(
            f"✅ **Đã đăng tin tuyển thành viên cho băng [{clan['tag']}] {clan['name']} thành công!**\n👉 Xem bài đăng tại: {post_msg.jump_url}",
            ephemeral=True
        )


# =============================================================================
# TRUNG TÂM NHIỆM VỤ & ĐIỂM DANH (DAILY + WEEKLY + CHECK-IN)
# =============================================================================

async def _render_mission_hub(interaction: discord.Interaction, clan: Dict[str, Any], bot: Any, mode: str = "daily"):
    from utils.embeds import build_quests_embed
    from utils.canvas import generate_quests_image
    from utils.constants import DEFAULT_DAILY_QUESTS

    today = get_today_vn_string()
    week_key = get_current_week_key()
    daily_quests = await bot.db.ensure_daily_quests(clan["clan_id"], today)
    weekly_quests = await bot.db.ensure_weekly_quests(clan["clan_id"], week_key)

    if mode == "weekly":
        buf = await asyncio.to_thread(generate_quests_image, clan, weekly_quests, week_key)
        file = discord.File(fp=buf, filename="quests.png")
        files = [file]
        logo_ref = await resolve_clan_logo(clan, files, fallback_to_default=True)
        embed = build_quests_embed(clan, weekly_quests, week_key, attachment_filename="quests.png")
        if logo_ref:
            embed.set_thumbnail(url=logo_ref)
    else:
        meta_map = {q["quest_type"]: q for q in DEFAULT_DAILY_QUESTS}
        lines = []
        for dq in daily_quests:
            m = meta_map.get(dq["quest_type"], {})
            cur = min(dq["current_value"], dq["target_value"])
            tgt = dq["target_value"]
            pct = int(cur * 100 / max(1, tgt))
            bar = "🟩" * (pct // 20) + "⬜" * (5 - pct // 20)
            status_icon = "✅" if dq["completed"] else "⏳"
            lines.append(
                f"{status_icon} **{m.get('title', dq['quest_type'])}** (`{cur}/{tgt}`)\n"
                f"┗ {bar} `{pct}%` • Thưởng: **+{dq['reward_exp']} EXP** + **+{dq.get('reward_coins', 30)} Xu Linh Thú**"
            )
        files = []
        logo_ref = await resolve_clan_logo(clan, files, fallback_to_default=True)
        embed = discord.Embed(
            title=f"📅 NHIỆM VỤ NGÀY & ĐIỂM DANH — [{clan['tag']}] {clan['name']}",
            description=(
                f"Ngày: **{today}** *(Làm mới lúc 00:00 giờ Việt Nam)*\n\n"
                + "\n\n".join(lines)
            ),
            color=parse_hex_color(clan.get("color_hex")),
            timestamp=datetime.now()
        )
        if logo_ref:
            embed.set_thumbnail(url=logo_ref)
        embed.set_footer(text="Bấm [📅 Điểm Danh Hằng Ngày] hoặc chuyển sang [🎯 Nhiệm Vụ Tuần] bên dưới!")

    view = ClanMissionHubView(clan=clan, bot=bot, active_mode=mode)
    await interaction.edit_original_response(content=None, embed=embed, attachments=files, view=view)


class ClanMissionHubView(SafeView):
    """Giao diện gộp Điểm Danh Hằng Ngày + Nhiệm Vụ Ngày + Nhiệm Vụ Tuần."""
    def __init__(self, clan: Dict[str, Any], bot: Any, active_mode: str = "daily"):
        super().__init__(timeout=600)
        self.clan = clan
        self.bot = bot
        self.active_mode = active_mode

    @ui.button(label="Điểm Danh Hằng Ngày", emoji="📅", style=discord.ButtonStyle.success, row=0)
    async def checkin_btn(self, interaction: discord.Interaction, button: ui.Button):
        res = await perform_daily_checkin(self.bot.db, interaction.guild_id, interaction.user.id)
        if not res["ok"]:
            await auto_dismiss_notice(interaction, content=res["error"], delay=5)
            return
        if res.get("clan_streak_updated") and self.bot:
            from utils.streak_nick import sync_clan_streak_queue
            asyncio.create_task(sync_clan_streak_queue(self.bot, self.clan["clan_id"]))
        streak_note = "🎁 *(Thưởng +50 EXP mốc 7 ngày!)*" if res["is_streak_7"] else ""
        pet_note = f" *(gồm +{res['pet_bonus_exp']} EXP buff Linh Thú)*" if res.get("pet_bonus_exp") else ""
        await auto_dismiss_notice(
            interaction,
            content=(
                f"🎉 **Điểm danh thành công!**\n"
                f"• Chuỗi streak: **{res['new_streak']} ngày** {streak_note}\n"
                f"• Băng nhận: **+{res['clan_exp_to_add']} EXP**{pet_note} • Cá nhân: **+{res['contribution']} Cống hiến**"
            ),
            delay=6
        )

    @ui.button(label="Nhiệm Vụ Ngày", emoji="🌤️", style=discord.ButtonStyle.primary, row=0)
    async def daily_tab_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        await _render_mission_hub(interaction, self.clan, self.bot, mode="daily")

    @ui.button(label="Nhiệm Vụ Tuần", emoji="🎯", style=discord.ButtonStyle.primary, row=0)
    async def weekly_tab_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        await _render_mission_hub(interaction, self.clan, self.bot, mode="weekly")

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, row=1)
    async def back_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, interaction.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=1)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)


# =============================================================================
# HỆ THỐNG LINH THÚ BĂNG ĐẢNG (CLAN PET — PILLOW VECTOR + ANCHOR SYSTEM)
# =============================================================================

def build_pet_status_embed(pet: Dict[str, Any], clan: Dict[str, Any], attachment_name: str = "clan_pet.png") -> discord.Embed:
    info = get_pet_level_info(int(pet.get("exp", 0)))
    sp = PET_SPECIES.get(pet["species"], {"name": pet["species"], "emoji": "🐾"})
    hunger = int(pet.get("hunger", 80))
    mood = int(pet.get("mood", 80))

    if hunger <= 0 or mood <= 0:
        buff_status = "⚠️ Tạm ngưng buff (Pet đang đói/buồn về 0%, hãy cho ăn hoặc vuốt ve!)"
    elif info["checkin_bonus_pct"] > 0:
        buff_status = f"✨ Đang kích hoạt **+{info['checkin_bonus_pct']}% EXP Điểm Danh**"
    else:
        buff_status = f"🥚 Trứng đang ấp ({info['cur_exp']}/200 Pet EXP để nở)"

    unlocked_txt = ", ".join(PET_SLOT_NAMES.get(s, s) for s in info["unlocked_slots"])
    exp_display = f"MAX • {info['cur_exp']:,}" if info["level"] >= 99 else f"{info['cur_exp']:,}/{info['next_level_exp']:,}"
    embed = discord.Embed(
        title=f"{sp['emoji']} LINH THÚ BĂNG: {pet['name']} — [{clan['tag']}] {clan['name']}",
        description=(
            f"• **Chủng loài:** {sp['name']} • **Giai đoạn:** {info['stage_name']} (Stage {info['stage']}/5)\n"
            f"• **Cấp độ Pet:** Level **{info['level']}** (`{exp_display}` Pet EXP)\n"
            f"• **Quỹ Xu Linh Thú:** **{pet.get('pet_coins', 0):,}** Xu 🪙\n"
            f"• **Hiệu ứng thụ động:** {buff_status}\n"
            f"• **Slot đồ đã mở:** {unlocked_txt}"
        ),
        color=parse_hex_color(clan.get("color_hex")),
        timestamp=datetime.now()
    )
    embed.set_image(url=f"attachment://{attachment_name}")
    embed.set_footer(text="Cả băng cùng chăm sóc, kiếm Xu qua Điểm Danh / Voice Co-op / Nhiệm Vụ để mua Style!")
    return embed


async def open_clan_pet_screen(interaction: discord.Interaction, clan: Dict[str, Any], bot: Any, edit_original: bool = True):
    pet = await bot.db.get_clan_pet(clan["clan_id"])
    if not pet:
        desc_lines = [
            f"{sp['emoji']} **{sp['name']}** — {sp['desc']}"
            for sp in PET_SPECIES.values()
        ]
        embed = discord.Embed(
            title=f"🥚 NHẬN TRỨNG LINH THÚ — [{clan['tag']}] {clan['name']}",
            description=(
                "Băng của bạn chưa có **Linh Thú Băng Đảng**!\n"
                "Hãy để **Chủ Băng** chọn 1 trong 4 hệ linh thú dưới đây để cả băng cùng nuôi dưỡng, tiến hóa qua 5 giai đoạn và diện 5 phong cách thời trang cực chất:\n\n"
                + "\n".join(desc_lines)
            ),
            color=parse_hex_color(clan.get("color_hex")),
            timestamp=datetime.now()
        )
        view = ClanPetEggSelectView(clan=clan, bot=bot)
        if edit_original:
            await interaction.edit_original_response(content=None, embed=embed, attachments=[], view=view)
        else:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        return

    from utils.pet_canvas import generate_clan_pet_image
    buf = await asyncio.to_thread(generate_clan_pet_image, pet, clan)
    file = discord.File(fp=buf, filename="clan_pet.png")
    embed = build_pet_status_embed(pet, clan, "clan_pet.png")
    view = ClanPetView(clan=clan, pet=pet, user=interaction.user, bot=bot)
    if edit_original:
        await interaction.edit_original_response(content=None, embed=embed, attachments=[file], view=view)
    else:
        await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)


class ClanPetEggSelectView(SafeView):
    """Chọn trứng Linh Thú khởi đầu (Dành cho Chủ Băng)."""
    def __init__(self, clan: Dict[str, Any], bot: Any):
        super().__init__(timeout=300)
        self.clan = clan
        self.bot = bot

        options = [
            discord.SelectOption(
                label=sp["name"],
                value=sp_id,
                emoji=sp["emoji"],
                description=sp["desc"][:100]
            )
            for sp_id, sp in PET_SPECIES.items()
        ]
        self.species_select.options = options

    @ui.select(placeholder="🥚 Chọn chủng loại Trứng Linh Thú cho băng...", row=0)
    async def species_select(self, interaction: discord.Interaction, select: ui.Select):
        if int(self.clan["leader_id"]) != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await auto_dismiss_notice(interaction, content="❌ Chỉ **Chủ Băng** mới có quyền chọn trứng Linh Thú khởi đầu!", delay=5)
            return
        await interaction.response.defer()
        existing = await self.bot.db.get_clan_pet(self.clan["clan_id"])
        if existing:
            await open_clan_pet_screen(interaction, self.clan, self.bot, edit_original=True)
            return

        sp_id = select.values[0]
        sp = PET_SPECIES[sp_id]
        default_name = f"Bé {sp['name']}"
        await self.bot.db.create_clan_pet(self.clan["clan_id"], sp_id, default_name)
        await self.bot.db.add_clan_log(
            clan_id=self.clan["clan_id"],
            actor_id=interaction.user.id,
            action="PET_ADOPT",
            details=f"Nhận Trứng Linh Thú **{sp['name']}** ({default_name}) cho băng!"
        )
        await open_clan_pet_screen(interaction, self.clan, self.bot, edit_original=True)

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, row=1)
    async def back_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, interaction.user, self.bot)


class ClanPetRenameModal(SafeModal, title="✏️ Đổi Tên Linh Thú Băng"):
    def __init__(self, clan: Dict[str, Any], current_name: str, bot: Any):
        super().__init__()
        self.clan = clan
        self.bot = bot
        self.pet_name = ui.TextInput(
            label="Tên Mới Cho Linh Thú (2-24 ký tự)",
            default=current_name[:24],
            min_length=2,
            max_length=24,
            required=True
        )
        self.add_item(self.pet_name)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        new_name = self.pet_name.value.strip()
        await self.bot.db.update_clan_pet(self.clan["clan_id"], name=new_name)
        await self.bot.db.add_clan_log(
            clan_id=self.clan["clan_id"],
            actor_id=interaction.user.id,
            action="PET_RENAME",
            details=f"Đổi tên Linh Thú băng thành **{new_name}**."
        )
        await open_clan_pet_screen(interaction, self.clan, self.bot, edit_original=True)


class ClanPetShopView(SafeView):
    """Cửa hàng thời trang & phông nền Linh Thú — Phân chia danh mục + phong cách + xem trước."""
    def __init__(
        self,
        clan: Dict[str, Any],
        pet: Dict[str, Any],
        owned_ids: List[str],
        style_filter: str,
        bot: Any,
        selected_item_id: Optional[str] = None,
        slot_filter: str = "ALL",
    ):
        super().__init__(timeout=300)
        self.clan = clan
        self.pet = pet
        self.owned_ids = set(owned_ids)
        self.style_filter = style_filter
        self.slot_filter = slot_filter
        self.bot = bot
        self.selected_item_id = selected_item_id

        slot_opts = [
            discord.SelectOption(label="📂 Tất cả danh mục", value="ALL", default=(slot_filter == "ALL"))
        ] + [
            discord.SelectOption(label=label, value=key, default=(slot_filter == key))
            for key, label in PET_SLOT_NAMES.items()
        ]
        self.slot_select.options = slot_opts

        style_opts = [
            discord.SelectOption(label="🌟 Tất cả phong cách", value="ALL", default=(style_filter == "ALL"))
        ] + [
            discord.SelectOption(label=label, value=key, default=(style_filter == key))
            for key, label in PET_STYLE_NAMES.items()
        ]
        self.style_select.options = style_opts

        items = [
            it for it in PET_CATALOG
            if (slot_filter == "ALL" or it["slot"] == slot_filter)
            and (style_filter == "ALL" or it["style"] == style_filter)
        ][:25]
        item_opts = []
        for it in items:
            owned_tag = "✅ Đã có" if it["item_id"] in self.owned_ids else f"🪙 {it['price']} Xu"
            item_opts.append(
                discord.SelectOption(
                    label=f"{it['name']} ({owned_tag})"[:100],
                    value=it["item_id"],
                    default=(it["item_id"] == selected_item_id),
                    description=f"{PET_SLOT_NAMES.get(it['slot'], it['slot'])} • Stage {it['min_stage']}+"[:100]
                )
            )
        if not item_opts:
            item_opts.append(discord.SelectOption(label="Không có vật phẩm ở mục lọc này", value="NONE"))
            self.buy_select.disabled = True
        self.buy_select.options = item_opts

        if not selected_item_id or selected_item_id not in PET_CATALOG_MAP:
            self.remove_item(self.confirm_buy_btn)
        else:
            sel_item = PET_CATALOG_MAP[selected_item_id]
            if selected_item_id in self.owned_ids:
                self.confirm_buy_btn.label = "Đã Sở Hữu Trong Tủ Đồ"
                self.confirm_buy_btn.style = discord.ButtonStyle.secondary
                self.confirm_buy_btn.disabled = True
            else:
                self.confirm_buy_btn.label = f"Mua Ngay ({sel_item['price']} Xu)"
                self.confirm_buy_btn.style = discord.ButtonStyle.success
                self.confirm_buy_btn.disabled = int(pet.get("pet_coins", 0)) < sel_item["price"]

    @ui.select(placeholder="📂 Chọn Danh Mục vật phẩm (Mũ / Áo / Cánh / Nền...)", row=0)
    async def slot_select(self, interaction: discord.Interaction, select: ui.Select):
        await interaction.response.defer()
        pet = await self.bot.db.get_clan_pet(self.clan["clan_id"])
        inv = await self.bot.db.get_pet_inventory(self.clan["clan_id"])
        view = ClanPetShopView(self.clan, pet, inv, self.style_filter, self.bot, slot_filter=select.values[0])
        embed = discord.Embed(
            title=f"🛒 CỬA HÀNG LINH THÚ — Quỹ Băng: {pet['pet_coins']:,} Xu 🪙",
            description="Chọn danh mục / phong cách rồi chọn vật phẩm bên dưới để **xem trước trực tiếp trên Linh Thú**!",
            color=discord.Color.gold()
        )
        await interaction.edit_original_response(embed=embed, attachments=[], view=view)

    @ui.select(placeholder="🎨 Lọc theo phong cách thời trang...", row=1)
    async def style_select(self, interaction: discord.Interaction, select: ui.Select):
        await interaction.response.defer()
        pet = await self.bot.db.get_clan_pet(self.clan["clan_id"])
        inv = await self.bot.db.get_pet_inventory(self.clan["clan_id"])
        view = ClanPetShopView(self.clan, pet, inv, select.values[0], self.bot, slot_filter=self.slot_filter)
        embed = discord.Embed(
            title=f"🛒 CỬA HÀNG LINH THÚ — Quỹ Băng: {pet['pet_coins']:,} Xu 🪙",
            description="Chọn vật phẩm ở menu dưới để **xem trước trực tiếp trên Linh Thú** trước khi bấm mua!",
            color=discord.Color.gold()
        )
        await interaction.edit_original_response(embed=embed, attachments=[], view=view)

    @ui.select(placeholder="👁️ Chọn vật phẩm để XEM TRƯỚC trên Linh Thú...", row=2)
    async def buy_select(self, interaction: discord.Interaction, select: ui.Select):
        item_id = select.values[0]
        if item_id == "NONE":
            return
        item = PET_CATALOG_MAP.get(item_id)
        if not item:
            return
        await interaction.response.defer()
        pet = await self.bot.db.get_clan_pet(self.clan["clan_id"])
        inv = await self.bot.db.get_pet_inventory(self.clan["clan_id"])

        from utils.pet_canvas import generate_clan_pet_preview_image
        buf = await asyncio.to_thread(generate_clan_pet_preview_image, pet, self.clan, item)
        file = discord.File(fp=buf, filename="pet_preview.png")

        owned = item_id in inv
        cur_info = get_pet_level_info(int(pet.get("exp", 0)))
        stage_warn = f"\n⚠️ *Linh Thú hiện đang ở Stage {cur_info['stage']}, món này mặc được từ **Stage {item['min_stage']}** (đang hiển thị mô phỏng)*." if cur_info["stage"] < item["min_stage"] else ""
        embed = discord.Embed(
            title=f"👁️ XEM TRƯỚC: {item['name']}",
            description=(
                f"• **Phong cách:** {PET_STYLE_NAMES.get(item['style'], item['style'])}\n"
                f"• **Vị trí:** {PET_SLOT_NAMES.get(item['slot'], item['slot'])}\n"
                f"• **Giá bán:** **{item['price']}** Xu 🪙 *(Quỹ băng hiện có: **{pet['pet_coins']:,}** Xu)*\n"
                f"• **Trạng thái:** {'✅ Đã sở hữu trong Tủ Đồ' if owned else '🛒 Chưa mua'}"
                f"{stage_warn}"
            ),
            color=discord.Color.gold()
        )
        embed.set_image(url="attachment://pet_preview.png")
        view = ClanPetShopView(self.clan, pet, inv, self.style_filter, self.bot, selected_item_id=item_id, slot_filter=self.slot_filter)
        await interaction.edit_original_response(embed=embed, attachments=[file], view=view)

    @ui.button(label="Mua Vật Phẩm Này", emoji="🛒", style=discord.ButtonStyle.success, row=3)
    async def confirm_buy_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not self.selected_item_id or self.selected_item_id not in PET_CATALOG_MAP:
            return
        item = PET_CATALOG_MAP[self.selected_item_id]
        res = await self.bot.db.buy_pet_item(self.clan["clan_id"], self.selected_item_id, item["price"])
        if not res["ok"]:
            await auto_dismiss_notice(interaction, content=res["error"], delay=5)
            return
        await interaction.response.defer()
        pet = await self.bot.db.get_clan_pet(self.clan["clan_id"])
        inv = await self.bot.db.get_pet_inventory(self.clan["clan_id"])
        view = ClanPetShopView(self.clan, pet, inv, self.style_filter, self.bot, selected_item_id=self.selected_item_id, slot_filter=self.slot_filter)
        embed = discord.Embed(
            title=f"🛒 CỬA HÀNG LINH THÚ — Quỹ: {pet['pet_coins']:,} Xu 🪙",
            description=f"✅ Đã mua **{item['name']}** vào Tủ Đồ Chung của băng! Hãy vào **Tủ Đồ & Phối Style** để mặc cho Pet.",
            color=discord.Color.green()
        )
        await interaction.edit_original_response(embed=embed, attachments=[], view=view)

    @ui.button(label="Quay Lại Linh Thú", emoji="🐾", style=discord.ButtonStyle.secondary, row=3)
    async def back_pet_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        await open_clan_pet_screen(interaction, self.clan, self.bot, edit_original=True)


class ClanPetWardrobeView(SafeView):
    """Tủ đồ & Phối Style cho Linh Thú phân theo Danh mục & Slot đã mở khóa."""
    def __init__(self, clan: Dict[str, Any], pet: Dict[str, Any], owned_ids: List[str], bot: Any, slot_filter: str = "ALL"):
        super().__init__(timeout=300)
        self.clan = clan
        self.pet = pet
        self.owned_ids = owned_ids
        self.slot_filter = slot_filter
        self.bot = bot

        slot_opts = [
            discord.SelectOption(label="📂 Tất cả danh mục đang có", value="ALL", default=(slot_filter == "ALL"))
        ] + [
            discord.SelectOption(label=label, value=key, default=(slot_filter == key))
            for key, label in PET_SLOT_NAMES.items()
        ]
        self.slot_select.options = slot_opts

        info = get_pet_level_info(int(pet.get("exp", 0)))
        unlocked = set(info["unlocked_slots"])
        equipped = pet.get("equipped") or {}

        opts = []
        for iid in owned_ids:
            it = PET_CATALOG_MAP.get(iid)
            if not it:
                continue
            item_slot = it.get("slot", "outfit")
            if slot_filter != "ALL" and item_slot != slot_filter:
                continue
            is_eq = equipped.get(item_slot) == iid
            min_st = it.get("min_stage", 1)
            locked_note = "" if (item_slot in unlocked and info["stage"] >= min_st) else f" [Khóa - Cần Stage {min_st}]"
            opts.append(
                discord.SelectOption(
                    label=f"{'✅ ' if is_eq else ''}{it['name']}{locked_note}"[:100],
                    value=iid,
                    description=PET_SLOT_NAMES.get(item_slot, item_slot)[:100]
                )
            )
            if len(opts) >= 25:
                break
        if not opts:
            empty_msg = "Không có món đồ nào trong danh mục này" if owned_ids else "Tủ đồ đang trống (Hãy ghé Cửa Hàng!)"
            opts.append(discord.SelectOption(label=empty_msg, value="EMPTY"))
            self.equip_select.disabled = True
        self.equip_select.options = opts

    @ui.select(placeholder="📂 Lọc Tủ Đồ theo Danh Mục...", row=0)
    async def slot_select(self, interaction: discord.Interaction, select: ui.Select):
        await interaction.response.defer()
        pet = await self.bot.db.get_clan_pet(self.clan["clan_id"])
        inv = await self.bot.db.get_pet_inventory(self.clan["clan_id"])
        view = ClanPetWardrobeView(self.clan, pet, inv, self.bot, slot_filter=select.values[0])
        await interaction.edit_original_response(view=view)

    @ui.select(placeholder="👗 Chọn món đồ trong Tủ Đồ để Mặc / Tháo...", row=1)
    async def equip_select(self, interaction: discord.Interaction, select: ui.Select):
        iid = select.values[0]
        if iid == "EMPTY":
            return
        item = PET_CATALOG_MAP.get(iid)
        if not item:
            return
        pet = await self.bot.db.get_clan_pet(self.clan["clan_id"])
        info = get_pet_level_info(int(pet.get("exp", 0)))
        item_slot = item.get("slot", "outfit")
        min_st = item.get("min_stage", 1)
        if item_slot not in info["unlocked_slots"] or info["stage"] < min_st:
            await auto_dismiss_notice(
                interaction,
                content=f"🔒 Món **{item['name']}** ({PET_SLOT_NAMES.get(item_slot, item_slot)}) yêu cầu **Stage {min_st}**! Hãy nuôi Pet lên cấp nhé.",
                delay=5
            )
            return

        equipped = dict(pet.get("equipped") or {})
        if equipped.get(item_slot) == iid:
            equipped.pop(item_slot, None)
            msg_txt = f"👕 Đã tháo **{item['name']}** khỏi Linh Thú."
        else:
            equipped[item_slot] = iid
            msg_txt = f"✨ Đã mặc **{item['name']}** cho Linh Thú!"

        await self.bot.db.update_clan_pet(self.clan["clan_id"], equipped=equipped)
        await interaction.response.defer()
        await open_clan_pet_screen(interaction, self.clan, self.bot, edit_original=True)
        await auto_dismiss_notice(interaction, content=msg_txt, delay=4)

    @ui.button(label="Tháo Tất Cả Đồ", emoji="🧹", style=discord.ButtonStyle.danger, row=2)
    async def unequip_all_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self.bot.db.update_clan_pet(self.clan["clan_id"], equipped={})
        await interaction.response.defer()
        await open_clan_pet_screen(interaction, self.clan, self.bot, edit_original=True)

    @ui.button(label="Quay Lại Linh Thú", emoji="🐾", style=discord.ButtonStyle.secondary, row=2)
    async def back_pet_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        await open_clan_pet_screen(interaction, self.clan, self.bot, edit_original=True)


class ClanPetView(SafeView):
    """Bảng điều khiển Linh Thú Băng Đảng 1-Click."""
    def __init__(self, clan: Dict[str, Any], pet: Dict[str, Any], user: discord.Member, bot: Any):
        super().__init__(timeout=600)
        self.clan = clan
        self.pet = pet
        self.user = user
        self.bot = bot

        is_leader = int(clan["leader_id"]) == user.id
        if not is_leader and not user.guild_permissions.administrator:
            self.remove_item(self.toggle_perm_btn)

    async def _do_care(self, interaction: discord.Interaction, action_type: str, hunger_d: int, mood_d: int, raw_exp: int, cost: int, label: str):
        cd = PET_ACTION_COOLDOWNS[action_type]
        rem = await self.bot.db.get_pet_action_cooldown(interaction.guild_id, interaction.user.id, action_type, cd)
        if rem > 0:
            ready_ts = int(time.time()) + rem
            await auto_dismiss_notice(interaction, content=f"⏳ Bạn vừa **{label}** gần đây! Có thể thực hiện lại <t:{ready_ts}:R>.", delay=5)
            return

        today = get_today_vn_string()
        res = await self.bot.db.interact_with_pet(
            self.clan["clan_id"], hunger_d, mood_d, raw_exp, cost, today, daily_exp_cap=PET_DAILY_EXP_CAP
        )
        if not res["ok"]:
            await auto_dismiss_notice(interaction, content=res["error"], delay=5)
            return

        await self.bot.db.set_pet_action_cooldown(interaction.guild_id, interaction.user.id, action_type)
        if res["evolved"]:
            await self.bot.db.add_clan_log(
                clan_id=self.clan["clan_id"],
                actor_id=interaction.user.id,
                action="PET_EVOLVE",
                details=f"Linh Thú **{self.pet['name']}** đã tiến hóa lên **{res['stage_name']}** (Lv.{res['new_level']})!"
            )

        await interaction.response.defer()
        await open_clan_pet_screen(interaction, self.clan, self.bot, edit_original=True)
        cap_note = " *(đã đạt trần Pet EXP hôm nay)*" if res["capped"] else ""
        evo_note = f"\n🎉 **TIẾN HÓA!** Linh thú đã đạt giai đoạn **{res['stage_name']}**!" if res["evolved"] else ""
        await auto_dismiss_notice(
            interaction,
            content=f"🐾 **{label} thành công!** (+{res['added_exp']} Pet EXP{cap_note}){evo_note}",
            delay=6
        )

    @ui.button(label="Cho Ăn (10 Xu)", emoji="🍖", style=discord.ButtonStyle.success, row=0)
    async def feed_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._do_care(interaction, "feed", 25, 0, 30, 10, "Cho ăn")

    @ui.button(label="Vuốt Ve (Free)", emoji="👋", style=discord.ButtonStyle.primary, row=0)
    async def play_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._do_care(interaction, "play", 0, 15, 10, 0, "Vuốt ve")

    @ui.button(label="Tặng Quà (35 Xu)", emoji="🎁", style=discord.ButtonStyle.primary, row=0)
    async def gift_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._do_care(interaction, "gift", 50, 50, 100, 35, "Tặng quà cao cấp")

    @ui.button(label="Tủ Đồ & Phối Style", emoji="👗", style=discord.ButtonStyle.secondary, row=1)
    async def wardrobe_btn(self, interaction: discord.Interaction, button: ui.Button):
        pet = await self.bot.db.get_clan_pet(self.clan["clan_id"])
        is_leader = int(self.clan["leader_id"]) == interaction.user.id
        is_officer = is_leader or self.clan.get("rank") in (Ranks.CO_LEADER, Ranks.OFFICER)
        if not pet.get("allow_member_style") and not is_officer and not interaction.user.guild_permissions.administrator:
            await auto_dismiss_notice(interaction, content="🔒 Chủ Băng đang bật chế độ chỉ Cán Bộ trở lên mới được thay đồ cho Linh Thú!", delay=5)
            return
        await interaction.response.defer()
        inv = await self.bot.db.get_pet_inventory(self.clan["clan_id"])
        view = ClanPetWardrobeView(self.clan, pet, inv, self.bot)
        embed = discord.Embed(
            title=f"👗 TỦ ĐỒ LINH THÚ: {pet['name']}",
            description=f"Đang sở hữu **{len(inv)}** vật phẩm. Chọn món đồ bên dưới để Mặc / Tháo ngay!",
            color=parse_hex_color(self.clan.get("color_hex"))
        )
        await interaction.edit_original_response(embed=embed, attachments=[], view=view)

    @ui.button(label="Cửa Hàng", emoji="🛒", style=discord.ButtonStyle.secondary, row=1)
    async def shop_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        pet = await self.bot.db.get_clan_pet(self.clan["clan_id"])
        inv = await self.bot.db.get_pet_inventory(self.clan["clan_id"])
        view = ClanPetShopView(self.clan, pet, inv, "ALL", self.bot)
        embed = discord.Embed(
            title=f"🛒 CỬA HÀNG LINH THÚ — Quỹ Băng: {pet['pet_coins']:,} Xu 🪙",
            description="Dùng **Xu Linh Thú** (kiếm từ Điểm Danh, Nhiệm Vụ Ngày/Tuần, Voice Co-op) để mua đồ vào Tủ Đồ Chung của băng!",
            color=discord.Color.gold()
        )
        await interaction.edit_original_response(embed=embed, attachments=[], view=view)

    @ui.button(label="Đổi Tên Pet", emoji="✏️", style=discord.ButtonStyle.secondary, row=1)
    async def rename_pet_btn(self, interaction: discord.Interaction, button: ui.Button):
        is_leader = int(self.clan["leader_id"]) == interaction.user.id
        is_officer = is_leader or self.clan.get("rank") in (Ranks.CO_LEADER, Ranks.OFFICER)
        if not is_officer and not interaction.user.guild_permissions.administrator:
            await auto_dismiss_notice(interaction, content="❌ Chỉ Cán Bộ trở lên mới có quyền đổi tên Linh Thú!", delay=5)
            return
        await interaction.response.send_modal(ClanPetRenameModal(self.clan, self.pet["name"], self.bot))

    @ui.button(label="Bật/Tắt Mem Phối Đồ", emoji="🔐", style=discord.ButtonStyle.secondary, row=2)
    async def toggle_perm_btn(self, interaction: discord.Interaction, button: ui.Button):
        pet = await self.bot.db.get_clan_pet(self.clan["clan_id"])
        new_val = 0 if pet.get("allow_member_style") else 1
        await self.bot.db.update_clan_pet(self.clan["clan_id"], allow_member_style=new_val)
        txt = "**BẬT** (Mọi thành viên đều có thể phối đồ)" if new_val else "**TẮT** (Chỉ Cán Bộ trở lên được phối đồ)"
        await auto_dismiss_notice(interaction, content=f"🔐 Quyền phối đồ thành viên: {txt}", delay=5)

    @ui.button(label="Quay Lại Hub", emoji="🏠", style=discord.ButtonStyle.secondary, row=2)
    async def back_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        await return_to_hub(interaction, interaction.user, self.bot)

    @ui.button(label="Đóng Bảng", emoji="🗑️", style=discord.ButtonStyle.secondary, row=2)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        if hasattr(self.bot, "dismiss_user_panel"):
            await self.bot.dismiss_user_panel(interaction.user.id)
