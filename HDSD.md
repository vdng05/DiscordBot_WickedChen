# 🏰 CẨM NANG HƯỚNG DẪN HỆ THỐNG BĂNG ĐẢNG (CLAN)

> 💡 **Tài liệu này được biên soạn ngắn gọn, dễ hiểu dành cho toàn thể thành viên server, game thủ và các chủ băng. Toàn bộ tính năng đều được tự động hóa bằng nút bấm và popup (Modal) trực quan, bạn có thể copy nguyên nội dung này để dán vào kênh `#huong-dan` hoặc `#luat-clan` của server Discord!**

---

## ⚡ TRUNG TÂM ĐIỀU KHIỂN 1-CLICK: `/clan hub`
👉 **Cách nhanh nhất để dùng bot:** Bạn chỉ cần gõ lệnh duy nhất `/clan hub`.
Mọi tính năng quan trọng đều được **model hóa 100% bằng nút bấm, menu thả xuống và popup (Modal)**:
- **Nếu chưa có băng:**
  - Bấm **`[📩 Nộp Đơn Vào Băng]`**: Mở trực tiếp hộp thoại Modal nhập liệu nộp đơn (nếu server có 1 băng thì popup ngay lập tức, nếu nhiều băng sẽ hiện menu chọn băng rồi popup modal).
  - Bấm **`[📜 Xem Danh Sách Băng Mở Tuyển]`**: Menu thả xuống danh sách băng để chọn xem hồ sơ và bấm **`[📩 Nộp Đơn / Gia Nhập]`** chỉ với 1 click, không cần gõ bất kỳ câu lệnh nào.
  - Bấm **`[✨ Thành Lập Băng Mới]`**: Mở form đăng ký băng mới.
  - Bấm **`[🏆 Bảng Xếp Hạng Server]`**: Xem bảng vàng danh dự và chuyển đổi các tiêu chí (Cấp độ, Tuần, Sĩ số) bằng nút bấm.
- **Nếu đã có băng:**
  - **Hằng ngày:** Bấm **`[📅 Điểm Danh Hằng Ngày]`**, **`[🎯 Nhiệm Vụ Tuần]`**, **`[🏰 Hồ Sơ Băng Của Bạn]`**, hoặc **`[🚪 Rời Băng]`** (có xác nhận 2 lớp an toàn).
  - **Vinh danh & Nghệ thuật:** Bấm **`[📜 Cột Mốc Lịch Sử]`**, **`[🖼️ Ảnh Nền Băng (Full HD)]`**, **`[📜 Nhật Ký Băng]`**.
  - **Quản lý & Nhân sự (Cán Bộ / Chủ Băng):** Bấm **`[👥 Quản Lý Thành Viên]`** (Mời qua menu chọn người, Thăng chức, Giáng chức, Trục xuất, Chuyển quyền Chủ Băng), **`[🎖️ Trao Danh Hiệu]`**, **`[⚙️ Cài Đặt Băng]`**, **`[🛡️ Cài Đặt Role]`**.

### 🧹 Cơ Chế Tự Động Dọn Dẹp & Chống Đầy Chat (Auto-Dismiss & In-Place Navigation)
- **Điều Hướng Tại Chỗ (In-Place Edit):** Khi bấm vào các mục con (Hồ sơ, Nhiệm vụ, Cột mốc, Cài đặt, Bảng xếp hạng...), bot sẽ biến đổi trực tiếp trên cùng một tin nhắn, **không spam thêm tin nhắn mới** làm trôi chat.
- **Tự Động Thu Hồi Bảng Cũ (Auto-Dismiss):** Khi bạn dùng một lệnh khác hoặc mở tính năng mới, bot sẽ tự động xóa/dismiss bảng điều khiển trước đó để màn hình luôn gọn gàng.
- **Nút `[🏠 Quay Lại Hub]` & `[🗑️ Đóng Bảng]`:** Tích hợp sẵn trên mọi giao diện để bạn quay về trang chính hoặc đóng bảng ngay lập tức khi hoàn thành thao tác.
- **Thông Báo Tự Biến Mất:** Các thông báo trạng thái nhỏ (điểm danh thành công, cảnh báo thiếu quyền...) sẽ tự động biến mất sau 5-6 giây.

---

## 👤 PHẦN 1: DÀNH CHO THÀNH VIÊN & NGƯỜI CHƠI (GAMERS)

