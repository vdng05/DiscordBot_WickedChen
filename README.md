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
- **1 Discord Role** riêng biệt (định dạng `[TAG] Tên Băng`, hỗ trợ màu đơn sắc, **Gradient 2 màu**, **Icon Role**, tách nhóm `hoist`).
- **1 Kênh Chat Text riêng** *(Riêng tư — chỉ thành viên băng nhìn thấy)*.
- **1 Kênh Nhật Ký Băng riêng (`📜・nhat-ky-...`)** *(Riêng tư — chỉ thành viên băng nhìn thấy để theo dõi lịch sử hoạt động)*.
- **1 Kênh Voice** *(Công khai/Public để mọi người giao lưu; tự động mở khóa thêm **Kênh Voice thứ 2** khi băng đạt Cấp độ 3)*.
- Toàn bộ kênh được gom gọn gàng trong **1 Category duy nhất** do Quản Trị Viên chỉ định. Bot **không tự ý chỉnh sửa hay xóa bất kỳ kênh, role hoặc tin nhắn nào** ngoài lệnh trực tiếp từ người dùng/quản trị viên.

---

## 2. Kiến Trúc Vận Hàng & Ma Trận Phân Quyền (RBAC)

### 📌 Quy Tắc Cốt Lõi
1. **Độc nhất:** Mỗi thành viên chỉ được tham gia tối đa 1 băng đảng duy nhất trong cùng 1 server Discord.
2. **Tự do chuyển băng (Không Cooldown mặc định):** Thành viên rời băng hoặc bị trục xuất có thể tạo hoặc xin vào băng mới ngay lập tức *(Admin vẫn có thể bật cooldown tùy chọn trong `/clan-admin setup`)*.
3. **Quyền riêng tư & An toàn:** Kênh chat và kênh nhật ký của băng tự động khóa `@everyone` (ẩn hoàn toàn) và chỉ cấp quyền truy cập cho Role của băng đó cùng Quản Trị Viên server; kênh Voice để công khai cho cộng đồng giao lưu.
4. **Phân quyền sử dụng Bot (`/bot-access`):** Chủ Bot có thể chọn Role được phép sử dụng bot trên từng server (`Bật Tất Cả` mặc định, `Chọn Role Cụ Thể`, hoặc `Tắt Tất Cả`).

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

### 16 Bảng Dữ Liệu Chính:
1. `guild_configs`: Cấu hình Category, kênh Log, Role yêu cầu và thời gian cooldown của từng Server.
2. `clans`: Lưu trữ tên, tag, khẩu hiệu, role_id, text_channel_id, log_channel_id, voice_channel_id, extra_voice_channel_id, cấp độ, EXP, **chuỗi lửa băng (`clan_streak`, `last_streak_date`, `daily_checkin_count`)**, màu role, logo, banner.
3. `clan_members`: Lưu danh sách thành viên, cấp bậc (LEADER -> MEMBER), danh hiệu nội bộ (`custom_title`), điểm cống hiến, chuỗi ngày điểm danh, và trạng thái **Lửa Streak trên biệt danh** (`streak_nick_enabled`, `last_applied_suffix`, `had_original_nick`, `nick_warned_len`).
4. `member_checkin_history`: Theo dõi lịch sử điểm danh độc lập theo `(guild_id, user_id)` để chống farm điểm danh qua nhiều băng trong ngày.
5. `member_cooldowns`: Theo dõi timestamp hết hạn thời gian chờ sau khi rời băng (nếu server bật cooldown).
6. `clan_requests`: Quản lý lời mời (`INVITE`) và đơn xin vào (`APPLY`), đi kèm `status` (`PENDING`, `ACCEPTED`, `REJECTED`, `EXPIRED`, `CANCELLED`).
7. `clan_parties`: Lưu trữ các kèo chơi game LFG, người tạo, slot tối đa, giờ hẹn, trạng thái `OPEN`/`CLOSED`.
8. `clan_party_participants`: Danh sách người tham gia kèo phân tách giữa `MAIN` (đội hình chính) và `RESERVE` (dự bị).
9. `clan_weekly_quests`: 3 nhiệm vụ hợp tác tuần của từng băng (`CHECKIN_COUNT`, `VOICE_MINUTES`, `CHAT_MESSAGES`).
10. `clan_daily_quests`: 3 nhiệm vụ ngày của từng băng (`DAILY_CHECKIN`, `DAILY_CHAT`, `DAILY_VOICE`), thưởng EXP & Xu Linh Thú.
11. `clan_pets`: Linh Thú chung của từng băng (`species`, `name`, `exp`, `level`, `stage`, `hunger`, `mood`, `pet_coins`, `equipped_json`, `allow_member_style`).
12. `clan_pet_inventory`: Tủ đồ chung các trang phục & phụ kiện Linh Thú đã mở khóa của băng.
13. `clan_pet_cooldowns`: Cooldown tương tác chăm sóc Linh Thú theo từng thành viên.
14. `clan_logs`: Lịch sử hoạt động nội bộ (thăng/giáng chức, mời, rời, kick, thăng cấp, danh hiệu).
15. `clan_milestones`: Các cột mốc lịch sử trọng đại của băng (ngày thành lập, các mốc thăng cấp).
16. `bot_access_configs`: Cấu hình phân quyền Role được phép sử dụng bot theo từng server (`ALL`, `ROLES`, `NONE`).

