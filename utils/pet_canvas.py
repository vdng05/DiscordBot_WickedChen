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
RENDER_VERSION = "v2"


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


def _draw_background(img: Image.Image, bg_id: Optional[str], c1: Tuple[int, int, int], c2: Tuple[int, int, int], stage: int = 1):
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
    elif bg_id == "bg_galaxy_nebula":
        top, bot = (14, 8, 36), (56, 22, 86)
    elif bg_id == "bg_neon_dojo":
        top, bot = (18, 12, 26), (58, 18, 44)
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
    elif bg_id == "bg_galaxy_nebula":
        draw.ellipse([70, 80, 320, 310], fill=(135, 65, 225, 45))
        draw.ellipse([260, 150, 530, 400], fill=(0, 195, 255, 38))
        for i in range(40):
            sx, sy = (i * 83 + 19) % w, (i * 59 + 29) % (h - 90)
            r = 2 if i % 3 else 3
            draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(255, 255, 255, 190))
    elif bg_id == "bg_neon_dojo":
        draw.rectangle([40, 180, 110, 440], fill=(24, 20, 38, 220), outline=(255, 60, 145, 175), width=2)
        draw.rectangle([490, 150, 560, 440], fill=(24, 20, 38, 220), outline=(0, 225, 255, 175), width=2)
        draw.rectangle([0, 415, w, h], fill=(32, 24, 44, 235))
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

    # Vòng năng lượng dưới chân (hoành tráng hơn từ Stage 4-5)
    draw.ellipse([105, 422, 495, 480], fill=(0, 0, 0, 95))
    if stage >= 4:
        draw.ellipse([115, 424, 485, 476], outline=(*c1, 165), width=3)
    if stage >= 5:
        draw.ellipse([90, 416, 510, 486], outline=(*c2, 185), width=2)


def _paste_anchored(base: Image.Image, overlay: Image.Image, anchor: Tuple[int, int, float]):
    cx, cy, scale = anchor
    nw = max(1, int(overlay.width * scale))
    nh = max(1, int(overlay.height * scale))
    resized = overlay.resize((nw, nh), Image.Resampling.LANCZOS)
    base.alpha_composite(resized, (int(cx - nw / 2), int(cy - nh / 2)))


def _draw_aura_and_back(img: Image.Image, species: str, stage: int, equipped: dict, c1: Tuple[int, int, int], c2: Tuple[int, int, int]):
    """Layer 1: Hào quang Tối Thượng & Cánh / Áo choàng / Katana đeo lưng."""
    anchors = PET_ANCHORS[species][stage]
    aura_id = equipped.get("aura")
    if stage >= 5 or aura_id:
        ax, ay, ascale = anchors["aura"]
        aura_layer = Image.new("RGBA", (440, 440), (0, 0, 0, 0))
        ad = ImageDraw.Draw(aura_layer, "RGBA")
        col_a = (255, 110, 40) if aura_id == "aura_dragon_flame" else (
            (255, 130, 185) if aura_id == "aura_sakura_storm" else (
                (145, 60, 255) if aura_id == "aura_void_lightning" else c1
            )
        )
        col_b = (255, 215, 70) if aura_id == "aura_dragon_flame" else (
            (255, 215, 235) if aura_id == "aura_sakura_storm" else (
                (0, 235, 255) if aura_id == "aura_void_lightning" else c2
            )
        )
        for r, alpha in ((195, 28), (155, 46), (118, 65)):
            ad.ellipse([220 - r, 220 - r, 220 + r, 220 + r], fill=(*col_a, alpha), outline=(*col_b, alpha + 55), width=3)
        for i in range(16):
            ang = math.radians(i * 22.5)
            px = 220 + int(math.cos(ang) * 175)
            py = 220 + int(math.sin(ang) * 175)
            r_dot = 7 if i % 2 == 0 else 4
            ad.ellipse([px - r_dot, py - r_dot, px + r_dot, py + r_dot], fill=(*col_b, 220))
        _paste_anchored(img, aura_layer, (ax, ay, ascale))

    back_id = equipped.get("back")
    if stage >= 4 and back_id:
        b_layer = Image.new("RGBA", (420, 280), (0, 0, 0, 0))
        bd = ImageDraw.Draw(b_layer, "RGBA")
        if back_id == "back_angel_wings":
            bd.polygon([(165, 130), (18, 22), (48, 152), (140, 178)], fill=(252, 252, 255, 240), outline=(180, 205, 240, 255), width=3)
            bd.polygon([(255, 130), (402, 22), (372, 152), (280, 178)], fill=(252, 252, 255, 240), outline=(180, 205, 240, 255), width=3)
            bd.polygon([(155, 145), (52, 95), (72, 185), (145, 185)], fill=(235, 244, 255, 225))
            bd.polygon([(265, 145), (368, 95), (348, 185), (275, 185)], fill=(235, 244, 255, 225))
        elif back_id == "back_demon_wings":
            bd.polygon([(165, 130), (16, 28), (52, 160), (140, 172)], fill=(48, 22, 68, 240), outline=(195, 65, 255, 255), width=4)
            bd.polygon([(255, 130), (404, 28), (368, 160), (280, 172)], fill=(48, 22, 68, 240), outline=(195, 65, 255, 255), width=4)
        elif back_id == "back_royal_cape":
            bd.polygon([(140, 50), (280, 50), (355, 255), (65, 255)], fill=(155, 22, 46, 240), outline=(245, 200, 75, 255), width=4)
            bd.polygon([(155, 60), (265, 60), (325, 240), (95, 240)], fill=(185, 28, 56, 230))
        elif back_id == "back_cyber_wings":
            bd.polygon([(160, 125), (15, 42), (62, 152), (142, 162)], fill=(18, 28, 54, 240), outline=(0, 230, 255, 255), width=4)
            bd.polygon([(260, 125), (405, 42), (358, 152), (278, 162)], fill=(18, 28, 54, 240), outline=(255, 50, 190, 255), width=4)
            bd.polygon([(145, 140), (48, 118), (78, 178), (138, 172)], fill=(0, 230, 255, 140))
            bd.polygon([(275, 140), (372, 118), (342, 178), (282, 172)], fill=(255, 50, 190, 140))
        elif back_id == "back_katana":
            bd.line([(72, 235), (348, 30)], fill=(38, 40, 50, 255), width=12)
            bd.line([(312, 56), (348, 30)], fill=(220, 45, 65, 255), width=14)
            bd.ellipse([300, 46, 324, 70], fill=(245, 200, 65, 255))
            bd.line([(348, 235), (72, 30)], fill=(38, 40, 50, 255), width=12)
            bd.line([(108, 56), (72, 30)], fill=(220, 45, 65, 255), width=14)
            bd.ellipse([96, 46, 120, 70], fill=(245, 200, 65, 255))
        _paste_anchored(img, b_layer, anchors["back"])


