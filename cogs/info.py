"""
Selection RP — Інформація та допомога
"""

import discord
from discord.ext import commands
from datetime import datetime, timezone

from utils import embed, get_staff_level, is_owner
from config import COLOR, STAFF_LEVELS


HELP_DATA = {
    "Модерація": {
        "emoji": "⚔️",
        "level": 1,
        "commands": [
            ("!варн <@юзер> [причина]",         "Видати попередження"),
            ("!варни <@юзер>",                   "Список попереджень юзера"),
            ("!зняти_варн <ID>",                 "Зняти конкретний варн"),
            ("!мьют <@юзер> [тривалість] [причина]", "Замьютити (10m, 2h, 1d)"),
            ("!анмьют <@юзер>",                  "Розмьютити"),
            ("!кік <@юзер> [причина]",           "Кікнути учасника"),
            ("!бан <@юзер> [тривалість] [причина]","Забанити"),
            ("!анбан <ID>",                      "Розбанити за ID"),
            ("!м'якийбан <@юзер>",               "Softban (кік + видалення повідомлень)"),
            ("!очистити [кількість] [@юзер]",    "Видалити повідомлення"),
            ("!профіль [@юзер]",                 "Мод-профіль учасника"),
            ("!банлист [сторінка]",              "Список активних банів"),
        ]
    },
    "Скарги": {
        "emoji": "📩",
        "level": 0,
        "commands": [
            ("!скарга",                 "Подати скаргу (форма)"),
            ("!скарги_список [статус]", "Список скарг (pending/reviewing/resolved/rejected)"),
            ("!скарга_інфо <ID>",       "Детальна інформація про скаргу"),
            ("!статистика_скарг",       "Статистика по скаргах"),
        ]
    },
    "Персонал": {
        "emoji": "👮",
        "level": 4,
        "commands": [
            ("!призначити <@юзер> <рівень>", "Призначити персонал (1-5)"),
            ("!зняти <@юзер> [причина]",     "Зняти з персоналу"),
            ("!підвищити <@юзер>",           "Підвищити на 1 рівень"),
            ("!знизити <@юзер>",             "Знизити на 1 рівень"),
            ("!персонал",                    "Список всього персоналу"),
            ("!ранг [@юзер]",                "Перевірити рівень"),
        ]
    },
    "Адміністрація": {
        "emoji": "⚙️",
        "level": 3,
        "commands": [
            ("!setup",                       "Авто-налаштування серверу"),
            ("!setup_лог <тип> [#канал]",    "Встановити канал логу"),
            ("!оголошення <#канал> <текст>", "Надіслати оголошення"),
            ("!заблокувати_канал [#канал]",  "Заблокувати канал"),
            ("!розблокувати_канал [#канал]", "Розблокувати канал"),
            ("!повільний_режим [секунди]",   "Повільний режим"),
            ("!налаштування_бота",           "Поточні налаштування"),
            ("!журнал [кількість]",          "Журнал дій бота"),
        ]
    },
}


