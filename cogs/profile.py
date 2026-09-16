import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime

class Profile(commands.Cog):
    """個人資料卡片系統"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_folder = './data'
    
    def get_profile_file(self, guild_id: int) -> str:
        """獲取個人資料檔案路徑"""
        folder = os.path.join(self.data_folder, str(guild_id))
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, 'profiles.json')
    
    def load_profiles(self, guild_id: int) -> dict:
        """載入個人資料"""
        file_path = self.get_profile_file(guild_id)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_profiles(self, guild_id: int, profiles: dict):
        """儲存個人資料"""
        file_path = self.get_profile_file(guild_id)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)
    
    def get_user_profile(self, guild_id: int, user_id: int) -> dict:
        """獲取用戶資料"""
        profiles = self.load_profiles(guild_id)
        user_key = str(user_id)
        
        if user_key not in profiles:
            profiles[user_key] = {
                'bio': None,
                'color': None,
                'title': None,
                'created_at': datetime.utcnow().isoformat()
            }
            self.save_profiles(guild_id, profiles)
        
        return profiles[user_key]
    
    def get_user_stats(self, guild_id: int, user_id: int) -> dict:
        """獲取用戶統計數據"""
        stats = {
            'level': 0,
            'xp': 0,
            'rank': 0,
            'total_xp': 0,
            'messages': 0,
            'game_wins': 0,
            'game_losses': 0,
            'daily_streak': 0,
            'achievements': 0
        }
        
        # 獲取等級數據
        levels_file = os.path.join(self.data_folder, str(guild_id), 'levels.json')
        if os.path.exists(levels_file):
            with open(levels_file, 'r', encoding='utf-8') as f:
                levels_data = json.load(f)
                user_key = str(user_id)
                if user_key in levels_data:
                    u_data = levels_data[user_key]
                    lvl = u_data.get('level', 1)
                    tot_xp = u_data.get('total_xp', u_data.get('xp', 0))
                    
                    req_before = sum(100 + (l - 1) * 50 for l in range(1, lvl))
                    xp_in_level = max(0, tot_xp - req_before)
                    
                    stats['level'] = lvl
                    stats['xp'] = xp_in_level
                    stats['total_xp'] = tot_xp
                    stats['messages'] = u_data.get('messages', 0)
                    
                    # 計算排名
                    sorted_users = sorted(
                        levels_data.items(),
                        key=lambda x: x[1].get('total_xp', x[1].get('xp', 0)),
                        reverse=True
                    )
                    for idx, (uid, _) in enumerate(sorted_users, 1):
                        if uid == user_key:
                            stats['rank'] = idx
                            break
        
        # 獲取遊戲數據
        game_file = os.path.join(self.data_folder, str(guild_id), 'game_stats.json')
        if os.path.exists(game_file):
            with open(game_file, 'r', encoding='utf-8') as f:
                game_data = json.load(f)
                user_key = str(user_id)
                if user_key in game_data:
                    u_game = game_data[user_key]
                    total_wins = u_game.get('total_wins', u_game.get('wins', 0))
                    total_games = u_game.get('total_games', 0)
                    stats['game_wins'] = total_wins
                    stats['game_losses'] = max(0, total_games - total_wins) if total_games >= total_wins else u_game.get('losses', 0)
        
        # 獲取簽到數據
        daily_file = os.path.join(self.data_folder, str(guild_id), 'daily.json')
        if os.path.exists(daily_file):
            with open(daily_file, 'r', encoding='utf-8') as f:
                daily_data = json.load(f)
                user_key = str(user_id)
                if user_key in daily_data:
                    stats['daily_streak'] = daily_data[user_key].get('streak', 0)
        
        # 獲取成就數據
        achievement_file = os.path.join(self.data_folder, str(guild_id), 'achievements.json')
        if os.path.exists(achievement_file):
            with open(achievement_file, 'r', encoding='utf-8') as f:
                achievement_data = json.load(f)
                user_key = str(user_id)
                if user_key in achievement_data:
                    stats['achievements'] = len(achievement_data[user_key].get('unlocked', []))
        
        return stats
    
    profile_group = app_commands.Group(name="個人資料", description="個人資料卡片管理")
    
    @profile_group.command(name="查看", description="查看個人資料卡片")
    @app_commands.describe(用戶="要查看的用戶（留空查看自己）")
    async def view_profile(
        self,
        interaction: discord.Interaction,
        用戶: discord.Member = None
    ):
        """查看個人資料卡片"""
        target = 用戶 or interaction.user
        guild_id = interaction.guild.id
        
        # 獲取個人資料和統計
        profile = self.get_user_profile(guild_id, target.id)
        stats = self.get_user_stats(guild_id, target.id)
        
        # 創建嵌入
        embed_color = int(profile['color'], 16) if profile['color'] else discord.Color.from_rgb(37, 99, 235)
        embed = discord.Embed(
            title=f"📋 {target.display_name} 的個人資料",
            color=embed_color,
            timestamp=datetime.utcnow()
        )
        
        # 設置頭像
        embed.set_thumbnail(url=target.display_avatar.url)
        
        # 自定義標題
        if profile['title']:
            embed.description = f"*{profile['title']}*"
        
        # 個人簡介
        if profile['bio']:
            embed.add_field(
                name="📝 個人簡介",
                value=profile['bio'],
                inline=False
            )
        
        # 等級信息
        next_level_xp = 100 + (stats['level'] - 1) * 50
        xp_progress = f"{stats['xp']}/{next_level_xp}"
        progress_bar = self.create_progress_bar(stats['xp'], next_level_xp)
        
        embed.add_field(
            name="⭐ 等級系統",
            value=(
                f"等級：**{stats['level']}**\n"
                f"經驗：{xp_progress}\n"
                f"{progress_bar}\n"
                f"排名：**#{stats['rank']}**"
            ),
            inline=True
        )
        
        # 活躍統計
        embed.add_field(
            name="📊 活躍統計",
            value=(
                f"訊息數：**{stats['messages']}**\n"
                f"總經驗：**{stats['total_xp']}**\n"
                f"連續簽到：**{stats['daily_streak']}** 天"
            ),
            inline=True
        )
        
        # 遊戲統計
        total_games = stats['game_wins'] + stats['game_losses']
        win_rate = (stats['game_wins'] / total_games * 100) if total_games > 0 else 0
        
        embed.add_field(
            name="🎮 遊戲統計",
            value=(
                f"勝場：**{stats['game_wins']}**\n"
                f"敗場：**{stats['game_losses']}**\n"
                f"勝率：**{win_rate:.1f}%**"
            ),
            inline=True
        )
        
        # 成就
        embed.add_field(
            name="🏆 成就",
            value=f"已解鎖：**{stats['achievements']}** 個",
            inline=True
        )
        
        # 加入時間
        joined_at = target.joined_at.strftime("%Y年%m月%d日") if target.joined_at else "未知"
        embed.add_field(
            name="📅 加入時間",
            value=joined_at,
            inline=True
        )
        
        embed.set_footer(text=f"用戶 ID: {target.id}")
        
        await interaction.response.send_message(embed=embed)
    
    @profile_group.command(name="設定簡介", description="設定個人簡介")
    @app_commands.describe(簡介="你的個人簡介（最多100字）")
    async def set_bio(self, interaction: discord.Interaction, 簡介: str):
        """設定個人簡介"""
        if len(簡介) > 100:
            await interaction.response.send_message(
                "❌ 個人簡介不能超過 100 個字！",
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild.id
        profiles = self.load_profiles(guild_id)
        user_key = str(interaction.user.id)
        
        if user_key not in profiles:
            profiles[user_key] = {}
        
        profiles[user_key]['bio'] = 簡介
        self.save_profiles(guild_id, profiles)
        
        await interaction.response.send_message(
            f"✅ 已設定個人簡介：\n{簡介}"
        )
    
    @profile_group.command(name="設定標題", description="設定個人標題")
    @app_commands.describe(標題="你的個人標題（最多30字）")
    async def set_title(self, interaction: discord.Interaction, 標題: str):
        """設定個人標題"""
        if len(標題) > 30:
            await interaction.response.send_message(
                "❌ 個人標題不能超過 30 個字！",
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild.id
        profiles = self.load_profiles(guild_id)
        user_key = str(interaction.user.id)
        
        if user_key not in profiles:
            profiles[user_key] = {}
        
        profiles[user_key]['title'] = 標題
        self.save_profiles(guild_id, profiles)
        
        await interaction.response.send_message(
            f"✅ 已設定個人標題：*{標題}*"
        )
    
    @profile_group.command(name="設定顏色", description="設定資料卡顏色")
    @app_commands.describe(顏色="十六進位顏色代碼（例如：#2563eb）")
    async def set_color(self, interaction: discord.Interaction, 顏色: str):
        """設定資料卡顏色"""
        # 驗證顏色格式
        if not 顏色.startswith('#') or len(顏色) != 7:
            await interaction.response.send_message(
                "❌ 請使用正確的十六進位顏色格式（例如：#2563eb）",
                ephemeral=True
            )
            return
        
        try:
            int(顏色[1:], 16)  # 驗證是否為有效的十六進位
        except ValueError:
            await interaction.response.send_message(
                "❌ 無效的顏色代碼！",
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild.id
        profiles = self.load_profiles(guild_id)
        user_key = str(interaction.user.id)
        
        if user_key not in profiles:
            profiles[user_key] = {}
        
        profiles[user_key]['color'] = 顏色[1:]  # 移除 # 符號
        self.save_profiles(guild_id, profiles)
        
        # 創建預覽
        embed = discord.Embed(
            title="✅ 顏色已設定",
            description=f"你的資料卡現在使用這個顏色：{顏色}",
            color=int(顏色[1:], 16)
        )
        
        await interaction.response.send_message(embed=embed)
    
    @profile_group.command(name="清除", description="清除個人資料自定義設定")
    async def clear_profile(self, interaction: discord.Interaction):
        """清除個人資料"""
        guild_id = interaction.guild.id
        profiles = self.load_profiles(guild_id)
        user_key = str(interaction.user.id)
        
        if user_key in profiles:
            profiles[user_key] = {
                'bio': None,
                'color': None,
                'title': None,
                'created_at': profiles[user_key].get('created_at', datetime.utcnow().isoformat())
            }
            self.save_profiles(guild_id, profiles)
        
        await interaction.response.send_message(
            "✅ 已清除個人資料自定義設定"
        )
    
    def create_progress_bar(self, current: int, total: int, length: int = 10) -> str:
        """創建進度條"""
        filled = int((current / total) * length) if total > 0 else 0
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}]"
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'📦 {self.__class__.__name__} cog已載入')

async def setup(bot):
    await bot.add_cog(Profile(bot))
