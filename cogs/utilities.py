import discord
from discord import app_commands
from discord.ext import commands
import urllib.parse
from datetime import datetime, timedelta
import re
import asyncio

class Utilities(commands.Cog):
    """實用工具指令"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # 創建指令组
    util_group = app_commands.Group(name="工具", description="實用工具")
    
    @util_group.command(name="頭像", description="查看用戶頭像")
    @app_commands.describe(user="要查看頭像的用戶")
    async def avatar(self, interaction: discord.Interaction, user: discord.User = None):
        """顯示用戶頭像"""
        user = user or interaction.user
        
        embed = discord.Embed(
            title=f"🖼️ {user.name} 的頭像",
            color=discord.Color.blue()
        )
        embed.set_image(url=user.display_avatar.url)
        embed.add_field(
            name="下載連結",
            value=f"[PNG]({user.display_avatar.with_format('png').url}) | "
                  f"[JPG]({user.display_avatar.with_format('jpg').url}) | "
                  f"[WEBP]({user.display_avatar.with_format('webp').url})"
        )
        
        await interaction.response.send_message(embed=embed)
    
    @util_group.command(name="計算器", description="簡單計算器")
    @app_commands.describe(expression="数学表達式，例如: 2+2 或 10*5")
    async def calculator(self, interaction: discord.Interaction, expression: str):
        """計算数学表達式"""
        try:
            # 只允許安全的字符
            if not re.match(r'^[0-9+\-*/().\s]+$', expression):
                await interaction.response.send_message("❌ 表達式包含非法字符！只允許數字和運算符", ephemeral=True)
                return
            
            # 計算結果
            result = eval(expression)
            
            embed = discord.Embed(
                title="🧮 計算器",
                color=discord.Color.green()
            )
            embed.add_field(name="表達式", value=f"`{expression}`", inline=False)
            embed.add_field(name="結果", value=f"**{result}**", inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ 計算錯誤: {str(e)}", ephemeral=True)
    
    @util_group.command(name="倒數計時", description="創建一個倒數計時")
    @app_commands.describe(
        minutes="分鐘數",
        reason="倒數計時原因（可選）"
    )
    async def countdown(self, interaction: discord.Interaction, minutes: int, reason: str = "倒數計時"):
        """創建倒數計時"""
        if minutes < 1 or minutes > 60:
            await interaction.response.send_message("❌ 時間必須在1-60分鐘之間", ephemeral=True)
            return
        
        end_time = datetime.utcnow() + timedelta(minutes=minutes)
        
        embed = discord.Embed(
            title="⏰ 倒數計時开始",
            description=f"**{reason}**",
            color=discord.Color.orange()
        )
        embed.add_field(name="时长", value=f"{minutes} 分鐘", inline=True)
        embed.add_field(name="结束時間", value=discord.utils.format_dt(end_time, style='R'), inline=True)
        embed.timestamp = end_time
        
        await interaction.response.send_message(embed=embed)
    
    @util_group.command(name="提醒我", description="設定一個提醒")
    @app_commands.describe(
        duration="时长（分鐘）",
        message="提醒内容"
    )
    async def remind(self, interaction: discord.Interaction, duration: int, message: str):
        """設定提醒"""
        if duration < 1 or duration > 1440:  # 最多24小時
            await interaction.response.send_message("❌ 時間必須在1-1440分鐘之間（最多24小時）", ephemeral=True)
            return
        
        remind_time = datetime.utcnow() + timedelta(minutes=duration)
        
        embed = discord.Embed(
            title="⏰ 提醒已設定",
            description=f"我会在 {discord.utils.format_dt(remind_time, style='R')} 提醒你",
            color=discord.Color.green()
        )
        embed.add_field(name="提醒内容", value=message, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # 等待指定時間
        await discord.utils.sleep_until(remind_time)
        
        # 發送提醒
        remind_embed = discord.Embed(
            title="🔔 提醒",
            description=message,
            color=discord.Color.gold()
        )
        remind_embed.set_footer(text=f"你在 {duration} 分鐘前設定了这個提醒")
        
        try:
            await interaction.user.send(embed=remind_embed)
        except:
            # 如果无法私信，就在頻道提醒
            await interaction.channel.send(f"{interaction.user.mention}", embed=remind_embed)
    
    @util_group.command(name="縮短文字", description="縮短长文字")
    @app_commands.describe(
        text="要縮短的文字",
        length="最大長度（預設100）"
    )
    async def shorten(self, interaction: discord.Interaction, text: str, length: int = 100):
        """縮短文字"""
        if len(text) <= length:
            await interaction.response.send_message(f"✅ 文字已经够短了！({len(text)} 字符)", ephemeral=True)
            return
        
        shortened = text[:length-3] + "..."
        
        embed = discord.Embed(
            title="✂️ 文字縮短",
            color=discord.Color.blue()
        )
        embed.add_field(name="原文字", value=f"{text[:100]}..." if len(text) > 100 else text, inline=False)
        embed.add_field(name="縮短后", value=shortened, inline=False)
        embed.add_field(name="統計", value=f"原長度: {len(text)} → 新長度: {len(shortened)}", inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @util_group.command(name="隨機數", description="生成隨機數")
    @app_commands.describe(
        minimum="最小值",
        maximum="最大值"
    )
    async def random_number(self, interaction: discord.Interaction, minimum: int, maximum: int):
        """生成隨機數"""
        if minimum >= maximum:
            await interaction.response.send_message("❌ 最小值必須小于最大值", ephemeral=True)
            return
        
        import random
        result = random.randint(minimum, maximum)
        
        embed = discord.Embed(
            title="🎲 隨機數生成器",
            color=discord.Color.purple()
        )
        embed.add_field(name="範圍", value=f"{minimum} - {maximum}", inline=True)
        embed.add_field(name="結果", value=f"**{result}**", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @util_group.command(name="定時消息", description="在指定時間發送一則訊息")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(
        time="時間格式: YYYY/MM/DD HH:MM (UTC+8)，例如: 2026/02/18 15:30",
        message="要發送的訊息內容",
        channel="要發送到的頻道（可選，預設為當前頻道）"
    )
    async def schedule_message(
        self, 
        interaction: discord.Interaction, 
        time: str, 
        message: str,
        channel: discord.TextChannel = None
    ):
        """在指定時間發送一則訊息（UTC+8時區）"""
        # 立即回應，避免超時
        await interaction.response.defer(ephemeral=True)
        
        # 確定目標頻道
        target_channel = channel if channel else interaction.channel
        
        # 解析時間（UTC+8）
        time_format = "%Y/%m/%d %H:%M"
        utc8_offset = timedelta(hours=8)
        
        try:
            # 解析輸入的時間（視為 UTC+8）
            input_time = datetime.strptime(time, time_format)
            
            # 獲取當前 UTC+8 時間
            now_utc = datetime.utcnow()
            now_utc8 = now_utc + utc8_offset
            
            # 檢查時間是否在未來
            if input_time <= now_utc8:
                await interaction.followup.send(
                    f"⚠️ 指定的時間已經過去！\n"
                    f"📅 當前時間 (UTC+8): {now_utc8.strftime('%Y/%m/%d %H:%M:%S')}\n"
                    f"📅 指定時間 (UTC+8): {input_time.strftime('%Y/%m/%d %H:%M:%S')}",
                    ephemeral=True
                )
                return
            
            # 計算時間差
            time_diff = input_time - now_utc8
            
            # 檢查是否超過30天
            if time_diff.total_seconds() > (30 * 24 * 3600):
                await interaction.followup.send(
                    "⚠️ 排程時間過長（超過 30 天）。請設定較近的時間。",
                    ephemeral=True
                )
                return
            
            # 通知用戶排程成功
            success_embed = discord.Embed(
                title="✅ 定時消息已設定",
                color=discord.Color.green()
            )
            success_embed.add_field(
                name="📅 發送時間 (UTC+8)",
                value=f"**{input_time.strftime('%Y年%m月%d日 %H:%M')}**",
                inline=False
            )
            success_embed.add_field(
                name="📢 發送頻道",
                value=target_channel.mention,
                inline=True
            )
            success_embed.add_field(
                name="⏱️ 倒數時間",
                value=f"{int(time_diff.total_seconds() // 3600)} 小時 {int((time_diff.total_seconds() % 3600) // 60)} 分鐘",
                inline=True
            )
            success_embed.add_field(
                name="💬 訊息預覽",
                value=f"`{message[:100]}{'...' if len(message) > 100 else ''}`",
                inline=False
            )
            success_embed.set_footer(text=f"設定者: {interaction.user.name}")
            
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
            # 等待到指定時間
            await asyncio.sleep(time_diff.total_seconds())
            
            # 發送訊息
            send_embed = discord.Embed(
                description=message,
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            send_embed.set_footer(text=f"由 {interaction.user.name} 排程發送")
            
            await target_channel.send(embed=send_embed)
            
        except ValueError:
            await interaction.followup.send(
                f"❌ 時間格式錯誤！\n"
                f"⚠️ 請使用格式: `YYYY/MM/DD HH:MM`\n"
                f"📝 範例: `2026/02/18 15:30`\n"
                f"🕐 時區: UTC+8",
                ephemeral=True
            )
        except discord.Forbidden:
            try:
                await interaction.user.send(
                    f"❌ 定時消息發送失敗：我沒有在 {target_channel.mention} 頻道發送訊息的權限。"
                )
            except:
                pass
        except Exception as e:
            print(f"定時消息錯誤: {e}")
            try:
                await interaction.user.send(
                    f"❌ 定時消息執行失敗：{str(e)}\n"
                    f"可能原因：機器人重啟、頻道被刪除或權限變更。"
                )
            except:
                pass
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'📦 {self.__class__.__name__} cog已載入')

async def setup(bot):
    await bot.add_cog(Utilities(bot))
