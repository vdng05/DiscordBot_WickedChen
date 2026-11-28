"""
Hệ thống hằng số, bảng mốc cấp độ, phần thưởng EXP và phân quyền RBAC
"""

class Ranks:
    LEADER = "LEADER"
    CO_LEADER = "CO_LEADER"
    OFFICER = "OFFICER"
    MEMBER = "MEMBER"

    WEIGHTS = {
        LEADER: 4,
        CO_LEADER: 3,
        OFFICER: 2,
        MEMBER: 1
    }

    NAMES = {
        LEADER: "Chủ Băng",
        CO_LEADER: "Phó Băng",
        OFFICER: "Cán Bộ",
        MEMBER: "Thành Viên"
    }

    LIMITS = {
        CO_LEADER: 2,
        OFFICER: 4
    }

RANK_WEIGHTS = Ranks.WEIGHTS
RANK_NAMES = Ranks.NAMES
RANK_LIMITS = Ranks.LIMITS

class JoinModes:
    OPEN = "OPEN"
    APPROVAL = "APPROVAL"
    INVITE_ONLY = "INVITE_ONLY"

    NAMES = {
        OPEN: "🟢 Mở Tự Do (Vào ngay)",
        APPROVAL: "🟡 Cần Duyệt (Mặc định)",
        INVITE_ONLY: "🔒 Chỉ Nhận Lời Mời"
    }

# Bảng mốc Cấp độ & Quyền lợi mở khóa
LEVELS = [
    {
        "level": 1,
        "req_exp": 0,
        "max_members": 15,
        "title": "Cơ Bản",
        "perks": "1 kênh Text + 1 kênh Voice riêng, đổi màu Role cơ bản"
    },
    {
        "level": 2,
        "req_exp": 1000,
        "max_members": 25,
        "title": "Khởi Sắc",
        "perks": "Tăng sĩ số tối đa lên 25 người, tùy chỉnh khẩu hiệu nâng cao"
    },
    {
        "level": 3,
        "req_exp": 3500,
        "max_members": 40,
        "title": "Vững Mạnh",
        "perks": "Mở khóa kênh Voice thứ 2 (tách 2 nhóm chơi game khác nhau)"
    },
    {
        "level": 4,
        "req_exp": 8000,
        "max_members": 60,
        "title": "Hùng Mạnh",
        "perks": "Mở khóa gắn Icon Role (nếu server đạt Boost cấp 2), huy hiệu VIP"
    },
    {
        "level": 5,
        "req_exp": 15000,
        "max_members": 100,
        "title": "Huyền Thoại",
        "perks": "Không giới hạn tạo kèo Party song song, mở khóa đổi định dạng tên kênh"
    }
]

# Cơ chế cộng EXP
class ExpRewards:
    # Nhắn tin tương tác
    CHAT_EXP = 5
    CHAT_CONTRIBUTION = 1
    CHAT_MIN_LENGTH = 5
    CHAT_COOLDOWN_SECONDS = 60

    # Ngồi Voice chung (Co-op Voice)
    VOICE_EXP = 15
    VOICE_CONTRIBUTION = 3
    VOICE_MIN_MEMBERS = 2
    VOICE_INTERVAL_MINUTES = 5

    # Điểm danh hằng ngày
    CHECKIN_EXP = 30
    CHECKIN_CONTRIBUTION = 10
    CHECKIN_STREAK_7_BONUS_EXP = 50

EXP_REWARDS = ExpRewards

class QuestTypes:
    CHECKIN_COUNT = "CHECKIN_COUNT"
    VOICE_MINUTES = "VOICE_MINUTES"
    CHAT_MESSAGES = "CHAT_MESSAGES"

QUEST_TYPES = QuestTypes

DEFAULT_WEEKLY_QUESTS = [
    {
        "quest_type": QuestTypes.CHECKIN_COUNT,
        "title": "📅 Điểm Danh Đồng Lòng",
        "description": "Đạt tổng cộng 30 lượt điểm danh từ các thành viên trong tuần",
        "target_value": 30,
        "reward_exp": 300
    },
    {
        "quest_type": QuestTypes.VOICE_MINUTES,
        "title": "🎙️ Tám Chuyện Cùng Nhau",
        "description": "Tích lũy tổng cộng 2 giờ (120 phút) ngồi Voice co-op chung",
        "target_value": 120,
        "reward_exp": 400
    },
    {
        "quest_type": QuestTypes.CHAT_MESSAGES,
        "title": "💬 Sôi Nổi Kênh Chat",
        "description": "Cùng nhau gửi 100 tin nhắn giao lưu gắn kết trong kênh chat riêng của băng",
        "target_value": 100,
        "reward_exp": 300
    }
]

