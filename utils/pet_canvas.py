"""
Pillow Vector Hybrid Layered Canvas Renderer cho Hệ Thống Linh Thú Băng Đảng (Clan Pet).
Chuẩn 600x600 RGBA với 8 lớp Z-Index + Hệ tọa độ neo (Anchor System) + Smart MD5 Cache.
"""

import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from PIL import Image, ImageDraw

from config import Config
from utils.canvas import get_font, hex_to_rgb
from utils.constants import PET_ANCHORS, PET_SPECIES, get_pet_level_info
from utils.time_helper import get_vietnam_now

PET_CACHE_DIR = Config.DATA_DIR / "pet_cache"


def compute_pet_expression(hunger: int, mood: int, hour: Optional[int] = None) -> str:
    """Xác định biểu cảm thời gian thực theo Độ No, Độ Vui và giờ Việt Nam."""
    if hunger < 30:
        return "hungry"
    if hour is None:
        hour = get_vietnam_now().hour
    if 0 <= hour < 6:
        return "sleepy"
    if mood >= 70:
        return "happy"
    return "neutral"


def _blend(c1: Tuple[int, int, int], c2: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _draw_background(img: Image.Image, bg_id: Optional[str], c1: Tuple[int, int, int], c2: Tuple[int, int, int]):
    """Layer 0: Phông nền 600x600."""
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = img.size

    if bg_id == "bg_sunny_beach":
        top, bot = (48, 162, 235), (255, 214, 130)
    elif bg_id == "bg_sakura_night":
        top, bot = (22, 14, 42), (76, 30, 74)
    elif bg_id == "bg_royal_hall":
        top, bot = (34, 16, 48), (92, 54, 24)
    elif bg_id == "bg_cyber_grid":
        top, bot = (10, 14, 30), (20, 40, 74)
    else:
        top = _blend((16, 18, 32), c1, 0.28)
        bot = _blend((24, 28, 48), c2, 0.25)

    for y in range(h):
        col = _blend(top, bot, y / max(1, h - 1))
        draw.line([(0, y), (w, y)], fill=(*col, 255))

    if bg_id == "bg_cyber_grid":
        grid_col = (*c1, 55)
        for x in range(0, w, 40):
            draw.line([(x, 0), (x, h)], fill=grid_col, width=1)
        for y in range(0, h, 40):
            draw.line([(0, y), (w, y)], fill=grid_col, width=1)
    elif bg_id == "bg_sakura_night":
        for i in range(28):
            px = (i * 97 + 31) % w
            py = (i * 67 + 43) % (h - 120)
            draw.ellipse([px, py, px + 8, py + 5], fill=(255, 168, 204, 175))
    elif bg_id == "bg_sunny_beach":
        draw.ellipse([440, 50, 540, 150], fill=(255, 240, 140, 220))
        draw.rectangle([0, 410, w, h], fill=(242, 206, 138, 255))
        draw.rectangle([0, 360, w, 415], fill=(64, 196, 224, 210))
    elif bg_id == "bg_royal_hall":
        draw.polygon([(300, 40), (140, 430), (460, 430)], fill=(255, 215, 110, 35))
        draw.rectangle([0, 430, w, h], fill=(110, 24, 42, 220))
    else:
        # Sân đứng tối giản cho mặc định
        draw.ellipse([110, 410, 490, 475], fill=(0, 0, 0, 85))
        draw.ellipse([130, 415, 470, 468], outline=(*c1, 130), width=2)


def _paste_anchored(base: Image.Image, overlay: Image.Image, anchor: Tuple[int, int, float]):
    cx, cy, scale = anchor
    nw = max(1, int(overlay.width * scale))
    nh = max(1, int(overlay.height * scale))
    resized = overlay.resize((nw, nh), Image.Resampling.LANCZOS)
    base.alpha_composite(resized, (int(cx - nw / 2), int(cy - nh / 2)))


def _draw_aura_and_back(img: Image.Image, species: str, stage: int, equipped: dict, c1: Tuple[int, int, int], c2: Tuple[int, int, int]):
    """Layer 1: Hào quang Tối Thượng & Cánh / Katana đeo lưng."""
    anchors = PET_ANCHORS[species][stage]
    aura_id = equipped.get("aura")
    if stage >= 5 or aura_id:
        ax, ay, ascale = anchors["aura"]
        aura_layer = Image.new("RGBA", (420, 420), (0, 0, 0, 0))
        ad = ImageDraw.Draw(aura_layer, "RGBA")
        col_a = (255, 110, 40) if aura_id == "aura_dragon_flame" else c1
        col_b = (255, 215, 70) if aura_id == "aura_dragon_flame" else c2
        for r, alpha in ((185, 35), (145, 55), (110, 75)):
            ad.ellipse([210 - r, 210 - r, 210 + r, 210 + r], fill=(*col_a, alpha), outline=(*col_b, alpha + 45), width=3)
        for i in range(12):
            ang = math.radians(i * 30)
            px = 210 + int(math.cos(ang) * 165)
            py = 210 + int(math.sin(ang) * 165)
            ad.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(*col_b, 200))
        _paste_anchored(img, aura_layer, (ax, ay, ascale))

    back_id = equipped.get("back")
    if stage >= 4 and back_id:
        b_layer = Image.new("RGBA", (380, 260), (0, 0, 0, 0))
        bd = ImageDraw.Draw(b_layer, "RGBA")
        if back_id == "back_angel_wings":
            bd.polygon([(150, 120), (20, 30), (45, 145), (125, 165)], fill=(250, 250, 255, 235), outline=(190, 210, 240, 255), width=3)
            bd.polygon([(230, 120), (360, 30), (335, 145), (255, 165)], fill=(250, 250, 255, 235), outline=(190, 210, 240, 255), width=3)
        elif back_id == "back_cyber_wings":
            bd.polygon([(145, 115), (15, 45), (55, 145), (130, 150)], fill=(20, 32, 60, 235), outline=(0, 230, 255, 255), width=4)
            bd.polygon([(235, 115), (365, 45), (325, 145), (250, 150)], fill=(20, 32, 60, 235), outline=(255, 50, 190, 255), width=4)
        elif back_id == "back_katana":
            bd.line([(75, 215), (305, 35)], fill=(45, 45, 55, 255), width=12)
            bd.line([(275, 58), (305, 35)], fill=(220, 45, 65, 255), width=14)
            bd.ellipse([264, 48, 286, 70], fill=(245, 200, 65, 255))
        _paste_anchored(img, b_layer, anchors["back"])