---

## 4. Danh Mục Bộ Lệnh Slash Commands Đầy Đủ

### 4.1. Nhóm A: Quản Trị Server & Chủ Bot (`/clan-admin`, `/bot-access`)
- `/clan-admin setup`: Chỉ định Category chứa kênh các băng, kênh Log sự kiện, bật/tắt cho mem tự tạo, role điều kiện và số giờ cooldown rời băng (mặc định `0`).
- `/clan-admin force-delete [tên_băng] [lý_do]`: Buộc xóa băng vi phạm quy định server (đi kèm nút xác nhận 2 lớp an toàn).
- `/clan-admin sync`: Quét toàn bộ server, tự động khôi phục lại Role/Kênh bị thiếu nếu lỡ bị xóa tay và đồng bộ thành viên (không tự ý sửa tên hay xóa kênh đang tồn tại).
- `/bot-access` *(Dành riêng cho Chủ Bot trong `OWNER_IDS`)*: Phân quyền Role được phép dùng bot (`Bật Tất Cả`, `Chọn Role Cụ Thể` có phân trang, hoặc `Tắt Tất Cả`) và mở **👑 Quản Lý & Buff Hệ Thống** (buff EXP băng, buff Pet & Xu, đổi Loài/Stage & xem trước Pet trực tiếp, mở Full Tủ Đồ, Random Style, sửa tên/tag/sĩ số, hoặc xóa sạch băng/Pet).

### 4.2. Nhóm B: Trung Tâm Điều Khiển, Khởi Tạo & Tùy Biến Băng
- `/clan hub`: **Trung tâm điều khiển 1-Click tinh gọn** (`Nhiệm Vụ & Điểm Danh`, `Hồ Sơ Băng`, `Linh Thú Băng`, `Thách Đấu / Tạo Kèo`, `Bảng Xếp Hạng`, `Cột Mốc Lịch Sử`, `Quản Lý Thành Viên`, `Đăng Tin Tuyển`, `Cài Đặt Băng`) với cơ chế điều hướng tại chỗ & tự động dọn bảng cũ.
- `/clan-pet`: Mở trực tiếp bảng **Linh Thú Băng Đảng** (chọn 1 trong 4 loài: *Mèo Cyber, Tiểu Long, Cáo Tinh, Slime Hoàng Gia*; nuôi qua 5 giai đoạn từ Trứng → Tối Thượng bằng đồ họa Pillow 2x Supersampling; Cửa hàng xem trước 45 món đồ & Tủ đồ ôm khít silhouette; buff +5% đến +15% EXP Điểm danh & xuất hiện trên Wallpaper Full HD).
- `/clan create`: Mở **Discord Modal** nhập Tên băng (3-25 ký tự), Tag ngắn (2-5 ký tự viết hoa), Khẩu hiệu (tối đa 100 ký tự). Bot tự tạo Role và cụm 3 kênh (Chat riêng, Nhật ký riêng, Voice công khai).
- `/clan settings`: Mở bảng điều khiển dành riêng cho **Chủ Băng (`LEADER`) hoặc Admin Server**:
  - *Đổi Tên / Tag / Khẩu Hiệu:* Hộp thoại Modal nhập mới (khóa cooldown 7 ngày để chống Rate Limit Discord).
  - *Cài Đặt Role (`/clan setup-role`, `/clan set-role`, `/clan set-gradient`):* Đổi tên Role, màu đơn sắc hoặc **Gradient 2 màu**, tách nhóm (`hoist`), cho phép tag (`mentionable`), hoặc liên kết Role an toàn có sẵn *(chặn Role quản trị/nhạy cảm, Role của băng khác và Role đang có người ngoài băng nắm giữ nếu bạn không phải Admin)*.
  - *Logo, Banner & Icon Role (`/clan upload-image`, `/clan set-image`):* Tải ảnh trực tiếp từ máy tính/điện thoại (thời gian chờ **15 phút**), dán link URL, hoặc dùng **Logo Bát Giác & Banner Cyber Gaming Canvas mặc định** (Logo & Banner dùng được ngay từ Level 1; Icon Role yêu cầu server đạt Boost Lv.2).
  - *Chế Độ Tuyển Quân:* Chọn giữa Mở Tự Do (`OPEN`), Cần Duyệt (`APPROVAL` - mặc định), hoặc Chỉ Nhận Lời Mời (`INVITE_ONLY`).