class Info(commands.Cog, name="Інформація"):

    def __init__(self, bot):
        self.bot = bot

    # ══════════════════════════════════════════════════════════
    #  ДОПОМОГА
    # ══════════════════════════════════════════════════════════
    @commands.command(name="допомога", aliases=["help", "h", "команди"])
    async def help_cmd(self, ctx, category: str = None):
        level = get_staff_level(self.bot, ctx.author)
        if is_owner(ctx.author):
            level = 5

        if category:
            # Конкретна категорія
            for cat_name, data in HELP_DATA.items():
                if category.lower() in cat_name.lower():
                    if level < data["level"] and not is_owner(ctx.author):
                        return await ctx.reply("🚫 Недостатньо прав.", delete_after=5)
                    e = embed(
                        f"{data['emoji']}  {cat_name}",
                        color_key="info"
                    )
                    for cmd, desc in data["commands"]:
                        e.add_field(name=f"`{cmd}`", value=desc, inline=False)
                    return await ctx.send(embed=e)
            return await ctx.reply("❓ Категорія не знайдена.", delete_after=5)

        # Загальне меню
        e = discord.Embed(
            title="📚  Selection RP — Довідка",
            description=("Використовуйте `!допомога <категорія>` для деталей.\n"
                         "Показано лише команди доступні вашому рівню."),
            color=COLOR["info"],
            timestamp=datetime.now(timezone.utc)
        )
        e.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)

        for cat_name, data in HELP_DATA.items():
            if level >= data["level"] or is_owner(ctx.author):
                e.add_field(
                    name=f"{data['emoji']} {cat_name}",
                    value=f"`!допомога {cat_name.lower()}`",
                    inline=True
                )

        lvl_name = STAFF_LEVELS[level]["name"] if level > 0 else "Учасник"
        e.set_footer(text=f"Ваш рівень: {lvl_name}  ·  Префікс: !")
        await ctx.send(embed=e)

    # ══════════════════════════════════════════════════════════
    #  ІНФОРМАЦІЯ ПРО СЕРВЕР
    # ══════════════════════════════════════════════════════════
    @commands.command(name="сервер", aliases=["serverinfo", "server"])
    async def server_info(self, ctx):
        g = ctx.guild
        e = discord.Embed(
            title=f"🌍  {g.name}",
            color=COLOR["info"],
            timestamp=datetime.now(timezone.utc)
        )
        if g.icon:
            e.set_thumbnail(url=g.icon.url)
        e.add_field(name="👑 Власник",      value=g.owner.mention if g.owner else "—")
        e.add_field(name="👥 Учасники",     value=str(g.member_count))
        e.add_field(name="📅 Створено",     value=discord.utils.format_dt(g.created_at, "R"))
        e.add_field(name="📢 Каналів",      value=str(len(g.channels)))
        e.add_field(name="🎭 Ролей",        value=str(len(g.roles)))
        e.add_field(name="😎 Емодзі",       value=str(len(g.emojis)))

        # Статистика скарг
        stats = self.bot.db.count_complaints_by_status(g.id)
        total = sum(stats.values())
        e.add_field(
            name="📩 Скарги",
            value=(f"Всього: {total}\n"
                   f"Очікує: {stats.get('pending', 0)}\n"
                   f"Вирішено: {stats.get('resolved', 0)}"),
        )
        await ctx.send(embed=e)

    # ══════════════════════════════════════════════════════════
    #  ІНФОРМАЦІЯ ПРО ЮЗЕРА
    # ══════════════════════════════════════════════════════════
    @commands.command(name="юзер", aliases=["userinfo", "ui", "whois"])
    async def user_info(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        level  = get_staff_level(self.bot, member)
        if is_owner(member):
            level = 5

        e = discord.Embed(
            title=f"👤  {member.display_name}",
            color=discord.Color(STAFF_LEVELS[level]["color"]) if level > 0 else discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc)
        )
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name="🆔 ID",        value=str(member.id))
        e.add_field(name="📛 Username",  value=str(member))
        e.add_field(name="📅 На сервері",value=discord.utils.format_dt(member.joined_at, "R"))
        e.add_field(name="📅 Акаунт",   value=discord.utils.format_dt(member.created_at, "R"))

        roles = [r.mention for r in reversed(member.roles) if r.name != "@everyone"]
        if roles:
            e.add_field(name=f"🎭 Ролі ({len(roles)})",
                        value=" ".join(roles[:15]) or "—", inline=False)

        if level > 0:
            e.add_field(name="🎖 Персонал", value=STAFF_LEVELS[level]["name"])

        await ctx.send(embed=e)

    # ══════════════════════════════════════════════════════════
    #  PING
    # ══════════════════════════════════════════════════════════
    @commands.command(name="пінг", aliases=["ping"])
    async def ping(self, ctx):
        lat = round(self.bot.latency * 1000)
        color = "success" if lat < 100 else ("warning" if lat < 200 else "error")
        await ctx.send(embed=embed(
            "🏓  Пінг",
            f"Затримка WebSocket: **{lat} мс**",
            color
        ))

    # ══════════════════════════════════════════════════════════
    #  РІВНІ
    # ══════════════════════════════════════════════════════════
    @commands.command(name="рівні", aliases=["levels", "ranks"])
    async def levels_info(self, ctx):
        e = embed("🎖  Рівні персоналу Selection RP", color_key="info")
        e.add_field(
            name="🔴 Рівень 5 — Головний Адміністратор",
            value="@artem_symy · Повний контроль над сервером та ботом.",
            inline=False
        )
        for lvl in range(4, 0, -1):
            info = STAFF_LEVELS[lvl]
            perms = {
                4: "Управління персоналом, бани, всі команди",
                3: "Бани, мьюти, кіки, скарги, оголошення",
                2: "Мьюти, кіки, очищення, управління каналами",
                1: "Варни, перегляд профілів і скарг",
            }
            e.add_field(
                name=f"{info['name']} (Рівень {lvl})",
                value=perms[lvl],
                inline=False
            )
        await ctx.send(embed=e)


async def setup(bot):
    await bot.add_cog(Info(bot))
