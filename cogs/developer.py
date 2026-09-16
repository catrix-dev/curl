import discord
from discord import app_commands
from discord.ext import commands
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

class Developer(commands.Cog):
    """開發者專用指令"""
    
    def __init__(self, bot):
        self.bot = bot
        # 从 .env 读取开发者 ID 列表
        load_dotenv()
        dev_ids = os.getenv('DEV_ID', '')
        self.dev_ids = [int(id.strip()) for id in dev_ids.split(',') if id.strip()]
        # 封锁数据文件路径
        self.blocked_users_file = './data/blocked_users.json'
        self._ensure_data_file()
    
    def _ensure_data_file(self):
        """确保封锁数据文件存在"""
        os.makedirs('./data', exist_ok=True)
        if not os.path.exists(self.blocked_users_file):
            with open(self.blocked_users_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=4)
    
    def load_blocked_users(self):
        """载入封锁用户列表"""
        try:
            with open(self.blocked_users_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def save_blocked_users(self, data):
        """保存封锁用户列表"""
        with open(self.blocked_users_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
    def is_user_blocked(self, user_id: int) -> bool:
        """检查用户是否被封锁"""
        blocked = self.load_blocked_users()
        return str(user_id) in blocked
    
    def is_developer(self, user_id: int) -> bool:
        """检查用户是否为开发者"""
        return user_id in self.dev_ids
    
    # 创建开发者指令组
    dev_group = app_commands.Group(name="開發", description="開發者專用指令")
    
    @dev_group.command(name="重啟", description="重新啟動機器人")
    async def restart(self, interaction: discord.Interaction):
        """重启机器人（仅开发者）"""
        # 检查权限
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 此命令僅限開發者使用！", 
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🔄 重新啟動機器人",
            description="機器人正在重新啟動...\n請稍候片刻",
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"執行者: {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)
        
        print('\n' + '═' * 62)
        print(f'🔄 開發者 {interaction.user.name} ({interaction.user.id}) 觸發重啟')
        print('═' * 62 + '\n')
        
        # 关闭机器人并重启
        await self.bot.close()
        os.execv(sys.executable, [sys.executable] + sys.argv)
    
    @dev_group.command(name="資訊", description="顯示開發者資訊")
    async def dev_info(self, interaction: discord.Interaction):
        """显示开发者信息"""
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 此命令僅限開發者使用！", 
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="👨‍💻 開發者資訊",
            color=discord.Color.blue()
        )
        
        # 显示授权的开发者
        dev_list = []
        for dev_id in self.dev_ids:
            try:
                user = await self.bot.fetch_user(dev_id)
                dev_list.append(f"• {user.name} (`{dev_id}`)")
            except:
                dev_list.append(f"• Unknown User (`{dev_id}`)")
        
        embed.add_field(
            name="授權開發者",
            value="\n".join(dev_list) if dev_list else "無",
            inline=False
        )
        
        # 系统信息
        embed.add_field(
            name="Python 版本",
            value=f"`{sys.version.split()[0]}`",
            inline=True
        )
        
        embed.add_field(
            name="Discord.py 版本",
            value=f"`{discord.__version__}`",
            inline=True
        )
        
        embed.add_field(
            name="伺服器數量",
            value=f"`{len(self.bot.guilds)}`",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @dev_group.command(name="執行", description="執行 Python 代碼")
    @app_commands.describe(代碼="要執行的 Python 代碼")
    async def eval_code(self, interaction: discord.Interaction, 代碼: str):
        """执行 Python 代码（仅开发者）"""
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 此命令僅限開發者使用！", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 执行代码
            result = eval(代碼)
            
            embed = discord.Embed(
                title="✅ 執行成功",
                color=discord.Color.green()
            )
            embed.add_field(name="代碼", value=f"```python\n{代碼}\n```", inline=False)
            embed.add_field(name="結果", value=f"```python\n{result}\n```", inline=False)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 執行錯誤",
                color=discord.Color.red()
            )
            embed.add_field(name="代碼", value=f"```python\n{代碼}\n```", inline=False)
            embed.add_field(name="錯誤", value=f"```python\n{type(e).__name__}: {str(e)}\n```", inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @dev_group.command(name="同步", description="同步斜線命令")
    async def sync_commands(self, interaction: discord.Interaction):
        """同步斜线命令到 Discord（仅开发者）"""
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 此命令僅限開發者使用！", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            synced = await self.bot.tree.sync()
            
            embed = discord.Embed(
                title="✅ 命令同步成功",
                description=f"已同步 **{len(synced)}** 個斜線命令",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"執行者: {interaction.user.name}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            print(f'✅ 開發者 {interaction.user.name} 同步了 {len(synced)} 個命令')
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 同步失敗",
                description=f"```{str(e)}```",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @dev_group.command(name="伺服器列表", description="查看所有伺服器")
    async def list_guilds(self, interaction: discord.Interaction):
        """列出所有服务器（仅开发者）"""
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 此命令僅限開發者使用！", 
                ephemeral=True
            )
            return
        
        guilds = self.bot.guilds
        
        embed = discord.Embed(
            title=f"📊 伺服器列表 ({len(guilds)})",
            color=discord.Color.blue()
        )
        
        # 按成员数排序
        sorted_guilds = sorted(guilds, key=lambda g: g.member_count, reverse=True)
        
        guild_list = []
        for i, guild in enumerate(sorted_guilds[:25], 1):  # 最多显示25个
            guild_list.append(
                f"{i}. **{guild.name}**\n"
                f"   └ ID: `{guild.id}` | 成員: `{guild.member_count}`"
            )
        
        embed.description = "\n".join(guild_list)
        
        if len(guilds) > 25:
            embed.set_footer(text=f"僅顯示前 25 個伺服器，共 {len(guilds)} 個")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @dev_group.command(name="更新", description="檢查並安裝更新")
    async def check_update(self, interaction: discord.Interaction):
        """检查更新（仅开发者）"""
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 此命令僅限開發者使用！", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # 获取 Updater cog
        updater = self.bot.get_cog('Updater')
        if not updater:
            embed = discord.Embed(
                title="❌ 錯誤",
                description="無法找到更新模組",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # 检查版本
        local_version = updater.get_local_version()
        remote_version = await updater.get_remote_version()
        
        if not local_version or not remote_version:
            embed = discord.Embed(
                title="❌ 無法檢查更新",
                description="無法讀取版本信息",
                color=discord.Color.red()
            )
            embed.add_field(name="本地版本", value=local_version or "讀取失敗", inline=True)
            embed.add_field(name="遠程版本", value=remote_version or "讀取失敗", inline=True)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # 比较版本
        if local_version == remote_version:
            embed = discord.Embed(
                title="✅ 已是最新版本",
                description=f"當前版本：`{local_version}`",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"執行者: {interaction.user.name}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # 发现新版本
        embed = discord.Embed(
            title="🎉 發現新版本",
            description=f"正在從 **{local_version}** 更新至 **{remote_version}**",
            color=discord.Color.orange()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # 执行更新
        print(f'\n🔄 開發者 {interaction.user.name} ({interaction.user.id}) 觸發手動更新')
        await updater.check_and_update()
    
    @dev_group.command(name="全局封銮", description="在機器人層面封銮用戶")
    @app_commands.describe(
        user_id="要封銮的用戶ID",
        reason="封銮原因"
    )
    async def global_ban(self, interaction: discord.Interaction, user_id: str, reason: str = "開發者全局封銮"):
        """全局封銮用戶（机器人层面）"""
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 此命令僅限開發者使用！", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            uid = int(user_id)
            user = await self.bot.fetch_user(uid)
        except ValueError:
            await interaction.followup.send(
                "❌ 無效的用戶ID，請輸入數字ID",
                ephemeral=True
            )
            return
        except discord.NotFound:
            await interaction.followup.send(
                "❌ 找不到該用戶",
                ephemeral=True
            )
            return
        
        # 检查是否已被封锁
        blocked = self.load_blocked_users()
        if str(uid) in blocked:
            await interaction.followup.send(
                f"⚠️ 用戶 {user.name} (`{uid}`) 已經被封銮",
                ephemeral=True
            )
            return
        
        # 添加到封锁列表
        blocked[str(uid)] = {
            "user_name": user.name,
            "reason": reason,
            "blocked_by": str(interaction.user),
            "blocked_by_id": interaction.user.id,
            "blocked_at": datetime.now().isoformat()
        }
        self.save_blocked_users(blocked)
        
        embed = discord.Embed(
            title="🚫 機器人層面封銮完成",
            description="此用戶已無法使用機器人的任何功能",
            color=discord.Color.red()
        )
        embed.add_field(name="目標用戶", value=f"{user.name} (`{user.id}`)", inline=False)
        embed.add_field(name="封銮原因", value=reason, inline=False)
        embed.add_field(name="執行者", value=f"{interaction.user.name} (`{interaction.user.id}`)", inline=False)
        embed.add_field(name="封銮時間", value=f"<t:{int(datetime.now().timestamp())}:F>", inline=False)
        
        embed.set_footer(text="機器人層面封銮 - 用戶將無法使用任何命令")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        print(f'\n🚫 開發者 {interaction.user.name} 對 {user.name}({user.id}) 執行機器人層面封銮')
        print(f'   原因: {reason}')
    
    @dev_group.command(name="全局解封", description="解除機器人層面封銮")
    @app_commands.describe(user_id="要解封的用戶ID")
    async def global_unban(self, interaction: discord.Interaction, user_id: str):
        """全局解封用戶（机器人层面）"""
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 此命令僅限開發者使用！", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            uid = int(user_id)
            user = await self.bot.fetch_user(uid)
        except ValueError:
            await interaction.followup.send(
                "❌ 無效的用戶ID，請輸入數字ID",
                ephemeral=True
            )
            return
        except discord.NotFound:
            await interaction.followup.send(
                "❌ 找不到該用戶",
                ephemeral=True
            )
            return
        
        # 检查是否被封锁
        blocked = self.load_blocked_users()
        if str(uid) not in blocked:
            await interaction.followup.send(
                f"⚠️ 用戶 {user.name} (`{uid}`) 未被封銮",
                ephemeral=True
            )
            return
        
        # 获取封锁信息
        block_info = blocked[str(uid)]
        
        # 从封锁列表移除
        del blocked[str(uid)]
        self.save_blocked_users(blocked)
        
        embed = discord.Embed(
            title="✅ 機器人層面解封完成",
            description="此用戶已恢復使用機器人功能的權限",
            color=discord.Color.green()
        )
        embed.add_field(name="目標用戶", value=f"{user.name} (`{user.id}`)", inline=False)
        embed.add_field(name="原封銮原因", value=block_info.get('reason', '無'), inline=False)
        embed.add_field(name="原執行者", value=block_info.get('blocked_by', '未知'), inline=True)
        embed.add_field(name="封銮時間", value=f"<t:{int(datetime.fromisoformat(block_info.get('blocked_at', datetime.now().isoformat())).timestamp())}:R>", inline=True)
        embed.add_field(name="解封執行者", value=f"{interaction.user.name} (`{interaction.user.id}`)", inline=False)
        
        embed.set_footer(text="機器人層面解封 - 用戶可以重新使用命令")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        print(f'\n✅ 開發者 {interaction.user.name} 對 {user.name}({user.id}) 執行機器人層面解封')
    
    @dev_group.command(name="封銮列表", description="查看所有被封銮的用戶")
    async def blocked_list(self, interaction: discord.Interaction):
        """查看封锁列表"""
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 此命令僅限開發者使用！", 
                ephemeral=True
            )
            return
        
        blocked = self.load_blocked_users()
        
        if not blocked:
            await interaction.response.send_message(
                "📋 目前沒有被封銮的用戶",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🚫 機器人層面封銮列表",
            description=f"共 {len(blocked)} 名用戶被封銮",
            color=discord.Color.red()
        )
        
        for uid, info in list(blocked.items())[:10]:  # 最多显示10个
            blocked_time = datetime.fromisoformat(info.get('blocked_at', datetime.now().isoformat()))
            embed.add_field(
                name=f"{info.get('user_name', 'Unknown')} (`{uid}`)",
                value=f"**原因:** {info.get('reason', '無')}\n**執行者:** {info.get('blocked_by', '未知')}\n**時間:** <t:{int(blocked_time.timestamp())}:R>",
                inline=False
            )
        
        if len(blocked) > 10:
            embed.set_footer(text=f"還有 {len(blocked) - 10} 名用戶未顯示")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.Cog.listener()
    async def on_ready(self):
        """機器人準備就緒"""
        if self.dev_ids:
            print(f'👨‍💻 開發者模組已載入 ({len(self.dev_ids)} 位開發者)')
        else:
            print('⚠️  開發者模組已載入，但未設定 DEV_ID')
        
        # 显示封锁用户数量
        blocked = self.load_blocked_users()
        if blocked:
            print(f'🚫 當前有 {len(blocked)} 名用戶被機器人層面封銮')

async def setup(bot):
    await bot.add_cog(Developer(bot))