- `/clan disband`: Mở Modal bắt buộc nhập chính xác tên băng để xác nhận giải tán.
- `/clan help`: Xem hướng dẫn sử dụng chi tiết trực quan ngay trong Discord.

### 4.3. Nhóm C: Nhân Sự & Tuyển Quân
- `/clan invite [@user]`: Ưu tiên gửi thẻ lời mời kèm nút **Chấp Nhận** / **Từ Chối** thẳng qua **DM** của người được mời (nếu khóa DM mới gửi ra kênh công khai, tuyệt đối không gửi vào kênh riêng của băng). Hết hạn sau 15 phút.
- `/clan-recruit`: *(Cán Bộ trở lên)* Mở Modal nhập thông tin tuyển thành viên và tự động đăng bài chiêu mộ công khai (kèm Logo, Banner, khẩu hiệu và nút `[Xin Gia Nhập Băng]`, `[Xem Thành Viên]`) vào kênh `#tuyen-thanh-vien` thuộc Category `BOT CLAN`.
- `/clan apply [tên_băng]`: Nộp đơn xin gia nhập băng kèm lời nhắn giới thiệu. Đẩy đơn vào kênh chat riêng để Cán Bộ duyệt (hoặc duyệt ngay nếu băng ở chế độ Mở Tự Do).
- `/clan promote [@user]` & `/clan demote [@user]`: Thăng hoặc giáng chức theo nấc `MEMBER ↔ OFFICER ↔ CO_LEADER` (khống chế tối đa 2 Phó Băng và 4 Cán Bộ).
- `/clan transfer [@user]`: Chuyển quyền Chủ Băng cho thành viên khác (Chủ Băng cũ tự động chuyển thành Phó Băng).
- `/clan kick [@user] [lý_do]`: Trục xuất thành viên cấp thấp hơn khỏi băng và gửi thông báo DM kèm lý do.
- `/clan leave`: Tự nguyện rời băng (có xác nhận 2 lớp; Chủ Băng bắt buộc phải nhượng quyền hoặc giải tán).

### 4.4. Nhóm D: Hồ Sơ, Thành Viên & Bảng Xếp Hạng
- `/clan info [tên_băng]`: Xem hồ sơ băng đảng màu trùng màu Role, kèm Logo, Banner, Sĩ số, Cấp độ, **🔥 Chuỗi Lửa Băng**, Thanh tiến trình EXP và các nút tương tác nhanh (**Xem Thành Viên**, **Điểm Danh Nhanh**, **Xem Banner Băng**, **Ảnh Nền Băng Full HD**, **Rời Băng**, **🔥 Lửa Streak: Đang Tắt/Bật** để tự nguyện gắn ` 🔥 N` sau tên gốc).
- `/clan members [tên_băng]`: Danh sách thành viên phân trang (10 người/trang), hiển thị chức vụ, **danh hiệu nội bộ**, điểm cống hiến, kèm **Menu Dropdown lọc theo chức vụ**.
- `/clan list`: Danh sách toàn bộ các băng trong server kèm trạng thái tuyển quân.
- `/clan leaderboard [tiêu_chí]`: Bảng vinh danh top băng đảng theo Cấp độ & EXP, Năng động tuần, hoặc Đông thành viên nhất.
- `/clan logs [trang]`: Nhật ký hoạt động nội bộ gần đây kèm mốc thời gian tương đối của Discord (`<t:timestamp:R>`).

### 4.5. Nhóm E: Hoạt Động Gắn Kết & Thách Đấu
- `/clan checkin`: Điểm danh mỗi ngày (reset lúc 00:00 giờ Việt Nam). Thưởng **+30 EXP băng**, **+10 Điểm cống hiến** và **+15 Xu Linh Thú**. Đạt chuỗi cá nhân 7 ngày liên tiếp thưởng thêm **+50 EXP**. Khi băng đạt **≥ 2 người điểm danh/ngày**, **Chuỗi Lửa Băng (`clan_streak`)** tăng +1 và tự động đồng bộ lên biệt danh các thành viên đang bật Lửa Streak.
- `/clan party`: Mở trung tâm **Thách Đấu & Lập Kèo**:
  - **Gửi Thư Thách Đấu:** Chọn 1 băng đối thủ (hoặc tất cả các băng trong server — chỉ `LEADER`/`CO_LEADER`, cooldown 12 giờ/lần để chống spam ping), nhập Tựa Game, Thể Thức, Thời Gian và Nội Dung qua Modal; băng nhận có nút **Chấp Nhận Thách Đấu** / **Từ Chối Lịch Sự**.
  - **Lập Kèo Nội Bộ (LFG):** Rủ anh em cùng băng lập team chơi game kèm nút **Tham Gia**, **Dự Bị**, **Rút Lui**, **Chốt / Đóng Kèo** và tự động nhắc trước 10 phút.
