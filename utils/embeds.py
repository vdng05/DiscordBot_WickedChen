"""
Xây dựng Discord Embeds trực quan, đồng bộ và thẩm mỹ cao
Tích hợp tài nguyên đồ họa phong phú (BoardAssets, Banners, Thumbnails) cho các Bảng
"""

import discord
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from utils.constants import Ranks, JoinModes, LEVELS


class BoardAssets:
    """Kho tài nguyên đồ họa chất lượng cao dành cho các Bảng (Boards) của Bot"""
    # Banners (Ảnh lớn 16:9 sắc nét, tải nhanh)
    DEFAULT_CLAN_BANNER = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=1000&auto=format&fit=crop"
    DEFAULT_CLAN_LOGO = "https://images.unsplash.com/photo-1579546929518-9e396f3cc809?q=80&w=400&auto=format&fit=crop"
    LEADERBOARD_BANNER = "https://images.unsplash.com/photo-1542751371-adc38448a05e?q=80&w=1000&auto=format&fit=crop"
    LEADERBOARD_THUMBNAIL = "https://images.unsplash.com/photo-1567427017947-545c5f8d16ad?q=80&w=400&auto=format&fit=crop"
    QUESTS_BANNER = "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?q=80&w=1000&auto=format&fit=crop"
    QUESTS_THUMBNAIL = "https://images.unsplash.com/photo-1614680376593-902f749f7ffc?q=80&w=400&auto=format&fit=crop"
    PARTY_BANNER = "https://images.unsplash.com/photo-1511512578047-dfb367046420?q=80&w=1000&auto=format&fit=crop"
    DEFAULT_PARTY_THUMBNAIL = "https://images.unsplash.com/photo-1612287232230-e374528148b3?q=80&w=400&auto=format&fit=crop"
    HUB_BANNER = "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?q=80&w=1000&auto=format&fit=crop"
    HUB_THUMBNAIL = "https://images.unsplash.com/photo-1563089145-599997674d42?q=80&w=400&auto=format&fit=crop"
    ROLE_SETUP_BANNER = "https://images.unsplash.com/photo-1550745165-9bc0b252726f?q=80&w=1000&auto=format&fit=crop"
    ROLE_SETUP_THUMBNAIL = "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=400&auto=format&fit=crop"
    CLAN_LIST_BANNER = "https://images.unsplash.com/photo-1511512578047-dfb367046420?q=80&w=1000&auto=format&fit=crop"
    LOGS_THUMBNAIL = "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=400&auto=format&fit=crop"

    # Game Thumbnails cho Party LFG
    GAME_THUMBNAILS = {
        "valorant": "https://images.unsplash.com/photo-1542751371-adc38448a05e?q=80&w=400&auto=format&fit=crop",
        "lol": "https://images.unsplash.com/photo-1563089145-599997674d42?q=80&w=400&auto=format&fit=crop",
        "liên minh": "https://images.unsplash.com/photo-1563089145-599997674d42?q=80&w=400&auto=format&fit=crop",
        "cs2": "https://images.unsplash.com/photo-1511512578047-dfb367046420?q=80&w=400&auto=format&fit=crop",
        "csgo": "https://images.unsplash.com/photo-1511512578047-dfb367046420?q=80&w=400&auto=format&fit=crop",
        "genshin": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?q=80&w=400&auto=format&fit=crop",
        "pubg": "https://images.unsplash.com/photo-1542751371-adc38448a05e?q=80&w=400&auto=format&fit=crop",
        "liên quân": "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?q=80&w=400&auto=format&fit=crop",
        "tft": "https://images.unsplash.com/photo-1579546929518-9e396f3cc809?q=80&w=400&auto=format&fit=crop"
    }

    @classmethod
    def get_game_thumbnail(cls, title: str) -> str:
        clean = title.lower()
        for kw, url in cls.GAME_THUMBNAILS.items():
            if kw in clean:
                return url
        return cls.DEFAULT_PARTY_THUMBNAIL