def _draw_limbs(draw: ImageDraw.ImageDraw, stage: int, body_cy: int, body_w: int, body_h: int, fill_col: Tuple[int, int, int, int], outline: Tuple[int, int, int, int], claw_col: Optional[Tuple[int, int, int, int]] = None):
    """Vẽ tay & chân phân biệt rõ từng giai đoạn tiến hóa."""
    if stage == 2:
        # Sơ sinh: tay chân ngắn mũm mĩm đáng yêu
        draw.ellipse([300 - body_w - 14, body_cy - 14, 300 - body_w + 14, body_cy + 14], fill=fill_col, outline=outline, width=3)
        draw.ellipse([300 + body_w - 14, body_cy - 14, 300 + body_w + 14, body_cy + 14], fill=fill_col, outline=outline, width=3)
        draw.ellipse([264, body_cy + body_h - 14, 294, body_cy + body_h + 10], fill=fill_col, outline=outline, width=3)
        draw.ellipse([306, body_cy + body_h - 14, 336, body_cy + body_h + 10], fill=fill_col, outline=outline, width=3)
        return

    # Stage 3, 4, 5: Tay dài & chân đứng vững chãi, Stage 4-5 có vai rộng & móng vuốt
    arm_w = 24 if stage == 3 else (30 if stage == 4 else 34)
    arm_len = 54 if stage == 3 else (68 if stage == 4 else 74)
    sx_l = 300 - body_w + 6
    sx_r = 300 + body_w - 6
    sy = body_cy - body_h + 22

    # Tay trái & phải dang nhẹ oai vệ
    draw.polygon([(sx_l, sy), (sx_l - arm_w - 12, sy + arm_len - 12), (sx_l - arm_w + 12, sy + arm_len), (sx_l + 6, sy + 24)], fill=fill_col, outline=outline, width=4)
    draw.polygon([(sx_r, sy), (sx_r + arm_w + 12, sy + arm_len - 12), (sx_r + arm_w - 12, sy + arm_len), (sx_r - 6, sy + 24)], fill=fill_col, outline=outline, width=4)

    # Chân đứng
    leg_top = body_cy + body_h - 18
    leg_bot = body_cy + body_h + (24 if stage == 3 else 34)
    draw.rounded_rectangle([254, leg_top, 288, leg_bot], radius=14, fill=fill_col, outline=outline, width=4)
    draw.rounded_rectangle([312, leg_top, 346, leg_bot], radius=14, fill=fill_col, outline=outline, width=4)

    if stage >= 4 and claw_col:
        for cx in (262, 272, 282, 318, 328, 338):
            draw.polygon([(cx - 3, leg_bot - 2), (cx + 3, leg_bot - 2), (cx, leg_bot + 7)], fill=claw_col)


def _draw_body(img: Image.Image, species: str, stage: int, level: int, c1: Tuple[int, int, int], c2: Tuple[int, int, int]):
    """Layer 2: Hình thái tiến hóa rõ rệt qua 5 giai đoạn cho 4 chủng loài."""
    draw = ImageDraw.Draw(img, "RGBA")
    outline = (20, 22, 32, 255)

    # Stage 1: Trứng Linh Thú
    if stage == 1:
        draw.ellipse([205, 175, 395, 415], fill=(*c1, 245), outline=outline, width=5)
        draw.arc([225, 225, 375, 330], start=15, end=165, fill=(*c2, 230), width=8)
        draw.ellipse([245, 205, 285, 245], fill=(255, 255, 255, 95))
        if level >= 3:
            crack = [(290, 215), (312, 248), (288, 275), (318, 305), (298, 332)]
            draw.line(crack, fill=(255, 245, 160, 245), width=5)
        return

    if species == "royal_slime":
        scale = {2: 0.72, 3: 0.88, 4: 1.02, 5: 1.12}[stage]
        rx, ry = int(105 * scale), int(88 * scale)
        cx, cy = 300, 328
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(*c1, 220), outline=outline, width=4)
        draw.ellipse([cx - rx + 18, cy - ry + 16, cx + rx - 28, cy + 12], fill=(*c2, 130))
        draw.ellipse([cx - rx + 28, cy - ry + 24, cx - rx + 68, cy - ry + 52], fill=(255, 255, 255, 150))
        if stage >= 3:
            # Lõi tinh thể phát sáng giữa thân
            draw.polygon([(300, cy - 22), (322, cy + 4), (300, cy + 28), (278, cy + 4)], fill=(*c2, 205), outline=(255, 255, 255, 190), width=2)
        if stage >= 4:
            # Vương miện vàng + 2 slime vệ tinh
            draw.polygon([(262, cy - ry + 8), (274, cy - ry - 28), (294, cy - ry - 6), (300, cy - ry - 38), (306, cy - ry - 6), (326, cy - ry - 28), (338, cy - ry + 8)], fill=(255, 212, 65, 255), outline=outline, width=3)
            draw.ellipse([135, 315, 175, 351], fill=(*c1, 205), outline=outline, width=3)
            draw.ellipse([425, 315, 465, 351], fill=(*c2, 205), outline=outline, width=3)
        if stage >= 5:
            # Quả cầu năng lượng bay quanh Slime Tối Thượng
            for ox, oy in ((155, 230), (445, 230), (185, 170), (415, 170)):
                draw.ellipse([ox - 10, oy - 10, ox + 10, oy + 10], fill=(255, 235, 145, 235), outline=(*c1, 255), width=2)
        return

    # Tỷ lệ hình thể thay đổi rõ rệt: Baby chibi đầu to -> Teen thon -> Adult cao lớn -> Apex uy nghiêm
    head_r = {2: 70, 3: 64, 4: 62, 5: 64}[stage]
    head_cy = {2: 278, 3: 238, 4: 214, 5: 206}[stage]
    body_w = {2: 46, 3: 54, 4: 66, 5: 72}[stage]
    body_h = {2: 44, 3: 68, 4: 84, 5: 90}[stage]
    body_cy = head_cy + head_r + body_h - 18

    if species == "cyber_cat":
        body_col = (46, 56, 84, 255)
        accent = c1
        # Đuôi năng lượng (từ Stage 4+ có đuôi kiếm neon kép)
        if stage == 2:
            draw.line([(300 + body_w - 6, body_cy + 12), (378, body_cy - 18), (392, body_cy - 44)], fill=(*accent, 255), width=9)
        elif stage == 3:
            draw.line([(300 + body_w - 6, body_cy + 16), (402, body_cy - 18), (430, body_cy - 78)], fill=(*accent, 255), width=12)
            draw.ellipse([418, body_cy - 92, 444, body_cy - 66], fill=(*c2, 255))
        else:
            draw.line([(300 + body_w - 8, body_cy + 18), (412, body_cy - 22), (448, body_cy - 95)], fill=(*accent, 255), width=14)
            draw.polygon([(448, body_cy - 95), (475, body_cy - 135), (432, body_cy - 115)], fill=(*c2, 255), outline=outline, width=2)
            if stage >= 5:
                draw.line([(300 - body_w + 8, body_cy + 18), (188, body_cy - 22), (152, body_cy - 95)], fill=(*c2, 255), width=12)
                draw.polygon([(152, body_cy - 95), (125, body_cy - 135), (168, body_cy - 115)], fill=(*accent, 255), outline=outline, width=2)

        _draw_limbs(draw, stage, body_cy, body_w, body_h, body_col, outline, claw_col=(*c2, 255))
        draw.rounded_rectangle([300 - body_w, body_cy - body_h, 300 + body_w, body_cy + body_h], radius=28, fill=body_col, outline=outline, width=4)
        # Lõi năng lượng ngực + giáp vai Stage 4-5
        draw.polygon([(300, body_cy - 34), (326, body_cy - 4), (300, body_cy + 26), (274, body_cy - 4)], fill=(*accent, 220))
        if stage >= 4:
            draw.polygon([(224, body_cy - body_h + 6), (258, body_cy - body_h + 4), (242, body_cy - body_h + 32)], fill=(*accent, 240), outline=outline, width=3)
            draw.polygon([(376, body_cy - body_h + 6), (342, body_cy - body_h + 4), (358, body_cy - body_h + 32)], fill=(*accent, 240), outline=outline, width=3)

        # Tai nhọn
        ear_h = 26 if stage == 2 else (42 if stage == 3 else 56)
        draw.polygon([(242, head_cy - 28), (222, head_cy - head_r - ear_h), (276, head_cy - head_r + 12)], fill=body_col, outline=outline, width=4)
        draw.polygon([(358, head_cy - 28), (378, head_cy - head_r - ear_h), (324, head_cy - head_r + 12)], fill=body_col, outline=outline, width=4)
        draw.polygon([(246, head_cy - 36), (233, head_cy - head_r - ear_h + 18), (268, head_cy - head_r + 14)], fill=(*accent, 240))
        draw.polygon([(354, head_cy - 36), (367, head_cy - head_r - ear_h + 18), (332, head_cy - head_r + 14)], fill=(*accent, 240))
        draw.ellipse([300 - head_r, head_cy - head_r, 300 + head_r, head_cy + head_r], fill=body_col, outline=outline, width=4)
        if stage >= 4:
            # Vạch cyber trên má & trán
            draw.line([(246, head_cy + 10), (262, head_cy + 16)], fill=(*c2, 240), width=4)
            draw.line([(354, head_cy + 10), (338, head_cy + 16)], fill=(*c2, 240), width=4)
            draw.polygon([(300, head_cy - 48), (310, head_cy - 30), (300, head_cy - 18), (290, head_cy - 30)], fill=(*c2, 245))

    elif species == "mini_dragon":
        body_col = _blend((38, 126, 94), c1, 0.45)
        body_rgba = (*body_col, 255)
        belly_col = (248, 222, 142, 255)
        # Đuôi rồng có gai ở Stage 4-5
        tail_x = 405 if stage == 2 else (440 if stage == 3 else 472)
        draw.polygon([(300 + body_w - 14, body_cy + 24), (tail_x, body_cy + 36), (tail_x + 18, body_cy - 16), (300 + body_w - 8, body_cy - 4)], fill=body_rgba, outline=outline, width=4)
        if stage >= 4:
            draw.polygon([(tail_x + 8, body_cy - 10), (tail_x + 34, body_cy - 34), (tail_x + 2, body_cy - 28)], fill=(245, 200, 75, 255), outline=outline, width=2)

        # Cánh rồng phát triển rõ qua từng giai đoạn (Stage 2 chưa có, Stage 3 cánh nhỏ, Stage 4 cánh lớn, Stage 5 cánh rồng hoàng kim khổng lồ)
        if stage >= 3:
            w_span = {3: 74, 4: 118, 5: 145}[stage]
            w_top = {3: 75, 4: 120, 5: 145}[stage]
            draw.polygon([(250, body_cy - 26), (250 - w_span, body_cy - w_top), (250 - w_span + 24, body_cy + 16)], fill=(*c2, 235), outline=outline, width=4)
            draw.polygon([(350, body_cy - 26), (350 + w_span, body_cy - w_top), (350 + w_span - 24, body_cy + 16)], fill=(*c2, 235), outline=outline, width=4)
            if stage >= 4:
                draw.line([(250, body_cy - 26), (250 - w_span + 8, body_cy - w_top + 38)], fill=outline, width=3)
                draw.line([(350, body_cy - 26), (350 + w_span - 8, body_cy - w_top + 38)], fill=outline, width=3)

        _draw_limbs(draw, stage, body_cy, body_w, body_h, body_rgba, outline, claw_col=(248, 222, 142, 255))
        draw.rounded_rectangle([300 - body_w, body_cy - body_h, 300 + body_w, body_cy + body_h], radius=30, fill=body_rgba, outline=outline, width=4)
        draw.ellipse([300 - body_w + 16, body_cy - body_h + 16, 300 + body_w - 16, body_cy + body_h - 8], fill=belly_col)
        if stage >= 4:
            # Vạch vảy bụng rồng trưởng thành
            for vy in range(body_cy - body_h + 36, body_cy + body_h - 24, 24):
                draw.arc([300 - body_w + 26, vy, 300 + body_w - 26, vy + 18], start=10, end=170, fill=(210, 168, 84, 220), width=3)

        # Sừng rồng: Stage 2 mầm ngắn, Stage 3 vừa, Stage 4 cong dài, Stage 5 cặp sừng kép + ngọc trán
        horn_h = {2: 18, 3: 36, 4: 54, 5: 66}[stage]
        draw.polygon([(256, head_cy - head_r + 20), (230, head_cy - head_r - horn_h), (276, head_cy - head_r + 6)], fill=(245, 200, 85, 255), outline=outline, width=3)
        draw.polygon([(344, head_cy - head_r + 20), (370, head_cy - head_r - horn_h), (324, head_cy - head_r + 6)], fill=(245, 200, 85, 255), outline=outline, width=3)
        if stage >= 5:
            draw.polygon([(238, head_cy - head_r + 36), (195, head_cy - head_r - 22), (248, head_cy - head_r + 20)], fill=(255, 165, 60, 255), outline=outline, width=3)
            draw.polygon([(362, head_cy - head_r + 36), (405, head_cy - head_r - 22), (352, head_cy - head_r + 20)], fill=(255, 165, 60, 255), outline=outline, width=3)

        draw.ellipse([300 - head_r, head_cy - head_r, 300 + head_r, head_cy + head_r], fill=body_rgba, outline=outline, width=4)
        if stage >= 4:
            # Ngọc rồng phát sáng giữa trán ở Stage 4-5
            draw.polygon([(300, head_cy - 50), (312, head_cy - 34), (300, head_cy - 20), (288, head_cy - 34)], fill=(*c2, 255), outline=(255, 240, 160, 255), width=2)

    else:
        # Cáo Tinh (Spirit Fox) — 1 đuôi (Stage 2) -> 3 đuôi (Stage 3-4) -> 5 đuôi + vòng linh lực (Stage 5)
        fur_col = _blend((240, 128, 56), c1, 0.25)
        fur_rgba = (*fur_col, 255)
        tail_count = 1 if stage == 2 else (3 if stage <= 4 else 5)
        tail_len = {2: 115, 3: 145, 4: 170, 5: 190}[stage]
        for ti in range(tail_count):
            ang = math.radians(-55 + (ti - (tail_count - 1) / 2) * 28)
            tx = 300 + int(math.sin(ang) * tail_len) + (28 if tail_count == 1 else 0)
            ty = body_cy - int(math.cos(ang) * (tail_len * 0.68)) + 15
            draw.line([(300, body_cy + 18), (tx, ty)], fill=fur_rgba, width=24 if stage <= 3 else 28)
            draw.ellipse([tx - 16, ty - 16, tx + 16, ty + 16], fill=(255, 245, 232, 255), outline=outline, width=2)

        _draw_limbs(draw, stage, body_cy, body_w, body_h, fur_rgba, outline)
        draw.rounded_rectangle([300 - body_w, body_cy - body_h, 300 + body_w, body_cy + body_h], radius=30, fill=fur_rgba, outline=outline, width=4)
        draw.ellipse([250, head_cy + head_r - 22, 350, head_cy + head_r + 36], fill=(255, 245, 232, 255), outline=outline, width=3)

        ear_h = {2: 28, 3: 42, 4: 54, 5: 60}[stage]
        draw.polygon([(238, head_cy - 28), (218, head_cy - head_r - ear_h), (274, head_cy - head_r + 12)], fill=fur_rgba, outline=outline, width=4)
        draw.polygon([(362, head_cy - 28), (382, head_cy - head_r - ear_h), (326, head_cy - head_r + 12)], fill=fur_rgba, outline=outline, width=4)
        draw.ellipse([300 - head_r, head_cy - head_r, 300 + head_r, head_cy + head_r], fill=fur_rgba, outline=outline, width=4)
        if stage >= 4:
            # Ấn ký Cửu Vĩ trên trán
            draw.polygon([(300, head_cy - 50), (310, head_cy - 32), (300, head_cy - 20), (290, head_cy - 32)], fill=(255, 95, 115, 240))


def _draw_face(img: Image.Image, species: str, stage: int, expression: str):
    """Layer 3: Mắt & miệng theo biểu cảm và khí chất từng giai đoạn."""
    if stage == 1:
        return
    draw = ImageDraw.Draw(img, "RGBA")
    cy = 326 if species == "royal_slime" else {2: 278, 3: 238, 4: 214, 5: 206}[stage]
    lx, rx = 272, 328

    if expression == "sleepy":
        draw.arc([lx - 14, cy - 8, lx + 14, cy + 12], start=0, end=180, fill=(20, 22, 30, 255), width=4)
        draw.arc([rx - 14, cy - 8, rx + 14, cy + 12], start=0, end=180, fill=(20, 22, 30, 255), width=4)
        draw.ellipse([292, cy + 18, 308, cy + 32], fill=(220, 95, 115, 255))
        draw.text((366, cy - 52), "Zzz", font=get_font(22, bold=True), fill=(210, 225, 255, 230))
    elif expression == "hungry":
        draw.line([(lx - 12, cy - 8), (lx + 10, cy + 2), (lx - 12, cy + 10)], fill=(20, 22, 30, 255), width=4)
        draw.line([(rx + 12, cy - 8), (rx - 10, cy + 2), (rx + 12, cy + 10)], fill=(20, 22, 30, 255), width=4)
        draw.arc([284, cy + 22, 316, cy + 38], start=180, end=360, fill=(20, 22, 30, 255), width=4)
    else:
        eye_r = 14 if stage == 2 else 12
        for ex in (lx, rx):
            draw.ellipse([ex - eye_r, cy - eye_r, ex + eye_r, cy + eye_r], fill=(20, 22, 30, 255))
            draw.ellipse([ex - 6, cy - 8, ex + 2, cy], fill=(255, 255, 255, 255))
        if stage >= 4:
            # Lông mày uy nghiêm cho Trưởng Thành & Tối Thượng
            draw.line([(lx - 16, cy - 22), (lx + 12, cy - 16)], fill=(20, 22, 32, 255), width=4)
            draw.line([(rx + 16, cy - 22), (rx - 12, cy - 16)], fill=(20, 22, 32, 255), width=4)
        if expression == "happy":
            draw.ellipse([lx - 26, cy + 10, lx - 10, cy + 22], fill=(255, 130, 155, 165))
            draw.ellipse([rx + 10, cy + 10, rx + 26, cy + 22], fill=(255, 130, 155, 165))
            draw.arc([284, cy + 12, 316, cy + 32], start=0, end=180, fill=(20, 22, 30, 255), width=4)
        else:
            draw.line([(290, cy + 22), (310, cy + 22)], fill=(20, 22, 30, 255), width=4)


def _draw_outfit(img: Image.Image, species: str, stage: int, equipped: dict, c1: Tuple[int, int, int]):
    """Layer 4: Trang phục cắt may chữ T có tay áo, cổ áo, thắt lưng & cầu vai (không còn là hình vuông đơn điệu)."""
    outfit_id = equipped.get("outfit")
    if stage < 3 or not outfit_id:
        return

    # Slime mặc khăn choàng / áo choàng cổ hoàng gia gọn đẹp
    if species == "royal_slime":
        s_layer = Image.new("RGBA", (220, 120), (0, 0, 0, 0))
        sd = ImageDraw.Draw(s_layer, "RGBA")
        col_map = {
            "outfit_hoodie": (42, 46, 62, 235),
            "outfit_bomber": (185, 48, 65, 235),
            "outfit_cyber_armor": (22, 34, 62, 235),
            "outfit_royal_vest": (135, 24, 48, 235),
            "outfit_tuxedo": (24, 26, 36, 235),
            "outfit_mage_robe": (72, 44, 136, 235),
            "outfit_cloud_robe": (28, 30, 44, 235),
            "outfit_samurai": (165, 32, 42, 235),
            "outfit_tanktop": (65, 165, 245, 235),
        }
        scol = col_map.get(outfit_id, (*c1, 230))
        sd.pieslice([30, 10, 190, 105], start=0, end=180, fill=scol, outline=(20, 22, 32, 255), width=3)
        _paste_anchored(img, s_layer, (300, 385, 0.92))
        return

    o_layer = Image.new("RGBA", (240, 180), (0, 0, 0, 0))
    od = ImageDraw.Draw(o_layer, "RGBA")
    outline = (20, 22, 32, 255)
    # Phom áo chữ T có vai + 2 tay áo + thân áo
    shirt_poly = [(48, 24), (192, 24), (226, 66), (200, 88), (180, 68), (180, 158), (60, 158), (60, 68), (40, 88), (14, 66)]

    if outfit_id == "outfit_hoodie":
        od.polygon(shirt_poly, fill=(44, 48, 66, 250), outline=outline, width=4)
        od.polygon([(84, 24), (120, 52), (156, 24)], fill=(*c1, 245), outline=outline, width=3)
        od.line([(106, 46), (106, 78)], fill=(235, 235, 245, 255), width=3)
        od.line([(134, 46), (134, 78)], fill=(235, 235, 245, 255), width=3)
        od.rounded_rectangle([84, 108, 156, 146], radius=12, fill=(32, 36, 52, 255), outline=outline, width=3)
    elif outfit_id == "outfit_bomber":
        od.polygon(shirt_poly, fill=(185, 42, 62, 250), outline=outline, width=4)
        od.polygon([(14, 66), (48, 24), (60, 68), (40, 88)], fill=(242, 242, 248, 250), outline=outline, width=3)
        od.polygon([(226, 66), (192, 24), (180, 68), (200, 88)], fill=(242, 242, 248, 250), outline=outline, width=3)
        od.line([(120, 28), (120, 156)], fill=(245, 210, 80, 255), width=4)
        od.rectangle([60, 144, 180, 158], fill=(28, 30, 42, 255))
    elif outfit_id == "outfit_cyber_armor":
        od.polygon(shirt_poly, fill=(22, 34, 58, 250), outline=(0, 230, 255, 255), width=4)
        # Cầu vai giáp công nghệ
        od.polygon([(34, 26), (76, 22), (62, 54), (20, 48)], fill=(36, 52, 86, 255), outline=(0, 230, 255, 255), width=3)
        od.polygon([(206, 26), (164, 22), (178, 54), (220, 48)], fill=(36, 52, 86, 255), outline=(0, 230, 255, 255), width=3)
        od.polygon([(120, 48), (144, 74), (120, 100), (96, 74)], fill=(0, 235, 255, 235), outline=(255, 255, 255, 220), width=2)
        od.rectangle([62, 126, 178, 142], fill=(0, 215, 255, 190))
    elif outfit_id == "outfit_royal_vest":
        od.polygon(shirt_poly, fill=(135, 22, 46, 250), outline=(245, 200, 75, 255), width=4)
        # Cổ áo chữ V lộ sơ mi trắng + cà vạt vàng
        od.polygon([(92, 24), (148, 24), (120, 82)], fill=(248, 248, 252, 255), outline=outline, width=2)
        od.polygon([(114, 34), (126, 34), (124, 72), (120, 80), (116, 72)], fill=(245, 198, 65, 255))
        od.line([(120, 82), (120, 156)], fill=(245, 200, 75, 255), width=4)
        for by in (98, 122, 144):
            od.ellipse([106, by - 4, 114, by + 4], fill=(245, 200, 75, 255))
            od.ellipse([126, by - 4, 134, by + 4], fill=(245, 200, 75, 255))
    elif outfit_id == "outfit_tuxedo":
        od.polygon(shirt_poly, fill=(24, 26, 36, 252), outline=(215, 220, 235, 220), width=3)
        od.polygon([(94, 24), (146, 24), (120, 84)], fill=(250, 250, 255, 255), outline=outline, width=2)
        od.polygon([(104, 34), (120, 44), (136, 34), (136, 48), (120, 42), (104, 48)], fill=(220, 42, 65, 255))
    elif outfit_id == "outfit_mage_robe":
        od.polygon(shirt_poly, fill=(68, 42, 132, 250), outline=(245, 200, 75, 255), width=4)
        od.line([(120, 28), (120, 156)], fill=(245, 200, 75, 255), width=5)
        od.ellipse([106, 64, 134, 92], fill=(90, 220, 255, 240), outline=(245, 200, 75, 255), width=2)
    elif outfit_id == "outfit_cloud_robe":
        od.polygon(shirt_poly, fill=(28, 30, 46, 250), outline=(225, 65, 85, 255), width=4)
        # Vạt áo chéo Kimono + đai Obi đỏ
        od.line([(86, 26), (148, 114)], fill=(245, 245, 250, 240), width=6)
        od.line([(154, 26), (116, 76)], fill=(245, 245, 250, 240), width=6)
        od.rectangle([58, 112, 182, 134], fill=(215, 48, 68, 255), outline=outline, width=3)
        od.ellipse([70, 56, 102, 80], fill=(225, 65, 85, 220))
    elif outfit_id == "outfit_samurai":
        od.polygon(shirt_poly, fill=(145, 28, 38, 250), outline=(245, 200, 75, 255), width=4)
        for ry in (56, 82, 108, 134):
            od.line([(62, ry), (178, ry)], fill=(245, 200, 75, 235), width=4)
        od.polygon([(26, 28), (74, 24), (60, 62), (14, 54)], fill=(34, 36, 48, 255), outline=(245, 200, 75, 255), width=3)
        od.polygon([(214, 28), (166, 24), (180, 62), (226, 54)], fill=(34, 36, 48, 255), outline=(245, 200, 75, 255), width=3)
    elif outfit_id == "outfit_tanktop":
        tank_poly = [(74, 26), (166, 26), (176, 156), (64, 156)]
        od.polygon(tank_poly, fill=(246, 248, 255, 248), outline=(58, 162, 245, 255), width=4)
        od.pieslice([94, 12, 146, 56], start=0, end=180, fill=(0, 0, 0, 0), outline=(58, 162, 245, 255), width=4)
        od.ellipse([96, 68, 144, 116], fill=(255, 205, 65, 240))

    _paste_anchored(img, o_layer, PET_ANCHORS[species][stage]["outfit"])


def _draw_headwear(img: Image.Image, species: str, stage: int, equipped: dict):
    """Layer 5: Mũ / Đội đầu (mở từ Stage 2+)."""
    hat_id = equipped.get("headwear")
    if stage < 2 or not hat_id:
        return
    h_layer = Image.new("RGBA", (200, 140), (0, 0, 0, 0))
    hd = ImageDraw.Draw(h_layer, "RGBA")
    outline = (20, 22, 32, 255)
    if hat_id == "hat_cap_back":
        hd.pieslice([48, 38, 152, 118], start=180, end=360, fill=(225, 55, 70, 255), outline=outline, width=4)
        hd.rectangle([115, 68, 176, 82], fill=(30, 34, 46, 255), outline=outline, width=3)
    elif hat_id == "hat_gaming_headset":
        hd.arc([38, 28, 162, 122], start=185, end=355, fill=(38, 42, 58, 255), width=12)
        hd.rounded_rectangle([28, 66, 54, 112], radius=10, fill=(0, 225, 255, 255), outline=outline, width=3)
        hd.rounded_rectangle([146, 66, 172, 112], radius=10, fill=(255, 65, 185, 255), outline=outline, width=3)
    elif hat_id == "hat_gold_crown":
        hd.polygon([(50, 96), (58, 40), (84, 72), (100, 28), (116, 72), (142, 40), (150, 96)], fill=(255, 210, 65, 255), outline=outline, width=4)
        hd.ellipse([93, 62, 107, 76], fill=(230, 45, 75, 255))
    elif hat_id == "hat_ninja_band":
        hd.rectangle([38, 64, 162, 92], fill=(28, 34, 52, 255), outline=outline, width=3)
        hd.rectangle([74, 68, 126, 88], fill=(195, 205, 220, 255), outline=outline, width=2)
    elif hat_id == "hat_duck":
        hd.ellipse([54, 34, 146, 98], fill=(255, 222, 65, 255), outline=outline, width=4)
        hd.ellipse([80, 74, 120, 94], fill=(255, 140, 40, 255), outline=outline, width=3)
    elif hat_id == "hat_wizard":
        hd.ellipse([26, 82, 174, 114], fill=(54, 38, 108, 255), outline=(245, 200, 75, 255), width=3)
        hd.polygon([(56, 92), (144, 92), (108, 16)], fill=(68, 46, 134, 255), outline=outline, width=4)
        hd.rectangle([64, 76, 136, 90], fill=(245, 200, 75, 255))
    elif hat_id == "hat_oni_horns":
        hd.polygon([(46, 98), (34, 38), (74, 82)], fill=(225, 45, 65, 255), outline=outline, width=4)
        hd.polygon([(154, 98), (166, 38), (126, 82)], fill=(225, 45, 65, 255), outline=outline, width=4)
        hd.ellipse([86, 68, 114, 96], fill=(245, 200, 75, 255), outline=outline, width=3)
    elif hat_id == "hat_cat_ears_rgb":
        hd.arc([44, 46, 156, 120], start=185, end=355, fill=(32, 36, 52, 255), width=8)
        hd.polygon([(46, 74), (36, 22), (80, 56)], fill=(32, 36, 52, 255), outline=(0, 235, 255, 255), width=4)
        hd.polygon([(154, 74), (164, 22), (120, 56)], fill=(32, 36, 52, 255), outline=(255, 65, 195, 255), width=4)
    elif hat_id == "hat_halo_angel":
        hd.ellipse([48, 22, 152, 56], fill=(0, 0, 0, 0), outline=(255, 228, 110, 255), width=7)
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
        elif face_id == "face_monocle":
            fd.ellipse([96, 16, 142, 62], fill=(165, 225, 255, 75), outline=(245, 200, 75, 255), width=4)
            fd.line([(142, 42), (148, 76)], fill=(245, 200, 75, 255), width=3)
        elif face_id == "face_star_blush":
            fd.ellipse([18, 36, 46, 58], fill=(255, 120, 165, 220))
            fd.ellipse([124, 36, 152, 58], fill=(255, 120, 165, 220))
            fd.polygon([(32, 34), (36, 44), (46, 44), (38, 50), (40, 60), (32, 54), (24, 60), (26, 50), (18, 44), (28, 44)], fill=(255, 225, 90, 245))
        _paste_anchored(img, f_layer, PET_ANCHORS[species][stage]["face"])

    held_id = equipped.get("held")
    if stage >= 4 and held_id:
        hl_layer = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hl_layer, "RGBA")
        outline = (20, 22, 32, 255)
        if held_id == "held_gamepad":
            hd.rounded_rectangle([16, 38, 104, 82], radius=16, fill=(32, 38, 56, 255), outline=(0, 225, 255, 255), width=3)
            hd.ellipse([28, 50, 44, 66], fill=(0, 225, 255, 255))
            hd.ellipse([74, 48, 86, 60], fill=(255, 70, 165, 255))
        elif held_id == "held_boba":
            hd.polygon([(38, 38), (82, 38), (74, 96), (46, 96)], fill=(245, 225, 195, 245), outline=outline, width=3)
            hd.line([(60, 12), (60, 38)], fill=(255, 90, 140, 255), width=5)
            for bx, by in ((50, 82), (60, 86), (68, 80)):
                hd.ellipse([bx - 4, by - 4, bx + 4, by + 4], fill=(30, 24, 24, 255))
        elif held_id == "held_scepter":
            hd.line([(60, 108), (60, 32)], fill=(245, 200, 75, 255), width=8)
            hd.ellipse([42, 12, 78, 48], fill=(90, 215, 255, 245), outline=(255, 240, 150, 255), width=3)
        elif held_id == "held_sword":
            hd.polygon([(54, 8), (66, 8), (68, 76), (52, 76)], fill=(0, 235, 255, 245), outline=(255, 255, 255, 255), width=2)
            hd.rectangle([42, 76, 78, 86], fill=(245, 200, 75, 255), outline=outline, width=2)
            hd.rectangle([55, 86, 65, 108], fill=(42, 46, 62, 255))
        elif held_id == "held_mic":
            hd.line([(60, 104), (60, 50)], fill=(38, 42, 56, 255), width=8)
            hd.ellipse([44, 22, 76, 54], fill=(215, 220, 235, 255), outline=(255, 70, 180, 255), width=3)
        elif held_id == "held_lantern":
            hd.line([(60, 12), (60, 32)], fill=(245, 200, 75, 255), width=4)
            hd.ellipse([36, 30, 84, 88], fill=(235, 65, 75, 245), outline=(245, 200, 75, 255), width=3)
            hd.ellipse([50, 48, 70, 70], fill=(255, 235, 140, 230))
        _paste_anchored(img, hl_layer, PET_ANCHORS[species][stage]["held"])


