# 🏰 CẨM NANG HƯỚNG DẪN HỆ THỐNG BĂNG ĐẢNG (CLAN)

> 💡 **Tài liệu này được biên soạn ngắn gọn, dễ hiểu dành cho toàn thể thành viên server, game thủ và các chủ băng. Toàn bộ tính năng đều được tự động hóa bằng nút bấm và popup (Modal) trực quan, bạn có thể copy nguyên nội dung này để dán vào kênh `#huong-dan` hoặc `#luat-clan` của server Discord!**

---

## ⚡ TRUNG TÂM ĐIỀU KHIỂN 1-CLICK: `/clan hub`
👉 **Cách nhanh nhất để dùng bot:** Bạn chỉ cần gõ lệnh duy nhất `/clan hub`.
Mọi tính năng quan trọng sẽ hiện ra ngay dưới dạng các **nút bấm thông minh**:
- **Nếu chưa có băng:** Bấm nút xem danh sách băng mở tuyển, xem Bảng Xếp Hạng hoặc tự lập băng mới.
- **Nếu đã có băng:** Bấm nút Điểm danh hằng ngày, Xem Nhiệm vụ tuần, Xem hồ sơ băng, Mở bảng quản lý, Cài đặt Role, Xem Cột mốc lịch sử, Xuất ảnh nền Full HD hoặc Trao danh hiệu... bằng 1 cú click!

---

## 👤 PHẦN 1: DÀNH CHO THÀNH VIÊN & NGƯỜI CHƠI (GAMERS)

### 1. Cách Tìm Băng & Xin Gia Nhập
- **Xem tất cả băng trong server:** Gõ `/clan list` để xem băng nào đang mở tuyển và còn slot trống.
- **Xem chi tiết một băng:** Gõ `/clan info` (chọn tên băng từ danh sách tự động gợi ý). Dưới hồ sơ có sẵn nút **`[📩 Xin Gia Nhập]`**.
- **Nộp đơn xin vào băng:** Gõ `/clan apply [tên_băng]`. Bot sẽ mở popup nhỏ để bạn gửi vài lời giới thiệu ngắn.
- **Nếu được mời vào băng:** Khi Cán Bộ mời bạn bằng lệnh `/clan invite`, bạn chỉ việc bấm nút **`[✅ Chấp Nhận Lời Mời]`** màu xanh là vào ngay!

### 2. Điểm Danh Nhận Thưởng Hằng Ngày
- Gõ `/clan checkin` (hoặc bấm nút 📅 trong `/clan hub`).
- Mỗi ngày nhận ngay **+10 Điểm cống hiến cá nhân** và đóng góp **+30 EXP** cho băng.
- **Chuỗi liên tiếp (Streak):** Điểm danh đều đặn 7 ngày liên tiếp được thưởng thêm **+50 EXP**! *(Reset lúc 00:00 hằng ngày theo giờ Việt Nam)*.

### 3. Cày Nhiệm Vụ Tuần Đồng Đội (Weekly Quests)
- Gõ `/clan quests` để theo dõi 3 nhiệm vụ tuần của cả băng:
  1. **📅 Điểm Danh Đồng Đội:** Đạt đủ tổng số 35 lượt check-in của cả băng trong tuần (+350 EXP).
  2. **🎙️ Voice Co-op Chơi Game:** Cùng ngồi kênh Voice buôn chuyện / nghe nhạc / treo máy cùng nhau từ 2 người trở lên (+500 EXP khi đạt 300 phút). Mute hay deafen nghe nhạc vẫn tính điểm bình thường!
  3. **💬 Sôi Nổi Kênh Chat:** Tương tác, trò chuyện trong kênh chat riêng của băng (+300 EXP khi đạt 100 tin nhắn).
- Hoàn thành mỗi nhiệm vụ thưởng thẳng từ **+300 đến +500 EXP** cho băng *(Tự động làm mới vào 00:00 Thứ Hai hằng tuần)*.

### 4. Rời Băng & Thời Gian Chờ (Cooldown)
- Nếu muốn rời băng hiện tại, gõ `/clan leave`.
- ⚠️ **Lưu ý chống nhảy băng:** Sau khi rời băng (hoặc bị trục xuất), bạn cần chờ **24 giờ** mới có thể tạo băng mới hoặc nộp đơn vào băng khác.