def create_progress_bar(current: int, max_val: int, size: int = 12) -> str:
    """Tạo thanh tiến trình đồ họa hiện đại [▰▰▰▰▰▰▰▱▱▱] kèm tỷ lệ phần trăm"""
    if max_val <= 0:
        return "`[▰▰▰▰▰▰▰▰▰▰▰▰]` **(TỐI ĐA)**"
    ratio = min(1.0, max(0.0, current / max_val))
    filled = round(ratio * size)
    empty = size - filled
    bar = "▰" * filled + "▱" * empty
    percent = int(ratio * 100)
    return f"`[{bar}]` **{percent}%**"


def parse_hex_color(hex_str: Optional[str]) -> discord.Color:
    """Chuyển mã Hex sang discord.Color an toàn"""
    if not hex_str:
        return discord.Color.blurple()
    try:
        clean = hex_str.strip().lstrip("#")
        return discord.Color(int(clean, 16))
    except (ValueError, TypeError):
        return discord.Color.blurple()


def get_level_info(total_exp: int) -> Dict[str, Any]:
    """Tính toán thông tin cấp độ và tiến trình EXP hiện tại"""
    current = LEVELS[0]
    next_level = None

    for i, lvl in enumerate(LEVELS):
        if total_exp >= lvl["req_exp"]:
            current = lvl
            next_level = LEVELS[i + 1] if i + 1 < len(LEVELS) else None
        else:
            break

    is_max = next_level is None
    cur_req = current["req_exp"]
    next_req = next_level["req_exp"] if next_level else cur_req
    progress_exp = total_exp - cur_req
    needed_exp = (next_req - cur_req) if not is_max else 0
    ratio = 1.0 if is_max else (progress_exp / needed_exp if needed_exp > 0 else 0.0)

    return {
        "level": current["level"],
        "title": current["title"],
        "max_members": current["max_members"],
        "perks": current["perks"],
        "is_max": is_max,
        "total_exp": total_exp,
        "cur_req": cur_req,
        "next_req": next_req,
        "progress_exp": progress_exp,
        "needed_exp": needed_exp,
        "ratio": ratio
    }


def build_clan_info_embed(clan: Dict[str, Any], members: List[Dict[str, Any]], level_info: Dict[str, Any], attachment_filename: Optional[str] = None) -> discord.Embed:
    """Tạo Embed hồ sơ chi tiết của băng đảng với đồ họa sinh động"""
    co_leaders = [m for m in members if m["rank"] == Ranks.CO_LEADER]
    co_leaders_str = ", ".join(f"<@{m['user_id']}>" for m in co_leaders) if co_leaders else "_Chưa có Phó Băng_"

    embed_color = parse_hex_color(clan.get("color_hex"))

    level_badges = {
        1: "🥉 Tân Binh",
        2: "🥈 Khởi Nghĩa",
        3: "🥇 Trưởng Thành (Mở Voice 2)",
        4: "💎 Tinh Anh",
        5: "👑 Bá Chủ Hoàng Gia"
    }
    badge = level_badges.get(level_info["level"], "🛡️ Băng Đảng")

    if level_info["is_max"]:
        exp_bar = "`[▰▰▰▰▰▰▰▰▰▰▰▰]` **Đạt cấp tối đa (MAX)**"
        exp_display = f"**Lv.{level_info['level']} {badge}** — {clan['exp']:,} EXP (Tối Đa)"
    else:
        exp_bar = create_progress_bar(level_info["progress_exp"], level_info["needed_exp"])
        exp_display = f"**Lv.{level_info['level']} {badge}** — {clan['exp']:,} / {level_info['next_req']:,} EXP"

    embed = discord.Embed(
        title=f"🏰 HỒ SƠ BĂNG: [{clan['tag']}] {clan['name']}",
        description=f"💬 *\"{clan.get('description') or 'Chưa có khẩu hiệu.'}\"*",
        color=embed_color,
        timestamp=datetime.now()
    )

    embed.add_field(name="👑 Chủ Băng", value=f"<@{clan['leader_id']}>", inline=True)
    embed.add_field(name="⭐ Ban Cán Bộ", value=co_leaders_str, inline=True)
    embed.add_field(name="👥 Sĩ Số Thành Viên", value=f"**{len(members)} / {clan['max_members']}** thành viên", inline=True)

    embed.add_field(name="🌟 Tiến Trình Cấp Độ", value=f"{exp_display}\n{exp_bar}", inline=False)
    embed.add_field(name="🔥 Điểm Năng Động Tuần", value=f"**+{clan.get('weekly_exp', 0):,}** EXP", inline=True)
    embed.add_field(name="🚪 Chế Độ Tuyển Quân", value=JoinModes.NAMES.get(clan.get("join_mode"), clan.get("join_mode", "APPROVAL")), inline=True)
    embed.add_field(name="📅 Ngày Khởi Lập", value=f"<t:{clan['created_at']}:D> (<t:{clan['created_at']}:R>)", inline=True)

    if clan.get("logo_url"):
        embed.set_thumbnail(url=clan["logo_url"])

    if attachment_filename:
        embed.set_image(url=f"attachment://{attachment_filename}")
    elif clan.get("banner_url"):
        embed.set_image(url=clan["banner_url"])

    embed.set_footer(text=f"ID Băng: {clan['clan_id']} • Cấp {level_info['level']} ({level_info['title']})")
    return embed


def build_members_embed(clan: Dict[str, Any], members: List[Dict[str, Any]], page: int = 1, page_size: int = 10, rank_filter: Optional[str] = None) -> Tuple[discord.Embed, int]:
    """Tạo Embed danh sách thành viên hỗ trợ phân trang & lọc chức vụ kèm đồ họa"""
    embed_color = parse_hex_color(clan.get("color_hex"))
    filtered = [m for m in members if m["rank"] == rank_filter] if rank_filter else members

    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
    current_page = min(max(1, page), total_pages)
    start_idx = (current_page - 1) * page_size
    paged = filtered[start_idx:start_idx + page_size]

    rank_badges = {
        Ranks.LEADER: "👑",
        Ranks.CO_LEADER: "⭐",
        Ranks.OFFICER: "🛡️",
        Ranks.MEMBER: "👤"
    }

    if paged:
        lines = []
        for i, m in enumerate(paged):
            idx = start_idx + i + 1
            badge = rank_badges.get(m["rank"], "👤")
            r_name = Ranks.NAMES.get(m["rank"], m["rank"])
            title_tag = f" • 【 {m['custom_title']} 】" if m.get("custom_title") else ""
            lines.append(
                f"`#{idx:02d}` {badge} <@{m['user_id']}> **({r_name})**{title_tag}\n"
                f"   ┗ 🏆 Cống hiến: **{m['contribution_points']}** • 🔥 Chuỗi Streak: **{m.get('checkin_streak', 0)} ngày**"
            )
        desc = f"📊 Tổng cộng: **{len(filtered)}** thành viên {f'(Bộ lọc: {Ranks.NAMES.get(rank_filter)})' if rank_filter else ''}\n\n" + "\n\n".join(lines)
    else:
        desc = "_Không tìm thấy thành viên nào phù hợp với bộ lọc._"

    embed = discord.Embed(
        title=f"👥 BẢNG THÀNH VIÊN: [{clan['tag']}] {clan['name']}",
        description=desc,
        color=embed_color,
        timestamp=datetime.now()
    )
    if clan.get("logo_url"):
        embed.set_thumbnail(url=clan["logo_url"])
    embed.set_footer(text=f"Trang {current_page} / {total_pages} • Sĩ số: {len(members)}/{clan['max_members']}")
    return embed, total_pages


