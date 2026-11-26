"""
Cog Bộ Lệnh Chính Của Băng Đảng (/clan)
Bao gồm toàn bộ các nhóm lệnh: Khởi tạo, Cài đặt, Nhân sự, Tra cứu & Hoạt động
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal
from datetime import datetime
import asyncio
import time

from utils.constants import (
    Ranks,
    JoinModes,
    RANK_WEIGHTS,
    RANK_NAMES,
    RANK_LIMITS,
    EXP_REWARDS
)
from utils.embeds import (
    build_clan_info_embed,
    build_members_embed,
    build_clan_list_embed,
    build_leaderboard_embed,
    build_quests_embed,
    build_logs_embed,
    build_party_embed,
    build_role_setup_embed,
    get_level_info,
    BoardAssets,
    send_dm_notification
)
from utils.ui_components import (
    CreateClanModal,
    SettingsDashboardView,
    DisbandClanModal,
    ApplyClanModal,
    ClanInfoView,
    RequestView,
    PartyView,
    TransferConfirmView,
    MembersPaginationView,
    LogsPaginationView,
    ClanHubView,
    WelcomeGreetingView,
    ClanRoleSetupView,
    ClanQuickPartyModal
)
from utils.time_helper import (
    get_today_vn_string,
    get_yesterday_vn_string,
    get_current_week_key,
    parse_scheduled_time
)
from utils.logger import setup_logging

logger = setup_logging("ClanCommands")

async def clan_name_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Gợi ý tự động tên và tag của các băng đảng trong server khi người dùng gõ phím"""
    try:
        clans = await interaction.client.db.get_all_clans_in_guild(interaction.guild_id)
        choices = []
        clean = current.lower().strip()
        for c in clans:
            label = f"[{c['tag']}] {c['name']} (Lv.{c['level']})"[:100]
            if not clean or clean in c["name"].lower() or clean in c["tag"].lower() or clean in label.lower():
                choices.append(app_commands.Choice(name=label, value=c["name"]))
                if len(choices) >= 25:
                    break
        return choices
    except Exception:
        return []