---

## 🏰 PHẦN 2: DÀNH CHO CHỦ BĂNG (LEADER) & CÁN BỘ

### 1. Thành Lập Băng Mới: `/clan create`
- Gõ `/clan create`, một bảng nhập liệu (Modal) sẽ hiện lên:
  - **Tên băng:** 3 đến 25 ký tự (Ví dụ: *Hoàng Gia*).
  - **Tag viết tắt:** 2 đến 5 ký tự in hoa (Ví dụ: *HG*).
  - **Khẩu hiệu:** Phương châm hoặc slogan của nhóm.
- Sau khi gửi, bot sẽ tự động tạo Role riêng `[TAG] Tên Băng`, 1 kênh Chat và 1 kênh Voice riêng tư, cấp vai trò Chủ Băng cho bạn!

### 2. Thiết Lập & Tùy Biến Role Băng: `/clan setup-role` (hoặc nút 🛡️ trong `/clan hub`)
Chủ Băng có toàn quyền thiết lập Role cho clan:
- **🌈 Màu Gradient Chuyển Sắc 2 Màu:**
  - Chọn nhanh từ **8 dải Gradient cực đẹp có sẵn** (Sunset Fire, Cyberpunk Neon, Magic Violet, Emerald Forest, Dragon Flame, Golden Luxury, Deep Ocean, Dark Phantom).
  - Hoặc bấm nút **`[🌈 Nhập Màu Gradient]`** (hoặc gõ `/clan set-gradient start_hex:#... end_hex:#...`) để tùy chọn 2 màu bạn thích.
  - 💎 *Lưu ý về Server Boost:* Nếu Server của bạn có Server Boost hỗ trợ đổi màu Gradient, role sẽ chuyển màu tuyệt đẹp trên danh sách thành viên. Nếu Server chưa có Boost, bot sẽ **tự động fallback sang màu đơn sắc chính** mà không gây lỗi!
- **🎨 Bảng Màu Đơn Sắc:** Chọn nhanh 12 màu có sẵn hoặc bấm **`[🎨 Nhập Màu Đơn]`** để gõ mã Hex tùy ý.
- **✏️ Đổi Tên Hiển Thị Role:** Tùy chỉnh tên role hiển thị trên server.
- **📌 Tách Nhóm Thành Viên (Hoist):** 1-click Bật/Tắt hiển thị thành viên clan thành một nhóm riêng biệt trên danh sách online server.
- **🔔 Cho Phép Tag (@mention):** 1-click Bật/Tắt cho phép mọi người tag role.
- **🔗 Liên Kết Role Có Sẵn:** Chọn một Role đã có sẵn trong Server để làm Role Clan (qua menu chọn Role hoặc gõ lệnh `/clan set-role @role`).

### 3. Tải Lên Trực Tiếp Ảnh Logo, Banner & Icon Role: `/clan upload-image`
Không cần phải đi copy link ảnh trên mạng phức tạp, bạn có thể **tải trực tiếp file ảnh từ máy tính hoặc điện thoại**:
- **🖼️ Logo Băng:** `/clan upload-image loai:logo file:[chọn ảnh]` — Ảnh đại diện hiển thị ở góc hồ sơ băng.
- **🎨 Banner Băng (Cấp 2+):** `/clan upload-image loai:banner file:[chọn ảnh]` — Ảnh bìa lớn trang trí hồ sơ băng.
- **🌟 Icon Role Băng:** `/clan upload-image loai:role_icon file:[chọn ảnh]` — Gán Icon hiển thị ngay bên cạnh tên của toàn thể anh em trong server *(Yêu cầu Server Boost Cấp 2)*.

### 4. Bảng Cài Đặt Băng Tổng Thể: `/clan settings`
Mở bảng điều khiển tương tác (dành cho Chủ Băng & Cán Bộ):
- **🛡️ Cài Đặt Role Băng:** Mở nhanh giao diện thiết lập role.
- **🖼️ Cài Logo & Banner:** Cài đặt nhanh qua link URL nếu không muốn upload tệp.
- **🚪 Chế Độ Tuyển Quân:**
  - *🟢 Mở Tự Do (OPEN):* Ai xin vào cũng được duyệt ngay lập tức.
  - *🟡 Cần Duyệt (APPROVAL - Mặc định):* Gửi đơn vào kênh chat để cán bộ bấm nút duyệt.
  - *🔒 Chỉ Nhận Lời Mời (INVITE_ONLY):* Khóa nộp đơn ngoài, chỉ cán bộ mời mới vào được.