def _draw_body(img: Image.Image, species: str, stage: int, level: int, c1: Tuple[int, int, int], c2: Tuple[int, int, int]):
    """Layer 2: Vẽ thân hình theo (species, stage) hoàn toàn bằng Pillow Vector."""
    draw = ImageDraw.Draw(img, "RGBA")
    outline = (22, 24, 34, 255)

    # Giai đoạn 1: Trứng Linh Thú
    if stage == 1:
        draw.ellipse([205, 175, 395, 415], fill=(*c1, 245), outline=outline, width=5)
        draw.arc([225, 225, 375, 330], start=15, end=165, fill=(*c2, 230), width=8)
        draw.ellipse([245, 205, 285, 245], fill=(255, 255, 255, 90))
        if level >= 3:
            # Vết nứt phát sáng từ Lv.3
            crack = [(290, 215), (312, 248), (288, 275), (318, 305), (298, 332)]
            draw.line(crack, fill=(255, 245, 160, 245), width=5)
        return

    # Các giai đoạn 2..5: Thân theo loài
    if species == "royal_slime":
        scale = {2: 0.78, 3: 0.90, 4: 1.0, 5: 1.08}[stage]
        rx, ry = int(108 * scale), int(92 * scale)
        cx, cy = 300, 325
        # Thân giọt nước mềm mại bán trong suốt
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(*c1, 215), outline=outline, width=4)
        draw.ellipse([cx - rx + 18, cy - ry + 16, cx + rx - 28, cy + 10], fill=(*c2, 125))
        draw.ellipse([cx - rx + 30, cy - ry + 24, cx - rx + 70, cy - ry + 54], fill=(255, 255, 255, 145))
        if stage >= 4:
            # Vương miện slime hoàng gia
            draw.polygon([(265, cy - ry + 6), (275, cy - ry - 26), (295, cy - ry - 6), (300, cy - ry - 34), (305, cy - ry - 6), (325, cy - ry - 26), (335, cy - ry + 6)], fill=(255, 210, 65, 255), outline=outline, width=3)
        return

    # Kích thước thân & đầu cho Mèo Cyber, Tiểu Long, Cáo Tinh
    head_r = {2: 68, 3: 72, 4: 74, 5: 76}[stage]
    head_cy = {2: 265, 3: 242, 4: 226, 5: 220}[stage]
    body_w = {2: 56, 3: 64, 4: 74, 5: 78}[stage]
    body_h = {2: 58, 3: 76, 4: 88, 5: 92}[stage]
    body_cy = head_cy + head_r + body_h - 24

    if species == "cyber_cat":
        body_col = (52, 62, 92, 255)
        accent = c1
        # Đuôi năng lượng neon
        tail_pts = [(300 + body_w - 8, body_cy + 20), (395, body_cy - 10), (425, body_cy - 65), (410, body_cy - 85)]
        draw.line(tail_pts, fill=(*accent, 255), width=12)
        draw.ellipse([398, body_cy - 98, 424, body_cy - 72], fill=(*c2, 255))
        # Thân & chân
        draw.rounded_rectangle([300 - body_w, body_cy - body_h, 300 + body_w, body_cy + body_h], radius=36, fill=body_col, outline=outline, width=4)
        draw.ellipse([268, body_cy - 34, 332, body_cy + 28], fill=(*accent, 180))
        # Tai nhọn
        draw.polygon([(238, head_cy - 32), (222, head_cy - head_r - 28), (275, head_cy - head_r + 12)], fill=body_col, outline=outline, width=4)
        draw.polygon([(362, head_cy - 32), (378, head_cy - head_r - 28), (325, head_cy - head_r + 12)], fill=body_col, outline=outline, width=4)
        draw.polygon([(242, head_cy - 42), (233, head_cy - head_r - 12), (266, head_cy - head_r + 14)], fill=(*accent, 235))
        draw.polygon([(358, head_cy - 42), (367, head_cy - head_r - 12), (334, head_cy - head_r + 14)], fill=(*accent, 235))
        # Đầu
        draw.ellipse([300 - head_r, head_cy - head_r, 300 + head_r, head_cy + head_r], fill=body_col, outline=outline, width=4)
        if stage >= 5:
            draw.arc([300 - head_r + 8, head_cy - head_r + 8, 300 + head_r - 8, head_cy + head_r - 8], start=200, end=340, fill=(*accent, 255), width=4)

    elif species == "mini_dragon":
        body_col = _blend((42, 128, 96), c1, 0.45)
        belly_col = (245, 218, 138, 255)
        # Đuôi rồng
        draw.polygon([(300 + body_w - 15, body_cy + 20), (425, body_cy + 35), (445, body_cy - 10), (300 + body_w - 10, body_cy - 8)], fill=(*body_col, 255), outline=outline, width=4)
        # Cánh nhỏ tự nhiên từ stage 3+
        if stage >= 3:
            w_span = 75 if stage == 3 else 110
            draw.polygon([(245, body_cy - 25), (245 - w_span, body_cy - 85), (245 - w_span + 20, body_cy + 10)], fill=(*c2, 230), outline=outline, width=3)
            draw.polygon([(355, body_cy - 25), (355 + w_span, body_cy - 85), (355 + w_span - 20, body_cy + 10)], fill=(*c2, 230), outline=outline, width=3)
        # Thân + bụng vảy
        draw.rounded_rectangle([300 - body_w, body_cy - body_h, 300 + body_w, body_cy + body_h], radius=38, fill=(*body_col, 255), outline=outline, width=4)
        draw.ellipse([300 - body_w + 18, body_cy - body_h + 18, 300 + body_w - 18, body_cy + body_h - 10], fill=belly_col)
        # Sừng
        horn_h = 26 if stage == 2 else 44
        draw.polygon([(256, head_cy - head_r + 18), (235, head_cy - head_r - horn_h), (275, head_cy - head_r + 6)], fill=(245, 200, 90, 255), outline=outline, width=3)
        draw.polygon([(344, head_cy - head_r + 18), (365, head_cy - head_r - horn_h), (325, head_cy - head_r + 6)], fill=(245, 200, 90, 255), outline=outline, width=3)
        # Đầu
        draw.ellipse([300 - head_r, head_cy - head_r, 300 + head_r, head_cy + head_r], fill=(*body_col, 255), outline=outline, width=4)

    else:
        # Cáo Tinh (Spirit Fox) — số đuôi tăng dần 1 -> 3 -> 5 đuôi
        fur_col = _blend((240, 128, 56), c1, 0.25)
        tail_count = 1 if stage <= 2 else (3 if stage <= 4 else 5)
        for ti in range(tail_count):
            ang = math.radians(-50 + (ti - (tail_count - 1) / 2) * 28)
            tx = 300 + int(math.sin(ang) * 145) + 35
            ty = body_cy - int(math.cos(ang) * 95) + 15
            draw.line([(300, body_cy + 15), (tx, ty)], fill=(*fur_col, 255), width=26)
            draw.ellipse([tx - 16, ty - 16, tx + 16, ty + 16], fill=(255, 245, 232, 255), outline=outline, width=2)
        # Thân + cổ lông xù
        draw.rounded_rectangle([300 - body_w, body_cy - body_h, 300 + body_w, body_cy + body_h], radius=38, fill=(*fur_col, 255), outline=outline, width=4)
        draw.ellipse([256, head_cy + head_r - 22, 344, head_cy + head_r + 34], fill=(255, 245, 232, 255), outline=outline, width=3)
        # Tai cáo
        draw.polygon([(236, head_cy - 30), (220, head_cy - head_r - 32), (274, head_cy - head_r + 12)], fill=(*fur_col, 255), outline=outline, width=4)
        draw.polygon([(364, head_cy - 30), (380, head_cy - head_r - 32), (326, head_cy - head_r + 12)], fill=(*fur_col, 255), outline=outline, width=4)
        # Đầu
        draw.ellipse([300 - head_r, head_cy - head_r, 300 + head_r, head_cy + head_r], fill=(*fur_col, 255), outline=outline, width=4)