### 1. Cách Tìm Băng & Xin Gia Nhập (1-Click)
- **Xem danh sách & xin gia nhập ngay:** Bấm nút **`[📜 Xem Danh Sách Băng Mở Tuyển]`** trong `/clan hub` (hoặc gõ `/clan list`).
  - **Nộp đơn siêu tốc:** Bấm nút **`[📩 Nộp Đơn Vào Băng]`** ngay dưới danh sách, Modal điền đơn sẽ hiện ra ngay lập tức!
  - **Hoặc chọn từ Menu:** Chọn băng bạn quan tâm từ Menu thả xuống để xem hồ sơ chi tiết cùng nút **`[📩 Nộp Đơn / Gia Nhập]`** và **`[👥 Xem Thành Viên]`**!
- **Nếu được mời vào băng:** Khi Cán Bộ mời bạn, tin nhắn mời sẽ hiện ra kèm nút **`[✅ Chấp Nhận Lời Mời]`** màu xanh — bấm 1 cái là vào ngay!

### 2. Điểm Danh Nhận Thưởng Hằng Ngày
- Bấm nút **`[📅 Điểm Danh Hằng Ngày]`** trong `/clan hub` (hoặc gõ `/clan checkin`).
- Mỗi ngày nhận ngay **+10 Điểm cống hiến cá nhân** và đóng góp **+30 EXP** cho băng.
- **Chuỗi liên tiếp (Streak):** Điểm danh đều đặn 7 ngày liên tiếp được thưởng thêm **+50 EXP**! *(Reset lúc 00:00 hằng ngày theo giờ Việt Nam)*.

### 3. Cày Nhiệm Vụ Tuần Đồng Đội (Weekly Quests)
- Bấm nút **`[🎯 Nhiệm Vụ Tuần]`** trong `/clan hub` (hoặc gõ `/clan quests`) để theo dõi:
  1. **📅 Điểm Danh Đồng Đội:** Đạt đủ tổng số 35 lượt check-in của cả băng trong tuần (+350 EXP).
  2. **🎙️ Voice Co-op Chơi Game:** Cùng ngồi kênh Voice buôn chuyện / nghe nhạc / treo máy cùng nhau từ 2 người trở lên (+500 EXP khi đạt 300 phút). Mute hay deafen nghe nhạc vẫn tính điểm bình thường!
  3. **💬 Sôi Nổi Kênh Chat:** Tương tác, trò chuyện trong kênh chat riêng của băng (+300 EXP khi đạt 100 tin nhắn).
- Hoàn thành mỗi nhiệm vụ thưởng thẳng từ **+300 đến +500 EXP** cho băng *(Tự động làm mới vào 00:00 Thứ Hai hằng tuần)*.

### 4. Rời Băng Tự Do (Không Bị Timeout / Cooldown)
- Bấm nút **`[🚪 Rời Băng]`** màu đỏ trong `/clan hub` (hoặc gõ `/clan leave`).
- Bot sẽ mở hộp thoại xác nhận 2 lớp để tránh bấm nhầm.
- ✨ **Tự do tuyệt đối:** Bạn hoàn toàn không bị áp dụng thời gian chờ (cooldown/timeout) sau khi rời băng, có thể thoải mái tạo băng mới hoặc nộp đơn vào băng khác ngay lập tức!

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

### 6. Bổ Nhiệm & Quản Lý Nhân Sự (Nút `[👥 Quản Lý Thành Viên]` Trong `/clan hub`)
Bạn không cần phải nhớ các câu lệnh slash command phức tạp, chỉ cần bấm **`[👥 Quản Lý Thành Viên]`** trong `/clan hub`:
- **➕ Mời thành viên mới:** Menu chọn người dùng Discord (User Picker) trực quan, chọn ai là gửi ngay lời mời có nút xác nhận (hạn 15 phút).
- **⬆️ Thăng chức:** Bấm nút $\rightarrow$ Chọn thành viên từ menu thả xuống để thăng lên Cán Bộ hoặc Phó Băng.
- **⬇️ Giáng chức:** Bấm nút $\rightarrow$ Chọn cán bộ để hạ bậc chức vụ. *(Tối đa 2 Phó Băng và 4 Cán Bộ)*.
- **👢 Trục xuất:** Bấm nút $\rightarrow$ Chọn thành viên vi phạm $\rightarrow$ Nhập lý do trong popup để trục xuất (Bot sẽ gửi thông báo riêng qua DM kèm lý do cho thành viên, không phạt cooldown).
- **👑 Chuyển giao Chủ Băng:** Chỉ dành cho Chủ Băng, chọn người kế vị từ menu thả xuống và xác nhận an toàn 2 lớp.
- **💥 Giải Tán Băng:** Nút Giải Tán Băng (yêu cầu gõ chính xác tên băng trong Modal để xác nhận an toàn, tránh bấm nhầm).
*(Ngoài ra, bạn vẫn có thể dùng các lệnh `/clan invite`, `/clan promote`, `/clan demote`, `/clan kick`, `/clan transfer`, `/clan disband` nếu thích gõ lệnh)*.

