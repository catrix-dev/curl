from aiohttp import web, ClientSession
from aiohttp_session import setup, get_session, session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet
import discord
import os
import ssl
import asyncio
import base64
import json
import sqlite3
import re
import urllib.parse
import time
import secrets
from datetime import datetime


def format_prompts_for_web(prompts: list) -> str:
    """將多條提示詞格式化為 Web 面板字串：每條提示詞以逗號 (,) 結尾，換行若無逗號視為同一條"""
    if not prompts:
        return ""
    items = []
    for i, p in enumerate(prompts):
        p_clean = p.strip()
        if not p_clean:
            continue
        if i < len(prompts) - 1:
            if not p_clean.endswith(",") and not p_clean.endswith("，"):
                p_clean += ","
        items.append(p_clean)
    return "\n".join(items)


def parse_prompts_from_web(text: str) -> list:
    """解析 Web 面板字串：以行尾逗號 (,) 或 (，) 區隔各條提示詞，換行未帶逗號代表屬於同一條提示詞"""
    if not text or not text.strip():
        return []
    prompts = []
    current_lines = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            if current_lines:
                current_lines.append("")
            continue
        if line.endswith(",") or line.endswith("，"):
            content = line[:-1].rstrip()
            if content or current_lines:
                current_lines.append(content)
                p = "\n".join(current_lines).strip()
                if p:
                    prompts.append(p)
                current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        p = "\n".join(current_lines).strip()
        if p:
            prompts.append(p)
    return prompts