### 5. Duyệt Đơn & Chào Đón Thành Viên Mới
- Khi có thành viên nộp đơn, bot sẽ gửi thẻ thông báo vào kênh chat riêng của băng.
- Cán bộ chỉ cần bấm nút **`[✅ Duyệt Đơn]`** hoặc **`[❌ Từ Chối]`** ngay trên tin nhắn.
- Sau khi duyệt thành công, bot sẽ gửi tin nhắn chào mừng kèm nút **`[🎉 Chào Mừng! 👋]`** để anh em trong băng bấm vào gửi lời chào đón đồng đội mới!

### 6. Bổ Nhiệm & Quản Lý Nhân Sự
- **Mời thành viên:** `/clan invite @user` (người được mời có 15 phút để phản hồi).
- **Thăng chức / Giáng chức:**
  - `/clan promote @user`: Nâng bậc từ Thành viên lên Cán Bộ hoặc Phó Băng.
  - `/clan demote @user`: Hạ bậc nhân sự.
  - *Quy định:* Tối đa 2 Phó Băng và 4 Cán Bộ.
- **Trục xuất thành viên vi phạm:** `/clan kick @user [lý do]`.
- **Chuyển giao quyền Chủ Băng:** `/clan transfer @user` (Chủ cũ tự động chuyển thành Phó Băng).
- **Giải tán băng:** `/clan disband` (Yêu cầu gõ chính xác tên băng để xác nhận an toàn 2 lớp).

### 7. Trao Danh Hiệu & Biệt Danh Nội Bộ: Nút `[🎖️ Trao Danh Hiệu]` trong `/clan hub`
- Cán Bộ, Phó Băng và Chủ Băng có thể trao tặng các danh hiệu/biệt danh độc đáo cho thành viên (Ví dụ: `Gánh Team 👑`, `Cú Đêm 🌙`, `Chúa Hề 🤡`, `Trùm Nấu Lẩu 🍲`...).
- **Cách dùng:** Mở `/clan hub` $\rightarrow$ bấm **`[🎖️ Trao Danh Hiệu]`** $\rightarrow$ chọn thành viên từ menu thả xuống $\rightarrow$ nhập danh hiệu mong muốn (hoặc để trống để gỡ).
- Danh hiệu sẽ xuất hiện kiêu hãnh trên **Bảng thành viên (`/clan members`)** và khắc ghi trang trọng trên **Ảnh Nền Wallpaper Full HD** của băng!

### 8. Biên Niên Sử & Xuất Ảnh Nền Wallpaper Full HD (1920x1080)
- **📜 Cột Mốc Lịch Sử:** Bấm **`[📜 Cột Mốc Lịch Sử]`** trong `/clan hub` để xem dòng thời gian ghi dấu các sự kiện trọng đại của băng (ngày thành lập, các mốc thăng cấp).
- **🖼️ Xuất Ảnh Nền Desktop Full HD:** Bấm **`[🖼️ Ảnh Nền Băng (Full HD)]`** trong `/clan hub`. Bot sẽ vẽ tự động tác phẩm Wallpaper 1920x1080 tuyệt đẹp mang biểu tượng, chỉ số, danh sách nòng cốt và biên niên sử của băng để anh em tải về làm hình nền máy tính!

---

## 👑 PHẦN 3: DÀNH CHO QUẢN TRỊ VIÊN SERVER (ADMIN)

### 1. Cơ Chế Tự Động Hóa Thông Minh (Dynamic Auto-Provisioning)
- **Không cần cấu hình phức tạp:** Nếu Admin chưa kịp cài đặt, ngay lần đầu tiên gõ `/clan create`, bot sẽ **tự động khởi tạo Category `🏰 BĂNG ĐẢNG`** và kênh ghi nhật ký `#📜・nhật-ký-băng` hoàn toàn tự động!
- **Tùy chỉnh thủ công (nếu muốn):** Dùng `/clan-admin setup` để chỉ định Category hoặc kênh Log riêng theo ý bạn.