def _draw_face(img: Image.Image, species: str, stage: int, expression: str):
    """Layer 3: Vẽ mắt & miệng theo biểu cảm thời gian thực."""
    if stage == 1:
        return
    draw = ImageDraw.Draw(img, "RGBA")
    cy = 320 if species == "royal_slime" else {2: 265, 3: 242, 4: 226, 5: 220}[stage]
    lx, rx = 270, 330

    if expression == "sleepy":
        draw.arc([lx - 14, cy - 8, lx + 14, cy + 12], start=0, end=180, fill=(20, 22, 30, 255), width=4)
        draw.arc([rx - 14, cy - 8, rx + 14, cy + 12], start=0, end=180, fill=(20, 22, 30, 255), width=4)
        draw.ellipse([292, cy + 18, 308, cy + 32], fill=(220, 95, 115, 255))
        font_z = get_font(22, bold=True)
        draw.text((370, cy - 55), "Zzz", font=font_z, fill=(210, 225, 255, 230))
    elif expression == "hungry":
        draw.line([(lx - 12, cy - 8), (lx + 10, cy + 2), (lx - 12, cy + 10)], fill=(20, 22, 30, 255), width=4)
        draw.line([(rx + 12, cy - 8), (rx - 10, cy + 2), (rx + 12, cy + 10)], fill=(20, 22, 30, 255), width=4)
        draw.arc([284, cy + 22, 316, cy + 38], start=180, end=360, fill=(20, 22, 30, 255), width=4)
    else:
        for ex in (lx, rx):
            draw.ellipse([ex - 13, cy - 13, ex + 13, cy + 13], fill=(20, 22, 30, 255))
            draw.ellipse([ex - 6, cy - 8, ex + 2, cy], fill=(255, 255, 255, 255))
        if expression == "happy":
            draw.ellipse([lx - 26, cy + 10, lx - 10, cy + 22], fill=(255, 130, 155, 165))
            draw.ellipse([rx + 10, cy + 10, rx + 26, cy + 22], fill=(255, 130, 155, 165))
            draw.arc([284, cy + 12, 316, cy + 32], start=0, end=180, fill=(20, 22, 30, 255), width=4)
        else:
            draw.line([(290, cy + 22), (310, cy + 22)], fill=(20, 22, 30, 255), width=4)


