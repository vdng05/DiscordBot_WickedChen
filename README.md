# 🏰 WickedChen Clan Bot — All-in-One Discord Clan System

<p align="center">
  <b>Hệ thống Quản lý Băng Đảng & Hội Nhóm Cộng Đồng Hòa Bình trên Discord, kiến trúc Feature-Folder (Vertical Slice Architecture), tích hợp SQLite bất đồng bộ (aiosqlite WAL Mode) siêu nhẹ, chuẩn mực dự án SosaGallery và tối ưu 100% cho VPS nhẹ.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Version" />
  <img src="https://img.shields.io/badge/discord.py-v2.3+-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="discord.py" />
  <img src="https://img.shields.io/badge/Architecture-Feature--Folder-success?style=for-the-badge" alt="Architecture" />
  <img src="https://img.shields.io/badge/Database-SQLite%20(WAL%20Mode)-blue?style=for-the-badge" alt="Database" />
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
</p>

---

## 📑 Mục Lục
- [1. Giới Thiệu Dự Án](#1-giới-thiệu-dự-án)
- [2. Kiến Trúc Vận Hành & Ma Trận Phân Quyền (RBAC)](#2-kiến-trúc-vận-hành--ma-trận-phân-quyền-rbac)
- [3. Cơ Sở Dữ Liệu SQLite Bất Đồng Bộ (WAL Mode)](#3-cơ-sở-dữ-liệu-sqlite-bất-đồng-bộ-wal-mode)
- [4. Danh Mục Bộ Lệnh Slash Commands Đầy Đủ](#4-danh-mục-bộ-lệnh-slash-commands-đầy-đủ)
  - [4.1. Nhóm A: Quản Trị Server (/clan-admin)](#41-nhóm-a-quản-trị-server-clan-admin)
  - [4.2. Nhóm B: Khởi Tạo & Tùy Biến Băng (/clan create, settings, disband)](#42-nhóm-b-khởi-tạo--tùy-biến-băng-clan-create-settings-disband)
  - [4.3. Nhóm C: Nhân Sự & Tuyển Quân (/clan invite, apply, promote, kick...)](#43-nhóm-c-nhân-sự--tuyển-quân-clan-invite-apply-promote-kick)
  - [4.4. Nhóm D: Hồ Sơ, Thành Viên & Bảng Xếp Hạng (/clan info, members, list...)](#44-nhóm-d-hồ-sơ-thành-viên--bảng-xếp-hạng-clan-info-members-list)
  - [4.5. Nhóm E: Hoạt Động Gắn Kết (/clan checkin, party, quests)](#45-nhóm-e-hoạt-động-gắn-kết-clan-checkin-party-quests)
- [5. Cơ Chế Cấp Độ, Năng Động & Mở Khóa Đặc Quyền](#5-cơ-chế-cấp-độ-năng-động--mở-khóa-đặc-quyền)
- [6. Cấu Trúc Thư Mục Chuẩn Hóa (Feature-Folder)](#6-cấu-trúc-thư-mục-chuẩn-hóa-feature-folder)
- [7. Hướng Dẫn Cài Đặt & Triển Khai Toàn Diện](#7-hướng-dẫn-cài-đặt--triển-khai-toàn-diện)
  - [Cách 1: Chạy trực tiếp bằng Python (Windows / Linux) — Khuyên dùng](#cách-1-chạy-trực-tiếp-bằng-python-windows--linux)
  - [Cách 2: Triển khai 1-click bằng Docker & Docker Compose](#cách-2-triển-khai-1-click-bằng-docker--docker-compose)
- [8. Cơ Chế Phòng Ngừa Lỗi & Chống Race Condition](#8-cơ-chế-phòng-ngừa-lỗi--chống-race-condition)

---

## 1. Giới Thiệu Dự Án

**WickedChen Clan Bot** là hệ thống quản lý hội nhóm / băng đảng Discord vận hành theo triết lý **hòa bình, gắn kết cộng đồng**, tập trung vào rủ nhau chơi game (Party LFG), điểm danh nhận thưởng, thi đua lành mạnh và nâng cấp không gian sinh hoạt chung.

Mỗi băng đảng trong server được ánh xạ trực tiếp thành:
- **1 Discord Role** riêng biệt (định dạng `[TAG] Tên Băng`, bật `hoist` để phân tách trên cột thành viên).
- **1 Kênh Chat Text riêng** bảo mật tuyệt đối.
- **1 Kênh Voice riêng** (và tự động mở khóa thêm **Kênh Voice thứ 2** khi băng đạt Cấp độ 3).
- Toàn bộ kênh được gom gọn gàng trong **1 Category** do Quản Trị Viên chỉ định.

---

## 2. Kiến Trúc Vận Hàng & Ma Trận Phân Quyền (RBAC)

### 📌 Quy Tắc Cốt Lõi
1. **Độc nhất:** Mỗi thành viên chỉ được tham gia tối đa 1 băng đảng duy nhất trong cùng 1 server Discord.
2. **Chống nhảy băng (Cooldown):** Sau khi tự rời băng hoặc bị trục xuất, thành viên phải chờ **24 giờ** (Admin có thể tùy chỉnh) mới được phép lập băng hoặc xin vào băng mới.
3. **Quyền riêng tư tuyệt đối:** Kênh riêng của băng tự động khóa `@everyone` (ẩn hoàn toàn) và chỉ cấp quyền truy cập cho Role của băng đó cùng Quản Trị Viên server.

### 🛡️ Ma Trận Phân Quyền (RBAC)
| Chức năng / Quyền hạn | Admin Server | Chủ Băng (LEADER) | Phó Băng (CO_LEADER) | Cán Bộ (OFFICER) | Thành Viên (MEMBER) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Cấu hình Category, giới hạn server | ✅ | ❌ | ❌ | ❌ | ❌ |
| Tạo băng mới (hoặc xét duyệt) | ✅ | Tùy cấu hình | Tùy cấu hình | Tùy cấu hình | Tùy cấu hình |
| Sửa tên, tag, logo, banner, màu Role | ✅ | ✅ | ❌ | ❌ | ❌ |
| Bổ nhiệm / Giáng chức Phó Băng | ✅ | ✅ | ❌ | ❌ | ❌ |
| Bổ nhiệm / Giáng chức Cán Bộ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Duyệt đơn xin gia nhập / Mời thành viên | ❌ | ✅ | ✅ | ✅ | ❌ |
| Trục xuất (kick) thành viên cấp thấp hơn | ✅ | ✅ | ✅ (chỉ Officer/Member) | ❌ | ❌ |
| Chuyển giao quyền Chủ Băng / Giải tán băng | ✅ (chỉ xóa) | ✅ | ❌ | ❌ | ❌ |
| Tạo kèo chơi chung (Party / LFG) | ❌ | ✅ | ✅ | ✅ | ✅ |
| Xem hồ sơ, danh sách, điểm danh, rời băng | ✅ (chỉ xem) | ✅ (không thể tự rời) | ✅ | ✅ | ✅ |

---

## 3. Cơ Sở Dữ Liệu SQLite Bất Đồng Bộ (WAL Mode)

Hệ thống sử dụng **SQLite 3** kết hợp chế độ **WAL (Write-Ahead Logging)** thông qua thư viện `aiosqlite`, cho phép đọc và ghi bất đồng bộ với độ trễ cực thấp, không tốn RAM và không cần cài đặt các hệ quản trị nặng nề:

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
```

### 8 Bảng Dữ Liệu Chính:
1. `guild_configs`: Cấu hình Category, kênh Log, Role yêu cầu và thời gian cooldown của từng Server.
2. `clans`: Lưu trữ tên, tag, khẩu hiệu, role_id, text_channel_id, voice_channel_id, cấp độ, EXP, màu role, logo, banner.
3. `clan_members`: Lưu danh sách thành viên, cấp bậc (LEADER -> MEMBER), điểm cống hiến, chuỗi ngày điểm danh (Streak).
4. `member_cooldowns`: Theo dõi timestamp hết hạn thời gian chờ sau khi rời băng.
5. `clan_requests`: Quản lý lời mời (`INVITE`) và đơn xin vào (`APPLY`), đi kèm `status` (PENDING, ACCEPTED, REJECTED, EXPIRED).
6. `clan_parties`: Lưu trữ các kèo chơi game LFG, người tạo, slot tối đa, giờ hẹn, trạng thái OPEN/CLOSED.
7. `clan_party_participants`: Danh sách người tham gia kèo phân tách giữa `MAIN` (đội hình chính) và `RESERVE` (dự bị).
8. `clan_weekly_quests`: 3 nhiệm vụ hợp tác tuần của từng băng (CHECKIN_COUNT, VOICE_MINUTES, PARTY_COMPLETED).
9. `clan_logs`: Lịch sử hoạt động nội bộ (thăng/giáng chức, mời, rời, kick, thăng cấp).

---

## 4. Danh Mục Bộ Lệnh Slash Commands Đầy Đủ

### 4.1. Nhóm A: Quản Trị Server (/clan-admin)
- `/clan-admin setup`: Chỉ định Category chứa kênh các băng, kênh Log sự kiện, bật/tắt cho mem tự tạo, role điều kiện và số giờ cooldown rời băng.
- `/clan-admin force-delete [tên_băng] [lý_do]`: Buộc xóa băng vi phạm quy định server (đi kèm nút xác nhận 2 lớp an toàn).
- `/clan-admin sync`: Quét toàn bộ server, tự động khôi phục lại Role/Kênh nếu lỡ bị Admin xóa tay, đồng thời đồng bộ lại danh sách thành viên giữa Discord và Database.

### 4.2. Nhóm B: Khởi Tạo & Tùy Biến Băng
- `/clan create`: Mở **Discord Modal** nhập Tên băng (3-25 ký tự), Tag ngắn (2-5 ký tự viết hoa), Khẩu hiệu (tối đa 100 ký tự). Bot tự tạo Role hoisted và cụm kênh Chat/Voice riêng.
- `/clan settings`: Mở bảng điều khiển **Ephemeral** dành riêng cho Chủ Băng:
  - *Đổi Tên / Tag / Khẩu Hiệu:* Hộp thoại Modal nhập mới (khóa cooldown 7 ngày để chống Rate Limit Discord).
  - *Đổi Màu Role:* Nhập mã màu Hex tùy ý (ví dụ `#FF5733`).
  - *Logo & Banner:* Cài đặt link ảnh Logo hiển thị hoặc Banner hồ sơ (Banner mở khóa khi đạt Level 2).
  - *Chế Độ Tuyển Quân:* Chọn giữa Mở Tự Do (vào thẳng), Cần Duyệt (mặc định), hoặc Chỉ Nhận Lời Mời.
- `/clan disband`: Mở Modal bắt buộc nhập chính xác tên băng để xác nhận giải tán.
- `/clan set-image [loại: logo / banner] [link / đính kèm ảnh]`: Cập nhật nhanh ảnh cho băng.

### 4.3. Nhóm C: Nhân Sự & Tuyển Quân
- `/clan invite [@user]`: Gửi thẻ lời mời vào kênh chat kèm nút **Chấp Nhận** (xanh) và **Từ Chối** (đỏ). Hết hạn sau 15 phút.
- `/clan apply [tên_băng]`: Nộp đơn xin gia nhập băng kèm lời nhắn giới thiệu. Đẩy đơn vào kênh chat riêng để Cán Bộ duyệt.
- `/clan promote [@user]` & `/clan demote [@user]`: Thăng hoặc giáng chức theo nấc `MEMBER ↔ OFFICER ↔ CO_LEADER` (khống chế tối đa 2 Phó Băng và 4 Cán Bộ).
- `/clan transfer [@user]`: Chuyển quyền Chủ Băng cho thành viên khác (Chủ Băng cũ tự động chuyển thành Phó Băng).
- `/clan kick [@user] [lý_do]`: Trục xuất thành viên cấp thấp hơn khỏi băng và gắn cooldown 24 giờ.
- `/clan leave`: Tự nguyện rời băng (Chủ Băng bị khóa lệnh này, bắt buộc phải nhượng quyền hoặc giải tán).

### 4.4. Nhóm D: Hồ Sơ, Thành Viên & Bảng Xếp Hạng
- `/clan info [tên_băng]`: Xem hồ sơ băng đảng màu trùng màu Role, kèm ảnh Logo, Banner, Sĩ số, Cấp độ, Thanh tiến trình EXP ASCII và 2 nút bấm tương tác nhanh: **Xem Thành Viên** và **Xin Gia Nhập**.
- `/clan members [tên_băng]`: Danh sách thành viên phân trang (10 người/trang), sắp xếp theo chức vụ và điểm cống hiến, kèm **Menu Dropdown lọc theo chức vụ**.
- `/clan list`: Danh sách toàn bộ các băng trong server kèm trạng thái tuyển quân.
- `/clan leaderboard [tiêu_chí]`: Bảng vinh danh top băng đảng theo Cấp độ & EXP, Năng động tuần, hoặc Đông thành viên nhất.
- `/clan logs [trang]`: Nhật ký hoạt động nội bộ gần đây kèm mốc thời gian tương đối của Discord (`<t:timestamp:R>`).

### 4.5. Nhóm E: Hoạt Động Gắn Kết
- `/clan checkin`: Điểm danh mỗi ngày (reset lúc 00:00 giờ Việt Nam). Thưởng **+30 EXP băng**, **+10 Điểm cống hiến**. Đạt chuỗi 7 ngày liên tiếp thưởng thêm **+50 EXP**.
- `/clan party [tiêu_đề] [số_người] [thời_gian]`: Tạo thẻ kèo rủ chơi game (LFG) trong kênh chat riêng của băng. Gồm các nút: **Tham Gia (Đội hình chính)**, **Dự Bị**, **Rút Lui** và **Chốt / Đóng Kèo**. Bot tự động ping nhắc nhở 10 phút trước giờ hẹn.
- `/clan quests`: Bảng theo dõi 3 nhiệm vụ tuần đồng đội (Điểm danh, Ngồi Voice co-op, Tổ chức kèo Party). Hoàn thành thưởng từ +300 đến +500 EXP.

---

## 5. Cơ Chế Cấp Độ, Năng Động & Mở Khóa Đặc Quyền

### Nguồn Cộng EXP Băng:
- **Chat tương tác:** +5 EXP băng & +1 Điểm cống hiến (tin nhắn tối thiểu 5 ký tự, cooldown 60 giây chống spam).
- **Ngồi Voice Co-op:** Cứ mỗi 5 phút có từ 2 thành viên cùng băng ngồi chung trong kênh Voice bất kỳ (không tính người tự tắt loa `self_deaf` hoặc kênh AFK), băng nhận **+15 EXP** và mỗi người nhận **+3 Điểm cống hiến**.
- **Điểm danh & Nhiệm vụ tuần:** Cộng thưởng theo quy tắc ở Nhóm E.

### Bảng Mốc Cấp Độ:
| Cấp độ | EXP yêu cầu | Sĩ số tối đa | Đặc quyền mở khóa |
| :---: | :---: | :---: | :--- |
| **Level 1** | 0 EXP | 15 người | 1 Kênh Text + 1 Kênh Voice riêng, đổi màu Role cơ bản |
| **Level 2** | 1.000 EXP | 25 người | Mở khóa đặt Banner hồ sơ băng, tùy chỉnh khẩu hiệu |
| **Level 3** | 3.500 EXP | 40 người | **Mở khóa kênh Voice thứ 2** (tự động tạo kênh Voice 2 tách nhóm chơi game) |
| **Level 4** | 8.000 EXP | 60 người | Mở khóa Icon Role VIP, huy hiệu trên Bảng Xếp Hạng |
| **Level 5** | 15.000 EXP | 100 người | Không giới hạn kèo Party song song, đổi định dạng tên kênh tự do |

---

## 6. Cấu Trúc Thư Mục Chuẩn Hóa (Feature-Folder)

```plaintext
WickedChen/
├── cogs/
│   ├── clan_admin/
│   │   ├── __init__.py
│   │   └── clan_admin.py      # Lệnh quản trị server: setup, force-delete, sync
│   ├── clan/
│   │   ├── __init__.py
│   │   └── clan_commands.py   # Toàn bộ Slash Commands /clan (Nhóm B, C, D, E)
│   └── clan_events/
│       ├── __init__.py
│       └── clan_events.py     # Xử lý chat EXP, voice ticker 5p, party reminder, reset tuần
├── utils/
│   ├── constants.py           # Bảng mốc Level, chức vụ, EXP, nhiệm vụ tuần
│   ├── database.py            # SQLite bất đồng bộ (aiosqlite WAL Mode)
│   ├── embeds.py              # Xây dựng Discord Embeds trực quan & thanh tiến trình
│   ├── error_handler.py       # Bộ bắt và xử lý lỗi tập trung cho Slash Commands
│   ├── logger.py              # Định dạng log màu và timestamp
│   ├── time_helper.py         # Xử lý giờ Việt Nam (Asia/Ho_Chi_Minh) & chu kỳ tuần ISO
│   └── ui_components.py       # Discord Views, Buttons, Select Menus và Modals
├── data/
│   └── clan_bot.db            # File SQLite cơ sở dữ liệu duy nhất
├── tests/
│   └── test_system.py         # Bộ kiểm thử tích hợp 10 bài test tự động
├── config.py                  # Quản lý tập trung mọi biến môi trường
├── Dockerfile                 # Đóng gói container Docker siêu nhẹ
├── docker-compose.yml         # Triển khai 1-click trên VPS
├── requirements.txt           # Thư viện phụ thuộc
├── .env.example               # Mẫu cấu hình
├── .env                       # File cấu hình thực tế (chứa Bot Token)
└── main.py                    # Điểm khởi chạy chính của Bot
```

---

## 7. Hướng Dẫn Cài Đặt & Triển Khai Toàn Diện

### Cách 1: Chạy trực tiếp bằng Python (Windows / Linux)

#### Bước 1: Cài đặt Python 3.12+
Đảm bảo máy đã cài đặt Python 3.12 trở lên:
```bash
python --version
```

#### Bước 2: Cài đặt thư viện phụ thuộc
```bash
pip install -r requirements.txt
```

#### Bước 3: Cấu hình file `.env`
Mở file `.env` và điền thông tin của bot:
```env
DISCORD_TOKEN=dien_bot_token_vao_day
OWNER_IDS=dien_discord_user_id_cua_ban
SYNC_ON_STARTUP=true
TIMEZONE=Asia/Ho_Chi_Minh
DEFAULT_LEAVE_COOLDOWN_HOURS=24
LOG_LEVEL=INFO
```

> [!IMPORTANT]
> **Bật đầy đủ Privileged Gateway Intents trên Discord Developer Portal:**
> 1. Truy cập [Discord Developer Portal](https://discord.com/developers/applications).
> 2. Chọn Bot của bạn -> Mục **Bot**.
> 3. Bật cả 3 mục: **Presence Intent**, **Server Members Intent**, và **Message Content Intent**.

#### Bước 4: Khởi chạy Bot
```bash
python main.py
```

---

### Cách 2: Triển khai 1-click bằng Docker & Docker Compose

Triển khai gọn gàng trên Linux VPS chỉ với 1 dòng lệnh:
```bash
# Khởi chạy ngầm container
docker compose up -d --build

# Xem log hoạt động thời gian thực
docker compose logs -f
```

---

## 8. Cơ Chế Phòng Ngừa Lỗi & Chống Race Condition

1. **Khóa nguyên tử chống Race Condition khi duyệt đơn:**
   Câu lệnh SQL cập nhật trạng thái đơn duyệt luôn đi kèm điều kiện:
   ```sql
   UPDATE clan_requests SET status = ? WHERE request_id = ? AND status = 'PENDING'
   ```
   Sau đó kiểm tra `rowcount == 1`. Nếu 2 Phó Băng cùng bấm Duyệt 1 lúc, chỉ đúng 1 người thao tác thành công, người còn lại nhận thông báo đã được xử lý.

2. **Chống lỗi Thứ bậc Role (Role Hierarchy):**
   Role của Bot trong mục **Server Settings -> Roles** phải được kéo nằm **cao hơn** toàn bộ Role Băng Đảng. Nếu role bot nằm thấp hơn, Discord sẽ chặn quyền quản lý role.

3. **Tự động xử lý khi Chủ Băng rời server:**
   Nếu Chủ Băng thoát khỏi server, bot tự động tìm Phó Băng gia nhập lâu nhất (hoặc Cán Bộ / Thành Viên lâu nhất) để tự động trao lại quyền Chủ Băng và thông báo vào kênh chat. Nếu không còn ai trong băng, bot tự động dọn dẹp sạch kênh và role.

4. **Khôi phục khi Admin lỡ tay xóa kênh/role:**
   Nếu kênh hoặc role của băng bị xóa thủ công, bot ghi nhận và phát cảnh báo vào `log_channel`, admin chỉ cần gõ `/clan-admin sync` để tự động tái tạo.
