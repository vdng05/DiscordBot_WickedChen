"""
Cog Quản Trị Hệ Thống Băng Đảng (/clan-admin)
Dành riêng cho Quản Trị Viên (Administrator)
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from datetime import datetime
from utils.logger import setup_logging
from utils.ui_components import ForceDeleteConfirmView, BotAccessControlView
from utils.embeds import build_bot_access_embed

logger = setup_logging("ClanAdmin")

async def clan_name_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Gợi ý tự động tên và tag của các băng đảng trong server khi admin gõ phím"""
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

class ClanAdmin(commands.Cog):
    """Bộ lệnh quản trị hệ thống Băng Đảng cho Admin Server"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    admin_group = app_commands.Group(
        name="clan-admin",
        description="Lệnh quản trị hệ thống Băng Đảng (Dành cho Quản Trị Viên)",
        default_permissions=discord.Permissions(administrator=True)
    )

    @admin_group.command(name="setup", description="Thiết lập Category và kênh hệ thống cho Băng Đảng")
    @app_commands.describe(
        category="Category chứa toàn bộ các kênh chat & voice của các băng",
        log_channel="Kênh ghi nhật ký sự kiện chung của server (tùy chọn)",
        allow_member_create="Bật/Tắt cho phép thành viên thường tự lập băng (Mặc định: Bật)",
        create_fee_role="Role yêu cầu nếu muốn giới hạn quyền lập băng (tùy chọn)",
        cooldown_hours="Thời gian chờ sau khi rời băng mới được vào/lập băng mới (giờ, mặc định 0 - không chờ)"
    )
    async def setup(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel,
        log_channel: Optional[discord.TextChannel] = None,
        allow_member_create: bool = True,
        create_fee_role: Optional[discord.Role] = None,
        cooldown_hours: int = 0
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        # Kiểm tra quyền bot
        me = guild.me
        if not me.guild_permissions.manage_roles or not me.guild_permissions.manage_channels:
            await interaction.followup.send("❌ Bot thiếu quyền `Manage Roles` hoặc `Manage Channels` trên server này!", ephemeral=True)
            return

        await self.bot.db.save_guild_config(
            guild_id=guild.id,
            category_id=category.id,
            log_channel_id=log_channel.id if log_channel else None,
            allow_member_create=allow_member_create,
            required_role_id=create_fee_role.id if create_fee_role else None,
            cooldown_hours=cooldown_hours
        )

        embed = discord.Embed(
            title="✅ THIẾT LẬP HỆ THỐNG BĂNG ĐẢNG THÀNH CÔNG!",
            description="Hệ thống quản lý Hội Nhóm / Băng Đảng đã sẵn sàng hoạt động.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="📁 Category Hoạt Động", value=category.mention, inline=True)
        embed.add_field(name="📜 Kênh Nhật Ký (Log)", value=log_channel.mention if log_channel else "_Không thiết lập_", inline=True)
        embed.add_field(name="👥 Cho Phép Mem Tự Tạo", value="Có" if allow_member_create else "Chỉ Admin", inline=True)
        embed.add_field(name="🎖️ Role Yêu Cầu Để Tạo", value=create_fee_role.mention if create_fee_role else "_Tất cả thành viên_", inline=True)
        embed.add_field(name="⏳ Cooldown Rời Băng", value=f"{cooldown_hours} giờ", inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @admin_group.command(name="force-delete", description="Buộc xóa một băng đảng vi phạm quy định server")
    @app_commands.describe(
        ten_bang="Tên hoặc Tag của băng muốn xóa bắt buộc",
        ly_do="Lý do xóa bắt buộc"
    )
    @app_commands.autocomplete(ten_bang=clan_name_autocomplete)
    async def force_delete(
        self,
        interaction: discord.Interaction,
        ten_bang: str,
        ly_do: Optional[str] = "Admin cưỡng chế xóa vi phạm"
    ):
        guild = interaction.guild
        clan = await self.bot.db.get_clan_by_name(guild.id, ten_bang) or await self.bot.db.get_clan_by_tag(guild.id, ten_bang)
        if not clan:
            await interaction.response.send_message(f"❌ Không tìm thấy băng nào có tên hoặc tag khớp với: **{ten_bang}**!", ephemeral=True)
            return

        embed = discord.Embed(
            title="⚠️ XÁC NHẬN XÓA BẮT BUỘC BĂNG ĐẢNG",
            description=f"Bạn có chắc chắn muốn xóa bắt buộc băng **[{clan['tag']}] {clan['name']}** không?\n\n**Hành động này sẽ:**\n• Xóa toàn bộ Role và Kênh Chat/Voice của băng.\n• Xóa toàn bộ dữ liệu cống hiến, cấp độ và thành viên.\n• Không thể hoàn tác!",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Lý Do", value=ly_do or "Không có lý do.")

        view = ForceDeleteConfirmView(clan=clan, reason=ly_do or "Không có lý do.", bot=self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @admin_group.command(name="sync", description="Quét và đồng bộ Role, Kênh và Thành viên bị lệch")
    async def sync_clans(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        config = await self.bot.db.get_guild_config(guild.id)
        if not config:
            await interaction.followup.send("❌ Server chưa được thiết lập hệ thống Băng Đảng! Dùng `/clan-admin setup` trước.", ephemeral=True)
            return

        clans = await self.bot.db.get_all_clans_in_guild(guild.id)
        roles_fixed = 0
        channels_fixed = 0
        members_synced = 0
        issues = []

        category = guild.get_channel(int(config["clan_category_id"]))

        for c in clans:
            # 1. Kiểm tra Role
            role = guild.get_role(int(c["role_id"]))
            if not role:
                try:
                    role = await guild.create_role(
                        name=f"[{c['tag']}] {c['name']}",
                        color=discord.Color.from_str(c.get("color_hex", "#5865F2")),
                        hoist=True,
                        mentionable=True,
                        reason=f"Khôi phục role bị xóa cho {c['name']}"
                    )
                    await self.bot.db.update_clan(c["clan_id"], role_id=str(role.id))
                    roles_fixed += 1
                    issues.append(f"Khôi phục Role cho băng **{c['name']}**.")
                except Exception as e:
                    issues.append(f"Không thể tạo lại Role cho băng **{c['name']}**: {e}")

            # 2. Kiểm tra Kênh Chat, Nhật Ký Băng & Voice Public (KHÔNG tự ý sửa đổi/xóa kênh đang tồn tại)
            from utils.text_helper import to_channel_slug
            clean_slug = to_channel_slug(c["name"])[:30]
            expected_ch_name = f"💬・{clean_slug}"
            expected_log_name = f"📜・nhat-ky-{clean_slug}"[:35]

            text_ch = guild.get_channel(int(c["text_channel_id"])) if c.get("text_channel_id") else None
            if not text_ch and role:
                try:
                    text_ch = await guild.create_text_channel(
                        name=expected_ch_name,
                        category=category,
                        overwrites={
                            guild.default_role: discord.PermissionOverwrite(view_channel=False, send_messages=False),
                            role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                        }
                    )
                    await self.bot.db.update_clan(c["clan_id"], text_channel_id=str(text_ch.id))
                    channels_fixed += 1
                    issues.append(f"Khôi phục kênh chat cho băng **{c['name']}** ({expected_ch_name}).")
                except Exception as e:
                    issues.append(f"Không thể tạo lại kênh chat cho băng **{c['name']}**: {e}")

            log_ch = guild.get_channel(int(c["log_channel_id"])) if c.get("log_channel_id") else None
            if not log_ch and role:
                try:
                    log_ch = await guild.create_text_channel(
                        name=expected_log_name,
                        category=category,
                        overwrites={
                            guild.default_role: discord.PermissionOverwrite(view_channel=False, send_messages=False),
                            role: discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True),
                            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, read_message_history=True)
                        }
                    )
                    await self.bot.db.update_clan(c["clan_id"], log_channel_id=str(log_ch.id))
                    channels_fixed += 1
                    issues.append(f"Khôi phục kênh nhật ký cho băng **{c['name']}** ({expected_log_name}).")
                except Exception as e:
                    issues.append(f"Không thể tạo lại kênh nhật ký cho băng **{c['name']}**: {e}")

            voice_ch = guild.get_channel(int(c["voice_channel_id"])) if c.get("voice_channel_id") else None
            if not voice_ch and role:
                try:
                    voice_ch = await guild.create_voice_channel(
                        name=f"🔊・[{c['tag']}] Phòng Sinh Hoạt",
                        category=category,
                        overwrites={
                            guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
                            role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
                        }
                    )
                    await self.bot.db.update_clan(c["clan_id"], voice_channel_id=str(voice_ch.id))
                    channels_fixed += 1
                    issues.append(f"Khôi phục kênh voice public cho băng **{c['name']}**.")
                except Exception as e:
                    issues.append(f"Không thể tạo lại kênh voice cho băng **{c['name']}**: {e}")

            # 3. Đồng bộ thành viên Role vs DB
            if role:
                db_members = await self.bot.db.get_clan_members(c["clan_id"])
                db_uids = {int(m["user_id"]) for m in db_members}

                # Cấp role cho người trong DB mà thiếu role
                for m in db_members:
                    g_member = guild.get_member(int(m["user_id"]))
                    if g_member and role not in g_member.roles:
                        try:
                            await g_member.add_roles(role, reason="Đồng bộ role băng")
                            members_synced += 1
                        except Exception:
                            pass

                # Gỡ role của người có role nhưng không có trong DB
                for g_member in role.members:
                    if g_member.id not in db_uids and not g_member.bot:
                        try:
                            await g_member.remove_roles(role, reason="Gỡ role mồ côi")
                            members_synced += 1
                        except Exception:
                            pass

        embed = discord.Embed(
            title="🔄 ĐỒNG BỘ HỆ THỐNG HOÀN TẤT",
            description=f"Đã quét toàn bộ **{len(clans)}** băng đảng trong server.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="🛡️ Role Khôi Phục", value=str(roles_fixed), inline=True)
        embed.add_field(name="💬 Kênh Khôi Phục", value=str(channels_fixed), inline=True)
        embed.add_field(name="👥 Thành Viên Đồng Bộ", value=str(members_synced), inline=True)

        if issues:
            embed.add_field(name="Chi Tiết Xử Lý", value="\n".join(issues[:10]), inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="bot-access", description="Chọn Role được phép dùng bot, Bật tất cả hoặc Tắt tất cả (Chỉ Chủ Bot)")
    async def owner_bot_access(self, interaction: discord.Interaction):
        is_owner = await self.bot.is_bot_owner(interaction.user) if hasattr(self.bot, "is_bot_owner") else await self.bot.is_owner(interaction.user)
        if not is_owner:
            await interaction.response.send_message("🔒 Lệnh này chỉ dành riêng cho **Chủ Bot (Bot Owner)**!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "register_user_panel"):
            await self.bot.register_user_panel(interaction.user.id, interaction)

        cfg = await self.bot.db.get_bot_access_config(interaction.guild_id)
        embed = build_bot_access_embed(interaction.guild.name, cfg["mode"], cfg["role_ids"])
        view = BotAccessControlView(guild_name=interaction.guild.name, mode=cfg["mode"], role_ids=cfg["role_ids"], bot=self.bot)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ClanAdmin(bot))
