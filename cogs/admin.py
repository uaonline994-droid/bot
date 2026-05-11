"""
Selection RP — Адмін-панель
Автоматичне налаштування серверу, управління каналами логування
"""

import discord
from discord.ext import commands

from utils import staff_check, is_owner, embed, success, error, send_log
from config import CHANNELS, COLOR, STAFF_LEVELS


class Admin(commands.Cog, name="Адмін"):

    def __init__(self, bot):
        self.bot = bot

    # ── Перевірка: тільки адмін або власник ──────────────────
    def _is_admin(self, ctx):
        return (is_owner(ctx.author)
                or ctx.author.guild_permissions.administrator
                or self.bot.db.get_staff_level(ctx.author.id, ctx.guild.id) >= 4)

    # ══════════════════════════════════════════════════════════
    #  АВТО-НАЛАШТУВАННЯ
    # ══════════════════════════════════════════════════════════
    @commands.command(name="setup", aliases=["налаштування", "init"])
    @commands.has_permissions(administrator=True)
    async def setup_server(self, ctx):
        """Автоматично створює всі потрібні канали та ролі."""
        if not self._is_admin(ctx):
            return await ctx.reply(embed=error("Тільки для адміністраторів."))

        msg = await ctx.send(embed=embed(
            "⚙️  Налаштування Selection RP...",
            "Зачекайте, це може зайняти кілька секунд.",
            "info"
        ))

        guild   = ctx.guild
        created = []

        # ── Категорія для каналів логування ──────────────────
        cat = discord.utils.get(guild.categories, name="📋 Selection RP — Logs")
        if not cat:
            cat = await guild.create_category(
                "📋 Selection RP — Logs",
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(read_messages=False)
                }
            )
            created.append("📁 Категорія логів")

        # ── Канали логування ──────────────────────────────────
        log_channels = {
            "log_channel":         "📋︱mod-log",
            "action_log_channel":  "📜︱action-log",
            "join_log_channel":    "🚪︱join-log",
            "complaint_log_channel": "📩︱complaint-log",
        }
        for key, name in log_channels.items():
            ch = discord.utils.get(guild.text_channels, name=name)
            if not ch:
                ch = await guild.create_text_channel(name, category=cat)
                created.append(f"#{name}")
            self.bot.db.set_channel(guild.id, key, ch.id)

        # ── Публічна категорія ────────────────────────────────
        pub_cat = discord.utils.get(guild.categories, name="📨 Selection RP")
        if not pub_cat:
            pub_cat = await guild.create_category("📨 Selection RP")
            created.append("📁 Публічна категорія")

        complaint_ch = discord.utils.get(guild.text_channels, name="📨︱скарги")
        if not complaint_ch:
            complaint_ch = await guild.create_text_channel(
                "📨︱скарги", category=pub_cat)
            created.append("#📨︱скарги")
        self.bot.db.set_channel(guild.id, "complaint_channel", complaint_ch.id)

        # ── Ролі персоналу ────────────────────────────────────
        for lvl, info in STAFF_LEVELS.items():
            role = discord.utils.get(guild.roles, name=info["name"])
            if not role:
                role = await guild.create_role(
                    name=info["name"],
                    color=discord.Color(info["color"]),
                    hoist=True
                )
                created.append(f"Роль {info['name']}")

        # ── Роль Muted ────────────────────────────────────────
        muted = discord.utils.get(guild.roles, name="🔇 Muted")
        if not muted:
            muted = await guild.create_role(
                name="🔇 Muted",
                color=discord.Color.from_rgb(100, 100, 100),
                reason="Selection RP — Muted role"
            )
            for channel in guild.channels:
                try:
                    await channel.set_permissions(
                        muted, send_messages=False, speak=False, add_reactions=False)
                except Exception:
                    pass
            created.append("Роль 🔇 Muted")
        self.bot.db.set_muted_role(guild.id, muted.id)

        # ── Фінальний звіт ────────────────────────────────────
        e = embed("✅  Налаштування завершено!", color_key="success", author=ctx.author)
        if created:
            e.add_field(name="Створено:", value="\n".join(f"• {i}" for i in created), inline=False)
        else:
            e.add_field(name="Стан", value="Все вже налаштовано ✔")
        e.add_field(
            name="ℹ️ Наступні кроки",
            value="1. Призначте персонал командою `!призначити`\n"
                  "2. Перевірте права ролей\n"
                  "3. Бот готовий до роботи!",
            inline=False
        )
        await msg.edit(embed=e)

    # ══════════════════════════════════════════════════════════
    #  ВСТАНОВИТИ КАНАЛ
    # ══════════════════════════════════════════════════════════
    @commands.command(name="setcannel", aliases=["setlog_ch"])
    @commands.has_permissions(administrator=True)
    async def set_channel(self, ctx, log_type: str, channel: discord.TextChannel = None):
        """Встановити канал. Типи: log, action, join, complaint, complaint_log"""
        channel = channel or ctx.channel
        mapping = {
            "log":           "log_channel",
            "action":        "action_log_channel",
            "join":          "join_log_channel",
            "complaint":     "complaint_channel",
            "complaint_log": "complaint_log_channel",
        }
        key = mapping.get(log_type.lower())
        if not key:
            return await ctx.reply(embed=error(f"Доступні типи: {', '.join(mapping.keys())}"))
        self.bot.db.set_channel(ctx.guild.id, key, channel.id)
        await ctx.send(embed=success(f"Канал `{log_type}` → {channel.mention}", ctx.author))

    # ══════════════════════════════════════════════════════════
    #  ПОТОЧНІ НАЛАШТУВАННЯ
    # ══════════════════════════════════════════════════════════
    @commands.command(name="налаштування_бота", aliases=["botsettings", "settings"])
    @staff_check(3)
    async def bot_settings(self, ctx):
        s = self.bot.db.get_settings(ctx.guild.id)
        e = embed("⚙️  Налаштування бота", color_key="info")
        items = [
            ("📋 Мод-лог",           s["log_channel"]),
            ("📜 Журнал дій",         s["action_log_channel"]),
            ("🚪 Лог входів",         s["join_log_channel"]),
            ("📩 Канал скарг",        s["complaint_channel"]),
            ("📩 Лог скарг",          s["complaint_log_channel"]),
            ("🔇 Роль Muted",         s["muted_role"]),
        ]
        for name, val in items:
            if val:
                ref = ctx.guild.get_channel(val) or ctx.guild.get_role(val)
                disp = ref.mention if ref else f"ID:{val}"
            else:
                disp = "❌ Не встановлено"
            e.add_field(name=name, value=disp)
        await ctx.send(embed=e)

    # ══════════════════════════════════════════════════════════
    #  ANNOUNCE
    # ══════════════════════════════════════════════════════════
    @commands.command(name="оголошення", aliases=["announce", "ann"])
    @staff_check(3)
    async def announce(self, ctx, channel: discord.TextChannel, *, text: str):
        """Надіслати оголошення в канал від імені бота."""
        e = discord.Embed(
            description=text,
            color=COLOR["info"],
            timestamp=discord.utils.utcnow()
        )
        e.set_author(
            name="📢  Selection RP — Оголошення",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None
        )
        e.set_footer(text=f"Від: {ctx.author.display_name}")
        await channel.send(embed=e)
        await ctx.reply(embed=success(f"Оголошення надіслано в {channel.mention}", ctx.author))
        await ctx.message.delete(delay=3)

    # ══════════════════════════════════════════════════════════
    #  LOCK / UNLOCK канал
    # ══════════════════════════════════════════════════════════
    @commands.command(name="заблокувати_канал", aliases=["lockdown", "lock"])
    @staff_check(2)
    async def lock(self, ctx, channel: discord.TextChannel = None, *, reason: str = ""):
        channel = channel or ctx.channel
        await channel.set_permissions(ctx.guild.default_role, send_messages=False)
        self.bot.db.log_action(ctx.guild.id, "LOCK_CHANNEL", ctx.author.id,
                               details=f"#{channel.name}: {reason}")
        e = embed("🔒  Канал заблоковано",
                  f"{channel.mention} закрито для повідомлень.\n{reason}",
                  "warning", ctx.author)
        await ctx.send(embed=e)
        await send_log(self.bot, ctx.guild, e)

    @commands.command(name="розблокувати_канал", aliases=["unlock"])
    @staff_check(2)
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        await channel.set_permissions(ctx.guild.default_role, send_messages=None)
        self.bot.db.log_action(ctx.guild.id, "UNLOCK_CHANNEL", ctx.author.id,
                               details=f"#{channel.name}")
        e = embed("🔓  Канал розблоковано",
                  f"{channel.mention} знову відкрито.", "success", ctx.author)
        await ctx.send(embed=e)
        await send_log(self.bot, ctx.guild, e)

    # ══════════════════════════════════════════════════════════
    #  SLOWMODE
    # ══════════════════════════════════════════════════════════
    @commands.command(name="повільний_режим", aliases=["slowmode", "slow"])
    @staff_check(2)
    async def slowmode(self, ctx, seconds: int = 0,
                       channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        await channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            msg = f"Повільний режим вимкнено у {channel.mention}"
        else:
            msg = f"Повільний режим {seconds}с у {channel.mention}"
        await ctx.send(embed=success(msg, ctx.author))

    # ══════════════════════════════════════════════════════════
    #  ЖУРНАЛ ДІЙ БОТА
    # ══════════════════════════════════════════════════════════
    @commands.command(name="журнал", aliases=["actionlog", "alog"])
    @staff_check(3)
    async def action_log(self, ctx, limit: int = 20):
        logs = self.bot.db.get_action_log(ctx.guild.id, min(limit, 30))
        if not logs:
            return await ctx.send(embed=embed("📜  Журнал дій", "Порожньо.", "info"))
        e = embed(f"📜  Журнал дій (останні {len(logs)})", color_key="log")
        for row in logs[:10]:
            actor   = ctx.guild.get_member(row["actor_id"])
            target  = ctx.guild.get_member(row["target_id"])
            a_name  = actor.display_name  if actor  else (f"ID:{row['actor_id']}"  if row["actor_id"]  else "—")
            t_name  = target.display_name if target else (f"ID:{row['target_id']}" if row["target_id"] else "—")
            e.add_field(
                name=f"`{row['action']}` · {row['created_at'][11:16]}",
                value=f"Хто: {a_name} → Кого: {t_name}\n{row['details'] or ''}",
                inline=False
            )
        await ctx.send(embed=e)


async def setup(bot):
    await bot.add_cog(Admin(bot))