def _draw_outfit(img: Image.Image, species: str, stage: int, equipped: dict, c1: Tuple[int, int, int]):
    """Layer 4: Trang phục (mở từ Stage 3+)."""
    outfit_id = equipped.get("outfit")
    if stage < 3 or not outfit_id or species == "royal_slime":
        return
    o_layer = Image.new("RGBA", (180, 160), (0, 0, 0, 0))
    od = ImageDraw.Draw(o_layer, "RGBA")
    outline = (20, 22, 32, 255)
    if outfit_id == "outfit_hoodie":
        od.rounded_rectangle([24, 18, 156, 138], radius=28, fill=(42, 46, 62, 245), outline=outline, width=4)
        od.polygon([(60, 18), (90, 44), (120, 18)], fill=(*c1, 240))
    elif outfit_id == "outfit_cyber_armor":
        od.rounded_rectangle([20, 16, 160, 140], radius=22, fill=(24, 34, 58, 245), outline=(0, 230, 255, 255), width=4)
        od.rectangle([72, 44, 108, 76], fill=(0, 230, 255, 220))
    elif outfit_id == "outfit_royal_vest":
        od.rounded_rectangle([24, 16, 156, 138], radius=24, fill=(135, 24, 48, 245), outline=(245, 200, 75, 255), width=4)
        od.line([(90, 20), (90, 135)], fill=(245, 200, 75, 255), width=4)
    elif outfit_id == "outfit_cloud_robe":
        od.rounded_rectangle([22, 16, 158, 140], radius=24, fill=(28, 30, 44, 245), outline=(220, 60, 80, 255), width=4)
        od.ellipse([48, 56, 86, 84], fill=(220, 60, 80, 230))
        od.ellipse([96, 82, 134, 110], fill=(220, 60, 80, 230))
    elif outfit_id == "outfit_tanktop":
        od.rounded_rectangle([34, 22, 146, 134], radius=18, fill=(245, 245, 250, 240), outline=(65, 165, 245, 255), width=4)
    _paste_anchored(img, o_layer, PET_ANCHORS[species][stage]["outfit"])


