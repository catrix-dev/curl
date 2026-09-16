import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime
import asyncio
import html

class Tickets(commands.Cog):
    """客服單系統"""
    
    def __init__(self, bot):
        self.bot = bot
        self.tickets = {}  # {guild_id: ticket_data}
        
    def get_data_path(self, guild_id):
        """獲取數據文件路徑"""
        return f'./data/{guild_id}/tickets.json'
    
    def load_data(self, guild_id):
        """載入客服單數據"""
        path = self.get_data_path(guild_id)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'enabled': False,
            'category_id': None,
            'support_role_id': None,
            'log_channel_id': None,
            'panel_channel_id': None,
            'panel_message_id': None,
            'tickets': {},
            'ticket_count': 0
        }
    
    def save_data(self, guild_id, data):
        """保存客服單數據"""
        path = self.get_data_path(guild_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_transcript_path(self, guild_id, ticket_id, channel_name):
        """獲取聊天記錄HTML文件路徑"""
        return f'./data/{guild_id}/ticket/{channel_name}-{ticket_id}.html'
    
    def init_transcript(self, guild_id, ticket_id, channel_name, user):
        """初始化聊天記錄HTML文件"""
        path = self.get_transcript_path(guild_id, ticket_id, channel_name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        html_header = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>客服單 #{ticket_id} - {channel_name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', 'Microsoft JhengHei', sans-serif;
            background: #36393f;
            color: #dcddde;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #2f3136;
            border-radius: 8px;
            padding: 20px;
        }}
        .header {{
            border-bottom: 2px solid #202225;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            color: #ffffff;
            font-size: 24px;
            margin-bottom: 5px;
        }}
        .header .info {{
            color: #b9bbbe;
            font-size: 14px;
        }}
        .message {{
            display: flex;
            padding: 10px 0;
            border-bottom: 1px solid #2d2d2d;
        }}
        .message:hover {{
            background: #32353b;
        }}
        .avatar {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            margin-right: 15px;
            flex-shrink: 0;
        }}
        .message-content {{
            flex: 1;
        }}
        .message-header {{
            display: flex;
            align-items: baseline;
            margin-bottom: 5px;
        }}
        .username {{
            font-weight: 600;
            color: #ffffff;
            margin-right: 8px;
        }}
        .timestamp {{
            font-size: 12px;
            color: #72767d;
        }}
        .text {{
            color: #dcddde;
            line-height: 1.5;
            word-wrap: break-word;
        }}
        .embed {{
            background: #2f3136;
            border-left: 4px solid #5865f2;
            padding: 10px;
            margin-top: 5px;
            border-radius: 4px;
        }}
        .attachment {{
            margin-top: 5px;
            max-width: 400px;
        }}
        .attachment img {{
            max-width: 100%;
            border-radius: 4px;
        }}
        .system-message {{
            background: #2d2d2d;
            padding: 8px 12px;
            border-left: 4px solid #faa61a;
            margin: 10px 0;
            border-radius: 4px;
            font-size: 14px;
            color: #b9bbbe;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎫 客服單 #{ticket_id}</h1>
            <div class="info">
                <strong>頻道名稱：</strong>{channel_name}<br>
                <strong>創建者：</strong>{user.name}#{user.discriminator}<br>
                <strong>創建時間：</strong>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>
        <div class="messages">
'''
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html_header)
    
    def append_to_transcript(self, guild_id, ticket_id, channel_name, message):
        """追加消息到聊天記錄"""
        path = self.get_transcript_path(guild_id, ticket_id, channel_name)
        
        if not os.path.exists(path):
            return
        
        # 獲取用戶頭像
        avatar_url = message.author.display_avatar.url if message.author.display_avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
        
        # 格式化時間
        timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
        
        # 處理消息內容與各欄位 HTML 轉義，杜絕 XSS
        clean_content = message.clean_content or message.content or ""
        safe_content = html.escape(clean_content)
        safe_author_name = html.escape(str(message.author.name or "未知用戶"))
        safe_avatar_url = html.escape(avatar_url)

        message_html = f'''
            <div class="message">
                <img src="{safe_avatar_url}" alt="Avatar" class="avatar">
                <div class="message-content">
                    <div class="message-header">
                        <span class="username">{safe_author_name}</span>
                        <span class="timestamp">{timestamp}</span>
                    </div>
'''

        if safe_content:
            message_html += f'                    <div class="text">{safe_content}</div>\n'

        # 處理附件
        for attachment in message.attachments:
            safe_att_url = html.escape(attachment.url)
            safe_att_name = html.escape(attachment.filename)
            if attachment.content_type and attachment.content_type.startswith('image/'):
                message_html += f'                    <div class="attachment"><img src="{safe_att_url}" alt="附件"></div>\n'
            else:
                message_html += f'                    <div class="attachment"><a href="{safe_att_url}">{safe_att_name}</a></div>\n'

        # 處理嵌入
        for embed in message.embeds:
            message_html += '                    <div class="embed">\n'
            if embed.title:
                message_html += f'                        <strong>{html.escape(str(embed.title))}</strong><br>\n'
            if embed.description:
                message_html += f'                        {html.escape(str(embed.description))}<br>\n'
            message_html += '                    </div>\n'

        message_html += '''
                </div>
            </div>
'''
        
        with open(path, 'a', encoding='utf-8') as f:
            f.write(message_html)
    
    def finalize_transcript(self, guild_id, ticket_id, channel_name):
        """完成聊天記錄HTML文件"""
        path = self.get_transcript_path(guild_id, ticket_id, channel_name)
        
        if not os.path.exists(path):
            return
        
        html_footer = f'''
        </div>
        <div class="system-message">
            ✅ 客服單已於 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 關閉
        </div>
    </div>
</body>
</html>
'''
        
        with open(path, 'a', encoding='utf-8') as f:
            f.write(html_footer)
    
    # 客服單群組
    ticket_group = app_commands.Group(name="客服單", description="客服單系統管理")
    
    @ticket_group.command(name="設定", description="設定客服單系統")
    @app_commands.describe(
        分類="客服單頻道的分類",
        支持角色="支持團隊角色",
        日誌頻道="記錄客服單操作的頻道"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup(
        self,
        interaction: discord.Interaction,
        分類: discord.CategoryChannel,
        支持角色: discord.Role = None,
        日誌頻道: discord.TextChannel = None
    ):
        """設定客服單系統"""
        guild_id = str(interaction.guild.id)
        data = self.tickets.get(guild_id, self.load_data(guild_id))
        
        data['category_id'] = str(分類.id)
        data['support_role_id'] = str(支持角色.id) if 支持角色 else None
        data['log_channel_id'] = str(日誌頻道.id) if 日誌頻道 else None
        data['enabled'] = True
        
        self.tickets[guild_id] = data
        self.save_data(guild_id, data)
        
        embed = discord.Embed(
            title="✅ 客服單系統已設定",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="分類", value=分類.mention, inline=False)
        if 支持角色:
            embed.add_field(name="支持角色", value=支持角色.mention, inline=True)
        if 日誌頻道:
            embed.add_field(name="日誌頻道", value=日誌頻道.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @ticket_group.command(name="開關", description="啟用或停用客服單系統")
    @app_commands.describe(狀態="true=啟用, false=停用")
    @app_commands.default_permissions(administrator=True)
    async def toggle(self, interaction: discord.Interaction, 狀態: bool):
        """啟用或停用客服單系統"""
        guild_id = str(interaction.guild.id)
        data = self.tickets.get(guild_id, self.load_data(guild_id))
        
        data['enabled'] = 狀態
        self.tickets[guild_id] = data
        self.save_data(guild_id, data)
        
        status = "✅ 已啟用" if 狀態 else "❌ 已停用"
        await interaction.response.send_message(f"{status} 客服單系統")
    
    @ticket_group.command(name="面板", description="創建客服單面板")
    @app_commands.describe(頻道="要發送面板的頻道")
    @app_commands.default_permissions(administrator=True)
    async def panel(self, interaction: discord.Interaction, 頻道: discord.TextChannel = None):
        """創建客服單面板"""
        # 檢查用戶是否有管理員權限
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 只有伺服器管理員才能創建客服單面板！",
                ephemeral=True
            )
            return
        
        guild_id = str(interaction.guild.id)
        data = self.tickets.get(guild_id, self.load_data(guild_id))
        
        if not data['enabled']:
            await interaction.response.send_message("❌ 請先使用 `/客服單 設定` 配置系統", ephemeral=True)
            return
        
        target_channel = 頻道 or interaction.channel
        
        embed = discord.Embed(
            title="🎫 客服單系統",
            description="需要幫助嗎？點擊下方按鈕創建客服單\n\n"
                       "📋 創建客服單後，我們的支持團隊會儘快回覆您\n"
                       "⏱️ 請耐心等待，我們會盡快處理您的問題",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"{interaction.guild.name} 客服支持")
        
        view = TicketPanelView(self)
        message = await target_channel.send(embed=embed, view=view)
        
        # 保存面板訊息ID
        data['panel_channel_id'] = str(target_channel.id)
        data['panel_message_id'] = str(message.id)
        self.tickets[guild_id] = data
        self.save_data(guild_id, data)
        
        await interaction.response.send_message(f"✅ 已在 {target_channel.mention} 創建客服單面板", ephemeral=True)
    

    
    @ticket_group.command(name="添加", description="添加用戶到客服單")
    @app_commands.describe(用戶="要添加的用戶")
    async def add_user(self, interaction: discord.Interaction, 用戶: discord.Member):
        """添加用戶到客服單"""
        guild_id = str(interaction.guild.id)
        data = self.tickets.get(guild_id, self.load_data(guild_id))
        
        # 檢查是否在客服單頻道中
        ticket_id = None
        for tid, ticket in data['tickets'].items():
            if str(ticket.get('channel_id')) == str(interaction.channel.id):
                ticket_id = tid
                break
        
        if not ticket_id:
            await interaction.response.send_message("❌ 這不是一個客服單頻道", ephemeral=True)
            return

        # 權限檢查：僅限客服單創建者或管理人員
        ticket_creator = data['tickets'][ticket_id].get('user_id')
        is_creator = str(interaction.user.id) == str(ticket_creator)
        is_staff = interaction.user.guild_permissions.manage_channels
        if not (is_creator or is_staff):
            await interaction.response.send_message("❌ 您沒有權限管理此客服單成員", ephemeral=True)
            return
        
        # 添加權限
        await interaction.channel.set_permissions(用戶, read_messages=True, send_messages=True)
        await interaction.response.send_message(f"✅ 已添加 {用戶.mention} 到此客服單")
    
    @ticket_group.command(name="移除", description="從客服單移除用戶")
    @app_commands.describe(用戶="要移除的用戶")
    async def remove_user(self, interaction: discord.Interaction, 用戶: discord.Member):
        """從客服單移除用戶"""
        guild_id = str(interaction.guild.id)
        data = self.tickets.get(guild_id, self.load_data(guild_id))
        
        # 檢查是否在客服單頻道中
        ticket_id = None
        for tid, ticket in data['tickets'].items():
            if str(ticket.get('channel_id')) == str(interaction.channel.id):
                ticket_id = tid
                break
        
        if not ticket_id:
            await interaction.response.send_message("❌ 這不是一個客服單頻道", ephemeral=True)
            return

        # 權限檢查：僅限客服單創建者或管理人員
        ticket_creator = data['tickets'][ticket_id].get('user_id')
        is_creator = str(interaction.user.id) == str(ticket_creator)
        is_staff = interaction.user.guild_permissions.manage_channels
        if not (is_creator or is_staff):
            await interaction.response.send_message("❌ 您沒有權限管理此客服單成員", ephemeral=True)
            return

        if str(用戶.id) == str(ticket_creator):
            await interaction.response.send_message("❌ 不能移除客服單建立者", ephemeral=True)
            return
        
        # 移除權限
        await interaction.channel.set_permissions(用戶, overwrite=None)
        await interaction.response.send_message(f"✅ 已從此客服單移除 {用戶.mention}")
    
    @ticket_group.command(name="列表", description="查看所有客服單")
    @app_commands.default_permissions(manage_channels=True)
    async def list_tickets(self, interaction: discord.Interaction):
        """查看所有客服單"""
        guild_id = str(interaction.guild.id)
        data = self.tickets.get(guild_id, self.load_data(guild_id))
        
        open_tickets = [t for t in data['tickets'].values() if t['status'] == 'open']
        
        embed = discord.Embed(
            title="🎫 客服單列表",
            description=f"目前有 {len(open_tickets)} 個開啟的客服單",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        for ticket_id, ticket in data['tickets'].items():
            if ticket['status'] == 'open':
                channel = interaction.guild.get_channel(int(ticket['channel_id']))
                if channel:
                    embed.add_field(
                        name=f"#{ticket_id}",
                        value=f"頻道: {channel.mention}\n"
                              f"創建者: <@{ticket['user_id']}>\n"
                              f"時間: {ticket['created_at'][:10]}",
                        inline=True
                    )
        
        if not open_tickets:
            embed.description = "目前沒有開啟的客服單"
        
        await interaction.response.send_message(embed=embed)
    
    async def create_ticket(self, interaction: discord.Interaction):
        """創建新客服單"""
        guild_id = str(interaction.guild.id)
        data = self.tickets.get(guild_id, self.load_data(guild_id))
        
        if not data['enabled']:
            await interaction.response.send_message("❌ 客服單系統未啟用", ephemeral=True)
            return
        
        # 檢查用戶是否已有開啟的客服單
        for ticket in data['tickets'].values():
            if ticket['user_id'] == str(interaction.user.id) and ticket['status'] == 'open':
                channel = interaction.guild.get_channel(int(ticket['channel_id']))
                if channel:
                    await interaction.response.send_message(
                        f"❌ 您已有一個開啟的客服單: {channel.mention}",
                        ephemeral=True
                    )
                    return
        
        await interaction.response.defer(ephemeral=True)
        
        # 獲取分類
        cat_id = data.get('category_id')
        category = interaction.guild.get_channel(int(cat_id)) if cat_id and str(cat_id).isdigit() else None
        if not category:
            await interaction.followup.send("❌ 找不到客服單分類，請聯繫管理員", ephemeral=True)
            return
        
        # 創建客服單ID
        data['ticket_count'] += 1
        ticket_id = str(data['ticket_count']).zfill(4)
        
        # 設定權限
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # 添加支持角色權限
        sup_id = data.get('support_role_id')
        if sup_id and str(sup_id).isdigit():
            support_role = interaction.guild.get_role(int(sup_id))
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        # 創建頻道
        channel = await interaction.guild.create_text_channel(
            name=f"客服單-{ticket_id}",
            category=category,
            overwrites=overwrites
        )
        
        # 保存客服單數據
        data['tickets'][ticket_id] = {
            'user_id': str(interaction.user.id),
            'channel_id': str(channel.id),
            'channel_name': f"客服單-{ticket_id}",
            'status': 'open',
            'created_at': datetime.now().isoformat(),
            'closed_at': None,
            'closed_by': None,
            'close_reason': None
        }
        
        self.tickets[guild_id] = data
        self.save_data(guild_id, data)
        
        # 初始化聊天記錄HTML
        self.init_transcript(guild_id, ticket_id, f"客服單-{ticket_id}", interaction.user)
        
        # 發送歡迎訊息（帶關閉按鈕）
        embed = discord.Embed(
            title=f"🎫 客服單 #{ticket_id}",
            description=f"您好 {interaction.user.mention}！\n\n"
                       "感謝您創建客服單，我們的支持團隊會盡快回覆您。\n"
                       "請詳細描述您的問題。\n\n"
                       "使用下方的 **關閉客服單** 按鈕來關閉此客服單。",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"客服單 ID: {ticket_id}")
        
        # 創建關閉按鈕視圖
        close_view = CloseTicketView(self, ticket_id, str(interaction.user.id))
        
        role_mention = ""
        if sup_id and str(sup_id).isdigit():
            s_role = interaction.guild.get_role(int(sup_id))
            if s_role:
                role_mention = f" {s_role.mention}"

        await channel.send(
            content=f"{interaction.user.mention}{role_mention}",
            embed=embed,
            view=close_view
        )
        
        await interaction.followup.send(f"✅ 已創建客服單: {channel.mention}", ephemeral=True)
        
        # 記錄到日誌
        log_cid = data.get('log_channel_id')
        if log_cid and str(log_cid).isdigit():
            log_channel = interaction.guild.get_channel(int(log_cid))
            if log_channel:
                log_embed = discord.Embed(
                    title="📋 新客服單",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                log_embed.add_field(name="客服單 ID", value=f"#{ticket_id}", inline=True)
                log_embed.add_field(name="創建者", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="頻道", value=channel.mention, inline=True)
                
                await log_channel.send(embed=log_embed)
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'📦 {self.__class__.__name__} cog已載入')
        # 載入所有伺服器的數據
        for guild in self.bot.guilds:
            guild_id = str(guild.id)
            self.tickets[guild_id] = self.load_data(guild_id)
        print(f'    - 已載入 {len(self.tickets)} 個伺服器的客服單數據')
        
        # 重新註冊持久化視圖
        self.bot.add_view(TicketPanelView(self))
        
        # 為所有開啟的客服單註冊關閉按鈕視圖
        for guild_id, data in self.tickets.items():
            if data and 'tickets' in data:
                for ticket_id, ticket in data['tickets'].items():
                    if ticket.get('status') == 'open':
                        close_view = CloseTicketView(self, ticket_id, ticket['user_id'])
                        self.bot.add_view(close_view)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """監聽消息並保存到聊天記錄"""
        # 忽略機器人消息和非公會消息
        if message.author.bot or not message.guild:
            return
        
        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)
        
        # 檢查是否在客服單頻道中
        data = self.tickets.get(guild_id)
        if not data:
            return
        
        for ticket_id, ticket in data['tickets'].items():
            if ticket['channel_id'] == channel_id and ticket['status'] == 'open':
                # 保存消息到HTML
                self.append_to_transcript(
                    guild_id,
                    ticket_id,
                    ticket.get('channel_name', f"客服單-{ticket_id}"),
                    message
                )
                break

class CloseReasonModal(discord.ui.Modal, title='關閉客服單'):
    """關閉原因輸入框"""
    
    reason = discord.ui.TextInput(
        label='關閉原因',
        placeholder='請輸入關閉此客服單的原因...',
        required=False,
        max_length=200,
        default='無'
    )
    
    def __init__(self, cog, ticket_id):
        super().__init__()
        self.cog = cog
        self.ticket_id = ticket_id
    
    async def on_submit(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        data = self.cog.tickets.get(guild_id, self.cog.load_data(guild_id))
        
        if self.ticket_id not in data['tickets']:
            await interaction.response.send_message("❌ 客服單不存在", ephemeral=True)
            return
        
        ticket = data['tickets'][self.ticket_id]
        
        # 完成聊天記錄
        self.cog.finalize_transcript(guild_id, self.ticket_id, ticket.get('channel_name', f"客服單-{self.ticket_id}"))
        
        # 更新客服單狀態
        ticket['status'] = 'closed'
        ticket['closed_at'] = datetime.now().isoformat()
        ticket['closed_by'] = str(interaction.user.id)
        ticket['close_reason'] = str(self.reason.value)
        
        self.cog.tickets[guild_id] = data
        self.cog.save_data(guild_id, data)
        
        # 發送關閉訊息
        embed = discord.Embed(
            title="🔒 客服單已關閉",
            description=f"此客服單將在 5 秒後刪除",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="關閉者", value=interaction.user.mention)
        embed.add_field(name="原因", value=str(self.reason.value))
        
        await interaction.response.send_message(embed=embed)
        
        # 記錄到日誌頻道
        if data['log_channel_id']:
            log_channel = interaction.guild.get_channel(int(data['log_channel_id']))
            if log_channel:
                log_embed = discord.Embed(
                    title="📋 客服單已關閉",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                log_embed.add_field(name="客服單 ID", value=f"#{self.ticket_id}", inline=True)
                log_embed.add_field(name="創建者", value=f"<@{ticket['user_id']}>", inline=True)
                log_embed.add_field(name="關閉者", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="原因", value=str(self.reason.value), inline=False)
                log_embed.add_field(name="創建時間", value=ticket['created_at'], inline=True)
                log_embed.add_field(name="關閉時間", value=ticket['closed_at'], inline=True)
                
                await log_channel.send(embed=log_embed)
        
        # 5秒後刪除頻道
        await asyncio.sleep(5)
        await interaction.channel.delete()

class CloseTicketView(discord.ui.View):
    """客服單關閉按鈕視圖"""
    
    def __init__(self, cog, ticket_id, creator_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.ticket_id = ticket_id
        self.creator_id = creator_id
        
        # 使用綁定 ticket_id 的唯一 custom_id，避免跨客服單覆寫衝突
        close_btn = discord.ui.Button(
            label="關閉客服單",
            style=discord.ButtonStyle.red,
            emoji="🔒",
            custom_id=f"close_ticket_{ticket_id}"
        )
        close_btn.callback = self.close_ticket_button_callback
        self.add_item(close_btn)
    
    async def close_ticket_button_callback(self, interaction: discord.Interaction):
        # 檢查權限
        is_owner = str(interaction.user.id) == str(self.creator_id)
        is_staff = interaction.user.guild_permissions.manage_channels
        
        if not (is_owner or is_staff):
            await interaction.response.send_message("❌ 您沒有權限關閉此客服單", ephemeral=True)
            return
        
        # 顯示關閉原因輸入框
        await interaction.response.send_modal(CloseReasonModal(self.cog, self.ticket_id))

class TicketPanelView(discord.ui.View):
    """客服單面板視圖"""
    
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    
    @discord.ui.button(
        label="創建客服單",
        style=discord.ButtonStyle.green,
        emoji="🎫",
        custom_id="create_ticket_button"
    )
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.create_ticket(interaction)

async def setup(bot):
    await bot.add_cog(Tickets(bot))
