import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime, timedelta
import random
import asyncio

class Daily(commands.Cog):
    """每日簽到系統"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_dir = "data"
        self.daily_data = {}
        self.lock = asyncio.Lock()
        os.makedirs(self.data_dir, exist_ok=True)
    
    def get_data_file(self, guild_id: str):
        """獲取伺服器數據檔案路徑"""
        guild_dir = os.path.join(self.data_dir, guild_id)
        os.makedirs(guild_dir, exist_ok=True)
        return os.path.join(guild_dir, "daily.json")
    
    def load_data(self, guild_id: str):
        """載入簽到數據"""
        data_file = self.get_data_file(guild_id)
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_data(self, guild_id: str):
        """保存簽到數據"""
        data_file = self.get_data_file(guild_id)
        tmp_file = data_file + f".tmp_{os.getpid()}"
        try:
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(self.daily_data.get(guild_id, {}), f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, data_file)
        except Exception:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass
            raise
    
    def get_user_data(self, guild_id: str, user_id: str):
        """獲取用戶簽到數據"""
        if guild_id not in self.daily_data:
            self.daily_data[guild_id] = self.load_data(guild_id)
        
        if user_id not in self.daily_data[guild_id]:
            self.daily_data[guild_id][user_id] = {
                "last_checkin": None,
                "streak": 0,
                "total_checkins": 0,
                "total_points": 0
            }
        
        return self.daily_data[guild_id][user_id]
    
    def can_checkin(self, last_checkin: str) -> bool:
        """檢查是否可以簽到"""
        if not last_checkin:
            return True
        
        last = datetime.fromisoformat(last_checkin)
        now = datetime.utcnow()
        
        # 檢查是否是不同的一天
        return last.date() < now.date()
    
    def is_consecutive(self, last_checkin: str) -> bool:
        """檢查是否為連續簽到"""
        if not last_checkin:
            return False
        
        last = datetime.fromisoformat(last_checkin)
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        
        return last.date() == yesterday
    
    # 創建指令組
    daily_group = app_commands.Group(name="簽到", description="每日簽到系統")
    
    @daily_group.command(name="打卡", description="每日簽到獲取積分")
    async def checkin(self, interaction: discord.Interaction):
        """每日簽到"""
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        async with self.lock:
            data = self.get_user_data(guild_id, user_id)
            
            # 檢查是否可以簽到
            if not self.can_checkin(data["last_checkin"]):
                last = datetime.fromisoformat(data["last_checkin"])
                next_checkin = last + timedelta(days=1)
                time_left = next_checkin - datetime.utcnow()
                hours = int(time_left.total_seconds() // 3600)
                minutes = int((time_left.total_seconds() % 3600) // 60)
                
                await interaction.response.send_message(
                    f"❌ 你今天已經簽到過了！\n下次簽到時間：{hours} 小時 {minutes} 分鐘後",
                    ephemeral=True
                )
                return
            
            # 檢查連續簽到
            if self.is_consecutive(data["last_checkin"]):
                data["streak"] += 1
            else:
                data["streak"] = 1
            
            # 計算獎勵
            base_points = random.randint(50, 100)
            streak_bonus = min(data["streak"] * 5, 100)  # 最多額外 100 分
            total_points = base_points + streak_bonus
            
            # 更新數據
            data["last_checkin"] = datetime.utcnow().isoformat()
            data["total_checkins"] += 1
            data["total_points"] += total_points
            
            self.save_data(guild_id)
            streak_val = data["streak"]
            total_pts = data["total_points"]
            total_chks = data["total_checkins"]
        
        # 觸發成就檢查
        achievements_cog = self.bot.get_cog("Achievements")
        if achievements_cog:
            asyncio.create_task(achievements_cog.check_achievements(interaction.user, interaction.guild, "daily", streak_val))
        
        # 創建嵌入訊息
        embed = discord.Embed(
            title="✅ 簽到成功！",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        embed.add_field(name="獲得積分", value=f"🪙 **{total_points}** 分", inline=True)
        embed.add_field(name="連續簽到", value=f"🔥 **{streak_val}** 天", inline=True)
        embed.add_field(name="總積分", value=f"💰 **{total_pts}** 分", inline=True)
        
        if streak_bonus > 0:
            embed.add_field(
                name="連續獎勵",
                value=f"額外獲得 **{streak_bonus}** 分！",
                inline=False
            )
        
        embed.set_footer(text=f"第 {total_chks} 次簽到")
        
        await interaction.response.send_message(embed=embed)
    
    @daily_group.command(name="查看", description="查看簽到資訊")
    async def view(self, interaction: discord.Interaction, user: discord.Member = None):
        """查看簽到資訊"""
        user = user or interaction.user
        
        if user.bot:
            await interaction.response.send_message("❌ 機器人沒有簽到記錄！", ephemeral=True)
            return
        
        guild_id = str(interaction.guild.id)
        user_id = str(user.id)
        
        data = self.get_user_data(guild_id, user_id)
        
        embed = discord.Embed(
            title=f"📅 {user.name} 的簽到資訊",
            color=user.color or discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        embed.add_field(name="總積分", value=f"💰 **{data['total_points']}**", inline=True)
        embed.add_field(name="連續簽到", value=f"🔥 **{data['streak']}** 天", inline=True)
        embed.add_field(name="簽到次數", value=f"📊 **{data['total_checkins']}** 次", inline=True)
        
        if data["last_checkin"]:
            last = datetime.fromisoformat(data["last_checkin"])
            embed.add_field(
                name="上次簽到",
                value=discord.utils.format_dt(last, style='R'),
                inline=False
            )
        else:
            embed.add_field(name="上次簽到", value="從未簽到", inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @daily_group.command(name="排行榜", description="查看簽到積分排行榜")
    async def leaderboard(self, interaction: discord.Interaction):
        """簽到排行榜"""
        await interaction.response.defer()
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.daily_data:
            self.daily_data[guild_id] = self.load_data(guild_id)
        
        if not self.daily_data[guild_id]:
            await interaction.followup.send("❌ 目前沒有任何簽到記錄", ephemeral=True)
            return
        
        # 排序用戶
        sorted_users = sorted(
            self.daily_data[guild_id].items(),
            key=lambda x: x[1]["total_points"],
            reverse=True
        )[:10]
        
        embed = discord.Embed(
            title=f"🏆 {interaction.guild.name} 簽到排行榜",
            description="積分前10名",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        
        medals = ["🥇", "🥈", "🥉"]
        
        for idx, (user_id, data) in enumerate(sorted_users, 1):
            try:
                uid = int(user_id)
                user = interaction.guild.get_member(uid) if interaction.guild else None
                if not user:
                    user = await self.bot.fetch_user(uid)
                name = user.display_name if user else f"未知用戶 ({user_id})"
                medal = medals[idx-1] if idx <= 3 else f"#{idx}"
                
                embed.add_field(
                    name=f"{medal} {name}",
                    value=f"積分: **{data['total_points']}** 💰\n連續: {data['streak']} 天 🔥\n簽到: {data['total_checkins']} 次",
                    inline=False
                )
            except:
                continue
        
        await interaction.followup.send(embed=embed)
    
    @daily_group.command(name="重置", description="重置用戶簽到數據（需要管理員權限）")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(user="要重置的用戶")
    async def reset(self, interaction: discord.Interaction, user: discord.Member):
        """重置簽到數據"""
        if user.bot:
            await interaction.response.send_message("❌ 無法重置機器人數據", ephemeral=True)
            return
        
        guild_id = str(interaction.guild.id)
        user_id = str(user.id)
        
        if guild_id not in self.daily_data:
            self.daily_data[guild_id] = self.load_data(guild_id)
        
        if user_id in self.daily_data[guild_id]:
            del self.daily_data[guild_id][user_id]
            self.save_data(guild_id)
            await interaction.response.send_message(f"✅ 已重置 {user.mention} 的簽到數據", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 該用戶沒有簽到數據", ephemeral=True)
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'📦 {self.__class__.__name__} cog已載入')
        # 載入所有伺服器的數據
        for guild in self.bot.guilds:
            guild_id = str(guild.id)
            self.daily_data[guild_id] = self.load_data(guild_id)
        print(f'📅 已載入 {len(self.daily_data)} 個伺服器的簽到數據')

async def setup(bot):
    await bot.add_cog(Daily(bot))
