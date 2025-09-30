# 🪙 utils.loggers.ghouldengo_logs import pretty_log

import traceback
from datetime import datetime

import discord
from discord.ext import commands

# -------------------- 🪙 Global Bot Reference --------------------
BOT_INSTANCE: commands.Bot | None = None


def set_ghouldengo_bot(bot: commands.Bot):
    """Set the global bot instance for automatic logging."""
    global BOT_INSTANCE
    BOT_INSTANCE = bot


# -------------------- 🪙 Logging Tags --------------------
TAGS = {
    "info": "🪙  INFO",
    "db": "💰 DB",
    "cmd": "📜 COMMAND",
    "ready": "✨ READY",
    "error": "💥 ERROR",
    "warn": "⚠️ WARN",
    "critical": "🚨 CRITICAL",
    "auction": "👻 AUCTION",
    "coins": "🏅 COINS",
    "sent": "📨 SENT",
}


# -------------------- 🎨 ANSI Colors --------------------
# Ultra-light, soft tones
COLOR_SOFT_CREAM = "\033[38;2;255;255;210m"  # 🪙 pale cream (info/default)
COLOR_PEACH = "\033[38;2;255;220;180m"  # ⚠️ peach (warnings)
COLOR_SOFT_RED = "\033[38;2;255;150;150m"  # 💥 softer red (errors/critical)
COLOR_RESET = "\033[0m"

MAIN_COLORS = {
    "yellow": COLOR_SOFT_CREAM,
    "orange": COLOR_PEACH,
    "red": COLOR_SOFT_RED,
    "reset": COLOR_RESET,
}

# -------------------- ⚠️ Critical Logs Channel --------------------
CRITICAL_LOG_CHANNEL_ID = (
    1410202143570530375  # TODO: replace with Gholdengo’s error log channel
)


# -------------------- 🌟 Pretty Log --------------------
def pretty_log(
    tag: str = None,
    message: str = "",
    *,
    label: str = None,
    bot: commands.Bot = None,
    include_trace: bool = True,
):
    """Gold-themed pretty log with timestamp + emoji (now pastel)."""
    prefix = TAGS.get(tag) if tag else ""
    prefix_part = f"[{prefix}] " if prefix else ""
    label_str = f"[{label}] " if label else ""

    # Pick color
    if tag in ("critical", "error"):
        color = MAIN_COLORS["red"]
    elif tag == "warn":
        color = MAIN_COLORS["orange"]
    else:
        color = MAIN_COLORS["yellow"]

    now = datetime.now().strftime("%H:%M:%S")
    log_message = f"{color}[{now}] {prefix_part}{label_str}{message}{COLOR_RESET}"
    print(log_message)

    # Print traceback in console
    if include_trace and tag in ("error", "critical"):
        traceback.print_exc()

    bot_to_use = bot or BOT_INSTANCE

    # Send to Discord channel if needed
    if bot_to_use and tag in ("critical", "error", "warn"):
        try:
            channel = bot_to_use.get_channel(CRITICAL_LOG_CHANNEL_ID)
            if channel:
                full_message = f"{prefix_part}{label_str}{message}"
                if include_trace and tag in ("error", "critical"):
                    full_message += f"\n```py\n{traceback.format_exc()}```"
                if len(full_message) > 2000:
                    full_message = full_message[:1997] + "..."
                bot_to_use.loop.create_task(channel.send(full_message))
        except Exception:
            print("[❌ ERROR] Failed to send log to bot channel:")
            traceback.print_exc()