def build_milestones_embed(clan: Dict[str, Any], milestones: List[Dict[str, Any]]) -> discord.Embed:
    """Tạo Embed dòng thời gian biên niên sử cột mốc của Băng Đảng"""
    embed = discord.Embed(
        title=f"📜 BIÊN NIÊN SỬ CỘT MỐC: [{clan['tag']}] {clan['name']}",
        description="Ghi nhận các chiến tích, mốc thăng cấp và khoảnh khắc vẻ vang của băng đảng!",
        color=parse_hex_color(clan.get("color_hex")),
        timestamp=datetime.now()
    )
    if not milestones:
        embed.description += "\n\n_Băng đảng hiện chưa có cột mốc nào được ghi nhận. Hãy tiếp tục hoạt động cùng anh em nhé!_"
    else:
        for idx, m in enumerate(milestones[:10]):
            achieved = m.get("achieved_at", int(datetime.now().timestamp()))
            embed.add_field(
                name=f"{idx+1}. {m['title']} (<t:{achieved}:d>)",
                value=m.get("description") or "_Không có mô tả chi tiết._",
                inline=False
            )
    if clan.get("logo_url"):
        embed.set_thumbnail(url=clan["logo_url"])
    embed.set_footer(text="Cột mốc được tự động ghi nhận theo thời gian thực")
    return embed


