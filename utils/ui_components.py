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
from typing import Optional, Dict, Any, List
from utils.constants import (
    Ranks,
    JoinModes,
    Cooldowns,
    RANK_WEIGHTS,
    RANK_NAMES,
    RANK_LIMITS
)
from utils.embeds import (
    build_clan_info_embed,
    build_clan_list_embed,
    build_leaderboard_embed,
    build_members_embed,
    build_logs_embed,
    build_party_embed,
    build_role_setup_embed,
    get_level_info,
    parse_hex_color,
    send_dm_notification
)
from utils.logger import setup_logging
from utils.time_helper import get_current_week_key

logger = setup_logging("UIComponents")

# =============================================================================
# MODALS
# =============================================================================

class CreateClanModal(ui.Modal, title="🏰 Thành Lập Băng Đảng Mới"):
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

        # TỰ ĐỘNG KHỞI TẠO ĐỘNG: Nếu server chưa setup, Admin tạo băng thì bot tự tạo Category & Log channel luôn!
        if not config:
            if is_admin:
                try:
                    category = await guild.create_category("🏰 BĂNG ĐẢNG", reason="Tự động khởi tạo hệ thống Băng Đảng")
                    log_ch = await guild.create_text_channel("📜・nhật-ký-băng", category=category, reason="Tự động tạo kênh log băng")
                    await self.bot.db.save_guild_config(
                        guild_id=guild.id,
                        category_id=category.id,
                        log_channel_id=log_ch.id,
                        allow_member_create=True,
                        required_role_id=None,
                        cooldown_hours=24
                    )
                    config = await self.bot.db.get_guild_config(guild.id)
                    logger.info(f"Đã tự động khởi tạo Category & Kênh Log cho server {guild.name} ({guild.id})")
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

            # 2. Tạo Kênh Text & Voice trong Category (Tự phục hồi nếu category bị xóa & tự mở rộng Category nếu đầy 50 kênh)
            category = guild.get_channel(int(config["clan_category_id"]))
            if not category:
                try:
                    category = await guild.create_category("🏰 BĂNG ĐẢNG", reason="Tự phục hồi Category bị thiếu")
                    await self.bot.db.save_guild_config(
                        guild_id=guild.id,
                        category_id=category.id,
                        log_channel_id=config.get("log_channel_id"),
                        allow_member_create=bool(config.get("allow_member_create", 1)),
                        required_role_id=config.get("required_role_id"),
                        cooldown_hours=int(config.get("leave_cooldown_hours", 24))
                    )
                except Exception:
                    category = None
            elif len(category.channels) >= 48:
                # Category hiện tại đã gần đầy 50 kênh -> Tự động tìm hoặc tạo Category mở rộng (Part II, III...)
                overflow_cat = None
                for cat in guild.categories:
                    if "BĂNG ĐẢNG" in cat.name.upper() and len(cat.channels) < 48:
                        overflow_cat = cat
                        break
                if not overflow_cat:
                    num_cats = sum(1 for c in guild.categories if "BĂNG ĐẢNG" in c.name.upper()) + 1
                    roman_map = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
                    sub_title = roman_map[num_cats - 1] if num_cats <= len(roman_map) else str(num_cats)
                    try:
                        overflow_cat = await guild.create_category(f"🏰 BĂNG ĐẢNG {sub_title}", reason="Tự động mở rộng Category khi đạt giới hạn 50 kênh")
                    except Exception:
                        overflow_cat = category
                category = overflow_cat

            clean_channel_slug = re.sub(r"[^a-z0-9]", "-", name.lower())[:30]
            text_channel_name = f"💬・{tag.lower()}-{clean_channel_slug}"
            voice_channel_name = f"🔊・[{tag}] Phòng Sinh Hoạt"

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False, send_messages=False),
                clan_role: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, embed_links=True, attach_files=True,
                    read_message_history=True, connect=True, speak=True, use_voice_activation=True
                ),
                me: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, manage_messages=True, manage_channels=True,
                    manage_roles=True, connect=True, move_members=True
                )
            }

            text_channel = await guild.create_text_channel(
                name=text_channel_name,
                category=category,
                topic=f"Kênh sinh hoạt chính thức của Băng [{tag}] {name} | Khẩu hiệu: {slogan}",
                overwrites=overwrites
            )

            voice_channel = await guild.create_voice_channel(
                name=voice_channel_name,
                category=category,
                overwrites=overwrites
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
                color_hex="#5865F2"
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


class RenameClanModal(ui.Modal):
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__(title=f"✏️ Đổi Thông Tin: {clan['name']}")
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
        role = guild.get_role(int(self.clan["role_id"]))
        if role:
            try:
                await role.edit(name=f"[{tag}] {name}")
            except Exception as e:
                logger.warn(f"Không thể đổi tên role: {e}")

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


class ColorClanModal(ui.Modal, title="🎨 Đổi Màu Sắc Role Băng"):
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


class RoleNameModal(ui.Modal, title="✏️ Đổi Tên Hiển Thị Role Băng"):
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



class ImagesClanModal(ui.Modal, title="🖼️ Cài Đặt Logo & Banner Băng"):
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__()
        self.clan = clan
        self.bot = bot

        self.logo_url = ui.TextInput(
            label="Link Ảnh Logo (Bắt đầu bằng http/https)",
            default=clan.get("logo_url") or "",
            required=False
        )
        self.banner_url = ui.TextInput(
            label="Link Ảnh Banner (Yêu cầu Level 2+)",
            default=clan.get("banner_url") or "",
            required=False
        )
        self.add_item(self.logo_url)
        self.add_item(self.banner_url)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        logo = self.logo_url.value.strip() or None
        banner = self.banner_url.value.strip() or None

        if logo and not logo.startswith(("http://", "https://")):
            await interaction.followup.send("❌ Link Logo phải bắt đầu bằng `http://` hoặc `https://`!", ephemeral=True)
            return

        if banner:
            if self.clan["level"] < 2:
                await interaction.followup.send("❌ Băng cần đạt **Level 2** trở lên để mở khóa tính năng đặt Banner hồ sơ!", ephemeral=True)
                return
            if not banner.startswith(("http://", "https://")):
                await interaction.followup.send("❌ Link Banner phải bắt đầu bằng `http://` hoặc `https://`!", ephemeral=True)
                return

        await self.bot.db.update_clan(self.clan["clan_id"], logo_url=logo, banner_url=banner)
        await self.bot.db.add_clan_log(
            clan_id=self.clan["clan_id"],
            actor_id=interaction.user.id,
            action="UPDATE_IMAGES",
            details="Cập nhật Logo hoặc Banner."
        )

        await interaction.followup.send("✅ Đã cập nhật Logo và Banner hồ sơ thành công!", ephemeral=True)


class GradientColorModal(ui.Modal, title="🌈 Nhập Dải Màu Gradient Tùy Chọn"):
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


class ApplyClanModal(ui.Modal):
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__(title=f"📝 Đơn Xin Vào: {clan['name']}")
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
            role = guild.get_role(int(clan["role_id"]))
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
            text_ch = guild.get_channel(int(clan["text_channel_id"]))
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


class DisbandClanModal(ui.Modal):
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__(title=f"⚠️ Giải Tán Băng: {clan['name']}")
        self.clan = clan
        self.bot = bot

        self.confirm_name = ui.TextInput(
            label=f'Gõ chính xác tên băng: "{clan["name"]}"',
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
        for ch_key in ("text_channel_id", "voice_channel_id", "extra_voice_channel_id"):
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

class ClanQuickPartyModal(ui.Modal, title="🎮 Tạo Kèo Rủ Chơi Game Nhanh"):
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
        label="Thời Gian Bắt Đầu (Ví dụ: 21:00 hoặc để trống)",
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
        text_ch = interaction.guild.get_channel(int(self.clan["text_channel_id"]))
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


# =============================================================================
# VIEWS & BUTTONS
# =============================================================================

class ClanInfoView(ui.View):
    """View tương tác động dưới /clan info tùy theo vai trò của người xem"""
    def __init__(self, clan_id: int, can_apply: bool = False, is_member: bool = False, is_leader: bool = False, bot: Any = None):
        super().__init__(timeout=None)
        self.clan_id = clan_id
        self.bot = bot

        if not can_apply:
            self.remove_item(self.apply_button)

        if not is_member:
            self.remove_item(self.checkin_btn)

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
        await interaction.response.defer(ephemeral=True)
        from utils.time_helper import get_today_vn_string, get_yesterday_vn_string, get_current_week_key
        from utils.constants import EXP_REWARDS

        clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not clan or clan["clan_id"] != self.clan_id:
            await interaction.followup.send("❌ Bạn không thuộc băng này!", ephemeral=True)
            return

        today = get_today_vn_string()
        yesterday = get_yesterday_vn_string()
        if clan.get("last_checkin_date") == today:
            await interaction.followup.send("ℹ️ Hôm nay bạn đã điểm danh rồi! Hãy quay lại sau 00:00 nhé.", ephemeral=True)
            return

        new_streak = 1
        if clan.get("last_checkin_date") == yesterday:
            new_streak = (clan.get("checkin_streak") or 0) + 1

        clan_exp_to_add = EXP_REWARDS.CHECKIN_EXP
        is_streak_7 = (new_streak % 7 == 0)
        if is_streak_7:
            clan_exp_to_add += EXP_REWARDS.CHECKIN_STREAK_7_BONUS_EXP

        await self.bot.db.update_checkin(interaction.guild_id, interaction.user.id, today, new_streak)
        await self.bot.db.add_clan_exp(clan["clan_id"], clan_exp_to_add, clan_exp_to_add)

        week_key = get_current_week_key()
        quest_res = await self.bot.db.increment_quest_progress(clan["clan_id"], week_key, "CHECKIN_COUNT", 1)
        if quest_res["completed_now"]:
            await self.bot.db.add_clan_exp(clan["clan_id"], quest_res["reward_exp"], quest_res["reward_exp"])

        await interaction.followup.send(
            f"🎉 **Điểm danh thành công!**\n"
            f"• Chuỗi streak: **{new_streak} ngày** {'🎁 *(Thưởng thêm +50 EXP mốc 7 ngày!)*' if is_streak_7 else ''}\n"
            f"• Băng nhận: **+{clan_exp_to_add} EXP** • Cá nhân nhận: **+10 Điểm cống hiến**",
            ephemeral=True
        )

    @ui.button(label="Cài Đặt", emoji="⚙️", style=discord.ButtonStyle.secondary, custom_id="clan_quick_settings_btn")
    async def settings_btn(self, interaction: discord.Interaction, button: ui.Button):
        clan = await self.bot.db.get_clan_by_id(self.clan_id)
        if not clan or int(clan["leader_id"]) != interaction.user.id:
            await interaction.response.send_message("❌ Chỉ Chủ Băng mới có quyền truy cập cài đặt!", ephemeral=True)
            return
        view = SettingsDashboardView(clan=clan, bot=self.bot)
        await interaction.response.send_message("⚙️ Bảng điều khiển cài đặt băng:", view=view, ephemeral=True)


class WelcomeGreetingView(ui.View):
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


class CustomTitleModal(ui.Modal):
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


class ClanCustomTitleMemberSelectView(ui.View):
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

        from utils.canvas import generate_clan_profile_image
        buf = await asyncio.to_thread(generate_clan_profile_image, clan, len(members), level_info)
        file = discord.File(fp=buf, filename="clan_profile.png")
        embed = build_clan_info_embed(clan, members, level_info, attachment_filename="clan_profile.png")
        if clan.get("logo_url"):
            embed.set_thumbnail(url=clan["logo_url"])

        view = ClanDetailView(clan=clan, can_apply=can_apply, is_member=is_member, is_leader=is_leader, bot=self.bot)
        await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)


class ClanDetailView(ui.View):
    """View hiển thị hồ sơ chi tiết của băng được chọn từ danh sách"""
    def __init__(self, clan: Dict[str, Any], can_apply: bool, is_member: bool, is_leader: bool, bot):
        super().__init__(timeout=180)
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
        embed, total_pages = build_members_embed(self.clan, members, page=1, page_size=10)
        view = MembersPaginationView(clan_id=self.clan["clan_id"], current_page=1, total_pages=total_pages, current_filter="ALL", bot=self.bot)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


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


class QuickApplySelectView(ui.View):
    """View phụ chứa Dropdown nộp đơn nhanh"""
    def __init__(self, clans: List[Dict[str, Any]], bot):
        super().__init__(timeout=120)
        self.add_item(QuickApplyDropdown(clans=clans, bot=bot))


class ClanListInteractiveView(ui.View):
    """View tương tác cho Bảng danh mục Băng Đảng kèm Dropdown và Nút Lập Băng Mới"""
    def __init__(self, clans: List[Dict[str, Any]], bot):
        super().__init__(timeout=180)
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
        await interaction.response.defer(ephemeral=True)
        from utils.canvas import generate_leaderboard_image
        clans = await self.bot.db.get_leaderboard(interaction.guild_id, criteria="level", limit=10)
        buf = await asyncio.to_thread(generate_leaderboard_image, interaction.guild.name, clans, "level")
        file = discord.File(fp=buf, filename="leaderboard.png")
        embed = build_leaderboard_embed(interaction.guild.name, clans, criteria="level", attachment_filename="leaderboard.png")
        view = LeaderboardInteractiveView(guild_name=interaction.guild.name, bot=self.bot, initial_criteria="level")
        await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)


