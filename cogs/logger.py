"""
Selection RP — Система логування
Логує: join/leave, edit/delete повідомлень, зміни ролей, голосові канали
"""

import discord
from discord.ext import commands
from datetime import datetime, timezone

from utils import embed, send_log
from config import COLOR


class Logger(commands.Cog, name="Логування"):

    def __init__(self, bot):
        self.bot = bot

    # ── Хелпер: отримати канал логу ─────────────────────────
    async def _log(self, guild, e, ch_type="action_log_channel"):
        await send_log(self.bot, guild, e, ch_type)

    # ══════════════════════════════════════════════════════════
    #  JOIN / LEAVE
    # ══════════════════════════════════════════════════════════
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        e = discord.Embed(
            title="📥  Новий учасник",
            color=COLOR["success"],
            timestamp=datetime.now(timezone.utc)
        )
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name="Учасник",   value=f"{member.mention} (`{member.id}`)")
        e.add_field(name="Акаунт",    value=discord.utils.format_dt(member.created_at, "R"))
        e.add_field(name="Всього",    value=str(member.guild.member_count))
        await self._log(member.guild, e, "join_log_channel")
        self.bot.db.log_action(member.guild.id, "JOIN", target_id=member.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        e = discord.Embed(
            title="📤  Учасник покинув",
            color=COLOR["warning"],
            timestamp=datetime.now(timezone.utc)
        )
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name="Учасник",  value=f"{member} (`{member.id}`)")
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        if roles:
            e.add_field(name="Ролі", value=" ".join(roles[-10:]), inline=False)
        await self._log(member.guild, e, "join_log_channel")
        self.bot.db.log_action(member.guild.id, "LEAVE", target_id=member.id)

    # ══════════════════════════════════════════════════════════
    #  ПОВІДОМЛЕННЯ
    # ══════════════════════════════════════════════════════════
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.content == after.content:
            return
        e = discord.Embed(
            title="✏️  Повідомлення відредаговано",
            color=COLOR["info"],
            timestamp=datetime.now(timezone.utc)
        )
        e.add_field(name="Автор",   value=f"{before.author.mention} (`{before.author.id}`)")
        e.add_field(name="Канал",   value=before.channel.mention)
        e.add_field(name="До",      value=before.content[:1000] or "—", inline=False)
        e.add_field(name="Після",   value=after.content[:1000]  or "—", inline=False)
        e.add_field(name="Посилання", value=f"[Перейти]({after.jump_url})")
        await self._log(before.guild, e)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        e = discord.Embed(
            title="🗑️  Повідомлення видалено",
            color=COLOR["error"],
            timestamp=datetime.now(timezone.utc)
        )
        e.add_field(name="Автор",  value=f"{message.author.mention} (`{message.author.id}`)")
        e.add_field(name="Канал",  value=message.channel.mention)
        e.add_field(name="Зміст",  value=message.content[:1000] or "*(вкладення/embed)*",
                    inline=False)
        if message.attachments:
            e.add_field(name="Вкладення",
                        value="\n".join(a.filename for a in message.attachments),
                        inline=False)
        await self._log(message.guild, e)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        if not messages or not messages[0].guild:
            return
        guild = messages[0].guild
        e = discord.Embed(
            title="🗑️  Масове видалення повідомлень",
            color=COLOR["error"],
            timestamp=datetime.now(timezone.utc)
        )
        e.add_field(name="Кількість", value=str(len(messages)))
        e.add_field(name="Канал",     value=messages[0].channel.mention)
        await self._log(guild, e)

    # ══════════════════════════════════════════════════════════
    #  РОЛІ
    # ══════════════════════════════════════════════════════════
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        added   = set(after.roles) - set(before.roles)
        removed = set(before.roles) - set(after.roles)
        if not added and not removed:
            return
        e = discord.Embed(
            title="🎭  Зміна ролей",
            color=COLOR["moderation"],
            timestamp=datetime.now(timezone.utc)
        )
        e.add_field(name="Учасник", value=f"{after.mention} (`{after.id}`)")
        if added:
            e.add_field(name="➕ Додано",  value=" ".join(r.mention for r in added))
        if removed:
            e.add_field(name="➖ Знято",   value=" ".join(r.mention for r in removed))
        await self._log(after.guild, e)

    # ══════════════════════════════════════════════════════════
    #  ГОЛОСОВІ КАНАЛИ
    # ══════════════════════════════════════════════════════════
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel:
            return
        if after.channel and not before.channel:
            action = f"📞 Зайшов у **{after.channel.name}**"
        elif before.channel and not after.channel:
            action = f"📵 Вийшов з **{before.channel.name}**"
        else:
            action = f"🔀 Перейшов: **{before.channel.name}** → **{after.channel.name}**"

        e = discord.Embed(
            title="🎤  Голосовий канал",
            description=f"{member.mention} {action}",
            color=COLOR["log"],
            timestamp=datetime.now(timezone.utc)
        )
        await self._log(member.guild, e)

    # ══════════════════════════════════════════════════════════
    #  МЮТ / БАН через Discord (аудит лог)
    # ══════════════════════════════════════════════════════════
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user):
        e = discord.Embed(
            title="🔨  Бан (Discord)",
            color=COLOR["error"],
            timestamp=datetime.now(timezone.utc)
        )
        e.add_field(name="Учасник", value=f"{user} (`{user.id}`)")
        e.set_thumbnail(url=user.display_avatar.url)
        await self._log(guild, e)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user):
        e = discord.Embed(
            title="🔓  Анбан (Discord)",
            color=COLOR["success"],
            timestamp=datetime.now(timezone.utc)
        )
        e.add_field(name="Учасник", value=f"{user} (`{user.id}`)")
        await self._log(guild, e)

    # ══════════════════════════════════════════════════════════
    #  КОМАНДИ
    # ══════════════════════════════════════════════════════════
    @commands.command(name="setup_лог", aliases=["setlog", "setup_log"])
    @commands.has_permissions(administrator=True)
    async def setup_log(self, ctx,
                        log_type: str = "log",
                        channel: discord.TextChannel = None):
        """
        Встановити канал логування.
        Типи: log, action, join, complaint, complaint_log
        """
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
            return await ctx.reply(f"Невідомий тип. Доступні: {', '.join(mapping)}")
        self.bot.db.set_channel(ctx.guild.id, key, channel.id)
        await ctx.send(embed=embed(
            "✅  Лог встановлено",
            f"Тип `{log_type}` → {channel.mention}",
            "success",
            ctx.author
        ))


async def setup(bot):
    await bot.add_cog(Logger(bot))