def build_clan_list_embed(guild_name: str, clans: List[Dict[str, Any]]) -> discord.Embed:
    """Tạo Embed hiển thị danh sách tất cả các băng trong server"""
    embed = discord.Embed(
        title=f"📜 BẢNG DANH MỤC BĂNG ĐẢNG — {guild_name}",
        description=(
            f"Máy chủ hiện đang có **{len(clans)}** băng đảng đang hoạt động.\n"
            "👉 Hãy chọn băng phù hợp và dùng lệnh `/clan apply [tên_băng]` để gia nhập!"
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )

    if not clans:
        embed.description = "Server hiện chưa có băng đảng nào! Hãy là người tiên phong lập băng với lệnh `/clan create`."
        return embed

    lines = []
    for i, c in enumerate(clans[:12]):
        is_full = c["member_count"] >= c["max_members"]
        status = "🔴 Đầy Slot" if is_full else ("🟢 Mở Tự Do" if c["join_mode"] == "OPEN" else ("🔒 Chỉ Nhận Lời Mời" if c["join_mode"] == "INVITE_ONLY" else "🟡 Cần Xét Duyệt"))
        lines.append(
            f"**`#{i + 1:02d}` [{c['tag']}] {c['name']}** (Lv.{c['level']})\n"
            f"   ┗ 👥 **{c['member_count']}/{c['max_members']}** thành viên • {status} • 👑 <@{c['leader_id']}>"
        )

    embed.add_field(name="🏰 Danh Sách Băng Đang Sinh Hoạt", value="\n\n".join(lines), inline=False)
    return embed


def build_leaderboard_embed(guild_name: str, clans: List[Dict[str, Any]], criteria: str = "level", attachment_filename: Optional[str] = None) -> discord.Embed:
    """Tạo Embed Bảng Xếp Hạng tôn vinh mức độ gắn kết với đồ họa vinh danh xịn sò"""
    criteria_names = {
        "level": "🌟 Cấp Độ & Tổng Điểm EXP",
        "weekly": "🔥 Năng Động Tuần",
        "members": "👥 Sĩ Số Thành Viên"
    }

    embed = discord.Embed(
        title=f"🏆 BẢNG VINH DANH BĂNG ĐẢNG — {guild_name}",
        description=(
            f"🎯 Tiêu chí xếp hạng: **{criteria_names.get(criteria, criteria)}**\n"
            "Bảng xếp hạng tôn vinh tinh thần đồng đội và độ gắn kết giữa các thành viên."
        ),
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )

    if attachment_filename:
        embed.set_image(url=f"attachment://{attachment_filename}")

    if not clans:
        embed.description = "Chưa có dữ liệu băng đảng nào trên máy chủ để xếp hạng."
        return embed

    lines = []
    for idx, c in enumerate(clans[:10]):
        mem_cnt = c.get("member_count", 0)
        max_m = c.get("max_members", 20)
        if criteria == "weekly":
            metric = f"+{c.get('weekly_exp', 0):,} EXP tuần"
        elif criteria == "members":
            metric = f"{mem_cnt}/{max_m} thành viên"
        else:
            metric = f"Lv.{c['level']} • {c['exp']:,} EXP"

        if idx == 0:
            podium = (
                f"👑 ┏━━ 🥇 **TOP 1 QUÁN QUÂN: [{c['tag']}] {c['name']}** ━━┓\n"
                f"   ┃ 👑 Chủ Băng: <@{c['leader_id']}>\n"
                f"   ┃ 📊 Thành Tích: **{metric}** • Sĩ số: **{mem_cnt}** người\n"
                f"   ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛"
            )
            lines.append(podium)
        elif idx == 1:
            lines.append(f"🥈 **TOP 2 Á QUÂN:** **[{c['tag']}] {c['name']}**\n   ↳ 👑 <@{c['leader_id']}> • 📊 **{metric}**")
        elif idx == 2:
            lines.append(f"🥉 **TOP 3 QUÝ QUÂN:** **[{c['tag']}] {c['name']}**\n   ↳ 👑 <@{c['leader_id']}> • 📊 **{metric}**")
        else:
            lines.append(f"`#{idx + 1:02d}` **[{c['tag']}] {c['name']}** ━ 📊 **{metric}** • 👑 <@{c['leader_id']}>")

    embed.add_field(name="🏅 Bảng Xếp Hạng Top Băng", value="\n\n".join(lines), inline=False)
    embed.set_footer(text=f"Cập nhật lúc {datetime.now().strftime('%H:%M • %d/%m/%Y')}")
    return embed


def build_quests_embed(clan: Dict[str, Any], quests: List[Dict[str, Any]], week_key: str, attachment_filename: Optional[str] = None) -> discord.Embed:
    """Tạo Embed Bảng Nhiệm Vụ Tuần (Quest Board) với đồ họa phiêu lưu và tiến độ chi tiết"""
    embed_color = parse_hex_color(clan.get("color_hex"))
    quest_titles = {
        "CHECKIN_COUNT": "📅 Điểm Danh Đồng Lòng",
        "VOICE_MINUTES": "🎙️ Đàm Đạo Voice Co-op",
        "CHAT_MESSAGES": "💬 Sôi Nổi Kênh Chat"
    }
    quest_descs = {
        "CHECKIN_COUNT": "Tổng số lượt điểm danh hằng ngày của cả băng trong tuần",
        "VOICE_MINUTES": "Số phút cùng ngồi Voice từ 2 thành viên trở lên",
        "CHAT_MESSAGES": "Số tin nhắn giao lưu gắn kết trong kênh chat riêng của băng"
    }

    embed = discord.Embed(
        title=f"📜 BẢNG NHIỆM VỤ TUẦN ĐỒNG ĐỘI: [{clan['tag']}] {clan['name']}",
        description=(
            f"Chu kỳ tuần: **{week_key}** *(Reset 00:00 Thứ Hai hằng tuần)*\n"
            "Cùng anh em hợp sức hoàn thành các nhiệm vụ ngày và tuần để tăng vọt điểm EXP và cống hiến cho clan!"
        ),
        color=embed_color,
        timestamp=datetime.now()
    )

    if attachment_filename:
        embed.set_image(url=f"attachment://{attachment_filename}")

    for q in quests:
        title = quest_titles.get(q["quest_type"], q["quest_type"])
        desc = quest_descs.get(q["quest_type"], "")
        status_badge = "✅ **ĐÃ HOÀN THÀNH (+{} EXP)**".format(q['reward_exp']) if q["completed"] else "⏳ **ĐANG THỰC HIỆN**"
        bar = create_progress_bar(q["current_value"], q["target_value"], size=10)

        card = (
            f"🎯 *{desc}*\n"
            f"📊 Tiến độ: **{q['current_value']} / {q['target_value']}** ━ {status_badge}\n"
            f"{bar}\n"
            f"🎁 Thưởng khi hoàn tất: **+{q['reward_exp']} EXP Băng**"
        )
        embed.add_field(name=f"✨ {title}", value=card, inline=False)

    return embed


def build_logs_embed(clan: Dict[str, Any], logs: List[Dict[str, Any]], page: int = 1, total_pages: int = 1) -> discord.Embed:
    """Tạo Embed hiển thị nhật ký hoạt động gần đây kèm đồ họa"""
    embed_color = parse_hex_color(clan.get("color_hex"))

    if logs:
        lines = []
        for l in logs:
            target_str = f" mục tiêu: <@{l['target_id']}>" if l.get("target_id") else ""
            lines.append(
                f"• <t:{l['created_at']}:R>: **{l['action']}** bởi <@{l['actor_id']}>{target_str}\n"
                f"  ↳ *{l.get('details') or 'Không có chi tiết'}*"
            )
        desc = "\n\n".join(lines)
    else:
        desc = "_Chưa có nhật ký hoạt động nào gần đây._"

    embed = discord.Embed(
        title=f"📜 BẢNG NHẬT KÝ HOẠT ĐỘNG: [{clan['tag']}] {clan['name']}",
        description=desc,
        color=embed_color,
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=BoardAssets.LOGS_THUMBNAIL)
    embed.set_footer(text=f"Trang {page} / {total_pages} • Ghi nhận tự động")
    return embed


def build_party_embed(title: str, creator_id: int, max_slots: int, scheduled_at: Optional[int],
                      main_users: List[int], reserve_users: List[int], status: str = "OPEN") -> discord.Embed:
    """Tạo Embed hiển thị thẻ kèo Party / LFG với đồ họa game và danh sách slot trực quan"""
    is_closed = status == "CLOSED"
    color = discord.Color.greyple() if is_closed else discord.Color.blurple()

    # Nhận diện game từ tiêu đề để gắn Thumbnail phù hợp
    game_thumbnail = BoardAssets.get_game_thumbnail(title)

    time_str = f"<t:{scheduled_at}:F> (<t:{scheduled_at}:R>)" if scheduled_at else "⚡ **Chiến ngay khi đủ team!**"

    embed = discord.Embed(
        title=f"🎮 BẢNG KÈO THI ĐẤU: {title.upper()}",
        description=(
            f"👑 Trưởng kèo: <@{creator_id}>\n"
            f"Trạng thái: **{'🔴 ĐÃ ĐÓNG / CHỐT ĐỘI HÌNH' if is_closed else '🟢 ĐANG MỞ ĐĂNG KÝ (BẤM NÚT ĐỂ VÀO)'}**\n"
            f"⏰ Giờ hẹn: {time_str}"
        ),
        color=color,
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=game_thumbnail)
    embed.set_image(url=BoardAssets.PARTY_BANNER)

    # Hiển thị từng slot chính trực quan
    main_lines = []
    for i in range(max_slots):
        if i < len(main_users):
            role_badge = "👑 Host" if i == 0 and main_users[i] == creator_id else "⚔️ Tuyển Thủ"
            main_lines.append(f"`[ Slot {i + 1:02d} ]` <@{main_users[i]}> **({role_badge})**")
        else:
            main_lines.append(f"`[ Slot {i + 1:02d} ]` _(Slot trống — Bấm Tham Gia)_")

    embed.add_field(
        name=f"🎯 Đội Hình Thi Đấu Chính ({len(main_users)}/{max_slots})",
        value="\n".join(main_lines),
        inline=False
    )

    if reserve_users:
        reserve_lines = [f"`[ Dự Bị {i + 1:02d} ]` <@{uid}>" for i, uid in enumerate(reserve_users)]
        embed.add_field(name=f"🛡️ Hàng Ghế Dự Bị ({len(reserve_users)})", value="\n".join(reserve_lines), inline=False)
    else:
        embed.add_field(name="🛡️ Hàng Ghế Dự Bị", value="_Chưa có thành viên dự bị nào_", inline=False)

    embed.set_footer(text="Bot tự động ping nhắc nhở toàn đội trước giờ hẹn 10 phút!")
    return embed


def build_role_setup_embed(clan: Dict[str, Any], role: Optional[discord.Role], attachment_filename: Optional[str] = None) -> discord.Embed:
    """Tạo Embed giao diện cài đặt & tùy biến Role Băng Đảng cho Chủ Băng kèm đồ họa"""
    if role:
        color_hex = f"#{role.color.value:06X}" if role.color.value else clan.get("color_hex", "#5865F2")
        sec_hex = None
        if hasattr(role, "secondary_color") and role.secondary_color and role.secondary_color.value:
            sec_hex = f"#{role.secondary_color.value:06X}"
        elif clan.get("secondary_color_hex"):
            sec_hex = clan.get("secondary_color_hex")

        if sec_hex:
            color_display = f"`{color_hex}` ➔ `{sec_hex}` (🌈 Gradient Đa Sắc)"
        else:
            color_display = f"`{color_hex}` (Đơn sắc)"

        has_icon = bool(getattr(role, "display_icon", None))
        icon_display = "✅ Đã có Icon" if has_icon else "❌ Chưa có *(Dùng lệnh `/clan upload-image` để cài)*"

        desc = (
            f"Băng đảng: **[{clan['tag']}] {clan['name']}**\n\n"
            f"🛡️ **Vai trò hiện tại:** {role.mention} (ID: `{role.id}`)\n"
            f"✏️ **Tên hiển thị:** `{role.name}`\n"
            f"🎨 **Màu sắc:** {color_display}\n"
            f"⭐ **Icon Vai Trò (Boost Lv.2):** {icon_display}\n"
            f"📌 **Tách nhóm thành viên (Hoist):** {'✅ Đang Bật' if role.hoist else '❌ Đang Tắt'}\n"
            f"🔔 **Cho phép mọi người Tag (@mention):** {'✅ Cho Phép' if role.mentionable else '❌ Không'}\n"
            f"📊 **Vị trí quyền hạn:** Thứ `#{role.position}` trên máy chủ\n\n"
            "👉 *Dùng menu bên dưới để chọn Bảng Màu Đơn Sắc, Bảng Gradient, chọn Role server hoặc bấm các nút bên dưới:*"
        )
        embed_color = role.color if role.color.value else parse_hex_color(clan.get("color_hex"))
    else:
        desc = (
            f"Băng đảng: **[{clan['tag']}] {clan['name']}**\n\n"
            f"⚠️ **Vai trò của băng hiện không tìm thấy trên server!** (Có thể đã bị xóa thủ công).\n"
            "👉 Hãy dùng danh sách bên dưới để chọn một Role có sẵn trên Server hoặc gõ `/clan-admin sync` để bot tạo lại."
        )
        embed_color = discord.Color.red()

    embed = discord.Embed(
        title="🛡️ TRUNG TÂM THIẾT LẬP ROLE BĂNG ĐẢNG",
        description=desc,
        color=embed_color,
        timestamp=datetime.now()
    )
    if clan.get("logo_url"):
        embed.set_thumbnail(url=clan["logo_url"])
    if attachment_filename:
        embed.set_image(url=f"attachment://{attachment_filename}")
    embed.set_footer(text="Hỗ trợ đầy đủ tính năng Server Boost: Gradient 2 màu và Icon Vai Trò")
    return embed