class WebServer:
    """網頁後台控制器"""
    
    def __init__(self, bot, host='0.0.0.0', port=8080):
        self.bot = bot
        self.host = host
        self.port = port
        
        # Discord OAuth2 設定
        self.client_id = os.getenv('DISCORD_CLIENT_ID')
        self.client_secret = os.getenv('DISCORD_CLIENT_SECRET')
        self.redirect_uri = os.getenv('DISCORD_REDIRECT_URI', f'http://localhost:{port}/callback')
        
        # 開發者 ID
        dev_ids = os.getenv('DEV_ID', '')
        self.dev_ids = [int(id.strip()) for id in dev_ids.split(',') if id.strip()]
        
        # SSL 設定
        self.ssl_cert = os.getenv('SSL_CERT')
        self.ssl_key = os.getenv('SSL_KEY')
        
        # Session 密鑰
        session_secret = os.getenv('SESSION_SECRET', fernet.Fernet.generate_key().decode())
        secret_key = base64.urlsafe_b64decode(session_secret.encode() if len(session_secret) == 44 else base64.urlsafe_b64encode(session_secret.encode()[:32]))
        
        # 快取與鎖
        self._user_guilds_cache = {}

        # 創建應用
        self.app = web.Application(middlewares=[session_middleware(EncryptedCookieStorage(secret_key)), self.error_middleware])
        self.setup_routes()

    @staticmethod
    def _atomic_json_write(file_path: str, data, indent: int = 2):
        """原子寫入 JSON 檔案，防止斷電或併發衝突導致檔案損壞或丟失"""
        dir_name = os.path.dirname(os.path.abspath(file_path))
        os.makedirs(dir_name, exist_ok=True)
        tmp_file = f"{file_path}.tmp_{os.getpid()}_{time.time()}"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, file_path)
        except Exception:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass
            raise

    async def get_user_guilds(self, access_token: str):
        """獲取用戶 Discord 伺服器清單（60 秒記憶體快取，防範 429 Rate Limit）"""
        if not access_token:
            return None
        now = time.time()
        cached = self._user_guilds_cache.get(access_token)
        if cached and now - cached[0] < 60:
            return cached[1]
        try:
            async with ClientSession() as client_session:
                headers = {'Authorization': f"Bearer {access_token}"}
                async with client_session.get('https://discord.com/api/users/@me/guilds', headers=headers) as resp:
                    if resp.status == 200:
                        user_guilds = await resp.json()
                        self._user_guilds_cache[access_token] = (now, user_guilds)
                        return user_guilds
                    elif resp.status == 429:
                        if cached:
                            return cached[1]
                        return None
                    return None
        except Exception as e:
            if cached:
                return cached[1]
            return None
    
    @web.middleware
    async def error_middleware(self, request, handler):
        """錯誤處理中間件"""
        try:
            response = await handler(request)
            # 處理404錯誤
            if response.status == 404:
                # 如果是API請求，返回JSON
                if request.path.startswith('/api/'):
                    return response
                # 如果是頁面請求，返回404.html
                with open('web/404.html', 'r', encoding='utf-8') as f:
                    html = f.read()
                return web.Response(text=html, content_type='text/html', status=404)
            return response
        except web.HTTPException as ex:
            # 處理HTTP異常
            if ex.status == 404:
                # 如果是API請求，返回JSON
                if request.path.startswith('/api/'):
                    return web.json_response({'error': 'Not found'}, status=404)
                # 如果是頁面請求，返回404.html
                with open('web/404.html', 'r', encoding='utf-8') as f:
                    html = f.read()
                return web.Response(text=html, content_type='text/html', status=404)
            raise
    
    def setup_routes(self):
        """設定路由"""
        self.app.router.add_get('/', self.index)
        self.app.router.add_get('/login', self.login)
        self.app.router.add_get('/callback', self.callback)
        self.app.router.add_get('/select-server', self.select_server)
        self.app.router.add_get('/dashboard/{guild_id}', self.dashboard)
        self.app.router.add_get('/dashboard/{guild_id}/', self.dashboard)
        self.app.router.add_get('/dashboard/{guild_id}/{feature}', self.dashboard)
        self.app.router.add_get('/dashboard/{guild_id}/{feature}/', self.dashboard)
        self.app.router.add_get('/my-tickets', self.my_tickets)
        self.app.router.add_get('/logout', self.logout)
        self.app.router.add_get('/privacy', self.privacy)
        self.app.router.add_get('/privacy.html', self.privacy)
        self.app.router.add_get('/icon.png', self.serve_icon)
        self.app.router.add_get('/logo.png', self.serve_logo)
        self.app.router.add_get('/favicon.ico', self.serve_favicon_ico)
        self.app.router.add_get('/favicon.png', self.serve_favicon_png)
        self.app.router.add_get('/apple-touch-icon.png', self.serve_apple_touch_icon)
        self.app.router.add_get('/api/guilds', self.api_guilds)
        self.app.router.add_get('/api/my-tickets', self.api_my_tickets)
        self.app.router.add_get('/api/stats/{guild_id}', self.api_stats)
        self.app.router.add_get('/api/data/{guild_id}/{data_type}', self.api_data)
        self.app.router.add_post('/api/welcome/{guild_id}/toggle', self.api_toggle_welcome)
        self.app.router.add_post('/api/welcome/{guild_id}/update', self.api_update_welcome)
        
        # 自定義命令 API
        self.app.router.add_get('/api/custom-commands/{guild_id}', self.api_get_custom_commands)
        self.app.router.add_post('/api/custom-commands/{guild_id}', self.api_add_custom_command)
        self.app.router.add_put('/api/custom-commands/{guild_id}/{command_name}', self.api_edit_custom_command)
        self.app.router.add_delete('/api/custom-commands/{guild_id}/{command_name}', self.api_delete_custom_command)
        
        # 臨時語音頻道 API
        self.app.router.add_get('/api/temp-voice/{guild_id}', self.api_get_temp_voice_config)
        self.app.router.add_post('/api/temp-voice/{guild_id}', self.api_update_temp_voice_config)
        self.app.router.add_get('/api/channels/{guild_id}', self.api_get_channels)
        
        # 警告系統 API
        self.app.router.add_get('/api/warnings/{guild_id}', self.api_get_warnings)
        self.app.router.add_delete('/api/warnings/{guild_id}/{user_id}', self.api_clear_warnings)
        self.app.router.add_delete('/api/warnings/{guild_id}/{user_id}/latest', self.api_remove_latest_warning)
        self.app.router.add_delete('/api/warnings/{guild_id}/{user_id}/{index}', self.api_remove_warning_by_index)
        
        # 成就系統 API
        self.app.router.add_get('/api/achievements/{guild_id}', self.api_get_achievements)
        self.app.router.add_post('/api/achievements/{guild_id}/{user_id}/{achievement_id}', self.api_grant_achievement)
        self.app.router.add_delete('/api/achievements/{guild_id}/{user_id}/{achievement_id}', self.api_revoke_achievement)
        
        # 客服單系統 API
        self.app.router.add_get('/api/tickets/{guild_id}', self.api_get_tickets)
        self.app.router.add_post('/api/tickets/{guild_id}/settings', self.api_update_ticket_settings)
        self.app.router.add_post('/api/tickets/{guild_id}/{ticket_id}/close', self.api_close_ticket)
        self.app.router.add_get('/api/tickets/{guild_id}/{ticket_id}/transcript', self.api_get_ticket_transcript)
        self.app.router.add_post('/api/tickets/{guild_id}/create-panel', self.api_create_ticket_panel)
        
        # 自動回覆系統 API
        self.app.router.add_get('/api/auto-reply/{guild_id}', self.api_get_auto_replies)
        self.app.router.add_post('/api/auto-reply/{guild_id}', self.api_add_auto_reply)
        self.app.router.add_put('/api/auto-reply/{guild_id}/{rule_id}', self.api_update_auto_reply)
        self.app.router.add_delete('/api/auto-reply/{guild_id}/{rule_id}', self.api_delete_auto_reply)
        self.app.router.add_post('/api/auto-reply/{guild_id}/toggle', self.api_toggle_auto_reply_system)
        self.app.router.add_post('/api/auto-reply/{guild_id}/{rule_id}/toggle', self.api_toggle_auto_reply_rule)
        
        # 安全系統 API
        self.app.router.add_get('/api/security/{guild_id}', self.api_get_security)
        self.app.router.add_post('/api/security/{guild_id}', self.api_update_security)
        self.app.router.add_post('/api/security/{guild_id}/banned-words', self.api_add_banned_word)
        self.app.router.add_delete('/api/security/{guild_id}/banned-words', self.api_delete_banned_word)
        
        # AI 聊天系統 API
        self.app.router.add_get('/api/ai/{guild_id}', self.api_get_ai_config)
        self.app.router.add_post('/api/ai/{guild_id}/toggle', self.api_toggle_ai)
        self.app.router.add_post('/api/ai/{guild_id}/settings', self.api_update_ai_settings)
        self.app.router.add_post('/api/ai/{guild_id}/roles', self.api_update_ai_roles)
        self.app.router.add_post('/api/ai/{guild_id}/ban', self.api_ai_ban_user)
        self.app.router.add_delete('/api/ai/{guild_id}/ban/{user_id}', self.api_ai_unban_user)
        self.app.router.add_post('/api/ai/{guild_id}/unban/{user_id}', self.api_ai_unban_user)
        self.app.router.add_post('/api/ai/{guild_id}/unban', self.api_ai_unban_user)
        self.app.router.add_delete('/api/ai/{guild_id}/memory/{user_id}', self.api_clear_ai_memory)
        self.app.router.add_get('/api/roles/{guild_id}', self.api_get_roles)
        
        # 開發者面板 API
        self.app.router.add_get('/dev-panel', self.dev_panel)
        self.app.router.add_get('/api/dev/all-guilds', self.api_dev_all_guilds)
        self.app.router.add_get('/api/dev/guild-config/{guild_id}', self.api_dev_guild_config)
        self.app.router.add_get('/api/dev/guild-members/{guild_id}', self.api_dev_guild_members)
    
    async def index(self, request):
        """主頁"""
        session = await get_session(request)
        user = session.get('user')
        
        if user:
            # 已登錄，重定向到伺服器選擇頁面
            raise web.HTTPFound('/select-server')
        
        with open('web/index.html', 'r', encoding='utf-8') as f:
            html = f.read()
        return web.Response(text=html, content_type='text/html')

    async def privacy(self, request):
        """隱私權政策頁面"""
        with open('web/privacy.html', 'r', encoding='utf-8') as f:
            html = f.read()
        return web.Response(text=html, content_type='text/html')

    async def serve_icon(self, request):
        return web.FileResponse('web/icon.png')

    async def serve_logo(self, request):
        return web.FileResponse('web/logo.png')

    async def serve_favicon_ico(self, request):
        return web.FileResponse('web/favicon.ico')

    async def serve_favicon_png(self, request):
        return web.FileResponse('web/favicon.png')

    async def serve_apple_touch_icon(self, request):
        return web.FileResponse('web/apple-touch-icon.png')
    
    async def login(self, request):
        """Discord 登錄（含 CSRF State 驗證）"""
        session = await get_session(request)
        state = secrets.token_urlsafe(16)
        session['oauth_state'] = state
        oauth_url = (
            f"https://discord.com/api/oauth2/authorize"
            f"?client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&response_type=code"
            f"&scope=identify%20guilds"
            f"&state={state}"
        )
        raise web.HTTPFound(oauth_url)
    
    async def callback(self, request):
        """OAuth2 回調"""
        code = request.query.get('code')
        state = request.query.get('state')
        session = await get_session(request)
        saved_state = session.pop('oauth_state', None)
        if saved_state and state != saved_state:
            return web.Response(text="錯誤：OAuth State 驗證失敗 (CSRF 攔截)", status=400)
        
        if not code:
            return web.Response(text="錯誤：未提供授權碼", status=400)
        
        # 交換 access token
        async with ClientSession() as session:
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': self.redirect_uri
            }
            
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            
            async with session.post('https://discord.com/api/oauth2/token', data=data, headers=headers) as resp:
                if resp.status != 200:
                    return web.Response(text="登錄失敗", status=400)
                
                token_data = await resp.json()
                access_token = token_data['access_token']
            
            # 獲取用戶資訊
            headers = {'Authorization': f"Bearer {access_token}"}
            async with session.get('https://discord.com/api/users/@me', headers=headers) as resp:
                user_data = await resp.json()
            
            # 儲存 session
            session = await get_session(request)
            session['user'] = {
                'id': user_data['id'],
                'username': user_data['username'],
                'avatar': user_data.get('avatar'),
                'discriminator': user_data.get('discriminator', '0')
            }
            session['access_token'] = access_token
        
        next_url = session.pop('next_url', None)
        if next_url and str(next_url).startswith('/dashboard/'):
            raise web.HTTPFound(next_url)
        raise web.HTTPFound('/select-server')
    
    async def select_server(self, request):
        """伺服器選擇頁面"""
        session = await get_session(request)
        user = session.get('user')
        
        if not user:
            raise web.HTTPFound('/login')
        
        with open('web/select_server.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        # 替換用戶資訊
        avatar_url = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png" if user.get('avatar') else "https://cdn.discordapp.com/embed/avatars/0.png"
        
        html = html.replace('{USERNAME}', user['username'])
        html = html.replace('{AVATAR_URL}', avatar_url)
        
        return web.Response(text=html, content_type='text/html')
    
    async def my_tickets(self, request):
        """我的客服單頁面"""
        session = await get_session(request)
        user = session.get('user')
        
        if not user:
            raise web.HTTPFound('/login')
        
        with open('web/my-tickets.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        # 替換用戶資訊
        avatar_url = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png" if user.get('avatar') else "https://cdn.discordapp.com/embed/avatars/0.png"
        
        html = html.replace('{USERNAME}', user['username'])
        html = html.replace('{AVATAR_URL}', avatar_url)
        
        return web.Response(text=html, content_type='text/html')
    
    async def api_guilds(self, request):
        """API：獲取用戶的伺服器列表"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        access_token = session.get('access_token')
        
        # 獲取機器人所在的伺服器
        bot_guild_ids = {str(guild.id) for guild in self.bot.guilds}
        
        # 獲取用戶的 Discord 伺服器（使用 60s 記憶體快取）
        user_guilds = await self.get_user_guilds(access_token)
        if user_guilds is None:
            return web.json_response({'error': 'Failed to fetch guilds'}, status=500)
        
        # 過濾有管理權限且機器人也在的伺服器
        accessible_guilds = []
        for guild in user_guilds:
            permissions = int(guild.get('permissions', 0))
            guild_id = guild['id']
            
            # 檢查管理員權限或管理伺服器權限
            if (permissions & 0x8 or permissions & 0x20) and guild_id in bot_guild_ids:
                # 獲取伺服器圖標
                icon_url = None
                if guild.get('icon'):
                    icon_url = f"https://cdn.discordapp.com/icons/{guild_id}/{guild['icon']}.png"
                
                # 獲取成員數量
                bot_guild = self.bot.get_guild(int(guild_id))
                member_count = bot_guild.member_count if bot_guild else 0
                
                accessible_guilds.append({
                    'id': guild_id,
                    'name': guild['name'],
                    'icon': icon_url,
                    'member_count': member_count
                })
        
        return web.json_response({'guilds': accessible_guilds})
    
    async def api_stats(self, request):
        """API：特定伺服器統計數據"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        # 獲取伺服器
        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({'error': 'Guild not found'}, status=404)
        
        # 收集統計數據
        stats = {
            'guild_name': guild.name,
            'member_count': guild.member_count,
            'channel_count': len(guild.channels),
            'role_count': len(guild.roles),
            'text_channels': len(guild.text_channels),
            'voice_channels': len(guild.voice_channels),
            'categories': len(guild.categories),
        }
        
        return web.json_response(stats)
    
    async def api_data(self, request):
        """API：讀取伺服器數據文件"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        data_type = request.match_info.get('data_type')
        
        # 驗證數據類型
        allowed_types = ['levels', 'welcome', 'reaction_roles', 'daily', 'birthdays', 'birthday_settings', 'game_stats', 'statistics']
        if data_type not in allowed_types:
            return web.json_response({'error': 'Invalid data type'}, status=400)
        
        # 讀取數據文件
        data_file = os.path.join('data', guild_id, f'{data_type}.json')
        
        if not os.path.exists(data_file):
            return web.json_response({'data': {}, 'exists': False})
        
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return web.json_response({'data': data, 'exists': True})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_toggle_welcome(self, request):
        """API：切換歡迎系統開關"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            # 獲取請求數據
            data = await request.json()
            toggle_type = data.get('type')  # 'welcome' 或 'leave'
            enabled = data.get('enabled')  # True 或 False
            
            if toggle_type not in ['welcome', 'leave']:
                return web.json_response({'error': 'Invalid type'}, status=400)
            
            # 讀取現有設定
            data_file = os.path.join('data', guild_id, 'welcome.json')
            
            if not os.path.exists(data_file):
                # 創建預設設定
                os.makedirs(os.path.dirname(data_file), exist_ok=True)
                settings = {
                    'welcome_enabled': False,
                    'leave_enabled': False,
                    'welcome_channel': None,
                    'leave_channel': None,
                    'welcome_message': '歡迎 {user} 加入 {server}！',
                    'leave_message': '{username} 離開了伺服器'
                }
            else:
                with open(data_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            
            # 更新設定
            if toggle_type == 'welcome':
                settings['welcome_enabled'] = enabled
            else:
                settings['leave_enabled'] = enabled
            
            # 儲存設定
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            
            return web.json_response({
                'success': True,
                'settings': settings
            })
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_update_welcome(self, request):
        """API：更新歡迎系統設定"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            # 獲取請求數據
            data = await request.json()
            
            # 讀取現有設定
            data_file = os.path.join('data', guild_id, 'welcome.json')
            
            if not os.path.exists(data_file):
                # 創建預設設定
                os.makedirs(os.path.dirname(data_file), exist_ok=True)
                settings = {
                    'welcome_enabled': False,
                    'leave_enabled': False,
                    'welcome_channel': None,
                    'leave_channel': None,
                    'welcome_message': '歡迎 {user} 加入 {server}！',
                    'leave_message': '{username} 離開了伺服器'
                }
            else:
                with open(data_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            
            # 更新設定（只更新提供的字段）
            if 'welcome_channel' in data:
                settings['welcome_channel'] = data['welcome_channel']
            if 'leave_channel' in data:
                settings['leave_channel'] = data['leave_channel']
            if 'welcome_message' in data:
                settings['welcome_message'] = data['welcome_message']
            if 'leave_message' in data:
                settings['leave_message'] = data['leave_message']
            
            # 儲存設定
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            
            return web.json_response({
                'success': True,
                'settings': settings
            })
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_get_custom_commands(self, request):
        """API：獲取自定義命令列表"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        data_file = os.path.join('data', guild_id, 'custom_commands.json')
        
        if not os.path.exists(data_file):
            return web.json_response({'commands': {}})
        
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                commands = json.load(f)
            return web.json_response({'commands': commands})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_add_custom_command(self, request):
        """API：添加自定義命令"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            data = await request.json()
            command_name = data.get('name')
            response = data.get('response')
            
            if not command_name or not response:
                return web.json_response({'error': 'Missing name or response'}, status=400)
            
            data_file = os.path.join('data', guild_id, 'custom_commands.json')
            os.makedirs(os.path.dirname(data_file), exist_ok=True)
            
            # 讀取現有命令
            commands = {}
            if os.path.exists(data_file):
                with open(data_file, 'r', encoding='utf-8') as f:
                    commands = json.load(f)
            
            # 檢查命令是否已存在
            if command_name in commands:
                return web.json_response({'error': 'Command already exists'}, status=400)
            
            # 添加命令
            from datetime import datetime
            commands[command_name] = {
                'response': response,
                'created_by': session.get('user')['id'],
                'created_at': datetime.utcnow().isoformat(),
                'uses': 0
            }
            
            # 儲存
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(commands, f, ensure_ascii=False, indent=2)
            
            return web.json_response({'success': True, 'commands': commands})
        
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_edit_custom_command(self, request):
        """API：編輯自定義命令"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        command_name = request.match_info.get('command_name')
        
        try:
            data = await request.json()
            new_response = data.get('response')
            
            if not new_response:
                return web.json_response({'error': 'Missing response'}, status=400)
            
            data_file = os.path.join('data', guild_id, 'custom_commands.json')
            
            if not os.path.exists(data_file):
                return web.json_response({'error': 'Commands file not found'}, status=404)
            
            with open(data_file, 'r', encoding='utf-8') as f:
                commands = json.load(f)
            
            if command_name not in commands:
                return web.json_response({'error': 'Command not found'}, status=404)
            
            # 更新命令
            from datetime import datetime
            commands[command_name]['response'] = new_response
            commands[command_name]['edited_by'] = session.get('user')['id']
            commands[command_name]['edited_at'] = datetime.utcnow().isoformat()
            
            # 儲存
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(commands, f, ensure_ascii=False, indent=2)
            
            return web.json_response({'success': True, 'commands': commands})
        
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_delete_custom_command(self, request):
        """API：刪除自定義命令"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        command_name = request.match_info.get('command_name')
        
        try:
            data_file = os.path.join('data', guild_id, 'custom_commands.json')
            
            if not os.path.exists(data_file):
                return web.json_response({'error': 'Commands file not found'}, status=404)
            
            with open(data_file, 'r', encoding='utf-8') as f:
                commands = json.load(f)
            
            if command_name not in commands:
                return web.json_response({'error': 'Command not found'}, status=404)
            
            # 刪除命令
            del commands[command_name]
            
            # 儲存
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(commands, f, ensure_ascii=False, indent=2)
            
            return web.json_response({'success': True, 'commands': commands})
        
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_get_temp_voice_config(self, request):
        """API：獲取臨時語音配置"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        data_file = os.path.join('data', guild_id, 'temp_voice.json')
        
        if not os.path.exists(data_file):
            return web.json_response({
                'config': {
                    'enabled': False,
                    'trigger_channel_id': None,
                    'category_id': None,
                    'channel_name_format': '{username} 的頻道',
                    'user_limit': 0,
                    'default_bitrate': 64000
                }
            })
        
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return web.json_response({'config': config})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_update_temp_voice_config(self, request):
        """API：更新臨時語音配置"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            data = await request.json()
            
            data_file = os.path.join('data', guild_id, 'temp_voice.json')
            os.makedirs(os.path.dirname(data_file), exist_ok=True)
            
            # 讀取現有配置
            config = {
                'enabled': False,
                'trigger_channel_id': None,
                'category_id': None,
                'channel_name_format': '{username} 的頻道',
                'user_limit': 0,
                'default_bitrate': 64000
            }
            
            if os.path.exists(data_file):
                with open(data_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            # 更新配置
            if 'enabled' in data:
                config['enabled'] = data['enabled']
            if 'trigger_channel_id' in data:
                # 將字符串 ID 轉換為整數（如果不為 None）
                try:
                    config['trigger_channel_id'] = int(data['trigger_channel_id']) if data['trigger_channel_id'] else None
                except (ValueError, TypeError):
                    config['trigger_channel_id'] = None
            if 'category_id' in data:
                # 將字符串 ID 轉換為整數（如果不為 None）
                try:
                    config['category_id'] = int(data['category_id']) if data['category_id'] else None
                except (ValueError, TypeError):
                    config['category_id'] = None
            if 'channel_name_format' in data:
                config['channel_name_format'] = data['channel_name_format']
            if 'user_limit' in data:
                config['user_limit'] = data['user_limit']
            if 'default_bitrate' in data:
                config['default_bitrate'] = data['default_bitrate']
            
            # 儲存
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            return web.json_response({'success': True, 'config': config})
        
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_get_channels(self, request):
        """API：獲取伺服器頻道列表"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            guild = self.bot.get_guild(int(guild_id))
            
            if not guild:
                return web.json_response({'error': 'Guild not found'}, status=404)
            
            # 獲取各類頻道
            text_channels = []
            voice_channels = []
            categories = []
            
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    text_channels.append({
                        'id': str(channel.id),
                        'name': channel.name,
                        'position': channel.position
                    })
                elif isinstance(channel, discord.VoiceChannel):
                    voice_channels.append({
                        'id': str(channel.id),
                        'name': channel.name,
                        'position': channel.position
                    })
                elif isinstance(channel, discord.CategoryChannel):
                    categories.append({
                        'id': str(channel.id),
                        'name': channel.name,
                        'position': channel.position
                    })
            
            return web.json_response({
                'text_channels': sorted(text_channels, key=lambda x: x['position']),
                'voice_channels': sorted(voice_channels, key=lambda x: x['position']),
                'categories': sorted(categories, key=lambda x: x['position'])
            })
        
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def dashboard(self, request):
        """儀表板"""
        session = await get_session(request)
        user = session.get('user')
        
        if not user:
            session['next_url'] = str(request.rel_url)
            raise web.HTTPFound('/login')
        
        guild_id = request.match_info.get('guild_id')
        feature = request.match_info.get('feature', '')
        if feature:
            feature = urllib.parse.unquote(str(feature)).strip()
        
        # 檢查是否為開發者
        is_dev = self.is_developer(user['id'])
        
        # 驗證用戶是否有權限訪問此伺服器
        has_access = False
        guild_name = "Unknown Server"
        
        if is_dev:
            # 開發者直接允許訪問，從機器人獲取伺服器名稱
            guild = self.bot.get_guild(int(guild_id))
            if guild:
                has_access = True
                guild_name = guild.name
            else:
                with open('web/404.html', 'r', encoding='utf-8') as f:
                    html = f.read()
                return web.Response(text=html, content_type='text/html', status=404)
        else:
            # 非開發者需要有管理權限
            access_token = session.get('access_token')
            user_guilds = await self.get_user_guilds(access_token)
            if not user_guilds:
                raise web.HTTPFound('/select-server')
            
            # 檢查用戶是否在此伺服器且有管理權限
            for guild in user_guilds:
                if guild['id'] == guild_id:
                    permissions = int(guild.get('permissions', 0))
                    if permissions & 0x8 or permissions & 0x20:  # 管理員或管理伺服器
                        has_access = True
                        guild_name = guild['name']
                        break
        
        if not has_access:
            with open('web/404.html', 'r', encoding='utf-8') as f:
                html = f.read()
            return web.Response(text=html, content_type='text/html', status=404)
        
        with open('web/dashboard.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        # 替換用戶資訊
        avatar_url = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png" if user.get('avatar') else "https://cdn.discordapp.com/embed/avatars/0.png"
        
        html = html.replace('{USERNAME}', user['username'])
        html = html.replace('{AVATAR_URL}', avatar_url)
        html = html.replace('{GUILD_ID}', guild_id)
        html = html.replace('{GUILD_NAME}', guild_name)
        html = html.replace('{INITIAL_FEATURE}', feature or '')
        
        return web.Response(text=html, content_type='text/html')
    
    async def logout(self, request):
        """登出"""
        session = await get_session(request)
        session.clear()
        raise web.HTTPFound('/')
    
    async def api_get_warnings(self, request):
        """獲取警告數據"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info['guild_id']
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            file_path = f'./data/{guild_id}/warnings.json'
            if not os.path.exists(file_path):
                return web.json_response({'warnings': {}})
            
            with open(file_path, 'r', encoding='utf-8') as f:
                warnings_data = json.load(f)
            
            # 獲取用戶信息
            guild = self.bot.get_guild(int(guild_id))
            enriched_warnings = {}
            
            if guild:
                for user_id, warnings in warnings_data.items():
                    member = guild.get_member(int(user_id))
                    enriched_warnings[user_id] = {
                        'username': member.name if member else '未知用戶',
                        'display_name': member.display_name if member else '未知用戶',
                        'avatar': str(member.display_avatar.url) if member else None,
                        'warnings': warnings,
                        'warn_count': len(warnings)
                    }
            else:
                enriched_warnings = {uid: {'username': '未知', 'warnings': warns, 'warn_count': len(warns)} 
                                   for uid, warns in warnings_data.items()}
            
            return web.json_response({'warnings': enriched_warnings})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_clear_warnings(self, request):
        """清除用戶所有警告"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info['guild_id']
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        user_id = request.match_info['user_id']
        
        try:
            file_path = f'./data/{guild_id}/warnings.json'
            if not os.path.exists(file_path):
                return web.json_response({'success': True, 'message': '沒有警告記錄'})
            
            with open(file_path, 'r', encoding='utf-8') as f:
                warnings_data = json.load(f)
            
            if user_id in warnings_data:
                warn_count = len(warnings_data[user_id])
                del warnings_data[user_id]
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(warnings_data, f, ensure_ascii=False, indent=4)
                
                return web.json_response({
                    'success': True, 
                    'message': f'已清除 {warn_count} 次警告'
                })
            else:
                return web.json_response({'success': True, 'message': '沒有警告記錄'})
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_remove_latest_warning(self, request):
        """移除用戶最近一次警告"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info['guild_id']
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        user_id = request.match_info['user_id']
        
        try:
            file_path = f'./data/{guild_id}/warnings.json'
            if not os.path.exists(file_path):
                return web.json_response({'success': False, 'message': '沒有警告記錄'})
            
            with open(file_path, 'r', encoding='utf-8') as f:
                warnings_data = json.load(f)
            
            if user_id in warnings_data and len(warnings_data[user_id]) > 0:
                removed = warnings_data[user_id].pop()
                
                if len(warnings_data[user_id]) == 0:
                    del warnings_data[user_id]
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(warnings_data, f, ensure_ascii=False, indent=4)
                
                return web.json_response({
                    'success': True, 
                    'message': f'已移除警告',
                    'removed_warning': removed
                })
            else:
                return web.json_response({'success': False, 'message': '沒有警告記錄'})
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_remove_warning_by_index(self, request):
        """移除用戶指定索引的警告"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info['guild_id']
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        user_id = request.match_info['user_id']
        index = int(request.match_info['index'])
        
        try:
            file_path = f'./data/{guild_id}/warnings.json'
            if not os.path.exists(file_path):
                return web.json_response({'success': False, 'message': '沒有警告記錄'})
            
            with open(file_path, 'r', encoding='utf-8') as f:
                warnings_data = json.load(f)
            
            if user_id in warnings_data and len(warnings_data[user_id]) > index >= 0:
                removed = warnings_data[user_id].pop(index)
                
                if len(warnings_data[user_id]) == 0:
                    del warnings_data[user_id]
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(warnings_data, f, ensure_ascii=False, indent=4)
                
                return web.json_response({
                    'success': True, 
                    'message': '已移除警告',
                    'removed_warning': removed
                })
            else:
                return web.json_response({'success': False, 'message': '警告不存在'})
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_get_achievements(self, request):
        """獲取成就數據"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info['guild_id']
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            file_path = f'./data/{guild_id}/achievements.json'
            if not os.path.exists(file_path):
                return web.json_response({'achievements': {}})
            
            with open(file_path, 'r', encoding='utf-8') as f:
                achievements_data = json.load(f)
            
            # 獲取用戶信息和成就定義
            guild = self.bot.get_guild(int(guild_id))
            achievements_cog = self.bot.get_cog('Achievements')
            
            enriched_achievements = {}
            
            if guild and achievements_cog:
                achievement_defs = achievements_cog.achievement_definitions
                
                for user_id, user_achievements in achievements_data.items():
                    member = guild.get_member(int(user_id))
                    
                    # 豐富成就信息（支援 dict 與 list 兼容結構）
                    enriched_list = []
                    if isinstance(user_achievements, dict):
                        unlocked_ids = user_achievements.get('unlocked', [])
                    elif isinstance(user_achievements, list):
                        unlocked_ids = user_achievements
                    else:
                        unlocked_ids = []

                    for ach_id in unlocked_ids:
                        if ach_id in achievement_defs:
                            ach_def = achievement_defs[ach_id]
                            enriched_list.append({
                                'id': ach_id,
                                'name': ach_def.get('name', ach_id),
                                'description': ach_def.get('description', ''),
                                'rarity': ach_def.get('tier', 'common'),
                                'category': ach_def.get('category', 'general')
                            })
                    
                    enriched_achievements[user_id] = {
                        'username': member.name if member else '未知用戶',
                        'display_name': member.display_name if member else '未知用戶',
                        'avatar': str(member.display_avatar.url) if member else None,
                        'achievements': enriched_list,
                        'achievement_count': len(enriched_list)
                    }
            else:
                enriched_achievements = {uid: {'username': '未知', 'achievements': achs.get('unlocked', []) if isinstance(achs, dict) else achs, 'achievement_count': len(achs.get('unlocked', []) if isinstance(achs, dict) else achs)} 
                                        for uid, achs in achievements_data.items()}
            
            return web.json_response({'achievements': enriched_achievements})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_grant_achievement(self, request):
        """授予成就"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info['guild_id']
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        user_id = request.match_info['user_id']
        achievement_id = request.match_info['achievement_id']
        
        try:
            file_path = f'./data/{guild_id}/achievements.json'
            
            # 載入數據
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    achievements_data = json.load(f)
            else:
                achievements_data = {}
            
            achievements_cog = self.bot.get_cog('Achievements')
            if achievements_cog:
                success = achievements_cog.unlock_achievement(int(guild_id), int(user_id), achievement_id)
                if success:
                    return web.json_response({'success': True, 'message': '成就已授予'})
                else:
                    return web.json_response({'success': False, 'message': '用戶已擁有此成就'})

            # 添加成就（使用標準 dict schema）
            if user_id not in achievements_data or isinstance(achievements_data[user_id], list):
                old_list = achievements_data.get(user_id, []) if isinstance(achievements_data.get(user_id), list) else []
                achievements_data[user_id] = {
                    'unlocked': list(old_list),
                    'progress': {}
                }
            
            if achievement_id not in achievements_data[user_id]['unlocked']:
                achievements_data[user_id]['unlocked'].append(achievement_id)
                achievements_data[user_id][achievement_id] = {
                    'unlocked_at': datetime.utcnow().isoformat()
                }
                
                # 保存
                os.makedirs(f'./data/{guild_id}', exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(achievements_data, f, ensure_ascii=False, indent=4)
                
                return web.json_response({
                    'success': True, 
                    'message': '成就已授予'
                })
            else:
                return web.json_response({
                    'success': False, 
                    'message': '用戶已擁有此成就'
                })
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_revoke_achievement(self, request):
        """撤銷成就"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info['guild_id']
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        user_id = request.match_info['user_id']
        achievement_id = request.match_info['achievement_id']
        
        try:
            file_path = f'./data/{guild_id}/achievements.json'
            if not os.path.exists(file_path):
                return web.json_response({'success': False, 'message': '沒有成就記錄'})
            
            with open(file_path, 'r', encoding='utf-8') as f:
                achievements_data = json.load(f)
            
            if user_id in achievements_data:
                u_data = achievements_data[user_id]
                removed = False
                if isinstance(u_data, list):
                    if achievement_id in u_data:
                        u_data.remove(achievement_id)
                        removed = True
                        if len(u_data) == 0:
                            del achievements_data[user_id]
                elif isinstance(u_data, dict):
                    unlocked = u_data.get('unlocked', [])
                    if achievement_id in unlocked:
                        unlocked.remove(achievement_id)
                        removed = True
                        if achievement_id in u_data:
                            del u_data[achievement_id]
                        if len(unlocked) == 0:
                            del achievements_data[user_id]
                
                if removed:
                    self._atomic_json_write(file_path, achievements_data, indent=4)
                    return web.json_response({
                        'success': True, 
                        'message': '成就已撤銷'
                    })
                else:
                    return web.json_response({
                        'success': False, 
                        'message': '用戶沒有此成就'
                    })
            else:
                return web.json_response({
                    'success': False, 
                    'message': '用戶沒有此成就'
                })
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_get_tickets(self, request):
        """API：獲取客服單數據"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info['guild_id']
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            file_path = f'./data/{guild_id}/tickets.json'
            if not os.path.exists(file_path):
                return web.json_response({
                    'exists': False,
                    'data': {
                        'enabled': False,
                        'category_id': None,
                        'support_role_id': None,
                        'log_channel_id': None,
                        'tickets': {},
                        'ticket_count': 0
                    }
                })
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 豐富客服單信息（添加用戶名等）
            guild = self.bot.get_guild(int(guild_id))
            if guild:
                for ticket_id, ticket in data['tickets'].items():
                    user = guild.get_member(int(ticket['user_id']))
                    ticket['user_name'] = user.name if user else '未知用戶'
                    ticket['user_avatar'] = str(user.avatar.url) if user and user.avatar else None
                    
                    if ticket.get('closed_by'):
                        closer = guild.get_member(int(ticket['closed_by']))
                        ticket['closer_name'] = closer.name if closer else '未知用戶'
            
            return web.json_response({'exists': True, 'data': data})
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_update_ticket_settings(self, request):
        """API：更新客服單設定"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info['guild_id']
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            body = await request.json()
            file_path = f'./data/{guild_id}/tickets.json'
            
            # 讀取現有數據
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {
                    'enabled': False,
                    'category_id': None,
                    'support_role_id': None,
                    'log_channel_id': None,
                    'tickets': {},
                    'ticket_count': 0
                }
            
            # 更新設定
            if 'enabled' in body:
                data['enabled'] = bool(body['enabled'])
            if 'category_id' in body:
                c_id = str(body['category_id']).strip() if body['category_id'] is not None else ""
                data['category_id'] = c_id if c_id and c_id.isdigit() else None
            if 'support_role_id' in body:
                r_id = str(body['support_role_id']).strip() if body['support_role_id'] is not None else ""
                data['support_role_id'] = r_id if r_id and r_id.isdigit() else None
            if 'log_channel_id' in body:
                l_id = str(body['log_channel_id']).strip() if body['log_channel_id'] is not None else ""
                data['log_channel_id'] = l_id if l_id and l_id.isdigit() else None
            if 'panel_channel_id' in body:
                p_id = str(body['panel_channel_id']).strip() if body['panel_channel_id'] is not None else ""
                data['panel_channel_id'] = p_id if p_id and p_id.isdigit() else None
            
            # 原子保存數據
            self._atomic_json_write(file_path, data, indent=4)
            
            return web.json_response({'success': True, 'message': '設定已更新'})
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_close_ticket(self, request):
        """API：關閉客服單（已禁用）"""
        return web.json_response({
            'success': False, 
            'message': '網頁後台不支援關閉客服單，請使用 Discord 內的關閉按鈕'
        }, status=403)
    
    async def api_my_tickets(self, request):
        """API：獲取當前用戶的所有客服單"""
        session = await get_session(request)
        user = session.get('user')
        
        if not user:
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        user_id = user['id']
        
        try:
            all_tickets = []
            server_map = {}
            
            # 遍歷所有伺服器，找出用戶的客服單
            for guild in self.bot.guilds:
                guild_id = str(guild.id)
                file_path = f'./data/{guild_id}/tickets.json'
                
                if not os.path.exists(file_path):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 找出屬於該用戶的客服單
                    for ticket_id, ticket in data.get('tickets', {}).items():
                        if str(ticket.get('user_id')) == str(user_id):
                            ticket_info = {
                                'ticket_id': ticket_id,
                                'guild_id': guild_id,
                                'channel_name': ticket.get('channel_name', '未知'),
                                'channel_id': ticket.get('channel_id'),
                                'status': ticket.get('status', 'unknown'),
                                'created_at': ticket.get('created_at', ''),
                                'closed_at': ticket.get('closed_at'),
                                'closed_reason': ticket.get('close_reason')
                            }
                            all_tickets.append(ticket_info)
                            server_map[guild_id] = guild.name
                
                except Exception as e:
                    print(f"讀取伺服器 {guild.name} 的客服單時發生錯誤: {e}")
                    continue
            
            return web.json_response({
                'tickets': all_tickets,
                'servers': server_map
            })
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_get_ticket_transcript(self, request):
        """API：獲取客服單聊天記錄HTML"""
        session = await get_session(request)
        user = session.get('user')
        
        if not user:
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info['guild_id']
        ticket_id = request.match_info['ticket_id']
        
        # 檢查用戶權限
        if not await self.check_guild_permission(user['id'], guild_id, session.get('access_token')):
            # 如果不是管理員，檢查是否為客服單創建者
            try:
                file_path = f'./data/{guild_id}/tickets.json'
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if ticket_id in data['tickets']:
                        ticket = data['tickets'][ticket_id]
                        if str(ticket.get('user_id')) != str(user['id']):
                            return web.json_response({'error': 'Forbidden'}, status=403)
                    else:
                        return web.json_response({'error': '客服單不存在'}, status=404)
                else:
                    return web.json_response({'error': '找不到客服單'}, status=404)
            except:
                return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            # 獲取客服單數據
            file_path = f'./data/{guild_id}/tickets.json'
            if not os.path.exists(file_path):
                return web.json_response({'error': '找不到客服單'}, status=404)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if ticket_id not in data['tickets']:
                return web.json_response({'error': '客服單不存在'}, status=404)
            
            ticket = data['tickets'][ticket_id]
            
            # 檢查權限：只有客服單創建者或管理員可以查看
            user_id = user['id']
            is_ticket_owner = str(ticket.get('user_id')) == str(user_id)
            
            # 檢查是否為管理員（從 access_token 獲取用戶的公團權限）
            is_admin = False
            access_token = session.get('access_token')
            if access_token:
                user_guilds = await self.get_user_guilds(access_token)
                if user_guilds:
                    for guild in user_guilds:
                        if str(guild['id']) == str(guild_id):
                            permissions = int(guild.get('permissions', 0))
                            is_admin = (permissions & 0x8) == 0x8
                            break
            
            if not (is_ticket_owner or is_admin):
                return web.json_response({'error': '無權查看此客服單'}, status=403)
            
            # 獲取HTML文件
            channel_name = ticket.get('channel_name', f"客服單-{ticket_id}")
            transcript_path = f'./data/{guild_id}/ticket/{channel_name}-{ticket_id}.html'
            
            if not os.path.exists(transcript_path):
                return web.json_response({'error': '找不到聊天記錄'}, status=404)
            
            with open(transcript_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            return web.Response(text=html_content, content_type='text/html')
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_create_ticket_panel(self, request):
        """API：創建客服單面板"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info['guild_id']
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            body = await request.json()
            channel_id = body.get('channel_id')
            
            if not channel_id:
                return web.json_response({'error': '缺少頻道ID'}, status=400)
            
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return web.json_response({'error': '找不到伺服器'}, status=404)
            
            channel = guild.get_channel(int(channel_id))
            if not channel:
                return web.json_response({'error': '找不到頻道'}, status=404)
            
            # 獲取tickets cog
            tickets_cog = self.bot.get_cog('Tickets')
            if not tickets_cog:
                return web.json_response({'error': '客服單系統未啟動'}, status=500)
            
            # 創建嵌入消息
            embed = discord.Embed(
                title="🎫 客服單系統",
                description="需要幫助嗎？點擊下方按鈕創建客服單\n\n"
                           "📋 創建客服單後，我們的支持團隊會盡快回覆您\n"
                           "⏱️ 請耐心等待，我們會盡快處理您的問題",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"{guild.name} 客服支持")
            
            # 導入TicketPanelView
            from cogs.tickets import TicketPanelView
            view = TicketPanelView(tickets_cog)
            
            # 發送面板
            message = await channel.send(embed=embed, view=view)
            
            # 保存面板訊息ID
            file_path = f'./data/{guild_id}/tickets.json'
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {
                    'enabled': False,
                    'category_id': None,
                    'support_role_id': None,
                    'log_channel_id': None,
                    'panel_channel_id': None,
                    'panel_message_id': None,
                    'tickets': {},
                    'ticket_count': 0
                }
            
            data['panel_channel_id'] = str(channel_id)
            data['panel_message_id'] = str(message.id)
            
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            return web.json_response({
                'success': True,
                'message': '已創建客服單面板',
                'channel_id': str(channel_id),
                'message_id': str(message.id)
            })
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    # ===== 自動回覆系統 API =====
    
    async def api_get_auto_replies(self, request):
        """API：獲取自動回覆規則"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        file_path = f'./data/{guild_id}/auto_reply.json'
        
        if not os.path.exists(file_path):
            return web.json_response({
                'enabled': True,
                'rules': []
            })
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 獲取伺服器頻道和角色信息
            guild = self.bot.get_guild(int(guild_id))
            if guild:
                # 添加頻道和角色名稱
                for rule in data.get('rules', []):
                    # 添加頻道名稱
                    if 'channel_ids' in rule:
                        channels = []
                        for ch_id in rule['channel_ids']:
                            channel = guild.get_channel(int(ch_id))
                            if channel:
                                channels.append({'id': ch_id, 'name': channel.name})
                        rule['channels'] = channels
                    
                    # 添加角色名稱
                    if 'role_ids' in rule:
                        roles = []
                        for role_id in rule['role_ids']:
                            role = guild.get_role(int(role_id))
                            if role:
                                roles.append({'id': role_id, 'name': role.name})
                        rule['roles'] = roles
            
            return web.json_response(data)
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_add_auto_reply(self, request):
        """API：添加自動回覆規則"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            data_input = await request.json()
            
            # 載入現有數據
            file_path = f'./data/{guild_id}/auto_reply.json'
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {'enabled': True, 'rules': []}
            
            # 創建新規則
            new_rule = {
                'id': max([r.get('id', 0) for r in data.get('rules', [])] + [0]) + 1,
                'trigger': data_input.get('trigger', ''),
                'reply': data_input.get('reply', ''),
                'match_type': data_input.get('match_type', 'contains'),
                'reply_type': data_input.get('reply_type', 'message'),
                'enabled': data_input.get('enabled', True),
                'case_sensitive': data_input.get('case_sensitive', False),
                'mention_user': data_input.get('mention_user', False),
                'trigger_once': data_input.get('trigger_once', False),
                'channel_ids': data_input.get('channel_ids', []),
                'role_ids': data_input.get('role_ids', []),
                'reaction': data_input.get('reaction', '👍'),
                'triggered_count': 0,
                'created_at': datetime.now().isoformat(),
                'created_by': session.get('user', {}).get('id')
            }
            
            data.setdefault('rules', []).append(new_rule)
            
            # 保存
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return web.json_response({'success': True, 'rule': new_rule})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_update_auto_reply(self, request):
        """API：更新自動回覆規則"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        rule_id = int(request.match_info.get('rule_id'))
        
        try:
            data_input = await request.json()
            
            file_path = f'./data/{guild_id}/auto_reply.json'
            if not os.path.exists(file_path):
                return web.json_response({'error': '找不到自動回覆數據'}, status=404)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 查找並更新規則
            found = False
            for rule in data.get('rules', []):
                if rule['id'] == rule_id:
                    rule['trigger'] = data_input.get('trigger', rule['trigger'])
                    rule['reply'] = data_input.get('reply', rule['reply'])
                    rule['match_type'] = data_input.get('match_type', rule['match_type'])
                    rule['reply_type'] = data_input.get('reply_type', rule['reply_type'])
                    rule['enabled'] = data_input.get('enabled', rule['enabled'])
                    rule['case_sensitive'] = data_input.get('case_sensitive', rule.get('case_sensitive', False))
                    rule['mention_user'] = data_input.get('mention_user', rule.get('mention_user', False))
                    rule['trigger_once'] = data_input.get('trigger_once', rule.get('trigger_once', False))
                    rule['channel_ids'] = data_input.get('channel_ids', rule.get('channel_ids', []))
                    rule['role_ids'] = data_input.get('role_ids', rule.get('role_ids', []))
                    rule['reaction'] = data_input.get('reaction', rule.get('reaction', '👍'))
                    rule['updated_at'] = datetime.now().isoformat()
                    found = True
                    break
            
            if not found:
                return web.json_response({'error': '找不到指定規則'}, status=404)
            
            # 保存
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return web.json_response({'success': True})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_delete_auto_reply(self, request):
        """API：刪除自動回覆規則"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        rule_id = int(request.match_info.get('rule_id'))
        
        try:
            file_path = f'./data/{guild_id}/auto_reply.json'
            if not os.path.exists(file_path):
                return web.json_response({'error': '找不到自動回覆數據'}, status=404)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 刪除規則
            original_length = len(data.get('rules', []))
            data['rules'] = [r for r in data.get('rules', []) if r['id'] != rule_id]
            
            if len(data['rules']) == original_length:
                return web.json_response({'error': '找不到指定規則'}, status=404)
            
            # 保存
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return web.json_response({'success': True})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_toggle_auto_reply_system(self, request):
        """API：開關自動回覆系統"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            data_input = await request.json()
            enabled = data_input.get('enabled', True)
            
            file_path = f'./data/{guild_id}/auto_reply.json'
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {'enabled': True, 'rules': []}
            
            data['enabled'] = enabled
            
            # 保存
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return web.json_response({'success': True, 'enabled': enabled})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_toggle_auto_reply_rule(self, request):
        """API：開關特定自動回覆規則"""
        session = await get_session(request)
        
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        
        # 檢查用戶權限
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        rule_id = int(request.match_info.get('rule_id'))
        
        try:
            data_input = await request.json()
            enabled = data_input.get('enabled', True)
            
            file_path = f'./data/{guild_id}/auto_reply.json'
            if not os.path.exists(file_path):
                return web.json_response({'error': '找不到自動回覆數據'}, status=404)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 更新規則狀態
            found = False
            for rule in data.get('rules', []):
                if rule['id'] == rule_id:
                    rule['enabled'] = enabled
                    found = True
                    break
            
            if not found:
                return web.json_response({'error': '找不到指定規則'}, status=404)
            
            # 保存
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return web.json_response({'success': True, 'enabled': enabled})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    # ==================== 安全系統 API ====================
    
    async def api_get_security(self, request):
        """獲取安全系統設定"""
        try:
            guild_id = request.match_info['guild_id']
            
            # 檢查權限
            session = await get_session(request)
            user = session.get('user')
            if not user:
                return web.json_response({'error': '未登入'}, status=401)
            
            # 檢查用戶權限
            if not await self.check_guild_permission(user['id'], guild_id, session.get('access_token')):
                return web.json_response({'error': 'Forbidden'}, status=403)
            
            # 獲取數據
            filepath = f"./data/{guild_id}/security.json"
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {
                    "enabled": True,
                    "banned_words": [],
                    "timeout_duration": 60,
                    "action_type": "timeout",
                    "whitelist_roles": [],
                    "whitelist_channels": [],
                    "case_sensitive": False,
                    "match_type": "contains"
                }
            
            return web.json_response(data)
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_update_security(self, request):
        """更新安全系統設定"""
        try:
            guild_id = request.match_info['guild_id']
            
            # 檢查權限
            session = await get_session(request)
            user = session.get('user')
            if not user:
                return web.json_response({'error': '未登入'}, status=401)
            
            # 檢查用戶權限
            if not await self.check_guild_permission(user['id'], guild_id, session.get('access_token')):
                return web.json_response({'error': 'Forbidden'}, status=403)
            
            # 讀取請求數據
            data = await request.json()
            
            # 驗證數據
            if 'timeout_duration' in data:
                timeout = data['timeout_duration']
                if not isinstance(timeout, int) or timeout < 1 or timeout > 2419200:
                    return web.json_response({'error': '超時時長必須在 1-2419200 秒之間'}, status=400)
            
            if 'action_type' in data:
                if data['action_type'] not in ['timeout', 'delete', 'warn']:
                    return web.json_response({'error': '無效的處罰類型'}, status=400)
            
            if 'match_type' in data:
                if data['match_type'] not in ['contains', 'exact', 'regex']:
                    return web.json_response({'error': '無效的匹配模式'}, status=400)
            
            # 保存數據
            folder = f"./data/{guild_id}"
            os.makedirs(folder, exist_ok=True)
            
            filepath = f"{folder}/security.json"
            
            # 讀取現有數據或創建新數據
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            else:
                existing_data = {
                    "enabled": True,
                    "banned_words": [],
                    "timeout_duration": 60,
                    "action_type": "timeout",
                    "whitelist_roles": [],
                    "whitelist_channels": [],
                    "case_sensitive": False,
                    "match_type": "contains"
                }
            
            # 更新數據
            existing_data.update(data)
            
            # 保存
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
            
            return web.json_response({'success': True, 'data': existing_data})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_add_banned_word(self, request):
        """添加違禁詞"""
        try:
            guild_id = request.match_info['guild_id']
            
            # 檢查權限
            session = await get_session(request)
            user = session.get('user')
            if not user:
                return web.json_response({'error': '未登入'}, status=401)
            
            # 檢查用戶權限
            if not await self.check_guild_permission(user['id'], guild_id, session.get('access_token')):
                return web.json_response({'error': 'Forbidden'}, status=403)
            
            # 讀取請求數據
            data = await request.json()
            word = data.get('word', '').strip()
            
            if not word:
                return web.json_response({'error': '違禁詞不能為空'}, status=400)
            
            # 讀取現有數據
            folder = f"./data/{guild_id}"
            os.makedirs(folder, exist_ok=True)
            filepath = f"{folder}/security.json"
            
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    security_data = json.load(f)
            else:
                security_data = {
                    "enabled": True,
                    "banned_words": [],
                    "timeout_duration": 60,
                    "action_type": "timeout",
                    "whitelist_roles": [],
                    "whitelist_channels": [],
                    "case_sensitive": False,
                    "match_type": "contains"
                }
            
            # 檢查是否已存在
            if word in security_data['banned_words']:
                return web.json_response({'error': '該違禁詞已存在'}, status=400)
            
            # 添加違禁詞
            security_data['banned_words'].append(word)
            
            # 保存
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(security_data, f, ensure_ascii=False, indent=2)
            
            return web.json_response({'success': True, 'word': word, 'banned_words': security_data['banned_words']})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_delete_banned_word(self, request):
        """刪除違禁詞"""
        try:
            guild_id = request.match_info['guild_id']
            
            # 檢查權限
            session = await get_session(request)
            user = session.get('user')
            if not user:
                return web.json_response({'error': '未登入'}, status=401)
            
            # 檢查用戶權限
            if not await self.check_guild_permission(user['id'], guild_id, session.get('access_token')):
                return web.json_response({'error': 'Forbidden'}, status=403)
            
            # 讀取請求數據
            data = await request.json()
            word = data.get('word', '').strip()
            
            if not word:
                return web.json_response({'error': '違禁詞不能為空'}, status=400)
            
            # 讀取現有數據
            filepath = f"./data/{guild_id}/security.json"
            if not os.path.exists(filepath):
                return web.json_response({'error': '安全系統數據不存在'}, status=404)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                security_data = json.load(f)
            
            # 檢查是否存在
            if word not in security_data['banned_words']:
                return web.json_response({'error': '該違禁詞不存在'}, status=404)
            
            # 移除違禁詞
            security_data['banned_words'].remove(word)
            
            # 保存
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(security_data, f, ensure_ascii=False, indent=2)
            
            return web.json_response({'success': True, 'word': word, 'banned_words': security_data['banned_words']})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    def is_developer(self, user_id):
        """檢查用戶是否為開發者"""
        return int(user_id) in self.dev_ids
    
    async def check_guild_permission(self, user_id, guild_id, access_token):
        """檢查用戶是否有權限訪問指定的伺服器
        
        Args:
            user_id: 用戶 ID
            guild_id: 伺服器 ID（字符串）
            access_token: Discord OAuth2 access token
            
        Returns:
            bool: 用戶是否有權限
        """
        # 開發者可以訪問所有伺服器
        if self.is_developer(user_id):
            return True
        
        # 檢查機器人是否在該伺服器中
        bot_guild_ids = {str(guild.id) for guild in self.bot.guilds}
        if guild_id not in bot_guild_ids:
            return False
        
        # 獲取用戶的 Discord 伺服器列表（60s 快取防 429）
        try:
            user_guilds = await self.get_user_guilds(access_token)
            if not user_guilds:
                return False
            
            # 檢查用戶是否對該伺服器有管理權限
            for guild in user_guilds:
                if guild['id'] == guild_id:
                    permissions = int(guild.get('permissions', 0))
                    # 檢查管理員權限 (0x8) 或管理伺服器權限 (0x20)
                    return bool(permissions & 0x8 or permissions & 0x20)
            
            return False
        except Exception as e:
            print(f"權限檢查錯誤: {e}")
            return False
    
    async def dev_panel(self, request):
        """開發者面板"""
        session = await get_session(request)
        user = session.get('user')
        
        if not user:
            raise web.HTTPFound('/login')
        
        # 驗證是否為開發者
        if not self.is_developer(user['id']):
            with open('web/404.html', 'r', encoding='utf-8') as f:
                html = f.read()
            return web.Response(text=html, content_type='text/html', status=404)
        
        with open('web/dev-panel.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        # 替換用戶資訊
        avatar_url = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png" if user.get('avatar') else "https://cdn.discordapp.com/embed/avatars/0.png"
        
        html = html.replace('{USERNAME}', user['username'])
        html = html.replace('{AVATAR_URL}', avatar_url)
        
        return web.Response(text=html, content_type='text/html')
    
    async def api_dev_all_guilds(self, request):
        """API：獲取所有伺服器列表（開發者專用）"""
        try:
            session = await get_session(request)
            user = session.get('user')
            
            if not user:
                return web.json_response({'error': 'Unauthorized'}, status=401)
            
            # 驗證是否為開發者
            if not self.is_developer(user['id']):
                return web.json_response({'error': 'Forbidden'}, status=403)
            
            # 獲取所有伺服器資訊
            guilds_data = []
            for guild in self.bot.guilds:
                try:
                    # 獲取伺服器圖標
                    icon_url = str(guild.icon.url) if guild.icon else None
                    
                    # 計算在線成員數
                    online_count = sum(1 for m in guild.members if m.status != discord.Status.offline)
                    
                    guilds_data.append({
                        'id': str(guild.id),
                        'name': guild.name,
                        'icon': icon_url,
                        'member_count': guild.member_count,
                        'online_count': online_count,
                        'owner_id': str(guild.owner_id),
                        'created_at': guild.created_at.isoformat(),
                        'text_channels': len(guild.text_channels),
                        'voice_channels': len(guild.voice_channels),
                        'roles': len(guild.roles),
                        'emojis': len(guild.emojis)
                    })
                except Exception as e:
                    print(f"處理伺服器 {guild.id} 時出錯: {e}")
                    # 繼續處理其他伺服器
                    continue
            
            return web.json_response({'guilds': guilds_data, 'total': len(guilds_data)})
        except Exception as e:
            print(f"api_dev_all_guilds 錯誤: {e}")
            import traceback
            traceback.print_exc()
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_dev_guild_config(self, request):
        """API：獲取伺服器所有配置（開發者專用）"""
        try:
            session = await get_session(request)
            user = session.get('user')
            
            if not user:
                return web.json_response({'error': 'Unauthorized'}, status=401)
            
            # 驗證是否為開發者
            if not self.is_developer(user['id']):
                return web.json_response({'error': 'Forbidden'}, status=403)
            
            guild_id = request.match_info.get('guild_id')
            guild = self.bot.get_guild(int(guild_id))
            
            if not guild:
                return web.json_response({'error': 'Guild not found'}, status=404)
            
            # 讀取所有配置文件
            data_dir = os.path.join('data', guild_id)
            configs = {}
            
            if os.path.exists(data_dir):
                for filename in os.listdir(data_dir):
                    if filename.endswith('.json'):
                        filepath = os.path.join(data_dir, filename)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                config_name = filename[:-5]  # 移除 .json
                                configs[config_name] = json.load(f)
                        except Exception as e:
                            print(f"讀取配置文件 {filename} 失敗: {e}")
                            configs[filename] = {'error': str(e)}
            
            # 獲取伺服器基本資訊
            guild_info = {
                'id': str(guild.id),
                'name': guild.name,
                'icon': str(guild.icon.url) if guild.icon else None,
                'owner': str(guild.owner) if guild.owner else 'Unknown',
                'owner_id': str(guild.owner_id),
                'member_count': guild.member_count,
                'created_at': guild.created_at.isoformat(),
                'premium_tier': guild.premium_tier,
                'premium_subscription_count': guild.premium_subscription_count or 0,
                'description': guild.description,
                'features': list(guild.features),
                'verification_level': str(guild.verification_level),
                'channels': {
                    'text': len(guild.text_channels),
                    'voice': len(guild.voice_channels),
                    'categories': len(guild.categories),
                    'total': len(guild.channels)
                },
                'roles': len(guild.roles),
                'emojis': len(guild.emojis)
            }
            
            return web.json_response({
                'guild_info': guild_info,
                'configs': configs
            })
        except Exception as e:
            print(f"api_dev_guild_config 錯誤: {e}")
            import traceback
            traceback.print_exc()
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_dev_guild_members(self, request):
        """API：獲取伺服器成員列表（開發者專用）"""
        try:
            session = await get_session(request)
            user = session.get('user')
            
            if not user:
                return web.json_response({'error': 'Unauthorized'}, status=401)
            
            # 驗證是否為開發者
            if not self.is_developer(user['id']):
                return web.json_response({'error': 'Forbidden'}, status=403)
            
            guild_id = request.match_info.get('guild_id')
            guild = self.bot.get_guild(int(guild_id))
            
            if not guild:
                return web.json_response({'error': 'Guild not found'}, status=404)
            
            # 獲取成員列表（限制前100個，避免過大）
            limit = int(request.query.get('limit', 100))
            members_data = []
            
            for member in list(guild.members)[:limit]:
                try:
                    members_data.append({
                        'id': str(member.id),
                        'name': member.name,
                        'display_name': member.display_name,
                        'avatar': str(member.display_avatar.url),
                        'bot': member.bot,
                        'status': str(member.status),
                        'joined_at': member.joined_at.isoformat() if member.joined_at else None,
                        'roles': [role.name for role in member.roles if role.name != '@everyone'],
                        'top_role': member.top_role.name if member.top_role else None
                    })
                except Exception as e:
                    print(f"處理成員 {member.id} 時出錯: {e}")
                    # 繼續處理其他成員
                    continue
            
            return web.json_response({
                'members': members_data,
                'total': guild.member_count,
                'shown': len(members_data)
            })
        except Exception as e:
            print(f"api_dev_guild_members 錯誤: {e}")
            import traceback
            traceback.print_exc()
            return web.json_response({'error': str(e)}, status=500)

    # ---------------- AI 聊天系統 API ----------------

    async def api_get_roles(self, request):
        """API：獲取伺服器身分組清單"""
        session = await get_session(request)
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return web.json_response({'error': 'Guild not found'}, status=404)
            
            roles = []
            for r in sorted(guild.roles, key=lambda x: x.position, reverse=True):
                if r.is_default():
                    continue
                color_hex = f"#{r.color.value:06x}" if r.color.value else "#99aab5"
                roles.append({
                    'id': str(r.id),
                    'name': r.name,
                    'color': color_hex,
                    'position': r.position
                })
            return web.json_response({'success': True, 'roles': roles})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def api_get_ai_config(self, request):
        """API：獲取伺服器 AI 設定與今日用量"""
        session = await get_session(request)
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            guild = self.bot.get_guild(int(guild_id))
            roles = []
            if guild:
                for r in sorted(guild.roles, key=lambda x: x.position, reverse=True):
                    if r.is_default():
                        continue
                    color_hex = f"#{r.color.value:06x}" if r.color.value else "#99aab5"
                    roles.append({
                        'id': str(r.id),
                        'name': r.name,
                        'color': color_hex,
                        'position': r.position
                    })
            
            file_path = f'./data/{guild_id}/ai_chat.json'
            default_config = {
                "enabled": True,
                "daily_limit": 1500,
                "default_role_limit": 85,
                "role_limits": {},
                "default_image_limit": 25,
                "image_role_limits": {},
                "default_draw_limit": 10,
                "draw_role_limits": {},
                "persona": "normal",
                "ai_channels": [],
                "system_prompt": "你是一個友善、熱心、幽默且知識豐富的 Discord 機器人 AI 助手。請使用繁體中文親切地回答用戶的所有問題。",
                "banned_users": {},
                "daily_usage": {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "total_messages": 0,
                    "users": {},
                    "user_images": {},
                    "user_draws": {}
                }
            }

            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = default_config

            # 補齊預設值
            for k, v in default_config.items():
                if k not in config:
                    config[k] = v

            # 跨日重置檢查
            today = datetime.now().strftime("%Y-%m-%d")
            daily_usage = config.get("daily_usage", {})
            if daily_usage.get("date") != today:
                config["daily_usage"] = {
                    "date": today,
                    "total_messages": 0,
                    "users": {},
                    "user_images": {},
                    "user_draws": {}
                }
                self._atomic_json_write(file_path, config, indent=2)
            else:
                updated_usage = False
                if "user_images" not in daily_usage:
                    daily_usage["user_images"] = {}
                    updated_usage = True
                if "user_draws" not in daily_usage:
                    daily_usage["user_draws"] = {}
                    updated_usage = True
                if updated_usage:
                    config["daily_usage"] = daily_usage

            # 讀取 server-memory.db 專屬提示詞 (支援多條累加紀錄)
            db_file = os.path.join('data', str(guild_id), 'server-memory.db')
            prompts = []
            if os.path.exists(db_file):
                try:
                    with sqlite3.connect(db_file) as conn:
                        try:
                            cur = conn.execute("SELECT prompt FROM server_prompts ORDER BY id ASC")
                            rows = cur.fetchall()
                            if rows:
                                prompts = [r[0] for r in rows if r[0].strip()]
                        except Exception:
                            pass
                        if not prompts:
                            try:
                                cur = conn.execute("SELECT prompt FROM server_prompt WHERE id = 1")
                                row = cur.fetchone()
                                if row and row[0].strip():
                                    prompts = [row[0].strip()]
                            except Exception:
                                pass
                except Exception:
                    pass
            if not prompts and config.get('system_prompt'):
                prompts = [config.get('system_prompt').strip()]

            # 依規則格式化：以逗號結尾區隔提示詞，換行無逗號視為同一條
            config['server_prompt'] = format_prompts_for_web(prompts)

            return web.json_response({
                'success': True,
                'config': config,
                'roles': roles
            })
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def api_toggle_ai(self, request):
        """API：開關伺服器 AI 聊天功能"""
        session = await get_session(request)
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            data_input = await request.json()
            enabled = bool(data_input.get('enabled', False))
            
            file_path = f'./data/{guild_id}/ai_chat.json'
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {
                    "enabled": True,
                    "daily_limit": 1500,
                    "default_role_limit": 85,
                    "role_limits": {},
                    "default_image_limit": 25,
                    "default_draw_limit": 10,
                    "ai_channels": [],
                    "system_prompt": "",
                    "banned_users": {},
                    "daily_usage": {
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "total_messages": 0,
                        "users": {}
                    }
                }
            
            config['enabled'] = enabled
            self._atomic_json_write(file_path, config, indent=2)
            
            return web.json_response({'success': True, 'enabled': enabled})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def api_update_ai_settings(self, request):
        """API：更新 AI 基本設定（系統提示詞、預設額度、每日上限）"""
        session = await get_session(request)
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            data_input = await request.json()
            file_path = f'./data/{guild_id}/ai_chat.json'
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {"enabled": True, "role_limits": {}, "banned_users": {}}
            
            if 'server_prompt' in data_input or 'system_prompt' in data_input:
                raw_prompt = data_input.get('server_prompt', data_input.get('system_prompt', '')).strip()
                parsed_prompts = parse_prompts_from_web(raw_prompt)
                formatted_web_prompt = format_prompts_for_web(parsed_prompts)

                config['system_prompt'] = "\n\n".join(parsed_prompts)
                config['server_prompt'] = formatted_web_prompt

                # 同步儲存至 data/<guild_id>/server-memory.db (寫入 server_prompts 累加表)
                db_file = os.path.join('data', str(guild_id), 'server-memory.db')
                os.makedirs(os.path.dirname(db_file), exist_ok=True)
                with sqlite3.connect(db_file) as conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS server_prompts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            prompt TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            created_by TEXT
                        )
                    """)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS server_prompt (
                            id INTEGER PRIMARY KEY CHECK (id = 1),
                            prompt TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            updated_by TEXT
                        )
                    """)
                    conn.execute("DELETE FROM server_prompts")
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    username = session.get('user', {}).get('username', 'Web 管理員')
                    for p in parsed_prompts:
                        if p.strip():
                            conn.execute(
                                "INSERT INTO server_prompts (prompt, created_at, created_by) VALUES (?, ?, ?)",
                                (p.strip(), now_str, username)
                            )
                    combined = "\n\n".join(parsed_prompts)
                    conn.execute("""
                        INSERT INTO server_prompt (id, prompt, updated_at, updated_by)
                        VALUES (1, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            prompt = excluded.prompt,
                            updated_at = excluded.updated_at,
                            updated_by = excluded.updated_by
                    """, (combined, now_str, username))
                    conn.commit()

            if 'default_role_limit' in data_input:
                config['default_role_limit'] = min(max(20, int(data_input['default_role_limit'])), 500)
            if 'default_image_limit' in data_input:
                try:
                    config['default_image_limit'] = max(0, min(100, int(data_input['default_image_limit'])))
                except (ValueError, TypeError):
                    pass
            if 'default_draw_limit' in data_input:
                try:
                    config['default_draw_limit'] = max(0, min(100, int(data_input['default_draw_limit'])))
                except (ValueError, TypeError):
                    pass
            if 'persona' in data_input:
                p = str(data_input['persona']).strip()
                if p in ['cute_cat', 'normal', 'engineer', 'catgirl']:
                    config['persona'] = p
            notice_msg = ""
            if 'daily_limit' in data_input:
                new_limit = min(max(200, int(data_input['daily_limit'])), 3000)
                config['daily_limit'] = new_limit
                if "limit_request" in config:
                    del config["limit_request"]
            
            self._atomic_json_write(file_path, config, indent=2)
            
            return web.json_response({'success': True, 'config': config, 'notice': notice_msg})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def api_update_ai_roles(self, request):
        """API：更新身分組每日文字與圖片配額"""
        session = await get_session(request)
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            data_input = await request.json()
            role_limits = data_input.get('role_limits', {})
            image_role_limits = data_input.get('image_role_limits', {})
            
            file_path = f'./data/{guild_id}/ai_chat.json'
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {"enabled": True, "role_limits": {}, "image_role_limits": {}, "banned_users": {}}
            
            clean_limits = {}
            for role_id, limit in role_limits.items():
                try:
                    limit_int = int(limit)
                    if limit_int != -1:
                        limit_int = min(max(20, limit_int), 500)
                    clean_limits[str(role_id)] = limit_int
                except ValueError:
                    continue

            clean_img_limits = {}
            for role_id, limit in image_role_limits.items():
                try:
                    limit_int = int(limit)
                    if limit_int != -1:
                        limit_int = max(0, min(100, limit_int))
                    clean_img_limits[str(role_id)] = limit_int
                except ValueError:
                    continue
            
            config['role_limits'] = clean_limits
            config['image_role_limits'] = clean_img_limits
            self._atomic_json_write(file_path, config, indent=2)
            
            return web.json_response({
                'success': True,
                'role_limits': clean_limits,
                'image_role_limits': clean_img_limits
            })
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def api_ai_ban_user(self, request):
        """API：封禁特定用戶在伺服器使用 AI 聊天"""
        session = await get_session(request)
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            data_input = await request.json()
            user_id = str(data_input.get('user_id', '')).strip()
            reason = str(data_input.get('reason', '網頁控制台封禁')).strip()
            
            if not user_id:
                return web.json_response({'error': '請輸入用戶 ID'}, status=400)
            
            file_path = f'./data/{guild_id}/ai_chat.json'
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {"enabled": True, "role_limits": {}, "banned_users": {}}
            
            banned_users = config.get('banned_users', {})
            user_name = user_id
            guild = self.bot.get_guild(int(guild_id))
            if guild:
                member = guild.get_member(int(user_id))
                if member:
                    user_name = str(member)
            
            banned_users[user_id] = {
                "name": user_name,
                "reason": reason,
                "banned_at": datetime.now().isoformat(),
                "banned_by": session.get('user', {}).get('username', 'WebAdmin')
            }
            config['banned_users'] = banned_users
            
            self._atomic_json_write(file_path, config, indent=2)
            
            # 清空該用戶記憶
            mem_path = f'./data/{guild_id}/ai-memory/{user_id}.json'
            if os.path.exists(mem_path):
                try:
                    os.remove(mem_path)
                except Exception:
                    pass
            
            return web.json_response({'success': True, 'banned_users': banned_users})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def api_ai_unban_user(self, request):
        """API：解封特定用戶"""
        session = await get_session(request)
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            user_id = request.match_info.get('user_id')
            if not user_id and request.can_read_body:
                try:
                    body = await request.json()
                    user_id = body.get('user_id')
                except Exception:
                    pass

            if not user_id:
                return web.json_response({'error': 'Missing user_id'}, status=400)

            user_id_raw = urllib.parse.unquote(str(user_id)).strip()
            user_id_clean = re.sub(r"[<@!>]", "", user_id_raw).strip()
            snowflakes = re.findall(r"\b\d{17,20}\b", user_id_raw)
            if snowflakes:
                user_id_clean = snowflakes[0]

            file_path = f'./data/{guild_id}/ai_chat.json'
            deleted = False
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                banned_users = config.get('banned_users', {})
                keys_to_del = [k for k in list(banned_users.keys()) if str(k).strip() == user_id_clean or (user_id_clean.isdigit() and str(k).strip() == str(int(user_id_clean)))]
                for k in keys_to_del:
                    del banned_users[k]
                    deleted = True
                
                config['banned_users'] = banned_users
                self._atomic_json_write(file_path, config, indent=2)
            
            return web.json_response({'success': True, 'deleted': deleted, 'user_id': user_id_clean})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def api_clear_ai_memory(self, request):
        """API：清空特定用戶的 AI 對話記憶"""
        session = await get_session(request)
        if not session.get('user'):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        guild_id = request.match_info.get('guild_id')
        if not await self.check_guild_permission(session.get('user')['id'], guild_id, session.get('access_token')):
            return web.json_response({'error': 'Forbidden'}, status=403)
        
        try:
            user_id = request.match_info.get('user_id')
            mem_path = f'./data/{guild_id}/ai-memory/{user_id}.json'
            cleared = False
            if os.path.exists(mem_path):
                try:
                    os.remove(mem_path)
                    cleared = True
                except Exception:
                    pass
            
            return web.json_response({'success': True, 'cleared': cleared})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def start(self):
        """啟動 Web 伺服器"""
        runner = web.AppRunner(self.app)
        await runner.setup()

        ssl_context = None
        if self.ssl_cert and self.ssl_key:
            if os.path.exists(self.ssl_cert) and os.path.exists(self.ssl_key):
                try:
                    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                    ssl_context.load_cert_chain(self.ssl_cert, self.ssl_key)
                    print(f'🔒 SSL/TLS 憑證載入成功: {self.ssl_cert}')
                except Exception as e:
                    print(f'⚠️ SSL/TLS 憑證載入失敗，以 HTTP 模式啟動: {e}')
                    ssl_context = None
            else:
                print('⚠️ 找不到 SSL 憑證或密鑰檔案，以 HTTP 模式啟動')

        if not ssl_context:
            site = web.TCPSite(runner, self.host, self.port)
            await site.start()
            print(f'🌐 網頁控制台已啟動: http://{self.host}:{self.port}')
            print(f'   本地訪問: http://localhost:{self.port}')
            if self.dev_ids:
                print(f'👨‍💻 開發者面板: http://localhost:{self.port}/dev-panel')
            return

        # 若啟用 SSL，以隨機端口在本地啟動 aiohttp HTTPS 站點
        internal_site = web.TCPSite(runner, '127.0.0.1', 0, ssl_context=ssl_context)
        await internal_site.start()
        internal_port = internal_site.port

        # 在對外端口啟動智慧分流分發器：
        # - 若為 TLS 握手 (首字節 0x16)，直接雙向轉發至內部 HTTPS 站點
        # - 若為純 HTTP 請求，自動回覆 301 重新導向至 HTTPS，避免 ERR_EMPTY_RESPONSE
        async def handle_client(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter):
            upstream_writer = None
            try:
                initial_data = await asyncio.wait_for(client_reader.read(4096), timeout=10.0)
                if not initial_data:
                    client_writer.close()
                    await client_writer.wait_closed()
                    return

                if initial_data[0] == 0x16:
                    # TLS ClientHello -> 轉發至本地 HTTPS 站點
                    upstream_reader, upstream_writer = await asyncio.open_connection('127.0.0.1', internal_port)
                    upstream_writer.write(initial_data)
                    await upstream_writer.drain()

                    async def forward(r, w):
                        try:
                            while True:
                                chunk = await r.read(65536)
                                if not chunk:
                                    break
                                w.write(chunk)
                                await w.drain()
                        except Exception:
                            pass
                        finally:
                            try:
                                if not w.is_closing():
                                    w.close()
                                    await w.wait_closed()
                            except Exception:
                                pass

                    await asyncio.gather(
                        forward(client_reader, upstream_writer),
                        forward(upstream_reader, client_writer),
                        return_exceptions=True
                    )
                else:
                    # 純 HTTP 請求 -> 301 重新導向至 HTTPS
                    text = initial_data.decode('latin1', 'ignore')
                    lines = text.split('\r\n')
                    path = '/'
                    host = f'curl.cat6666.me:{self.port}'
                    if lines and lines[0]:
                        parts = lines[0].split(' ')
                        if len(parts) >= 2:
                            path = parts[1]
                    for line in lines[1:]:
                        if line.lower().startswith('host:'):
                            h = line[5:].strip()
                            if h:
                                host = h
                            break

                    redirect_url = f"https://{host}{path}"
                    body = (
                        f"<!DOCTYPE html><html><head><title>301 Moved Permanently</title></head>"
                        f"<body><h1>301 Moved Permanently</h1>"
                        f"<p>The document has moved to <a href=\"{redirect_url}\">{redirect_url}</a>.</p></body></html>\r\n"
                    ).encode('utf-8')

                    resp = (
                        f"HTTP/1.1 301 Moved Permanently\r\n"
                        f"Location: {redirect_url}\r\n"
                        f"Content-Type: text/html; charset=utf-8\r\n"
                        f"Content-Length: {len(body)}\r\n"
                        f"Connection: close\r\n\r\n"
                    ).encode('utf-8') + body

                    client_writer.write(resp)
                    await client_writer.drain()
            except Exception:
                pass
            finally:
                try:
                    if not client_writer.is_closing():
                        client_writer.close()
                        await client_writer.wait_closed()
                except Exception:
                    pass
                if upstream_writer and not upstream_writer.is_closing():
                    try:
                        upstream_writer.close()
                        await upstream_writer.wait_closed()
                    except Exception:
                        pass

        self.server = await asyncio.start_server(handle_client, self.host, self.port)
        print(f'🔒 SSL/TLS 智慧分流已啟動 (HTTPS 支援 & HTTP 自動跳轉): {self.host}:{self.port}')
        print(f'🌐 網頁控制台 (HTTPS): https://{self.host}:{self.port}')
        print(f'   本地訪問: https://localhost:{self.port}')
        if self.dev_ids:
            print(f'👨‍💻 開發者面板: https://localhost:{self.port}/dev-panel')
