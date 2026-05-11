"""Selection RP — Утиліти"""

import discord
from datetime import datetime, timezone
from config import COLOR, STAFF_LEVELS, OWNER_ID, OWNER_USERNAME


# ─────────────────────────────────────────────────────────────
#  Перевірки прав
# ─────────────────────────────────────────────────────────────
def is_owner(user: discord.Member) -> bool:
    """Перевіряє чи є юзер головним адміном (@artem_symy)."""
    return user.id == OWNER_ID or str(user).lower() == OWNER_USERNAME.lower()


def get_staff_level(bot, member: discord.Member) -> int:
    row = bot.db.get_staff(member.id, member.guild.id)
    if row:
        return row["level"]
    if is_owner(member) or member.guild_permissions.administrator:
        return 5
    return 0


def has_level(bot, member: discord.Member, required: int) -> bool:
    return get_staff_level(bot, member) >= required


def staff_check(required_level: int):
    """Декоратор-перевірка рівня персоналу."""
    async def predicate(ctx):
        if is_owner(ctx.author):
            return True
        level = ctx.bot.db.get_staff_level(ctx.author.id, ctx.guild.id)
        if level >= required_level:
            return True
        await ctx.reply(
            f"🚫 Потрібен рівень персоналу: **{STAFF_LEVELS[required_level]['name']}** або вище.",
            delete_after=8
        )
        return False
    from discord.ext.commands import check
    return check(predicate)


# ─────────────────────────────────────────────────────────────
#  Форматування часу
# ─────────────────────────────────────────────────────────────
def parse_duration(text: str) -> int | None:
    """'10m' → 600, '2h' → 7200, '1d' → 86400, None якщо безстроково."""
    if not text or text.lower() in ("0", "назавжди", "перм", "perm", "permanent"):
        return None
    units = {"s": 1, "с": 1, "m": 60, "м": 60, "хв": 60,
             "h": 3600, "г": 3600, "год": 3600,
             "d": 86400, "д": 86400, "дн": 86400}
    import re
    m = re.fullmatch(r"(\d+)\s*([a-zа-яі]+)", text.strip(), re.IGNORECASE)
    if m:
        n, u = int(m.group(1)), m.group(2).lower()
        return n * units.get(u, 60)
    if text.isdigit():
        return int(text)
    return None


def fmt_duration(seconds: int | None) -> str:
    if seconds is None:
        return "Назавжди"
    if seconds < 60:
        return f"{seconds} сек"
    if seconds < 3600:
        return f"{seconds // 60} хв"
    if seconds < 86400:
        return f"{seconds // 3600} год"
    return f"{seconds // 86400} дн"


def fmt_dt(dt_str: str | None) -> str:
    if not dt_str:
        return "—"
    try:
        dt = datetime.fromisoformat(dt_str)
        return discord.utils.format_dt(dt, style="f")
    except Exception:
        return dt_str


# ─────────────────────────────────────────────────────────────
#  Стандартні embed-шаблони
# ─────────────────────────────────────────────────────────────
def embed(title: str, description: str = "", color_key: str = "info",
          author: discord.Member | None = None) -> discord.Embed:
    e = discord.Embed(
        title=title,
        description=description,
        color=COLOR.get(color_key, 0x5865F2),
        timestamp=datetime.now(timezone.utc)
    )
    if author:
        e.set_footer(text=f"Дія: {author.display_name}", icon_url=author.display_avatar.url)
    return e


def success(desc: str, author=None) -> discord.Embed:
    return embed("✅  Успішно", desc, "success", author)


def error(desc: str) -> discord.Embed:
    return embed("❌  Помилка", desc, "error")


def warn_embed(desc: str, author=None) -> discord.Embed:
    return embed("⚠️  Увага", desc, "warning", author)


# ─────────────────────────────────────────────────────────────
#  Знайти канал логування
# ─────────────────────────────────────────────────────────────
async def get_log_channel(bot, guild: discord.Guild, channel_type: str = "log_channel"):
    settings = bot.db.get_settings(guild.id)
    ch_id = settings[channel_type] if settings else None
    if ch_id:
        return guild.get_channel(ch_id)
    return None


async def send_log(bot, guild: discord.Guild, embed: discord.Embed,
                   channel_type: str = "log_channel"):
    ch = await get_log_channel(bot, guild, channel_type)
    if ch:
        try:
            await ch.send(embed=embed)
        except discord.Forbidden:
            pass