def _draw_headwear(img: Image.Image, species: str, stage: int, equipped: dict):
    """Layer 5: Mũ / Đội đầu (mở từ Stage 2+)."""
    hat_id = equipped.get("headwear")
    if stage < 2 or not hat_id:
        return
    h_layer = Image.new("RGBA", (180, 120), (0, 0, 0, 0))
    hd = ImageDraw.Draw(h_layer, "RGBA")
    outline = (20, 22, 32, 255)
    if hat_id == "hat_cap_back":
        hd.pieslice([38, 28, 142, 108], start=180, end=360, fill=(225, 55, 70, 255), outline=outline, width=4)
        hd.rectangle([105, 58, 166, 72], fill=(30, 34, 46, 255), outline=outline, width=3)
    elif hat_id == "hat_gaming_headset":
        hd.arc([28, 18, 152, 112], start=185, end=355, fill=(38, 42, 58, 255), width=12)
        hd.rounded_rectangle([18, 56, 44, 102], radius=10, fill=(0, 225, 255, 255), outline=outline, width=3)
        hd.rounded_rectangle([136, 56, 162, 102], radius=10, fill=(255, 65, 185, 255), outline=outline, width=3)
    elif hat_id == "hat_gold_crown":
        hd.polygon([(40, 86), (48, 30), (74, 62), (90, 18), (106, 62), (132, 30), (140, 86)], fill=(255, 210, 65, 255), outline=outline, width=4)
        hd.ellipse([83, 52, 97, 66], fill=(230, 45, 75, 255))
    elif hat_id == "hat_ninja_band":
        hd.rectangle([28, 54, 152, 82], fill=(28, 34, 52, 255), outline=outline, width=3)
        hd.rectangle([64, 58, 116, 78], fill=(195, 205, 220, 255), outline=outline, width=2)
    elif hat_id == "hat_duck":
        hd.ellipse([44, 24, 136, 88], fill=(255, 222, 65, 255), outline=outline, width=4)
        hd.ellipse([70, 64, 110, 84], fill=(255, 140, 40, 255), outline=outline, width=3)
    _paste_anchored(img, h_layer, PET_ANCHORS[species][stage]["headwear"])


