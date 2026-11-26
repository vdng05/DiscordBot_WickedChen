"""
Module Dynamic Canvas Image Generator dành cho Discord Clan Bot.
Tự động vẽ các thẻ đồ họa (Banners, Cards, Leaderboards, Quests) với độ phân giải cao,
khử răng cưa (anti-aliasing) bằng Pillow, tương thích 100% tiếng Việt UTF-8.
"""

import io
import math
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Danh sách font chữ hỗ trợ tiếng Việt trên Windows / Linux
FONT_BOLD_CANDIDATES = ["segoeuib.ttf", "arialbd.ttf", "tahomabd.ttf", "DejaVuSans-Bold.ttf"]
FONT_REGULAR_CANDIDATES = ["segoeui.ttf", "arial.ttf", "tahoma.ttf", "DejaVuSans.ttf"]


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Tải font chữ hệ thống hỗ trợ tiếng Việt mượt mà"""
    candidates = FONT_BOLD_CANDIDATES if bold else FONT_REGULAR_CANDIDATES
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass

    # Đường dẫn Linux phổ biến
    linux_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
    ]
    for path in linux_paths:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass

    return ImageFont.load_default()


def hex_to_rgb(hex_str: str, default: Tuple[int, int, int] = (88, 101, 242)) -> Tuple[int, int, int]:
    """Chuyển mã Hex (#RRGGBB) sang Tuple RGB"""
    if not hex_str:
        return default
    clean = hex_str.strip().lstrip("#")
    if len(clean) == 6:
        try:
            return (int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16))
        except ValueError:
            pass
    return default


def draw_gradient_background(
    width: int,
    height: int,
    start_rgb: Tuple[int, int, int],
    end_rgb: Tuple[int, int, int],
    horizontal: bool = False
) -> Image.Image:
    """Tạo ảnh nền chuyển sắc (Gradient) mượt mà"""
    base = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(base)

    if horizontal:
        for x in range(width):
            ratio = x / max(width - 1, 1)
            r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio)
            g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio)
            b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio)
            draw.line([(x, 0), (x, height)], fill=(r, g, b, 255))
    else:
        for y in range(height):
            ratio = y / max(height - 1, 1)
            r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio)
            g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio)
            b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    return base


def draw_progress_bar(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    progress: float,
    bg_color: Tuple[int, int, int, int] = (40, 44, 62, 255),
    fill_color: Tuple[int, int, int, int] = (88, 101, 242, 255),
    radius: int = 8
):
    """Vẽ thanh tiến trình bo góc mượt mà"""
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=radius, fill=bg_color)
    total_w = x2 - x1
    pct = max(0.0, min(1.0, progress))
    if pct > 0:
        fill_w = max(int(total_w * pct), radius * 2)
        draw.rounded_rectangle((x1, y1, x1 + fill_w, y2), radius=radius, fill=fill_color)


def draw_sparkle(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    size: int,
    color: Tuple[int, int, int, int] = (255, 235, 150, 255)
):
    """Vẽ hiệu ứng ngôi sao lấp lánh 4 cánh sang trọng (Glint / Sparkle)"""
    draw.line([(cx - size, cy), (cx + size, cy)], fill=color, width=2)
    draw.line([(cx, cy - size), (cx, cy + size)], fill=color, width=2)
    s2 = max(2, int(size * 0.45))
    draw.line([(cx - s2, cy - s2), (cx + s2, cy + s2)], fill=color, width=1)
    draw.line([(cx - s2, cy + s2), (cx + s2, cy - s2)], fill=color, width=1)
    draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=(255, 255, 255, 255))


