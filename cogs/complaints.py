"""
Selection RP — Система скарг
Подача, розгляд, вирішення / відхилення скарг
"""

import discord
from discord.ext import commands
from discord import ui
from datetime import datetime, timezone

from utils import (staff_check, is_owner, get_staff_level,
                   embed, success, error, send_log)
from config import COLOR, MAX_COMPLAINTS_PER_DAY


# ─────────────────────────────────────────────────────────────
#  Категорії скарг
# ─────────────────────────────────────────────────────────────
COMPLAINT_CATEGORIES = {
    "Образа / Токсичність":  "🤬",
    "Порушення RP":          "🎭",
    "Читинг / Баги":         "🐞",
    "Харасмент":             "😡",
    "Спам":                  "📢",
    "Дискримінація":         "🚫",
    "Скарга на персонал":    "👮",
    "Інше":                  "📌",
}

STATUS_COLOR = {
    "pending":   0xFEE75C,
    "reviewing": 0x5865F2,
    "resolved":  0x57F287,
    "rejected":  0xED4245,
}
STATUS_LABEL = {
    "pending":   "⏳ На розгляді",
    "reviewing": "🔍 Розглядається",
    "resolved":  "✅ Вирішено",
    "rejected":  "❌ Відхилено",
}


# ─────────────────────────────────────────────────────────────
#  Модальне вікно подачі скарги
# ─────────────────────────────────────────────────────────────
class ComplaintModal(ui.Modal, title="📩  Подача скарги"):
    target = ui.TextInput(
        label="На кого скарга (ім'я або ID)",
        placeholder="Наприклад: SomePlayer#0000 або 123456789",
        max_length=100,
        required=True,
    )
    category_input = ui.TextInput(
        label="Категорія",
        placeholder="Образа / Порушення RP / Читинг / Харасмент / Спам / Інше",
        max_length=50,
        required=True,
    )
    description = ui.TextInput(
        label="Опис порушення",
        placeholder="Детально опишіть що сталося, де, коли...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )
    evidence = ui.TextInput(
        label="Докази (посилання, скріншоти, опис)",
        placeholder="Вставте посилання або опишіть наявні докази",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False,
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        guild   = interaction.guild
        author  = interaction.user
        db      = self.cog.bot.db

        # Ліміт на добу
        today_count = db.get_user_complaints_today(author.id, guild.id)
        if today_count >= MAX_COMPLAINTS_PER_DAY:
            return await interaction.response.send_message(
                embed=error(f"Ви вже подали **{today_count}** скарг сьогодні. "
                            f"Ліміт — {MAX_COMPLAINTS_PER_DAY}."),
                ephemeral=True
            )

        cat = self.category_input.value.strip()
        # Нормалізуємо категорію
        for c in COMPLAINT_CATEGORIES:
            if cat.lower() in c.lower():
                cat = c
                break

        cid = db.add_complaint(
            guild_id     = guild.id,
            author_id    = author.id,
            author_name  = str(author),
            target_id    = None,
            target_name  = self.target.value,
            category     = cat,
            description  = self.description.value,
            evidence     = self.evidence.value or None,
        )

        # Відповідь скаржнику
        await interaction.response.send_message(
            embed=success(
                f"Скарга **#{cid}** подана успішно!\n"
                "Персонал розгляне її найближчим часом.",
                author
            ),
            ephemeral=True
        )

        # Публікуємо у канал скарг
        await self.cog._post_complaint(guild, cid)


# ─────────────────────────────────────────────────────────────
#  Кнопки управління скаргою (для персоналу)
# ─────────────────────────────────────────────────────────────
class ComplaintView(ui.View):
    def __init__(self, cog, complaint_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.complaint_id = complaint_id
        self.custom_id_prefix = f"complaint_{complaint_id}"

    def _check_staff(self, interaction) -> bool:
        lvl = get_staff_level(self.cog.bot, interaction.user)
        return lvl >= 1 or is_owner(interaction.user)

    @ui.button(label="🔍 Взяти на розгляд", style=discord.ButtonStyle.blurple,
               custom_id="take_complaint")
    async def take(self, interaction: discord.Interaction, button: ui.Button):
        if not self._check_staff(interaction):
            return await interaction.response.send_message(
                "🚫 Тільки персонал може розглядати скарги.", ephemeral=True)
        db  = self.cog.bot.db
        c   = db.get_complaint(self.complaint_id)
        if c["status"] != "pending":
            return await interaction.response.send_message(
                f"Скарга вже має статус: {STATUS_LABEL.get(c['status'])}.", ephemeral=True)
        db.update_complaint_status(self.complaint_id, "reviewing",
                                   handler_id=interaction.user.id)
        db.log_action(interaction.guild.id, "COMPLAINT_TAKE",
                      interaction.user.id, c["author_id"],
                      f"Скарга #{self.complaint_id}")
        await interaction.response.send_message(
            f"✅ Ви взяли скаргу **#{self.complaint_id}** на розгляд.", ephemeral=True)
        await self.cog._update_complaint_message(interaction.guild, self.complaint_id)

    @ui.button(label="✅ Вирішено", style=discord.ButtonStyle.green,
               custom_id="resolve_complaint")
    async def resolve(self, interaction: discord.Interaction, button: ui.Button):
        if not self._check_staff(interaction):
            return await interaction.response.send_message("🚫 Заборонено.", ephemeral=True)
        await interaction.response.send_modal(
            ComplaintNoteModal(self.cog, self.complaint_id, "resolved"))

    @ui.button(label="❌ Відхилити", style=discord.ButtonStyle.red,
               custom_id="reject_complaint")
    async def reject(self, interaction: discord.Interaction, button: ui.Button):
        if not self._check_staff(interaction):
            return await interaction.response.send_message("🚫 Заборонено.", ephemeral=True)
        await interaction.response.send_modal(
            ComplaintNoteModal(self.cog, self.complaint_id, "rejected"))


class ComplaintNoteModal(ui.Modal):
    note = ui.TextInput(
        label="Коментар модератора",
        placeholder="Опишіть рішення або причину відхилення...",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True,
    )

    def __init__(self, cog, complaint_id, new_status):
        title = "✅  Вирішення скарги" if new_status == "resolved" else "❌  Відхилення скарги"
        super().__init__(title=title)
        self.cog        = cog
        self.complaint_id = complaint_id
        self.new_status = new_status

    async def on_submit(self, interaction: discord.Interaction):
        db = self.cog.bot.db
        db.update_complaint_status(
            self.complaint_id, self.new_status,
            handler_id=interaction.user.id,
            note=self.note.value
        )
        db.log_action(interaction.guild.id,
                      f"COMPLAINT_{self.new_status.upper()}",
                      interaction.user.id, detail=f"#{self.complaint_id}: {self.note.value}")
        status_text = STATUS_LABEL[self.new_status]
        await interaction.response.send_message(
            f"{status_text} — Скарга **#{self.complaint_id}** оновлена.", ephemeral=True)
        await self.cog._update_complaint_message(interaction.guild, self.complaint_id)

        # Повідомити скаржника
        c = db.get_complaint(self.complaint_id)
        try:
            author = interaction.guild.get_member(c["author_id"])
            if author:
                dm = embed(f"📩  Скарга #{self.complaint_id} — {status_text}",
                           color_key="success" if self.new_status == "resolved" else "error")
                dm.add_field(name="Рішення модератора", value=self.note.value)
                await author.send(embed=dm)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
#  Cog
# ─────────────────────────────────────────────────────────────
class Complaints(commands.Cog, name="Скарги"):

    def __init__(self, bot):
        self.bot = bot
        # Відновлюємо persistent views
        bot.loop.create_task(self._restore_views())

    async def _restore_views(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            complaints = self.bot.db.get_complaints(
                guild.id, status=None, limit=200)
            for c in complaints:
                if c["status"] in ("pending", "reviewing") and c["message_id"]:
                    self.bot.add_view(
                        ComplaintView(self, c["id"]),
                        message_id=c["message_id"]
                    )

    # ── Публікація скарги у канал ────────────────────────────
    async def _post_complaint(self, guild: discord.Guild, complaint_id: int):
        settings = self.bot.db.get_settings(guild.id)
        ch_id    = settings["complaint_channel"] if settings else None
        ch       = guild.get_channel(ch_id) if ch_id else None
        if not ch:
            return

        c   = self.bot.db.get_complaint(complaint_id)
        cat = c["category"]
        ico = COMPLAINT_CATEGORIES.get(cat, "📌")

        e = discord.Embed(
            title=f"{ico}  Скарга #{complaint_id}",
            color=STATUS_COLOR["pending"],
            timestamp=datetime.now(timezone.utc)
        )
        e.add_field(name="👤 Скаржник",   value=f"<@{c['author_id']}> ({c['author_name']})")
        e.add_field(name="🎯 На кого",    value=c["target_name"] or "—")
        e.add_field(name="📂 Категорія",  value=f"{ico} {cat}", inline=False)
        e.add_field(name="📝 Опис",       value=c["description"], inline=False)
        if c["evidence"]:
            e.add_field(name="🔗 Докази", value=c["evidence"], inline=False)
        e.set_footer(text=f"Статус: {STATUS_LABEL['pending']}")

        view = ComplaintView(self, complaint_id)
        msg  = await ch.send(embed=e, view=view)
        self.bot.db.update_complaint_status(complaint_id, "pending", msg_id=msg.id)
        self.bot.add_view(view, message_id=msg.id)

        # Лог у complaint_log
        log_e = embed(f"📩  Нова скарга #{complaint_id}", color_key="complaint")
        log_e.add_field(name="Скаржник", value=f"<@{c['author_id']}>")
        log_e.add_field(name="На кого",  value=c["target_name"] or "—")
        log_e.add_field(name="Категорія",value=cat)
        await send_log(self.bot, guild, log_e, "complaint_log_channel")

    # ── Оновлення embed скарги після зміни статусу ───────────
    async def _update_complaint_message(self, guild: discord.Guild, complaint_id: int):
        c        = self.bot.db.get_complaint(complaint_id)
        settings = self.bot.db.get_settings(guild.id)
        ch_id    = settings["complaint_channel"] if settings else None
        ch       = guild.get_channel(ch_id) if ch_id else None
        if not ch or not c["message_id"]:
            return
        try:
            msg = await ch.fetch_message(c["message_id"])
        except Exception:
            return

        status = c["status"]
        cat    = c["category"]
        ico    = COMPLAINT_CATEGORIES.get(cat, "📌")

        e = discord.Embed(
            title=f"{ico}  Скарга #{complaint_id}  ·  {STATUS_LABEL[status]}",
            color=STATUS_COLOR.get(status, 0x5865F2),
            timestamp=datetime.now(timezone.utc)
        )
        e.add_field(name="👤 Скаржник",  value=f"<@{c['author_id']}>")
        e.add_field(name="🎯 На кого",   value=c["target_name"] or "—")
        e.add_field(name="📂 Категорія", value=f"{ico} {cat}", inline=False)
        e.add_field(name="📝 Опис",      value=c["description"], inline=False)
        if c["evidence"]:
            e.add_field(name="🔗 Докази", value=c["evidence"], inline=False)
        if c["handler_id"]:
            e.add_field(name="👮 Модератор", value=f"<@{c['handler_id']}>")
        if c["handler_note"]:
            e.add_field(name="💬 Коментар", value=c["handler_note"], inline=False)
        e.set_footer(text=f"Статус: {STATUS_LABEL[status]}")

        # Якщо закрита — без кнопок
        if status in ("resolved", "rejected"):
            await msg.edit(embed=e, view=None)
        else:
            await msg.edit(embed=e, view=ComplaintView(self, complaint_id))

    # ══════════════════════════════════════════════════════════
    #  КОМАНДИ
    # ══════════════════════════════════════════════════════════

    @commands.command(name="скарга", aliases=["complaint", "report"])
    async def submit_complaint(self, ctx):
        """Відкриває форму для подачі скарги."""
        await ctx.message.delete(delay=3)
        e = embed(
            "📩  Подача скарги — Selection RP",
            "Натисни кнопку нижче, щоб заповнити форму.",
            color_key="complaint"
        )
        e.add_field(name="⏱ Час відповіді", value="Зазвичай до 24 годин")
        e.add_field(name="📋 Ліміт",        value=f"{MAX_COMPLAINTS_PER_DAY} скарг / день")

        class SubmitView(discord.ui.View):
            def __init__(self_v, cog):
                super().__init__(timeout=120)
                self_v.cog = cog

            @discord.ui.button(label="📩 Подати скаргу", style=discord.ButtonStyle.primary)
            async def btn(self_v, interaction, button):
                await interaction.response.send_modal(ComplaintModal(self_v.cog))

        await ctx.send(embed=e, view=SubmitView(self))

    @commands.command(name="скарги_список", aliases=["complaints", "clist"])
    @staff_check(1)
    async def complaints_list(self, ctx, status: str = "pending", page: int = 1):
        """Список скарг за статусом: pending / reviewing / resolved / rejected"""
        status = status.lower()
        if status == "всі":
            status = None
        items    = self.bot.db.get_complaints(ctx.guild.id, status, limit=100)
        per_page = 5
        total    = len(items)
        pages    = max(1, (total + per_page - 1) // per_page)
        page     = max(1, min(page, pages))
        sl       = items[(page - 1) * per_page: page * per_page]

        label = STATUS_LABEL.get(status, "Всі") if status else "Всі"
        e     = embed(f"📋  Скарги — {label}  (стор. {page}/{pages})", color_key="complaint")
        if not sl:
            e.description = "Скарг не знайдено."
        for c in sl:
            ico = COMPLAINT_CATEGORIES.get(c["category"], "📌")
            e.add_field(
                name=f"#{c['id']} {ico} {c['category']}",
                value=(f"**Від:** {c['author_name']}\n"
                       f"**На:** {c['target_name'] or '—'}\n"
                       f"**Статус:** {STATUS_LABEL.get(c['status'],'—')}\n"
                       f"**Дата:** {c['created_at'][:16]}"),
                inline=True
            )
        e.set_footer(text=f"Всього: {total}")
        await ctx.send(embed=e)

    @commands.command(name="скарга_інфо", aliases=["cinfo", "complaint_info"])
    @staff_check(1)
    async def complaint_info(self, ctx, complaint_id: int):
        c = self.bot.db.get_complaint(complaint_id)
        if not c:
            return await ctx.send(embed=error(f"Скарга #{complaint_id} не знайдена."))
        if c["guild_id"] != ctx.guild.id:
            return await ctx.send(embed=error("Не ваш сервер."))

        status = c["status"]
        ico    = COMPLAINT_CATEGORIES.get(c["category"], "📌")
        e      = discord.Embed(
            title=f"{ico}  Скарга #{complaint_id}",
            color=STATUS_COLOR.get(status, 0x5865F2),
            timestamp=datetime.now(timezone.utc)
        )
        e.add_field(name="Скаржник",  value=f"<@{c['author_id']}> ({c['author_name']})")
        e.add_field(name="На кого",   value=c["target_name"] or "—")
        e.add_field(name="Категорія", value=f"{ico} {c['category']}", inline=False)
        e.add_field(name="Опис",      value=c["description"], inline=False)
        if c["evidence"]:
            e.add_field(name="Докази", value=c["evidence"], inline=False)
        e.add_field(name="Статус",    value=STATUS_LABEL.get(status, status))
        if c["handler_id"]:
            e.add_field(name="Модератор", value=f"<@{c['handler_id']}>")
        if c["handler_note"]:
            e.add_field(name="Коментар мода", value=c["handler_note"], inline=False)
        e.add_field(name="Створено",  value=c["created_at"][:16])
        e.add_field(name="Оновлено",  value=c["updated_at"][:16])
        await ctx.send(embed=e)

    @commands.command(name="статистика_скарг", aliases=["cstats"])
    @staff_check(1)
    async def complaint_stats(self, ctx):
        stats = self.bot.db.count_complaints_by_status(ctx.guild.id)
        e = embed("📊  Статистика скарг", color_key="complaint")
        total = sum(stats.values())
        for status, cnt in stats.items():
            e.add_field(name=STATUS_LABEL.get(status, status), value=str(cnt))
        e.add_field(name="📦 Всього", value=str(total))
        await ctx.send(embed=e)

    @commands.command(name="setup_скарги", aliases=["setup_complaints"])
    @staff_check(5)
    async def setup_complaints(self, ctx, channel: discord.TextChannel = None):
        """Встановити канал для скарг."""
        channel = channel or ctx.channel
        self.bot.db.set_channel(ctx.guild.id, "complaint_channel", channel.id)
        await ctx.send(embed=success(
            f"Канал скарг встановлено: {channel.mention}", ctx.author))


async def setup(bot):
    await bot.add_cog(Complaints(bot))
