"""
Selection RP — Управління персоналом
Призначення, зняття, підвищення, список персоналу
"""

import discord
from discord.ext import commands

from utils import (staff_check, is_owner, get_staff_level,
                   embed, success, error, send_log)
from config import STAFF_LEVELS, COLOR


class Staff(commands.Cog, name="Персонал"):

    def __init__(self, bot):
        self.bot = bot

    # ── Хелпер: синхронізувати роль ─────────────────────────
    async def _sync_role(self, guild, member, level: int, old_level: int = 0):
        """Видаляє стару роль персоналу, додає нову."""
        from config import ROLE_NAMES
        # Видалити всі ролі персоналу
        for lvl, info in STAFF_LEVELS.items():
            role = discord.utils.get(guild.roles, name=info["name"])
            if role and role in member.roles:
                try:
                    await member.remove_roles(role)
                except Exception:
                    pass
        # Додати нову
        if level > 0:
            info    = STAFF_LEVELS[level]
            role    = discord.utils.get(guild.roles, name=info["name"])
            if not role:
                role = await guild.create_role(
                    name=info["name"],
                    color=discord.Color(info["color"]),
                    hoist=True,
                    reason="Selection RP — Staff role"
                )
            try:
                await member.add_roles(role)
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════
    #  ПРИЗНАЧИТИ ПЕРСОНАЛ
    # ══════════════════════════════════════════════════════════
    @commands.command(name="призначити", aliases=["addstaff", "appoint"])
    @staff_check(4)
    async def add_staff(self, ctx, member: discord.Member,
                        level: int, *, notes: str = ""):
        if level < 1 or level > 5:
            return await ctx.reply(embed=error("Рівень від 1 до 5."))
        if not is_owner(ctx.author) and level >= get_staff_level(self.bot, ctx.author):
            return await ctx.reply(embed=error(
                "Не можна призначити рівний або вищий рівень за власний."))
        if is_owner(member):
            return await ctx.reply(embed=error("Головний адмін не потребує призначення."))

        old_level = get_staff_level(self.bot, member)
        self.bot.db.add_staff(member.id, ctx.guild.id, str(member),
                              level, ctx.author.id, notes)
        await self._sync_role(ctx.guild, member, level, old_level)
        self.bot.db.log_action(ctx.guild.id, "STAFF_ADD", ctx.author.id, member.id,
                               f"Рівень {level}: {STAFF_LEVELS[level]['name']}")

        e = embed(f"👮  Новий персонал", color_key="info", author=ctx.author)
        e.add_field(name="Учасник", value=member.mention)
        e.add_field(name="Рівень",  value=f"**{STAFF_LEVELS[level]['name']}** (Рівень {level})")
        if notes:
            e.add_field(name="Примітки", value=notes, inline=False)
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)
        await send_log(self.bot, ctx.guild, e)

        # DM
        try:
            dm = embed(
                "🎉  Вас призначено на посаду персоналу Selection RP!",
                f"Ваш рівень: **{STAFF_LEVELS[level]['name']}**\n"
                f"Призначив: {ctx.author.display_name}",
                "success"
            )
            await member.send(embed=dm)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════
    #  ЗНЯТИ ПЕРСОНАЛ
    # ══════════════════════════════════════════════════════════
    @commands.command(name="зняти", aliases=["removestaff", "destaff", "fire"])
    @staff_check(4)
    async def remove_staff(self, ctx, member: discord.Member, *, reason: str = "Не вказано"):
        if is_owner(member):
            return await ctx.reply(embed=error("Не можна зняти головного адміна."))
        row = self.bot.db.get_staff(member.id, ctx.guild.id)
        if not row:
            return await ctx.reply(embed=error("Учасник не є персоналом."))
        if not is_owner(ctx.author) and row["level"] >= get_staff_level(self.bot, ctx.author):
            return await ctx.reply(embed=error("Не можна зняти рівного або вищого."))

        old_level = row["level"]
        self.bot.db.remove_staff(member.id, ctx.guild.id)
        await self._sync_role(ctx.guild, member, 0, old_level)
        self.bot.db.log_action(ctx.guild.id, "STAFF_REMOVE", ctx.author.id,
                               member.id, reason)

        e = embed("👮  Персонал знятий", color_key="warning", author=ctx.author)
        e.add_field(name="Учасник",       value=member.mention)
        e.add_field(name="Колишній рівень",value=STAFF_LEVELS[old_level]["name"])
        e.add_field(name="Причина",       value=reason, inline=False)
        await ctx.send(embed=e)
        await send_log(self.bot, ctx.guild, e)

        try:
            dm = embed(
                "😔  Вас знято з посади персоналу Selection RP",
                f"Причина: {reason}\nЗняв: {ctx.author.display_name}",
                "error"
            )
            await member.send(embed=dm)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════
    #  ПІДВИЩИТИ / ЗНИЗИТИ
    # ══════════════════════════════════════════════════════════
    @commands.command(name="підвищити", aliases=["promote"])
    @staff_check(4)
    async def promote(self, ctx, member: discord.Member):
        if is_owner(member):
            return await ctx.reply(embed=error("Не можна підвищити головного адміна."))
        row = self.bot.db.get_staff(member.id, ctx.guild.id)
        if not row:
            return await ctx.reply(embed=error("Учасник не є персоналом."))
        if row["level"] >= 5:
            return await ctx.reply(embed=error("Вже максимальний рівень."))
        if not is_owner(ctx.author) and row["level"] >= get_staff_level(self.bot, ctx.author) - 1:
            return await ctx.reply(embed=error("Недостатньо прав для підвищення."))

        new_level = row["level"] + 1
        self.bot.db.update_staff_level(member.id, ctx.guild.id, new_level)
        await self._sync_role(ctx.guild, member, new_level, row["level"])
        self.bot.db.log_action(ctx.guild.id, "STAFF_PROMOTE", ctx.author.id,
                               member.id, f"{row['level']} → {new_level}")

        e = embed("⬆️  Підвищення", color_key="success", author=ctx.author)
        e.add_field(name="Учасник", value=member.mention)
        e.add_field(name="Рівень",  value=(
            f"{STAFF_LEVELS[row['level']]['name']} → **{STAFF_LEVELS[new_level]['name']}**"
        ))
        await ctx.send(embed=e)
        await send_log(self.bot, ctx.guild, e)

    @commands.command(name="знизити", aliases=["demote"])
    @staff_check(4)
    async def demote(self, ctx, member: discord.Member):
        if is_owner(member):
            return await ctx.reply(embed=error("Не можна понизити головного адміна."))
        row = self.bot.db.get_staff(member.id, ctx.guild.id)
        if not row:
            return await ctx.reply(embed=error("Учасник не є персоналом."))
        if row["level"] <= 1:
            return await ctx.reply(embed=error("Вже мінімальний рівень. Використайте !зняти."))

        new_level = row["level"] - 1
        self.bot.db.update_staff_level(member.id, ctx.guild.id, new_level)
        await self._sync_role(ctx.guild, member, new_level, row["level"])
        self.bot.db.log_action(ctx.guild.id, "STAFF_DEMOTE", ctx.author.id,
                               member.id, f"{row['level']} → {new_level}")

        e = embed("⬇️  Пониження", color_key="warning", author=ctx.author)
        e.add_field(name="Учасник", value=member.mention)
        e.add_field(name="Рівень",  value=(
            f"{STAFF_LEVELS[row['level']]['name']} → **{STAFF_LEVELS[new_level]['name']}**"
        ))
        await ctx.send(embed=e)
        await send_log(self.bot, ctx.guild, e)

    # ══════════════════════════════════════════════════════════
    #  СПИСОК ПЕРСОНАЛУ
    # ══════════════════════════════════════════════════════════
    @commands.command(name="персонал", aliases=["staff", "team"])
    async def staff_list(self, ctx):
        all_staff = self.bot.db.get_all_staff(ctx.guild.id)
        e = discord.Embed(
            title="👮  Персонал Selection RP",
            color=COLOR["info"],
            timestamp=discord.utils.utcnow()
        )

        # Завжди показуємо власника
        e.add_field(
            name="🔴 Головний Адміністратор",
            value="<@artem_symy> — @artem_symy",
            inline=False
        )

        # Групуємо по рівнях
        by_level = {5: [], 4: [], 3: [], 2: [], 1: []}
        for s in all_staff:
            lvl = s["level"]
            if lvl in by_level:
                by_level[lvl].append(s)

        for lvl in range(5, 0, -1):
            members_in_level = by_level[lvl]
            if members_in_level:
                names = "\n".join(
                    f"<@{s['user_id']}>" for s in members_in_level
                )
                e.add_field(
                    name=STAFF_LEVELS[lvl]["name"],
                    value=names,
                    inline=False
                )

        total = len(all_staff) + 1  # +1 owner
        e.set_footer(text=f"Всього персоналу: {total}")
        await ctx.send(embed=e)

    # ══════════════════════════════════════════════════════════
    #  РАНГ ПЕРСОНАЛУ (перевірити свій/чужий рівень)
    # ══════════════════════════════════════════════════════════
    @commands.command(name="ранг", aliases=["rank", "mylevel"])
    async def rank(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        lvl    = get_staff_level(self.bot, member)
        if is_owner(member):
            lvl = 5
        e = embed(f"🎖  Рівень — {member.display_name}", color_key="info")
        e.set_thumbnail(url=member.display_avatar.url)
        if lvl == 0:
            e.description = "Звичайний учасник сервера."
        else:
            e.description = (
                f"**{STAFF_LEVELS[lvl]['name']}**\n"
                f"Рівень: `{lvl}`"
            )
        await ctx.send(embed=e)


async def setup(bot):
    await bot.add_cog(Staff(bot))
