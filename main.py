"""
Clan Discord Bot — Entry Point & Main Application Class
Kiến trúc Feature-Folder kế thừa từ tiêu chuẩn SosaGallery
Tích hợp SQLite bất đồng bộ (aiosqlite WAL Mode) & Discord.py v2.x
"""

import asyncio
import os
import signal
import sys
from pathlib import Path

# Đảm bảo mã hóa UTF-8 trên Windows console (tránh lỗi charmap cp1258 / UnicodeEncodeError)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import discord
from discord.ext import commands

from config import Config
from utils.logger import setup_logging
from utils.database import DatabaseManager
from utils.error_handler import global_app_command_error

# Khởi tạo logger hệ thống
logger = setup_logging("ClanBot")


class ClanBot(commands.Bot):
    """Lớp Bot chính kế thừa commands.Bot với cơ chế tự động nạp cogs, SQLite và quản lý tài nguyên"""

    def __init__(self, use_privileged_intents: bool = True, should_sync: bool = True):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True
        intents.voice_states = True
        if use_privileged_intents:
            intents.message_content = True
            intents.members = True

        super().__init__(
            command_prefix=Config.COMMAND_PREFIX,
            intents=intents,
            help_command=None,
            owner_ids=set(Config.OWNER_IDS) if Config.OWNER_IDS else None
        )

        # Database Manager Singleton
        self.db = DatabaseManager(Config.DB_PATH)
        self.use_privileged_intents = use_privileged_intents
        self.should_sync = should_sync

        # Quản lý bảng điều khiển đang mở của người dùng: user_id -> discord.Interaction
        # Tự động dismiss / xóa bảng cũ khi người dùng mở hoặc sử dụng tính năng khác
        self.active_user_panels: dict[int, discord.Interaction] = {}

    async def register_user_panel(self, user_id: int, interaction: discord.Interaction):
        """Đăng ký panel mới và tự động dismiss panel cũ của user nếu có để tránh đầy chat"""
        old_interaction = self.active_user_panels.get(user_id)
        if old_interaction and old_interaction != interaction:
            try:
                await old_interaction.delete_original_response()
            except Exception:
                pass
        self.active_user_panels[user_id] = interaction

    async def dismiss_user_panel(self, user_id: int):
        """Đóng và xóa bảng điều khiển của user nếu đang mở"""
        old_interaction = self.active_user_panels.pop(user_id, None)
        if old_interaction:
            try:
                await old_interaction.delete_original_response()
            except Exception:
                pass

    async def setup_hook(self):
        """Khởi động cơ sở dữ liệu SQLite, gắn error handler và tự động nạp toàn bộ cogs"""
        # 1. Khởi tạo cơ sở dữ liệu SQLite WAL mode
        await self.db.initialize()

        # 2. Gắn bộ xử lý lỗi tập trung cho toàn bộ Slash Commands
        self.tree.on_error = global_app_command_error

        # 3. Quét và nạp tất cả cogs
        logger.info("Đang tự động nạp các module Cogs...")
        cogs_dir = Config.BASE_DIR / "cogs"

        if cogs_dir.exists():
            for folder in sorted(cogs_dir.iterdir()):
                if folder.is_dir() and not folder.name.startswith(("_", ".")):
                    for file in sorted(folder.glob("*.py")):
                        if file.name.startswith("_"):
                            continue
                        # Module path dạng cogs.folder.filename
                        ext_path = f"cogs.{folder.name}.{file.stem}"
                        try:
                            await self.load_extension(ext_path)
                            logger.info(f"Đã nạp thành công Cog: {ext_path}")
                        except Exception as e:
                            logger.error(f"Lỗi khi nạp Cog {ext_path}: {e}", exc_info=True)

        # 4. Tự động đồng bộ Slash Commands nếu bật SYNC_ON_STARTUP
        if Config.SYNC_ON_STARTUP and self.should_sync:
            try:
                logger.info("Đang tự động đồng bộ Slash Commands với Discord Gateway...")
                synced = await self.tree.sync()
                logger.info(f"Đã đồng bộ thành công {len(synced)} Slash Commands toàn cầu!")
            except Exception as sync_err:
                logger.error(f"Lỗi khi đồng bộ Slash Commands: {sync_err}")

    async def on_ready(self):
        """Kích hoạt khi bot kết nối thành công đến Discord Gateway"""
        logger.info(f"Bot đã online thành công với tên: {self.user.name}#{self.user.discriminator} (ID: {self.user.id})")
        logger.info(f"Đang hoạt động trên {len(self.guilds)} server Discord.")

        # Đặt Rich Presence trực quan
        try:
            activity = discord.CustomActivity(name="🏰 Hệ Thống Băng Đảng | /clan hub")
            await self.change_presence(status=discord.Status.online, activity=activity)
        except Exception:
            pass


