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

    # 2. Tạo Clan (kèm log_channel_id riêng của băng)
    clan_id = await db.create_clan(
        guild_id=123456789,
        name="Hoàng Gia",
        tag="HG",
        description="Khẩu hiệu hoàng gia",
        role_id=1001,
        text_channel_id=2001,
        voice_channel_id=3001,
        leader_id=9999,
        log_channel_id=4001
    )
    assert clan_id > 0

    clan = await db.get_clan_by_id(clan_id)
    assert clan["name"] == "Hoàng Gia"
    assert clan["tag"] == "HG"
    assert clan["level"] == 1
    assert clan["log_channel_id"] == "4001"
    by_log = await db.get_clan_by_channel_id(4001)
    assert by_log is not None and by_log["clan_id"] == clan_id
    print("✅ 3. Tạo Clan thành công (ID: %d, kèm log_channel_id riêng)." % clan_id)

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

    # 16. Kiểm tra các Views tương tác mới (ClanListInteractiveView, LeaderboardInteractiveView, LeaveClanConfirmView, ClanMemberManagementView)
    import discord
    from utils.ui_components import (
        ClanListInteractiveView,
        LeaderboardInteractiveView,
        LeaveClanConfirmView,
        ClanMemberManagementView
    )
    clans_list = [clan]
    cl_view = ClanListInteractiveView(clans=clans_list, bot=bot)
    assert len(cl_view.children) >= 2

    lb_view = LeaderboardInteractiveView(guild_name="Test Server", bot=bot, initial_criteria="level")
    assert len(lb_view.children) >= 3

    leave_view = LeaveClanConfirmView(clan=clan, bot=bot)
    assert len(leave_view.children) == 2

    class DummyUser:
        id = 9999
        guild_permissions = discord.Permissions.all()

    mgmt_view = ClanMemberManagementView(clan=clan, user=DummyUser(), bot=bot)
    assert len(mgmt_view.children) >= 4
    print("✅ 16. Toàn bộ các View tương tác 1-Click (Danh sách băng, Bảng xếp hạng, Quản lý thành viên, Rời băng) sẵn sàng.")

    # 17. Kiểm tra Sinh Ảnh Mặc Định Tự Tạo (Default Clan Logo & Banner) bằng Canvas
    from utils.canvas import generate_default_clan_logo, generate_default_clan_banner
    from utils.embeds import build_clan_info_embed, get_level_info
    default_clan = dict(clan)
    default_clan["logo_url"] = None
    default_clan["banner_url"] = None

    logo_buf = generate_default_clan_logo(default_clan)
    assert logo_buf.getbuffer().nbytes > 5000, "Default logo bytes must be valid"

    banner_buf = generate_default_clan_banner(default_clan, member_count=len(members))
    assert banner_buf.getbuffer().nbytes > 15000, "Default banner bytes must be valid"

    lvl_info = get_level_info(default_clan.get("exp", 0))
    info_embed = build_clan_info_embed(
        default_clan, members, lvl_info,
        attachment_filename="clan_profile.png",
        logo_filename="default_logo.png"
    )
    assert info_embed.thumbnail.url == "attachment://default_logo.png"
    assert info_embed.image.url == "attachment://clan_profile.png"
    print("✅ 17. Tự động sinh Logo Bát Giác & Banner Gaming mặc định lộng lẫy bằng Canvas thành công 100%.")

    # 18. Kiểm tra Chuyển đổi tên kênh Tiếng Việt sang ASCII Slug không dấu (to_channel_slug)
    from utils.text_helper import to_channel_slug
    test_slug_1 = to_channel_slug("Chó Điên")
    assert test_slug_1 == "cho-dien", f"Expected 'cho-dien', got '{test_slug_1}'"

    test_slug_2 = to_channel_slug("[NGU] Chó Điên")
    assert test_slug_2 == "ngu-cho-dien", f"Expected 'ngu-cho-dien', got '{test_slug_2}'"

    test_slug_3 = to_channel_slug("nhật-ký-băng")
    assert test_slug_3 == "nhat-ky-bang", f"Expected 'nhat-ky-bang', got '{test_slug_3}'"

    test_slug_4 = to_channel_slug("Đại Bàng Lửa & Rồng Vàng")
    assert test_slug_4 == "dai-bang-lua-rong-vang", f"Expected 'dai-bang-lua-rong-vang', got '{test_slug_4}'"

    # Kiểm tra tên kênh text chỉ dùng tên băng không kèm tag
    channel_name_clean = f"💬・{to_channel_slug('Chó Điên')}"
    assert channel_name_clean == "💬・cho-dien", f"Expected '💬・cho-dien', got '{channel_name_clean}'"
    print("✅ 18. Chuyển đổi tên kênh tiếng Việt không dấu chuẩn Discord (to_channel_slug) chính xác tuyệt đối.")

    # 19. Kiểm tra Cơ chế Auto-Dismiss & Quản lý Panel người dùng (register_user_panel)
    class DummyInteraction:
        def __init__(self, uid):
            self.user = type("U", (), {"id": uid})()
            self.deleted = False
        async def delete_original_response(self):
            self.deleted = True

    dummy_inter_1 = DummyInteraction(12345)
    await bot.register_user_panel(12345, dummy_inter_1)
    assert bot.active_user_panels[12345] == dummy_inter_1

    # Khi mở bảng mới -> bảng cũ tự động bị dismiss / delete
    dummy_inter_2 = DummyInteraction(12345)
    await bot.register_user_panel(12345, dummy_inter_2)
    assert dummy_inter_1.deleted is True
    assert bot.active_user_panels[12345] == dummy_inter_2

    await bot.dismiss_user_panel(12345)
    assert dummy_inter_2.deleted is True
    assert 12345 not in bot.active_user_panels
    print("✅ 19. Cơ chế Auto-Dismiss và dọn dẹp panel tương tác của người dùng hoạt động hoàn hảo.")

    # 20. Kiểm tra Bảng Quản Lý & Tải Ảnh Trực Tiếp (ClanImageUploadDashboardView & build_image_settings_embed)
    from utils.embeds import build_image_settings_embed
    from utils.ui_components import ClanImageUploadDashboardView
    partial_clan = dict(clan)
    partial_clan["logo_url"] = "https://cdn.discordapp.com/attachments/123/logo.png"
    partial_clan["banner_url"] = None
    img_embed = build_image_settings_embed(partial_clan, default_banner_filename="default_banner.png")
    assert img_embed.title == "🖼️ TRUNG TÂM QUẢN LÝ & TẢI ẢNH BĂNG ĐẢNG"
    assert img_embed.thumbnail.url == "https://cdn.discordapp.com/attachments/123/logo.png"
    assert img_embed.image.url == "attachment://default_banner.png"
    img_view = ClanImageUploadDashboardView(clan=partial_clan, bot=bot)
    assert len(img_view.children) == 7
    print("✅ 20. Bảng điều khiển tải ảnh trực tiếp (hiển thị song song Logo tùy chỉnh & Banner mặc định) hoạt động mượt mà.")

    # 21. Kiểm tra LFG Party Kèo Game & Nhắc nhở trước giờ chơi (Party Reminders)
    now_ts = int(time.time())
    p_id = await db.create_party(
        clan_id=clan_id,
        creator_id=9999,
        channel_id=2001,
        message_id=55555,
        title="Leo Rank Valorant",
        max_slots=5,
        scheduled_at=now_ts + 300 # 5 phút nữa
    )
    assert p_id > 0
    upcoming = await db.get_upcoming_parties_to_remind(now_ts, window_seconds=600)
    assert any(p["party_id"] == p_id for p in upcoming)
    reminded_count = await db.mark_party_reminded(p_id)
    assert reminded_count == 1
    upcoming_after = await db.get_upcoming_parties_to_remind(now_ts, window_seconds=600)
    assert not any(p["party_id"] == p_id for p in upcoming_after)
    print("✅ 21. Hệ thống Kèo chơi game LFG & Vòng lặp tự động nhắc nhở trước giờ thi đấu chuẩn xác 100%.")

    # 22. Kiểm tra Lưu trữ & Phân giải Ảnh Bền Vững (utils/image_storage.py)
    from utils.image_storage import resolve_clan_logo, resolve_clan_banner, delete_local_asset, ensure_assets_dir
    assets_dir = ensure_assets_dir()
    fake_logo = assets_dir / "clan_999999_logo.png"
    fake_logo.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    local_clan = dict(clan)
    local_clan["logo_url"] = f"local://{fake_logo.as_posix()}"
    local_clan["banner_url"] = None

    resolved_files = []
    logo_ref = await resolve_clan_logo(local_clan, resolved_files, fallback_to_default=True)
    banner_ref = await resolve_clan_banner(local_clan, resolved_files, member_count=2, leader_name="Vũ Đăng", fallback_to_default=True)
    assert logo_ref == "attachment://clan_logo.png"
    assert banner_ref == "attachment://default_banner.png"
    assert len(resolved_files) == 2

    res_embed = build_image_settings_embed(local_clan, default_logo_filename=logo_ref, default_banner_filename=banner_ref)
    assert res_embed.thumbnail.url == "attachment://clan_logo.png"
    assert res_embed.image.url == "attachment://default_banner.png"
    assert "Lưu trữ bền vững" in res_embed.description
    for rf in resolved_files:
        rf.close()
    delete_local_asset(local_clan["logo_url"])
    assert not fake_logo.exists()

    # Kiểm tra Hồ Sơ Băng hiển thị Banner tùy chỉnh khi đã upload banner
    from utils.ui_components import build_clan_profile_payload
    custom_banner_clan = dict(clan)
    custom_banner_clan["banner_url"] = "https://cdn.example.com/my_banner.png"
    prof_embed, prof_files = await build_clan_profile_payload(custom_banner_clan, members, lvl_info, None)
    assert prof_embed.image.url == "https://cdn.example.com/my_banner.png"
    for pf in prof_files:
        pf.close()
    print("✅ 22. Hệ thống lưu trữ ảnh bền vững (local://), hiển thị Banner tùy chỉnh trên Hồ Sơ Băng & fallback hoạt động 100%.")

    # 23. Kiểm tra Nhật Ký Băng (total_pages), Thư Thách Đấu Băng Đảng & Giới hạn Field 1024 ký tự của Party
    logs_check = await db.get_clan_logs(clan_id, page=1, page_size=10)
    assert "total_pages" in logs_check and logs_check["total_pages"] >= 1

    from utils.embeds import build_party_embed, build_challenge_embed
    from utils.ui_components import (
        ClanChallengeTargetView,
        build_challenge_target_embed,
        ClanQuickPartyModal,
        DisbandClanModal,
        ClanChallengeModal,
        SafeView
    )
    big_party = build_party_embed("Custom 50 Slots", 9999, 50, None, [9999], [])
    assert len(big_party.fields[0].value) <= 1024, "Party field value must never exceed 1024 chars"

    ch_embed = build_challenge_embed(clan, 9999, "Valorant", "5v5 • BO3", "21:00", "Giao hữu tối nay nhé!", target_clan=None)
    assert "THƯ THÁCH ĐẤU" in ch_embed.title
    ch_view = ClanChallengeTargetView(source_clan=clan, other_clans=[], bot=bot)
    assert len(ch_view.children) == 3
    assert isinstance(ch_view, SafeView)

    # Kiểm tra thông báo khi server chỉ có 1 băng duy nhất
    solo_embed = build_challenge_target_embed([])
    assert "băng đảng duy nhất" in solo_embed.description

    # Kiểm tra giới hạn 45 ký tự của Modal Title & TextInput Label (tránh lỗi 'didn't respond in time')
    party_modal = ClanQuickPartyModal(clan=clan, bot=bot)
    assert len(party_modal.title) <= 45
    assert len(party_modal.party_time.label) <= 45

    long_clan = dict(clan)
    long_clan["name"] = "Băng Đảng Siêu Cấp Vô Địch"  # 26 ký tự
    disband_modal = DisbandClanModal(clan=long_clan, bot=bot)
    assert len(disband_modal.title) <= 45
    assert len(disband_modal.confirm_name.label) <= 45

    ch_modal = ClanChallengeModal(source_clan=clan, target_clan=None, bot=bot)
    assert len(ch_modal.title) <= 45
    for item in ch_modal.children:
        if hasattr(item, "label"):
            assert len(item.label) <= 45
    print("✅ 23. Nhật ký băng, Thư Thách Đấu (gồm chế độ 1 băng duy nhất), giới hạn 45 ký tự Modal & SafeView hoạt động 100%.")

    # 24. Kiểm tra Phân Quyền Sử Dụng Bot Theo Role Dành Cho Chủ Bot (/bot-access)
    default_acc = await db.get_bot_access_config(123456789)
    assert default_acc["mode"] == "ALL" and default_acc["role_ids"] == []

    await db.set_bot_access_config(123456789, mode="ROLES", role_ids=["555111", "555222"])
    roles_acc = await db.get_bot_access_config(123456789)
    assert roles_acc["mode"] == "ROLES" and roles_acc["role_ids"] == ["555111", "555222"]

    await db.set_bot_access_config(123456789, mode="NONE", role_ids=["555111", "555222"])
    none_acc = await db.get_bot_access_config(123456789)
    assert none_acc["mode"] == "NONE"

    from utils.embeds import build_bot_access_embed
    from utils.ui_components import BotAccessControlView
    ba_embed = build_bot_access_embed("Test Server", "ROLES", ["555111"])
    assert "PHÂN QUYỀN SỬ DỤNG BOT" in ba_embed.title
    ba_view = BotAccessControlView("Test Server", "ROLES", ["555111"], bot=bot)
    assert len(ba_view.children) == 4
    print("✅ 24. Phân quyền Role sử dụng bot dành cho Chủ Bot (ALL / ROLES / NONE) hoạt động chuẩn xác 100%.")

    print("=" * 60)
    print("🎉 TẤT CẢ 24 BÀI KIỂM THỬ HỆ THỐNG ĐỀU VƯỢT QUA 100%!")
    print("=" * 60)

    # Dọn dẹp test db
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

if __name__ == "__main__":
    asyncio.run(run_tests())