- `/clan quests`: Bảng theo dõi **Nhiệm Vụ Ngày** (3 nhiệm vụ làm mới 00:00 mỗi ngày) & **Nhiệm Vụ Tuần** (3 nhiệm vụ đồng đội: **Điểm danh**, **Voice Co-op**, **Sôi nổi kênh chat**, thưởng **+300 đến +500 EXP**).

---

## 5. Cơ Chế Cấp Độ, Năng Động & Mở Khóa Đặc Quyền

### Nguồn Cộng EXP Băng:
- **Chat tương tác:** +5 EXP băng & +1 Điểm cống hiến (tin nhắn tối thiểu 5 ký tự trong kênh chat băng, cooldown 60 giây chống spam).
- **Ngồi Voice Co-op:** Cứ mỗi 5 phút có từ 2 thành viên cùng băng ngồi chung trong kênh Voice (không tính kênh AFK; vẫn tính khi mute/deafen), băng nhận **+15 EXP** và mỗi người nhận **+3 Điểm cống hiến**.
- **Đêm Lửa Trại Cuối Tuần (x2 EXP):** Diễn ra vào **20:00 – 23:00 Thứ Bảy & Chủ Nhật** (giờ Việt Nam), nhân đôi toàn bộ EXP nhận được từ Chat và Voice Co-op.
- **Điểm danh & Nhiệm vụ tuần:** Cộng thưởng theo quy tắc ở Nhóm E *(lịch sử điểm danh theo dõi độc lập từng ngày theo `(guild_id, user_id)`, không thể rời băng sang băng khác để điểm danh lần 2 trong ngày)*.

### Bảng Mốc Cấp Độ:
| Cấp độ | EXP yêu cầu | Sĩ số tối đa | Đặc quyền nổi bật |
| :---: | :---: | :---: | :--- |
| **Level 1** | 0 EXP | 15 người | 1 Kênh Chat riêng + 1 Kênh Nhật Ký + 1 Kênh Voice public, đổi màu Role đơn sắc/Gradient, upload Logo & Banner (Icon Role tùy theo Server Boost Lv.2) |
| **Level 2** | 1.000 EXP | 25 người | Tăng sĩ số tối đa lên 25, mở rộng không gian hoạt động của băng |
| **Level 3** | 3.500 EXP | 40 người | **Mở khóa kênh Voice thứ 2** (tự động tạo kênh Voice 2 tách nhóm chơi game) |
| **Level 4** | 8.000 EXP | 60 người | Tăng sĩ số tối đa lên 60 thành viên |
| **Level 5** | 15.000 EXP | 100 người | Đỉnh cao danh vọng, tối đa 100 thành viên |

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
│   ├── canvas.py              # Vẽ Logo Bát Giác, Banner Cyber Gaming & Wallpaper Full HD 1920x1080
│   ├── constants.py           # Bảng mốc Level, chức vụ, EXP, nhiệm vụ tuần
│   ├── database.py            # SQLite bất đồng bộ (aiosqlite WAL Mode)
│   ├── embeds.py              # Xây dựng Discord Embeds trực quan & thanh tiến trình
│   ├── error_handler.py       # Bộ bắt và xử lý lỗi tập trung cho Slash Commands
│   ├── image_storage.py       # Lưu trữ bền vững ảnh Logo/Banner tải lên (local://)
│   ├── logger.py              # Định dạng log màu và timestamp
│   ├── pet_canvas.py          # Canvas Engine 2x vẽ Linh Thú 5 giai đoạn & trang phục ôm khít silhouette
│   ├── streak_nick.py         # Dịch vụ Lửa Streak trên biệt danh (Exact-Suffix Match, giới hạn 32 ký tự)
│   ├── text_helper.py         # Chuyển đổi tên kênh tiếng Việt không dấu chuẩn Discord
│   ├── time_helper.py         # Xử lý giờ Việt Nam (Asia/Ho_Chi_Minh) & chu kỳ tuần ISO
│   └── ui_components.py       # Discord Views, Buttons, Select Menus và Modals
├── data/
│   └── clan_bot.db            # File SQLite cơ sở dữ liệu duy nhất
├── tests/
│   └── test_system.py         # Bộ kiểm thử tích hợp 35 bài test tự động
├── HDSD.md                    # Cẩm nang hướng dẫn sử dụng chi tiết cho người dùng & Admin
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
DEFAULT_LEAVE_COOLDOWN_HOURS=0
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