def ensure_token() -> str:
    """Kiểm tra và tự động hướng dẫn người dùng nhập Token nếu chưa có file .env"""
    token = Config.DISCORD_TOKEN.strip()
    if token:
        return token

    print("\n" + "=" * 65)
    print("🔑 CHƯA CÓ TOKEN BOT DISCORD!")
    print("=" * 65)
    print("Bot cần Bot Token từ https://discord.com/developers/applications")
    print("👉 Hãy dán Discord Bot Token của bạn vào đây rồi bấm Enter:")
    try:
        user_input = input("Token: ").strip().strip("'\"")
    except (EOFError, KeyboardInterrupt):
        return ""

    if user_input:
        env_file = Config.BASE_DIR / ".env"
        lines = []
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

        token_written = False
        new_lines = []
        for line in lines:
            if line.startswith("DISCORD_TOKEN="):
                new_lines.append(f"DISCORD_TOKEN={user_input}\n")
                token_written = True
            else:
                new_lines.append(line)
        if not token_written:
            new_lines.append(f"\nDISCORD_TOKEN={user_input}\n")

        with open(env_file, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        Config.DISCORD_TOKEN = user_input
        print("✅ Đã tự động lưu Token vào file .env! Đang kết nối Discord...")
        return user_input

    return ""


async def main():
    """Hàm khởi động chính của ứng dụng"""
    token = ensure_token()
    if not token:
        logger.warning("Không có Token. Quá trình khởi chạy dừng lại.")
        return

    # Khởi tạo Bot với đầy đủ quyền Privileged Intents
    bot = ClanBot(use_privileged_intents=True)

    # Bắt tín hiệu ngắt an toàn trên Linux/Windows
    if sys.platform != "win32":
        for s in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_event_loop().add_signal_handler(s, lambda: asyncio.create_task(bot.close()))

    try:
        await bot.start(token)
    except discord.errors.PrivilegedIntentsRequired:
        print("\n" + "=" * 70)
        print("⚠️  CẢNH BÁO: CHƯA BẬT PRIVILEGED INTENTS TRÊN DISCORD DEVELOPER PORTAL")
        print("=" * 70)
        print("Bot đang yêu cầu quyền 'Server Members Intent' và 'Message Content Intent'")
        print("nhưng tài khoản Bot trên Discord Developer Portal chưa được gạt bật.")
        print("\n👉 CÁCH BẬT NHANH TRONG 30 GIÂY:")
        print("1. Truy cập: https://discord.com/developers/applications")
        print("2. Bấm chọn ứng dụng Bot của bạn -> Chọn mục 'Bot' ở thanh menu bên trái.")
        print("3. Kéo xuống mục 'Privileged Gateway Intents' và GẠT BẬT XANH cả 3 mục:")
        print("   ✅ Presence Intent (Tùy chọn)")
        print("   ✅ Server Members Intent (Khuyên dùng)")
        print("   ✅ Message Content Intent (Để tính EXP khi chat)")
        print("4. Bấm nút 'Save Changes' màu xanh ở dưới cùng.")
        print("=" * 70)
        print("🔄 Đang tự động kết nối lại ở Chế Độ Dự Phòng (Fallback Mode) để bot vẫn online...\n")

        if not bot.is_closed():
            await bot.close()

        fallback_bot = ClanBot(use_privileged_intents=False, should_sync=False)
        try:
            await fallback_bot.start(token)
        except Exception as fb_err:
            logger.error(f"Lỗi khi khởi chạy bot ở chế độ dự phòng: {fb_err}", exc_info=True)
        finally:
            if not fallback_bot.is_closed():
                await fallback_bot.close()
    except KeyboardInterrupt:
        logger.info("Nhận thao tác bàn phím (Ctrl+C). Đang tắt bot...")
    except Exception as e:
        logger.error(f"Lỗi khi khởi chạy bot: {e}", exc_info=True)
    finally:
        if not bot.is_closed():
            await bot.close()
        await bot.db.close()
        logger.info("Bot đã tắt an toàn.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
