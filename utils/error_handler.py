import discord
from discord import app_commands
from utils.logger import setup_logging

logger = setup_logging("ErrorHandler")

class ClanException(app_commands.AppCommandError):
    """Ngoại lệ cơ sở cho các lỗi nghiệp vụ Băng Đảng"""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

async def global_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Bộ xử lý lỗi tập trung cho toàn bộ Slash Commands"""
    # Trích xuất lỗi thực tế nếu bị bọc bởi CommandInvokeError
    if isinstance(error, app_commands.CommandInvokeError):
        error = error.original

    if isinstance(error, ClanException):
        msg = f"❌ {error.message}"
    elif isinstance(error, app_commands.MissingPermissions):
        missing = ", ".join(f"`{p}`" for p in error.missing_permissions)
        msg = f"❌ Bạn không đủ quyền để dùng lệnh này! Yêu cầu: {missing}"
    elif isinstance(error, app_commands.BotMissingPermissions):
        missing = ", ".join(f"`{p}`" for p in error.missing_permissions)
        msg = f"❌ Bot thiếu các quyền Discord sau để thực hiện lệnh: {missing}"
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"⏳ Lệnh đang trong thời gian chờ! Vui lòng thử lại sau `{error.retry_after:.1f}` giây."
    else:
        logger.error(f"Lỗi không xác định khi thực thi lệnh /{interaction.command.name if interaction.command else 'unknown'}: {error}", exc_info=True)
        msg = f"❌ Đã xảy ra lỗi nội bộ khi xử lý: `{type(error).__name__}`. Vui lòng liên hệ Admin!"

    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception as send_err:
        logger.error(f"Không thể gửi thông báo lỗi đến user: {send_err}")
