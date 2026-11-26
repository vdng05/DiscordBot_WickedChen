"""
Quản lý lưu trữ và phân giải hình ảnh (Logo / Banner) bền vững cho Băng Đảng.
Giải quyết triệt để lỗi link Discord CDN bị xóa sau khi dọn tin nhắn hoặc hết hạn sau 24 giờ.
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import discord

ASSETS_DIR = Path("./data/clan_assets")
LOCAL_PREFIX = "local://"
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB


def ensure_assets_dir() -> Path:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    return ASSETS_DIR


def _safe_ext(filename: str, content_type: str = "") -> str:
    lower = (filename or "").lower()
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        if lower.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    if "gif" in content_type:
        return ".gif"
    return ".png"


async def save_clan_attachment(clan_id: int, image_type: str, attachment: discord.Attachment) -> str:
    """
    Tải tệp đính kèm từ Discord về lưu cục bộ tại data/clan_assets/
    và trả về URI nội bộ dạng `local://data/clan_assets/...`.
    """
    ensure_assets_dir()
    if attachment.size and attachment.size > MAX_UPLOAD_BYTES:
        raise ValueError("Dung lượng ảnh vượt quá giới hạn 8MB!")

    data = await attachment.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Dung lượng ảnh vượt quá giới hạn 8MB!")

    ext = _safe_ext(attachment.filename, attachment.content_type or "")

    # Xóa các file cũ cùng loại của clan này (tránh rác ổ đĩa nếu đổi đuôi .png -> .gif)
    for old_file in ASSETS_DIR.glob(f"clan_{clan_id}_{image_type}.*"):
        try:
            old_file.unlink()
        except Exception:
            pass

    target_path = ASSETS_DIR / f"clan_{clan_id}_{image_type}{ext}"
    await asyncio.to_thread(target_path.write_bytes, data)
    return f"{LOCAL_PREFIX}{target_path.as_posix()}"


def delete_local_asset(uri: Optional[str]) -> None:
    """Xóa tệp ảnh cục bộ nếu uri có tiền tố local://"""
    if not uri or not uri.startswith(LOCAL_PREFIX):
        return
    path = Path(uri[len(LOCAL_PREFIX):])
    if path.exists() and path.is_file():
        try:
            path.unlink()
        except Exception:
            pass


def resolve_local_asset_file(uri: Optional[str], attachment_name: str) -> Optional[discord.File]:
    """Nếu uri là local:// và file còn tồn tại trên đĩa, trả về discord.File tương ứng."""
    if not uri or not uri.startswith(LOCAL_PREFIX):
        return None
    path = Path(uri[len(LOCAL_PREFIX):])
    if path.exists() and path.is_file():
        return discord.File(fp=str(path), filename=attachment_name)
    return None


async def resolve_clan_logo(
    clan: Dict[str, Any],
    files: List[discord.File],
    fallback_to_default: bool = True
) -> Optional[str]:
    """
    Trả về URL hợp lệ cho `embed.set_thumbnail(url=...)`.
    - Nếu là `local://`: đính kèm file vào `files` và trả về `attachment://...`.
    - Nếu là `http(s)://`: trả về nguyên URL.
    - Nếu trống hoặc file local bị mất & `fallback_to_default=True`: sinh Logo Bát Giác mặc định.
    """
    logo_uri = clan.get("logo_url")
    if logo_uri:
        if logo_uri.startswith(LOCAL_PREFIX):
            ext = Path(logo_uri[len(LOCAL_PREFIX):]).suffix or ".png"
            fname = f"clan_logo{ext}"
            f = resolve_local_asset_file(logo_uri, fname)
            if f:
                files.append(f)
                return f"attachment://{fname}"
        elif logo_uri.startswith(("http://", "https://")):
            return logo_uri

    if fallback_to_default:
        from utils.canvas import generate_default_clan_logo
        logo_buf = await asyncio.to_thread(generate_default_clan_logo, clan)
        files.append(discord.File(fp=logo_buf, filename="default_logo.png"))
        return "attachment://default_logo.png"

    return None


async def resolve_clan_banner(
    clan: Dict[str, Any],
    files: List[discord.File],
    member_count: int = 1,
    leader_name: Optional[str] = None,
    fallback_to_default: bool = True
) -> Optional[str]:
    """
    Trả về URL hợp lệ cho `embed.set_image(url=...)`.
    - Nếu là `local://`: đính kèm file vào `files` và trả về `attachment://...`.
    - Nếu là `http(s)://`: trả về nguyên URL.
    - Nếu trống hoặc file local bị mất & `fallback_to_default=True`: sinh Banner Gaming mặc định.
    """
    banner_uri = clan.get("banner_url")
    if banner_uri:
        if banner_uri.startswith(LOCAL_PREFIX):
            ext = Path(banner_uri[len(LOCAL_PREFIX):]).suffix or ".png"
            fname = f"clan_banner{ext}"
            f = resolve_local_asset_file(banner_uri, fname)
            if f:
                files.append(f)
                return f"attachment://{fname}"
        elif banner_uri.startswith(("http://", "https://")):
            return banner_uri

    if fallback_to_default:
        from utils.canvas import generate_default_clan_banner
        banner_buf = await asyncio.to_thread(generate_default_clan_banner, clan, member_count, leader_name)
        files.append(discord.File(fp=banner_buf, filename="default_banner.png"))
        return "attachment://default_banner.png"

    return None