class Cooldowns:
    RENAME_COOLDOWN_DAYS = 7
    INVITE_EXPIRE_MINUTES = 15
    PARTY_REMINDER_MINUTES = 10


# =============================================================================
# NHIỆM VỤ NGÀY (DAILY QUESTS) — RESET 00:00 GIỜ VIỆT NAM
# =============================================================================

class DailyQuestTypes:
    DAILY_CHECKIN = "DAILY_CHECKIN"
    DAILY_CHAT = "DAILY_CHAT"
    DAILY_VOICE = "DAILY_VOICE"


DEFAULT_DAILY_QUESTS = [
    {
        "quest_type": DailyQuestTypes.DAILY_CHECKIN,
        "title": "📅 Điểm Danh Hôm Nay",
        "description": "Đạt 5 lượt điểm danh của thành viên trong ngày hôm nay",
        "target_value": 5,
        "reward_exp": 50,
        "reward_coins": 30,
    },
    {
        "quest_type": DailyQuestTypes.DAILY_CHAT,
        "title": "💬 Chào Buổi Mới Kênh Chat",
        "description": "Gửi 20 tin nhắn trò chuyện trong kênh chat riêng của băng hôm nay",
        "target_value": 20,
        "reward_exp": 50,
        "reward_coins": 30,
    },
    {
        "quest_type": DailyQuestTypes.DAILY_VOICE,
        "title": "🎙️ Voice Co-op Hôm Nay",
        "description": "Tích lũy 30 phút ngồi Voice chung từ 2 người trở lên hôm nay",
        "target_value": 30,
        "reward_exp": 80,
        "reward_coins": 40,
    },
]


# =============================================================================
# HỆ THỐNG LINH THÚ BĂNG ĐẢNG (CLAN PET)
# =============================================================================

PET_SPECIES = {
    "cyber_cat": {
        "name": "Mèo Cyber",
        "emoji": "🐱",
        "desc": "Dáng gọn lẹ, tai nhọn phát sáng và đuôi năng lượng neon sắc sảo.",
    },
    "mini_dragon": {
        "name": "Tiểu Long",
        "emoji": "🐉",
        "desc": "Có sừng oai phong và đôi cánh rồng lớn dần qua từng giai đoạn.",
    },
    "spirit_fox": {
        "name": "Cáo Tinh",
        "emoji": "🦊",
        "desc": "Bộ lông xù mềm mại, số lượng đuôi tăng dần (1 → 3 → 5 đuôi).",
    },
    "royal_slime": {
        "name": "Slime Hoàng Gia",
        "emoji": "👑",
        "desc": "Thân tròn mềm mại bán trong suốt, đổi sắc theo màu Gradient của băng.",
    },
}

PET_STAGES = [
    {
        "stage": 1,
        "name": "Trứng Linh Thú",
        "min_level": 1,
        "max_level": 4,
        "checkin_bonus_pct": 0,
        "unlocked_slots": ["background"],
        "perk": "Chờ đủ 200 Pet EXP (Lv.5) để nở",
    },
    {
        "stage": 2,
        "name": "Sơ Sinh (Baby)",
        "min_level": 5,
        "max_level": 14,
        "checkin_bonus_pct": 5,
        "unlocked_slots": ["background", "headwear"],
        "perk": "+5% EXP Điểm danh & mở khóa Mũ / Đội đầu",
    },
    {
        "stage": 3,
        "name": "Thiếu Niên (Teen)",
        "min_level": 15,
        "max_level": 29,
        "checkin_bonus_pct": 8,
        "unlocked_slots": ["background", "headwear", "outfit", "face"],
        "perk": "+8% EXP Điểm danh & mở khóa Quần áo + Kính/Phụ kiện mặt",
    },
    {
        "stage": 4,
        "name": "Trưởng Thành (Adult)",
        "min_level": 30,
        "max_level": 49,
        "checkin_bonus_pct": 12,
        "unlocked_slots": ["background", "headwear", "outfit", "face", "back", "held"],
        "perk": "+12% EXP Điểm danh & mở khóa Cánh/Áo choàng + Đồ cầm tay",
    },
    {
        "stage": 5,
        "name": "Tối Thượng (Apex)",
        "min_level": 50,
        "max_level": 999,
        "checkin_bonus_pct": 15,
        "unlocked_slots": ["background", "headwear", "outfit", "face", "back", "held", "aura"],
        "perk": "+15% EXP Điểm danh, mở khóa Hào quang & hiện trên Wallpaper Full HD",
    },
]


