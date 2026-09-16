import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
import re
import random
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple


def parse_duration(duration_str: str) -> Optional[int]:
    """解析時長字串為總秒數 (支援: 30s, 10m, 2h, 1d, 1w)"""
    duration_str = duration_str.strip().lower()
    match = re.fullmatch(r"(\d+)\s*([smhdw])", duration_str)
    if not match:
        if duration_str.isdigit():
            return int(duration_str) * 60
        return None
    value, unit = int(match.group(1)), match.group(2)
    multipliers = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400,
        'w': 604800
    }
    return value * multipliers.get(unit, 60)


class GiveawayView(discord.ui.View):
    """抽獎持久化按鈕介面"""

    def __init__(self, cog, message_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.message_id = message_id

        # 參加按鈕
        self.join_btn = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="參加抽獎",
            emoji="🎉",
            custom_id=f"giveaway_join_{message_id}"
        )
        self.join_btn.callback = self.handle_join
        self.add_item(self.join_btn)

        # 查看名單按鈕
        self.list_btn = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="參加名單",
            emoji="👥",
            custom_id=f"giveaway_list_{message_id}"
        )
        self.list_btn.callback = self.handle_list
        self.add_item(self.list_btn)

    async def handle_join(self, interaction: discord.Interaction):
        """處理參加/退出抽獎 (含身分組、等級、今日發言等門檻驗證)"""
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        gw = self.cog.get_giveaway(guild_id, self.message_id)

        if not gw or gw.get("status") != "active":
            await interaction.response.send_message("❌ 此抽獎活動已結束或已取消！", ephemeral=True)
            return

        participants: List[int] = gw.setdefault("participants", [])

        # 若已在名單中，允許點擊退出
        if user_id in participants:
            participants.remove(user_id)
            self.cog.save_giveaway(guild_id, gw)
            await self.cog.update_giveaway_message(interaction.guild, gw)
            await interaction.response.send_message(
                f"👋 您已退出 **{gw['prize']}** 的抽獎活動！",
                ephemeral=True
            )
            return

        # 檢查資格門檻 (身分組、等級、今日發言數、歷史發言數)
        eligible, err_msg = self.cog.check_user_eligibility(interaction.guild, interaction.user, gw)
        if not eligible:
            await interaction.response.send_message(err_msg, ephemeral=True)
            return

        # 加入參加名單
        participants.append(user_id)
        self.cog.save_giveaway(guild_id, gw)
        await self.cog.update_giveaway_message(interaction.guild, gw)
        await interaction.response.send_message(
            f"🎉 成功參加 **{gw['prize']}** 抽獎！祝你好運！\n（再次點擊按鈕可退出抽獎）",
            ephemeral=True
        )

    async def handle_list(self, interaction: discord.Interaction):
        """私密回覆查看參加者名單"""
        guild_id = interaction.guild.id
        gw = self.cog.get_giveaway(guild_id, self.message_id)

        if not gw:
            await interaction.response.send_message("❌ 找不到此抽獎資料。", ephemeral=True)
            return

        participants: List[int] = gw.get("participants", [])
        count = len(participants)

        if count == 0:
            await interaction.response.send_message("ℹ️ 目前尚無任何成員參加抽獎。", ephemeral=True)
            return

        # 顯示前 50 位
        mention_list = [f"<@{uid}>" for uid in participants[:50]]
        content = " ".join(mention_list)
        if count > 50:
            content += f"\n... 等共 **{count}** 位成員參加。"

        embed = discord.Embed(
            title=f"👥 抽獎參加名單 — {gw['prize']}",
            description=f"目前累計參加人數：**{count}** 位\n\n{content}",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class Giveaway(commands.Cog):
    """🎁 伺服器抽獎系統 (Giveaway System)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data_dir = "./data"
        self._stats_cache: Dict[int, Dict[str, Any]] = {}
        self._dirty_guilds: set = set()
        self.check_giveaways.start()
        self.flush_stats_loop.start()

    def cog_unload(self):
        self.check_giveaways.cancel()
        self.flush_stats_loop.cancel()
        self.flush_all_stats()

    @commands.Cog.listener()
    async def on_ready(self):
        """機器人上線時，自動為所有進行中的抽獎註冊持久化按鈕"""
        await self.register_all_active_views()
        print("📦 Giveaway cog已載入並註冊抽獎按鈕監聽")

    async def register_all_active_views(self):
        """遍歷所有伺服器註冊 active 抽獎的 View"""
        try:
            if not os.path.exists(self.data_dir):
                return
            for guild_entry in os.listdir(self.data_dir):
                guild_path = os.path.join(self.data_dir, guild_entry)
                if os.path.isdir(guild_path) and guild_entry.isdigit():
                    gw_file = os.path.join(guild_path, "giveaways.json")
                    if os.path.exists(gw_file):
                        try:
                            with open(gw_file, "r", encoding="utf-8") as f:
                                giveaways = json.load(f)
                            for gw in giveaways.values():
                                if gw.get("status") == "active":
                                    msg_id = int(gw["message_id"])
                                    view = GiveawayView(self, msg_id)
                                    self.bot.add_view(view, message_id=msg_id)
                        except Exception as e:
                            print(f"⚠️ 載入伺服器 {guild_entry} 抽獎視圖失敗: {e}")
        except Exception as e:
            print(f"⚠️ 註冊抽獎視圖發生異常: {e}")

    # ---------------- 今日發言監聽與統計 ----------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """監聽文字訊息，統計伺服器成員今日發言次數"""
        if message.author.bot or not message.guild:
            return
        self.record_user_message(message.guild.id, message.author.id)

    @tasks.loop(seconds=15.0)
    async def flush_stats_loop(self):
        """定期將記憶體中的用戶發言統計批次寫入檔案，降低磁碟 I/O"""
        self.flush_all_stats()

    def flush_all_stats(self):
        """將所有標記為修改過的伺服器發言統計持久化到檔案"""
        for guild_id in list(self._dirty_guilds):
            data = self._stats_cache.get(guild_id)
            if data:
                self.save_user_stats(guild_id, data)
        self._dirty_guilds.clear()

    def get_user_stats_path(self, guild_id: int) -> str:
        guild_dir = os.path.join(self.data_dir, str(guild_id))
        os.makedirs(guild_dir, exist_ok=True)
        return os.path.join(guild_dir, "giveaway_user_stats.json")

    def load_user_stats(self, guild_id: int) -> Dict[str, Any]:
        today = datetime.now().strftime("%Y-%m-%d")
        if guild_id in self._stats_cache:
            data = self._stats_cache[guild_id]
            if data.get("date") != today:
                data["date"] = today
                data["today_messages"] = {}
                self._dirty_guilds.add(guild_id)
            return data

        path = self.get_user_stats_path(guild_id)
        default_data = {"date": today, "today_messages": {}, "total_messages": {}}

        if not os.path.exists(path):
            self._stats_cache[guild_id] = default_data
            return default_data
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 若跨日則重置 today_messages
            if data.get("date") != today:
                data["date"] = today
                data["today_messages"] = {}
                self._dirty_guilds.add(guild_id)
            self._stats_cache[guild_id] = data
            return data
        except Exception:
            self._stats_cache[guild_id] = default_data
            return default_data

    def save_user_stats(self, guild_id: int, data: Dict[str, Any]):
        path = self.get_user_stats_path(guild_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record_user_message(self, guild_id: int, user_id: int):
        """累加用戶今日發言與總發言次數 (高速記憶體快取，異步定期落盤)"""
        data = self.load_user_stats(guild_id)
        uid_str = str(user_id)
        today_msgs = data.setdefault("today_messages", {})
        total_msgs = data.setdefault("total_messages", {})

        today_msgs[uid_str] = today_msgs.get(uid_str, 0) + 1
        total_msgs[uid_str] = total_msgs.get(uid_str, 0) + 1
        self._dirty_guilds.add(guild_id)

    def get_user_today_messages(self, guild_id: int, user_id: int) -> int:
        """獲取用戶今天在該伺服器的發言次數"""
        data = self.load_user_stats(guild_id)
        return data.get("today_messages", {}).get(str(user_id), 0)

    def get_user_total_messages(self, guild_id: int, user_id: int) -> int:
        """獲取用戶在該伺服器的累積總發言數 (整合 statistics.json / levels.json)"""
        counts = []
        uid_str = str(user_id)

        # 1. giveaway 自帶統計
        data = self.load_user_stats(guild_id)
        counts.append(data.get("total_messages", {}).get(uid_str, 0))

        # 2. levels.json
        levels_path = os.path.join(self.data_dir, str(guild_id), "levels.json")
        if os.path.exists(levels_path):
            try:
                with open(levels_path, "r", encoding="utf-8") as f:
                    levels_data = json.load(f)
                counts.append(levels_data.get(uid_str, {}).get("messages", 0))
            except Exception:
                pass

        # 3. statistics.json
        stats_path = os.path.join(self.data_dir, str(guild_id), "statistics.json")
        if os.path.exists(stats_path):
            try:
                with open(stats_path, "r", encoding="utf-8") as f:
                    stats_data = json.load(f)
                counts.append(stats_data.get("user_stats", {}).get(uid_str, {}).get("messages", 0))
            except Exception:
                pass

        return max(counts) if counts else 0

    def get_user_level(self, guild_id: int, user_id: int) -> int:
        """獲取用戶在該伺服器的等級 (讀取 levels.json)"""
        levels_path = os.path.join(self.data_dir, str(guild_id), "levels.json")
        if os.path.exists(levels_path):
            try:
                with open(levels_path, "r", encoding="utf-8") as f:
                    levels_data = json.load(f)
                return levels_data.get(str(user_id), {}).get("level", 0)
            except Exception:
                pass
        return 0

    def check_user_eligibility(self, guild: discord.Guild, member: discord.Member, gw: dict) -> Tuple[bool, str]:
        """檢查成員是否符合該抽獎的所有門檻條件"""
        failed_reasons = []

        # 1. 身分組檢查
        req_role_id = gw.get("required_role_id")
        if req_role_id:
            role = guild.get_role(int(req_role_id))
            if role and role not in member.roles:
                failed_reasons.append(f"• 身分組門檻：需持有 {role.mention}")

        # 2. 最低等級檢查
        min_level = gw.get("min_level")
        if min_level and min_level > 0:
            user_level = self.get_user_level(guild.id, member.id)
            if user_level < min_level:
                failed_reasons.append(f"• 等級門檻：需達到 **Lv.{min_level}** (您目前為 Lv.{user_level})")

        # 3. 今日發言數檢查
        req_today_msgs = gw.get("req_today_msgs")
        if req_today_msgs and req_today_msgs > 0:
            user_today_msgs = self.get_user_today_messages(guild.id, member.id)
            if user_today_msgs < req_today_msgs:
                failed_reasons.append(f"• 今日發言門檻：今天需在伺服器發言至少 **{req_today_msgs}** 句 (您今天已發言 {user_today_msgs} 句)")

        # 4. 歷史發言數檢查
        req_total_msgs = gw.get("req_total_msgs")
        if req_total_msgs and req_total_msgs > 0:
            user_total_msgs = self.get_user_total_messages(guild.id, member.id)
            if user_total_msgs < req_total_msgs:
                failed_reasons.append(f"• 歷史發言門檻：累積總發言需達到 **{req_total_msgs}** 句 (您目前累積 {user_total_msgs} 句)")

        if failed_reasons:
            msg = "❌ **您尚未符合本次抽獎的參加資格：**\n\n" + "\n".join(failed_reasons) + "\n\n💡 達成條件後即可再次點擊「參加抽獎」！"
            return False, msg
        return True, ""

    # ---------------- 抽獎資料存取 ----------------

    def get_giveaways_path(self, guild_id: int) -> str:
        guild_dir = os.path.join(self.data_dir, str(guild_id))
        os.makedirs(guild_dir, exist_ok=True)
        return os.path.join(guild_dir, "giveaways.json")

    def load_guild_giveaways(self, guild_id: int) -> Dict[str, Any]:
        path = self.get_giveaways_path(guild_id)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_guild_giveaways(self, guild_id: int, data: Dict[str, Any]):
        path = self.get_giveaways_path(guild_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_giveaway(self, guild_id: int, message_id: int) -> Optional[Dict[str, Any]]:
        all_gw = self.load_guild_giveaways(guild_id)
        return all_gw.get(str(message_id))

    def save_giveaway(self, guild_id: int, gw_data: Dict[str, Any]):
        all_gw = self.load_guild_giveaways(guild_id)
        all_gw[str(gw_data["message_id"])] = gw_data
        self.save_guild_giveaways(guild_id, all_gw)

    # ---------------- 抽獎卡片渲染 ----------------

    def create_giveaway_embed(self, gw: dict) -> discord.Embed:
        """建立進行中的抽獎 Embed"""
        end_ts = int(gw["end_timestamp"])
        count = len(gw.get("participants", []))
        winners_count = gw.get("winners_count", 1)

        embed = discord.Embed(
            title=f"🎉 抽獎活動：{gw['prize']}",
            color=discord.Color.from_rgb(255, 182, 193)  # 溫馨粉色
        )

        desc_lines = []
        if gw.get("description"):
            desc_lines.append(f"> {gw['description']}\n")

        desc_lines.append(f"• 點擊下方 **「🎉 參加抽獎」** 按鈕即可加入！")
        desc_lines.append(f"• 獲獎名額：**{winners_count}** 位")
        desc_lines.append(f"• 截止倒數：<t:{end_ts}:R> (<t:{end_ts}:f>)")
        desc_lines.append(f"• 發起人：<@{gw['host_id']}>")

        # 資格限制彙整展示
        req_role_id = gw.get("required_role_id")
        min_level = gw.get("min_level")
        req_today_msgs = gw.get("req_today_msgs")
        req_total_msgs = gw.get("req_total_msgs")

        requirements = []
        if req_role_id:
            requirements.append(f"持有身分組：<@&{req_role_id}>")
        if min_level and min_level > 0:
            requirements.append(f"最低等級要求：**Lv.{min_level}** 以上")
        if req_today_msgs and req_today_msgs > 0:
            requirements.append(f"今日發言要求：至少 **{req_today_msgs}** 句")
        if req_total_msgs and req_total_msgs > 0:
            requirements.append(f"歷史總發言要求：至少 **{req_total_msgs}** 句")

        if requirements:
            desc_lines.append("• 🔒 **參加資格門檻**：")
            for req in requirements:
                desc_lines.append(f"  └ {req}")

        desc_lines.append(f"• 目前參加人數：**{count}** 位")

        embed.description = "\n".join(desc_lines)
        embed.set_footer(text=f"抽獎 ID: {gw['message_id']} • 自動開獎系統")
        return embed

    def create_ended_embed(self, gw: dict, winners: List[int]) -> discord.Embed:
        """建立開獎結束後的 Embed"""
        embed = discord.Embed(
            title=f"🎊 抽獎活動已結束：{gw['prize']}",
            color=discord.Color.gold()
        )

        lines = []
        if gw.get("description"):
            lines.append(f"> {gw['description']}\n")

        lines.append(f"• 發起人：<@{gw['host_id']}>")
        lines.append(f"• 總參加人數：**{len(gw.get('participants', []))}** 位")

        if winners:
            winners_str = ", ".join(f"<@{uid}>" for uid in winners)
            lines.append(f"• 🏆 **恭喜幸運得主**：{winners_str}")
        else:
            lines.append("• 🏆 **幸運得主**：無符合資格之參加者，本次抽獎流標。")

        embed.description = "\n".join(lines)
        embed.set_footer(text=f"抽獎 ID: {gw['message_id']} • 開獎完成")
        return embed

    async def update_giveaway_message(self, guild: discord.Guild, gw: dict):
        """更新抽獎訊息中的參加人數與卡片內容"""
        try:
            channel = guild.get_channel(int(gw["channel_id"]))
            if not channel:
                channel = await guild.fetch_channel(int(gw["channel_id"]))
            if channel:
                msg = await channel.fetch_message(int(gw["message_id"]))
                embed = self.create_giveaway_embed(gw)
                await msg.edit(embed=embed)
        except Exception:
            pass

    # ---------------- 定時巡邏與開獎邏輯 ----------------

    @tasks.loop(seconds=5.0)
    async def check_giveaways(self):
        """定期檢查所有到期的抽獎活動"""
        now_ts = datetime.now(timezone.utc).timestamp()

        for guild in self.bot.guilds:
            giveaways = self.load_guild_giveaways(guild.id)

            for msg_id_str, gw in list(giveaways.items()):
                if gw.get("status") == "active":
                    end_ts = float(gw.get("end_timestamp", 0))
                    if now_ts >= end_ts:
                        await self.end_giveaway(guild, gw)

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    async def end_giveaway(self, guild: discord.Guild, gw: dict, manual_winner_count: Optional[int] = None) -> List[int]:
        """結束抽獎並抽出得主 (複驗資格)"""
        gw["status"] = "ended"
        participants: List[int] = gw.get("participants", [])
        winners_count = manual_winner_count or gw.get("winners_count", 1)

        # 複驗資格並隨機抽選
        valid_candidates = []
        for uid in participants:
            member = guild.get_member(uid)
            if not member:
                try:
                    member = await guild.fetch_member(uid)
                except Exception:
                    member = None
            if member:
                eligible, _ = self.check_user_eligibility(guild, member, gw)
                if eligible:
                    valid_candidates.append(uid)

        winners = []
        if valid_candidates:
            draw_count = min(winners_count, len(valid_candidates))
            winners = random.sample(valid_candidates, draw_count)

        gw["winners"] = winners
        gw["ended_at"] = datetime.now(timezone.utc).isoformat()
        self.save_giveaway(guild.id, gw)

        # 更新 Discord 訊息
        try:
            channel = guild.get_channel(int(gw["channel_id"]))
            if not channel:
                channel = await guild.fetch_channel(int(gw["channel_id"]))
            if channel:
                msg = await channel.fetch_message(int(gw["message_id"]))
                ended_embed = self.create_ended_embed(gw, winners)
                await msg.edit(embed=ended_embed, view=None)

                # 發送中獎祝賀通知
                if winners:
                    winners_mentions = " ".join(f"<@{uid}>" for uid in winners)
                    await channel.send(
                        f"🎉 恭喜 {winners_mentions} 贏得 **{gw['prize']}**！請留意發起人 <@{gw['host_id']}> 的領獎資訊！",
                        reference=msg
                    )
                else:
                    await channel.send(
                        f"📢 抽獎 **{gw['prize']}** 已結束，由於沒有符合資格的參加者，本次抽獎流標。",
                        reference=msg
                    )
        except Exception as e:
            print(f"⚠️ 開獎推播失敗 (Guild {guild.id}, Msg {gw.get('message_id')}): {e}")

        return winners

    # ---------------- 斜線指令群組 ----------------

    giveaway_group = app_commands.Group(
        name="抽獎",
        description="🎁 伺服器福利與抽獎活動系統"
    )

    @giveaway_group.command(name="發起", description="發起一場新的抽獎活動 (支援身分組、等級、今日發言等門檻)")
    @app_commands.describe(
        獎品="抽獎獎品名稱 (例如: Discord Nitro 1個月、1000 遊戲金幣)",
        時長="抽獎持續時間 (例如: 30s, 10m, 2h, 1d, 1w)",
        獲獎人數="預計抽出之中獎名額 (預設 1 人)",
        頻道="發布抽獎的頻道 (預設為當前頻道)",
        資格身分組="限制必須持有該身分組方可參加 (選填)",
        最低等級="限制需達到之等級門檻 (選填，如: 5 代表 Lv.5 以上)",
        今日發言要求="限制今天在伺服器發言需達指定次數 (選填，如: 3 代表需講超過3句話)",
        歷史發言要求="限制伺服器累積總發言數需達指定次數 (選填)",
        說明="補充抽獎規則、贊助者或額外備註說明 (選填)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_start(
        self,
        interaction: discord.Interaction,
        獎品: str,
        時長: str,
        獲獎人數: Optional[app_commands.Range[int, 1, 20]] = 1,
        頻道: Optional[discord.TextChannel] = None,
        資格身分組: Optional[discord.Role] = None,
        最低等級: Optional[app_commands.Range[int, 1, 100]] = None,
        今日發言要求: Optional[app_commands.Range[int, 1, 1000]] = None,
        歷史發言要求: Optional[app_commands.Range[int, 1, 100000]] = None,
        說明: Optional[str] = None
    ):
        """發起抽獎"""
        duration_sec = parse_duration(時長)
        if not duration_sec or duration_sec < 10:
            await interaction.response.send_message(
                "❌ 時長格式錯誤或太短！請輸入至少 10 秒以上的有效時長（如 `30s`、`10m`、`2h`、`1d`、`1w`）。",
                ephemeral=True
            )
            return

        target_channel = 頻道 or interaction.channel
        now_dt = datetime.now(timezone.utc)
        end_timestamp = now_dt.timestamp() + duration_sec

        gw_data = {
            "guild_id": interaction.guild.id,
            "channel_id": target_channel.id,
            "message_id": 0,
            "prize": 獎品.strip(),
            "winners_count": 獲獎人數,
            "host_id": interaction.user.id,
            "host_name": str(interaction.user),
            "start_timestamp": now_dt.timestamp(),
            "end_timestamp": end_timestamp,
            "required_role_id": 資格身分組.id if 資格身分組 else None,
            "min_level": 最低等級,
            "req_today_msgs": 今日發言要求,
            "req_total_msgs": 歷史發言要求,
            "description": 說明.strip() if 說明 else "",
            "participants": [],
            "winners": [],
            "status": "active"
        }

        # 發送預覽訊息
        temp_embed = self.create_giveaway_embed(gw_data)
        try:
            msg = await target_channel.send(embed=temp_embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ 機器人在頻道 {target_channel.mention} 沒有發送訊息的權限！",
                ephemeral=True
            )
            return

        gw_data["message_id"] = msg.id

        # 綁定持久化 View 並更新訊息
        view = GiveawayView(self, msg.id)
        self.bot.add_view(view, message_id=msg.id)
        final_embed = self.create_giveaway_embed(gw_data)
        await msg.edit(embed=final_embed, view=view)

        # 儲存抽獎資料
        self.save_giveaway(interaction.guild.id, gw_data)

        # 提示發起成功，並列出門檻摘要
        restr_summary = []
        if 資格身分組:
            restr_summary.append(f"身分組: {資格身分組.name}")
        if 最低等級:
            restr_summary.append(f"等級: Lv.{最低等級}+")
        if 今日發言要求:
            restr_summary.append(f"今日發言: {今日發言要求}句+")
        if 歷史發言要求:
            restr_summary.append(f"累積發言: {歷史發言要求}句+")

        restr_str = f"（門檻：{', '.join(restr_summary)}）" if restr_summary else "（無門檻限制）"

        await interaction.response.send_message(
            f"✅ 成功在 {target_channel.mention} 發起 **{獎品}** 抽獎活動 {restr_str}！\n[點此前往查看抽獎訊息]({msg.jump_url})",
            ephemeral=True
        )

    @giveaway_group.command(name="結束", description="提前結束指定抽獎活動並立即開獎")
    @app_commands.describe(訊息id="抽獎訊息的 ID (可在抽獎卡片底部查看)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_end(self, interaction: discord.Interaction, 訊息id: str):
        """手動結束抽獎"""
        if not 訊息id.isdigit():
            await interaction.response.send_message("❌ 請輸入有效的數字訊息 ID！", ephemeral=True)
            return

        msg_id = int(訊息id)
        gw = self.get_giveaway(interaction.guild.id, msg_id)

        if not gw:
            await interaction.response.send_message("❌ 找不到該抽獎紀錄，請確認訊息 ID 是否正確！", ephemeral=True)
            return

        if gw.get("status") != "active":
            await interaction.response.send_message("❌ 此抽獎活動已經結束或已被取消！", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        winners = await self.end_giveaway(interaction.guild, gw)

        if winners:
            win_str = ", ".join(f"<@{uid}>" for uid in winners)
            await interaction.followup.send(f"✅ 抽獎活動已提前結束並開獎！幸運得主為：{win_str}")
        else:
            await interaction.followup.send("✅ 抽獎活動已提前結束！因無符合資格的參加者，本次抽獎流標。")

    @giveaway_group.command(name="重抽", description="為已結束的抽獎活動重新抽選中獎者")
    @app_commands.describe(
        訊息id="抽獎訊息的 ID",
        人數="重新抽出之人數 (預設 1 人)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_reroll(
        self,
        interaction: discord.Interaction,
        訊息id: str,
        人數: Optional[app_commands.Range[int, 1, 10]] = 1
    ):
        """重新抽獎"""
        if not 訊息id.isdigit():
            await interaction.response.send_message("❌ 請輸入有效的數字訊息 ID！", ephemeral=True)
            return

        msg_id = int(訊息id)
        gw = self.get_giveaway(interaction.guild.id, msg_id)

        if not gw:
            await interaction.response.send_message("❌ 找不到該抽獎紀錄！", ephemeral=True)
            return

        if gw.get("status") != "ended":
            await interaction.response.send_message("❌ 只有已結束的抽獎才能進行重抽！", ephemeral=True)
            return

        participants: List[int] = gw.get("participants", [])
        if not participants:
            await interaction.response.send_message("❌ 該抽獎沒有任何參加者，無法進行重抽！", ephemeral=True)
            return

        # 排除原獲獎者（若名額充裕）且複驗資格
        old_winners = gw.get("winners", [])
        pool = []
        for uid in participants:
            if uid not in old_winners:
                member = interaction.guild.get_member(uid)
                if not member:
                    try:
                        member = await interaction.guild.fetch_member(uid)
                    except Exception:
                        member = None
                if member:
                    eligible, _ = self.check_user_eligibility(interaction.guild, member, gw)
                    if eligible:
                        pool.append(uid)

        if not pool:
            # 回退至全體符合資格者
            for uid in participants:
                member = interaction.guild.get_member(uid)
                if not member:
                    try:
                        member = await interaction.guild.fetch_member(uid)
                    except Exception:
                        member = None
                if member:
                    eligible, _ = self.check_user_eligibility(interaction.guild, member, gw)
                    if eligible:
                        pool.append(uid)

        if not pool:
            await interaction.response.send_message("❌ 目前無任何符合資格的成員可供重抽！", ephemeral=True)
            return

        draw_count = min(人數, len(pool))
        new_winners = random.sample(pool, draw_count)

        gw["winners"] = new_winners
        self.save_giveaway(interaction.guild.id, gw)

        channel = interaction.guild.get_channel(int(gw["channel_id"]))
        if not channel:
            try:
                channel = await interaction.guild.fetch_channel(int(gw["channel_id"]))
            except Exception:
                channel = None
        if channel:
            try:
                msg = await channel.fetch_message(msg_id)
                ended_embed = self.create_ended_embed(gw, new_winners)
                await msg.edit(embed=ended_embed)
                mentions = " ".join(f"<@{uid}>" for uid in new_winners)
                await channel.send(
                    f"🎉 **【重新抽選得主】** 恭喜 {mentions} 成為 **{gw['prize']}** 的新得主！",
                    reference=msg
                )
            except Exception:
                pass

        win_mentions = ", ".join(f"<@{uid}>" for uid in new_winners)
        await interaction.response.send_message(f"✅ 重抽成功！新得主為：{win_mentions}", ephemeral=True)

    @giveaway_group.command(name="取消", description="取消進行中的抽獎活動 (不開獎)")
    @app_commands.describe(訊息id="抽獎訊息的 ID")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_cancel(self, interaction: discord.Interaction, 訊息id: str):
        """取消抽獎"""
        if not 訊息id.isdigit():
            await interaction.response.send_message("❌ 請輸入有效的數字訊息 ID！", ephemeral=True)
            return

        msg_id = int(訊息id)
        gw = self.get_giveaway(interaction.guild.id, msg_id)

        if not gw:
            await interaction.response.send_message("❌ 找不到該抽獎紀錄！", ephemeral=True)
            return

        if gw.get("status") != "active":
            await interaction.response.send_message("❌ 該抽獎活動已不是進行中狀態，無法取消！", ephemeral=True)
            return

        gw["status"] = "cancelled"
        self.save_giveaway(interaction.guild.id, gw)

        channel = interaction.guild.get_channel(int(gw["channel_id"]))
        if channel:
            try:
                msg = await channel.fetch_message(msg_id)
                embed = discord.Embed(
                    title=f"🚫 抽獎活動已取消：{gw['prize']}",
                    description=f"此抽獎活動已被管理員 <@{interaction.user.id}> 取消，不進行開獎。",
                    color=discord.Color.red()
                )
                await msg.edit(embed=embed, view=None)
            except Exception:
                pass

        await interaction.response.send_message("✅ 抽獎活動已成功取消！", ephemeral=True)

    @giveaway_group.command(name="列表", description="查看本伺服器進行中的抽獎清單")
    async def giveaway_list(self, interaction: discord.Interaction):
        """列出進行中的抽獎"""
        giveaways = self.load_guild_giveaways(interaction.guild.id)
        active_list = [gw for gw in giveaways.values() if gw.get("status") == "active"]

        embed = discord.Embed(
            title=f"🎁 伺服器抽獎清單 — {interaction.guild.name}",
            color=discord.Color.blue()
        )

        if not active_list:
            embed.description = "目前沒有任何正在進行中的抽獎活動。"
        else:
            embed.description = f"目前共有 **{len(active_list)}** 場抽獎進行中：\n"
            for gw in active_list[:10]:
                end_ts = int(gw["end_timestamp"])
                embed.add_field(
                    name=f"🎉 {gw['prize']} (名額: {gw.get('winners_count', 1)})",
                    value=(
                        f"• 頻道: <#{gw['channel_id']}>\n"
                        f"• 截止時間: <t:{end_ts}:R>\n"
                        f"• 目前參加: **{len(gw.get('participants', []))}** 人\n"
                        f"• ID: `{gw['message_id']}`"
                    ),
                    inline=False
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaway(bot))
