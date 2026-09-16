import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio
import os
import json
from datetime import datetime

class Games(commands.Cog):
    """遊戲系統"""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}  # 儲存進行中的遊戲
    
    def save_game_stats(self, guild_id: int, user_id: int, game_type: str, won: bool):
        """儲存遊戲統計"""
        guild_id_str = str(guild_id)
        user_id_str = str(user_id)
        
        # 確保目錄存在
        data_dir = os.path.join('data', guild_id_str)
        os.makedirs(data_dir, exist_ok=True)
        
        file_path = os.path.join(data_dir, 'game_stats.json')
        
        # 讀取現有數據
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}
        
        # 初始化用戶數據
        if user_id_str not in data:
            data[user_id_str] = {
                'total_games': 0,
                'total_wins': 0,
                'games': {}
            }
        
        # 更新統計
        data[user_id_str]['total_games'] += 1
        if won:
            data[user_id_str]['total_wins'] += 1
        
        # 更新遊戲類型統計
        if game_type not in data[user_id_str]['games']:
            data[user_id_str]['games'][game_type] = {'played': 0, 'won': 0}
        
        data[user_id_str]['games'][game_type]['played'] += 1
        if won:
            data[user_id_str]['games'][game_type]['won'] += 1
        
        # 儲存數據
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_rewards(self, guild_id: int, user_id: int, won: bool):
        """添加獎勵（經驗值和積分，同步記憶體與磁碟並觸發成就檢查）"""
        # 1. 添加簽到積分（透過 Daily Cog 記憶體更新）
        try:
            daily_cog = self.bot.get_cog('Daily')
            if daily_cog:
                g_str = str(guild_id)
                u_str = str(user_id)
                if hasattr(daily_cog, 'daily_data'):
                    if g_str not in daily_cog.daily_data:
                        daily_cog.daily_data[g_str] = daily_cog.load_data(g_str)
                    if u_str in daily_cog.daily_data[g_str]:
                        pts = 5 if won else 1
                        daily_cog.daily_data[g_str][u_str]['total_points'] = daily_cog.daily_data[g_str][u_str].get('total_points', 0) + pts
                        daily_cog.save_data(g_str)
            else:
                daily_file = os.path.join('data', str(guild_id), 'daily.json')
                if os.path.exists(daily_file):
                    with open(daily_file, 'r', encoding='utf-8') as f:
                        daily_data = json.load(f)
                    user_id_str = str(user_id)
                    if user_id_str in daily_data:
                        points = 5 if won else 1
                        daily_data[user_id_str]['total_points'] = daily_data[user_id_str].get('total_points', 0) + points
                        with open(daily_file, 'w', encoding='utf-8') as f:
                            json.dump(daily_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        
        # 2. 添加經驗值（透過 Leveling Cog 記憶體更新）
        try:
            leveling_cog = self.bot.get_cog('Leveling')
            if leveling_cog:
                g_str = str(guild_id)
                u_str = str(user_id)
                u_data = leveling_cog.get_user_data(g_str, u_str)
                xp_gain = 10 if won else 3
                u_data['xp'] = u_data.get('xp', 0) + xp_gain
                new_lvl = leveling_cog.calculate_level(u_data['xp'])
                u_data['level'] = new_lvl
                leveling_cog.save_data(g_str)
            else:
                levels_file = os.path.join('data', str(guild_id), 'levels.json')
                if os.path.exists(levels_file):
                    with open(levels_file, 'r', encoding='utf-8') as f:
                        levels_data = json.load(f)
                    user_id_str = str(user_id)
                    if user_id_str in levels_data:
                        xp = 10 if won else 3
                        levels_data[user_id_str]['xp'] = levels_data[user_id_str].get('xp', 0) + xp
                        with open(levels_file, 'w', encoding='utf-8') as f:
                            json.dump(levels_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # 3. 觸發成就檢查
        try:
            ach_cog = self.bot.get_cog('Achievements')
            if ach_cog:
                asyncio.create_task(ach_cog.check_achievements(guild_id, user_id))
        except Exception:
            pass
    
    # 創建遊戲指令群組
    game = app_commands.Group(name="遊戲", description="小遊戲系統")
    
    @game.command(name="猜數字", description="猜數字遊戲（1-100）")
    async def guess_number(self, interaction: discord.Interaction):
        """猜數字遊戲"""
        # 檢查是否已有進行中的遊戲
        user_id = interaction.user.id
        if user_id in self.active_games:
            await interaction.response.send_message("❌ 你已經有一個進行中的遊戲！", ephemeral=True)
            return
        
        # 生成隨機數字
        target = random.randint(1, 100)
        attempts = 0
        max_attempts = 7
        
        embed = discord.Embed(
            title="🎲 猜數字遊戲",
            description=f"我想了一個 1-100 之間的數字\n你有 {max_attempts} 次機會猜中它！\n\n請在聊天中輸入你的猜測",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
        
        # 標記遊戲進行中
        self.active_games[user_id] = True
        
        def check(m):
            return m.author.id == user_id and m.channel.id == interaction.channel.id
        
        won = False
        try:
            while attempts < max_attempts:
                try:
                    msg = await self.bot.wait_for('message', timeout=60.0, check=check)
                    
                    # 檢查是否為數字
                    if not msg.content.isdigit():
                        await msg.reply("❌ 請輸入一個數字！")
                        continue
                    
                    guess = int(msg.content)
                    attempts += 1
                    remaining = max_attempts - attempts
                    
                    if guess < 1 or guess > 100:
                        await msg.reply("❌ 請輸入 1-100 之間的數字！")
                        continue
                    
                    if guess == target:
                        won = True
                        result_embed = discord.Embed(
                            title="🎉 恭喜你猜對了！",
                            description=f"正確答案是 **{target}**\n你用了 **{attempts}** 次嘗試\n\n🎁 獲得獎勵：**+10 經驗值**、**+5 積分**",
                            color=discord.Color.green()
                        )
                        await msg.reply(embed=result_embed)
                        break
                    elif guess < target:
                        hint_embed = discord.Embed(
                            description=f"📈 太小了！剩餘次數：**{remaining}**",
                            color=discord.Color.orange()
                        )
                        await msg.reply(embed=hint_embed)
                    else:
                        hint_embed = discord.Embed(
                            description=f"📉 太大了！剩餘次數：**{remaining}**",
                            color=discord.Color.orange()
                        )
                        await msg.reply(embed=hint_embed)
                
                except asyncio.TimeoutError:
                    timeout_embed = discord.Embed(
                        title="⏰ 遊戲超時",
                        description=f"時間到了！正確答案是 **{target}**",
                        color=discord.Color.red()
                    )
                    await interaction.channel.send(embed=timeout_embed)
                    break
            
            # 用完所有次數
            if not won and attempts >= max_attempts:
                lose_embed = discord.Embed(
                    title="😢 遊戲結束",
                    description=f"很遺憾，你沒有猜中\n正確答案是 **{target}**\n\n🎁 安慰獎：**+3 經驗值**、**+1 積分**",
                    color=discord.Color.red()
                )
                await interaction.channel.send(embed=lose_embed)
        
        finally:
            # 移除遊戲標記
            if user_id in self.active_games:
                del self.active_games[user_id]
            
            # 儲存統計和獎勵
            self.save_game_stats(interaction.guild.id, user_id, "猜數字", won)
            self.add_rewards(interaction.guild.id, user_id, won)
    
    @game.command(name="猜拳", description="和機器人猜拳（剪刀石頭布）")
    @app_commands.describe(choice="你的選擇")
    @app_commands.choices(choice=[
        app_commands.Choice(name="✊ 石頭", value="石頭"),
        app_commands.Choice(name="✋ 布", value="布"),
        app_commands.Choice(name="✌️ 剪刀", value="剪刀")
    ])
    async def rock_paper_scissors(self, interaction: discord.Interaction, choice: str):
        """猜拳遊戲"""
        choices = ["石頭", "布", "剪刀"]
        bot_choice = random.choice(choices)
        
        # 判斷勝負
        emoji_map = {"石頭": "✊", "布": "✋", "剪刀": "✌️"}
        
        won = False
        result_text = ""
        color = discord.Color.blue()
        
        if choice == bot_choice:
            result_text = "🤝 平手！"
            color = discord.Color.blue()
        elif (choice == "石頭" and bot_choice == "剪刀") or \
             (choice == "布" and bot_choice == "石頭") or \
             (choice == "剪刀" and bot_choice == "布"):
            won = True
            result_text = "🎉 你贏了！"
            color = discord.Color.green()
        else:
            result_text = "😢 你輸了！"
            color = discord.Color.red()
        
        embed = discord.Embed(
            title="✊✋✌️ 猜拳遊戲",
            color=color
        )
        embed.add_field(name="你的選擇", value=f"{emoji_map[choice]} {choice}", inline=True)
        embed.add_field(name="機器人選擇", value=f"{emoji_map[bot_choice]} {bot_choice}", inline=True)
        embed.add_field(name="結果", value=result_text, inline=False)
        
        if won:
            embed.add_field(name="獎勵", value="🎁 **+10 經驗值**、**+5 積分**", inline=False)
        elif choice != bot_choice:
            embed.add_field(name="安慰獎", value="🎁 **+3 經驗值**、**+1 積分**", inline=False)
        
        await interaction.response.send_message(embed=embed)
        
        # 儲存統計和獎勵（平手不算）
        if choice != bot_choice:
            self.save_game_stats(interaction.guild.id, interaction.user.id, "猜拳", won)
            self.add_rewards(interaction.guild.id, interaction.user.id, won)
    
    @game.command(name="21點", description="21點撲克牌遊戲")
    async def blackjack(self, interaction: discord.Interaction):
        """21點遊戲"""
        user_id = interaction.user.id
        
        # 檢查是否已有進行中的遊戲
        if user_id in self.active_games:
            await interaction.response.send_message("❌ 你已經有一個進行中的遊戲！", ephemeral=True)
            return
        
        # 初始化牌組
        def draw_card():
            card = random.randint(1, 13)
            if card > 10:
                return 10  # J, Q, K
            return card
        
        def calculate_hand(cards):
            total = sum(cards)
            # 處理 A（可以是1或11）
            aces = cards.count(1)
            while total <= 11 and aces > 0:
                total += 10
                aces -= 1
            return total
        
        # 發牌
        player_cards = [draw_card(), draw_card()]
        dealer_cards = [draw_card(), draw_card()]
        
        player_total = calculate_hand(player_cards)
        dealer_total = calculate_hand(dealer_cards)
        
        # 創建初始嵌入訊息
        embed = discord.Embed(
            title="🃏 21點遊戲",
            color=discord.Color.blue()
        )
        embed.add_field(
            name=f"你的牌 ({player_total} 點)",
            value=f"🎴 {' '.join([str(c) for c in player_cards])}",
            inline=False
        )
        embed.add_field(
            name="莊家的牌",
            value=f"🎴 {dealer_cards[0]} ❓",
            inline=False
        )
        embed.set_footer(text="點擊下方按鈕選擇要牌或停牌")
        
        # 創建按鈕
        view = discord.ui.View(timeout=60)
        
        # 標記遊戲進行中
        self.active_games[user_id] = True
        game_over = False
        won = False
        
        async def hit_callback(button_interaction):
            nonlocal player_cards, player_total, game_over, won
            
            if button_interaction.user.id != user_id:
                await button_interaction.response.send_message("❌ 這不是你的遊戲！", ephemeral=True)
                return
            
            # 要牌
            player_cards.append(draw_card())
            player_total = calculate_hand(player_cards)
            
            # 檢查是否爆牌
            if player_total > 21:
                game_over = True
                won = False
                result_embed = discord.Embed(
                    title="💥 爆牌了！",
                    description=f"你的點數：**{player_total}**\n莊家的點數：**{dealer_total}**\n\n😢 你輸了！\n🎁 安慰獎：**+3 經驗值**、**+1 積分**",
                    color=discord.Color.red()
                )
                result_embed.add_field(name="你的牌", value=f"🎴 {' '.join([str(c) for c in player_cards])}", inline=False)
                result_embed.add_field(name="莊家的牌", value=f"🎴 {' '.join([str(c) for c in dealer_cards])}", inline=False)
                
                view.stop()
                await button_interaction.response.edit_message(embed=result_embed, view=None)
            else:
                # 更新顯示
                embed.set_field_at(0, name=f"你的牌 ({player_total} 點)", value=f"🎴 {' '.join([str(c) for c in player_cards])}", inline=False)
                await button_interaction.response.edit_message(embed=embed, view=view)
        
        async def stand_callback(button_interaction):
            nonlocal dealer_cards, dealer_total, game_over, won
            
            if button_interaction.user.id != user_id:
                await button_interaction.response.send_message("❌ 這不是你的遊戲！", ephemeral=True)
                return
            
            # 莊家要牌（<17就要牌）
            while dealer_total < 17:
                dealer_cards.append(draw_card())
                dealer_total = calculate_hand(dealer_cards)
            
            game_over = True
            
            # 判斷勝負
            if dealer_total > 21:
                won = True
                result = "🎉 莊家爆牌！你贏了！"
                color = discord.Color.green()
                reward = "🎁 獲得獎勵：**+10 經驗值**、**+5 積分**"
            elif player_total > dealer_total:
                won = True
                result = "🎉 你贏了！"
                color = discord.Color.green()
                reward = "🎁 獲得獎勵：**+10 經驗值**、**+5 積分**"
            elif player_total < dealer_total:
                won = False
                result = "😢 莊家贏了！"
                color = discord.Color.red()
                reward = "🎁 安慰獎：**+3 經驗值**、**+1 積分**"
            else:
                result = "🤝 平手！"
                color = discord.Color.blue()
                reward = ""
            
            result_embed = discord.Embed(
                title="🃏 遊戲結束",
                description=f"你的點數：**{player_total}**\n莊家的點數：**{dealer_total}**\n\n{result}\n{reward}",
                color=color
            )
            result_embed.add_field(name="你的牌", value=f"🎴 {' '.join([str(c) for c in player_cards])}", inline=False)
            result_embed.add_field(name="莊家的牌", value=f"🎴 {' '.join([str(c) for c in dealer_cards])}", inline=False)
            
            view.stop()
            await button_interaction.response.edit_message(embed=result_embed, view=None)
        
        # 添加按鈕
        hit_button = discord.ui.Button(label="要牌", style=discord.ButtonStyle.primary, emoji="🎴")
        hit_button.callback = hit_callback
        
        stand_button = discord.ui.Button(label="停牌", style=discord.ButtonStyle.secondary, emoji="✋")
        stand_button.callback = stand_callback
        
        view.add_item(hit_button)
        view.add_item(stand_button)
        
        await interaction.response.send_message(embed=embed, view=view)
        
        # 等待遊戲結束
        await view.wait()
        
        # 移除遊戲標記
        if user_id in self.active_games:
            del self.active_games[user_id]
        
        # 儲存統計和獎勵
        if game_over:
            self.save_game_stats(interaction.guild.id, user_id, "21點", won)
            self.add_rewards(interaction.guild.id, user_id, won)
    
    @game.command(name="統計", description="查看你的遊戲統計")
    async def game_stats(self, interaction: discord.Interaction, user: discord.Member = None):
        """查看遊戲統計"""
        target = user or interaction.user
        
        file_path = os.path.join('data', str(interaction.guild.id), 'game_stats.json')
        
        if not os.path.exists(file_path):
            await interaction.response.send_message("❌ 還沒有遊戲統計數據", ephemeral=True)
            return
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        user_id_str = str(target.id)
        
        if user_id_str not in data:
            await interaction.response.send_message(f"❌ {target.mention} 還沒有玩過遊戲", ephemeral=True)
            return
        
        user_data = data[user_id_str]
        total_games = user_data['total_games']
        total_wins = user_data['total_wins']
        win_rate = (total_wins / total_games * 100) if total_games > 0 else 0
        
        embed = discord.Embed(
            title=f"🎮 {target.display_name} 的遊戲統計",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="總遊戲場次", value=f"**{total_games}** 場", inline=True)
        embed.add_field(name="獲勝場次", value=f"**{total_wins}** 場", inline=True)
        embed.add_field(name="勝率", value=f"**{win_rate:.1f}%**", inline=True)
        
        # 各遊戲統計
        if user_data['games']:
            game_stats_text = ""
            for game_name, stats in user_data['games'].items():
                played = stats['played']
                won = stats['won']
                rate = (won / played * 100) if played > 0 else 0
                game_stats_text += f"**{game_name}**：{played} 場 | {won} 勝 | {rate:.1f}%\n"
            
            embed.add_field(name="各遊戲詳細", value=game_stats_text, inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @game.command(name="排行榜", description="查看遊戲勝率排行榜")
    async def game_leaderboard(self, interaction: discord.Interaction):
        """遊戲排行榜"""
        await interaction.response.defer()
        file_path = os.path.join('data', str(interaction.guild.id), 'game_stats.json')
        
        if not os.path.exists(file_path):
            await interaction.followup.send("❌ 還沒有遊戲統計數據", ephemeral=True)
            return
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not data:
            await interaction.followup.send("❌ 還沒有人玩過遊戲", ephemeral=True)
            return
        
        # 計算勝率並排序（至少玩過5場）
        leaderboard = []
        for user_id, stats in data.items():
            if stats['total_games'] >= 5:
                win_rate = (stats['total_wins'] / stats['total_games'] * 100)
                leaderboard.append({
                    'user_id': user_id,
                    'total_games': stats['total_games'],
                    'total_wins': stats['total_wins'],
                    'win_rate': win_rate
                })
        
        leaderboard.sort(key=lambda x: x['win_rate'], reverse=True)
        leaderboard = leaderboard[:10]  # 只取前10名
        
        if not leaderboard:
            await interaction.followup.send("❌ 還沒有達到 5 場遊戲的玩家", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🏆 遊戲勝率排行榜 (前10名)",
            description="*至少需要 5 場遊戲才會上榜*",
            color=discord.Color.gold()
        )
        
        medals = ["🥇", "🥈", "🥉"]
        leaderboard_text = ""
        
        for i, player in enumerate(leaderboard):
            try:
                user = await self.bot.fetch_user(int(player['user_id']))
                name = user.display_name
            except:
                name = "未知用戶"
            
            medal = medals[i] if i < 3 else f"**{i+1}.**"
            leaderboard_text += f"{medal} {name}\n"
            leaderboard_text += f"   勝率：**{player['win_rate']:.1f}%** | {player['total_wins']}/{player['total_games']} 場\n\n"
        
        embed.description += f"\n\n{leaderboard_text}"
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Games(bot))