def get_pet_level_info(pet_exp: int) -> dict:
    """Tính toán Level (1..99), Stage (1..5) và tiến độ EXP tiếp theo của Clan Pet."""
    exp = max(0, int(pet_exp or 0))
    # Công thức mượt: Lv.1=0, Lv.5=200, Lv.15=1200, Lv.30=4000, Lv.50=10000
    level = 1
    while level < 99:
        next_lv = level + 1
        req = int(4 * (next_lv - 1) ** 2 + 16 * (next_lv - 1))
        if exp < req:
            break
        level = next_lv

    cur_req = int(4 * (level - 1) ** 2 + 16 * (level - 1))
    next_req = int(4 * level ** 2 + 16 * level)
    stage_info = PET_STAGES[0]
    for st in PET_STAGES:
        if level >= st["min_level"]:
            stage_info = st

    return {
        "level": level,
        "stage": stage_info["stage"],
        "stage_name": stage_info["name"],
        "checkin_bonus_pct": stage_info["checkin_bonus_pct"],
        "unlocked_slots": stage_info["unlocked_slots"],
        "perk": stage_info["perk"],
        "cur_exp": exp,
        "cur_level_exp": cur_req,
        "next_level_exp": next_req,
    }


PET_SLOT_NAMES = {
    "background": "🖼️ Phông Nền",
    "headwear": "👒 Mũ / Đội Đầu",
    "face": "🕶️ Kính / Phụ Kiện Mặt",
    "outfit": "👕 Trang Phục",
    "back": "🪽 Cánh / Áo Choàng",
    "held": "🎮 Vật Cầm Tay",
    "aura": "✨ Hào Quang Tối Thượng",
}

PET_STYLE_NAMES = {
    "streetwear": "🧢 Streetwear / Hiphop",
    "cyber": "🎧 Cyber Gaming",
    "royal": "👑 Hoàng Gia / Fantasy",
    "ninja": "🥷 Cổ Trang / Ninja",
    "casual": "🧋 Đời Thường / Giải Trí",
}

