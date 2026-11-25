"""
Cog Xử Lý Sự Kiện Nền & Tác Vụ Định Kỳ
Bao gồm: Chat EXP, Voice Co-op 5 phút, Nhắc kèo Party, Reset Tuần,
Xử lý người rời server (kế vị / giải tán) và Cảnh báo xóa Role/Kênh thủ công
"""

import discord
from discord.ext import commands, tasks
from datetime import datetime
import time
from typing import Dict, Tuple

from utils.constants import (
    Ranks,
    EXP_REWARDS,
    LEVELS
)
from utils.embeds import get_level_info
from utils.time_helper import (
    get_vietnam_now,
    get_current_week_key
)
from utils.logger import setup_logging

logger = setup_logging("ClanEvents")

class ClanEvents(commands.Cog):
    """Lắng nghe sự kiện Gateway và chạy tác vụ nền định kỳ"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Cache chống spam EXP chat trong RAM: (guild_id, user_id) -> timestamp
        self._chat_cooldowns: Dict[Tuple[int, int], float] = {}
        # Cờ đánh dấu đã chạy reset tuần cho chu kỳ hiện tại
        self._last_weekly_reset_key: str = ""

    def cog_unload(self):
        if self.voice_coop_ticker.is_running():
            self.voice_coop_ticker.cancel()
        if self.one_minute_ticker.is_running():
            self.one_minute_ticker.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        """Khởi động các vòng lặp định kỳ khi bot đã sẵn sàng"""
        if not self.voice_coop_ticker.is_running():
            self.voice_coop_ticker.start()
            logger.info("Đã khởi chạy vòng lặp Voice Co-op Ticker (5 phút).")
        if not self.one_minute_ticker.is_running():
            self.one_minute_ticker.start()
            logger.info("Đã khởi chạy vòng lặp One Minute Ticker (1 phút).")

    # =========================================================================
    # SỰ KIỆN: TIN NHẮN TĂNG EXP CHAT
    # =========================================================================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or not isinstance(message.author, discord.Member):
            return

        content = message.content.strip()
        if len(content) < EXP_REWARDS.CHAT_MIN_LENGTH:
            return

        now = time.time()
        key = (message.guild.id, message.author.id)
        last_chat = self._chat_cooldowns.get(key, 0)

        if now - last_chat < EXP_REWARDS.CHAT_COOLDOWN_SECONDS:
            return

        # Kiểm tra người dùng có thuộc băng nào không
        clan = await self.bot.db.get_clan_by_member(message.guild.id, message.author.id)
        if not clan:
            return

        self._chat_cooldowns[key] = now

        exp_to_add = EXP_REWARDS.CHAT_EXP
        await self.bot.db.add_clan_exp(clan["clan_id"], exp_to_add, exp_to_add)
        await self.bot.db.add_contribution_points(message.guild.id, message.author.id, EXP_REWARDS.CHAT_CONTRIBUTION)

        # Cập nhật tiến độ nhiệm vụ tuần CHAT_MESSAGES
        week_key = get_current_week_key()
        quest_res = await self.bot.db.increment_quest_progress(clan["clan_id"], week_key, "CHAT_MESSAGES", 1)
        if quest_res["completed_now"]:
            await self.bot.db.add_clan_exp(clan["clan_id"], quest_res["reward_exp"], quest_res["reward_exp"])
            text_ch = message.guild.get_channel(int(clan["text_channel_id"]))
            if text_ch:
                embed = discord.Embed(
                    title="🎯 HOÀN THÀNH NHIỆM VỤ TUẦN!",
                    description=f"Chúc mừng anh em băng **{clan['name']}** đã hoàn thành nhiệm vụ **💬 Sôi Nổi Kênh Chat** (+{quest_res['reward_exp']} EXP)!",
                    color=discord.Color.gold(),
                    timestamp=datetime.now()
                )
                await text_ch.send(embed=embed)

        # Kiểm tra thăng cấp
        await self._check_level_up(message.guild, clan["clan_id"], clan["level"])

    # =========================================================================
    # VÒNG LẶP: CỘNG EXP VOICE CO-OP (MỖI 5 PHÚT)
    # =========================================================================
    @tasks.loop(minutes=5.0)
    async def voice_coop_ticker(self):
        """Quét các phòng voice: từ 2 thành viên cùng băng trở lên (không deaf, không AFK) được cộng EXP"""
        logger.debug("Đang quét các phòng voice để cộng EXP co-op...")
        try:
            for guild in self.bot.guilds:
                cfg = await self.bot.db.get_guild_config(guild.id)
                if not cfg:
                    continue

                afk_channel_id = guild.afk_channel.id if guild.afk_channel else None

                for vc in guild.voice_channels:
                    if vc.id == afk_channel_id or len(vc.members) < EXP_REWARDS.VOICE_MIN_MEMBERS:
                        continue

                    # Gom nhóm thành viên theo clan
                    clan_users_map: Dict[int, list] = {}

                    for m in vc.members:
                        if m.bot or m.voice.self_deaf or m.voice.deaf:
                            continue

                        mem_rec = await self.bot.db.get_clan_by_member(guild.id, m.id)
                        if not mem_rec:
                            continue

                        clan_id = mem_rec["clan_id"]
                        if clan_id not in clan_users_map:
                            clan_users_map[clan_id] = []
                        clan_users_map[clan_id].append(m.id)

                    # Thưởng EXP cho các băng đủ từ 2 người trở lên
                    for clan_id, user_ids in clan_users_map.items():
                        if len(user_ids) >= EXP_REWARDS.VOICE_MIN_MEMBERS:
                            clan = await self.bot.db.get_clan_by_id(clan_id)
                            if not clan:
                                continue

                            exp_to_add = EXP_REWARDS.VOICE_EXP
                            await self.bot.db.add_clan_exp(clan_id, exp_to_add, exp_to_add)

                            for uid in user_ids:
                                await self.bot.db.add_contribution_points(guild.id, uid, EXP_REWARDS.VOICE_CONTRIBUTION)

                            # Tiến độ nhiệm vụ tuần VOICE_MINUTES
                            week_key = get_current_week_key()
                            quest_res = await self.bot.db.increment_quest_progress(
                                clan_id, week_key, "VOICE_MINUTES", EXP_REWARDS.VOICE_INTERVAL_MINUTES
                            )
                            if quest_res["completed_now"]:
                                await self.bot.db.add_clan_exp(clan_id, quest_res["reward_exp"], quest_res["reward_exp"])

                            await self._check_level_up(guild, clan_id, clan["level"])
                            logger.info(f"Cộng +{exp_to_add} EXP voice co-op cho băng {clan['name']} ({len(user_ids)} người)")

        except Exception as e:
            logger.error(f"Lỗi trong voice_coop_ticker: {e}", exc_info=True)

    @voice_coop_ticker.before_loop
    async def before_voice_ticker(self):
        await self.bot.wait_until_ready()

    # =========================================================================
    # VÒNG LẶP: HẾT HẠN YÊU CẦU & RESET TUẦN (MỖI 1 PHÚT)
    # =========================================================================
    @tasks.loop(minutes=1.0)
    async def one_minute_ticker(self):
        now = int(time.time())

        # 1. Xử lý yêu cầu xin vào / lời mời quá hạn & vô hiệu nút
        try:
            expired = await self.bot.db.get_expired_pending_requests()
            if expired:
                for req in expired:
                    if req.get("message_id"):
                        guild = self.bot.get_guild(int(req["guild_id"]))
                        if guild:
                            for ch in guild.text_channels:
                                try:
                                    msg = await ch.fetch_message(int(req["message_id"]))
                                    if msg:
                                        for row in msg.components:
                                            for comp in row.children:
                                                comp.disabled = True
                                        await msg.edit(view=None)
                                        break
                                except Exception:
                                    continue
                await self.bot.db.mark_expired_requests()
        except Exception as e:
            logger.error(f"Lỗi dọn dẹp yêu cầu quá hạn: {e}")

        # 3. Dọn dẹp cooldown rời băng đã hết hạn
        try:
            await self.bot.db.clean_expired_cooldowns()
        except Exception as e:
            logger.error(f"Lỗi dọn dẹp cooldown: {e}")

        # 4. Kiểm tra Reset Tuần (Thứ Hai 00:00 giờ VN)
        try:
            vn_now = get_vietnam_now()
            # Thứ Hai là weekday() == 0, kiểm tra lúc 00:00 (hoặc 00:01)
            if vn_now.weekday() == 0 and vn_now.hour == 0 and vn_now.minute <= 2:
                current_week = get_current_week_key()
                if self._last_weekly_reset_key != current_week:
                    self._last_weekly_reset_key = current_week
                    await self._execute_weekly_reset(current_week)
        except Exception as e:
            logger.error(f"Lỗi kiểm tra reset tuần: {e}")

    @one_minute_ticker.before_loop
    async def before_one_minute_ticker(self):
        await self.bot.wait_until_ready()

    async def _execute_weekly_reset(self, current_week: str):
        """Thực thi Reset Tuần: vinh danh top 3, reset weekly_exp và sinh nhiệm vụ tuần mới"""
        logger.info(f"Bắt đầu quy trình tự động Reset Tuần cho chu kỳ: {current_week}")

        for guild in self.bot.guilds:
            cfg = await self.bot.db.get_guild_config(guild.id)
            if not cfg:
                continue

            # 1. Vinh danh Top 3 Băng Năng Động Nhất Tuần
            top_clans = await self.bot.db.get_leaderboard(guild.id, criteria="weekly", limit=3)
            if cfg.get("log_channel_id") and top_clans:
                log_ch = guild.get_channel(int(cfg["log_channel_id"]))
                if log_ch:
                    medals = ["🥇", "🥈", "🥉"]
                    lines = [
                        f"{medals[i]} **[{c['tag']}] {c['name']}** — **+{c.get('weekly_exp', 0):,}** EXP Tuần (Chủ Băng: <@{c['leader_id']}>)"
                        for i, c in enumerate(top_clans)
                    ]
                    embed = discord.Embed(
                        title="🏆 VINH DANH TOP 3 BĂNG NĂNG ĐỘNG NHẤT TUẦN QUA! 🏆",
                        description=f"Tuần mới đã khởi tranh! Xin chúc mừng các hội nhóm tích cực nhất tuần vừa rồi:\n\n" + "\n\n".join(lines),
                        color=discord.Color.gold(),
                        timestamp=datetime.now()
                    )
                    embed.set_footer(text="Điểm năng động tuần đã được làm mới về 0!")
                    await log_ch.send(embed=embed)

            # 2. Reset weekly_exp = 0
            await self.bot.db.reset_weekly_exp(guild.id)

            # 3. Tạo bộ nhiệm vụ tuần mới cho tất cả các băng
            all_clans = await self.bot.db.get_all_clans_in_guild(guild.id)
            for c in all_clans:
                await self.bot.db.ensure_weekly_quests(c["clan_id"], current_week)

        logger.info(f"Hoàn tất Reset Tuần cho chu kỳ {current_week}!")

    # =========================================================================
    # SỰ KIỆN: NGƯỜI RỜI SERVER (KẾ VỊ HOẶC GIẢI TÁN BĂNG)
    # =========================================================================
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        user_id = member.id

        try:
            membership = await self.bot.db.get_member(guild.id, user_id)
            if not membership:
                return

            clan = await self.bot.db.get_clan_by_id(membership["clan_id"])
            if not clan:
                await self.bot.db.remove_member(guild.id, user_id)
                return

            # Nếu người rời là CHỦ BĂNG
            if int(clan["leader_id"]) == user_id:
                logger.warn(f"Chủ Băng {clan['name']} ({user_id}) đã rời server Discord! Đang tìm người kế vị...")
                remaining = [m for m in await self.bot.db.get_clan_members(clan["clan_id"]) if int(m["user_id"]) != user_id]

                if not remaining:
                    # Băng không còn ai -> Tự động giải tán và dọn dẹp
                    logger.info(f"Băng {clan['name']} trống sau khi Chủ Băng rời. Tự động giải tán băng.")
                    for ch_key in ("text_channel_id", "voice_channel_id", "extra_voice_channel_id"):
                        ch_id = clan.get(ch_key)
                        if ch_id:
                            ch = guild.get_channel(int(ch_id))
                            if ch:
                                await ch.delete(reason="Băng trống tự giải tán")
                    role = guild.get_role(int(clan["role_id"]))
                    if role:
                        await role.delete(reason="Băng trống tự giải tán")
                    await self.bot.db.delete_clan(clan["clan_id"])
                    return

                # Kế vị: Chọn người thâm niên & chức vụ cao nhất đứng đầu danh sách
                successor = remaining[0]
                await self.bot.db.transfer_leadership(clan["clan_id"], guild.id, user_id, int(successor["user_id"]))
                await self.bot.db.remove_member(guild.id, user_id)

                await self.bot.db.add_clan_log(
                    clan_id=clan["clan_id"],
                    actor_id=user_id,
                    target_id=int(successor["user_id"]),
                    action="AUTO_TRANSFER_LEADER",
                    details=f"Chủ Băng cũ đã rời khỏi server. Quyền Chủ Băng tự động trao cho <@{successor['user_id']}>."
                )

                text_ch = guild.get_channel(int(clan["text_channel_id"]))
                if text_ch:
                    embed = discord.Embed(
                        title="👑 TỰ ĐỘNG CHUYỂN GIAO QUYỀN CHỦ BĂNG",
                        description=f"Chủ Băng cũ (<@{user_id}>) đã rời khỏi server Discord.\nDo đó, chức vụ **Chủ Băng (LEADER)** của **[{clan['tag']}] {clan['name']}** đã được tự động trao lại cho thành viên thâm niên nhất: <@{successor['user_id']}>!",
                        color=discord.Color.gold(),
                        timestamp=datetime.now()
                    )
                    await text_ch.send(embed=embed)

            else:
                # Thành viên thường / Cán bộ / Phó băng rời server
                await self.bot.db.remove_member(guild.id, user_id)
                cfg = await self.bot.db.get_guild_config(guild.id)
                cd_hours = cfg["leave_cooldown_hours"] if cfg else 24
                await self.bot.db.set_cooldown(guild.id, user_id, cd_hours)

                await self.bot.db.add_clan_log(
                    clan_id=clan["clan_id"],
                    actor_id=user_id,
                    action="LEAVE_SERVER",
                    details=f"<@{user_id}> rời khỏi server Discord và tự động rời khỏi băng."
                )

        except Exception as e:
            logger.error(f"Lỗi khi xử lý thành viên rời server: {e}", exc_info=True)

    # =========================================================================
    # SỰ KIỆN: CẢNH BÁO ROLE / CHANNEL BỊ XÓA THỦ CÔNG
    # =========================================================================
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        clan = await self.bot.db.get_clan_by_role_id(role.id)
        if not clan:
            return

        logger.warn(f"Role của băng {clan['name']} ({role.id}) vừa bị xóa thủ công!")
        cfg = await self.bot.db.get_guild_config(role.guild.id)
        if cfg and cfg.get("log_channel_id"):
            log_ch = role.guild.get_channel(int(cfg["log_channel_id"]))
            if log_ch:
                embed = discord.Embed(
                    title="⚠️ CẢNH BÁO: ROLE BĂNG ĐẢNG BỊ XÓA THỦ CÔNG",
                    description=f"Role của băng **[{clan['tag']}] {clan['name']}** vừa bị xóa khỏi Server.\n\n👉 **Khắc phục:** Quản trị viên vui lòng chạy lệnh `/clan-admin sync` để bot tự động tạo lại Role và cấp lại cho thành viên!",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                await log_ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        clan = await self.bot.db.get_clan_by_channel_id(channel.id)
        if not clan:
            return

        logger.warn(f"Kênh của băng {clan['name']} ({channel.id}) vừa bị xóa thủ công!")
        cfg = await self.bot.db.get_guild_config(channel.guild.id)
        if cfg and cfg.get("log_channel_id"):
            log_ch = channel.guild.get_channel(int(cfg["log_channel_id"]))
            if log_ch:
                embed = discord.Embed(
                    title="⚠️ CẢNH BÁO: KÊNH BĂNG ĐẢNG BỊ XÓA THỦ CÔNG",
                    description=f"Một kênh của băng **[{clan['tag']}] {clan['name']}** vừa bị xóa khỏi Server.\n\n👉 **Khắc phục:** Quản trị viên vui lòng dùng `/clan-admin sync` để bot tự động khôi phục kênh sinh hoạt!",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                await log_ch.send(embed=embed)

    # =========================================================================
    # HÀM PHỤ TRỢ: KIỂM TRA LÊN CẤP BĂNG
    # =========================================================================
    async def _check_level_up(self, guild: discord.Guild, clan_id: int, old_level: int):
        clan = await self.bot.db.get_clan_by_id(clan_id)
        if not clan:
            return

        lvl_info = get_level_info(clan["exp"])
        if lvl_info["level"] > old_level:
            extra_voice_id = clan.get("extra_voice_channel_id")

            # Mở khóa Level 3: Tạo Voice Channel thứ 2
            if lvl_info["level"] >= 3 and not extra_voice_id:
                try:
                    cfg = await self.bot.db.get_guild_config(guild.id)
                    category = guild.get_channel(int(cfg["clan_category_id"])) if cfg else None
                    clan_role = guild.get_role(int(clan["role_id"]))

                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
                        clan_role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, use_voice_activation=True),
                        guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, manage_channels=True, move_members=True)
                    }

                    vc2 = await guild.create_voice_channel(
                        name=f"🔊・[{clan['tag']}] Voice 2",
                        category=category,
                        overwrites=overwrites
                    )
                    extra_voice_id = vc2.id
                    logger.info(f"Đã tạo kênh Voice thứ 2 cho băng {clan['name']}: {vc2.id}")
                except Exception as e:
                    logger.error(f"Không thể tạo kênh voice thứ 2 cho {clan['name']}: {e}")

            await self.bot.db.update_clan_level(
                clan_id,
                level=lvl_info["level"],
                max_members=lvl_info["max_members"],
                extra_voice_channel_id=extra_voice_id
            )

            await self.bot.db.add_clan_log(
                clan_id=clan_id,
                actor_id=self.bot.user.id,
                action="LEVEL_UP",
                details=f"Băng thăng cấp từ Level {old_level} lên Level {lvl_info['level']}!"
            )

            # Thông báo vào kênh chat
            text_ch = guild.get_channel(int(clan["text_channel_id"]))
            if text_ch:
                embed = discord.Embed(
                    title=f"🎉 CHÚC MỪNG BĂNG ĐÃ THĂNG CẤP LÊN LEVEL {lvl_info['level']}! 🎉",
                    description=f"Toàn thể băng **{clan['name']}** đã chính thức cán mốc cấp độ mới!",
                    color=discord.Color.gold(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="✨ Cấp Độ Mới", value=f"**Cấp {lvl_info['level']} — {lvl_info['title']}**", inline=True)
                embed.add_field(name="👥 Giới Hạn Thành Viên", value=f"Tăng lên **{lvl_info['max_members']}** người", inline=True)
                embed.add_field(name="🎁 Đặc Quyền Mở Khóa", value=lvl_info["perks"], inline=False)
                embed.set_footer(text="Hãy tiếp tục hoạt động để mở khóa thêm nhiều đặc quyền độc quyền!")
                await text_ch.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ClanEvents(bot))