# =============================================================================
# BẢNG XẾP HẠNG TƯƠNG TÁC (LEADERBOARD INTERACTIVE VIEW)
# =============================================================================

class LeaderboardInteractiveView(ui.View):
    """View tương tác động chuyển đổi giữa các tiêu chí Bảng Xếp Hạng Server"""
    def __init__(self, guild_name: str, bot, initial_criteria: str = "level"):
        super().__init__(timeout=180)
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


# =============================================================================
# RỜI BĂNG TỰ NGUYỆN (LEAVE CLAN CONFIRM VIEW)
# =============================================================================

class LeaveClanConfirmView(ui.View):
    """View xác nhận 2 lớp cho việc tự nguyện rời băng"""
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__(timeout=60)
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

class KickMemberModal(ui.Modal):
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


class KickSelectView(ui.View):
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


class PromoteSelectView(ui.View):
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


class DemoteSelectView(ui.View):
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


class TransferLeaderSelectView(ui.View):
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
            title="💌 LỜI MỜI GIA NHẬP BĂNG ĐẢNG",
            description=f"Chào {target_user.mention}!\nBạn vừa nhận được lời mời gia nhập băng **[{clan['tag']}] {clan['name']}** từ Cán Bộ <@{inviter.id}>.",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="🏰 Tên Băng", value=f"[{clan['tag']}] {clan['name']}", inline=True)
        embed.add_field(name="👑 Chủ Băng", value=f"<@{clan['leader_id']}>", inline=True)
        embed.add_field(name="📜 Khẩu Hiệu", value=clan.get("description") or "Chưa có khẩu hiệu.", inline=False)
        embed.add_field(name="⏳ Hạn Chót", value=f"Lời mời tự hết hạn vào: <t:{expires_at}:R>", inline=False)
        embed.set_footer(text="Bấm nút bên dưới để Chấp Nhận hoặc Từ Chối")

        view = RequestView(request_id=req_id, bot=self.bot, is_invite=True)
        clan_text_ch = guild.get_channel(int(clan["text_channel_id"])) if clan.get("text_channel_id") else None
        target_ch = clan_text_ch or interaction.channel
        msg = await target_ch.send(content=target_user.mention, embed=embed, view=view)
        await self.bot.db.update_request_message_id(req_id, msg.id)

        # Gửi DM thông báo nhận lời mời
        dm_invite = discord.Embed(
            title="💌 BẠN NHẬN ĐƯỢC LỜI MỜI VÀO BĂNG",
            description=f"Cán Bộ <@{inviter.id}> đã gửi lời mời bạn gia nhập băng **[{clan['tag']}] {clan['name']}** tại máy chủ **{guild.name}**!",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        dm_invite.add_field(name="🏰 Tên Băng", value=f"[{clan['tag']}] {clan['name']}", inline=True)
        dm_invite.add_field(name="👑 Chủ Băng", value=f"<@{clan['leader_id']}>", inline=True)
        dm_invite.add_field(name="⏳ Hạn Lời Mời", value=f"<t:{expires_at}:R>", inline=True)
        dm_invite.add_field(name="👉 Thao Tác", value=f"Hãy vào kênh <#{target_ch.id}> trên máy chủ **{guild.name}** để bấm nút [✅ Chấp Nhận Lời Mời] nhé!", inline=False)
        dm_invite.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
        await send_dm_notification(target_user, dm_invite)

        await interaction.followup.send(f"✅ Đã gửi lời mời tham gia băng tới {target_user.mention} thành công!", ephemeral=True)


class ClanMemberManagementView(ui.View):
    """Trung Tâm Điều Khiển Quản Lý Thành Viên & Nhân Sự 1-Click"""
    def __init__(self, clan: Dict[str, Any], user: discord.Member, bot):
        super().__init__(timeout=180)
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


# =============================================================================
# TRUNG TÂM ĐIỀU KHIỂN BĂNG ĐẢNG (CLAN HUB)
# =============================================================================

class ClanHubView(ui.View):
    """Trung Tâm Điều Khiển Băng Đảng Tương Tác 1-Click Dành Cho Thành Viên Cộng Đồng"""
    def __init__(self, user: discord.Member, clan: Optional[Dict[str, Any]], bot):
        super().__init__(timeout=180)
        self.user = user
        self.clan = clan
        self.bot = bot

        if clan:
            self.remove_item(self.list_clans_btn)
            self.remove_item(self.create_clan_btn)
            self.remove_item(self.apply_hub_btn)
            is_leader = int(clan["leader_id"]) == user.id
            is_officer = is_leader or clan.get("rank") in (Ranks.CO_LEADER, Ranks.OFFICER)
            if not is_officer:
                self.remove_item(self.members_mgmt_btn)
                self.remove_item(self.manage_btn)
                self.remove_item(self.role_btn)
                self.remove_item(self.titles_btn)
                self.remove_item(self.logs_btn)
            elif not is_leader and not user.guild_permissions.administrator:
                self.remove_item(self.role_btn)
        else:
            self.remove_item(self.checkin_btn)
            self.remove_item(self.my_clan_btn)
            self.remove_item(self.quests_btn)
            self.remove_item(self.leave_btn)
            self.remove_item(self.manage_btn)
            self.remove_item(self.role_btn)
            self.remove_item(self.milestones_btn)
            self.remove_item(self.wallpaper_btn)
            self.remove_item(self.titles_btn)
            self.remove_item(self.logs_btn)
            self.remove_item(self.members_mgmt_btn)

    @ui.button(label="Điểm Danh Hằng Ngày", emoji="📅", style=discord.ButtonStyle.success, row=0)
    async def checkin_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        from utils.time_helper import get_today_vn_string, get_yesterday_vn_string, get_current_week_key
        from utils.constants import EXP_REWARDS

        clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not clan:
            await interaction.followup.send("❌ Bạn chưa tham gia băng nào!", ephemeral=True)
            return

        today = get_today_vn_string()
        yesterday = get_yesterday_vn_string()
        if clan.get("last_checkin_date") == today:
            await interaction.followup.send("ℹ️ Hôm nay bạn đã điểm danh rồi! Hãy quay lại sau 00:00 nhé.", ephemeral=True)
            return

        new_streak = 1
        if clan.get("last_checkin_date") == yesterday:
            new_streak = (clan.get("checkin_streak") or 0) + 1

        clan_exp_to_add = EXP_REWARDS.CHECKIN_EXP
        is_streak_7 = (new_streak % 7 == 0)
        if is_streak_7:
            clan_exp_to_add += EXP_REWARDS.CHECKIN_STREAK_7_BONUS_EXP

        await self.bot.db.update_checkin(interaction.guild_id, interaction.user.id, today, new_streak)
        await self.bot.db.add_clan_exp(clan["clan_id"], clan_exp_to_add, clan_exp_to_add)

        week_key = get_current_week_key()
        quest_res = await self.bot.db.increment_quest_progress(clan["clan_id"], week_key, "CHECKIN_COUNT", 1)
        if quest_res["completed_now"]:
            await self.bot.db.add_clan_exp(clan["clan_id"], quest_res["reward_exp"], quest_res["reward_exp"])

        await interaction.followup.send(
            f"🎉 **Điểm danh thành công!**\n"
            f"• Chuỗi streak: **{new_streak} ngày** {'🎁 *(Thưởng thêm +50 EXP mốc 7 ngày!)*' if is_streak_7 else ''}\n"
            f"• Băng nhận: **+{clan_exp_to_add} EXP** • Cá nhân nhận: **+10 Điểm cống hiến**",
            ephemeral=True
        )

    @ui.button(label="Nhiệm Vụ Tuần", emoji="🎯", style=discord.ButtonStyle.primary, row=0)
    async def quests_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not self.clan:
            await interaction.followup.send("❌ Bạn chưa tham gia băng nào!", ephemeral=True)
            return
        from utils.time_helper import get_current_week_key
        from utils.embeds import build_quests_embed
        from utils.canvas import generate_quests_image
        week_key = get_current_week_key()
        quests = await self.bot.db.ensure_weekly_quests(self.clan["clan_id"], week_key)
        buf = await asyncio.to_thread(generate_quests_image, self.clan, quests, week_key)
        file = discord.File(fp=buf, filename="quests.png")
        embed = build_quests_embed(self.clan, quests, week_key, attachment_filename="quests.png")
        if self.clan.get("logo_url"):
            embed.set_thumbnail(url=self.clan["logo_url"])
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)

    @ui.button(label="Hồ Sơ Băng Của Bạn", emoji="🏰", style=discord.ButtonStyle.secondary, row=0)
    async def my_clan_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not clan:
            await interaction.followup.send("❌ Bạn chưa tham gia băng nào!", ephemeral=True)
            return

        members = await self.bot.db.get_clan_members(clan["clan_id"])
        level_info = get_level_info(clan["exp"])
        from utils.canvas import generate_clan_profile_image
        buf = await asyncio.to_thread(generate_clan_profile_image, clan, len(members), level_info)
        file = discord.File(fp=buf, filename="clan_profile.png")
        embed = build_clan_info_embed(clan, members, level_info, attachment_filename="clan_profile.png")
        if clan.get("logo_url"):
            embed.set_thumbnail(url=clan["logo_url"])
        view = ClanInfoView(clan_id=clan["clan_id"], can_apply=False, is_member=True, is_leader=(int(clan["leader_id"]) == interaction.user.id), bot=self.bot)
        await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)

    @ui.button(label="Rời Băng", emoji="🚪", style=discord.ButtonStyle.danger, row=3)
    async def leave_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not self.clan:
            await interaction.response.send_message("❌ Bạn chưa tham gia băng nào!", ephemeral=True)
            return
        if int(self.clan["leader_id"]) == interaction.user.id:
            await interaction.response.send_message(
                "❌ **Bạn đang là Chủ Băng!** Bạn không thể tự ý rời băng.\n"
                "👉 Hãy chuyển giao quyền Chủ Băng cho người khác (trong **Quản Lý Thành Viên**) hoặc **Giải Tán Băng** (trong **Cài Đặt Băng**).",
                ephemeral=True
            )
            return
        view = LeaveClanConfirmView(clan=self.clan, bot=self.bot)
        await interaction.response.send_message(
            f"⚠️ Bạn có chắc chắn muốn rời khỏi băng **[{self.clan['tag']}] {self.clan['name']}** không?\n"
            f"*(Sau khi rời, bạn sẽ phải chờ 24 giờ mới có thể vào hoặc lập băng mới)*",
            view=view,
            ephemeral=True
        )

    @ui.button(label="Bảng Xếp Hạng Server", emoji="🏆", style=discord.ButtonStyle.secondary, row=1)
    async def leaderboard_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        from utils.canvas import generate_leaderboard_image
        clans = await self.bot.db.get_leaderboard(interaction.guild_id, criteria="level", limit=10)
        buf = await asyncio.to_thread(generate_leaderboard_image, interaction.guild.name, clans, "level")
        file = discord.File(fp=buf, filename="leaderboard.png")
        embed = build_leaderboard_embed(interaction.guild.name, clans, criteria="level", attachment_filename="leaderboard.png")
        view = LeaderboardInteractiveView(guild_name=interaction.guild.name, bot=self.bot, initial_criteria="level")
        await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)

    @ui.button(label="Cột Mốc Lịch Sử", emoji="📜", style=discord.ButtonStyle.secondary, row=1)
    async def milestones_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not self.clan:
            await interaction.followup.send("❌ Bạn chưa tham gia băng nào!", ephemeral=True)
            return
        from utils.embeds import build_milestones_embed
        milestones = await self.bot.db.get_clan_milestones(self.clan["clan_id"], limit=10)
        embed = build_milestones_embed(self.clan, milestones)
        if self.clan.get("logo_url"):
            embed.set_thumbnail(url=self.clan["logo_url"])
        await interaction.followup.send(embed=embed, ephemeral=True)

    @ui.button(label="Ảnh Nền Băng (Full HD)", emoji="🖼️", style=discord.ButtonStyle.secondary, row=1)
    async def wallpaper_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not self.clan:
            await interaction.followup.send("❌ Bạn chưa tham gia băng nào!", ephemeral=True)
            return
        from utils.canvas import generate_clan_wallpaper
        members = await self.bot.db.get_clan_members(self.clan["clan_id"])
        milestones = await self.bot.db.get_clan_milestones(self.clan["clan_id"], limit=5)
        buf = await asyncio.to_thread(generate_clan_wallpaper, self.clan, members, milestones)
        file = discord.File(fp=buf, filename="clan_wallpaper.png")
        embed = discord.Embed(
            title=f"🖼️ HÌNH NỀN DESKTOP BĂNG [{self.clan['tag']}] {self.clan['name']}",
            description="Tác phẩm đồ họa Full HD 1920x1080 ghi lại dấu ấn, thành viên chủ chốt và biên niên sử hào hùng của băng!",
            color=discord.Color.from_str(self.clan.get("color_hex") or "#5865F2"),
            timestamp=datetime.now()
        )
        embed.set_image(url="attachment://clan_wallpaper.png")
        embed.set_footer(text="Gợi ý: Nhấn vào ảnh và chọn 'Open in Browser' để tải về ảnh gốc chất lượng cao nhất!")
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)

    @ui.button(label="Nhật Ký Băng", emoji="📜", style=discord.ButtonStyle.secondary, row=1)
    async def logs_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not self.clan:
            await interaction.followup.send("❌ Bạn chưa tham gia băng nào!", ephemeral=True)
            return
        is_leader = int(self.clan["leader_id"]) == interaction.user.id
        is_officer = is_leader or self.clan.get("rank") in (Ranks.CO_LEADER, Ranks.OFFICER)
        if not is_officer and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Chỉ Cán Bộ, Phó Băng hoặc Chủ Băng mới có quyền xem nhật ký băng!", ephemeral=True)
            return
        from utils.embeds import build_logs_embed
        logs_data = await self.bot.db.get_clan_logs(self.clan["clan_id"], page=1, page_size=10)
        embed = build_logs_embed(self.clan, logs_data["logs"], page=1, total_pages=logs_data["total_pages"])
        view = LogsPaginationView(clan_id=self.clan["clan_id"], current_page=1, total_pages=logs_data["total_pages"], bot=self.bot)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @ui.button(label="Nộp Đơn Vào Băng", emoji="📩", style=discord.ButtonStyle.primary, row=1)
    async def apply_hub_btn(self, interaction: discord.Interaction, button: ui.Button):
        existing = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if existing:
            await interaction.response.send_message(f"❌ Bạn đã là thành viên của băng **{existing['name']}** rồi!", ephemeral=True)
            return

        clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        if not clans:
            await interaction.response.send_message("❌ Máy chủ hiện chưa có băng nào đang hoạt động!", ephemeral=True)
            return

        if len(clans) == 1:
            clan = await self.bot.db.get_clan_by_id(clans[0]["clan_id"])
            if not clan:
                await interaction.response.send_message("❌ Băng không tồn tại hoặc vừa bị giải tán!", ephemeral=True)
                return
            modal = ApplyClanModal(clan=clan, bot=self.bot)
            await interaction.response.send_modal(modal)
        else:
            view = QuickApplySelectView(clans=clans, bot=self.bot)
            await interaction.response.send_message("📩 **Hãy chọn băng bạn muốn nộp đơn gia nhập bên dưới:**", view=view, ephemeral=True)

    @ui.button(label="Quản Lý Thành Viên", emoji="👥", style=discord.ButtonStyle.primary, row=2)
    async def members_mgmt_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not self.clan:
            await interaction.response.send_message("❌ Bạn chưa tham gia băng nào!", ephemeral=True)
            return
        is_leader = int(self.clan["leader_id"]) == interaction.user.id
        is_officer = is_leader or self.clan.get("rank") in (Ranks.CO_LEADER, Ranks.OFFICER)
        if not is_officer and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Chỉ Cán Bộ hoặc Chủ Băng mới có quyền truy cập Quản Lý Thành Viên!", ephemeral=True)
            return
        view = ClanMemberManagementView(clan=self.clan, user=interaction.user, bot=self.bot)
        await interaction.response.send_message("👥 **BẢNG ĐIỀU KHIỂN QUẢN LÝ THÀNH VIÊN & NHÂN SỰ BĂNG:**", view=view, ephemeral=True)

    @ui.button(label="Trao Danh Hiệu", emoji="🎖️", style=discord.ButtonStyle.primary, row=2)
    async def titles_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not self.clan:
            await interaction.response.send_message("❌ Bạn chưa tham gia băng nào!", ephemeral=True)
            return
        is_leader = int(self.clan["leader_id"]) == interaction.user.id
        is_officer = is_leader or self.clan.get("rank") in (Ranks.CO_LEADER, Ranks.OFFICER)
        if not is_officer and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Chỉ Cán Bộ, Phó Băng hoặc Chủ Băng mới có quyền trao danh hiệu nội bộ!", ephemeral=True)
            return
        members = await self.bot.db.get_clan_members(self.clan["clan_id"])
        if not members:
            await interaction.response.send_message("❌ Băng chưa có thành viên!", ephemeral=True)
            return
        view = ClanCustomTitleMemberSelectView(clan=self.clan, members=members, guild=interaction.guild, bot=self.bot)
        await interaction.response.send_message("🎖️ **Chọn thành viên để trao hoặc chỉnh sửa danh hiệu nội bộ:**", view=view, ephemeral=True)

    @ui.button(label="Cài Đặt Băng", emoji="⚙️", style=discord.ButtonStyle.secondary, row=2)
    async def manage_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not self.clan:
            return
        view = SettingsDashboardView(clan=self.clan, bot=self.bot)
        await interaction.response.send_message("⚙️ Bảng điều khiển cài đặt băng:", view=view, ephemeral=True)

    @ui.button(label="Cài Đặt Role", emoji="🛡️", style=discord.ButtonStyle.secondary, row=2)
    async def role_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not self.clan:
            return
        is_leader = int(self.clan["leader_id"]) == interaction.user.id
        if not is_leader and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Chỉ Chủ Băng hoặc Quản Trị Viên mới có quyền thiết lập Role!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        role = interaction.guild.get_role(int(self.clan["role_id"])) if self.clan.get("role_id") else None
        from utils.canvas import generate_role_setup_image
        buf = await asyncio.to_thread(
            generate_role_setup_image,
            self.clan,
            role.name if role else f"[{self.clan['tag']}] {self.clan['name']}",
            self.clan.get("color_hex") or "#5865F2",
            self.clan.get("secondary_color_hex"),
            role.hoist if role else True,
            role.mentionable if role else True
        )
        file = discord.File(fp=buf, filename="role_setup.png")
        embed = build_role_setup_embed(self.clan, role, attachment_filename="role_setup.png")
        view = ClanRoleSetupView(clan=self.clan, bot=self.bot)
        await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)

    @ui.button(label="Xem Danh Sách Băng Mở Tuyển", emoji="📜", style=discord.ButtonStyle.primary, row=0)
    async def list_clans_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        from utils.embeds import build_clan_list_embed
        clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        embed = build_clan_list_embed(interaction.guild.name, clans)
        view = ClanListInteractiveView(clans=clans, bot=self.bot)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @ui.button(label="Thành Lập Băng Mới", emoji="✨", style=discord.ButtonStyle.success, row=0)
    async def create_clan_btn(self, interaction: discord.Interaction, button: ui.Button):
        modal = CreateClanModal(bot=self.bot)
        await interaction.response.send_modal(modal)