class ClanHelpView(discord.ui.View):
    """View hướng dẫn sử dụng tương tác đa tầng cho người dùng không rành dev"""
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.select(
        placeholder="📖 Chọn mục bạn muốn xem hướng dẫn...",
        options=[
            discord.SelectOption(label="👑 Dành Cho Quản Trị Viên (Admin)", value="admin", emoji="👑", description="Cách thiết lập server, quản lý và đồng bộ băng"),
            discord.SelectOption(label="🏰 Dành Cho Chủ Băng & Cán Bộ", value="officer", emoji="🏰", description="Cách tạo băng, tuyển quân, quản lý và thăng chức"),
            discord.SelectOption(label="👤 Dành Cho Thành Viên & Người Mới", value="member", emoji="👤", description="Cách xin vào băng, điểm danh, tạo kèo chơi chung"),
            discord.SelectOption(label="❓ Khắc Phục Sự Cố & Lưu Ý Quan Trọng", value="faq", emoji="❓", description="Lỗi quyền, lỗi role, thời gian cooldown")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        chosen = select.values[0]
        if chosen == "admin":
            embed = discord.Embed(
                title="👑 HƯỚNG DẪN DÀNH CHO ADMIN SERVER",
                description=(
                    "**1. Thiết lập Category & Kênh Log:**\n"
                    "• Dùng `/clan-admin setup` để chỉ định Category chứa kênh các băng và kênh ghi nhật ký.\n"
                    "• *Mẹo:* Nếu không cấu hình trước, khi Admin gõ `/clan create`, bot sẽ **tự động tạo** Category `🏰 BĂNG ĐẢNG` và kênh Log cho bạn!\n\n"
                    "**2. Thứ bậc Role (Rất quan trọng):**\n"
                    "• Vào *Server Settings -> Roles*, **kéo Role của Bot lên trên cùng** (hoặc cao hơn các Role Băng) để bot có quyền tạo và cấp role.\n\n"
                    "**3. Khôi phục tự động khi có lỗi:**\n"
                    "• Nếu ai đó lỡ xóa tay Role hoặc Kênh của băng, chỉ cần gõ `/clan-admin sync` là bot tự phục hồi 100%!"
                ),
                color=discord.Color.gold()
            )
        elif chosen == "officer":
            embed = discord.Embed(
                title="🏰 HƯỚNG DẪN DÀNH CHO CHỦ BĂNG & CÁN BỘ",
                description=(
                    "**1. Thành lập băng:** Gõ `/clan create` -> Điền tên (3-25 ký tự) và Tag viết hoa (2-5 ký tự).\n"
                    "**2. Cài đặt & Tùy biến:** Gõ `/clan settings` để đổi màu role, đặt Logo, đặt Banner hoặc đổi chế độ tuyển quân.\n"
                    "**3. Mời thành viên:** Gõ `/clan invite [@user]` để gửi lời mời có nút bấm trực tiếp.\n"
                    "**4. Quản lý chức vụ:**\n"
                    "• `/clan promote [@user]`: Thăng chức (Tối đa 4 Cán Bộ, 2 Phó Băng).\n"
                    "• `/clan demote [@user]`: Giáng chức.\n"
                    "• `/clan transfer [@user]`: Chuyển quyền Chủ Băng cho người khác."
                ),
                color=discord.Color.blue()
            )
        elif chosen == "member":
            embed = discord.Embed(
                title="👤 HƯỚNG DẪN DÀNH CHO THÀNH VIÊN",
                description=(
                    "**1. Xem & Gia nhập băng:**\n"
                    "• `/clan list`: Xem danh sách các băng đang mở tuyển.\n"
                    "• `/clan apply [tên_băng]`: Nộp đơn xin gia nhập (kèm lời nhắn).\n"
                    "• `/clan info [tên_băng]`: Xem thông tin, sĩ số và cấp độ của băng.\n\n"
                    "**2. Hoạt động nhận EXP:**\n"
                    "• `/clan checkin`: Điểm danh mỗi ngày (+30 EXP băng, duy trì chuỗi 7 ngày thưởng thêm +50 EXP).\n"
                    "• **Voice chung:** Cứ 2 thành viên cùng băng ngồi Voice 5 phút được cộng +15 EXP băng.\n"
                    "• **Kênh Chat riêng:** Nhắn tin trò chuyện trong kênh chat băng nhận EXP và cày nhiệm vụ tuần!"
                ),
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❓ CÂU HỎI THƯỜNG GẶP & KHẮC PHỤC SỰ CỐ",
                description=(
                    "**Q: Tôi vừa rời băng, bao giờ mới được vào băng mới?**\n"
                    "• A: Mặc định là **24 giờ** sau khi rời hoặc bị trục xuất để chống nhảy băng spam.\n\n"
                    "**Q: Tại sao bot báo 'Bot bị chặn quyền thao tác Role'?**\n"
                    "• A: Do Role của Bot đang nằm thấp hơn Role Băng trong Server Settings. Hãy kéo Role của Bot lên cao hơn.\n\n"
                    "**Q: Làm sao để mở khóa Kênh Voice thứ 2 cho băng?**\n"
                    "• A: Khi băng đạt **Level 3 (3.500 EXP)**, bot sẽ **tự động tạo thêm** kênh Voice 2 vào Category của băng!"
                ),
                color=discord.Color.orange()
            )
        await interaction.response.edit_message(embed=embed, view=self)


class ClanCommands(commands.Cog):
    """Hệ thống Slash Commands /clan toàn diện"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    clan_group = app_commands.Group(
        name="clan",
        description="Hệ thống lệnh Băng Đảng & Hội Nhóm"
    )

    # =========================================================================
    # NHÓM B: KHỞI TẠO & TÙY BIẾN
    # =========================================================================

    @clan_group.command(name="create", description="Mở hộp thoại tạo một băng đảng mới")
    async def clan_create(self, interaction: discord.Interaction):
        modal = CreateClanModal(bot=self.bot)
        await interaction.response.send_modal(modal)

    @clan_group.command(name="settings", description="Mở bảng điều khiển cài đặt băng đảng (Chỉ Chủ Băng)")
    async def clan_settings(self, interaction: discord.Interaction):
        clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not clan:
            await interaction.response.send_message("❌ Bạn chưa tham gia bất kỳ băng đảng nào!", ephemeral=True)
            return

        is_leader = int(clan["leader_id"]) == interaction.user.id
        if not is_leader and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Chỉ có Chủ Băng (LEADER) mới có quyền truy cập bảng cài đặt!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"⚙️ CÀI ĐẶT BĂNG ĐẢNG: [{clan['tag']}] {clan['name']}",
            description=(
                "Chọn mục bạn muốn tùy chỉnh từ danh sách bên dưới:\n\n"
                "• **Đổi Tên / Tag / Khẩu Hiệu:** Mở hộp thoại nhập thông tin mới (áp dụng cooldown 7 ngày).\n"
                "• **Đổi Màu Role:** Cập nhật màu sắc hiển thị Role thành viên.\n"
                "• **Logo & Banner:** Tải ảnh trực tiếp hoặc dán link ảnh hiển thị hồ sơ.\n"
                "• **Chế Độ Tuyển Quân:** Tự Do / Cần Duyệt / Chỉ Nhận Lời Mời."
            ),
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        view = SettingsDashboardView(clan=clan, bot=self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @clan_group.command(name="disband", description="Giải tán băng đảng của bạn (Chỉ Chủ Băng)")
    async def clan_disband(self, interaction: discord.Interaction):
        clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not clan:
            await interaction.response.send_message("❌ Bạn không thuộc băng nào!", ephemeral=True)
            return

        is_leader = int(clan["leader_id"]) == interaction.user.id
        if not is_leader and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Chỉ Chủ Băng mới có quyền giải tán băng!", ephemeral=True)
            return

        modal = DisbandClanModal(clan=clan, bot=self.bot)
        await interaction.response.send_modal(modal)

    @clan_group.command(name="set-image", description="Cập nhật nhanh Logo hoặc Banner cho băng của bạn")
    @app_commands.describe(
        loai="Chọn loại hình ảnh muốn đổi",
        link="Đường dẫn trực tiếp đến ảnh (http/https)",
        anh="Tải trực tiếp file ảnh từ máy của bạn"
    )
    async def clan_set_image(
        self,
        interaction: discord.Interaction,
        loai: Literal["logo", "banner"],
        link: Optional[str] = None,
        anh: Optional[discord.Attachment] = None
    ):
        await interaction.response.defer(ephemeral=True)
        clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not clan:
            await interaction.followup.send("❌ Bạn không thuộc băng nào!", ephemeral=True)
            return

        if int(clan["leader_id"]) != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Chỉ Chủ Băng mới có quyền cập nhật ảnh!", ephemeral=True)
            return

        image_url = anh.url if anh else link
        if not image_url:
            await interaction.followup.send("❌ Bạn phải cung cấp đường link ảnh hoặc đính kèm 1 file ảnh!", ephemeral=True)
            return

        if loai == "logo":
            await self.bot.db.update_clan(clan["clan_id"], logo_url=image_url)
            msg = f"✅ Đã cập nhật thành công **Logo** cho băng [{clan['tag']}] {clan['name']}!"
        else:
            await self.bot.db.update_clan(clan["clan_id"], banner_url=image_url)
            msg = f"✅ Đã cập nhật thành công **Banner** cho băng [{clan['tag']}] {clan['name']}!"

        await interaction.followup.send(msg, ephemeral=True)

    @clan_group.command(name="setup-role", description="Bảng điều khiển thiết lập & tùy biến Role Băng (Chủ Băng)")
    async def clan_setup_role(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "register_user_panel"):
            await self.bot.register_user_panel(interaction.user.id, interaction)
        clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not clan:
            await interaction.followup.send("❌ Bạn không thuộc băng nào!", ephemeral=True)
            return

        is_leader = int(clan["leader_id"]) == interaction.user.id
        if not is_leader and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Chỉ Chủ Băng hoặc Quản Trị Viên mới có quyền thiết lập Role!", ephemeral=True)
            return

        role = interaction.guild.get_role(int(clan["role_id"])) if clan.get("role_id") else None
        role_name = role.name if role else f"[{clan['tag']}] {clan['name']}"
        color_hex = f"#{role.color.value:06X}" if role and role.color.value else clan.get("color_hex", "#5865F2")
        sec_hex = clan.get("secondary_color_hex")
        hoist = role.hoist if role else True
        mentionable = role.mentionable if role else False

        from utils.canvas import generate_role_setup_image
        import asyncio
        buf = await asyncio.to_thread(generate_role_setup_image, clan, role_name, color_hex, sec_hex, hoist, mentionable)
        file = discord.File(fp=buf, filename="role_setup.png")
        files = [file]
        from utils.image_storage import resolve_clan_logo
        logo_filename = await resolve_clan_logo(clan, files, fallback_to_default=True)

        embed = build_role_setup_embed(clan, role, attachment_filename="role_setup.png", logo_filename=logo_filename)
        view = ClanRoleSetupView(clan=clan, bot=self.bot)
        await interaction.followup.send(embed=embed, files=files, view=view, ephemeral=True)

    @clan_group.command(name="set-role", description="Gán nhanh một Role có sẵn trên Server làm Role Băng (Chủ Băng)")
    @app_commands.describe(role="Chọn Role trên server bạn muốn gán làm Role của Băng")
    async def clan_set_role(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not clan:
            await interaction.followup.send("❌ Bạn không thuộc băng nào!", ephemeral=True)
            return

        is_leader = int(clan["leader_id"]) == interaction.user.id
        if not is_leader and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Chỉ Chủ Băng hoặc Quản Trị Viên mới có quyền gán Role!", ephemeral=True)
            return

        guild = interaction.guild
        if role.is_default():
            await interaction.followup.send("❌ Không thể chọn Role `@everyone`!", ephemeral=True)
            return

        if role.managed:
            await interaction.followup.send("❌ Không thể chọn Role tự động của Bot khác!", ephemeral=True)
            return

        if role >= guild.me.top_role:
            await interaction.followup.send(
                f"⚠️ Role {role.mention} đang nằm cao hơn hoặc bằng Role của Bot!\n"
                "Vui lòng vào **Server Settings -> Roles** kéo Role của Bot lên cao hơn.",
                ephemeral=True
            )
            return

        # Cập nhật quyền trên Text & Voice Channels
        old_role_id = clan.get("role_id")
        old_role = guild.get_role(int(old_role_id)) if old_role_id else None

        for ch_key in ("text_channel_id", "voice_channel_id", "extra_voice_channel_id"):
            ch_id = clan.get(ch_key)
            if ch_id:
                ch = guild.get_channel(int(ch_id))
                if ch:
                    try:
                        if old_role:
                            await ch.set_permissions(old_role, overwrite=None, reason="Đổi role clan")
                        await ch.set_permissions(
                            role,
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
                        logger.warn(f"Lỗi cập nhật quyền kênh: {ch_err}")

        # Cấp role cho toàn bộ thành viên hiện tại
        members = await self.bot.db.get_clan_members(clan["clan_id"])
        for m in members:
            try:
                target_mem = guild.get_member(int(m["user_id"])) or await guild.fetch_member(int(m["user_id"]))
                if target_mem:
                    await target_mem.add_roles(role, reason="Gán role mới cho clan")
            except Exception:
                pass

        hex_color = f"#{role.color.value:06X}" if role.color.value else "#5865F2"
        await self.bot.db.update_clan(clan["clan_id"], role_id=str(role.id), color_hex=hex_color)
        await self.bot.db.add_clan_log(
            clan_id=clan["clan_id"],
            actor_id=interaction.user.id,
            action="LINK_ROLE",
            details=f"Gán role mới {role.name} ({role.id})."
        )
        await interaction.followup.send(f"✅ Đã gán thành công Role {role.mention} làm Role chính thức của Băng!", ephemeral=True)

    # =========================================================================
    # NHÓM C: NHÂN SỰ & TUYỂN QUÂN
    # =========================================================================

    @clan_group.command(name="invite", description="Gửi lời mời tham gia băng đến một người bạn (Cán Bộ trở lên)")
    @app_commands.describe(user="Người bạn muốn mời vào băng")
    async def clan_invite(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer()
        guild = interaction.guild
        inviter = interaction.user

        clan = await self.bot.db.get_clan_by_member(guild.id, inviter.id)
        if not clan:
            await interaction.followup.send("❌ Bạn chưa tham gia bất kỳ băng nào!")
            return

        inviter_rank = clan["rank"]
        if RANK_WEIGHTS.get(inviter_rank, 0) < RANK_WEIGHTS[Ranks.OFFICER] and not inviter.guild_permissions.administrator:
            await interaction.followup.send("❌ Chỉ có Cán Bộ (OFFICER) trở lên mới có quyền gửi lời mời gia nhập!")
            return

        cur_count = await self.bot.db.get_member_count(clan["clan_id"])
        if cur_count >= clan["max_members"]:
            await interaction.followup.send(f"❌ Băng đã đạt giới hạn tối đa sĩ số ({cur_count}/{clan['max_members']})! Hãy nâng cấp Level băng để mở rộng chỗ.")
            return

        if user.bot:
            await interaction.followup.send("❌ Không thể mời Bot Discord vào băng!")
            return

        if user.id == inviter.id:
            await interaction.followup.send("❌ Bạn không thể tự mời chính mình!")
            return

        existing = await self.bot.db.get_clan_by_member(guild.id, user.id)
        if existing:
            await interaction.followup.send(f"❌ Người dùng này đã tham gia băng **{existing['name']}** rồi!")
            return

        # Tạo request trong DB
        expires_at = int(time.time()) + (15 * 60)
        req_id = await self.bot.db.create_request(
            clan_id=clan["clan_id"],
            guild_id=guild.id,
            user_id=user.id,
            actor_id=inviter.id,
            request_type="INVITE",
            expire_minutes=15
        )

        embed = discord.Embed(
            title="💌 LỜI MỜI GIA NHẬP BĂNG ĐẢNG",
            description=f"Chào {user.mention}!\nBạn vừa nhận được lời mời gia nhập băng **[{clan['tag']}] {clan['name']}** từ <@{inviter.id}>.",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="🏰 Tên Băng", value=f"[{clan['tag']}] {clan['name']}", inline=True)
        embed.add_field(name="👑 Chủ Băng", value=f"<@{clan['leader_id']}>", inline=True)
        embed.add_field(name="📜 Khẩu Hiệu", value=clan.get("description") or "Chưa có khẩu hiệu.", inline=False)
        embed.add_field(name="⏳ Hạn Chót", value=f"Lời mời tự hết hạn vào: <t:{expires_at}:R>", inline=False)
        embed.set_footer(text="Bấm nút bên dưới để Chấp Nhận hoặc Từ Chối")

        view = RequestView(request_id=req_id, bot=self.bot, is_invite=True)
        msg = await interaction.followup.send(content=user.mention, embed=embed, view=view)

        # Lưu message_id
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
        dm_invite.add_field(name="👉 Thao Tác", value=f"Hãy vào máy chủ **{guild.name}** để bấm nút [✅ Chấp Nhận Lời Mời] nhé!", inline=False)
        dm_invite.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
        await send_dm_notification(user, dm_invite)

    @clan_group.command(name="apply", description="Nộp đơn xin gia nhập một băng đảng")
    @app_commands.describe(ten_bang="Tên hoặc Tag của băng muốn xin vào (bỏ trống để chọn danh sách)")
    @app_commands.autocomplete(ten_bang=clan_name_autocomplete)
    async def clan_apply(self, interaction: discord.Interaction, ten_bang: Optional[str] = None):
        guild = interaction.guild
        existing = await self.bot.db.get_clan_by_member(guild.id, interaction.user.id)
        if existing:
            await interaction.response.send_message(f"❌ Bạn đã là thành viên của băng **{existing['name']}** rồi!", ephemeral=True)
            return

        if ten_bang:
            clan = await self.bot.db.get_clan_by_name(guild.id, ten_bang) or await self.bot.db.get_clan_by_tag(guild.id, ten_bang)
            if not clan:
                await interaction.response.send_message(f"❌ Không tìm thấy băng nào khớp với: **{ten_bang}**!", ephemeral=True)
                return
            modal = ApplyClanModal(clan=clan, bot=self.bot)
            await interaction.response.send_modal(modal)
        else:
            clans = await self.bot.db.get_all_clans_in_guild(guild.id)
            if not clans:
                await interaction.response.send_message("❌ Máy chủ hiện chưa có băng nào đang hoạt động!", ephemeral=True)
                return
            if len(clans) == 1:
                clan = await self.bot.db.get_clan_by_id(clans[0]["clan_id"])
                if not clan:
                    await interaction.response.send_message("❌ Băng không tồn tại!", ephemeral=True)
                    return
                modal = ApplyClanModal(clan=clan, bot=self.bot)
                await interaction.response.send_modal(modal)
            else:
                from utils.ui_components import QuickApplySelectView
                view = QuickApplySelectView(clans=clans, bot=self.bot)
                await interaction.response.send_message("📩 **Hãy chọn băng bạn muốn nộp đơn gia nhập bên dưới:**", view=view, ephemeral=True)

    @clan_group.command(name="promote", description="Thăng cấp bậc cho một thành viên trong băng")
    @app_commands.describe(user="Thành viên muốn thăng chức")
    async def clan_promote(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer()
        guild = interaction.guild
        actor_rec = await self.bot.db.get_clan_by_member(guild.id, interaction.user.id)
        target_rec = await self.bot.db.get_clan_by_member(guild.id, user.id)

        if not actor_rec:
            await interaction.followup.send("❌ Bạn không thuộc băng nào!")
            return
        if not target_rec or target_rec["clan_id"] != actor_rec["clan_id"]:
            await interaction.followup.send("❌ Thành viên này không thuộc băng của bạn!")
            return

        actor_w = RANK_WEIGHTS.get(actor_rec["rank"], 0)
        target_w = RANK_WEIGHTS.get(target_rec["rank"], 0)

        if actor_w <= target_w and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Bạn không thể thăng chức cho người có chức vụ bằng hoặc cao hơn bạn!")
            return

        new_rank = None
        if target_rec["rank"] == Ranks.MEMBER:
            officer_count = await self.bot.db.get_rank_count(actor_rec["clan_id"], Ranks.OFFICER)
            if officer_count >= RANK_LIMITS[Ranks.OFFICER]:
                await interaction.followup.send(f"❌ Băng đã đạt tối đa **{RANK_LIMITS[Ranks.OFFICER]}** Cán Bộ! Hãy giáng chức bớt trước.")
                return
            new_rank = Ranks.OFFICER
        elif target_rec["rank"] == Ranks.OFFICER:
            if actor_rec["rank"] != Ranks.LEADER and not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ Chỉ có Chủ Băng mới có quyền bổ nhiệm Phó Băng!")
                return
            co_count = await self.bot.db.get_rank_count(actor_rec["clan_id"], Ranks.CO_LEADER)
            if co_count >= RANK_LIMITS[Ranks.CO_LEADER]:
                await interaction.followup.send(f"❌ Băng đã đạt tối đa **{RANK_LIMITS[Ranks.CO_LEADER]}** Phó Băng!")
                return
            new_rank = Ranks.CO_LEADER
        else:
            await interaction.followup.send("❌ Thành viên này đã ở cấp bậc cao nhất có thể thăng chức!")
            return

        await self.bot.db.update_member_rank(guild.id, user.id, new_rank)
        await self.bot.db.add_clan_log(
            clan_id=actor_rec["clan_id"],
            actor_id=interaction.user.id,
            target_id=user.id,
            action="PROMOTE",
            details=f"<@{interaction.user.id}> đã thăng chức cho <@{user.id}> lên {RANK_NAMES[new_rank]}."
        )

        # Gửi DM thông báo thăng chức
        dm_promote = discord.Embed(
            title="⭐ BẠN ĐÃ ĐƯỢC THĂNG CHỨC!",
            description=f"Chúc mừng bạn! Bạn đã được <@{interaction.user.id}> thăng cấp lên chức vụ **{RANK_NAMES[new_rank]}** trong băng **[{actor_rec['tag']}] {actor_rec['name']}** tại máy chủ **{guild.name}**!",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        dm_promote.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
        await send_dm_notification(user, dm_promote)

        await interaction.followup.send(f"🎉 Chúc mừng {user.mention} đã được thăng chức lên **{RANK_NAMES[new_rank]}** trong băng **[{actor_rec['tag']}] {actor_rec['name']}**!")

    @clan_group.command(name="demote", description="Giáng cấp bậc của một cán bộ/phó băng")
    @app_commands.describe(user="Thành viên muốn giáng chức")
    async def clan_demote(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer()
        guild = interaction.guild
        actor_rec = await self.bot.db.get_clan_by_member(guild.id, interaction.user.id)
        target_rec = await self.bot.db.get_clan_by_member(guild.id, user.id)

        if not actor_rec:
            await interaction.followup.send("❌ Bạn không thuộc băng nào!")
            return
        if not target_rec or target_rec["clan_id"] != actor_rec["clan_id"]:
            await interaction.followup.send("❌ Thành viên này không thuộc băng của bạn!")
            return

        actor_w = RANK_WEIGHTS.get(actor_rec["rank"], 0)
        target_w = RANK_WEIGHTS.get(target_rec["rank"], 0)

        if actor_w <= target_w and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Bạn không thể giáng chức người có chức vụ bằng hoặc cao hơn bạn!")
            return

        if target_rec["rank"] == Ranks.CO_LEADER and actor_rec["rank"] != Ranks.LEADER and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Chỉ có Chủ Băng mới có quyền giáng chức Phó Băng!")
            return

        new_rank = None
        if target_rec["rank"] == Ranks.CO_LEADER:
            new_rank = Ranks.OFFICER
        elif target_rec["rank"] == Ranks.OFFICER:
            new_rank = Ranks.MEMBER
        else:
            await interaction.followup.send("❌ Thành viên này đã ở cấp bậc cơ bản (MEMBER), không thể giáng thêm!")
            return

        await self.bot.db.update_member_rank(guild.id, user.id, new_rank)
        await self.bot.db.add_clan_log(
            clan_id=actor_rec["clan_id"],
            actor_id=interaction.user.id,
            target_id=user.id,
            action="DEMOTE",
            details=f"<@{interaction.user.id}> đã giáng chức <@{user.id}> xuống {RANK_NAMES[new_rank]}."
        )

        # Gửi DM thông báo giáng chức
        dm_demote = discord.Embed(
            title="⬇️ ĐIỀU CHỈNH CHỨC VỤ BĂNG ĐẢNG",
            description=f"Chức vụ của bạn trong băng **[{actor_rec['tag']}] {actor_rec['name']}** tại máy chủ **{guild.name}** đã được điều chỉnh thành **{RANK_NAMES[new_rank]}** bởi <@{interaction.user.id}>.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        dm_demote.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
        await send_dm_notification(user, dm_demote)

        await interaction.followup.send(f"📉 Thành viên {user.mention} đã bị giáng chức xuống **{RANK_NAMES[new_rank]}** trong băng **[{actor_rec['tag']}] {actor_rec['name']}**.")

    @clan_group.command(name="transfer", description="Chuyển giao quyền Chủ Băng cho thành viên khác (Chỉ Chủ Băng)")
    @app_commands.describe(user="Thành viên được chỉ định làm Chủ Băng mới")
    async def clan_transfer(self, interaction: discord.Interaction, user: discord.Member):
        clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not clan:
            await interaction.response.send_message("❌ Bạn không thuộc băng nào!", ephemeral=True)
            return

        if int(clan["leader_id"]) != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Chỉ có Chủ Băng mới có quyền chuyển giao quyền lực!", ephemeral=True)
            return

        if user.id == interaction.user.id:
            await interaction.response.send_message("❌ Bạn đang là Chủ Băng rồi!", ephemeral=True)
            return

        target_rec = await self.bot.db.get_clan_by_member(interaction.guild_id, user.id)
        if not target_rec or target_rec["clan_id"] != clan["clan_id"]:
            await interaction.response.send_message("❌ Thành viên này không thuộc băng của bạn!", ephemeral=True)
            return

        embed = discord.Embed(
            title="👑 XÁC NHẬN CHUYỂN GIAO QUYỀN CHỦ BĂNG",
            description=(
                f"Bạn có chắc chắn muốn chuyển giao chức vụ **Chủ Băng (LEADER)** của **[{clan['tag']}] {clan['name']}** cho {user.mention} không?\n\n"
                "• Sau khi chuyển giao, bạn sẽ tự động hạ xuống làm **Phó Băng (CO_LEADER)**.\n"
                "• Nút xác nhận này tự hết hạn sau 30 giây."
            ),
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        view = TransferConfirmView(clan=clan, old_leader_id=interaction.user.id, new_leader_id=user.id, bot=self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @clan_group.command(name="kick", description="Trục xuất một thành viên khỏi băng")
    @app_commands.describe(user="Thành viên muốn trục xuất", ly_do="Lý do trục xuất")
    async def clan_kick(self, interaction: discord.Interaction, user: discord.Member, ly_do: Optional[str] = "Không nêu lý do"):
        await interaction.response.defer()
        guild = interaction.guild
        actor_rec = await self.bot.db.get_clan_by_member(guild.id, interaction.user.id)
        target_rec = await self.bot.db.get_clan_by_member(guild.id, user.id)

        if not actor_rec:
            await interaction.followup.send("❌ Bạn không thuộc băng nào!")
            return
        if not target_rec or target_rec["clan_id"] != actor_rec["clan_id"]:
            await interaction.followup.send("❌ Thành viên mục tiêu không thuộc băng của bạn!")
            return

        actor_w = RANK_WEIGHTS.get(actor_rec["rank"], 0)
        target_w = RANK_WEIGHTS.get(target_rec["rank"], 0)

        if actor_w <= target_w and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Bạn không thể trục xuất người có cấp bậc bằng hoặc cao hơn bạn!")
            return

        # Gỡ Role
        role = guild.get_role(int(actor_rec["role_id"]))
        if role:
            try:
                await user.remove_roles(role, reason=f"Bị kick bởi {interaction.user.name}")
            except Exception:
                pass

        # Xóa khỏi DB (Bỏ cooldown theo yêu cầu)
        await self.bot.db.remove_member(guild.id, user.id)

        await self.bot.db.add_clan_log(
            clan_id=actor_rec["clan_id"],
            actor_id=interaction.user.id,
            target_id=user.id,
            action="KICK",
            details=f"<@{interaction.user.id}> đã trục xuất <@{user.id}>. Lý do: {ly_do}"
        )

        # Gửi DM thông báo lý do trục xuất
        dm_kick = discord.Embed(
            title="👢 BẠN ĐÃ BỊ TRỤC XUẤT KHỎI BĂNG",
            description=f"Bạn đã bị trục xuất khỏi băng **[{actor_rec['tag']}] {actor_rec['name']}** tại máy chủ **{guild.name}**.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        dm_kick.add_field(name="👮 Người thực hiện", value=f"<@{interaction.user.id}> ({interaction.user.display_name})", inline=True)
        dm_kick.add_field(name="💬 Lý do trục xuất", value=ly_do, inline=False)
        dm_kick.add_field(name="✨ Lưu ý", value="Bạn không bị áp dụng thời gian chờ (cooldown) và có thể tự do gia nhập hoặc tạo băng khác ngay lập tức!", inline=False)
        dm_kick.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
        await send_dm_notification(user, dm_kick)

        await interaction.followup.send(f"👢 Đã trục xuất {user.mention} khỏi băng **[{actor_rec['tag']}] {actor_rec['name']}** thành công và gửi thông báo lý do qua DM.")

    @clan_group.command(name="leave", description="Tự nguyện rời khỏi băng hiện tại của bạn")
    async def clan_leave(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user

        mem_rec = await self.bot.db.get_clan_by_member(guild.id, user.id)
        if not mem_rec:
            await interaction.followup.send("❌ Bạn không tham gia bất kỳ băng nào trong server này!", ephemeral=True)
            return

        if int(mem_rec["leader_id"]) == user.id:
            await interaction.followup.send("❌ Chủ Băng không thể tự ý rời băng! Hãy dùng `/clan transfer` để nhượng quyền hoặc `/clan disband` để giải tán băng.", ephemeral=True)
            return

        # Gỡ Role
        role = guild.get_role(int(mem_rec["role_id"]))
        if role:
            try:
                await user.remove_roles(role, reason="Tự nguyện rời băng")
            except Exception:
                pass

        # Xóa khỏi DB (Bỏ cooldown theo yêu cầu)
        await self.bot.db.remove_member(guild.id, user.id)

        await self.bot.db.add_clan_log(
            clan_id=mem_rec["clan_id"],
            actor_id=user.id,
            action="LEAVE",
            details=f"<@{user.id}> đã tự nguyện rời khỏi băng."
        )

        await interaction.followup.send(f"👋 Bạn đã tự nguyện rời khỏi băng **[{mem_rec['tag']}] {mem_rec['name']}**. Bạn có thể tự do gia nhập hoặc lập băng mới ngay mà không cần chờ đợi!", ephemeral=True)

    # =========================================================================
    # NHÓM D: TRA CỨU & XẾP HẠNG
    # =========================================================================

    @clan_group.command(name="info", description="Xem thông tin chi tiết và hồ sơ của một băng đảng")
    @app_commands.describe(ten_bang="Tên hoặc Tag băng (để trống để xem băng của chính mình)")
    @app_commands.autocomplete(ten_bang=clan_name_autocomplete)
    async def clan_info(self, interaction: discord.Interaction, ten_bang: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "register_user_panel"):
            await self.bot.register_user_panel(interaction.user.id, interaction)
        guild = interaction.guild

        if ten_bang:
            clan = await self.bot.db.get_clan_by_name(guild.id, ten_bang) or await self.bot.db.get_clan_by_tag(guild.id, ten_bang)
        else:
            clan = await self.bot.db.get_clan_by_member(guild.id, interaction.user.id)

        if not clan:
            msg = f"❌ Không tìm thấy băng nào khớp với: **{ten_bang}**!" if ten_bang else "❌ Bạn chưa tham gia băng nào! Hãy dùng `/clan info [tên_băng]` để xem băng khác hoặc `/clan create` để lập băng."
            await interaction.followup.send(msg)
            return

        members = await self.bot.db.get_clan_members(clan["clan_id"])
        level_info = get_level_info(clan["exp"])
        viewer_clan = await self.bot.db.get_clan_by_member(guild.id, interaction.user.id)
        can_apply = (viewer_clan is None) and (clan["join_mode"] != JoinModes.INVITE_ONLY)
        is_member = (viewer_clan is not None and viewer_clan["clan_id"] == clan["clan_id"])
        is_leader = (int(clan["leader_id"]) == interaction.user.id)

        from utils.ui_components import build_clan_profile_payload
        embed, files = await build_clan_profile_payload(clan, members, level_info, interaction.guild)
        view = ClanInfoView(clan_id=clan["clan_id"], can_apply=can_apply, is_member=is_member, is_leader=is_leader, bot=self.bot)
        await interaction.followup.send(embed=embed, files=files, view=view)

    @clan_group.command(name="members", description="Xem danh sách thành viên trong băng kèm phân trang")
    @app_commands.describe(ten_bang="Tên hoặc Tag băng (để trống để xem băng của mình)")
    @app_commands.autocomplete(ten_bang=clan_name_autocomplete)
    async def clan_members(self, interaction: discord.Interaction, ten_bang: Optional[str] = None):
        await interaction.response.defer()
        guild = interaction.guild

        if ten_bang:
            clan = await self.bot.db.get_clan_by_name(guild.id, ten_bang) or await self.bot.db.get_clan_by_tag(guild.id, ten_bang)
        else:
            clan = await self.bot.db.get_clan_by_member(guild.id, interaction.user.id)

        if not clan:
            await interaction.followup.send("❌ Không tìm thấy thông tin băng!")
            return

        members = await self.bot.db.get_clan_members(clan["clan_id"])
        from utils.image_storage import resolve_clan_logo
        files = []
        logo_ref = await resolve_clan_logo(clan, files, fallback_to_default=True)
        embed, total_pages = build_members_embed(clan, members, page=1, page_size=10, logo_filename=logo_ref)
        view = MembersPaginationView(clan_id=clan["clan_id"], current_page=1, total_pages=total_pages, current_filter="ALL", bot=self.bot)
        await interaction.followup.send(embed=embed, files=files, view=view)

    @clan_group.command(name="list", description="Xem danh sách toàn bộ các băng đang hoạt động trong server")
    async def clan_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "register_user_panel"):
            await self.bot.register_user_panel(interaction.user.id, interaction)
        clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        embed = build_clan_list_embed(interaction.guild.name, clans)
        from utils.ui_components import ClanListInteractiveView
        view = ClanListInteractiveView(clans=clans, bot=self.bot)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @clan_group.command(name="leaderboard", description="Bảng vinh danh các băng đảng xuất sắc nhất server")
    @app_commands.describe(tieu_chi="Tiêu chí xếp hạng")
    async def clan_leaderboard(
        self,
        interaction: discord.Interaction,
        tieu_chi: Literal["level", "weekly", "members"] = "level"
    ):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "register_user_panel"):
            await self.bot.register_user_panel(interaction.user.id, interaction)
        clans = await self.bot.db.get_leaderboard(interaction.guild_id, criteria=tieu_chi, limit=10)

        from utils.canvas import generate_leaderboard_image
        import asyncio
        buf = await asyncio.to_thread(generate_leaderboard_image, interaction.guild.name, clans, tieu_chi)
        file = discord.File(fp=buf, filename="leaderboard.png")

        embed = build_leaderboard_embed(interaction.guild.name, clans, criteria=tieu_chi, attachment_filename="leaderboard.png")
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        from utils.ui_components import LeaderboardInteractiveView
        view = LeaderboardInteractiveView(guild_name=interaction.guild.name, bot=self.bot, initial_criteria=tieu_chi)
        await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)

    @clan_group.command(name="logs", description="Xem nhật ký hoạt động gần đây của băng (Cán Bộ trở lên)")
    @app_commands.describe(trang="Số trang cần xem (Mặc định: 1)")
    async def clan_logs(self, interaction: discord.Interaction, trang: int = 1):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "register_user_panel"):
            await self.bot.register_user_panel(interaction.user.id, interaction)
        clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not clan:
            await interaction.followup.send("❌ Bạn không thuộc băng nào!", ephemeral=True)
            return

        if clan["rank"] not in (Ranks.LEADER, Ranks.CO_LEADER, Ranks.OFFICER) and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Chỉ Cán Bộ trở lên mới có quyền xem nhật ký hoạt động!", ephemeral=True)
            return

        page = max(1, trang)
        data = await self.bot.db.get_clan_logs(clan["clan_id"], page=page, page_size=10)
        total_pages = max(1, (data["total"] + 9) // 10)

        embed = build_logs_embed(clan, data["logs"], page=page, total_pages=total_pages)
        view = LogsPaginationView(clan_id=clan["clan_id"], current_page=page, total_pages=total_pages, bot=self.bot)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    # =========================================================================
    # NHÓM E: HOẠT ĐỘNG CỘNG ĐỒNG
    # =========================================================================

    @clan_group.command(name="checkin", description="Điểm danh hằng ngày nhận EXP băng và điểm cống hiến cá nhân")
    async def clan_checkin(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild = interaction.guild
        user = interaction.user

        clan = await self.bot.db.get_clan_by_member(guild.id, user.id)
        if not clan:
            await interaction.followup.send("❌ Bạn chưa tham gia bất kỳ băng đảng nào!")
            return

        today = get_today_vn_string()
        yesterday = get_yesterday_vn_string()

        if clan.get("last_checkin_date") == today:
            await interaction.followup.send("❌ Hôm nay bạn đã điểm danh rồi! Hãy quay lại sau 00:00 (giờ Việt Nam).")
            return

        new_streak = 1
        if clan.get("last_checkin_date") == yesterday:
            new_streak = (clan.get("checkin_streak") or 0) + 1

        clan_exp_to_add = EXP_REWARDS.CHECKIN_EXP
        is_streak_7 = (new_streak % 7 == 0)
        if is_streak_7:
            clan_exp_to_add += EXP_REWARDS.CHECKIN_STREAK_7_BONUS_EXP

        await self.bot.db.update_checkin(guild.id, user.id, today, new_streak)
        await self.bot.db.add_clan_exp(clan["clan_id"], clan_exp_to_add, clan_exp_to_add)

        # Cập nhật nhiệm vụ tuần CHECKIN_COUNT
        week_key = get_current_week_key()
        quest_res = await self.bot.db.increment_quest_progress(clan["clan_id"], week_key, "CHECKIN_COUNT", 1)
        if quest_res["completed_now"]:
            await self.bot.db.add_clan_exp(clan["clan_id"], quest_res["reward_exp"], quest_res["reward_exp"])

        embed = discord.Embed(
            title="📅 ĐIỂM DANH HẰNG NGÀY THÀNH CÔNG!",
            description=f"Bạn đã điểm danh thành công cho băng **{clan['name']}**!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="🔥 Chuỗi Điểm Danh (Streak)", value=f"**{new_streak}** ngày {'🎁 *(Thưởng +50 EXP mốc 7 ngày!)*' if is_streak_7 else ''}", inline=True)
        embed.add_field(name="🏰 EXP Băng Nhận Được", value=f"**+{clan_exp_to_add}** EXP", inline=True)
        embed.add_field(name="🏆 Điểm Cống Hiến Cá Nhân", value=f"**+{EXP_REWARDS.CHECKIN_CONTRIBUTION}** điểm", inline=True)
        embed.set_footer(text="Hãy duy trì điểm danh hằng ngày cùng anh em!")

        await interaction.followup.send(embed=embed)

    @clan_group.command(name="upload-image", description="Tải lên trực tiếp ảnh Logo, Banner hoặc Icon riêng cho Role của Băng")
    @app_commands.describe(
        loai="Loại ảnh muốn cập nhật (logo: Logo Băng, banner: Banner Băng, role_icon: Icon Role Boost Lv.2)",
        file="Tệp ảnh tải lên từ thiết bị của bạn (PNG, JPG, WEBP, GIF)"
    )
    async def clan_upload_image(
        self,
        interaction: discord.Interaction,
        loai: Literal["logo", "banner", "role_icon"],
        file: discord.Attachment
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user

        clan = await self.bot.db.get_clan_by_member(guild.id, user.id)
        if not clan:
            await interaction.followup.send("❌ Bạn chưa tham gia bất kỳ băng đảng nào!", ephemeral=True)
            return

        is_leader = int(clan["leader_id"]) == user.id
        is_admin = user.guild_permissions.administrator or user.guild_permissions.manage_guild
        if not is_leader and not is_admin:
            await interaction.followup.send("❌ Chỉ Chủ Băng (LEADER) hoặc Quản Trị Viên mới có quyền tùy chỉnh hình ảnh của Băng!", ephemeral=True)
            return

        # Kiểm tra file có phải định dạng ảnh không
        content_type = file.content_type or ""
        valid_types = ("image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif")
        if not any(content_type.startswith(t) for t in valid_types) and not any(file.filename.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
            await interaction.followup.send("❌ Tệp tải lên phải là hình ảnh hợp lệ (PNG, JPG, WEBP, GIF)!", ephemeral=True)
            return

        if loai == "logo":
            from utils.image_storage import save_clan_attachment, resolve_clan_logo, resolve_clan_banner
            try:
                saved_uri = await save_clan_attachment(clan["clan_id"], "logo", file)
            except Exception as save_err:
                await interaction.followup.send(f"❌ Không thể lưu ảnh: `{save_err}`", ephemeral=True)
                return
            await self.bot.db.update_clan(clan["clan_id"], logo_url=saved_uri)
            clan["logo_url"] = saved_uri
            await self.bot.db.add_clan_log(
                clan_id=clan["clan_id"],
                actor_id=user.id,
                action="UPDATE_LOGO",
                details=f"Tải lên ảnh Logo mới cho Băng."
            )
            embed = discord.Embed(
                title="🖼️ CẬP NHẬT LOGO BĂNG THÀNH CÔNG!",
                description=f"Logo của băng **{clan['name']}** đã được cập nhật thành công!",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            files = []
            logo_ref = await resolve_clan_logo(clan, files, fallback_to_default=True)
            m_count = await self.bot.db.get_member_count(clan["clan_id"])
            l_mem = guild.get_member(int(clan["leader_id"])) if clan.get("leader_id") else None
            l_name = l_mem.display_name if l_mem else None
            banner_ref = await resolve_clan_banner(clan, files, member_count=m_count, leader_name=l_name, fallback_to_default=True)
            if logo_ref:
                embed.set_thumbnail(url=logo_ref)
            if banner_ref:
                embed.set_image(url=banner_ref)
            await interaction.followup.send(embed=embed, files=files, ephemeral=True)

        elif loai == "banner":
            from utils.image_storage import save_clan_attachment, resolve_clan_logo, resolve_clan_banner
            try:
                saved_uri = await save_clan_attachment(clan["clan_id"], "banner", file)
            except Exception as save_err:
                await interaction.followup.send(f"❌ Không thể lưu ảnh: `{save_err}`", ephemeral=True)
                return
            await self.bot.db.update_clan(clan["clan_id"], banner_url=saved_uri)
            clan["banner_url"] = saved_uri
            await self.bot.db.add_clan_log(
                clan_id=clan["clan_id"],
                actor_id=user.id,
                action="UPDATE_BANNER",
                details=f"Tải lên ảnh Banner mới cho Băng."
            )
            embed = discord.Embed(
                title="🎨 CẬP NHẬT BANNER BĂNG THÀNH CÔNG!",
                description=f"Banner của băng **{clan['name']}** đã được cập nhật thành công!",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            files = []
            logo_ref = await resolve_clan_logo(clan, files, fallback_to_default=True)
            m_count = await self.bot.db.get_member_count(clan["clan_id"])
            l_mem = guild.get_member(int(clan["leader_id"])) if clan.get("leader_id") else None
            l_name = l_mem.display_name if l_mem else None
            banner_ref = await resolve_clan_banner(clan, files, member_count=m_count, leader_name=l_name, fallback_to_default=True)
            if logo_ref:
                embed.set_thumbnail(url=logo_ref)
            if banner_ref:
                embed.set_image(url=banner_ref)
            await interaction.followup.send(embed=embed, files=files, ephemeral=True)

        elif loai == "role_icon":
            role_id = clan.get("role_id")
            if not role_id:
                await interaction.followup.send("❌ Băng của bạn chưa được liên kết Role trên server!", ephemeral=True)
                return

            role = guild.get_role(int(role_id))
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
                image_bytes = await file.read()
                await role.edit(display_icon=image_bytes, reason=f"Chủ Băng cài Role Icon: {user.name}")
                await self.bot.db.add_clan_log(
                    clan_id=clan["clan_id"],
                    actor_id=user.id,
                    action="UPDATE_ROLE_ICON",
                    details=f"Cập nhật Icon riêng cho Role {role.name}."
                )
                embed = discord.Embed(
                    title="🌟 CẬP NHẬT ICON ROLE BĂNG THÀNH CÔNG!",
                    description=(
                        f"Đã cập nhật Icon hiển thị cho Role {role.mention} thành công!\n"
                        "Icon này sẽ hiển thị trang trọng ngay bên cạnh tên của toàn thể anh em trong danh sách server."
                    ),
                    color=discord.Color.gold(),
                    timestamp=datetime.now()
                )
                embed.set_thumbnail(url=file.url)
                await interaction.followup.send(embed=embed, ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send("❌ Bot bị thiếu quyền `Manage Roles` để đổi Icon cho role!", ephemeral=True)
            except (discord.HTTPException, discord.InvalidArgument) as err:
                logger.warning(f"Lỗi đặt role icon (thiếu boost): {err}")
                await interaction.followup.send(
                    f"⚠️ **Không thể cài Icon cho Role: `{err}`**\n\n"
                    "👉 **Lưu ý quan trọng từ Discord:**\n"
                    "• Tính năng Role Icon yêu cầu Server phải đạt **Server Boost Cấp 2** trở lên.\n"
                    "• Tệp tải lên nên là ảnh vuông (PNG/JPG/WEBP), dung lượng dưới 256KB.",
                    ephemeral=True
                )

    @clan_group.command(name="set-gradient", description="Đổi màu Role sang dải Gradient 2 màu chuyển sắc (Yêu cầu Server Boost)")
    @app_commands.describe(
        start_hex="Mã màu bắt đầu (#HEX, ví dụ: #FF512F)",
        end_hex="Mã màu kết thúc (#HEX, ví dụ: #DD2476)"
    )
    async def clan_set_gradient(
        self,
        interaction: discord.Interaction,
        start_hex: str,
        end_hex: str
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user

        clan = await self.bot.db.get_clan_by_member(guild.id, user.id)
        if not clan:
            await interaction.followup.send("❌ Bạn chưa tham gia bất kỳ băng đảng nào!", ephemeral=True)
            return

        is_leader = int(clan["leader_id"]) == user.id
        is_admin = user.guild_permissions.administrator or user.guild_permissions.manage_guild
        if not is_leader and not is_admin:
            await interaction.followup.send("❌ Chỉ Chủ Băng hoặc Quản Trị Viên mới có quyền đổi màu Role!", ephemeral=True)
            return

        start_raw = start_hex.strip()
        end_raw = end_hex.strip()
        if not start_raw.startswith("#"):
            start_raw = f"#{start_raw}"
        if not end_raw.startswith("#"):
            end_raw = f"#{end_raw}"

        import re
        if not re.match(r"^#[0-9a-fA-F]{6}$", start_raw) or not re.match(r"^#[0-9a-fA-F]{6}$", end_raw):
            await interaction.followup.send("❌ Mã màu không hợp lệ! Vui lòng nhập định dạng Hex 6 ký tự (ví dụ: `#FF512F` và `#DD2476`).", ephemeral=True)
            return

        role_id = clan.get("role_id")
        if not role_id:
            await interaction.followup.send("❌ Băng chưa có Role trên máy chủ!", ephemeral=True)
            return

        role = guild.get_role(int(role_id))
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

        from utils.embeds import parse_hex_color
        start_color = parse_hex_color(start_raw)
        end_color = parse_hex_color(end_raw)
        start_clean = start_raw.upper()
        end_clean = end_raw.upper()

        try:
            await role.edit(
                color=start_color,
                secondary_color=end_color,
                reason=f"Chủ Băng cài màu Gradient: {user.name}"
            )
            await self.bot.db.update_clan(
                clan["clan_id"],
                color_hex=start_clean,
                secondary_color_hex=end_clean
            )
            await self.bot.db.add_clan_log(
                clan_id=clan["clan_id"],
                actor_id=user.id,
                action="UPDATE_COLOR",
                details=f"Đổi màu Role sang Gradient {start_clean} ➔ {end_clean}."
            )
            embed = discord.Embed(
                title="🌈 ĐỔI MÀU GRADIENT THÀNH CÔNG!",
                description=(
                    f"Đã cập nhật dải màu Gradient cho Role {role.mention}!\n\n"
                    f"• Màu khởi đầu: **{start_clean}**\n"
                    f"• Màu kết thúc: **{end_clean}**\n"
                    "*(Nếu server của bạn có Boost, màu role sẽ chuyển sắc gradient lung linh trên danh sách thành viên!)*"
                ),
                color=start_color,
                timestamp=datetime.now()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except (discord.HTTPException, discord.InvalidArgument) as err:
            logger.warning(f"Lỗi Gradient Role (thiếu boost): {err}")
            try:
                await role.edit(color=start_color, secondary_color=None, reason=f"Fallback sang màu đơn sắc: {user.name}")
                await self.bot.db.update_clan(clan["clan_id"], color_hex=start_clean, secondary_color_hex=None)
                await interaction.followup.send(
                    f"⚠️ **Server chưa đạt cấp độ Server Boost hỗ trợ Gradient 2 màu!**\n"
                    f"👉 Bot đã tự động áp dụng **màu đơn sắc chính {start_clean}** cho Role của bạn để đảm bảo hiển thị đẹp nhất.",
                    ephemeral=True
                )
            except Exception as fb_err:
                await interaction.followup.send(f"❌ Lỗi khi đổi màu role: `{fb_err}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi đổi màu role: `{e}`", ephemeral=True)

    @clan_group.command(name="party", description="Gửi thư thách đấu tới băng khác hoặc tạo kèo chơi game nội bộ")
    async def clan_party(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "register_user_panel"):
            await self.bot.register_user_panel(interaction.user.id, interaction)
        clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not clan:
            await interaction.followup.send("❌ Bạn chưa tham gia bất kỳ băng đảng nào!", ephemeral=True)
            return
        all_clans = await self.bot.db.get_all_clans_in_guild(interaction.guild_id)
        other_clans = [c for c in all_clans if c["clan_id"] != clan["clan_id"]]
        from utils.ui_components import ClanChallengeTargetView, build_challenge_target_embed
        embed = build_challenge_target_embed(other_clans)
        view = ClanChallengeTargetView(source_clan=clan, other_clans=other_clans, bot=self.bot)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @clan_group.command(name="quests", description="Xem danh sách nhiệm vụ tuần hợp tác của băng")
    async def clan_quests(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "register_user_panel"):
            await self.bot.register_user_panel(interaction.user.id, interaction)
        clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        if not clan:
            await interaction.followup.send("❌ Bạn chưa tham gia băng nào!", ephemeral=True)
            return

        week_key = get_current_week_key()
        quests = await self.bot.db.ensure_weekly_quests(clan["clan_id"], week_key)
        from utils.canvas import generate_quests_image
        buf = await asyncio.to_thread(generate_quests_image, clan, quests, week_key)
        file = discord.File(fp=buf, filename="quests.png")
        files = [file]
        from utils.image_storage import resolve_clan_logo
        logo_ref = await resolve_clan_logo(clan, files, fallback_to_default=True)
        embed = build_quests_embed(clan, quests, week_key, attachment_filename="quests.png", logo_filename=logo_ref)
        await interaction.followup.send(embed=embed, files=files, ephemeral=True)

    @clan_group.command(name="hub", description="Mở trung tâm điều khiển Băng Đảng tương tác 1-click")
    async def clan_hub(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "register_user_panel"):
            await self.bot.register_user_panel(interaction.user.id, interaction)
        clan = await self.bot.db.get_clan_by_member(interaction.guild_id, interaction.user.id)
        member_count = 0
        if clan:
            member_count = await self.bot.db.get_member_count(clan["clan_id"])
            desc = (
                f"Xin chào <@{interaction.user.id}>!\n\n"
                f"🏰 Băng đảng: **[{clan['tag']}] {clan['name']}**\n"
                f"🎖️ Chức vụ: **{RANK_NAMES.get(clan['rank'], clan['rank'])}**\n"
                f"⭐ Điểm cống hiến: **{clan.get('contribution_points', 0)}** • Chuỗi điểm danh: **{clan.get('checkin_streak', 0)} ngày**\n\n"
                "👉 *Bấm các nút bên dưới để thao tác nhanh bằng 1-click mà không cần nhớ lệnh:*"
            )
            color = discord.Color.gold()
        else:
            desc = (
                f"Xin chào <@{interaction.user.id}>!\n\n"
                "Bạn hiện **chưa gia nhập** băng đảng nào trong server.\n\n"
                "👉 *Bấm các nút bên dưới để xem danh sách băng đang mở tuyển hoặc tự lập băng mới:*"
            )
            color = discord.Color.blue()

        from utils.canvas import generate_clan_hub_image
        buf = await asyncio.to_thread(generate_clan_hub_image, clan, interaction.user.display_name, member_count)
        file = discord.File(fp=buf, filename="clan_hub.png")

        embed = discord.Embed(
            title="🎮 TRUNG TÂM ĐIỀU KHIỂN BĂNG ĐẢNG (CLAN HUB)",
            description=desc,
            color=color,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_image(url="attachment://clan_hub.png")
        view = ClanHubView(user=interaction.user, clan=clan, bot=self.bot)
        await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)

    @clan_group.command(name="help", description="Xem hướng dẫn sử dụng chi tiết & mẹo dùng bot trực quan")
    async def clan_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🏰 HƯỚNG DẪN SỬ DỤNG HỆ THỐNG BĂNG ĐẢNG",
            description=(
                "Chào mừng bạn đến với hệ thống Hội Nhóm & Băng Đảng cộng đồng!\n\n"
                "👉 Hãy **chọn mục bạn cần tìm hiểu** trong menu bên dưới để xem hướng dẫn chi tiết từng bước."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )
        embed.add_field(
            name="🚀 Các Lệnh Phổ Biến Nhất",
            value=(
                "• `/clan info`: Xem hồ sơ băng của bản thân\n"
                "• `/clan checkin`: Điểm danh nhận EXP mỗi ngày\n"
                "• `/clan hub`: Mở trung tâm điều khiển 1-click\n"
                "• `/clan create`: Thành lập một băng mới"
            ),
            inline=False
        )
        view = ClanHelpView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ClanCommands(bot))