# Bộ sưu tập đồ & phụ kiện vẽ bằng Pillow Vector + Anchor System (45 món, 7 danh mục, 5 phong cách)
PET_CATALOG = [
    # 1. Phông Nền (Stage 1+)
    {"item_id": "bg_cyber_grid", "name": "Lưới Cyber Neon", "style": "cyber", "slot": "background", "min_stage": 1, "price": 50},
    {"item_id": "bg_royal_hall", "name": "Sảnh Hoàng Gia", "style": "royal", "slot": "background", "min_stage": 1, "price": 60},
    {"item_id": "bg_sakura_night", "name": "Đêm Hoa Anh Đào", "style": "ninja", "slot": "background", "min_stage": 1, "price": 60},
    {"item_id": "bg_sunny_beach", "name": "Bãi Biển Nắng Vàng", "style": "casual", "slot": "background", "min_stage": 1, "price": 50},
    {"item_id": "bg_galaxy_nebula", "name": "Tinh Vân Vũ Trụ", "style": "royal", "slot": "background", "min_stage": 1, "price": 75},
    {"item_id": "bg_neon_dojo", "name": "Phố Đêm Streetwear", "style": "streetwear", "slot": "background", "min_stage": 1, "price": 70},
    # 2. Mũ / Đội Đầu (Stage 2+)
    {"item_id": "hat_cap_back", "name": "Mũ Lưỡi Trai Ngược", "style": "streetwear", "slot": "headwear", "min_stage": 2, "price": 80},
    {"item_id": "hat_gaming_headset", "name": "Tai Nghe Gaming LED", "style": "cyber", "slot": "headwear", "min_stage": 2, "price": 100},
    {"item_id": "hat_gold_crown", "name": "Vương Miện Mạ Vàng", "style": "royal", "slot": "headwear", "min_stage": 2, "price": 120},
    {"item_id": "hat_ninja_band", "name": "Băng Trán Kim Loại", "style": "ninja", "slot": "headwear", "min_stage": 2, "price": 90},
    {"item_id": "hat_duck", "name": "Mũ Vịt Vàng Đáng Yêu", "style": "casual", "slot": "headwear", "min_stage": 2, "price": 80},
    {"item_id": "hat_wizard", "name": "Mũ Pháp Sư Huyền Bí", "style": "royal", "slot": "headwear", "min_stage": 2, "price": 110},
    {"item_id": "hat_oni_horns", "name": "Mặt Nạ Sừng Oni", "style": "ninja", "slot": "headwear", "min_stage": 3, "price": 130},
    {"item_id": "hat_cat_ears_rgb", "name": "Băng Đô Tai Mèo RGB", "style": "cyber", "slot": "headwear", "min_stage": 2, "price": 115},
    {"item_id": "hat_halo_angel", "name": "Vòng Hào Quang Thiên Thần", "style": "royal", "slot": "headwear", "min_stage": 2, "price": 125},
    # 3. Kính / Phụ Kiện Mặt (Stage 3+)
    {"item_id": "face_sunglasses", "name": "Kính Mát Hiphop", "style": "streetwear", "slot": "face", "min_stage": 3, "price": 90},
    {"item_id": "face_vr_visor", "name": "Kính VR Neon", "style": "cyber", "slot": "face", "min_stage": 3, "price": 130},
    {"item_id": "face_ninja_mask", "name": "Khăn Bịt Mặt Ninja", "style": "ninja", "slot": "face", "min_stage": 3, "price": 100},
    {"item_id": "face_thug_life", "name": "Kính Pixel Thug Life", "style": "casual", "slot": "face", "min_stage": 3, "price": 110},
    {"item_id": "face_monocle", "name": "Kính Một Mắt Quý Tộc", "style": "royal", "slot": "face", "min_stage": 3, "price": 115},
    {"item_id": "face_star_blush", "name": "Sticker Ngôi Sao Đáng Yêu", "style": "casual", "slot": "face", "min_stage": 3, "price": 85},
    # 4. Trang Phục (Stage 3+)
    {"item_id": "outfit_hoodie", "name": "Áo Hoodie Streetwear", "style": "streetwear", "slot": "outfit", "min_stage": 3, "price": 120},
    {"item_id": "outfit_bomber", "name": "Áo Khoác Bomber Băng", "style": "streetwear", "slot": "outfit", "min_stage": 3, "price": 135},
    {"item_id": "outfit_cyber_armor", "name": "Áo Giáp Công Nghệ", "style": "cyber", "slot": "outfit", "min_stage": 3, "price": 150},
    {"item_id": "outfit_royal_vest", "name": "Vest Hoàng Gia Quý Tộc", "style": "royal", "slot": "outfit", "min_stage": 3, "price": 150},
    {"item_id": "outfit_tuxedo", "name": "Comple Điệp Viên Đen", "style": "streetwear", "slot": "outfit", "min_stage": 3, "price": 160},
    {"item_id": "outfit_mage_robe", "name": "Áo Choàng Pháp Sư", "style": "royal", "slot": "outfit", "min_stage": 3, "price": 155},
    {"item_id": "outfit_cloud_robe", "name": "Kimono Họa Tiết Mây", "style": "ninja", "slot": "outfit", "min_stage": 3, "price": 140},
    {"item_id": "outfit_samurai", "name": "Giáp Chiến Binh Samurai", "style": "ninja", "slot": "outfit", "min_stage": 4, "price": 190},
    {"item_id": "outfit_tanktop", "name": "Áo Ba Lỗ Mùa Hè", "style": "casual", "slot": "outfit", "min_stage": 3, "price": 90},
    # 5. Cánh / Áo Choàng / Lưng (Stage 4+)
    {"item_id": "back_angel_wings", "name": "Cánh Thiên Thần", "style": "royal", "slot": "back", "min_stage": 4, "price": 220},
    {"item_id": "back_demon_wings", "name": "Cánh Ác Quỷ Bóng Đêm", "style": "ninja", "slot": "back", "min_stage": 4, "price": 230},
    {"item_id": "back_royal_cape", "name": "Áo Choàng Đỏ Đế Vương", "style": "royal", "slot": "back", "min_stage": 4, "price": 210},
    {"item_id": "back_cyber_wings", "name": "Cánh Phản Lực Neon", "style": "cyber", "slot": "back", "min_stage": 4, "price": 240},
    {"item_id": "back_katana", "name": "Song Kiếm Katana Đeo Lưng", "style": "ninja", "slot": "back", "min_stage": 4, "price": 200},
    # 6. Vật Cầm Tay (Stage 4+)
    {"item_id": "held_gamepad", "name": "Tay Cầm Console", "style": "cyber", "slot": "held", "min_stage": 4, "price": 160},
    {"item_id": "held_boba", "name": "Cốc Trà Sữa Trân Châu", "style": "casual", "slot": "held", "min_stage": 4, "price": 140},
    {"item_id": "held_scepter", "name": "Quyền Trượng Ánh Sáng", "style": "royal", "slot": "held", "min_stage": 4, "price": 210},
    {"item_id": "held_sword", "name": "Thanh Kiếm Năng Lượng", "style": "cyber", "slot": "held", "min_stage": 4, "price": 220},
    {"item_id": "held_mic", "name": "Micro Idol Phát Sáng", "style": "streetwear", "slot": "held", "min_stage": 4, "price": 170},
    {"item_id": "held_lantern", "name": "Đèn Lồng Hoa Đăng", "style": "ninja", "slot": "held", "min_stage": 4, "price": 165},
    # 7. Hào Quang Tối Thượng (Stage 5)
    {"item_id": "aura_gradient_halo", "name": "Hào Quang Năng Lượng Băng", "style": "cyber", "slot": "aura", "min_stage": 5, "price": 320},
    {"item_id": "aura_dragon_flame", "name": "Hào Quang Hỏa Long Tối Thượng", "style": "royal", "slot": "aura", "min_stage": 5, "price": 350},
    {"item_id": "aura_sakura_storm", "name": "Vòng Xoáy Hoa Anh Đào", "style": "ninja", "slot": "aura", "min_stage": 5, "price": 330},
    {"item_id": "aura_void_lightning", "name": "Lôi Điện Hắc Ám", "style": "streetwear", "slot": "aura", "min_stage": 5, "price": 340},
]

