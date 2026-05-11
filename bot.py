"""
╔══════════════════════════════════════════════════════════╗
║          Selection RP — Discord Moderation Bot           ║
║          Головний адмін: @artem_symy                     ║
╚══════════════════════════════════════════════════════════╝
"""

import discord
from discord.ext import commands, tasks
import asyncio
import logging
import sys
from datetime import datetime, timezone, timedelta

from config import BOT_TOKEN, PREFIX, OWNER_ID, OWNER_USERNAME
from database import Database

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("SelectionRP")

# ── Intents ──────────────────────────────────────────────────
intents = discord.Intents.all()

# ── Bot клас ─────────────────────────────────────────────────
class SelectionBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )
        self.db = Database()
        self.owner_id = OWNER_ID

    # ── Setup hook: завантажуємо cogs ────────────────────────
    async def setup_hook(self):
        cogs = [
            "cogs.moderation",
            "cogs.complaints",
            "cogs.logger",
            "cogs.staff",
            "cogs.admin",
            "cogs.info",
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                log.info(f"✅  Cog завантажено: {cog}")
            except Exception as e:
                log.error(f"❌  Помилка завантаження {cog}: {e}")

        await self.tree.sync()
        log.info("🔄  Slash-команди синхронізовано")

    # ── on_ready ─────────────────────────────────────────────
    async def on_ready(self):
        log.info(f"🚀  Бот запущено як: {self.user}  (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Selection RP | !допомога"
            )
        )
        self.check_timers.start()

    # ── Перевірка прострочених мьютів/банів ─────────────────
    @tasks.loop(seconds=30)
    async def check_timers(self):
        # Прострочені мьюти
        for mute in self.db.get_expired_mutes():
            guild = self.get_guild(mute["guild_id"])
            if guild:
                member = guild.get_member(mute["user_id"])
                if member:
                    try:
                        await member.timeout(None, reason="Мьют завершено автоматично")
                    except Exception:
                        pass
            self.db.deactivate_mute(mute["id"])
            self.db.log_action(mute["guild_id"], "AUTO_UNMUTE",
                               target_id=mute["user_id"], details="Мьют завершено")

        # Прострочені бани
        for ban in self.db.get_expired_bans():
            guild = self.get_guild(ban["guild_id"])
            if guild:
                try:
                    user = await self.fetch_user(ban["user_id"])
                    await guild.unban(user, reason="Тимчасовий бан завершено")
                except Exception:
                    pass
            self.db.unban(ban["user_id"], ban["guild_id"])
            self.db.log_action(ban["guild_id"], "AUTO_UNBAN",
                               target_id=ban["user_id"], details="Бан завершено")

    @check_timers.before_loop
    async def before_check_timers(self):
        await self.wait_until_ready()

    # ── Глобальний обробник помилок ──────────────────────────
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("❌ У вас немає прав для цієї команди.", delete_after=8)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.reply("❌ Учасника не знайдено.", delete_after=8)
        elif isinstance(error, commands.BadArgument):
            await ctx.reply(f"❌ Невірний аргумент: {error}", delete_after=8)
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(
                f"⏳ Зачекайте `{error.retry_after:.1f}` сек перед повторним використанням.",
                delete_after=8
            )
        elif isinstance(error, commands.CheckFailure):
            await ctx.reply("🚫 У вас недостатньо прав.", delete_after=8)
        else:
            log.error(f"Помилка команди '{ctx.command}': {error}", exc_info=error)
            await ctx.reply(f"⚠️ Сталася помилка: `{error}`", delete_after=10)


# ── Запуск ────────────────────────────────────────────────────
import os
os.makedirs("data", exist_ok=True)

bot = SelectionBot()

if __name__ == "__main__":
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("\n⚠️  Вставте токен бота у config.py → BOT_TOKEN\n")
        sys.exit(1)
    bot.run(BOT_TOKEN, log_handler=None)
