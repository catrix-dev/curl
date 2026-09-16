import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime

class Achievements(commands.Cog):
    """成就系統"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_folder = './data'
        
        # 定義成就
        self.achievement_definitions = {
            # 訊息成就
            'first_message': {
                'name': '📝 初次發言',
                'description': '發送第一條訊息',
                'category': 'messages',
                'requirement': 1,
                'tier': 'common'
            },
            'chatty_100': {
                'name': '💬 健談者',
                'description': '發送 100 條訊息',
                'category': 'messages',
                'requirement': 100,
                'tier': 'common'
            },
            'chatty_500': {
                'name': '💬 話癆',
                'description': '發送 500 條訊息',
                'category': 'messages',
                'requirement': 500,
                'tier': 'rare'
            },
            'chatty_1000': {
                'name': '💬 聊天大師',
                'description': '發送 1000 條訊息',
                'category': 'messages',
                'requirement': 1000,
                'tier': 'epic'
            },
            
            # 等級成就
            'level_5': {
                'name': '⭐ 新手',
                'description': '達到 5 級',
                'category': 'level',
                'requirement': 5,
                'tier': 'common'
            },
            'level_10': {
                'name': '⭐ 進階',
                'description': '達到 10 級',
                'category': 'level',
                'requirement': 10,
                'tier': 'common'
            },
            'level_25': {
                'name': '⭐ 專家',
                'description': '達到 25 級',
                'category': 'level',
                'requirement': 25,
                'tier': 'rare'
            },
            'level_50': {
                'name': '⭐ 大師',
                'description': '達到 50 級',
                'category': 'level',
                'requirement': 50,
                'tier': 'epic'
            },
            'level_100': {
                'name': '⭐ 傳奇',
                'description': '達到 100 級',
                'category': 'level',
                'requirement': 100,
                'tier': 'legendary'
            },
            
            # 遊戲成就
            'first_win': {
                'name': '🎮 初次勝利',
                'description': '贏得第一場遊戲',
                'category': 'game_wins',
                'requirement': 1,
                'tier': 'common'
            },
            'winner_10': {
                'name': '🎮 勝利者',
                'description': '贏得 10 場遊戲',
                'category': 'game_wins',
                'requirement': 10,
                'tier': 'common'
            },
            'winner_50': {
                'name': '🎮 常勝軍',
                'description': '贏得 50 場遊戲',
                'category': 'game_wins',
                'requirement': 50,
                'tier': 'rare'
            },
            'winner_100': {
                'name': '🎮 遊戲大師',
                'description': '贏得 100 場遊戲',
                'category': 'game_wins',
                'requirement': 100,
                'tier': 'epic'
            },
            
            # 簽到成就
            'daily_7': {
                'name': '📅 堅持一週',
                'description': '連續簽到 7 天',
                'category': 'daily_streak',
                'requirement': 7,
                'tier': 'common'
            },
            'daily_30': {
                'name': '📅 堅持一月',
                'description': '連續簽到 30 天',
                'category': 'daily_streak',
                'requirement': 30,
                'tier': 'rare'
            },
            'daily_100': {
                'name': '📅 堅持百日',
                'description': '連續簽到 100 天',
                'category': 'daily_streak',
                'requirement': 100,
                'tier': 'epic'
            },
            'daily_365': {
                'name': '📅 全勤王',
                'description': '連續簽到 365 天',
                'category': 'daily_streak',
                'requirement': 365,
                'tier': 'legendary'
            },
            
            # 社交成就
            'social_butterfly': {
                'name': '🦋 社交達人',
                'description': '與 10 個不同的人互動',
                'category': 'special',
                'requirement': 1,
                'tier': 'rare'
            },
            'early_bird': {
                'name': '🌅 早起的鳥兒',
                'description': '在早上 6 點前發送訊息',
                'category': 'special',
                'requirement': 1,
                'tier': 'common'
            },
            'night_owl': {
                'name': '🦉 夜貓子',
                'description': '在凌晨 2 點後發送訊息',
                'category': 'special',
                'requirement': 1,
                'tier': 'common'
            },
        }
    
    def get_achievement_file(self, guild_id: int) -> str:
        """獲取成就檔案路徑"""
        folder = os.path.join(self.data_folder, str(guild_id))
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, 'achievements.json')
    
    def load_achievements(self, guild_id: int) -> dict:
        """載入成就數據（具備 list 結構向相容 dict 結構平滑遷移能力）"""
        file_path = self.get_achievement_file(guild_id)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    needs_save = False
                    for u_k, u_v in list(data.items()):
                        if isinstance(u_v, list):
                            data[u_k] = {
                                'unlocked': list(u_v),
                                'progress': {}
                            }
                            for a_id in u_v:
                                data[u_k][a_id] = {'unlocked_at': datetime.utcnow().isoformat()}
                            needs_save = True
                    if needs_save:
                        self.save_achievements(guild_id, data)
                    return data
            except Exception:
                pass
        return {}
    
    def save_achievements(self, guild_id: int, achievements: dict):
        """儲存成就數據"""
        file_path = self.get_achievement_file(guild_id)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(achievements, f, ensure_ascii=False, indent=2)
    
    def unlock_achievement(self, guild_id: int, user_id: int, achievement_id: str) -> bool:
        """解鎖成就"""
        achievements = self.load_achievements(guild_id)
        user_key = str(user_id)
        
        if user_key not in achievements:
            achievements[user_key] = {
                'unlocked': [],
                'progress': {}
            }
        
        if achievement_id not in achievements[user_key]['unlocked']:
            achievements[user_key]['unlocked'].append(achievement_id)
            achievements[user_key][achievement_id] = {
                'unlocked_at': datetime.utcnow().isoformat()
            }
            self.save_achievements(guild_id, achievements)
            return True
        
        return False
    
    async def check_achievements(self, guild_id: int, user_id: int):
        """檢查並解鎖成就"""
        # 獲取用戶統計
        stats = {}
        
        # 等級數據
        levels_file = os.path.join(self.data_folder, str(guild_id), 'levels.json')
        if os.path.exists(levels_file):
            with open(levels_file, 'r', encoding='utf-8') as f:
                levels_data = json.load(f)
                user_key = str(user_id)
                if user_key in levels_data:
                    stats['level'] = levels_data[user_key].get('level', 0)
                    stats['messages'] = levels_data[user_key].get('messages', 0)
        
        # 遊戲數據
        game_file = os.path.join(self.data_folder, str(guild_id), 'game_stats.json')
        if os.path.exists(game_file):
            with open(game_file, 'r', encoding='utf-8') as f:
                game_data = json.load(f)
                user_key = str(user_id)
                if user_key in game_data:
                    stats['game_wins'] = game_data[user_key].get('total_wins', game_data[user_key].get('wins', 0))
        
        # 簽到數據
        daily_file = os.path.join(self.data_folder, str(guild_id), 'daily.json')
        if os.path.exists(daily_file):
            with open(daily_file, 'r', encoding='utf-8') as f:
                daily_data = json.load(f)
                user_key = str(user_id)
                if user_key in daily_data:
                    stats['daily_streak'] = daily_data[user_key].get('streak', 0)
        
        # 檢查成就
        unlocked = []
        for achievement_id, achievement in self.achievement_definitions.items():
            category = achievement['category']
            requirement = achievement['requirement']
            
            if category in stats and stats[category] >= requirement:
                if self.unlock_achievement(guild_id, user_id, achievement_id):
                    unlocked.append(achievement)
        
        return unlocked
    
    achievement_group = app_commands.Group(name="成就", description="成就系統")
    
    @achievement_group.command(name="列表", description="查看所有成就")
    async def list_achievements(self, interaction: discord.Interaction):
        """查看所有成就"""
        guild_id = interaction.guild.id
        user_achievements = self.load_achievements(guild_id)
        user_key = str(interaction.user.id)
        unlocked = user_achievements.get(user_key, {}).get('unlocked', [])
        
        embed = discord.Embed(
            title="🏆 成就系統",
            description=f"已解鎖 **{len(unlocked)}** / **{len(self.achievement_definitions)}** 個成就",
            color=discord.Color.from_rgb(37, 99, 235),
            timestamp=datetime.utcnow()
        )
        
        # 按稀有度分類
        tiers = {
            'common': {'name': '普通', 'emoji': '⚪', 'achievements': []},
            'rare': {'name': '稀有', 'emoji': '🔵', 'achievements': []},
            'epic': {'name': '史詩', 'emoji': '🟣', 'achievements': []},
            'legendary': {'name': '傳奇', 'emoji': '🟡', 'achievements': []}
        }
        
        for achievement_id, achievement in self.achievement_definitions.items():
            tier = achievement['tier']
            is_unlocked = achievement_id in unlocked
            status = "✅" if is_unlocked else "🔒"
            
            tiers[tier]['achievements'].append(
                f"{status} {achievement['name']} - {achievement['description']}"
            )
        
        for tier_key, tier_data in tiers.items():
            if tier_data['achievements']:
                embed.add_field(
                    name=f"{tier_data['emoji']} {tier_data['name']}成就",
                    value="\n".join(tier_data['achievements'][:5]),  # 限制顯示數量
                    inline=False
                )
        
        embed.set_footer(text="完成特定任務以解鎖成就")
        
        await interaction.response.send_message(embed=embed)
    
    @achievement_group.command(name="我的成就", description="查看我的成就")
    async def my_achievements(self, interaction: discord.Interaction):
        """查看自己的成就"""
        guild_id = interaction.guild.id
        user_achievements = self.load_achievements(guild_id)
        user_key = str(interaction.user.id)
        unlocked = user_achievements.get(user_key, {}).get('unlocked', [])
        
        if not unlocked:
            await interaction.response.send_message(
                "❌ 你還沒有解鎖任何成就！\n使用 `/成就 列表` 查看所有可用成就。",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🏆 我的成就",
            description=f"已解鎖 **{len(unlocked)}** 個成就",
            color=discord.Color.from_rgb(37, 99, 235),
            timestamp=datetime.utcnow()
        )
        
        # 顯示已解鎖的成就
        achievement_list = []
        for achievement_id in unlocked[:20]:  # 限制顯示 20 個
            if achievement_id in self.achievement_definitions:
                achievement = self.achievement_definitions[achievement_id]
                user_obj = user_achievements.get(user_key, {})
                unlocked_at = user_obj.get(achievement_id, {}).get('unlocked_at') if isinstance(user_obj, dict) else None
                
                if unlocked_at:
                    try:
                        date = datetime.fromisoformat(unlocked_at).strftime("%Y-%m-%d")
                    except:
                        date = "未知"
                else:
                    date = "未知"
                
                achievement_list.append(
                    f"{achievement['name']}\n{achievement['description']}\n解鎖於：{date}"
                )
        
        if achievement_list:
            embed.add_field(
                name="已解鎖成就",
                value="\n\n".join(achievement_list),
                inline=False
            )
        else:
            embed.add_field(
                name="已解鎖成就",
                value="尚未解鎖任何成就",
                inline=False
            )
        
        embed.set_footer(text=f"用戶：{interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)
    
    @achievement_group.command(name="進度", description="查看自己的成就進度")
    async def view_progress(self, interaction: discord.Interaction):
        """查看成就進度"""
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        user_key = str(user_id)
        
        # 獲取統計數據
        stats = {
            'level': 0,
            'messages': 0,
            'game_wins': 0,
            'daily_streak': 0
        }
        
        # 等級數據
        levels_file = os.path.join(self.data_folder, str(guild_id), 'levels.json')
        if os.path.exists(levels_file):
            with open(levels_file, 'r', encoding='utf-8') as f:
                levels_data = json.load(f)
                if user_key in levels_data:
                    stats['level'] = levels_data[user_key].get('level', 0)
                    stats['messages'] = levels_data[user_key].get('messages', 0)
        
        # 遊戲數據
        game_file = os.path.join(self.data_folder, str(guild_id), 'game_stats.json')
        if os.path.exists(game_file):
            with open(game_file, 'r', encoding='utf-8') as f:
                game_data = json.load(f)
                if user_key in game_data:
                    stats['game_wins'] = game_data[user_key].get('total_wins', game_data[user_key].get('wins', 0))
        
        # 簽到數據
        daily_file = os.path.join(self.data_folder, str(guild_id), 'daily.json')
        if os.path.exists(daily_file):
            with open(daily_file, 'r', encoding='utf-8') as f:
                daily_data = json.load(f)
                user_key = str(user_id)
                if user_key in daily_data:
                    stats['daily_streak'] = daily_data[user_key].get('streak', 0)
        
        embed = discord.Embed(
            title="📊 成就進度",
            color=discord.Color.from_rgb(37, 99, 235),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="⭐ 等級",
            value=f"當前等級：**{stats['level']}**",
            inline=True
        )
        
        embed.add_field(
            name="💬 訊息",
            value=f"已發送：**{stats['messages']}** 條",
            inline=True
        )
        
        embed.add_field(
            name="🎮 遊戲勝利",
            value=f"勝場：**{stats['game_wins']}**",
            inline=True
        )
        
        embed.add_field(
            name="📅 簽到",
            value=f"連續：**{stats['daily_streak']}** 天",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'📦 {self.__class__.__name__} cog已載入')

async def setup(bot):
    await bot.add_cog(Achievements(bot))
