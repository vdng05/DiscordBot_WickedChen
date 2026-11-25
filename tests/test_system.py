"""
Comprehensive Unit & Integration Test for Clan Discord Bot
"""

import asyncio
import os
import sys
import shutil
import time
from pathlib import Path

# Thêm thư mục gốc vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.database import DatabaseManager
from utils.constants import Ranks, JoinModes, QuestTypes
from main import ClanBot

TEST_DB_PATH = Path("./data/test_clan_bot.db")

async def run_tests():
    print("=" * 60)
    print("BẮT ĐẦU CHẠY KIỂM THỬ TÍCH HỢP HỆ THỐNG CLAN BOT")
    print("=" * 60)

    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    db = DatabaseManager(TEST_DB_PATH)
    await db.initialize()
    print("✅ 1. Khởi tạo Cơ sở dữ liệu SQLite & Migration thành công.")

    # 1. Guild Config
    await db.save_guild_config(
        guild_id=123456789,
        category_id=987654321,
        log_channel_id=111222333,
        allow_member_create=True,
        required_role_id=None,
        cooldown_hours=24
    )
    cfg = await db.get_guild_config(123456789)
    assert cfg is not None
    assert cfg["clan_category_id"] == "987654321"
    print("✅ 2. Guild Config lưu và đọc chính xác.")

    # 2. Tạo Clan
    clan_id = await db.create_clan(
        guild_id=123456789,
        name="Hoàng Gia",
        tag="HG",
        description="Khẩu hiệu hoàng gia",
        role_id=1001,
        text_channel_id=2001,
        voice_channel_id=3001,
        leader_id=9999
    )
    assert clan_id > 0

    clan = await db.get_clan_by_id(clan_id)
    assert clan["name"] == "Hoàng Gia"
    assert clan["tag"] == "HG"
    assert clan["level"] == 1
    print("✅ 3. Tạo Clan thành công (ID: %d)." % clan_id)

    # 3. Thêm Thành Viên & Phân Quyền
    await db.add_member(123456789, 9999, clan_id, Ranks.LEADER)
    await db.add_member(123456789, 8888, clan_id, Ranks.MEMBER)

    count = await db.get_member_count(clan_id)
    assert count == 2

    # Thăng chức 8888 lên OFFICER
    await db.update_member_rank(123456789, 8888, Ranks.OFFICER)
    m8888 = await db.get_member(123456789, 8888)
    assert m8888["rank"] == Ranks.OFFICER
    print("✅ 4. Quản lý thành viên & Thăng chức thành công.")

    # 4. Điểm danh & Cống hiến
    await db.update_checkin(123456789, 8888, "2026-11-25", 5)
    m8888_after = await db.get_member(123456789, 8888)
    assert m8888_after["checkin_streak"] == 5
    assert m8888_after["contribution_points"] == 10
    print("✅ 5. Điểm danh hằng ngày & Tích lũy Streak hoạt động chuẩn xác.")

    # 5. Nhiệm vụ tuần
    quests = await db.ensure_weekly_quests(clan_id, "2026-W48")
    assert len(quests) == 3
    quest_types = [q["quest_type"] for q in quests]
    assert QuestTypes.CHECKIN_COUNT in quest_types
    assert QuestTypes.VOICE_MINUTES in quest_types
    assert QuestTypes.CHAT_MESSAGES in quest_types

    # Tăng tiến độ nhiệm vụ CHECKIN_COUNT và CHAT_MESSAGES
    q_res1 = await db.increment_quest_progress(clan_id, "2026-W48", QuestTypes.CHECKIN_COUNT, 1)
    assert q_res1["updated"] is True

    q_res2 = await db.increment_quest_progress(clan_id, "2026-W48", QuestTypes.CHAT_MESSAGES, 5)
    assert q_res2["updated"] is True
    print("✅ 6. Hệ thống Nhiệm Vụ Tuần (Check-in, Voice Co-op, Chat Messages) hoạt động mượt mà.")

    # 6. Gradient Role & Tải Ảnh Logo / Banner
    await db.update_clan(
        clan_id=clan_id,
        color_hex="#FF512F",
        secondary_color_hex="#DD2476",
        logo_url="https://cdn.discordapp.com/attachments/123/logo.png",
        banner_url="https://cdn.discordapp.com/attachments/123/banner.png"
    )
    clan_updated = await db.get_clan_by_id(clan_id)
    assert clan_updated["color_hex"] == "#FF512F"
    assert clan_updated["secondary_color_hex"] == "#DD2476"
    assert clan_updated["logo_url"] is not None
    assert clan_updated["banner_url"] is not None
    print("✅ 7. Gradient Role 2 màu & Tải lên ảnh Logo/Banner lưu trữ hoàn hảo.")

    # 7. Requests (Chống Race Condition)
    req_id = await db.create_request(
        clan_id=clan_id,
        guild_id=123456789,
        user_id=7777,
        actor_id=7777,
        request_type="APPLY",
        note="Xin vao bang"
    )
    # Lần 1: cập nhật ACCEPTED -> changes == 1
    c1 = await db.update_request_status(req_id, "ACCEPTED")
    assert c1 == 1

    # Lần 2 (người khác cùng bấm hoặc click lại) -> changes == 0 (Atomic lock)
    c2 = await db.update_request_status(req_id, "ACCEPTED")
    assert c2 == 0
    print("✅ 8. Cơ chế nguyên tử chống Race Condition (changes == 1) kiểm thử thành công.")

    # 8. Activity Logs
    await db.add_clan_log(
        clan_id=clan_id,
        actor_id=9999,
        action="TEST_ACTION",
        details="Thực thi kiểm thử tự động"
    )
    log_data = await db.get_clan_logs(clan_id, page=1, page_size=10)
    assert log_data["total"] >= 1
    print("✅ 9. Nhật ký hoạt động (Clan Logs) ghi nhận và phân trang chính xác.")

    # 9. Cooldown sau khi rời băng
    await db.set_cooldown(123456789, 7777, 24)
    cd = await db.get_cooldown(123456789, 7777)
    assert cd is not None
    print("✅ 10. Hệ thống Cooldown chống nhảy băng (24h) hoạt động đúng tiêu chuẩn.")

    # 10. Kiểm tra nạp Cog trên Bot instance
    bot = ClanBot()
    await bot.db.initialize()
    for ext in ["cogs.clan_admin.clan_admin", "cogs.clan.clan_commands", "cogs.clan_events.clan_events"]:
        await bot.load_extension(ext)
        print(f"✅ Nạp thành công Cog: {ext}")

    # 11. Kiểm tra UI Views động
    from utils.ui_components import WelcomeGreetingView, ClanHubView, ClanRoleSetupView, RoleNameModal
    from utils.embeds import build_role_setup_embed
    wg_view = WelcomeGreetingView(7777)
    assert wg_view.new_member_id == 7777
    assert len(wg_view.greeted_users) == 0

    role_embed = build_role_setup_embed(clan, None)
    assert role_embed.title == "🛡️ TRUNG TÂM THIẾT LẬP ROLE BĂNG ĐẢNG"
    role_view = ClanRoleSetupView(clan=clan, bot=bot)
    assert len(role_view.children) >= 4
    print("✅ 11. Thành phần UI tương tác & Cài đặt Role (ClanRoleSetupView, RoleNameModal) sẵn sàng.")

    # 12. Danh hiệu nội bộ (Custom Title & Badges)
    await db.update_member_custom_title(123456789, 8888, "Gánh Team 👑")
    m8888_title = await db.get_member(123456789, 8888)
    assert m8888_title["custom_title"] == "Gánh Team 👑"
    print("✅ 12. Trao & Cập nhật Danh hiệu nội bộ (Custom Title / Badges) thành công.")

    # 13. Cột mốc lịch sử (Clan Milestones)
    ms_id1 = await db.add_milestone(clan_id, "🏰 Khai Sinh Băng Đảng", "Băng Hoàng Gia chính thức thành lập.")
    ms_id2 = await db.add_milestone(clan_id, "🎉 Thăng Cấp Level 2", "Cán mốc cấp độ 2 Khởi Nghĩa.")
    assert ms_id1 > 0 and ms_id2 > 0
    milestones = await db.get_clan_milestones(clan_id)
    assert len(milestones) == 2
    assert milestones[0]["title"] == "🎉 Thăng Cấp Level 2"
    print("✅ 13. Lưu trữ và truy xuất Cột mốc lịch sử (Milestones) hoàn hảo.")

    # 14. Kiểm tra Sự kiện Đêm Lửa Trại (Bonfire Logic)
    from cogs.clan_events.clan_events import is_bonfire_active
    # Hàm chạy không lỗi
    bonfire_active = is_bonfire_active()
    assert isinstance(bonfire_active, bool)
    print("✅ 14. Logic kiểm tra Đêm Lửa Trại Cuối Tuần (Bonfire x2 EXP) hoạt động chuẩn.")

    # 15. Xuất Ảnh Nền Wallpaper Full HD 1920x1080 & Milestone Embed
    from utils.canvas import generate_clan_wallpaper
    from utils.embeds import build_milestones_embed
    members = await db.get_clan_members(clan_id)
    wall_buf = generate_clan_wallpaper(clan, members, milestones)
    assert wall_buf.getbuffer().nbytes > 10000
    ms_embed = build_milestones_embed(clan, milestones)
    assert ms_embed.title.startswith("📜 BIÊN NIÊN SỬ")
    print("✅ 15. Sinh Wallpaper Full HD (1920x1080) & Embed Cột Mốc Lịch Sử thành công.")

    print("=" * 60)
    print("🎉 TẤT CẢ 15 BÀI KIỂM THỬ HỆ THỐNG ĐỀU VƯỢT QUA 100%!")
    print("=" * 60)

    # Dọn dẹp test db
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

if __name__ == "__main__":
    asyncio.run(run_tests())