def draw_emblem_crest(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    radius: int,
    tag: str,
    color_rgb: Tuple[int, int, int],
    sec_rgb: Tuple[int, int, int] = (255, 215, 0),
    level: int = 1,
    show_crown: bool = True
):
    """Vẽ huy hiệu / emblem hoàng gia lộng lẫy lên canvas với kích thước tùy biến"""
    # 1. Hào quang phát sáng tỏa tròn (Radial Glow)
    r1, r2 = int(radius * 1.15), int(radius * 0.95)
    draw.ellipse((cx - r1, cy - r1, cx + r1, cy + r1), fill=(*color_rgb, 35))
    draw.ellipse((cx - r2, cy - r2, cx + r2, cy + r2), fill=(*color_rgb, 60))

    # 2. Vành tròn kim loại ngoài
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(*sec_rgb, 170), width=2)

    # 3. Khiên Bát Giác Hoàng Gia (Royal Octagon)
    pts = [
        (cx, cy - radius),
        (cx + int(radius * 0.72), cy - int(radius * 0.72)),
        (cx + radius, cy),
        (cx + int(radius * 0.72), cy + int(radius * 0.72)),
        (cx, cy + radius),
        (cx - int(radius * 0.72), cy + int(radius * 0.72)),
        (cx - radius, cy),
        (cx - int(radius * 0.72), cy - int(radius * 0.72))
    ]
    draw.polygon(pts, fill=(16, 20, 36, 250), outline=(*color_rgb, 230))
    # Viền trong sắc nét
    in_r = int(radius * 0.88)
    in_pts = [
        (cx, cy - in_r),
        (cx + int(in_r * 0.72), cy - int(in_r * 0.72)),
        (cx + in_r, cy),
        (cx + int(in_r * 0.72), cy + int(in_r * 0.72)),
        (cx, cy + in_r),
        (cx - int(in_r * 0.72), cy + int(in_r * 0.72)),
        (cx - in_r, cy),
        (cx - int(in_r * 0.72), cy - int(in_r * 0.72))
    ]
    draw.line(in_pts + [in_pts[0]], fill=(*sec_rgb, 210), width=1)

    # 4. Vương miện trên đỉnh
    if show_crown:
        crown_size = max(14, int(radius * 0.28))
        draw.text((cx, cy - int(radius * 0.44)), "👑", fill=(255, 215, 0), font=get_font(crown_size), anchor="mm")

    # 5. Tag Băng phát sáng
    tag_str = (tag or "CLAN").upper()
    font_size = max(16, int(radius * (0.42 if len(tag_str) <= 4 else 0.32)))
    font_tag = get_font(font_size, bold=True)
    # Glow / Drop Shadow
    draw.text((cx + 1, cy + int(radius * 0.08)), tag_str, fill=(0, 0, 0, 220), font=font_tag, anchor="mm")
    draw.text((cx, cy + int(radius * 0.06)), tag_str, fill=(255, 255, 255), font=font_tag, anchor="mm")

    # 6. Mini Pill cấp độ ở chân huy hiệu
    pw = int(radius * 0.95)
    ph = max(14, int(radius * 0.24))
    py = cy + int(radius * 0.45)
    draw.rounded_rectangle((cx - pw // 2, py, cx + pw // 2, py + ph), radius=6, fill=(24, 30, 52, 240), outline=(*sec_rgb, 200), width=1)
    draw.text((cx, py + ph // 2), f"LV.{level}", fill=(255, 215, 0), font=get_font(max(10, int(ph * 0.65)), bold=True), anchor="mm")

    # 7. Sparkles
    sp_size = max(4, int(radius * 0.12))
    draw_sparkle(draw, cx, cy - radius, sp_size, (*sec_rgb, 255))
    draw_sparkle(draw, cx, cy + radius, sp_size, (*sec_rgb, 255))
    draw_sparkle(draw, cx - radius, cy, sp_size - 1, (*color_rgb, 255))
    draw_sparkle(draw, cx + radius, cy, sp_size - 1, (*color_rgb, 255))


def generate_default_clan_logo(clan: Dict[str, Any]) -> io.BytesIO:
    """Tạo Logo / Avatar Huy Hiệu Băng Đảng Mặc Định Cực Kỳ Lộng Lẫy (512 x 512)"""
    W, H = 512, 512
    cx, cy = W // 2, H // 2
    color_rgb = hex_to_rgb(clan.get("color_hex"), (88, 101, 242))
    sec_rgb = hex_to_rgb(clan.get("secondary_color_hex"), (255, 215, 0)) if clan.get("secondary_color_hex") else (255, 215, 0)

    # 1. Nền Canvas Dark Obsidian với gradient chuyển sắc huyền bí
    base = draw_gradient_background(W, H, (10, 12, 22), (22, 26, 44), horizontal=False)
    draw = ImageDraw.Draw(base)

    # 2. Vòng hào quang phát sáng đa lớp (Multi-layer Radial Glow)
    glow_layers = [(235, 12), (200, 25), (165, 45), (130, 70), (95, 100)]
    for r, a in glow_layers:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*color_rgb, a))

    # 3. Các tia hào quang ma thuật / công nghệ (Magic / Tech Radial Rays)
    for angle_deg in range(0, 360, 20):
        rad = math.radians(angle_deg)
        x1 = cx + int(145 * math.cos(rad))
        y1 = cy + int(145 * math.sin(rad))
        x2 = cx + int(205 * math.cos(rad))
        y2 = cy + int(205 * math.sin(rad))
        draw.line([(x1, y1), (x2, y2)], fill=(*color_rgb, 70), width=1)

    # 4. Vòng tròn thiên hà / La bàn phép thuật ngoài
    draw.ellipse((cx - 200, cy - 200, cx + 200, cy + 200), outline=(*sec_rgb, 140), width=2)
    draw.ellipse((cx - 180, cy - 180, cx + 180, cy + 180), outline=(*color_rgb, 180), width=1)

    # 5. Khiên huy hiệu trung tâm hình Bát Giác Hoàng Gia (Royal Octagon Shield)
    shield_pts = [
        (cx, cy - 195),
        (cx + 140, cy - 135),
        (cx + 195, cy),
        (cx + 140, cy + 135),
        (cx, cy + 195),
        (cx - 140, cy + 135),
        (cx - 195, cy),
        (cx - 140, cy - 135)
    ]
    draw.polygon(shield_pts, fill=(16, 20, 34, 250), outline=(*color_rgb, 240))
    # Viền trong mạ vàng
    inner_shield_pts = [
        (cx, cy - 183),
        (cx + 130, cy - 127),
        (cx + 183, cy),
        (cx + 130, cy + 127),
        (cx, cy + 183),
        (cx - 130, cy + 127),
        (cx - 183, cy),
        (cx - 130, cy - 127)
    ]
    draw.line(inner_shield_pts + [inner_shield_pts[0]], fill=(*sec_rgb, 230), width=2)

    # 6. Biểu tượng Vương Miện / Ngôi Sao danh vọng trên đỉnh
    draw.text((cx, cy - 75), "👑", fill=(255, 215, 0), font=get_font(42), anchor="mm")

    # 7. Tag Băng Đảng phát sáng ở chính giữa
    tag_text = clan.get("tag", "CLAN").upper()
    font_tag = get_font(52 if len(tag_text) <= 4 else 42, bold=True)
    # Neon outer glow
    for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
        draw.text((cx + ox, cy + 8 + oy), tag_text, fill=(*color_rgb, 200), font=font_tag, anchor="mm")
    # Drop shadow
    draw.text((cx + 2, cy + 11), tag_text, fill=(0, 0, 0, 230), font=font_tag, anchor="mm")
    # Main foreground
    draw.text((cx, cy + 8), tag_text, fill=(255, 255, 255), font=font_tag, anchor="mm")

    # 8. Dải ruy băng / Pill Cấp Độ & Tên Băng ở phía dưới
    from utils.embeds import get_level_info
    lvl_info = get_level_info(clan.get("exp", 0))
    pill_box = (cx - 130, cy + 78, cx + 130, cy + 118)
    draw.rounded_rectangle(pill_box, radius=12, fill=(24, 30, 52, 240), outline=(*sec_rgb, 220), width=2)
    lvl_str = f"LV.{clan.get('level', 1)} • {lvl_info['title']}"
    draw.text((cx, cy + 97), lvl_str, fill=(255, 215, 0), font=get_font(12, bold=True), anchor="mm")

    # Tên Băng trang trọng phía dưới ruy băng
    name_str = f"★ {clan.get('name', 'Băng Đảng')[:18]} ★"
    draw.text((cx, cy + 145), name_str, fill=(220, 230, 250), font=get_font(15, bold=True), anchor="mm")

    # 9. Các hạt lấp lánh tỏa sáng (Sparkle Highlights)
    draw_sparkle(draw, cx, cy - 195, 16, (*sec_rgb, 255))
    draw_sparkle(draw, cx, cy + 195, 14, (*sec_rgb, 255))
    draw_sparkle(draw, cx - 195, cy, 14, (*color_rgb, 255))
    draw_sparkle(draw, cx + 195, cy, 14, (*color_rgb, 255))
    draw_sparkle(draw, cx - 140, cy - 135, 10, (255, 255, 255, 255))
    draw_sparkle(draw, cx + 140, cy - 135, 10, (255, 255, 255, 255))

    buf = io.BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf


def generate_default_clan_banner(clan: Dict[str, Any], member_count: int = 1) -> io.BytesIO:
    """Tạo Banner Header Băng Đảng Mặc Định Siêu Đẹp (1200 x 420)"""
    W, H = 1200, 420
    color_rgb = hex_to_rgb(clan.get("color_hex"), (88, 101, 242))
    sec_rgb = hex_to_rgb(clan.get("secondary_color_hex"), (255, 215, 0)) if clan.get("secondary_color_hex") else (255, 215, 0)

    # 1. Background gradient vũ trụ sâu thẳm
    base = draw_gradient_background(W, H, (10, 12, 22), (24, 20, 45), horizontal=True)
    draw = ImageDraw.Draw(base)

    # 2. Họa tiết lục giác ma trận Cybernetic (Hex Pattern) ở nửa bên phải
    hex_r = 30
    for hx in range(450, W, 70):
        for hy in range(30, H, 60):
            pts = [
                (hx + int(hex_r * math.cos(math.radians(a))), hy + int(hex_r * math.sin(math.radians(a))))
                for a in range(30, 390, 60)
            ]
            draw.polygon(pts, fill=None, outline=(*color_rgb, 25))

    # 3. Dải sáng vát chéo Cyber Streak
    draw.polygon([(460, 0), (520, 0), (320, H), (260, H)], fill=(*color_rgb, 35))
    draw.line([(520, 0), (320, H)], fill=(*sec_rgb, 100), width=2)

    # 4. Viền khung công nghệ với 4 góc bo kim loại
    draw.rounded_rectangle((16, 16, W - 16, H - 16), radius=20, outline=(*color_rgb, 180), width=2)
    draw.rounded_rectangle((22, 22, W - 22, H - 22), radius=16, outline=(255, 255, 255, 20), width=1)

    # Corner brackets (Góc kim loại)
    c_len = 35
    for bx, by, dx, dy in [(22, 22, 1, 1), (W - 22, 22, -1, 1), (22, H - 22, 1, -1), (W - 22, H - 22, -1, -1)]:
        draw.line([(bx, by), (bx + dx * c_len, by)], fill=sec_rgb, width=3)
        draw.line([(bx, by), (bx, by + dy * c_len)], fill=sec_rgb, width=3)

    # 5. Huy hiệu bên trái (Left Emblem Crest - Center x=180, y=210)
    draw_emblem_crest(draw, cx=180, cy=210, radius=115, tag=clan.get("tag", "CLAN"), color_rgb=color_rgb, sec_rgb=sec_rgb, level=clan.get("level", 1), show_crown=True)

    # 6. Thông tin chi tiết bên phải (Right Content Area)
    tx = 360
    draw.rounded_rectangle((tx, 45, tx + 330, 75), radius=8, fill=(28, 34, 56, 230), outline=(*sec_rgb, 160), width=1)
    draw.text((tx + 14, 52), "★ OFFICIAL CLAN • DISCORD GAMING ECOSYSTEM ★", fill=(255, 215, 0), font=get_font(11, bold=True))

    # Tên Băng siêu to lộng lẫy
    font_name = get_font(42, bold=True)
    name_str = f"[{clan.get('tag', 'CLAN')}] {clan.get('name', 'Băng Đảng')}"
    draw.text((tx + 2, 88), name_str, fill=(*color_rgb, 200), font=font_name)
    draw.text((tx, 86), name_str, fill=(255, 255, 255), font=font_name)

    # Slogan
    slogan = clan.get("description") or "Chưa có khẩu hiệu băng."
    draw.text((tx, 142), f"\"{slogan[:75]}\"", fill=(185, 200, 225), font=get_font(16, bold=False))

    # 4 Khối thông số (Pills)
    from utils.embeds import get_level_info
    lvl_info = get_level_info(clan.get("exp", 0))
    from utils.constants import JoinModes
    mode_name = JoinModes.NAMES.get(clan.get("join_mode"), "🟡 Cần Duyệt")
    pills = [
        ("👑 CHỦ BĂNG", f"<ID: {clan.get('leader_id')}>", (255, 215, 0)),
        ("👥 THÀNH VIÊN", f"{member_count}/{lvl_info['max_members']} Người", (100, 220, 255)),
        ("🚪 TUYỂN QUÂN", mode_name, (130, 230, 170)),
        ("🏆 EXP TÍCH LŨY", f"{clan.get('exp', 0):,} EXP", (255, 130, 180))
    ]
    py = 185
    pw = 185
    ph = 52
    for i, (plbl, pval, pcol) in enumerate(pills):
        px = tx + i * (pw + 14)
        draw.rounded_rectangle((px, py, px + pw, py + ph), radius=10, fill=(26, 32, 52, 230), outline=(*pcol, 130), width=1)
        draw.text((px + 12, py + 8), plbl, fill=pcol, font=get_font(11, bold=True))
        draw.text((px + 12, py + 26), pval, fill=(255, 255, 255), font=get_font(13, bold=True))

    # 7. Thanh tiến trình EXP ở phía dưới
    progress = lvl_info["ratio"]
    pct_display = int(progress * 100)
    draw.text((tx, 260), f"TIẾN ĐỘ THĂNG CẤP: {clan.get('exp', 0):,} / {lvl_info['next_req']:,} EXP ({pct_display}%)", fill=(210, 220, 240), font=get_font(13, bold=True))
    draw_progress_bar(draw, (tx, 285, W - 45, 305), progress, bg_color=(26, 32, 52, 255), fill_color=(*color_rgb, 255), radius=10)

    # Dòng footer
    draw.text((tx, 335), f"✨ ID Băng: {clan.get('clan_id')} • Ngày thành lập: Khởi lập vẻ vang trên server", fill=(140, 155, 185), font=get_font(13, bold=False))

    # Sparkles
    draw_sparkle(draw, W - 60, 45, 14, (*sec_rgb, 255))
    draw_sparkle(draw, tx + 400, 95, 10, (255, 255, 255, 255))

    buf = io.BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf


# =============================================================================
# 1. THẺ TRUNG TÂM ĐIỀU KHIỂN (CLAN HUB BANNER CARD)
# =============================================================================
def generate_clan_hub_image(
    clan: Optional[Dict[str, Any]],
    user_name: str,
    member_count: int = 0
) -> io.BytesIO:
    """Vẽ thẻ đồ họa Clan Hub phong cách Cyber / Esports Banner (920 x 300)"""
    W, H = 920, 300
    color_rgb = hex_to_rgb(clan.get("color_hex") if clan else None, (88, 101, 242))

    # Tạo nền chuyển sắc sang trọng deep navy
    base = draw_gradient_background(W, H, (15, 17, 28), (24, 28, 48), horizontal=True)
    draw = ImageDraw.Draw(base)

    # Khung bo viền ngoài với accent phát sáng nhẹ
    draw.rounded_rectangle((10, 10, W - 10, H - 10), radius=20, outline=(*color_rgb, 200), width=3)
    draw.rounded_rectangle((14, 14, W - 14, H - 14), radius=18, outline=(255, 255, 255, 25), width=1)

    if clan:
        clan_name = clan.get("name", "Băng Đảng")
        clan_tag = clan.get("tag", "CLAN")
        level = clan.get("level", 1)
        exp = clan.get("exp", 0)
        slogan = clan.get("description") or "Chưa có khẩu hiệu băng."

        from utils.embeds import get_level_info
        lvl_info = get_level_info(exp)
        next_exp = lvl_info["next_req"]
        cur_lvl_req = lvl_info["cur_req"]
        progress = lvl_info["ratio"]
        pct_display = int(progress * 100)

        # 1. Badge Emblem bên trái lộng lẫy
        sec_rgb = hex_to_rgb(clan.get("secondary_color_hex"), (255, 215, 0)) if clan.get("secondary_color_hex") else (255, 215, 0)
        draw_emblem_crest(draw, cx=105, cy=115, radius=68, tag=clan_tag, color_rgb=color_rgb, sec_rgb=sec_rgb, level=level, show_crown=True)

        # 2. Header & Tên Băng
        font_sub = get_font(14, bold=True)
        draw.text((200, 48), "🏰 TRUNG TÂM ĐIỀU KHIỂN BĂNG ĐẢNG", fill=(*color_rgb, 255), font=font_sub)

        font_title = get_font(34, bold=True)
        draw.text((200, 75), f"[{clan_tag}] {clan_name}", fill=(255, 255, 255), font=font_title)

        font_slogan = get_font(15, bold=False)
        clean_slogan = f"\"{slogan[:65]}...\"" if len(slogan) > 65 else f"\"{slogan}\""
        draw.text((200, 122), clean_slogan, fill=(180, 190, 210), font=font_slogan)

        # 3. 3 Khối Thống Kê (Pill Boxes)
        pills = [
            ("⭐ CẤP ĐỘ", f"Lv.{level} ({lvl_info['title']})", (255, 204, 0)),
            ("👥 SĨ SỐ", f"{member_count}/{lvl_info['max_members']} Thành Viên", (100, 220, 255)),
            ("🔥 STREAK", f"{clan.get('checkin_streak', 0)} Ngày Liên Tiếp", (255, 100, 130))
        ]
        start_x = 200
        pill_w = 210
        pill_h = 44
        pill_y = 155
        for i, (label, val, tint) in enumerate(pills):
            px = start_x + i * (pill_w + 15)
            draw.rounded_rectangle((px, pill_y, px + pill_w, pill_y + pill_h), radius=10, fill=(30, 35, 55, 240), outline=(*tint, 140), width=1)
            draw.text((px + 12, pill_y + 12), label, fill=tint, font=get_font(11, bold=True))
            draw.text((px + 12, pill_y + 26), val, fill=(255, 255, 255), font=get_font(13, bold=True))

        # 4. Thanh tiến trình EXP ở cạnh dưới
        bar_box = (35, 235, W - 35, 255)
        draw_progress_bar(draw, bar_box, progress, bg_color=(30, 35, 55, 255), fill_color=(*color_rgb, 255), radius=10)
        font_bar = get_font(13, bold=True)
        bar_text = f"TIẾN ĐỘ THĂNG CẤP: {exp:,} / {next_exp:,} EXP ({pct_display}%)"
        draw.text((45, 218), bar_text, fill=(210, 220, 240), font=font_bar)

    else:
        # Trường hợp thành viên chưa có băng
        font_hdr = get_font(16, bold=True)
        draw.text((W // 2, 55), "🏰 HỆ THỐNG LIÊN MINH & BĂNG ĐẢNG SERVER", fill=(88, 101, 242), font=font_hdr, anchor="mm")

        font_name = get_font(32, bold=True)
        draw.text((W // 2, 98), f"Xin chào, {user_name}!", fill=(255, 255, 255), font=font_name, anchor="mm")

        font_desc = get_font(16, bold=False)
        draw.text((W // 2, 145), "Bạn hiện chưa gia nhập bất kỳ băng đảng nào trong máy chủ.", fill=(180, 195, 220), font=font_desc, anchor="mm")

        # Khung hành động nhanh
        action_box = (120, 185, W - 120, 255)
        draw.rounded_rectangle(action_box, radius=14, fill=(30, 36, 60, 220), outline=(88, 101, 242, 180), width=2)
        font_action = get_font(15, bold=True)
        draw.text((W // 2, 220), "👉 Bấm các nút bên dưới để Khám Phá Danh Sách Băng hoặc Thành Lập Băng Mới!", fill=(100, 230, 180), font=font_action, anchor="mm")

    buf = io.BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf


# =============================================================================
# 2. THẺ BẢNG XẾP HẠNG (LEADERBOARD BANNER CARD)
# =============================================================================
def generate_leaderboard_image(
    guild_name: str,
    clans: List[Dict[str, Any]],
    criteria: str = "level"
) -> io.BytesIO:
    """Vẽ bảng xếp hạng Esports Tournament (920 x 520)"""
    W, H = 920, 520
    base = draw_gradient_background(W, H, (14, 16, 26), (22, 25, 42), horizontal=False)
    draw = ImageDraw.Draw(base)

    # Viền ngoài
    draw.rounded_rectangle((10, 10, W - 10, H - 10), radius=20, outline=(255, 204, 0, 180), width=2)

    # Tiêu đề
    criteria_name = "Cấp Độ & Tổng EXP" if criteria == "level" else "Năng Động Trong Tuần"
    font_title = get_font(26, bold=True)
    draw.text((40, 35), "🏆 BẢNG VINH DANH BĂNG ĐẢNG XUẤT SẮC", fill=(255, 215, 0), font=font_title)
    font_sub = get_font(14, bold=False)
    draw.text((40, 68), f"Máy chủ: {guild_name}  •  Tiêu chí xếp hạng: {criteria_name}", fill=(170, 180, 205), font=font_sub)

    # PODIUM TOP 3 (Cột bên trái)
    top1 = clans[0] if len(clans) > 0 else None
    top2 = clans[1] if len(clans) > 1 else None
    top3 = clans[2] if len(clans) > 2 else None

    podium_items = [
        (top1, "👑 QUÁN QUÂN (TOP 1)", (255, 215, 0), (50, 42, 18), 105, 110),
        (top2, "🥈 Á QUÂN (TOP 2)", (200, 210, 230), (32, 36, 48), 225, 88),
        (top3, "🥉 QUÝ QUÂN (TOP 3)", (215, 130, 70), (40, 30, 25), 325, 88),
    ]

    for clan_data, rank_title, border_c, bg_c, py, ph in podium_items:
        pbox = (40, py, 450, py + ph)
        draw.rounded_rectangle(pbox, radius=12, fill=(*bg_c, 240), outline=(*border_c, 220), width=2)
        if clan_data:
            c_tag = clan_data.get("tag", "CLAN")
            c_name = clan_data.get("name", "Băng")
            disp_name = c_name[:18] + "..." if len(c_name) > 18 else c_name
            c_lvl = clan_data.get("level", 1)
            c_exp = clan_data.get("exp", 0) if criteria == "level" else clan_data.get("weekly_exp", 0)

            draw.text((55, py + 12), rank_title, fill=border_c, font=get_font(12, bold=True))
            draw.text((55, py + 30), f"[{c_tag}] {disp_name}", fill=(255, 255, 255), font=get_font(19, bold=True))
            stat_text = f"⭐ Cấp {c_lvl}  •  {c_exp:,} EXP"
            draw.text((55, py + 56), stat_text, fill=(200, 215, 235), font=get_font(13, bold=False))
        else:
            draw.text((55, py + 12), rank_title, fill=border_c, font=get_font(12, bold=True))
            draw.text((55, py + 36), "Đang chờ băng kế tiếp...", fill=(120, 130, 150), font=get_font(15, bold=False))

    # BẢNG HẠNG 4 ĐẾN 8 (Cột bên phải)
    rx = 480
    rw = 400
    table_box = (rx, 105, rx + rw, 435)
    draw.rounded_rectangle(table_box, radius=14, fill=(20, 24, 38, 240), outline=(50, 60, 90, 180), width=1)

    draw.text((rx + 20, 120), "BẢNG XẾP HẠNG TOP TIẾP THEO", fill=(100, 200, 255), font=get_font(13, bold=True))
    draw.line([(rx + 15, 142), (rx + rw - 15, 142)], fill=(45, 55, 80), width=1)

    row_y = 155
    for rank_idx in range(4, 9):
        clan_idx = rank_idx - 1
        if clan_idx < len(clans):
            c = clans[clan_idx]
            tag_name = f"#{rank_idx}. [{c['tag']}] {c['name'][:16]}"
            c_exp = c.get("exp", 0) if criteria == "level" else c.get("weekly_exp", 0)
            sub_text = f"Lv.{c['level']} • {c_exp:,} EXP"
            draw.text((rx + 20, row_y), tag_name, fill=(255, 255, 255), font=get_font(14, bold=True))
            draw.text((rx + rw - 20, row_y), sub_text, fill=(160, 180, 210), font=get_font(13, bold=False), anchor="ra")
        else:
            draw.text((rx + 20, row_y), f"#{rank_idx}. ---", fill=(80, 90, 110), font=get_font(13, bold=False))

        row_y += 54

    buf = io.BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf


# =============================================================================
# 3. THẺ NHIỆM VỤ TUẦN (WEEKLY QUESTS BANNER CARD)
# =============================================================================
def generate_quests_image(
    clan: Dict[str, Any],
    quests: List[Dict[str, Any]],
    week_key: str
) -> io.BytesIO:
    """Vẽ bảng nhiệm vụ tuần hợp tác đồng đội (920 x 420)"""
    W, H = 920, 420
    base = draw_gradient_background(W, H, (16, 20, 34), (24, 28, 48), horizontal=False)
    draw = ImageDraw.Draw(base)

    # Viền ngoài phát sáng xanh cyan
    draw.rounded_rectangle((10, 10, W - 10, H - 10), radius=20, outline=(0, 242, 254, 180), width=2)

    # Header
    font_title = get_font(26, bold=True)
    draw.text((40, 32), "🎯 NHIỆM VỤ TUẦN HỢP TÁC ĐỒNG ĐỘI", fill=(0, 242, 254), font=font_title)
    font_sub = get_font(14, bold=False)
    draw.text((40, 65), f"Băng đảng: [{clan['tag']}] {clan['name']}  •  Chu kỳ: {week_key}", fill=(180, 195, 220), font=font_sub)

    # 3 Thẻ nhiệm vụ nằm ngang hoặc xếp tầng
    quest_config = {
        "CHECKIN_COUNT": ("📅 ĐIỂM DANH ĐỒNG ĐỘI", "Cả băng cùng điểm danh đủ số lượt trong tuần", (255, 204, 0)),
        "VOICE_MINUTES": ("🎙️ VOICE CO-OP CHƠI GAME", "Ngồi Voice chung từ 2 người trở lên", (100, 220, 255)),
        "CHAT_MESSAGES": ("💬 SÔI NỔI KÊNH CHAT", "Nhắn tin trò chuyện trong kênh chat riêng của băng", (255, 105, 180))
    }

    start_y = 100
    card_h = 90
    spacing = 15

    for i, q in enumerate(quests):
        q_type = q.get("quest_type")
        title, desc, color = quest_config.get(q_type, ("🎯 NHIỆM VỤ ĐỒNG ĐỘI", "", (88, 101, 242)))
        cur_v = q.get("current_value", 0)
        target_v = q.get("target_value", 1)
        reward = q.get("reward_exp", 0)
        completed = bool(q.get("completed", 0))

        progress = min(1.0, cur_v / max(1, target_v))
        cy = start_y + i * (card_h + spacing)
        card_box = (40, cy, W - 40, cy + card_h)

        # Hộp thẻ nhiệm vụ
        border_col = (46, 204, 113) if completed else color
        bg_col = (20, 35, 30) if completed else (26, 30, 48)
        draw.rounded_rectangle(card_box, radius=14, fill=(*bg_col, 240), outline=(*border_col, 180), width=2)

        # Tiêu đề & Mô tả
        draw.text((60, cy + 14), title, fill=border_col, font=get_font(15, bold=True))
        draw.text((60, cy + 34), desc, fill=(160, 175, 200), font=get_font(12, bold=False))

        # Thanh tiến trình
        bar_box = (60, cy + 56, W - 260, cy + 72)
        bar_fill = (46, 204, 113, 255) if completed else (*color, 255)
        draw_progress_bar(draw, bar_box, progress, bg_color=(36, 42, 65, 255), fill_color=bar_fill, radius=8)

        # Con số tiến độ
        pct = int(progress * 100)
        unit = "lượt" if "CHECKIN" in q_type else ("phút" if "VOICE" in q_type else "tin")
        prog_text = f"{cur_v:,} / {target_v:,} {unit} ({pct}%)"
        draw.text((W - 275, cy + 54), prog_text, fill=(220, 230, 250), font=get_font(13, bold=True), anchor="ra")

        # Cột trạng thái bên phải
        badge_box = (W - 230, cy + 20, W - 60, cy + 70)
        if completed:
            draw.rounded_rectangle(badge_box, radius=10, fill=(35, 75, 45, 255), outline=(46, 204, 113, 255), width=2)
            draw.text((W - 145, cy + 45), "HOÀN THÀNH ✅", fill=(46, 204, 113), font=get_font(13, bold=True), anchor="mm")
        else:
            draw.rounded_rectangle(badge_box, radius=10, fill=(35, 40, 60, 255), outline=(*color, 160), width=1)
            draw.text((W - 145, cy + 35), f"+{reward:,} EXP", fill=(255, 215, 0), font=get_font(14, bold=True), anchor="mm")
            draw.text((W - 145, cy + 54), "ĐANG DIỄN RA ⚡", fill=(170, 185, 210), font=get_font(10, bold=True), anchor="mm")

    buf = io.BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf


# =============================================================================
# 4. THẺ HỒ SƠ BĂNG (CLAN PROFILE CARD)
# =============================================================================
def generate_clan_profile_image(
    clan: Dict[str, Any],
    member_count: int,
    level_info: Dict[str, Any]
) -> io.BytesIO:
    """Vẽ thẻ hồ sơ băng đảng phong cách VIP Pass (920 x 320)"""
    W, H = 920, 320
    color_rgb = hex_to_rgb(clan.get("color_hex"), (88, 101, 242))
    sec_rgb = hex_to_rgb(clan.get("secondary_color_hex"), (221, 36, 118)) if clan.get("secondary_color_hex") else color_rgb

    base = draw_gradient_background(W, H, (16, 18, 30), (28, 32, 52), horizontal=True)
    draw = ImageDraw.Draw(base)

    # Viền gradient 2 màu nếu có
    draw.rounded_rectangle((10, 10, W - 10, H - 10), radius=20, outline=(*color_rgb, 220), width=3)

    # Biểu tượng Avatar Băng bên trái lộng lẫy
    draw_emblem_crest(draw, cx=105, cy=115, radius=68, tag=clan.get("tag", "CLAN"), color_rgb=color_rgb, sec_rgb=sec_rgb, level=clan.get("level", 1), show_crown=True)

    # Header Tên Băng
    font_name = get_font(34, bold=True)
    draw.text((200, 48), f"[{clan['tag']}] {clan['name']}", fill=(255, 255, 255), font=font_name)

    font_slogan = get_font(15, bold=False)
    slogan = clan.get("description") or "Chưa có khẩu hiệu băng."
    draw.text((200, 92), f"\"{slogan[:65]}\"", fill=(180, 190, 210), font=font_slogan)

    # Thông tin chi tiết
    join_mode_names = {
        "OPEN": "🟢 Mở Tự Do",
        "APPROVAL": "🟡 Cần Duyệt",
        "INVITE_ONLY": "🔒 Chỉ Nhận Lời Mời"
    }
    mode_text = join_mode_names.get(clan.get("join_mode"), "🟡 Cần Duyệt")

    info_pills = [
        ("👑 CHỦ BĂNG", f"<ID: {clan.get('leader_id')}>", (255, 204, 0)),
        ("👥 QUÂN SỐ", f"{member_count}/{level_info['max_members']} Người", (100, 220, 255)),
        ("🚪 TUYỂN QUÂN", mode_text, (130, 230, 170)),
        ("🏆 CẤP BĂNG", f"Cấp {clan['level']} ({level_info['title']})", (255, 130, 170))
    ]

    start_x = 200
    pill_w = 160
    pill_h = 44
    pill_y = 135
    for i, (lbl, val, col) in enumerate(info_pills):
        px = start_x + i * (pill_w + 14)
        draw.rounded_rectangle((px, pill_y, px + pill_w, pill_y + pill_h), radius=10, fill=(32, 38, 60, 240), outline=(*col, 130), width=1)
        draw.text((px + 10, pill_y + 11), lbl, fill=col, font=get_font(10, bold=True))
        draw.text((px + 10, pill_y + 25), val, fill=(255, 255, 255), font=get_font(12, bold=True))

    # Thanh EXP
    next_exp = level_info["next_req"]
    cur_exp = clan.get("exp", 0)
    progress = level_info["ratio"]
    pct_display = int(progress * 100)

    bar_box = (35, 245, W - 35, 265)
    draw_progress_bar(draw, bar_box, progress, bg_color=(30, 35, 55, 255), fill_color=(*color_rgb, 255), radius=10)
    font_bar = get_font(13, bold=True)
    draw.text((45, 225), f"KINH NGHIỆM: {cur_exp:,} / {next_exp:,} EXP ({pct_display}%)", fill=(210, 220, 240), font=font_bar)

    buf = io.BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf


# =============================================================================
# 5. THẺ PREVIEW ROLE SETUP (ROLE SETUP CARD)
# =============================================================================
def generate_role_setup_image(
    clan: Dict[str, Any],
    role_name: str,
    color_hex: str,
    secondary_color_hex: Optional[str] = None,
    hoist: bool = True,
    mentionable: bool = False
) -> io.BytesIO:
    """Vẽ thẻ xem trước trực quan hiệu ứng Role (920 x 280)"""
    W, H = 920, 280
    color_rgb = hex_to_rgb(color_hex, (88, 101, 242))
    sec_rgb = hex_to_rgb(secondary_color_hex, color_rgb) if secondary_color_hex else None

    base = draw_gradient_background(W, H, (16, 18, 30), (26, 30, 50), horizontal=True)
    draw = ImageDraw.Draw(base)

    draw.rounded_rectangle((10, 10, W - 10, H - 10), radius=20, outline=(*color_rgb, 200), width=2)

    # Tiêu đề
    draw.text((40, 30), "🛡️ TRUNG TÂM CÀI ĐẶT & XEM TRƯỚC ROLE BĂNG", fill=(255, 215, 0), font=get_font(24, bold=True))
    draw.text((40, 62), f"Băng đảng: [{clan['tag']}] {clan['name']}  •  Tùy biến quyền hạn & sắc màu", fill=(170, 185, 210), font=get_font(14, bold=False))

    # Hộp mô phỏng Role Pill của Discord
    pill_box = (40, 100, W - 40, 195)
    draw.rounded_rectangle(pill_box, radius=16, fill=(28, 33, 52, 255), outline=(55, 65, 95, 255), width=2)

    # Chấm tròn màu / gradient
    circle_center = (80, 147)
    circle_r = 18
    if sec_rgb:
        # Vẽ nửa hình tròn chuyển sắc hoặc viền gradient
        draw.ellipse((circle_center[0] - circle_r, circle_center[1] - circle_r, circle_center[0] + circle_r, circle_center[1] + circle_r), fill=color_rgb, outline=sec_rgb, width=4)
    else:
        draw.ellipse((circle_center[0] - circle_r, circle_center[1] - circle_r, circle_center[0] + circle_r, circle_center[1] + circle_r), fill=color_rgb)

    # Tên Role
    draw.text((115, 147), f"@{role_name}", fill=(255, 255, 255), font=get_font(24, bold=True), anchor="lm")

    # Thuộc tính bên phải của Role Pill
    col_desc = f"{color_hex} ➔ {secondary_color_hex} (Gradient 🌈)" if secondary_color_hex else f"{color_hex} (Đơn sắc 🎨)"
    draw.text((W - 65, 130), f"Màu sắc: {col_desc}", fill=(*color_rgb, 255), font=get_font(14, bold=True), anchor="ra")
    hoist_text = "Tách Nhóm (Hoist): BẬT ✅" if hoist else "Tách Nhóm (Hoist): TẮT ❌"
    draw.text((W - 65, 155), hoist_text, fill=(180, 220, 255), font=get_font(13, bold=False), anchor="ra")

    # Dòng chỉ dẫn phía dưới
    draw.text((W // 2, 235), "👉 Dùng menu bên dưới để chọn màu sẵn, nhập gradient 2 màu hoặc gán Role có sẵn trên Server!", fill=(140, 230, 190), font=get_font(13, bold=True), anchor="mm")

    buf = io.BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf


# =============================================================================
# 6. ẢNH NỀN DESKTOP KỶ NIỆM BĂNG ĐẢNG FULL HD (CLAN WALLPAPER 1920 x 1080)
# =============================================================================
def generate_clan_wallpaper(
    clan: Dict[str, Any],
    members: List[Dict[str, Any]],
    milestones: List[Dict[str, Any]]
) -> io.BytesIO:
    """Vẽ ảnh nền máy tính Full HD 1920x1080 kỷ niệm vẻ vang và dàn thành viên của Băng Đảng"""
    W, H = 1920, 1080
    color_rgb = hex_to_rgb(clan.get("color_hex"), (88, 101, 242))
    sec_rgb = hex_to_rgb(clan.get("secondary_color_hex"), (255, 105, 180)) if clan.get("secondary_color_hex") else color_rgb

    # 1. Background gradient vũ trụ sâu thẳm
    base = draw_gradient_background(W, H, (12, 14, 25), (22, 26, 44), horizontal=False)
    draw = ImageDraw.Draw(base)

    # Viền outer glow sang trọng
    draw.rounded_rectangle((20, 20, W - 20, H - 20), radius=28, outline=(*color_rgb, 200), width=3)
    draw.rounded_rectangle((26, 26, W - 26, H - 26), radius=24, outline=(255, 255, 255, 20), width=1)

    # 2. Header Emblem bên trái lộng lẫy
    draw_emblem_crest(draw, cx=180, cy=180, radius=95, tag=clan.get("tag", "CLAN"), color_rgb=color_rgb, sec_rgb=sec_rgb, level=clan.get("level", 1), show_crown=True)

    # 3. Tên Băng & Khẩu Hiệu
    draw.text((320, 95), "🏰 HỘI NHÓM & BĂNG ĐẢNG SERVER DISCORD", fill=sec_rgb, font=get_font(20, bold=True))
    draw.text((320, 125), f"[{clan['tag']}] {clan['name']}", fill=(255, 255, 255), font=get_font(52, bold=True))
    slogan = clan.get("description") or "Chưa có khẩu hiệu."
    draw.text((320, 195), f"\"{slogan[:80]}\"", fill=(180, 195, 225), font=get_font(22, bold=False))

    # Dãy chỉ số thống kê
    from utils.embeds import get_level_info
    lvl_info = get_level_info(clan.get("exp", 0))
    stats = [
        ("🏆 CẤP BĂNG", f"Cấp {clan.get('level', 1)} ({lvl_info['title']})", (255, 204, 0)),
        ("👥 QUÂN SỐ", f"{len(members)} / {lvl_info['max_members']} Thành Viên", (100, 220, 255)),
        ("⭐ TỔNG EXP", f"{clan.get('exp', 0):,} EXP", (255, 120, 180)),
        ("🔥 CHUỖI STREAK", f"{clan.get('checkin_streak', 0)} Ngày", (255, 150, 70))
    ]
    sx = 320
    for lbl, val, col in stats:
        draw.rounded_rectangle((sx, 240, sx + 250, 305), radius=12, fill=(28, 33, 54, 230), outline=(*col, 160), width=1)
        draw.text((sx + 15, 252), lbl, fill=col, font=get_font(12, bold=True))
        draw.text((sx + 15, 272), val, fill=(255, 255, 255), font=get_font(16, bold=True))
        sx += 265

    # 4. Box 1: Dàn Nhân Sự Cốt Cán (80, 340, 930, 990)
    p1 = (80, 340, 930, 990)
    draw.rounded_rectangle(p1, radius=20, fill=(20, 24, 38, 230), outline=(55, 65, 95, 200), width=2)
    draw.text((115, 365), "👑 DÀN NHÂN SỰ CỐT CÁN & THÀNH VIÊN", fill=(255, 215, 0), font=get_font(22, bold=True))
    draw.line([(115, 405), (895, 405)], fill=(45, 55, 80), width=1)

    rank_icons = {"LEADER": "👑 Chủ Băng", "CO_LEADER": "🥈 Phó Băng", "OFFICER": "🛡️ Cán Bộ", "MEMBER": "⚔️ Thành Viên"}
    my = 430
    for idx, m in enumerate(members[:8]):
        badge_rank = rank_icons.get(m.get("rank"), "⚔️ Thành Viên")
        uid_text = f"<ID: {m.get('user_id')}>"
        custom_t = f"【 {m['custom_title']} 】" if m.get("custom_title") else ""
        points = f"{m.get('contribution_points', 0):,} điểm cống hiến"

        draw.rounded_rectangle((115, my, 895, my + 54), radius=10, fill=(28, 34, 52, 200), outline=(50, 60, 85), width=1)
        draw.text((135, my + 14), f"{badge_rank} {uid_text}", fill=(255, 255, 255), font=get_font(16, bold=True))
        if custom_t:
            draw.text((500, my + 14), custom_t, fill=(255, 204, 0), font=get_font(15, bold=True))
        draw.text((875, my + 16), points, fill=(160, 180, 210), font=get_font(13, bold=False), anchor="ra")
        my += 68

    # 5. Box 2: Cột Mốc Lịch Sử (970, 340, 1840, 990)
    p2 = (970, 340, 1840, 990)
    draw.rounded_rectangle(p2, radius=20, fill=(20, 24, 38, 230), outline=(*sec_rgb, 180), width=2)
    draw.text((1005, 365), "📜 CỘT MỐC LỊCH SỬ & KỶ NIỆM ĐÁNG NHỚ", fill=sec_rgb, font=get_font(22, bold=True))
    draw.line([(1005, 405), (1805, 405)], fill=(45, 55, 80), width=1)

    import time
    if not milestones:
        draw.text((1405, 650), "Đang ghi nhận những chiến tích đầu tiên của Băng Đảng...", fill=(140, 150, 175), font=get_font(20, bold=False), anchor="mm")
    else:
        ty = 430
        for m_item in milestones[:7]:
            m_title = m_item.get("title", "Cột Mốc Mới")
            m_desc = m_item.get("description", "")
            achieved = m_item.get("achieved_at", int(time.time()))
            time_str = time.strftime("%d/%m/%Y %H:%M", time.localtime(achieved))

            draw.ellipse((1015, ty + 16, 1031, ty + 32), fill=sec_rgb)
            draw.text((1045, ty + 10), m_title, fill=(255, 255, 255), font=get_font(18, bold=True))
            draw.text((1805, ty + 12), time_str, fill=(150, 165, 190), font=get_font(13, bold=False), anchor="ra")
            if m_desc:
                draw.text((1045, ty + 34), m_desc[:65], fill=(180, 195, 220), font=get_font(14, bold=False))
            ty += 74

    # Watermark Footer
    draw.text((W // 2, 1030), "✨ WICKED CHEN CLAN ECOSYSTEM • DISCORD COMMUNITY WALLPAPER 1920x1080 ✨", fill=(120, 135, 165), font=get_font(14, bold=True), anchor="mm")

    buf = io.BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf
