"""
Pillow Vector 2.5D Cel-Shaded Canvas Renderer cho Hệ Thống Linh Thú Băng Đảng (Clan Pet).
- Vẽ ở độ phân giải Supersampling 2x (1200x1200 RGBA) rồi downsample LANCZOS về 600x600 siêu mịn.
- Tích hợp Đường cong Cubic Bezier, Cel-Shading 3 lớp (Bóng đổ + Ánh sáng viền), Neon Bloom (GaussianBlur),
  Mắt Anime 3 lớp, Hệ tọa độ neo (Anchor System) và Smart MD5 Cache (v3).
"""

import hashlib
import io
import json
import math
from typing import Any, Callable, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFilter

from config import Config
from utils.canvas import get_font, hex_to_rgb
from utils.constants import PET_ANCHORS, PET_SPECIES, get_pet_level_info
from utils.time_helper import get_vietnam_now

PET_CACHE_DIR = Config.DATA_DIR / "pet_cache"
PET_ASSETS_DIR = Config.BASE_DIR / "assets" / "pet"
RENDER_VERSION = "v5"
SS = 2  # Supersampling 2x: canvas nội bộ 1200x1200 -> 600x600


_OUTFIT_SKIN_STYLES = {
    "outfit_hoodie": ((110, 130, 185), (180, 200, 255), 0.08),
    "outfit_bomber": ((215, 65, 85), (255, 210, 95), 0.10),
    "outfit_cyber_armor": ((0, 225, 255), (85, 245, 255), 0.12),
    "outfit_royal_vest": ((245, 195, 65), (255, 235, 150), 0.10),
    "outfit_tuxedo": ((165, 175, 205), (235, 240, 255), 0.07),
    "outfit_mage_robe": ((155, 85, 255), (110, 225, 255), 0.12),
    "outfit_cloud_robe": ((225, 50, 75), (255, 150, 165), 0.10),
    "outfit_samurai": ((215, 55, 65), (245, 200, 75), 0.11),
    "outfit_tanktop": ((65, 185, 255), (255, 220, 110), 0.08),
}


def _load_pet_sprite(species: str, stage: int) -> Tuple[Optional[Image.Image], int]:
    """Tải Sprite Game Art trong assets/pet/{species}/stage_{n}.png (tự fallback về stage cao nhất hiện có)."""
    sp_dir = PET_ASSETS_DIR / species
    if not sp_dir.exists():
        return None, stage
    for s in range(stage, 0, -1):
        cand = sp_dir / f"stage_{s}.png"
        if cand.exists():
            try:
                return Image.open(cand).convert("RGBA"), s
            except Exception:
                pass
    return None, stage


def _apply_skin_shader(sprite: Image.Image, outfit_id: Optional[str]) -> Tuple[Image.Image, Optional[Tuple[int, int, int]]]:
    """Áp dụng sắc tố Skin nhẹ nhàng lên chính Sprite AI (giữ nguyên 100% chi tiết khối 3D)."""
    if not outfit_id or outfit_id not in _OUTFIT_SKIN_STYLES:
        return sprite, None
    tint_col, rim_col, strength = _OUTFIT_SKIN_STYLES[outfit_id]
    r, g, b, a = sprite.split()
    rgb = Image.merge("RGB", (r, g, b))
    tint_img = Image.new("RGB", sprite.size, tint_col)
    blended_rgb = Image.blend(rgb, tint_img, strength)
    sr, sg, sb = blended_rgb.split()
    return Image.merge("RGBA", (sr, sg, sb, a)), rim_col


def _draw_sprite_layer(
    img: Image.Image,
    species: str,
    stage: int,
    expression: str,
    c1: Tuple[int, int, int],
    outfit_id: Optional[str] = None,
) -> bool:
    """Dán Sprite Game Art làm Layer 2 (tích hợp Skin Shader + Rim Glow ôm sát dáng thú)."""
    sprite, loaded_stage = _load_pet_sprite(species, stage)
    if sprite is None:
        return False

    target_size = {1: 580, 2: 600, 3: 660, 4: 700, 5: 730}.get(stage, 660)
    if stage >= 4 and loaded_stage < stage:
        target_size = min(750, target_size + 25)
    resized = sprite.resize((target_size, target_size), Image.Resampling.LANCZOS)
    resized, skin_rim = _apply_skin_shader(resized, outfit_id)

    px = (img.width - resized.width) // 2
    py = 595 - resized.height // 2

    # Ánh sáng viền mềm (Rim Glow) theo Skin hoặc màu băng
    if stage >= 4 or skin_rim is not None:
        rim_col = skin_rim if skin_rim is not None else _lighten(c1, 0.25)
        alpha = resized.getchannel("A")
        glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        tinted = Image.new("RGBA", resized.size, (*rim_col, 165 if skin_rim else 135))
        tinted.putalpha(alpha)
        glow_layer.paste(tinted, (px, py), alpha)
        img.alpha_composite(glow_layer.filter(ImageFilter.GaussianBlur(16)))

    img.alpha_composite(resized, (px, py))

    # Huy hiệu biểu cảm nhỏ gọn ở góc đầu nếu đang buồn ngủ hoặc đói
    if expression == "sleepy":
        draw = ImageDraw.Draw(img, "RGBA")
        draw.text((790, 270), "Zzz", font=get_font(46, bold=True), fill=(210, 228, 255, 240))
    elif expression == "hungry":
        draw = ImageDraw.Draw(img, "RGBA")
        draw.rounded_rectangle([770, 265, 920, 325], radius=18, fill=(220, 55, 70, 225))
        draw.text((845, 295), "Đói!", font=get_font(30, bold=True), fill=(255, 255, 255, 255), anchor="mm")
    return True


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


def _darken(c: Tuple[int, int, int], factor: float = 0.35) -> Tuple[int, int, int]:
    return _blend(c, (10, 12, 22), factor)


def _lighten(c: Tuple[int, int, int], factor: float = 0.35) -> Tuple[int, int, int]:
    return _blend(c, (255, 255, 255), factor)


def _bezier(p0: Tuple[float, float], p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float], steps: int = 20) -> List[Tuple[float, float]]:
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1.0 - t
        x = (u ** 3) * p0[0] + 3 * (u ** 2) * t * p1[0] + 3 * u * (t ** 2) * p2[0] + (t ** 3) * p3[0]
        y = (u ** 3) * p0[1] + 3 * (u ** 2) * t * p1[1] + 3 * u * (t ** 2) * p2[1] + (t ** 3) * p3[1]
        pts.append((x, y))
    return pts


def _draw_bloom(base: Image.Image, draw_fn: Callable[[ImageDraw.ImageDraw], None], blur_radius: int = 16):
    """Vẽ hiệu ứng phát sáng Neon / Ma thuật thật bằng GaussianBlur + alpha_composite."""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer, "RGBA")
    draw_fn(ld)
    glow = layer.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    base.alpha_composite(glow)
    base.alpha_composite(layer)


def _draw_sparkle(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, col: Tuple[int, int, int, int]):
    ir = r * 0.28
    pts = [
        (cx, cy - r), (cx + ir, cy - ir),
        (cx + r, cy), (cx + ir, cy + ir),
        (cx, cy + r), (cx - ir, cy + ir),
        (cx - r, cy), (cx - ir, cy - ir),
    ]
    draw.polygon(pts, fill=col)


def _draw_shaded_ellipse(
    base: Image.Image,
    bbox: Tuple[float, float, float, float],
    fill_rgb: Tuple[int, int, int],
    outline: Tuple[int, int, int, int] = (20, 22, 34, 255),
    width: int = 7,
    alpha: int = 255,
):
    """Vẽ hình cầu/oval có đổ khối 3D (bóng dưới-phải + highlight trên-trái)."""
    x0, y0, x1, y1 = bbox
    w = max(1, int(x1 - x0))
    h = max(1, int(y1 - y0))
    part = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
    pd = ImageDraw.Draw(part, "RGBA")
    ox, oy = 10, 10

    pd.ellipse([ox, oy, ox + w, oy + h], fill=(*fill_rgb, alpha))
    # Bóng cel-shading phía dưới phải
    sh_col = (*_darken(fill_rgb, 0.32), min(255, alpha))
    pd.chord([ox + int(w * 0.04), oy + int(h * 0.04), ox + w - 2, oy + h - 2], start=350, end=155, fill=sh_col)
    # Điểm sáng mềm trên trái
    hi_col = (*_lighten(fill_rgb, 0.42), min(180, alpha))
    pd.ellipse([ox + int(w * 0.16), oy + int(h * 0.10), ox + int(w * 0.56), oy + int(h * 0.36)], fill=hi_col)
    # Viền sắc nét
    pd.ellipse([ox, oy, ox + w, oy + h], outline=outline, width=width)
    base.alpha_composite(part, (int(x0 - ox), int(y0 - oy)))


def _paste_anchored(base: Image.Image, overlay: Image.Image, anchor: Tuple[int, int, float]):
    cx, cy, scale = anchor
    cx *= SS
    cy *= SS
    nw = max(1, int(overlay.width * scale))
    nh = max(1, int(overlay.height * scale))
    resized = overlay.resize((nw, nh), Image.Resampling.LANCZOS)
    base.alpha_composite(resized, (int(cx - nw / 2), int(cy - nh / 2)))


def _draw_background(img: Image.Image, bg_id: Optional[str], c1: Tuple[int, int, int], c2: Tuple[int, int, int], stage: int = 1):
    """Layer 0 (1200x1200): Phông nền có chiều sâu, ánh sáng & sân đứng."""
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = img.size

    palettes = {
        "bg_sunny_beach": ((40, 148, 228), (255, 210, 128)),
        "bg_sakura_night": ((18, 12, 38), (82, 32, 78)),
        "bg_royal_hall": ((32, 14, 48), (94, 52, 24)),
        "bg_cyber_grid": ((8, 12, 28), (18, 42, 78)),
        "bg_galaxy_nebula": ((12, 8, 34), (62, 22, 92)),
        "bg_neon_dojo": ((16, 10, 26), (62, 18, 48)),
    }
    top, bot = palettes.get(bg_id, (_blend((14, 16, 30), c1, 0.25), _blend((22, 26, 46), c2, 0.25)))

    for y in range(h):
        col = _blend(top, bot, y / max(1, h - 1))
        draw.line([(0, y), (w, y)], fill=(*col, 255))

    # Spotlight mềm ở tâm nền
    spot = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spot, "RGBA")
    sd.ellipse([240, 180, 960, 900], fill=(*_lighten(c1, 0.2), 55))
    img.alpha_composite(spot.filter(ImageFilter.GaussianBlur(70)))

    draw = ImageDraw.Draw(img, "RGBA")
    if bg_id == "bg_cyber_grid":
        horizon = 760
        for i in range(-8, 9):
            draw.line([(600 + i * 36, horizon), (600 + i * 165, h)], fill=(*c1, 95), width=2)
        for gy in (790, 840, 910, 1000, 1110):
            draw.line([(0, gy), (w, gy)], fill=(*c2, 80), width=2)
        _draw_bloom(img, lambda d: d.line([(0, horizon), (w, horizon)], fill=(*c2, 200), width=4), blur_radius=10)
    elif bg_id == "bg_galaxy_nebula":
        neb = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        nd = ImageDraw.Draw(neb, "RGBA")
        nd.ellipse([140, 160, 680, 620], fill=(150, 70, 240, 75))
        nd.ellipse([520, 280, 1080, 820], fill=(0, 205, 255, 60))
        img.alpha_composite(neb.filter(ImageFilter.GaussianBlur(55)))
        draw = ImageDraw.Draw(img, "RGBA")
        for i in range(45):
            sx, sy = (i * 157 + 41) % w, (i * 113 + 53) % (h - 180)
            _draw_sparkle(draw, sx, sy, 6 if i % 4 == 0 else 3, (255, 255, 255, 210))
    elif bg_id == "bg_sakura_night":
        _draw_bloom(img, lambda d: d.ellipse([860, 160, 1040, 340], fill=(255, 245, 215, 235)), blur_radius=24)
        draw = ImageDraw.Draw(img, "RGBA")
        for i in range(32):
            px = (i * 181 + 60) % w
            py = (i * 137 + 90) % (h - 200)
            draw.ellipse([px, py, px + 18, py + 10], fill=(255, 168, 208, 195))
    elif bg_id == "bg_sunny_beach":
        _draw_bloom(img, lambda d: d.ellipse([880, 110, 1050, 280], fill=(255, 242, 145, 235)), blur_radius=26)
        draw = ImageDraw.Draw(img, "RGBA")
        draw.rectangle([0, 730, w, 850], fill=(48, 192, 224, 225))
        draw.rectangle([0, 840, w, h], fill=(244, 208, 138, 255))
    elif bg_id == "bg_royal_hall":
        draw.polygon([(600, 80), (260, 880), (940, 880)], fill=(255, 218, 120, 38))
        draw.rectangle([0, 870, w, h], fill=(118, 22, 42, 230))
        draw.line([(0, 870), (w, 870)], fill=(245, 200, 75, 210), width=5)
    elif bg_id == "bg_neon_dojo":
        draw.rectangle([70, 320, 210, 880], fill=(20, 16, 36, 225), outline=(255, 60, 150, 185), width=4)
        draw.rectangle([990, 280, 1130, 880], fill=(20, 16, 36, 225), outline=(0, 230, 255, 185), width=4)
        draw.rectangle([0, 845, w, h], fill=(28, 22, 42, 240))

    # Bệ đứng có bóng mềm + vòng phép từ Stage 4-5
    ped = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(ped, "RGBA")
    pd.ellipse([240, 845, 960, 960], fill=(0, 0, 0, 135))
    img.alpha_composite(ped.filter(ImageFilter.GaussianBlur(12)))
    draw = ImageDraw.Draw(img, "RGBA")
    if stage >= 4:
        _draw_bloom(
            img,
            lambda d: d.ellipse([230, 848, 970, 956], outline=(*c1, 210), width=5),
            blur_radius=10,
        )
    if stage >= 5:
        _draw_bloom(
            img,
            lambda d: d.ellipse([180, 832, 1020, 974], outline=(*c2, 220), width=4),
            blur_radius=12,
        )


def _draw_aura_and_back(img: Image.Image, species: str, stage: int, equipped: dict, c1: Tuple[int, int, int], c2: Tuple[int, int, int]):
    """Layer 1: Hào quang Neon Bloom & Cánh / Áo choàng / Song Kiếm."""
    anchors = PET_ANCHORS[species][stage]
    aura_id = equipped.get("aura")
    if stage >= 5 or aura_id:
        ax, ay, ascale = anchors["aura"]
        aura_layer = Image.new("RGBA", (920, 920), (0, 0, 0, 0))
        col_a = (255, 110, 40) if aura_id == "aura_dragon_flame" else (
            (255, 130, 185) if aura_id == "aura_sakura_storm" else (
                (155, 65, 255) if aura_id == "aura_void_lightning" else c1
            )
        )
        col_b = (255, 220, 80) if aura_id == "aura_dragon_flame" else (
            (255, 215, 235) if aura_id == "aura_sakura_storm" else (
                (0, 235, 255) if aura_id == "aura_void_lightning" else c2
            )
        )

        def _paint_aura(ad: ImageDraw.ImageDraw):
            for r, alpha in ((390, 32), (310, 48), (235, 65)):
                ad.ellipse([460 - r, 460 - r, 460 + r, 460 + r], fill=(*col_a, alpha), outline=(*col_b, alpha + 90), width=5)
            # Vòng phép hình học bát giác
            oct_pts = [(460 + math.cos(math.radians(i * 45)) * 340, 460 + math.sin(math.radians(i * 45)) * 340) for i in range(8)]
            ad.polygon(oct_pts, outline=(*col_b, 175), width=4)
            for i in range(16):
                ang = math.radians(i * 22.5)
                px = 460 + math.cos(ang) * 355
                py = 460 + math.sin(ang) * 355
                _draw_sparkle(ad, px, py, 18 if i % 2 == 0 else 10, (*col_b, 235))

        _draw_bloom(aura_layer, _paint_aura, blur_radius=18)
        _paste_anchored(img, aura_layer, (ax, ay, ascale))

    back_id = equipped.get("back")
    if stage >= 4 and back_id:
        b_layer = Image.new("RGBA", (920, 620), (0, 0, 0, 0))
        bd = ImageDraw.Draw(b_layer, "RGBA")
        cx = 460
        if back_id == "back_angel_wings":
            def _paint_aw(d: ImageDraw.ImageDraw):
                for side in (-1, 1):
                    sx = cx + side * 105
                    outer = _bezier((sx, 270), (sx + side * 165, 55), (sx + side * 310, 45), (sx + side * 375, 115)) + _bezier(
                        (sx + side * 375, 115), (sx + side * 310, 295), (sx + side * 195, 385), (sx, 360)
                    )
                    d.polygon(outer, fill=(242, 248, 255, 185), outline=(185, 220, 255, 235), width=5)
                    inner = _bezier((sx, 295), (sx + side * 125, 145), (sx + side * 235, 145), (sx + side * 275, 235))
                    d.line(inner, fill=(255, 255, 255, 210), width=7)
            _draw_bloom(b_layer, _paint_aw, blur_radius=12)
        elif back_id == "back_demon_wings":
            def _paint_dw(d: ImageDraw.ImageDraw):
                for side in (-1, 1):
                    sx = cx + side * 95
                    pts = _bezier((sx, 270), (sx + side * 165, 50), (sx + side * 320, 65), (sx + side * 375, 145)) + [
                        (sx + side * 290, 290), (sx + side * 205, 375), (sx + side * 115, 350)
                    ]
                    d.polygon(pts, fill=(48, 18, 72, 190), outline=(215, 75, 255, 240), width=6)
                    d.line([(sx, 285), (sx + side * 285, 275)], fill=(215, 85, 255, 175), width=4)
            _draw_bloom(b_layer, _paint_dw, blur_radius=12)
        elif back_id == "back_royal_cape":
            cape_pts = (
                [(325, 100), (595, 100)]
                + _bezier((595, 100), (725, 290), (765, 480), (750, 570))
                + [(460, 540), (170, 570)]
                + _bezier((170, 570), (155, 480), (195, 290), (325, 100))
            )
            bd.polygon(cape_pts, fill=(138, 18, 42, 225), outline=(245, 200, 75, 240), width=7)
            bd.polygon([(355, 118), (565, 118), (665, 535), (255, 535)], fill=(178, 26, 54, 185))
        elif back_id == "back_cyber_wings":
            # Cánh Hologram năng lượng bán trong suốt tỏa ra sau lưng, không đè cứng
            def _paint_cw(d: ImageDraw.ImageDraw):
                for side, col in ((-1, (0, 235, 255)), (1, (255, 65, 195))):
                    sx = cx + side * 115
                    d.polygon(
                        [(sx, 245), (sx + side * 345, 65), (sx + side * 305, 255), (sx + side * 45, 310)],
                        fill=(*col, 48),
                        outline=(*col, 235),
                        width=5,
                    )
                    d.polygon(
                        [(sx + side * 30, 315), (sx + side * 265, 250), (sx + side * 210, 395), (sx + side * 15, 365)],
                        fill=(*col, 38),
                        outline=(*col, 195),
                        width=4,
                    )
                    d.line([(sx, 265), (sx + side * 290, 125)], fill=(255, 255, 255, 175), width=3)
            _draw_bloom(b_layer, _paint_cw, blur_radius=14)
        elif back_id == "back_katana":
            for s in (-1, 1):
                x0, y0 = cx - s * 285, 510
                x1, y1 = cx + s * 285, 60
                bd.line([(x0, y0), (x1, y1)], fill=(36, 38, 48, 240), width=20)
                hx, hy = cx + s * 210, 140
                bd.line([(hx, hy), (x1, y1)], fill=(220, 45, 65, 245), width=24)
                bd.ellipse([hx - 20, hy - 20, hx + 20, hy + 20], fill=(245, 200, 65, 255), outline=(20, 22, 32, 255), width=5)

        _paste_anchored(img, b_layer, anchors["back"])


def _draw_limbs(
    img: Image.Image,
    stage: int,
    body_cy: int,
    body_w: int,
    body_h: int,
    fill_rgb: Tuple[int, int, int],
    outline: Tuple[int, int, int, int],
    claw_col: Optional[Tuple[int, int, int, int]] = None,
):
    """Vẽ tay & chân có đổ khối cho Stage 2..5 (tọa độ 1200x1200)."""
    draw = ImageDraw.Draw(img, "RGBA")
    if stage == 2:
        _draw_shaded_ellipse(img, (600 - body_w - 28, body_cy - 28, 600 - body_w + 28, body_cy + 28), fill_rgb, outline, 6)
        _draw_shaded_ellipse(img, (600 + body_w - 28, body_cy - 28, 600 + body_w + 28, body_cy + 28), fill_rgb, outline, 6)
        _draw_shaded_ellipse(img, (528, body_cy + body_h - 28, 588, body_cy + body_h + 20), fill_rgb, outline, 6)
        _draw_shaded_ellipse(img, (612, body_cy + body_h - 28, 672, body_cy + body_h + 20), fill_rgb, outline, 6)
        return

    arm_w = 48 if stage == 3 else (60 if stage == 4 else 68)
    arm_len = 108 if stage == 3 else (136 if stage == 4 else 148)
    sx_l = 600 - body_w + 12
    sx_r = 600 + body_w - 12
    sy = body_cy - body_h + 44

    sh_rgb = _darken(fill_rgb, 0.25)
    draw.polygon([(sx_l, sy), (sx_l - arm_w - 24, sy + arm_len - 24), (sx_l - arm_w + 24, sy + arm_len), (sx_l + 12, sy + 48)], fill=(*sh_rgb, 255), outline=outline, width=7)
    draw.polygon([(sx_r, sy), (sx_r + arm_w + 24, sy + arm_len - 24), (sx_r + arm_w - 24, sy + arm_len), (sx_r - 12, sy + 48)], fill=(*sh_rgb, 255), outline=outline, width=7)

    leg_top = body_cy + body_h - 36
    leg_bot = body_cy + body_h + (48 if stage == 3 else 68)
    draw.rounded_rectangle([508, leg_top, 576, leg_bot], radius=28, fill=(*fill_rgb, 255), outline=outline, width=7)
    draw.rounded_rectangle([624, leg_top, 692, leg_bot], radius=28, fill=(*fill_rgb, 255), outline=outline, width=7)

    if stage >= 4 and claw_col:
        for cx in (524, 544, 564, 636, 656, 676):
            draw.polygon([(cx - 6, leg_bot - 4), (cx + 6, leg_bot - 4), (cx, leg_bot + 14)], fill=claw_col, outline=outline, width=2)


def _draw_body(img: Image.Image, species: str, stage: int, level: int, c1: Tuple[int, int, int], c2: Tuple[int, int, int]):
    """Layer 2 (1200x1200): Thân hình 2.5D Cel-Shaded qua 5 giai đoạn cho 4 loài."""
    draw = ImageDraw.Draw(img, "RGBA")
    outline = (18, 20, 30, 255)

    if stage == 1:
        # Trứng 3D + vết nứt phát sáng Bloom từ Lv.3
        _draw_shaded_ellipse(img, (410, 350, 790, 830), c1, outline, width=9)
        draw = ImageDraw.Draw(img, "RGBA")
        draw.arc([450, 450, 750, 660], start=15, end=165, fill=(*c2, 235), width=14)
        if level >= 3:
            crack = [(580, 430), (624, 496), (576, 550), (636, 610), (596, 664)]
            _draw_bloom(img, lambda d: d.line(crack, fill=(255, 245, 160, 255), width=10), blur_radius=12)
        return

    if species == "royal_slime":
        scale = {2: 0.72, 3: 0.88, 4: 1.02, 5: 1.12}[stage]
        rx, ry = int(210 * scale), int(176 * scale)
        cx, cy = 600, 656
        _draw_shaded_ellipse(img, (cx - rx, cy - ry, cx + rx, cy + ry), c1, outline, width=8, alpha=225)
        draw = ImageDraw.Draw(img, "RGBA")
        if stage >= 3:
            _draw_bloom(
                img,
                lambda d: d.polygon([(600, cy - 44), (644, cy + 8), (600, cy + 56), (556, cy + 8)], fill=(*c2, 225), outline=(255, 255, 255, 210), width=4),
                blur_radius=10,
            )
            draw = ImageDraw.Draw(img, "RGBA")
        if stage >= 4:
            draw.polygon([(524, cy - ry + 16), (548, cy - ry - 56), (588, cy - ry - 12), (600, cy - ry - 76), (612, cy - ry - 12), (652, cy - ry - 56), (676, cy - ry + 16)], fill=(255, 212, 65, 255), outline=outline, width=6)
            _draw_shaded_ellipse(img, (270, 630, 350, 702), c1, outline, width=6, alpha=210)
            _draw_shaded_ellipse(img, (850, 630, 930, 702), c2, outline, width=6, alpha=210)
        if stage >= 5:
            _draw_bloom(
                img,
                lambda d: [d.ellipse([ox - 20, oy - 20, ox + 20, oy + 20], fill=(255, 235, 145, 245)) for ox, oy in ((310, 460), (890, 460), (370, 340), (830, 340))],
                blur_radius=12,
            )
        return

    head_r = {2: 140, 3: 128, 4: 124, 5: 128}[stage]
    head_cy = {2: 556, 3: 476, 4: 428, 5: 412}[stage]
    body_w = {2: 92, 3: 108, 4: 132, 5: 144}[stage]
    body_h = {2: 88, 3: 136, 4: 168, 5: 180}[stage]
    body_cy = head_cy + head_r + body_h - 36

    if species == "cyber_cat":
        body_rgb = (48, 58, 86)
        if stage == 2:
            tail = _bezier((600 + body_w - 10, body_cy + 24), (720, body_cy - 10), (770, body_cy - 60), (784, body_cy - 92))
            draw.line(tail, fill=(*c1, 255), width=18)
        elif stage == 3:
            tail = _bezier((600 + body_w - 10, body_cy + 32), (780, body_cy - 20), (840, body_cy - 100), (860, body_cy - 156))
            _draw_bloom(img, lambda d: d.line(tail, fill=(*c1, 255), width=22), blur_radius=10)
        else:
            t_r = _bezier((600 + body_w - 16, body_cy + 36), (800, body_cy - 24), (875, body_cy - 120), (896, body_cy - 190))
            _draw_bloom(img, lambda d: (d.line(t_r, fill=(*c1, 255), width=24), d.polygon([(896, body_cy - 190), (950, body_cy - 270), (864, body_cy - 230)], fill=(*c2, 255))), blur_radius=12)
            if stage >= 5:
                t_l = _bezier((600 - body_w + 16, body_cy + 36), (400, body_cy - 24), (325, body_cy - 120), (304, body_cy - 190))
                _draw_bloom(img, lambda d: (d.line(t_l, fill=(*c2, 255), width=22), d.polygon([(304, body_cy - 190), (250, body_cy - 270), (336, body_cy - 230)], fill=(*c1, 255))), blur_radius=12)

        _draw_limbs(img, stage, body_cy, body_w, body_h, body_rgb, outline, claw_col=(*c2, 255))
        _draw_shaded_ellipse(img, (600 - body_w, body_cy - body_h, 600 + body_w, body_cy + body_h), body_rgb, outline, width=8)
        _draw_bloom(img, lambda d: d.polygon([(600, body_cy - 68), (652, body_cy - 8), (600, body_cy + 52), (548, body_cy - 8)], fill=(*c1, 235)), blur_radius=10)

        draw = ImageDraw.Draw(img, "RGBA")
        ear_h = 52 if stage == 2 else (84 if stage == 3 else 112)
        draw.polygon([(484, head_cy - 56), (444, head_cy - head_r - ear_h), (552, head_cy - head_r + 24)], fill=(*body_rgb, 255), outline=outline, width=8)
        draw.polygon([(716, head_cy - 56), (756, head_cy - head_r - ear_h), (648, head_cy - head_r + 24)], fill=(*body_rgb, 255), outline=outline, width=8)
        draw.polygon([(492, head_cy - 72), (466, head_cy - head_r - ear_h + 36), (536, head_cy - head_r + 28)], fill=(*c1, 240))
        draw.polygon([(708, head_cy - 72), (734, head_cy - head_r - ear_h + 36), (664, head_cy - head_r + 28)], fill=(*c1, 240))
        _draw_shaded_ellipse(img, (600 - head_r, head_cy - head_r, 600 + head_r, head_cy + head_r), body_rgb, outline, width=8)
        if stage >= 4:
            _draw_bloom(
                img,
                lambda d: (
                    d.line([(492, head_cy + 20), (524, head_cy + 32)], fill=(*c2, 245), width=7),
                    d.line([(708, head_cy + 20), (676, head_cy + 32)], fill=(*c2, 245), width=7),
                    d.polygon([(600, head_cy - 96), (620, head_cy - 60), (600, head_cy - 36), (580, head_cy - 60)], fill=(*c2, 255)),
                ),
                blur_radius=8,
            )

    elif species == "mini_dragon":
        body_rgb = _blend((38, 130, 96), c1, 0.45)
        belly_col = (250, 224, 146, 255)
        tail_x = 810 if stage == 2 else (880 if stage == 3 else 944)
        draw.polygon([(600 + body_w - 28, body_cy + 48), (tail_x, body_cy + 72), (tail_x + 36, body_cy - 32), (600 + body_w - 16, body_cy - 8)], fill=(*_darken(body_rgb, 0.18), 255), outline=outline, width=8)
        if stage >= 4:
            draw.polygon([(tail_x + 16, body_cy - 20), (tail_x + 68, body_cy - 68), (tail_x + 4, body_cy - 56)], fill=(245, 200, 75, 255), outline=outline, width=5)

        if stage >= 3:
            w_span = {3: 148, 4: 236, 5: 290}[stage]
            w_top = {3: 150, 4: 240, 5: 290}[stage]
            for side in (-1, 1):
                sx = 600 + side * 100
                wing_pts = _bezier((sx, body_cy - 52), (sx + side * int(w_span * 0.55), body_cy - w_top), (sx + side * w_span, body_cy - int(w_top * 0.85)), (sx + side * w_span, body_cy - w_top + 60)) + [
                    (sx + side * (w_span - 48), body_cy + 32)
                ]
                draw.polygon(wing_pts, fill=(*c2, 235), outline=outline, width=7)
                if stage >= 4:
                    draw.line([(sx, body_cy - 52), (sx + side * (w_span - 16), body_cy - w_top + 76)], fill=outline, width=6)

        _draw_limbs(img, stage, body_cy, body_w, body_h, body_rgb, outline, claw_col=(250, 224, 146, 255))
        _draw_shaded_ellipse(img, (600 - body_w, body_cy - body_h, 600 + body_w, body_cy + body_h), body_rgb, outline, width=8)
        draw = ImageDraw.Draw(img, "RGBA")
        draw.ellipse([600 - body_w + 32, body_cy - body_h + 32, 600 + body_w - 32, body_cy + body_h - 16], fill=belly_col)
        if stage >= 4:
            for vy in range(body_cy - body_h + 72, body_cy + body_h - 48, 48):
                draw.arc([600 - body_w + 52, vy, 600 + body_w - 52, vy + 36], start=10, end=170, fill=(210, 168, 84, 225), width=6)

        horn_h = {2: 36, 3: 72, 4: 108, 5: 132}[stage]
        draw.polygon([(512, head_cy - head_r + 40), (460, head_cy - head_r - horn_h), (552, head_cy - head_r + 12)], fill=(245, 200, 85, 255), outline=outline, width=6)
        draw.polygon([(688, head_cy - head_r + 40), (740, head_cy - head_r - horn_h), (648, head_cy - head_r + 12)], fill=(245, 200, 85, 255), outline=outline, width=6)
        if stage >= 5:
            draw.polygon([(476, head_cy - head_r + 72), (390, head_cy - head_r - 44), (496, head_cy - head_r + 40)], fill=(255, 165, 60, 255), outline=outline, width=6)
            draw.polygon([(724, head_cy - head_r + 72), (810, head_cy - head_r - 44), (704, head_cy - head_r + 40)], fill=(255, 165, 60, 255), outline=outline, width=6)

        _draw_shaded_ellipse(img, (600 - head_r, head_cy - head_r, 600 + head_r, head_cy + head_r), body_rgb, outline, width=8)
        if stage >= 4:
            _draw_bloom(
                img,
                lambda d: d.polygon([(600, head_cy - 100), (624, head_cy - 68), (600, head_cy - 40), (576, head_cy - 68)], fill=(*c2, 255), outline=(255, 240, 160, 255), width=4),
                blur_radius=10,
            )

    else:
        fur_rgb = _blend((240, 128, 56), c1, 0.25)
        tail_count = 1 if stage == 2 else (3 if stage <= 4 else 5)
        tail_len = {2: 230, 3: 290, 4: 340, 5: 380}[stage]
        for ti in range(tail_count):
            ang = math.radians(-55 + (ti - (tail_count - 1) / 2) * 28)
            tx = 600 + int(math.sin(ang) * tail_len) + (56 if tail_count == 1 else 0)
            ty = body_cy - int(math.cos(ang) * (tail_len * 0.68)) + 30
            t_pts = _bezier((600, body_cy + 36), (600 + (tx - 600) * 0.4, body_cy - 40), (600 + (tx - 600) * 0.8, ty + 40), (tx, ty))
            draw.line(t_pts, fill=(*_darken(fur_rgb, 0.12), 255), width=48 if stage <= 3 else 56)
            draw.ellipse([tx - 32, ty - 32, tx + 32, ty + 32], fill=(255, 245, 232, 255), outline=outline, width=4)

        _draw_limbs(img, stage, body_cy, body_w, body_h, fur_rgb, outline)
        _draw_shaded_ellipse(img, (600 - body_w, body_cy - body_h, 600 + body_w, body_cy + body_h), fur_rgb, outline, width=8)
        draw = ImageDraw.Draw(img, "RGBA")
        draw.ellipse([500, head_cy + head_r - 44, 700, head_cy + head_r + 72], fill=(255, 245, 232, 255), outline=outline, width=6)

        ear_h = {2: 56, 3: 84, 4: 108, 5: 120}[stage]
        draw.polygon([(476, head_cy - 56), (436, head_cy - head_r - ear_h), (548, head_cy - head_r + 24)], fill=(*fur_rgb, 255), outline=outline, width=8)
        draw.polygon([(724, head_cy - 56), (764, head_cy - head_r - ear_h), (652, head_cy - head_r + 24)], fill=(*fur_rgb, 255), outline=outline, width=8)
        _draw_shaded_ellipse(img, (600 - head_r, head_cy - head_r, 600 + head_r, head_cy + head_r), fur_rgb, outline, width=8)
        if stage >= 4:
            _draw_bloom(img, lambda d: d.polygon([(600, head_cy - 100), (620, head_cy - 64), (600, head_cy - 40), (580, head_cy - 64)], fill=(255, 95, 115, 245)), blur_radius=8)