def _draw_face_and_held(img: Image.Image, species: str, stage: int, equipped: dict):
    """Layer 6: Kính / Phụ kiện mặt (Stage 3+) & Vật cầm tay (Stage 4+)."""
    face_id = equipped.get("face")
    if stage >= 3 and face_id:
        f_layer = Image.new("RGBA", (170, 80), (0, 0, 0, 0))
        fd = ImageDraw.Draw(f_layer, "RGBA")
        if face_id == "face_sunglasses":
            fd.rounded_rectangle([18, 18, 76, 52], radius=8, fill=(18, 20, 28, 245), outline=(245, 200, 75, 255), width=3)
            fd.rounded_rectangle([94, 18, 152, 52], radius=8, fill=(18, 20, 28, 245), outline=(245, 200, 75, 255), width=3)
            fd.line([(76, 30), (94, 30)], fill=(245, 200, 75, 255), width=4)
        elif face_id == "face_vr_visor":
            fd.rounded_rectangle([16, 16, 154, 56], radius=14, fill=(18, 24, 44, 235), outline=(0, 235, 255, 255), width=4)
            fd.line([(28, 36), (142, 36)], fill=(0, 235, 255, 220), width=4)
        elif face_id == "face_ninja_mask":
            fd.polygon([(30, 32), (140, 32), (126, 76), (44, 76)], fill=(28, 32, 46, 245), outline=(14, 16, 24, 255), width=3)
        elif face_id == "face_thug_life":
            fd.rectangle([20, 22, 74, 44], fill=(12, 12, 16, 255))
            fd.rectangle([96, 22, 150, 44], fill=(12, 12, 16, 255))
            fd.rectangle([74, 26, 96, 34], fill=(12, 12, 16, 255))
            fd.rectangle([30, 28, 44, 34], fill=(255, 255, 255, 255))
            fd.rectangle([106, 28, 120, 34], fill=(255, 255, 255, 255))
        _paste_anchored(img, f_layer, PET_ANCHORS[species][stage]["face"])

    held_id = equipped.get("held")
    if stage >= 4 and held_id:
        hl_layer = Image.new("RGBA", (110, 110), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hl_layer, "RGBA")
        outline = (20, 22, 32, 255)
        if held_id == "held_gamepad":
            hd.rounded_rectangle([12, 34, 98, 78], radius=16, fill=(32, 38, 56, 255), outline=(0, 225, 255, 255), width=3)
            hd.ellipse([24, 46, 40, 62], fill=(0, 225, 255, 255))
            hd.ellipse([68, 44, 80, 56], fill=(255, 70, 165, 255))
        elif held_id == "held_boba":
            hd.polygon([(34, 34), (76, 34), (68, 92), (42, 92)], fill=(245, 225, 195, 245), outline=outline, width=3)
            hd.line([(55, 10), (55, 34)], fill=(255, 90, 140, 255), width=5)
            for bx, by in ((46, 78), (55, 82), (63, 76)):
                hd.ellipse([bx - 4, by - 4, bx + 4, by + 4], fill=(30, 24, 24, 255))
        elif held_id == "held_scepter":
            hd.line([(55, 100), (55, 28)], fill=(245, 200, 75, 255), width=8)
            hd.ellipse([37, 10, 73, 46], fill=(90, 215, 255, 245), outline=(255, 240, 150, 255), width=3)
        _paste_anchored(img, hl_layer, PET_ANCHORS[species][stage]["held"])


