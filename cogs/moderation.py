"""
Selection RP — Модерація
Команди: warn, mute, unmute, kick, ban, unban, history
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta

from utils import (staff_check, is_owner, get_staff_level,
                   parse_duration, fmt_duration, fmt_dt,
                   embed, success, error, warn_embed, send_log)
from config import COLOR, WARN_MUTE_THRESHOLDS, STAFF_LEVELS


# ─────────────────────────────────────────────────────────────
class Moderation(commands.Cog, name="Модерація"):

    def __init__(self, bot):
        self.bot = bot

    # ── Хелпер: отримати/створити роль Muted ────────────────
    async def _muted_role(self, guild: discord.Guild) -> discord.Role:
        settings = self.bot.db.get_settings(guild.id)
        role_id  = settings["muted_role"] if settings else None
        role     = guild.get_role(role_id) if role_id else None
        if not role:
            role = discord.utils.get(guild.roles, name="🔇 Muted")
        if not role:
            role = await guild.create_role(
                name="🔇 Muted",
                color=discord.Color.from_rgb(100, 100, 100),
                reason="Selection RP — Muted role"
            )
            for channel in guild.channels:
                try:
                    await channel.set_permissions(role, send_messages=False,
                                                  speak=False, add_reactions=False)
                except Exception:
                    pass
            self.bot.db.set_muted_role(guild.id, role.id)
        return role

    # ══════════════════════════════════════════════════════════
    #  WARN
    # ══════════════════════════════════════════════════════════
    @commands.command(name="варн", aliases=["warn", "w"])
    @staff_check(1)
    async def warn(self, ctx, member: discord.Member, *, reason: str = "Не вказано"):
        if member.id == ctx.author.id:
            return await ctx.reply(embed=error("Не можна варнити себе."))
        if is_owner(member):
            return await ctx.reply(embed=error("Не можна варнити головного адміна."))
        if get_staff_level(self.bot, member) >= get_staff_level(self.bot, ctx.author):
            return await ctx.reply(embed=error("Не можна варнити рівного або вищого персоналу."))

        wid   = self.bot.db.add_warning(member.id, ctx.guild.id, reason, ctx.author.id)
        count = self.bot.db.count_warnings(member.id, ctx.guild.id)
        self.bot.db.log_action(ctx.guild.id, "WARN", ctx.author.id, member.id,
                               f"Варн #{wid}: {reason}")

        # Embed для каналу
        e = embed(f"⚠️  Попередження — #{wid}", color_key="warning")
        e.add_field(name="Учасник",       value=member.mention)
        e.add_field(name="Модератор",     value=ctx.author.mention)
        e.add_field(name="Причина",       value=reason, inline=False)
        e.add_field(name="Всього варнів", value=f"**{count}**")
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)

        # DM юзеру
        try:
            dm = embed("⚠️  Ви отримали попередження на Selection RP", color_key="warning")
            dm.add_field(name="Причина", value=reason)
            dm.add_field(name="Варнів всього", value=str(count))
            await member.send(embed=dm)
        except Exception:
            pass

        # Лог
        log_e = embed(f"⚠️ WARN #{wid}", color_key="moderation", author=ctx.author)
        log_e.add_field(name="Учасник",   value=f"{member} (`{member.id}`)")
        log_e.add_field(name="Причина",   value=reason)
        log_e.add_field(name="Варнів",    value=str(count))
        await send_log(self.bot, ctx.guild, log_e)

        # Авто-покарання за варни
        await self._check_warn_threshold(ctx, member, count)

    async def _check_warn_threshold(self, ctx, member, count):
        for threshold, duration in sorted(WARN_MUTE_THRESHOLDS.items()):
            if count == threshold:
                if duration is None:
                    # Авто-бан
                    try:
                        await member.ban(reason=f"Авто-бан: {count} попереджень")
                        self.bot.db.add_ban(member.id, ctx.guild.id, str(member),
                                            f"Авто-бан: {count} варнів", self.bot.user.id)
                        await ctx.send(embed=embed(
                            "🔨  Авто-бан",
                            f"{member.mention} отримав бан за **{count}** попереджень.",
                            "error"
                        ))
                    except Exception:
                        pass
                else:
                    # Авто-мьют
                    try:
                        until = discord.utils.utcnow() + timedelta(seconds=duration)
                        await member.timeout(until, reason=f"Авто-мьют: {count} попереджень")
                        self.bot.db.add_mute(member.id, ctx.guild.id,
                                             f"Авто-мьют: {count} варнів",
                                             self.bot.user.id, duration)
                        await ctx.send(embed=embed(
                            "🔇  Авто-мьют",
                            f"{member.mention} → мьют **{fmt_duration(duration)}** за {count} варнів.",
                            "warning"
                        ))
                    except Exception:
                        pass
                break

    # ══════════════════════════════════════════════════════════
    #  WARN LIST
    # ══════════════════════════════════════════════════════════
    @commands.command(name="варни", aliases=["warns", "wl"])
    @staff_check(1)
    async def warn_list(self, ctx, member: discord.Member):
        warns = self.bot.db.get_warnings(member.id, ctx.guild.id)
        e = embed(f"📋  Попередження — {member.display_name}", color_key="warning")
        e.set_thumbnail(url=member.display_avatar.url)
        if not warns:
            e.description = "Чисто — попереджень немає."
        else:
            for w in warns:
                mod = ctx.guild.get_member(w["moderator"])
                mod_name = mod.display_name if mod else f"ID:{w['moderator']}"
                e.add_field(
                    name=f"#{w['id']} · {w['created_at'][:10]}",
                    value=f"**Причина:** {w['reason']}\n**Модератор:** {mod_name}",
                    inline=False
                )
        await ctx.send(embed=e)

    # ══════════════════════════════════════════════════════════
    #  UNWARN
    # ══════════════════════════════════════════════════════════
    @commands.command(name="зняти_варн", aliases=["unwarn", "delwarn"])
    @staff_check(3)
    async def unwarn(self, ctx, warn_id: int):
        w = self.bot.db.conn.execute(
            "SELECT * FROM warnings WHERE id=? AND guild_id=?",
            (warn_id, ctx.guild.id)
        ).fetchone()
        if not w:
            return await ctx.reply(embed=error(f"Варн #{warn_id} не знайдено."))
        self.bot.db.remove_warning(warn_id, ctx.guild.id)
        self.bot.db.log_action(ctx.guild.id, "UNWARN", ctx.author.id, w["user_id"],
                               f"Знято варн #{warn_id}")
        await ctx.send(embed=success(f"Варн **#{warn_id}** знято."))

    # ══════════════════════════════════════════════════════════
    #  MUTE
    # ══════════════════════════════════════════════════════════
    @commands.command(name="мьют", aliases=["mute"])
    @staff_check(2)
    async def mute(self, ctx, member: discord.Member,
                   duration: str = "1h", *, reason: str = "Не вказано"):
        if is_owner(member):
            return await ctx.reply(embed=error("Не можна замьютити головного адміна."))
        if get_staff_level(self.bot, member) >= get_staff_level(self.bot, ctx.author):
            return await ctx.reply(embed=error("Не можна замьютити рівного або вищого."))

        secs  = parse_duration(duration)
        until = discord.utils.utcnow() + timedelta(seconds=secs) if secs else None
        try:
            await member.timeout(until, reason=reason)
        except discord.Forbidden:
            return await ctx.reply(embed=error("Не вистачає прав для мьюту."))

        mid = self.bot.db.add_mute(member.id, ctx.guild.id, reason,
                                   ctx.author.id, secs)
        self.bot.db.log_action(ctx.guild.id, "MUTE", ctx.author.id, member.id,
                               f"{fmt_duration(secs)} · {reason}")

        e = embed(f"🔇  Мьют", color_key="moderation", author=ctx.author)
        e.add_field(name="Учасник",    value=member.mention)
        e.add_field(name="Тривалість", value=fmt_duration(secs))
        e.add_field(name="Причина",    value=reason, inline=False)
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)

        try:
            dm = embed("🔇  Вас замьютили на Selection RP", color_key="moderation")
            dm.add_field(name="Тривалість", value=fmt_duration(secs))
            dm.add_field(name="Причина",    value=reason)
            await member.send(embed=dm)
        except Exception:
            pass

        await send_log(self.bot, ctx.guild, e)

    # ══════════════════════════════════════════════════════════
    #  UNMUTE
    # ══════════════════════════════════════════════════════════
    @commands.command(name="анмьют", aliases=["unmute"])
    @staff_check(2)
    async def unmute(self, ctx, member: discord.Member, *, reason: str = "Не вказано"):
        try:
            await member.timeout(None, reason=reason)
        except discord.Forbidden:
            return await ctx.reply(embed=error("Не вистачає прав."))
        self.bot.db.unmute(member.id, ctx.guild.id)
        self.bot.db.log_action(ctx.guild.id, "UNMUTE", ctx.author.id, member.id, reason)
        e = success(f"{member.mention} розмьючений. Причина: {reason}", ctx.author)
        await ctx.send(embed=e)
        await send_log(self.bot, ctx.guild, e)

    # ══════════════════════════════════════════════════════════
    #  KICK
    # ══════════════════════════════════════════════════════════
    @commands.command(name="кік", aliases=["kick"])
    @staff_check(2)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "Не вказано"):
        if is_owner(member):
            return await ctx.reply(embed=error("Не можна кікнути головного адміна."))
        if get_staff_level(self.bot, member) >= get_staff_level(self.bot, ctx.author):
            return await ctx.reply(embed=error("Не можна кікнути рівного або вищого."))

        # DM перед кіком
        try:
            dm = embed("👢  Вас кікнули з Selection RP", color_key="error")
            dm.add_field(name="Причина", value=reason)
            await member.send(embed=dm)
        except Exception:
            pass

        await member.kick(reason=reason)
        self.bot.db.add_kick(member.id, ctx.guild.id, str(member), reason, ctx.author.id)
        self.bot.db.log_action(ctx.guild.id, "KICK", ctx.author.id, member.id, reason)

        e = embed("👢  Кік", color_key="error", author=ctx.author)
        e.add_field(name="Учасник", value=f"{member} (`{member.id}`)")
        e.add_field(name="Причина", value=reason)
        await ctx.send(embed=e)
        await send_log(self.bot, ctx.guild, e)

    # ══════════════════════════════════════════════════════════
    #  BAN
    # ══════════════════════════════════════════════════════════
    @commands.command(name="бан", aliases=["ban"])
    @staff_check(3)
    async def ban(self, ctx, member: discord.Member,
                  duration: str = "перм", *, reason: str = "Не вказано"):
        if is_owner(member):
            return await ctx.reply(embed=error("Не можна забанити головного адміна."))
        if get_staff_level(self.bot, member) >= get_staff_level(self.bot, ctx.author):
            return await ctx.reply(embed=error("Не можна банити рівного або вищого."))

        secs = parse_duration(duration)

        # DM перед баном
        try:
            dm = embed("🔨  Вас забанили на Selection RP", color_key="error")
            dm.add_field(name="Тривалість", value=fmt_duration(secs))
            dm.add_field(name="Причина",    value=reason)
            await member.send(embed=dm)
        except Exception:
            pass

        await member.ban(reason=reason, delete_message_days=0)
        bid = self.bot.db.add_ban(member.id, ctx.guild.id, str(member),
                                  reason, ctx.author.id, secs)
        self.bot.db.log_action(ctx.guild.id, "BAN", ctx.author.id, member.id,
                               f"{fmt_duration(secs)} · {reason}")

        e = embed("🔨  Бан", color_key="error", author=ctx.author)
        e.add_field(name="Учасник",    value=f"{member} (`{member.id}`)")
        e.add_field(name="Тривалість", value=fmt_duration(secs))
        e.add_field(name="Причина",    value=reason, inline=False)
        e.set_footer(text=f"Ban ID: #{bid}")
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)

        # Лог у ban-list канал
        await send_log(self.bot, ctx.guild, e, "log_channel")
        await send_log(self.bot, ctx.guild, e, "action_log_channel")

    # ══════════════════════════════════════════════════════════
    #  UNBAN
    # ══════════════════════════════════════════════════════════
    @commands.command(name="анбан", aliases=["unban"])
    @staff_check(3)
    async def unban(self, ctx, user_id: int, *, reason: str = "Не вказано"):
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user, reason=reason)
        except discord.NotFound:
            return await ctx.reply(embed=error("Користувача не знайдено або він не в бані."))
        except discord.Forbidden:
            return await ctx.reply(embed=error("Не вистачає прав."))

        self.bot.db.unban(user_id, ctx.guild.id)
        self.bot.db.log_action(ctx.guild.id, "UNBAN", ctx.author.id, user_id, reason)

        e = success(f"{user.mention} (`{user_id}`) розбанений.\nПричина: {reason}", ctx.author)
        await ctx.send(embed=e)
        await send_log(self.bot, ctx.guild, e)

    # ══════════════════════════════════════════════════════════
    #  SOFTBAN (кік + видалення повідомлень)
    # ══════════════════════════════════════════════════════════
    @commands.command(name="м'якийбан", aliases=["softban", "sb"])
    @staff_check(3)
    async def softban(self, ctx, member: discord.Member, *, reason: str = "Не вказано"):
        if is_owner(member):
            return await ctx.reply(embed=error("Не можна."))
        await member.ban(reason=f"Softban: {reason}", delete_message_days=7)
        await ctx.guild.unban(member, reason="Softban - видалення повідомлень")
        self.bot.db.log_action(ctx.guild.id, "SOFTBAN", ctx.author.id, member.id, reason)
        e = embed("🧹  Soft-бан", color_key="warning", author=ctx.author)
        e.add_field(name="Учасник", value=f"{member}")
        e.add_field(name="Причина", value=reason)
        e.set_footer(text="7 днів повідомлень видалено")
        await ctx.send(embed=e)
        await send_log(self.bot, ctx.guild, e)

    # ══════════════════════════════════════════════════════════
    #  CLEAR (purge)
    # ══════════════════════════════════════════════════════════
    @commands.command(name="очистити", aliases=["clear", "purge"])
    @staff_check(2)
    async def clear(self, ctx, amount: int = 10, member: discord.Member = None):
        if amount < 1 or amount > 500:
            return await ctx.reply(embed=error("Від 1 до 500 повідомлень."))
        await ctx.message.delete()
        if member:
            def check(m): return m.author == member
            deleted = await ctx.channel.purge(limit=amount * 3, check=check)
        else:
            deleted = await ctx.channel.purge(limit=amount)
        self.bot.db.log_action(ctx.guild.id, "CLEAR", ctx.author.id,
                               details=f"{len(deleted)} повідомлень у #{ctx.channel.name}")
        msg = await ctx.send(embed=success(
            f"Видалено **{len(deleted)}** повідомлень.", ctx.author
        ))
        await msg.delete(delay=5)

    # ══════════════════════════════════════════════════════════
    #  HISTORY (профіль модерації)
    # ══════════════════════════════════════════════════════════
    @commands.command(name="профіль", aliases=["history", "profile", "modinfo"])
    @staff_check(1)
    async def profile(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        p = self.bot.db.get_user_profile(member.id, ctx.guild.id)

        e = embed(f"📁  Профіль — {member.display_name}", color_key="info")
        e.set_thumbnail(url=member.display_avatar.url)

        # Рівень персоналу
        lvl = get_staff_level(self.bot, member)
        if lvl > 0:
            e.add_field(name="🎖 Персонал", value=STAFF_LEVELS[lvl]["name"])
        else:
            e.add_field(name="🎖 Статус", value="Звичайний учасник")

        e.add_field(name="⚠️ Варни",   value=str(p["warnings"]))
        e.add_field(name="👢 Кіки",    value=str(len(p["kicks"])))
        e.add_field(name="🔇 Мьют",    value="Активний" if p["active_mute"] else "Немає")
        e.add_field(name="🔨 Бан",     value="Активний" if p["ban"] else "Немає")
        e.add_field(name="📩 Скарги",  value=str(p["complaints_filed"]))

        # Останні варни
        if p["all_warnings"]:
            wtext = "\n".join(
                f"`#{w['id']}` {w['reason'][:40]} — {w['created_at'][:10]}"
                for w in p["all_warnings"][:5]
            )
            e.add_field(name="Останні попередження", value=wtext, inline=False)

        e.add_field(name="Joined", value=discord.utils.format_dt(member.joined_at, "R"),
                    inline=True)
        await ctx.send(embed=e)

    # ══════════════════════════════════════════════════════════
    #  BAN LIST
    # ══════════════════════════════════════════════════════════
    @commands.command(name="банлист", aliases=["banlist", "bans"])
    @staff_check(1)
    async def ban_list(self, ctx, page: int = 1):
        bans = self.bot.db.get_ban_list(ctx.guild.id, limit=100)
        if not bans:
            return await ctx.send(embed=embed("🔨  Бан-лист", "Список порожній.", "info"))

        per_page = 10
        total    = len(bans)
        pages    = max(1, (total + per_page - 1) // per_page)
        page     = max(1, min(page, pages))
        slice_   = bans[(page - 1) * per_page: page * per_page]

        e = embed(f"🔨  Бан-лист — стор. {page}/{pages}", color_key="error")
        for b in slice_:
            mod = ctx.guild.get_member(b["moderator"])
            mod_name = mod.display_name if mod else f"ID:{b['moderator']}"
            e.add_field(
                name=f"#{b['id']} · {b['username'] or b['user_id']}",
                value=(f"**Причина:** {b['reason']}\n"
                       f"**Мод:** {mod_name}\n"
                       f"**Дата:** {b['created_at'][:10]}\n"
                       f"**До:** {fmt_dt(b['expires_at'])}"),
                inline=True
            )
        e.set_footer(text=f"Всього банів: {total}")
        await ctx.send(embed=e)


# ─────────────────────────────────────────────────────────────
async def setup(bot):
    await bot.add_cog(Moderation(bot))