def _draw_face(img: Image.Image, species: str, stage: int, expression: str, c1: Tuple[int, int, int]):
    """Layer 3 (1200x1200): Mắt Anime 3 lớp + má hồng mềm + lông mày uy nghiêm."""
    if stage == 1:
        return
    draw = ImageDraw.Draw(img, "RGBA")
    cy = 652 if species == "royal_slime" else {2: 556, 3: 476, 4: 428, 5: 412}[stage]
    lx, rx = 544, 656

    if expression == "sleepy":
        draw.arc([lx - 28, cy - 16, lx + 28, cy + 24], start=0, end=180, fill=(20, 22, 30, 255), width=8)
        draw.arc([rx - 28, cy - 16, rx + 28, cy + 24], start=0, end=180, fill=(20, 22, 30, 255), width=8)
        draw.ellipse([584, cy + 36, 616, cy + 64], fill=(220, 95, 115, 255))
        draw.text((732, cy - 104), "Zzz", font=get_font(44, bold=True), fill=(210, 225, 255, 235))
        return

    if expression == "hungry":
        draw.line([(lx - 24, cy - 16), (lx + 20, cy + 4), (lx - 24, cy + 20)], fill=(20, 22, 30, 255), width=8)
        draw.line([(rx + 24, cy - 16), (rx - 20, cy + 4), (rx + 24, cy + 20)], fill=(20, 22, 30, 255), width=8)
        draw.arc([568, cy + 44, 632, cy + 76], start=180, end=360, fill=(20, 22, 30, 255), width=8)
        return

    # Mắt 3 lớp có tròng mắt màu sắc + đồng tử + 2 đốm sáng
    eye_r = 28 if stage == 2 else 25
    iris_col = _lighten(c1, 0.15)
    for ex in (lx, rx):
        draw.ellipse([ex - eye_r - 3, cy - eye_r - 3, ex + eye_r + 3, cy + eye_r + 3], fill=(248, 250, 255, 255), outline=(18, 20, 30, 255), width=5)
        draw.ellipse([ex - eye_r + 4, cy - eye_r + 4, ex + eye_r - 4, cy + eye_r - 4], fill=(*iris_col, 255))
        draw.ellipse([ex - int(eye_r * 0.55), cy - int(eye_r * 0.55), ex + int(eye_r * 0.55), cy + int(eye_r * 0.55)], fill=(18, 20, 32, 255))
        draw.ellipse([ex - 13, cy - 16, ex - 1, cy - 4], fill=(255, 255, 255, 255))
        draw.ellipse([ex + 4, cy + 6, ex + 12, cy + 14], fill=(255, 255, 255, 230))

    if stage >= 4:
        draw.line([(lx - 32, cy - 44), (lx + 24, cy - 32)], fill=(20, 22, 32, 255), width=8)
        draw.line([(rx + 32, cy - 44), (rx - 24, cy - 32)], fill=(20, 22, 32, 255), width=8)

    if expression == "happy":
        blush = Image.new("RGBA", img.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(blush, "RGBA")
        bd.ellipse([lx - 54, cy + 20, lx - 18, cy + 44], fill=(255, 115, 150, 175))
        bd.ellipse([rx + 18, cy + 20, rx + 54, cy + 44], fill=(255, 115, 150, 175))
        img.alpha_composite(blush.filter(ImageFilter.GaussianBlur(8)))
        draw = ImageDraw.Draw(img, "RGBA")
        draw.arc([568, cy + 24, 632, cy + 64], start=0, end=180, fill=(20, 22, 30, 255), width=8)
    else:
        draw.line([(580, cy + 44), (620, cy + 44)], fill=(20, 22, 30, 255), width=8)


def _draw_outfit(img: Image.Image, species: str, stage: int, equipped: dict, c1: Tuple[int, int, int]):
    """Layer 4: Khăn choàng / Vòng cổ / Lõi năng lượng gọn nhẹ ôm cổ (không che thân thú AI)."""
    outfit_id = equipped.get("outfit")
    if stage < 3 or not outfit_id:
        return

    o_layer = Image.new("RGBA", (320, 160), (0, 0, 0, 0))
    od = ImageDraw.Draw(o_layer, "RGBA")
    outline = (18, 20, 32, 245)

    def _draw_scarf(main_col: Tuple[int, int, int], trim_col: Tuple[int, int, int]):
        # Bóng đổ mềm dưới khăn
        sh = Image.new("RGBA", o_layer.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh, "RGBA")
        sd.chord([54, 42, 266, 118], start=0, end=180, fill=(0, 0, 0, 110))
        o_layer.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
        d = ImageDraw.Draw(o_layer, "RGBA")
        # Vòng khăn ôm cổ cong tự nhiên
        collar_pts = _bezier((52, 54), (110, 96), (210, 96), (268, 54)) + _bezier((268, 54), (215, 70), (105, 70), (52, 54))
        d.polygon(collar_pts, fill=(*main_col, 245), outline=outline, width=4)
        # Đuôi khăn bay nhẹ lệch phải
        tail_pts = [(195, 74), (242, 70), (262, 134), (222, 142)]
        d.polygon(tail_pts, fill=(*main_col, 240), outline=outline, width=4)
        d.line([(234, 74), (251, 134)], fill=(*trim_col, 230), width=4)
        # Viền sáng trên khăn
        hi_pts = _bezier((64, 58), (116, 86), (204, 86), (256, 58))
        d.line(hi_pts, fill=(*trim_col, 220), width=4)

    if outfit_id == "outfit_cyber_armor":
        # Vòng cổ công nghệ + lõi năng lượng lục giác phát sáng Neon Cyan
        _draw_scarf((20, 32, 58), (0, 230, 255))
        _draw_bloom(
            o_layer,
            lambda d: d.polygon([(160, 64), (184, 84), (160, 108), (136, 84)], fill=(0, 240, 255, 250), outline=(255, 255, 255, 230), width=3),
            blur_radius=8,
        )
    elif outfit_id == "outfit_royal_vest":
        _draw_scarf((138, 22, 46), (245, 200, 75))
        od = ImageDraw.Draw(o_layer, "RGBA")
        od.ellipse([142, 68, 178, 104], fill=(245, 200, 75, 255), outline=outline, width=4)
        od.ellipse([151, 77, 169, 95], fill=(220, 40, 68, 255))
    elif outfit_id == "outfit_tuxedo":
        # Nơ bướm điệp viên đen + viền cổ trắng gọn gàng
        od.polygon([(112, 66), (160, 86), (208, 66), (208, 104), (160, 88), (112, 104)], fill=(215, 38, 60, 250), outline=outline, width=4)
        od.ellipse([148, 74, 172, 98], fill=(245, 48, 72, 255), outline=outline, width=3)
    elif outfit_id == "outfit_mage_robe":
        _draw_scarf((68, 42, 132), (245, 200, 75))
        _draw_bloom(o_layer, lambda d: d.ellipse([142, 68, 178, 104], fill=(95, 225, 255, 245), outline=(245, 200, 75, 255), width=4), blur_radius=8)
    elif outfit_id == "outfit_cloud_robe":
        _draw_scarf((26, 28, 42), (225, 55, 78))
    elif outfit_id == "outfit_samurai":
        _draw_scarf((152, 28, 38), (245, 200, 75))
        od = ImageDraw.Draw(o_layer, "RGBA")
        od.polygon([(142, 72), (178, 72), (170, 106), (150, 106)], fill=(245, 200, 75, 250), outline=outline, width=4)
    elif outfit_id == "outfit_bomber":
        _draw_scarf((185, 42, 62), (245, 245, 250))
    elif outfit_id == "outfit_hoodie":
        _draw_scarf((44, 48, 66), c1)
    elif outfit_id == "outfit_tanktop":
        # Dây chuyền vàng + mặt trời mùa hè
        chain = _bezier((80, 56), (125, 96), (195, 96), (240, 56))
        od.line(chain, fill=(245, 200, 75, 250), width=6)
        od.ellipse([144, 74, 176, 106], fill=(255, 210, 65, 255), outline=outline, width=4)

    _paste_anchored(img, o_layer, PET_ANCHORS[species][stage]["outfit"])


def _draw_headwear(img: Image.Image, species: str, stage: int, equipped: dict):
    """Layer 5 (2x): Mũ / Đội đầu sắc nét + đổ bóng mềm & highlight ánh sáng."""
    hat_id = equipped.get("headwear")
    if stage < 2 or not hat_id:
        return
    h_layer = Image.new("RGBA", (400, 280), (0, 0, 0, 0))
    hd = ImageDraw.Draw(h_layer, "RGBA")
    outline = (20, 22, 32, 245)
    if hat_id == "hat_cap_back":
        hd.pieslice([96, 76, 304, 236], start=180, end=360, fill=(215, 52, 68, 255), outline=outline, width=6)
        hd.pieslice([116, 86, 250, 180], start=195, end=310, fill=(245, 110, 125, 130))
        hd.rounded_rectangle([226, 136, 348, 166], radius=10, fill=(32, 36, 50, 255), outline=outline, width=5)
    elif hat_id == "hat_gaming_headset":
        # Vòng đeo mảnh ôm sát đầu + ốp tai Neon Bloom tinh tế
        hd.arc([78, 64, 322, 242], start=190, end=350, fill=(36, 40, 56, 255), width=14)
        hd.arc([84, 70, 316, 236], start=205, end=335, fill=(130, 145, 175, 165), width=4)
        _draw_bloom(
            h_layer,
            lambda d: (
                d.rounded_rectangle([58, 138, 102, 218], radius=18, fill=(24, 32, 52, 245), outline=(0, 230, 255, 255), width=5),
                d.rounded_rectangle([298, 138, 342, 218], radius=18, fill=(24, 32, 52, 245), outline=(255, 65, 185, 255), width=5),
                d.ellipse([70, 162, 90, 194], fill=(0, 235, 255, 240)),
                d.ellipse([310, 162, 330, 194], fill=(255, 70, 190, 240)),
            ),
            blur_radius=8,
        )
    elif hat_id == "hat_gold_crown":
        hd.polygon([(104, 192), (118, 86), (168, 146), (200, 60), (232, 146), (282, 86), (296, 192)], fill=(255, 206, 62, 255), outline=outline, width=6)
        hd.polygon([(122, 184), (130, 114), (168, 156), (200, 84), (200, 184)], fill=(255, 232, 125, 135))
        hd.ellipse([186, 126, 214, 154], fill=(230, 45, 75, 255), outline=outline, width=3)
    elif hat_id == "hat_ninja_band":
        hd.rounded_rectangle([76, 130, 324, 182], radius=14, fill=(28, 34, 52, 250), outline=outline, width=5)
        hd.rounded_rectangle([146, 136, 254, 176], radius=8, fill=(205, 215, 230, 255), outline=outline, width=4)
    elif hat_id == "hat_duck":
        hd.ellipse([108, 68, 292, 196], fill=(255, 222, 65, 255), outline=outline, width=6)
        hd.ellipse([160, 148, 240, 188], fill=(255, 140, 40, 255), outline=outline, width=5)
    elif hat_id == "hat_wizard":
        hd.ellipse([54, 164, 346, 226], fill=(54, 38, 108, 255), outline=(245, 200, 75, 255), width=5)
        hd.polygon([(114, 184), (286, 184), (216, 36)], fill=(68, 46, 134, 255), outline=outline, width=6)
        hd.rectangle([128, 152, 272, 178], fill=(245, 200, 75, 255))
    elif hat_id == "hat_oni_horns":
        hd.polygon([(94, 196), (70, 80), (148, 164)], fill=(225, 45, 65, 255), outline=outline, width=6)
        hd.polygon([(306, 196), (330, 80), (252, 164)], fill=(225, 45, 65, 255), outline=outline, width=6)
        hd.ellipse([172, 136, 228, 192], fill=(245, 200, 75, 255), outline=outline, width=5)
    elif hat_id == "hat_cat_ears_rgb":
        hd.arc([88, 92, 312, 240], start=185, end=355, fill=(32, 36, 52, 255), width=12)
        _draw_bloom(
            h_layer,
            lambda d: (
                d.polygon([(92, 148), (72, 48), (160, 114)], fill=(32, 36, 52, 245), outline=(0, 235, 255, 255), width=6),
                d.polygon([(308, 148), (328, 48), (240, 114)], fill=(32, 36, 52, 245), outline=(255, 65, 195, 255), width=6),
            ),
            blur_radius=8,
        )
    elif hat_id == "hat_halo_angel":
        _draw_bloom(h_layer, lambda d: d.ellipse([96, 44, 304, 112], fill=(0, 0, 0, 0), outline=(255, 232, 120, 255), width=10), blur_radius=10)
    _paste_anchored(img, h_layer, PET_ANCHORS[species][stage]["headwear"])


def _draw_face_and_held(img: Image.Image, species: str, stage: int, equipped: dict):
    """Layer 6 (2x): Kính có phản chiếu thủy tinh & Vật thể bay kèm (Floating Companion)."""
    face_id = equipped.get("face")
    if stage >= 3 and face_id:
        f_layer = Image.new("RGBA", (340, 160), (0, 0, 0, 0))
        fd = ImageDraw.Draw(f_layer, "RGBA")
        if face_id == "face_sunglasses":
            fd.rounded_rectangle([38, 38, 152, 102], radius=16, fill=(18, 22, 34, 205), outline=(245, 200, 75, 255), width=5)
            fd.rounded_rectangle([188, 38, 302, 102], radius=16, fill=(18, 22, 34, 205), outline=(245, 200, 75, 255), width=5)
            fd.line([(56, 86), (112, 48)], fill=(255, 255, 255, 125), width=6)
            fd.line([(206, 86), (262, 48)], fill=(255, 255, 255, 125), width=6)
            fd.line([(152, 60), (188, 60)], fill=(245, 200, 75, 255), width=6)
        elif face_id == "face_vr_visor":
            _draw_bloom(
                f_layer,
                lambda d: (
                    d.rounded_rectangle([34, 34, 306, 110], radius=26, fill=(16, 26, 52, 195), outline=(0, 235, 255, 255), width=6),
                    d.line([(56, 72), (284, 72)], fill=(0, 235, 255, 235), width=6),
                ),
                blur_radius=8,
            )
        elif face_id == "face_ninja_mask":
            fd.polygon([(62, 66), (278, 66), (250, 150), (90, 150)], fill=(28, 32, 46, 235), outline=(14, 16, 24, 255), width=5)
        elif face_id == "face_thug_life":
            fd.rectangle([42, 44, 148, 86], fill=(12, 12, 16, 245))
            fd.rectangle([192, 44, 298, 86], fill=(12, 12, 16, 245))
            fd.rectangle([148, 52, 192, 68], fill=(12, 12, 16, 245))
            fd.rectangle([62, 56, 90, 68], fill=(255, 255, 255, 255))
            fd.rectangle([212, 56, 240, 68], fill=(255, 255, 255, 255))
        elif face_id == "face_monocle":
            fd.ellipse([192, 32, 284, 124], fill=(165, 225, 255, 75), outline=(245, 200, 75, 255), width=6)
            fd.line([(284, 84), (296, 150)], fill=(245, 200, 75, 255), width=4)
        elif face_id == "face_star_blush":
            bl = Image.new("RGBA", f_layer.size, (0, 0, 0, 0))
            bd = ImageDraw.Draw(bl, "RGBA")
            bd.ellipse([36, 72, 94, 116], fill=(255, 115, 165, 190))
            bd.ellipse([246, 72, 304, 116], fill=(255, 115, 165, 190))
            f_layer.alpha_composite(bl.filter(ImageFilter.GaussianBlur(8)))
            fd = ImageDraw.Draw(f_layer, "RGBA")
            _draw_sparkle(fd, 64, 94, 20, (255, 230, 105, 245))
        _paste_anchored(img, f_layer, PET_ANCHORS[species][stage]["face"])

    held_id = equipped.get("held")
    if stage >= 4 and held_id:
        hl_layer = Image.new("RGBA", (240, 260), (0, 0, 0, 0))
        outline = (20, 22, 32, 245)
        # Đĩa hào quang bay lơ lửng dưới vật thể
        plat_col = (
            (0, 225, 255) if held_id in ("held_gamepad", "held_sword") else
            (245, 200, 75) if held_id in ("held_scepter", "held_lantern") else
            (255, 95, 185)
        )
        _draw_bloom(
            hl_layer,
            lambda d: d.ellipse([48, 196, 192, 236], fill=(*plat_col, 45), outline=(*plat_col, 210), width=4),
            blur_radius=8,
        )
        hd = ImageDraw.Draw(hl_layer, "RGBA")
        if held_id == "held_gamepad":
            hd.rounded_rectangle([32, 82, 208, 170], radius=32, fill=(30, 36, 56, 250), outline=(0, 225, 255, 255), width=5)
            hd.ellipse([56, 106, 88, 138], fill=(0, 225, 255, 255))
            hd.ellipse([148, 102, 172, 126], fill=(255, 70, 165, 255))
        elif held_id == "held_boba":
            hd.polygon([(78, 76), (162, 76), (146, 190), (94, 190)], fill=(245, 225, 195, 245), outline=outline, width=5)
            hd.line([(120, 24), (120, 76)], fill=(255, 90, 140, 255), width=9)
            for bx, by in ((102, 162), (120, 170), (136, 158)):
                hd.ellipse([bx - 8, by - 8, bx + 8, by + 8], fill=(30, 24, 24, 255))
        elif held_id == "held_scepter":
            hd.line([(120, 206), (120, 68)], fill=(245, 200, 75, 255), width=12)
            _draw_bloom(hl_layer, lambda d: d.ellipse([86, 26, 154, 94], fill=(90, 215, 255, 245), outline=(255, 240, 150, 255), width=5), blur_radius=10)
        elif held_id == "held_sword":
            _draw_bloom(hl_layer, lambda d: d.polygon([(108, 22), (132, 22), (136, 148), (104, 148)], fill=(0, 235, 255, 245), outline=(255, 255, 255, 255), width=4), blur_radius=10)
            hd = ImageDraw.Draw(hl_layer, "RGBA")
            hd.rectangle([86, 148, 154, 168], fill=(245, 200, 75, 255), outline=outline, width=4)
            hd.rectangle([110, 168, 130, 206], fill=(42, 46, 62, 255))
        elif held_id == "held_mic":
            hd.line([(120, 202), (120, 102)], fill=(38, 42, 56, 255), width=12)
            _draw_bloom(hl_layer, lambda d: d.ellipse([88, 46, 152, 110], fill=(225, 230, 245, 255), outline=(255, 70, 180, 255), width=5), blur_radius=8)
        elif held_id == "held_lantern":
            hd.line([(120, 24), (120, 62)], fill=(245, 200, 75, 255), width=6)
            _draw_bloom(hl_layer, lambda d: d.ellipse([72, 60, 168, 174], fill=(235, 65, 75, 245), outline=(245, 200, 75, 255), width=5), blur_radius=10)
        _paste_anchored(img, hl_layer, PET_ANCHORS[species][stage]["held"])


def _draw_ui_overlay(img: Image.Image, pet: Dict[str, Any], stage_name: str, level: int, c1: Tuple[int, int, int]):
    """Layer 7 (2x): HUD Glassmorphism siêu nét."""
    draw = ImageDraw.Draw(img, "RGBA")
    font_title = get_font(48, bold=True)
    font_sub = get_font(34, bold=True)
    font_bar = get_font(30, bold=True)

    draw.rounded_rectangle([60, 40, 1140, 164], radius=36, fill=(14, 16, 28, 205), outline=(*c1, 220), width=4)
    sp_name = PET_SPECIES.get(pet["species"], {}).get("name", pet["species"])
    draw.text((96, 54), f"{pet['name']} ({sp_name})", font=font_title, fill=(255, 255, 255, 255))
    draw.text((96, 112), f"Lv.{level} • {stage_name}", font=font_sub, fill=(255, 215, 110, 255))

    draw.rounded_rectangle([60, 1004, 1140, 1156], radius=36, fill=(14, 16, 28, 208), outline=(*c1, 195), width=4)
    hunger = max(0, min(100, int(pet.get("hunger", 80))))
    mood = max(0, min(100, int(pet.get("mood", 80))))

    draw.text((100, 1026), f"Độ No: {hunger}%", font=font_bar, fill=(255, 210, 140, 255))
    draw.rounded_rectangle([100, 1076, 560, 1116], radius=16, fill=(42, 46, 62, 255))
    if hunger > 0:
        draw.rounded_rectangle([100, 1076, 100 + int(460 * hunger / 100), 1116], radius=16, fill=(245, 155, 55, 255))

    draw.text((636, 1026), f"Độ Vui: {mood}%", font=font_bar, fill=(155, 235, 255, 255))
    draw.rounded_rectangle([636, 1076, 1100, 1116], radius=16, fill=(42, 46, 62, 255))
    if mood > 0:
        draw.rounded_rectangle([636, 1076, 636 + int(464 * mood / 100), 1116], radius=16, fill=(75, 210, 155, 255))


def render_pet_sprite_only(pet: Dict[str, Any], clan_color: str = "#5865F2", secondary_color: Optional[str] = None, size: int = 240) -> Image.Image:
    """Render riêng nhân vật Pet nền trong suốt để ghép lên Wallpaper Full HD."""
    c1 = hex_to_rgb(clan_color)
    c2 = hex_to_rgb(secondary_color) if secondary_color else _blend(c1, (255, 255, 255), 0.35)
    lvl_info = get_pet_level_info(int(pet.get("exp", 0)))
    stage = lvl_info["stage"]
    species = pet["species"]
    equipped = pet.get("equipped") or {}
    expr = compute_pet_expression(int(pet.get("hunger", 80)), int(pet.get("mood", 80)))

    canvas = Image.new("RGBA", (600 * SS, 600 * SS), (0, 0, 0, 0))
    _draw_aura_and_back(canvas, species, stage, equipped, c1, c2)
    if not _draw_sprite_layer(canvas, species, stage, expr, c1, outfit_id=equipped.get("outfit")):
        _draw_body(canvas, species, stage, lvl_info["level"], c1, c2)
        _draw_face(canvas, species, stage, expr, c1)
    _draw_outfit(canvas, species, stage, equipped, c1)
    _draw_headwear(canvas, species, stage, equipped)
    _draw_face_and_held(canvas, species, stage, equipped)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def generate_clan_pet_image(pet: Dict[str, Any], clan: Dict[str, Any]) -> io.BytesIO:
    """Render ảnh Pet 600x600 RGBA (từ 1200x1200 Supersampling) với Smart MD5 Cache."""
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

    hi_res = Image.new("RGBA", (600 * SS, 600 * SS), (0, 0, 0, 255))
    _draw_background(hi_res, equipped.get("background"), c1, c2, stage=stage)
    _draw_aura_and_back(hi_res, species, stage, equipped, c1, c2)
    if not _draw_sprite_layer(hi_res, species, stage, expr, c1, outfit_id=equipped.get("outfit")):
        _draw_body(hi_res, species, stage, level, c1, c2)
        _draw_face(hi_res, species, stage, expr, c1)
    _draw_outfit(hi_res, species, stage, equipped, c1)
    _draw_headwear(hi_res, species, stage, equipped)
    _draw_face_and_held(hi_res, species, stage, equipped)
    _draw_ui_overlay(hi_res, pet, lvl_info["stage_name"], level, c1)

    final_img = hi_res.resize((600, 600), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    final_img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()
    try:
        cache_path.write_bytes(raw_bytes)
    except Exception:
        pass
    buf.seek(0)
    return buf


def generate_clan_pet_preview_image(pet: Dict[str, Any], clan: Dict[str, Any], preview_item: Dict[str, Any]) -> io.BytesIO:
    """Render ảnh xem trước vật phẩm trong Cửa Hàng ở độ phân giải Supersampling 2x."""
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

    hi_res = Image.new("RGBA", (600 * SS, 600 * SS), (0, 0, 0, 255))
    _draw_background(hi_res, equipped.get("background"), c1, c2, stage=preview_stage)
    _draw_aura_and_back(hi_res, species, preview_stage, equipped, c1, c2)
    if not _draw_sprite_layer(hi_res, species, preview_stage, expr, c1, outfit_id=equipped.get("outfit")):
        _draw_body(hi_res, species, preview_stage, max(level, 3 if preview_stage == 1 else level), c1, c2)
        _draw_face(hi_res, species, preview_stage, expr, c1)
    _draw_outfit(hi_res, species, preview_stage, equipped, c1)
    _draw_headwear(hi_res, species, preview_stage, equipped)
    _draw_face_and_held(hi_res, species, preview_stage, equipped)

    stage_label = f"Xem trước (Stage {preview_stage})" if preview_stage > cur_stage else lvl_info["stage_name"]
    _draw_ui_overlay(hi_res, pet, stage_label, level, c1)

    final_img = hi_res.resize((600, 600), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    final_img.save(buf, format="PNG")
    buf.seek(0)
    return buf
