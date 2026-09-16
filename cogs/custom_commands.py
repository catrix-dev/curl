import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from typing import Optional

class CustomCommands(commands.Cog):
    """自定義命令系統"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_folder = './data'
    
    def get_commands_file(self, guild_id: int) -> str:
        """獲取伺服器的自定義命令檔案路徑"""
        folder = os.path.join(self.data_folder, str(guild_id))
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, 'custom_commands.json')
    
    def load_commands(self, guild_id: int) -> dict:
        """載入自定義命令"""
        file_path = self.get_commands_file(guild_id)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_commands(self, guild_id: int, commands: dict):
        """儲存自定義命令"""
        file_path = self.get_commands_file(guild_id)
        tmp_file = file_path + f".tmp_{os.getpid()}"
        try:
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(commands, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, file_path)
        except Exception:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass
            raise
    
    custom_group = app_commands.Group(name="自定義", description="自定義命令管理")
    
    @custom_group.command(name="添加", description="添加自定義命令")
    @app_commands.describe(
        命令名稱="命令的觸發詞（不包含/）",
        回覆內容="命令的回覆內容"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_command(
        self,
        interaction: discord.Interaction,
        命令名稱: str,
        回覆內容: str
    ):
        """添加自定義命令"""
        guild_id = interaction.guild.id
        commands = self.load_commands(guild_id)
        
        # 檢查命令名稱是否已存在
        if 命令名稱 in commands:
            await interaction.response.send_message(
                f"❌ 命令 `{命令名稱}` 已存在！請使用 `/自定義 編輯` 修改或先刪除。",
                ephemeral=True
            )
            return
        
        # 添加命令
        commands[命令名稱] = {
            'response': 回覆內容,
            'created_by': str(interaction.user.id),
            'created_at': discord.utils.utcnow().isoformat(),
            'uses': 0
        }
        
        self.save_commands(guild_id, commands)
        
        embed = discord.Embed(
            title="✅ 自定義命令已添加",
            description=f"**命令名稱：**`{命令名稱}`\n**回覆內容：**{回覆內容}",
            color=discord.Color.from_rgb(37, 99, 235),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"創建者：{interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)
    
    @custom_group.command(name="刪除", description="刪除自定義命令")
    @app_commands.describe(命令名稱="要刪除的命令名稱")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_command(
        self,
        interaction: discord.Interaction,
        命令名稱: str
    ):
        """刪除自定義命令"""
        guild_id = interaction.guild.id
        commands = self.load_commands(guild_id)
        
        if 命令名稱 not in commands:
            await interaction.response.send_message(
                f"❌ 命令 `{命令名稱}` 不存在！",
                ephemeral=True
            )
            return
        
        del commands[命令名稱]
        self.save_commands(guild_id, commands)
        
        await interaction.response.send_message(
            f"✅ 已刪除自定義命令：`{命令名稱}`"
        )
    
    @custom_group.command(name="編輯", description="編輯自定義命令")
    @app_commands.describe(
        命令名稱="要編輯的命令名稱",
        新回覆內容="新的回覆內容"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def edit_command(
        self,
        interaction: discord.Interaction,
        命令名稱: str,
        新回覆內容: str
    ):
        """編輯自定義命令"""
        guild_id = interaction.guild.id
        commands = self.load_commands(guild_id)
        
        if 命令名稱 not in commands:
            await interaction.response.send_message(
                f"❌ 命令 `{命令名稱}` 不存在！",
                ephemeral=True
            )
            return
        
        old_response = commands[命令名稱]['response']
        commands[命令名稱]['response'] = 新回覆內容
        commands[命令名稱]['edited_by'] = str(interaction.user.id)
        commands[命令名稱]['edited_at'] = discord.utils.utcnow().isoformat()
        
        self.save_commands(guild_id, commands)
        
        embed = discord.Embed(
            title="✅ 自定義命令已更新",
            color=discord.Color.from_rgb(37, 99, 235),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="命令名稱", value=f"`{命令名稱}`", inline=False)
        embed.add_field(name="舊回覆", value=old_response, inline=False)
        embed.add_field(name="新回覆", value=新回覆內容, inline=False)
        embed.set_footer(text=f"編輯者：{interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)
    
    @custom_group.command(name="列表", description="查看所有自定義命令")
    async def list_commands(self, interaction: discord.Interaction):
        """查看所有自定義命令"""
        guild_id = interaction.guild.id
        commands = self.load_commands(guild_id)
        
        if not commands:
            await interaction.response.send_message(
                "📝 此伺服器尚未設定任何自定義命令。\n使用 `/自定義 添加` 來創建第一個命令！",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📝 自定義命令列表",
            description=f"共有 {len(commands)} 個自定義命令",
            color=discord.Color.from_rgb(37, 99, 235),
            timestamp=discord.utils.utcnow()
        )
        
        for cmd_name, cmd_data in sorted(commands.items())[:25]:
            uses = cmd_data.get('uses', 0)
            response_preview = cmd_data['response'][:50]
            if len(cmd_data['response']) > 50:
                response_preview += "..."
            
            embed.add_field(
                name=f"`{cmd_name}` (使用 {uses} 次)",
                value=response_preview,
                inline=False
            )
        
        if len(commands) > 25:
            embed.set_footer(text=f"顯示前 25/{len(commands)} 個命令 | 使用 !命令名稱 來觸發自定義命令")
        else:
            embed.set_footer(text="使用 !命令名稱 來觸發自定義命令")
        
        await interaction.response.send_message(embed=embed)
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """監聽訊息以觸發自定義命令"""
        # 忽略機器人自己的訊息
        if message.author.bot:
            return
        
        # 忽略沒有內容的訊息
        if not message.content:
            return
        
        # 檢查是否在伺服器中
        if not message.guild:
            return
        
        # 檢查是否以 ! 開頭
        if not message.content.startswith('!'):
            return
        
        # 提取命令名稱
        parts = message.content[1:].strip().split()
        if not parts:
            return
        command_name = parts[0]
        
        # 載入自定義命令
        commands = self.load_commands(message.guild.id)
        
        # 檢查命令是否存在
        if command_name in commands:
            # 增加使用次數
            commands[command_name]['uses'] = commands[command_name].get('uses', 0) + 1
            self.save_commands(message.guild.id, commands)
            
            # 發送回覆
            await message.channel.send(commands[command_name]['response'])
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'📦 {self.__class__.__name__} cog已載入')

async def setup(bot):
    await bot.add_cog(CustomCommands(bot))