def _draw_ui_overlay(img: Image.Image, pet: Dict[str, Any], stage_name: str, level: int, c1: Tuple[int, int, int]):
    """Layer 7: Tên Pet, khung Level và 2 thanh Độ No / Độ Vui."""
    draw = ImageDraw.Draw(img, "RGBA")
    font_title = get_font(24, bold=True)
    font_sub = get_font(17, bold=True)
    font_bar = get_font(15, bold=True)

    # Top header pill
    draw.rounded_rectangle([30, 20, 570, 82], radius=18, fill=(14, 16, 28, 195), outline=(*c1, 210), width=2)
    sp_emoji = PET_SPECIES.get(pet["species"], {}).get("name", pet["species"])
    draw.text((48, 28), f"{pet['name']} ({sp_emoji})", font=font_title, fill=(255, 255, 255, 255))
    draw.text((48, 56), f"Lv.{level} • {stage_name}", font=font_sub, fill=(255, 215, 110, 255))

    # Bottom status bars
    draw.rounded_rectangle([30, 502, 570, 578], radius=18, fill=(14, 16, 28, 200), outline=(*c1, 180), width=2)
    hunger = max(0, min(100, int(pet.get("hunger", 80))))
    mood = max(0, min(100, int(pet.get("mood", 80))))

    # Hunger bar
    draw.text((50, 514), f"Độ No: {hunger}%", font=font_bar, fill=(255, 210, 140, 255))
    draw.rounded_rectangle([50, 538, 280, 558], radius=8, fill=(42, 46, 62, 255))
    if hunger > 0:
        draw.rounded_rectangle([50, 538, 50 + int(230 * hunger / 100), 558], radius=8, fill=(245, 155, 55, 255))

    # Mood bar
    draw.text((318, 514), f"Độ Vui: {mood}%", font=font_bar, fill=(155, 235, 255, 255))
    draw.rounded_rectangle([318, 538, 550, 558], radius=8, fill=(42, 46, 62, 255))
    if mood > 0:
        draw.rounded_rectangle([318, 538, 318 + int(232 * mood / 100), 558], radius=8, fill=(75, 210, 155, 255))