def _draw_ui_overlay(img: Image.Image, pet: Dict[str, Any], stage_name: str, level: int, c1: Tuple[int, int, int]):
    """Layer 7: Tên Pet, khung Level và 2 thanh Độ No / Độ Vui."""
    draw = ImageDraw.Draw(img, "RGBA")
    font_title = get_font(24, bold=True)
    font_sub = get_font(17, bold=True)
    font_bar = get_font(15, bold=True)

    draw.rounded_rectangle([30, 20, 570, 82], radius=18, fill=(14, 16, 28, 195), outline=(*c1, 210), width=2)
    sp_name = PET_SPECIES.get(pet["species"], {}).get("name", pet["species"])
    draw.text((48, 28), f"{pet['name']} ({sp_name})", font=font_title, fill=(255, 255, 255, 255))
    draw.text((48, 56), f"Lv.{level} • {stage_name}", font=font_sub, fill=(255, 215, 110, 255))

    draw.rounded_rectangle([30, 502, 570, 578], radius=18, fill=(14, 16, 28, 200), outline=(*c1, 180), width=2)
    hunger = max(0, min(100, int(pet.get("hunger", 80))))
    mood = max(0, min(100, int(pet.get("mood", 80))))

    draw.text((50, 514), f"Độ No: {hunger}%", font=font_bar, fill=(255, 210, 140, 255))
    draw.rounded_rectangle([50, 538, 280, 558], radius=8, fill=(42, 46, 62, 255))
    if hunger > 0:
        draw.rounded_rectangle([50, 538, 50 + int(230 * hunger / 100), 558], radius=8, fill=(245, 155, 55, 255))

    draw.text((318, 514), f"Độ Vui: {mood}%", font=font_bar, fill=(155, 235, 255, 255))
    draw.rounded_rectangle([318, 538, 550, 558], radius=8, fill=(42, 46, 62, 255))
    if mood > 0:
        draw.rounded_rectangle([318, 538, 318 + int(232 * mood / 100), 558], radius=8, fill=(75, 210, 155, 255))


def render_pet_sprite_only(pet: Dict[str, Any], clan_color: str = "#5865F2", secondary_color: Optional[str] = None, size: int = 240) -> Image.Image:
    """Render riêng nhân vật Pet nền trong suốt để ghép lên Wallpaper Full HD."""
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
            "v": RENDER_VERSION,
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

    for old_file in PET_CACHE_DIR.glob(f"{clan_id}_*.png"):
        try:
            old_file.unlink()
        except Exception:
            pass

    c1 = hex_to_rgb(c1_hex)
    c2 = hex_to_rgb(c2_hex) if c2_hex else _blend(c1, (255, 255, 255), 0.35)

    img = Image.new("RGBA", (600, 600), (0, 0, 0, 255))
    _draw_background(img, equipped.get("background"), c1, c2, stage=stage)
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
    _draw_background(img, equipped.get("background"), c1, c2, stage=preview_stage)
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