PET_CATALOG_MAP = {item["item_id"]: item for item in PET_CATALOG}

# Hệ tọa độ neo (Anchor Points): (center_x, center_y, scale) trên khung chuẩn 600x600 RGBA
# Căn chuẩn theo hệ hình khối hữu cơ 5 giai đoạn của Pet Canvas v6
_HUMANOID_ANCHORS = {
    1: {"headwear": (300, 175, 0.72), "face": (300, 275, 0.72), "outfit": (300, 355, 0.75), "back": (300, 315, 0.75), "held": (405, 360, 0.75), "aura": (300, 305, 0.88)},
    2: {"headwear": (300, 198, 0.84), "face": (300, 276, 0.82), "outfit": (300, 380, 0.85), "back": (300, 336, 0.84), "held": (405, 376, 0.78), "aura": (300, 315, 0.92)},
    3: {"headwear": (300, 166, 0.82), "face": (300, 238, 0.80), "outfit": (300, 356, 0.92), "back": (300, 330, 0.95), "held": (412, 356, 0.86), "aura": (300, 305, 0.98)},
    4: {"headwear": (300, 144, 0.82), "face": (300, 214, 0.80), "outfit": (300, 344, 1.00), "back": (300, 322, 1.06), "held": (426, 346, 0.94), "aura": (300, 296, 1.08)},
    5: {"headwear": (300, 134, 0.84), "face": (300, 206, 0.82), "outfit": (300, 340, 1.05), "back": (300, 318, 1.14), "held": (436, 342, 0.98), "aura": (300, 292, 1.16)},
}
_SLIME_ANCHORS = {
    1: _HUMANOID_ANCHORS[1],
    2: {"headwear": (300, 232, 0.80), "face": (300, 326, 0.80), "outfit": (300, 365, 0.85), "back": (300, 330, 0.84), "held": (435, 356, 0.78), "aura": (300, 325, 0.92)},
    3: {"headwear": (300, 208, 0.86), "face": (300, 326, 0.84), "outfit": (300, 365, 0.95), "back": (300, 328, 0.94), "held": (455, 354, 0.86), "aura": (300, 322, 1.00)},
    4: {"headwear": (300, 178, 0.90), "face": (300, 326, 0.86), "outfit": (300, 368, 1.02), "back": (300, 324, 1.04), "held": (472, 350, 0.92), "aura": (300, 318, 1.10)},
    5: {"headwear": (300, 166, 0.94), "face": (300, 326, 0.88), "outfit": (300, 368, 1.08), "back": (300, 320, 1.12), "held": (484, 348, 0.96), "aura": (300, 315, 1.18)},
}
PET_ANCHORS = {
    "cyber_cat": _HUMANOID_ANCHORS,
    "mini_dragon": _HUMANOID_ANCHORS,
    "spirit_fox": _HUMANOID_ANCHORS,
    "royal_slime": _SLIME_ANCHORS,
}

PET_DAILY_EXP_CAP = 300
PET_ACTION_COOLDOWNS = {
    "feed": 4 * 3600,
    "play": 4 * 3600,
    "gift": 6 * 3600,
}
