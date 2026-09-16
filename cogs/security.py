import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import timedelta
import re

class SecuritySystem(commands.Cog):
    """反垃圾/安全系統"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_folder = "./data"
        
    def get_security_data(self, guild_id):
        """獲取安全設定數據"""
        filepath = f"{self.data_folder}/{guild_id}/security.json"
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "enabled": True,
            "banned_words": [],
            "timeout_duration": 60,  # 秒
            "action_type": "timeout",  # timeout, delete, warn
            "whitelist_roles": [],  # 白名單角色 ID
            "whitelist_channels": [],  # 白名單頻道 ID
            "case_sensitive": False,  # 是否區分大小寫
            "match_type": "contains"  # contains, exact, regex
        }
    
    def save_security_data(self, guild_id, data):
        """保存安全設定數據"""
        folder = f"{self.data_folder}/{guild_id}"
        os.makedirs(folder, exist_ok=True)
        
        filepath = f"{folder}/security.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    
    def check_banned_word(self, content, banned_words, case_sensitive=False, match_type="contains"):
        """檢查是否包含違禁詞"""
        if not case_sensitive:
            content = content.lower()
        
        for word in banned_words:
            check_word = word if case_sensitive else word.lower()
            
            if match_type == "exact":
                # 完全匹配
                if content == check_word:
                    return True, word
            elif match_type == "contains":
                # 包含匹配
                if check_word in content:
                    return True, word
            elif match_type == "regex":
                # 正則匹配
                try:
                    pattern = re.compile(check_word, re.IGNORECASE if not case_sensitive else 0)
                    if pattern.search(content):
                        return True, word
                except re.error:
                    continue
        
        return False, None
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """監聽消息，檢查違禁詞"""
        # 忽略機器人消息
        if message.author.bot:
            return
        
        # 忽略私訊
        if not message.guild:
            return
        
        # 獲取安全設定
        data = self.get_security_data(message.guild.id)
        
        # 檢查系統是否啟用
        if not data.get("enabled", True):
            return
        
        # 檢查白名單角色
        if data.get("whitelist_roles"):
            user_role_ids = [role.id for role in message.author.roles]
            if any(role_id in user_role_ids for role_id in data["whitelist_roles"]):
                return
        
        # 檢查白名單頻道
        if data.get("whitelist_channels"):
            if message.channel.id in data["whitelist_channels"]:
                return
        
        # 檢查違禁詞
        banned_words = data.get("banned_words", [])
        if not banned_words:
            return
        
        has_banned, matched_word = self.check_banned_word(
            message.content,
            banned_words,
            data.get("case_sensitive", False),
            data.get("match_type", "contains")
        )
        
        if has_banned:
            action_type = data.get("action_type", "timeout")
            
            try:
                # 刪除消息
                if action_type in ["timeout", "delete", "warn"]:
                    await message.delete()
                
                # Timeout 用戶
                if action_type == "timeout":
                    timeout_duration = data.get("timeout_duration", 60)
                    await message.author.timeout(
                        timedelta(seconds=timeout_duration),
                        reason=f"使用違禁詞: {matched_word}"
                    )
                    
                    # 發送提示消息
                    warning_msg = await message.channel.send(
                        f"⚠️ {message.author.mention} 使用了違禁詞，已被禁言 {timeout_duration} 秒。",
                        delete_after=10
                    )
                
                elif action_type == "delete":
                    # 僅刪除消息並提示
                    await message.channel.send(
                        f"⚠️ {message.author.mention} 的消息因包含違禁詞已被刪除。",
                        delete_after=5
                    )
                
                elif action_type == "warn":
                    # 警告用戶（如果有警告系統）
                    await message.channel.send(
                        f"⚠️ {message.author.mention} 請勿使用違禁詞！",
                        delete_after=5
                    )
                
                # 記錄到日誌
                print(f"[安全系統] 用戶 {message.author} 在 {message.guild.name} 使用違禁詞: {matched_word}")
                
            except discord.Forbidden:
                print(f"[安全系統] 權限不足，無法處罰 {message.author}")
            except Exception as e:
                print(f"[安全系統] 錯誤: {e}")
    
    # 斜線指令組
    security_group = app_commands.Group(name="安全", description="安全系統管理")
    
    @security_group.command(name="添加違禁詞", description="添加違禁詞")
    @app_commands.describe(詞彙="要添加的違禁詞")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_banned_word(self, interaction: discord.Interaction, 詞彙: str):
        """添加違禁詞"""
        data = self.get_security_data(interaction.guild_id)
        
        if 詞彙 in data.get("banned_words", []):
            await interaction.response.send_message("❌ 該違禁詞已存在！", ephemeral=True)
            return
        
        if "banned_words" not in data:
            data["banned_words"] = []
        
        data["banned_words"].append(詞彙)
        self.save_security_data(interaction.guild_id, data)
        
        await interaction.response.send_message(f"✅ 已添加違禁詞：`{詞彙}`", ephemeral=True)
    
    @security_group.command(name="移除違禁詞", description="移除違禁詞")
    @app_commands.describe(詞彙="要移除的違禁詞")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_banned_word(self, interaction: discord.Interaction, 詞彙: str):
        """移除違禁詞"""
        data = self.get_security_data(interaction.guild_id)
        
        if 詞彙 not in data.get("banned_words", []):
            await interaction.response.send_message("❌ 該違禁詞不存在！", ephemeral=True)
            return
        
        data["banned_words"].remove(詞彙)
        self.save_security_data(interaction.guild_id, data)
        
        await interaction.response.send_message(f"✅ 已移除違禁詞：`{詞彙}`", ephemeral=True)
    
    @security_group.command(name="查看違禁詞", description="查看所有違禁詞")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_banned_words(self, interaction: discord.Interaction):
        """查看違禁詞列表"""
        data = self.get_security_data(interaction.guild_id)
        banned_words = data.get("banned_words", [])
        
        if not banned_words:
            await interaction.response.send_message("📋 當前沒有設定違禁詞。", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🛡️ 違禁詞列表",
            description="\n".join([f"`{i+1}.` {word}" for i, word in enumerate(banned_words)]),
            color=discord.Color.red()
        )
        embed.set_footer(text=f"共 {len(banned_words)} 個違禁詞")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @security_group.command(name="設定", description="配置安全系統")
    @app_commands.describe(
        啟用="是否啟用安全系統",
        超時時長="違規後超時時長（秒）",
        處罰類型="處罰類型（timeout/delete/warn）"
    )
    @app_commands.choices(處罰類型=[
        app_commands.Choice(name="超時（Timeout）", value="timeout"),
        app_commands.Choice(name="僅刪除消息", value="delete"),
        app_commands.Choice(name="警告", value="warn")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def configure(
        self, 
        interaction: discord.Interaction, 
        啟用: bool = None,
        超時時長: int = None,
        處罰類型: str = None
    ):
        """配置安全系統"""
        data = self.get_security_data(interaction.guild_id)
        
        changes = []
        if 啟用 is not None:
            data["enabled"] = 啟用
            changes.append(f"系統狀態：{'✅ 啟用' if 啟用 else '❌ 停用'}")
        
        if 超時時長 is not None:
            if 超時時長 < 1 or 超時時長 > 2419200:  # Discord 最大 28 天
                await interaction.response.send_message("❌ 超時時長必須在 1-2419200 秒之間！", ephemeral=True)
                return
            data["timeout_duration"] = 超時時長
            changes.append(f"超時時長：{超時時長} 秒")
        
        if 處罰類型:
            data["action_type"] = 處罰類型
            type_names = {"timeout": "超時", "delete": "刪除消息", "warn": "警告"}
            changes.append(f"處罰類型：{type_names.get(處罰類型, 處罰類型)}")
        
        if not changes:
            await interaction.response.send_message("❌ 請至少提供一個參數！", ephemeral=True)
            return
        
        self.save_security_data(interaction.guild_id, data)
        
        embed = discord.Embed(
            title="✅ 安全系統配置已更新",
            description="\n".join(changes),
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @security_group.command(name="狀態", description="查看安全系統狀態")
    @app_commands.checks.has_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction):
        """查看安全系統狀態"""
        data = self.get_security_data(interaction.guild_id)
        
        type_names = {"timeout": "超時（Timeout）", "delete": "刪除消息", "warn": "警告"}
        match_types = {"contains": "包含匹配", "exact": "完全匹配", "regex": "正則匹配"}
        
        embed = discord.Embed(
            title="🛡️ 安全系統狀態",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="系統狀態",
            value="✅ 啟用" if data.get("enabled", True) else "❌ 停用",
            inline=True
        )
        
        embed.add_field(
            name="違禁詞數量",
            value=f"{len(data.get('banned_words', []))} 個",
            inline=True
        )
        
        embed.add_field(
            name="處罰類型",
            value=type_names.get(data.get("action_type", "timeout"), "未知"),
            inline=True
        )
        
        embed.add_field(
            name="超時時長",
            value=f"{data.get('timeout_duration', 60)} 秒",
            inline=True
        )
        
        embed.add_field(
            name="匹配模式",
            value=match_types.get(data.get("match_type", "contains"), "未知"),
            inline=True
        )
        
        embed.add_field(
            name="區分大小寫",
            value="✅ 是" if data.get("case_sensitive", False) else "❌ 否",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(SecuritySystem(bot))
    print("📦 security cog已載入")