class RejectRequestModal(ui.Modal):
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


class RequestView(ui.View):
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
        guild = interaction.guild

        if decision == "ACCEPTED":
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
                inviter = guild.get_member(int(req["actor_id"]))
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
                inviter = guild.get_member(int(req["actor_id"]))
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

        res_msg = f"✅ Đã chấp nhận <@{req['user_id']}> vào băng **{clan['name']}**!" if decision == "ACCEPTED" else f"❌ Đã từ chối yêu cầu của <@{req['user_id']}>."
        await interaction.followup.send(res_msg, ephemeral=True)


class PartyView(ui.View):
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


class SettingsDashboardView(ui.View):
    """Bảng điều khiển Ephemeral cài đặt băng"""
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__(timeout=180)
        self.clan = clan
        self.bot = bot

    @ui.select(
        placeholder="⚙️ Chọn mục cài đặt bạn muốn chỉnh sửa...",
        options=[
            discord.SelectOption(label="Quản Lý Thành Viên & Nhân Sự", value="member_mgmt", emoji="👥", description="Mời người mới, thăng chức, giáng chức, trục xuất, chuyển quyền"),
            discord.SelectOption(label="Đổi Tên / Tag / Khẩu Hiệu", value="rename", emoji="✏️", description="Chỉnh sửa thông tin định danh (cooldown 7 ngày)"),
            discord.SelectOption(label="Cài Đặt Role Băng (Màu sắc, Tên, Hoist...)", value="role_setup", emoji="🛡️", description="Đổi màu, đổi tên, bật tách nhóm hoist hoặc chọn role server"),
            discord.SelectOption(label="Cập Nhật Logo & Banner", value="images", emoji="🖼️", description="Cài link ảnh hiển thị hồ sơ (Banner cần Lv.2+)"),
            discord.SelectOption(label="Chế Độ Tuyển Quân", value="join_mode", emoji="🚪", description="Mở Tự Do / Cần Duyệt / Chỉ Nhận Lời Mời"),
            discord.SelectOption(label="Giải Tán Băng Đảng", value="disband", emoji="💥", description="Giải tán băng vĩnh viễn (Chỉ Chủ Băng, bảo mật 2 lớp)")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: ui.Select):
        val = select.values[0]
        if val == "member_mgmt":
            view = ClanMemberManagementView(clan=self.clan, user=interaction.user, bot=self.bot)
            await interaction.response.send_message("👥 **Bảng Quản Lý Nhân Sự & Thành Viên Băng:**", view=view, ephemeral=True)
        elif val == "rename":
            modal = RenameClanModal(clan=self.clan, bot=self.bot)
            await interaction.response.send_modal(modal)
        elif val in ("color", "role_setup"):
            role = interaction.guild.get_role(int(self.clan["role_id"])) if self.clan.get("role_id") else None
            embed = build_role_setup_embed(self.clan, role)
            view = ClanRoleSetupView(clan=self.clan, bot=self.bot)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        elif val == "images":
            modal = ImagesClanModal(clan=self.clan, bot=self.bot)
            await interaction.response.send_modal(modal)
        elif val == "join_mode":
            view = JoinModeSelectView(clan_id=self.clan["clan_id"], current_mode=self.clan["join_mode"], bot=self.bot)
            await interaction.response.send_message("🚪 Chọn chế độ tuyển quân mới cho băng:", view=view, ephemeral=True)
        elif val == "disband":
            if int(self.clan["leader_id"]) != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ Chỉ có Chủ Băng mới có quyền giải tán băng!", ephemeral=True)
                return
            modal = DisbandClanModal(clan=self.clan, bot=self.bot)
            await interaction.response.send_modal(modal)


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
        await interaction.response.defer(ephemeral=True)
        selected_role: discord.Role = self.values[0]
        view: "ClanRoleSetupView" = self.view
        guild = interaction.guild

        if selected_role.is_default():
            await interaction.followup.send("❌ Không thể chọn Role `@everyone` làm Role Băng!", ephemeral=True)
            return

        if selected_role.managed:
            await interaction.followup.send("❌ Không thể chọn Role tự động của Bot khác làm Role Băng!", ephemeral=True)
            return

        if selected_role >= guild.me.top_role:
            await interaction.followup.send(
                f"⚠️ **Không thể gán Role {selected_role.mention}!**\n\n"
                "👉 Role này đang nằm **cao hơn hoặc bằng** vị trí Role của Bot trong máy chủ.\n"
                "Vui lòng vào **Server Settings -> Roles** và kéo Role của Bot lên vị trí cao hơn.",
                ephemeral=True
            )
            return

        old_role_id = view.clan.get("role_id")
        old_role = guild.get_role(int(old_role_id)) if old_role_id else None

        # Cập nhật quyền trên Text & Voice Channels
        for ch_key in ("text_channel_id", "voice_channel_id", "extra_voice_channel_id"):
            ch_id = view.clan.get(ch_key)
            if ch_id:
                ch = guild.get_channel(int(ch_id))
                if ch:
                    try:
                        if old_role:
                            await ch.set_permissions(old_role, overwrite=None, reason="Đổi role clan")
                        await ch.set_permissions(
                            selected_role,
                            view_channel=True,
                            send_messages=True,
                            embed_links=True,
                            attach_files=True,
                            read_message_history=True,
                            connect=True,
                            speak=True,
                            use_voice_activation=True,
                            reason="Gán role mới cho clan"
                        )
                    except Exception as ch_err:
                        logger.warning(f"Lỗi cập nhật quyền kênh: {ch_err}")

        # Cấp role mới cho toàn bộ thành viên hiện tại của clan
        members = await view.bot.db.get_clan_members(view.clan["clan_id"])
        for m in members:
            try:
                target_mem = guild.get_member(int(m["user_id"])) or await guild.fetch_member(int(m["user_id"]))
                if target_mem:
                    await target_mem.add_roles(selected_role, reason="Chuyển role clan")
            except Exception:
                pass

        hex_color = f"#{selected_role.color.value:06X}" if selected_role.color.value else "#5865F2"
        await view.bot.db.update_clan(
            view.clan["clan_id"],
            role_id=str(selected_role.id),
            color_hex=hex_color,
            secondary_color_hex=None
        )
        await view.bot.db.add_clan_log(
            clan_id=view.clan["clan_id"],
            actor_id=interaction.user.id,
            action="LINK_ROLE",
            details=f"Liên kết role mới {selected_role.name} ({selected_role.id})."
        )

        view.clan["role_id"] = str(selected_role.id)
        view.clan["color_hex"] = hex_color
        view.clan["secondary_color_hex"] = None

        new_embed = build_role_setup_embed(view.clan, selected_role)
        try:
            await interaction.message.edit(embed=new_embed, view=view)
        except Exception:
            pass

        await interaction.followup.send(
            f"✅ **Đã liên kết thành công Role mới cho Băng:** {selected_role.mention}!\n"
            f"• Toàn bộ quyền truy cập kênh riêng đã được chuyển giao cho Role mới.\n"
            f"• Role mới đã được tự động cấp cho các thành viên trong băng.",
            ephemeral=True
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
        await interaction.response.defer(ephemeral=True)
        chosen_pair = self.values[0]
        start_hex, end_hex = chosen_pair.split(":")
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

            new_embed = build_role_setup_embed(view.clan, role)
            try:
                await interaction.message.edit(embed=new_embed, view=view)
            except Exception:
                pass

            await interaction.followup.send(
                f"🌈 **Đã áp dụng màu Gradient thành công!**\n"
                f"• Dải màu: **{start_hex}** ➔ **{end_hex}**\n"
                f"*(Màu gradient hiển thị chuyển sắc tuyệt đẹp trên danh sách thành viên!)*",
                ephemeral=True
            )
        except (discord.HTTPException, discord.InvalidArgument) as err:
            logger.warning(f"Không thể áp dụng gradient (server có thể chưa đủ boost): {err}")
            # Fallback sang màu đơn sắc chính nếu server chưa đủ boost
            try:
                await role.edit(color=start_color, secondary_color=None, reason=f"Đổi màu Role đơn sắc (fallback): {interaction.user.name}")
                await view.bot.db.update_clan(view.clan["clan_id"], color_hex=start_hex, secondary_color_hex=None)
                view.clan["color_hex"] = start_hex
                view.clan["secondary_color_hex"] = None
                new_embed = build_role_setup_embed(view.clan, role)
                try:
                    await interaction.message.edit(embed=new_embed, view=view)
                except Exception:
                    pass

                await interaction.followup.send(
                    f"⚠️ **Server của bạn chưa mở tính năng màu Gradient 2 màu (Yêu cầu Server Boost)!**\n"
                    f"👉 Bot đã tự động áp dụng **màu đơn sắc chính {start_hex}** cho Role của bạn.",
                    ephemeral=True
                )
            except Exception as fb_err:
                await interaction.followup.send(f"❌ Lỗi khi đổi màu role: `{fb_err}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi đổi màu role: `{e}`", ephemeral=True)


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
        await interaction.response.defer(ephemeral=True)
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

            new_embed = build_role_setup_embed(view.clan, role)
            try:
                await interaction.message.edit(embed=new_embed, view=view)
            except Exception:
                pass

            await interaction.followup.send(f"🎨 Đã đổi màu Role thành công sang mã màu: **{chosen_hex}**!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Bot bị thiếu quyền `Manage Roles` để đổi màu role!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi đổi màu role: `{e}`", ephemeral=True)


class ClanRoleSetupView(ui.View):
    """Bảng điều khiển tương tác toàn diện cài đặt & tùy biến Role Băng"""
    def __init__(self, clan: Dict[str, Any], bot):
        super().__init__(timeout=180)
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
        await interaction.response.defer(ephemeral=True)
        role = interaction.guild.get_role(int(self.clan["role_id"])) if self.clan.get("role_id") else None
        if not role:
            await interaction.followup.send("❌ Không tìm thấy Role của băng trên server!", ephemeral=True)
            return

        if role >= interaction.guild.me.top_role:
            await interaction.followup.send("⚠️ Role này nằm cao hơn hoặc bằng Role của Bot!", ephemeral=True)
            return

        try:
            new_hoist = not role.hoist
            await role.edit(hoist=new_hoist, reason=f"Chủ Băng bật/tắt hoist: {interaction.user.name}")
            new_embed = build_role_setup_embed(self.clan, role)
            try:
                await interaction.message.edit(embed=new_embed, view=self)
            except Exception:
                pass
            status_text = "**BẬT** (Hiển thị riêng trên danh sách thành viên)" if new_hoist else "**TẮT** (Gộp chung với nhóm thông thường)"
            await interaction.followup.send(f"📌 Đã chuyển trạng thái Tách nhóm (Hoist) sang: {status_text}!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi đổi trạng thái Hoist: `{e}`", ephemeral=True)

    @ui.button(label="Cho Phép Tag", emoji="🔔", style=discord.ButtonStyle.secondary, row=4)
    async def toggle_mention_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        role = interaction.guild.get_role(int(self.clan["role_id"])) if self.clan.get("role_id") else None
        if not role:
            await interaction.followup.send("❌ Không tìm thấy Role của băng trên server!", ephemeral=True)
            return

        if role >= interaction.guild.me.top_role:
            await interaction.followup.send("⚠️ Role này nằm cao hơn hoặc bằng Role của Bot!", ephemeral=True)
            return

        try:
            new_mention = not role.mentionable
            await role.edit(mentionable=new_mention, reason=f"Chủ Băng bật/tắt mention: {interaction.user.name}")
            new_embed = build_role_setup_embed(self.clan, role)
            try:
                await interaction.message.edit(embed=new_embed, view=self)
            except Exception:
                pass
            status_text = "**BẬT** (Bất kỳ ai cũng có thể tag role này)" if new_mention else "**TẮT** (Chỉ ai có quyền đặc biệt mới tag được)"
            await interaction.followup.send(f"🔔 Đã chuyển trạng thái Cho phép Tag sang: {status_text}!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi đổi trạng thái Cho phép Tag: `{e}`", ephemeral=True)

    @ui.button(label="Tải Icon Role", emoji="🖼️", style=discord.ButtonStyle.primary, row=4)
    async def upload_icon_guide_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            "🌟 **HƯỚNG DẪN TẢI ICON CHO ROLE BĂNG (YÊU CẦU BOOST CẤP 2)**\n\n"
            "👉 Hãy dùng Slash Command sau để tải ảnh từ máy tính hoặc điện thoại lên làm Icon Role:\n"
            "**`/clan upload-image loai:role_icon file:[chọn ảnh của bạn]`**\n\n"
            "• Icon sẽ hiển thị ngay cạnh tên của toàn thể anh em trong danh sách server!\n"
            "• Định dạng khuyến nghị: Ảnh vuông (PNG/JPG), kích thước dưới 256KB.",
            ephemeral=True
        )



class JoinModeSelectView(ui.View):
    """View chọn chế độ tuyển quân"""
    def __init__(self, clan_id: int, current_mode: str, bot):
        super().__init__(timeout=60)
        self.clan_id = clan_id
        self.bot = bot

        options = [
            discord.SelectOption(label="🟢 Mở Tự Do (OPEN)", value="OPEN", default=(current_mode == "OPEN"), description="Ai xin vào cũng được duyệt ngay lập tức"),
            discord.SelectOption(label="🟡 Cần Duyệt (APPROVAL - Mặc định)", value="APPROVAL", default=(current_mode == "APPROVAL"), description="Gửi đơn vào kênh riêng để cán bộ xem xét"),
            discord.SelectOption(label="🔒 Chỉ Nhận Lời Mời (INVITE_ONLY)", value="INVITE_ONLY", default=(current_mode == "INVITE_ONLY"), description="Khóa nộp đơn, chỉ cán bộ mời mới vào được")
        ]
        self.select_menu.options = options

    @ui.select(placeholder="Chọn chế độ tuyển...")
    async def select_menu(self, interaction: discord.Interaction, select: ui.Select):
        await interaction.response.defer(ephemeral=True)
        chosen = select.values[0]
        await self.bot.db.update_clan(self.clan_id, join_mode=chosen)
        await self.bot.db.add_clan_log(
            clan_id=self.clan_id,
            actor_id=interaction.user.id,
            action="UPDATE_JOIN_MODE",
            details=f"Đổi chế độ tuyển quân sang {chosen}."
        )
        await interaction.followup.send(f"✅ Đã đổi chế độ tuyển quân thành: **{chosen}**!", ephemeral=True)


class MembersPaginationView(ui.View):
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

    async def _change_page(self, interaction: discord.Interaction, new_page: int):
        await interaction.response.defer()
        rank_filter = None if self.current_filter == "ALL" else self.current_filter
        clan = await self.bot.db.get_clan_by_id(self.clan_id)
        members = await self.bot.db.get_clan_members(self.clan_id, rank_filter=rank_filter)
        embed, total_pages = build_members_embed(clan, members, page=new_page, page_size=10, rank_filter=rank_filter)
        view = MembersPaginationView(self.clan_id, new_page, total_pages, self.current_filter, self.bot)
        await interaction.edit_original_response(embed=embed, view=view)


class LogsPaginationView(ui.View):
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

    async def _change_page(self, interaction: discord.Interaction, new_page: int):
        await interaction.response.defer()
        clan = await self.bot.db.get_clan_by_id(self.clan_id)
        data = await self.bot.db.get_clan_logs(self.clan_id, page=new_page, page_size=10)
        embed = build_logs_embed(clan, data["logs"], page=new_page, total_pages=self.total_pages)
        view = LogsPaginationView(self.clan_id, new_page, self.total_pages, self.bot)
        await interaction.edit_original_response(embed=embed, view=view)


class TransferConfirmView(ui.View):
    """View xác nhận chuyển giao quyền Chủ Băng (30 giây)"""
    def __init__(self, clan: Dict[str, Any], old_leader_id: int, new_leader_id: int, bot):
        super().__init__(timeout=30)
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


class ForceDeleteConfirmView(ui.View):
    """View xác nhận 2 lớp cho lệnh /clan-admin force-delete"""
    def __init__(self, clan: Dict[str, Any], reason: str, bot):
        super().__init__(timeout=60)
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
        for ch_key in ("text_channel_id", "voice_channel_id", "extra_voice_channel_id"):
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
