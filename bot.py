import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import sys
import json
from datetime import datetime
from dotenv import load_dotenv
from web.server import WebServer

# 載入環境變數
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
WEB_PORT = int(os.getenv('WEB_PORT', 8080))  # 網頁端口，預設8080

# 機器人狀態設定
BOT_STATUS_TYPE = os.getenv('BOT_STATUS_TYPE', 'playing')  # playing, watching, listening, streaming, competing
BOT_STATUS_TEXT = os.getenv('BOT_STATUS_TEXT', '/help 查看指令')
BOT_STATUS_URL = os.getenv('BOT_STATUS_URL', '')  # 僅用於 streaming 類型
BOT_STATUS_REFRESH_SECONDS = int(os.getenv('BOT_STATUS_REFRESH_SECONDS', 300))

# 讀取版本號
def get_version():
    """從 version.txt 讀取版本號"""
    try:
        with open('./version.txt', 'r', encoding='utf-8') as f:
            content = f.read().strip()
            # 解析 versions = x.x.x 格式
            if '=' in content:
                return content.split('=')[1].strip()
            return content
    except:
        return "Unknown"

def print_banner():
    """顯示啟動橫幅"""
    version = get_version()
    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        ██████╗██╗   ██╗██████╗ ██╗                           ║
║       ██╔════╝██║   ██║██╔══██╗██║                           ║
║       ██║     ██║   ██║██████╔╝██║                           ║
║       ██║     ██║   ██║██╔══██╗██║                           ║
║       ╚██████╗╚██████╔╝██║  ██║███████╗                      ║
║        ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝                      ║
║                                                              ║
║                    多功能 Discord 機器人                     ║
║                      Version {version:<31} ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)
    print(f"⏰ 啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 62)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        # 特權意圖 (Privileged Gateway Intents) 配置
        # 讀取 .env 中的設定，預設啟用 message_content 與 members
        intents.message_content = os.getenv('INTENT_MESSAGE_CONTENT', 'true').lower() == 'true'
        intents.members = os.getenv('INTENT_MEMBERS', 'true').lower() == 'true'
        intents.presences = os.getenv('INTENT_PRESENCES', 'false').lower() == 'true'
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        # 初始化網頁伺服器
        self.web_server = WebServer(self, port=WEB_PORT)
        self.status_update_task = None
        
        # 設置全局交互檢查與全局錯誤處理
        self.tree.interaction_check = self.global_interaction_check
        self.tree.on_error = self.global_app_command_error

    async def global_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """全局 App Command 錯誤處理器，確保任何指令出錯或權限不足時絕不『無反應』"""
        try:
            orig_error = getattr(error, 'original', error)

            if isinstance(error, app_commands.CommandNotFound):
                return

            if isinstance(error, app_commands.MissingPermissions):
                missing = [perm.replace('_', ' ').title() for perm in error.missing_permissions]
                msg = f"❌ 您沒有使用此指令的權限！缺少權限：`{', '.join(missing)}`"
            elif isinstance(error, app_commands.BotMissingPermissions):
                missing = [perm.replace('_', ' ').title() for perm in error.missing_permissions]
                msg = f"❌ 機器人缺少執行此指令所需的權限：`{', '.join(missing)}`"
            elif isinstance(error, app_commands.CommandOnCooldown):
                msg = f"⏳ 指令冷卻中，請在 `{error.retry_after:.1f}` 秒後重試。"
            elif isinstance(error, app_commands.NoPrivateMessage):
                msg = "❌ 此指令僅可在伺服器中使用，無法在私訊中執行。"
            elif isinstance(error, app_commands.CheckFailure):
                msg = "❌ 您不符合執行此指令的條件或權限。"
            else:
                msg = f"❌ 執行指令時發生錯誤：`{str(orig_error)}`"
                cmd_name = interaction.command.name if interaction.command else "未知"
                print(f"[錯誤] 斜線指令 /{cmd_name} 執行失敗: {orig_error}")

            if not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            print(f"[嚴重錯誤] 錯誤處理器本身出錯: {e}")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """全局前綴指令錯誤處理器"""
        orig_error = getattr(error, 'original', error)
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            missing = [perm.replace('_', ' ').title() for perm in error.missing_permissions]
            await ctx.reply(f"❌ 您缺少執行此指令的權限：`{', '.join(missing)}`", mention_author=False)
        elif isinstance(error, commands.BotMissingPermissions):
            missing = [perm.replace('_', ' ').title() for perm in error.missing_permissions]
            await ctx.reply(f"❌ 機器人缺少權限：`{', '.join(missing)}`", mention_author=False)
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(f"⏳ 請稍候 `{error.retry_after:.1f}` 秒後再使用此指令。", mention_author=False)
        else:
            await ctx.reply(f"❌ 執行指令時發生錯誤：`{str(orig_error)}`", mention_author=False)
            print(f"[錯誤] 前綴指令 !{ctx.command} 出錯: {orig_error}")

    def get_total_users(self) -> int:
        """取得所有伺服器的總使用者數"""
        total = 0
        for guild in self.guilds:
            if guild.member_count is not None:
                total += guild.member_count
            else:
                total += len(guild.members)
        return total

    def render_status_text(self) -> str:
        """將狀態模板中的變數替換為即時數值"""
        return (
            BOT_STATUS_TEXT
            .replace('{users}', str(self.get_total_users()))
            .replace('{guilds}', str(len(self.guilds)))
        )
    
    async def global_interaction_check(self, interaction: discord.Interaction) -> bool:
        """全局交互檢查 - 攔截被封鎖用戶的命令"""
        # 檢查用戶是否被封鎖
        blocked_file = './data/blocked_users.json'
        if os.path.exists(blocked_file):
            try:
                with open(blocked_file, 'r', encoding='utf-8') as f:
                    blocked = json.load(f)
                
                if str(interaction.user.id) in blocked:
                    # 用戶被封鎖，禁止執行命令
                    embed = discord.Embed(
                        title="🚫 您已被封鎖",
                        description="您已被機器人管理員封鎖，無法使用任何功能。",
                        color=discord.Color.red()
                    )
                    
                    block_info = blocked[str(interaction.user.id)]
                    embed.add_field(
                        name="封鎖原因",
                        value=block_info.get('reason', '未提供'),
                        inline=False
                    )
                    embed.add_field(
                        name="封鎖時間",
                        value=f"<t:{int(datetime.fromisoformat(block_info.get('blocked_at', datetime.now().isoformat())).timestamp())}:F>",
                        inline=False
                    )
                    
                    embed.set_footer(text="如有疑問，請聯繫機器人管理員")
                    
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return False
            except Exception as e:
                print(f"檢查封鎖列表時發生錯誤: {e}")
        
        return True
    
    async def set_bot_status(self):
        """設定機器人狀態"""
        status_type = BOT_STATUS_TYPE.lower()
        status_text = self.render_status_text()
        
        try:
            if status_type == 'playing':
                activity = discord.Game(name=status_text)
            elif status_type == 'watching':
                activity = discord.Activity(type=discord.ActivityType.watching, name=status_text)
            elif status_type == 'listening':
                activity = discord.Activity(type=discord.ActivityType.listening, name=status_text)
            elif status_type == 'streaming':
                stream_url = BOT_STATUS_URL or 'https://twitch.tv/discord'
                activity = discord.Streaming(name=status_text, url=stream_url)
            elif status_type == 'competing':
                activity = discord.Activity(type=discord.ActivityType.competing, name=status_text)
            else:
                activity = discord.Game(name=status_text)
            
            await self.change_presence(activity=activity, status=discord.Status.online)
            print(f"\n✅ 已設定機器人狀態: {status_type.title()} - {status_text}")
        except Exception as e:
            print(f"\n⚠️  設定機器人狀態失敗: {e}")

    async def status_update_loop(self):
        """定時刷新機器人狀態，保持統計數據為最新"""
        while not self.is_closed():
            try:
                await self.set_bot_status()
            except Exception as e:
                print(f"⚠️  狀態刷新失敗: {e}")
            await asyncio.sleep(max(30, BOT_STATUS_REFRESH_SECONDS))
    
    async def setup_hook(self):
        print("\n📦 正在初始化系統...")
        print("─" * 62)
        
        # 啟動網頁控制台
        print("🌐 啟動網頁控制台...")
        await self.web_server.start()
        print(f"   ✓ 網頁控制台已啟動 (端口: {WEB_PORT})")
        
        # 載入所有cogs
        print("\n📁 載入功能模組...")
        cog_count = 0
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                cog_name = filename[:-3].replace('_', ' ').title()
                print(f"   ✓ {cog_name}")
                cog_count += 1
        print(f"\n   總計載入 {cog_count} 個模組")
        
        # 同步slash commands
        print("\n⚡ 同步斜線命令...", flush=True)
        try:
            await self.tree.sync()
            print("   ✓ 命令已同步至 Discord", flush=True)
        except Exception as e:
            print(f"   ⚠️ 同步斜線命令失敗或被限流: {e}", flush=True)
        print("─" * 62)
        
        # 啟動終端輸入監聽
        self.loop.create_task(self.handle_terminal_input())
    
    async def on_ready(self):
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║                    🤖 機器人已成功啟動                       ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        
        # 設定機器人狀態
        await self.set_bot_status()

        if self.status_update_task is None or self.status_update_task.done():
            self.status_update_task = self.loop.create_task(self.status_update_loop())
        
        web_proto = "https" if (os.getenv('SSL_CERT') and os.getenv('SSL_KEY') and os.path.exists(os.getenv('SSL_CERT', '')) and os.path.exists(os.getenv('SSL_KEY', ''))) else "http"
        print("\n📊 機器人資訊:")
        print(f"   • 名稱:     {self.user.name}")
        print(f"   • ID:       {self.user.id}")
        print(f"   • 伺服器:   {len(self.guilds)} 個")
        print(f"   • 用戶數:   {self.get_total_users():,} 位")
        print(f"   • 延遲:     {round(self.latency * 1000)}ms")
        print(f"   • 網頁:     {web_proto}://localhost:{WEB_PORT}")
        print(f"   • 狀態:     {BOT_STATUS_TYPE.title()} - {self.render_status_text()}")
        
        print("\n" + "═" * 62)
        print("💬 終端命令:")
        print("   restart  - 重啟機器人     │   status  - 顯示狀態")
        print("   stop     - 關閉機器人     │   ver     - 查看版本")
        print("   help     - 顯示幫助")
        print("═" * 62)
        
        print("\n✨ 準備就緒！等待指令中...")
        print("\n💡 提示:")
        print("   • 使用 /help 查看所有指令")
        print(f"   • 訪問網頁控制台：{web_proto}://localhost:{WEB_PORT}")
        print("   • 在終端輸入 help 查看管理命令\n")
    
    async def handle_terminal_input(self):
        """處理終端輸入命令"""
        if not sys.stdin or not sys.stdin.isatty():
            return  # 背景常駐或 systemd 服務無終端時直接退出，避免空轉死循環

        def get_input():
            try:
                line = sys.stdin.readline()
                if not line:
                    return None
                return line.strip()
            except Exception:
                return None
        
        while True:
            try:
                # 在另一個執行緒中讀取輸入，避免阻塞事件循環
                command = await asyncio.get_event_loop().run_in_executor(None, get_input)
                
                if command is None:
                    break
                
                if not command:
                    continue
                
                # 處理命令
                if command.lower() in ['restart', '重啟', 'restat']:
                    print('\n' + '═' * 62)
                    print('🔄 正在重啟機器人...')
                    print('═' * 62 + '\n')
                    await self.close()
                    # 重新啟動 (支援 Linux/Windows)
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                
                elif command.lower() in ['stop', '關閉', 'quit', 'exit']:
                    print('\n' + '═' * 62)
                    print('🛑 正在關閉機器人...')
                    await self.web_server.stop()
                    await self.close()
                    print('✓ 已安全關閉')
                    print('═' * 62 + '\n')
                    sys.exit(0)
                
                elif command.lower() in ['status', '狀態']:
                    print('\n' + '╔' + '═' * 60 + '╗')
                    print('║' + ' ' * 22 + '📊 機器人狀態' + ' ' * 22 + '║')
                    print('╠' + '═' * 60 + '╣')
                    print(f'║  名稱:     {self.user.name:<45}║')
                    print(f'║  ID:       {str(self.user.id):<45}║')
                    print(f'║  伺服器:   {str(len(self.guilds)) + " 個":<45}║')
                    print(f'║  延遲:     {str(round(self.latency * 1000)) + "ms":<45}║')
                    web_proto = "https" if (os.getenv('SSL_CERT') and os.getenv('SSL_KEY') and os.path.exists(os.getenv('SSL_CERT', '')) and os.path.exists(os.getenv('SSL_KEY', ''))) else "http"
                    print(f'║  網頁:     {f"{web_proto}://localhost:{WEB_PORT}":<45}║')
                    print(f'║  運行時間: {str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")):<45}║')
                    print('╚' + '═' * 60 + '╝\n')
                
                elif command.lower() in ['ver', 'version', '版本']:
                    version = get_version()
                    print('\n' + '╔' + '═' * 60 + '╗')
                    print('║' + ' ' * 22 + '📌 版本資訊' + ' ' * 24 + '║')
                    print('╠' + '═' * 60 + '╣')
                    print(f'║  當前版本: {version:<46}║')
                    print('╚' + '═' * 60 + '╝\n')
                
                elif command.lower() in ['help', '幫助', 'h']:
                    print('\n' + '╔' + '═' * 60 + '╗')
                    print('║' + ' ' * 21 + '📋 可用終端命令' + ' ' * 21 + '║')
                    print('╠' + '═' * 60 + '╣')
                    print('║  restart / 重啟     重新啟動機器人' + ' ' * 21 + '║')
                    print('║  stop / 關閉        關閉機器人' + ' ' * 25 + '║')
                    print('║  status / 狀態      顯示機器人狀態' + ' ' * 21 + '║')
                    print('║  ver / 版本         顯示當前版本' + ' ' * 23 + '║')
                    print('║  help / 幫助        顯示此幫助訊息' + ' ' * 21 + '║')
                    print('╚' + '═' * 60 + '╝\n')
                
                else:
                    print(f'❌ 未知命令: {command}')
                    print('💡 輸入 help 查看可用命令\n')
            
            except Exception as e:
                print(f'❌ 處理命令時發生錯誤: {e}')
                await asyncio.sleep(0.1)

def main():
    print_banner()
    bot = MyBot()
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print('\n\n' + '═' * 62)
        print('⚠️  收到中斷信號，正在關閉...')
        print('═' * 62 + '\n')
    except Exception as e:
        print('\n\n' + '═' * 62)
        print(f'❌ 發生錯誤: {e}')
        print('═' * 62 + '\n')

if __name__ == '__main__':
    main()

# time 0