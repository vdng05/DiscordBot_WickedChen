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