def render_pet_sprite_only(pet: Dict[str, Any], clan_color: str = "#5865F2", secondary_color: Optional[str] = None, size: int = 240) -> Image.Image:
    """Render riêng nhân vật Pet nền trong suốt để ghép lên Wallpaper Full HD hoặc Hồ Sơ Băng."""
    c1 = hex_to_rgb(clan_color)
    c2 = hex_to_rgb(secondary_color) if secondary_color else _blend(c1, (255, 255, 255), 0.35)
    lvl_info = get_pet_level_info(int(pet.get("exp", 0)))
    stage = lvl_info["stage"]
    species = pet["species"]
    equipped = pet.get("equipped") or {}
    expr = compute_pet_expression(int(pet.get("hunger", 80)), int(pet.get("mood", 80)))

    canvas = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
    _draw_aura_and_back(canvas, species, stage, equipped, c1, c2)
    _draw_body(canvas, species, stage, lvl_info["level"], c1, c2)
    _draw_face(canvas, species, stage, expr)
    _draw_outfit(canvas, species, stage, equipped, c1)
    _draw_headwear(canvas, species, stage, equipped)
    _draw_face_and_held(canvas, species, stage, equipped)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def generate_clan_pet_image(pet: Dict[str, Any], clan: Dict[str, Any]) -> io.BytesIO:
    """Render ảnh Pet 600x600 RGBA với Smart MD5 Cache trong data/pet_cache/."""
    PET_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    clan_id = int(clan["clan_id"])
    c1_hex = clan.get("color_hex") or "#5865F2"
    c2_hex = clan.get("secondary_color_hex") or ""
    lvl_info = get_pet_level_info(int(pet.get("exp", 0)))
    stage = lvl_info["stage"]
    level = lvl_info["level"]
    species = pet["species"]
    equipped = pet.get("equipped") or {}
    hunger = int(pet.get("hunger", 80))
    mood = int(pet.get("mood", 80))
    expr = compute_pet_expression(hunger, mood)

    state_payload = json.dumps(
        {
            "s": species,
            "st": stage,
            "lv": level,
            "ex": expr,
            "eq": equipped,
            "c1": c1_hex,
            "c2": c2_hex,
            "n": pet.get("name"),
            "h": hunger,
            "m": mood,
        },
        sort_keys=True,
    )
    state_hash = hashlib.md5(state_payload.encode("utf-8")).hexdigest()[:12]
    cache_path = PET_CACHE_DIR / f"{clan_id}_{state_hash}.png"

    if cache_path.exists():
        return io.BytesIO(cache_path.read_bytes())

    # Xóa cache cũ của cùng clan_id để tránh phình ổ cứng VPS
    for old_file in PET_CACHE_DIR.glob(f"{clan_id}_*.png"):
        try:
            old_file.unlink()
        except Exception:
            pass

    c1 = hex_to_rgb(c1_hex)
    c2 = hex_to_rgb(c2_hex) if c2_hex else _blend(c1, (255, 255, 255), 0.35)

    img = Image.new("RGBA", (600, 600), (0, 0, 0, 255))
    _draw_background(img, equipped.get("background"), c1, c2)
    _draw_aura_and_back(img, species, stage, equipped, c1, c2)
    _draw_body(img, species, stage, level, c1, c2)
    _draw_face(img, species, stage, expr)
    _draw_outfit(img, species, stage, equipped, c1)
    _draw_headwear(img, species, stage, equipped)
    _draw_face_and_held(img, species, stage, equipped)
    _draw_ui_overlay(img, pet, lvl_info["stage_name"], level, c1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()
    try:
        cache_path.write_bytes(raw_bytes)
    except Exception:
        pass
    buf.seek(0)
    return buf


def generate_clan_pet_preview_image(pet: Dict[str, Any], clan: Dict[str, Any], preview_item: Dict[str, Any]) -> io.BytesIO:
    """Render ảnh xem trước vật phẩm trong Cửa Hàng trực tiếp lên Linh Thú (không ghi cache)."""
    c1_hex = clan.get("color_hex") or "#5865F2"
    c2_hex = clan.get("secondary_color_hex") or ""
    c1 = hex_to_rgb(c1_hex)
    c2 = hex_to_rgb(c2_hex) if c2_hex else _blend(c1, (255, 255, 255), 0.35)

    lvl_info = get_pet_level_info(int(pet.get("exp", 0)))
    cur_stage = lvl_info["stage"]
    preview_stage = max(cur_stage, int(preview_item.get("min_stage", 1)))
    level = lvl_info["level"]
    species = pet["species"]
    equipped = dict(pet.get("equipped") or {})
    equipped[preview_item["slot"]] = preview_item["item_id"]

    hunger = int(pet.get("hunger", 80))
    mood = int(pet.get("mood", 80))
    expr = compute_pet_expression(hunger, mood)

    img = Image.new("RGBA", (600, 600), (0, 0, 0, 255))
    _draw_background(img, equipped.get("background"), c1, c2)
    _draw_aura_and_back(img, species, preview_stage, equipped, c1, c2)
    _draw_body(img, species, preview_stage, max(level, 3 if preview_stage == 1 else level), c1, c2)
    _draw_face(img, species, preview_stage, expr)
    _draw_outfit(img, species, preview_stage, equipped, c1)
    _draw_headwear(img, species, preview_stage, equipped)
    _draw_face_and_held(img, species, preview_stage, equipped)

    stage_label = f"Xem trước (Stage {preview_stage})" if preview_stage > cur_stage else lvl_info["stage_name"]
    _draw_ui_overlay(img, pet, stage_label, level, c1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