### 7. Trao Danh Hiệu & Biệt Danh Nội Bộ: Nút `[🎖️ Trao Danh Hiệu]` trong `/clan hub`
- Cán Bộ, Phó Băng và Chủ Băng có thể trao tặng các danh hiệu/biệt danh độc đáo cho thành viên (Ví dụ: `Gánh Team 👑`, `Cú Đêm 🌙`, `Chúa Hề 🤡`, `Trùm Nấu Lẩu 🍲`...).
- **Cách dùng:** Mở `/clan hub` $\rightarrow$ bấm **`[🎖️ Trao Danh Hiệu]`** $\rightarrow$ chọn thành viên từ menu thả xuống $\rightarrow$ nhập danh hiệu mong muốn (hoặc để trống để gỡ).
- Danh hiệu sẽ xuất hiện kiêu hãnh trên **Bảng thành viên (`/clan members`)** và khắc ghi trang trọng trên **Ảnh Nền Wallpaper Full HD** của băng!

### 8. Biên Niên Sử & Xuất Ảnh Nền Wallpaper Full HD (1920x1080)
- **📜 Cột Mốc Lịch Sử:** Bấm **`[📜 Cột Mốc Lịch Sử]`** trong `/clan hub` để xem dòng thời gian ghi dấu các sự kiện trọng đại của băng (ngày thành lập, các mốc thăng cấp).
- **🖼️ Xuất Ảnh Nền Desktop Full HD:** Bấm **`[🖼️ Ảnh Nền Băng (Full HD)]`** trong `/clan hub`. Bot sẽ vẽ tự động tác phẩm Wallpaper 1920x1080 tuyệt đẹp mang biểu tượng, chỉ số, danh sách nòng cốt và biên niên sử của băng để anh em tải về làm hình nền máy tính!

### 9. Đồ Họa Mặc Định Siêu Lộng Lẫy (Tự Động Kiến Tạo Bằng Discord Framework)
- **Không lo thiếu ảnh:** Nếu Chủ Băng chưa tải ảnh tùy chỉnh lên, bot **hoàn toàn không sử dụng ảnh stock mạng chung chung** mà sẽ tự động vẽ đồ họa nhận diện thương hiệu riêng cho băng bằng Canvas Engine:
  - 🛡️ **Default Clan Logo (512x512):** Khiên Bát Giác Hoàng Gia (Royal Octagon Shield) mạ vàng, hào quang đa tầng neon theo màu chủ đạo của băng, vương miện hoàng gia, Tag băng phát sáng 3D và các hạt sao lấp lánh (Sparkles).
  - 🚩 **Default Clan Banner (1200x420 Widescreen):** Phong cách Cyber Gaming hiện đại với ma trận tổ ong lục giác, vệt sáng năng lượng, 4 góc bo kim loại, huy hiệu vương miện, 4 khối thông số glassmorphism và thanh tiến độ cấp độ rực rỡ.
- **Nút Xem Banner Tiện Lợi:** Bấm nút **`[🚩 Xem Banner Băng]`** trong `/clan info` hoặc khi duyệt danh sách băng để chiêm ngưỡng tác phẩm đồ họa của băng bất cứ lúc nào!

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

### 3. Chuẩn Hóa Tên Kênh Không Dấu & Cứu Hộ 1-Click: `/clan-admin sync`
- **Tên Kênh Tiếng Việt Không Dấu Chuẩn Discord:** Discord không cho phép dấu tiếng Việt trong tên kênh văn bản (các ký tự có dấu như `ó, đ, ê` trước đây bị Discord cắt thành dấu gạch nối rời rạc `💬・ngu-ch-i-n`). Bot đã loại bỏ tag trong tên kênh và chuyển đổi thành slug tên băng không dấu chuẩn gọn gàng (`💬・cho-dien`, `📜・nhat-ky-bang`).
- **Cứu Hộ & Tự Động Đổi Tên Kênh Cũ:** Khi Admin chạy lệnh `/clan-admin sync`:
  - Bot tự động quét và đổi tên các kênh chat bị lỗi gạch nối trước đây về tên tiếng Việt không dấu chuẩn đẹp.
  - Nếu ai đó lỡ tay xóa nhầm Role hoặc Kênh của một băng, bot sẽ **tự động tạo lại Role/Kênh bị thiếu**, gắn lại quyền chuẩn xác 100%!

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