### 2. Phân Quyền Vai Trò Của Bot Trên Discord (RẤT QUAN TRỌNG)
Để bot có thể cấp role và quản lý kênh cho các thành viên:
1. Vào **Cài Đặt Máy Chủ (Server Settings)** $\rightarrow$ **Vai trò (Roles)**.
2. Tìm vai trò của Bot $\rightarrow$ **Kéo vai trò của Bot lên vị trí cao nhất** (hoặc cao hơn toàn bộ các Role Băng Đảng).
3. Đảm bảo vai trò Bot có quyền `Quản lý Vai trò (Manage Roles)` và `Quản lý Kênh (Manage Channels)`.

### 3. Cứu Hộ Tự Động 1-Click: `/clan-admin sync`
- Nếu ai đó trong server lỡ tay xóa nhầm Role hoặc Kênh của một băng, chỉ cần gõ `/clan-admin sync`.
- Bot sẽ tự động rà soát cơ sở dữ liệu và **tự động tạo lại Role/Kênh bị thiếu**, gắn lại quyền chuẩn xác 100%!

### 4. Xóa Bắt Buộc Khi Băng Vi Phạm: `/clan-admin force-delete`
- Gõ `/clan-admin force-delete [tên_băng] [lý_do]`: Bot sẽ hiện nút xác nhận 2 lớp, sau đó xóa sạch Role, Kênh và dữ liệu của băng vi phạm, đồng thời lưu nhật ký xử lý vào kênh Log server.

---

## 📈 PHẦN 4: BẢNG CẤP ĐỘ BĂNG & CÁCH KIẾM EXP

| Cấp Độ | EXP Yêu Cầu | Sĩ Số Tối Đa | Đặc Quyền Nổi Bật |
| :---: | :---: | :---: | :--- |
| **Cấp 1** | 0 EXP | 15 người | 1 Kênh Chat + 1 Kênh Voice riêng, đổi màu Role đơn sắc & Gradient |
| **Cấp 2** | 1.000 EXP | 25 người | Mở khóa tải ảnh bìa Banner hồ sơ băng |
| **Cấp 3** | 3.500 EXP | 40 người | 🔥 **Tự động mở khóa Kênh Voice thứ 2** để chia team chơi game |
| **Cấp 4** | 8.000 EXP | 60 người | Tăng sĩ số tối đa, mở khóa Icon Role (nếu server đạt Boost Lv.2) |
| **Cấp 5** | 15.000 EXP | 100 người | Đỉnh cao danh vọng, tối đa quyền hạn hội nhóm |

### Bí Quyết Cày Cấp Băng Nhanh Nhất:
1. **Điểm danh mỗi ngày (`/clan checkin`):** +30 EXP/người, chuỗi 7 ngày thưởng thêm +50 EXP.
2. **Chat giao lưu trong kênh riêng:** +5 EXP mỗi tin nhắn (cooldown 60 giây chống spam) và tích lũy nhiệm vụ tuần.
3. **Treo Voice chơi game cùng nhau:** Cứ từ 2 thành viên cùng băng ngồi chung phòng Voice, mỗi 5 phút băng được cộng thẳng **+15 EXP**!
4. **Hoàn thành Nhiệm Vụ Tuần (`/clan quests`):** Nhận ngay **+300 đến +500 EXP** cho mỗi nhiệm vụ hoàn thành.
5. **🔥 Sự Kiện Đêm Lửa Trại Cuối Tuần (Weekend Clan Bonfire - x2 EXP):**
   - Diễn ra vào **Thứ Bảy & Chủ Nhật, từ 20:00 đến 23:00** (giờ Việt Nam).
   - Đúng 20:00, bot sẽ **tự động tag vai trò băng (`@Role Clan`)** trong kênh chat riêng của từng băng để hiệu triệu anh em tập hợp.
   - Trong suốt thời gian lửa trại, toàn bộ EXP nhận được từ **Chat và Voice Co-op đều được nhân đôi (x2)**!
   - Đến 23:00, bot sẽ gửi thông báo tổng kết khép lại đêm lửa trại. Đừng bỏ lỡ khung giờ vàng này để bứt phá bảng xếp hạng nhé!
