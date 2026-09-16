import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re
from datetime import datetime

class AutoReply(commands.Cog):
    """自動回覆系統"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_folder = './data'
        self._rules_cache = {}  # {guild_id_str: rules_dict}
    
    def get_auto_reply_file(self, guild_id):
        """獲取自動回覆數據文件路徑"""
        return os.path.join(self.data_folder, str(guild_id), 'auto_reply.json')
    
    def load_auto_replies(self, guild_id):
        """載入自動回覆規則（優先記憶體快取，避免每條訊息讀盤）"""
        guild_id_str = str(guild_id)
        if guild_id_str in self._rules_cache:
            return self._rules_cache[guild_id_str]

        file_path = self.get_auto_reply_file(guild_id)
        
        if not os.path.exists(file_path):
            data = {
                'enabled': True,
                'rules': []
            }
            self._rules_cache[guild_id_str] = data
            return data
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._rules_cache[guild_id_str] = data
                return data
        except Exception:
            data = {
                'enabled': True,
                'rules': []
            }
            self._rules_cache[guild_id_str] = data
            return data
    
    def save_auto_replies(self, guild_id, data):
        """保存自動回覆規則（同步更新快取與原子寫入磁碟）"""
        guild_id_str = str(guild_id)
        self._rules_cache[guild_id_str] = data
        file_path = self.get_auto_reply_file(guild_id)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        tmp_file = file_path + f".tmp_{os.getpid()}"
        try:
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, file_path)
        except Exception:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass
            raise
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """監聽消息並觸發自動回覆"""
        # 忽略機器人自己的消息
        if message.author.bot:
            return
        
        # 忽略沒有 guild 的消息（私訊）
        if not message.guild:
            return
        
        # 載入自動回覆規則
        data = self.load_auto_replies(message.guild.id)
        
        # 檢查是否啟用
        if not data.get('enabled', True):
            return
        
        rules = data.get('rules', [])
        
        # 遍歷所有規則
        for rule in rules:
            # 檢查規則是否啟用
            if not rule.get('enabled', True):
                continue
            
            # 檢查頻道限制
            channel_ids = rule.get('channel_ids', [])
            if channel_ids and str(message.channel.id) not in channel_ids:
                continue
            
            # 檢查角色限制
            role_ids = rule.get('role_ids', [])
            if role_ids:
                user_role_ids = [str(role.id) for role in message.author.roles]
                if not any(role_id in user_role_ids for role_id in role_ids):
                    continue
            
            # 檢查匹配類型
            match_type = rule.get('match_type', 'contains')
            trigger = rule.get('trigger', '')
            message_content = message.content
            
            matched = False
            
            if match_type == 'exact':
                # 完全匹配
                matched = message_content == trigger
            elif match_type == 'contains':
                # 包含關鍵詞
                if rule.get('case_sensitive', False):
                    matched = trigger in message_content
                else:
                    matched = trigger.lower() in message_content.lower()
            elif match_type == 'starts_with':
                # 以...開頭
                if rule.get('case_sensitive', False):
                    matched = message_content.startswith(trigger)
                else:
                    matched = message_content.lower().startswith(trigger.lower())
            elif match_type == 'ends_with':
                # 以...結尾
                if rule.get('case_sensitive', False):
                    matched = message_content.endswith(trigger)
                else:
                    matched = message_content.lower().endswith(trigger.lower())
            elif match_type == 'regex':
                # 正則表達式防 ReDoS：限制長度並捕獲異常
                if len(trigger) > 200:
                    continue
                try:
                    flags = 0 if rule.get('case_sensitive', False) else re.IGNORECASE
                    matched = re.search(trigger, message_content[:1000], flags=flags) is not None
                except Exception:
                    continue
            
            if matched:
                # 獲取回覆內容
                reply_content = rule.get('reply', '')
                
                # 替換變量
                reply_content = reply_content.replace('{user}', message.author.mention)
                reply_content = reply_content.replace('{username}', message.author.name)
                reply_content = reply_content.replace('{server}', message.guild.name)
                reply_content = reply_content.replace('{channel}', message.channel.mention)
                
                # 發送回覆
                reply_type = rule.get('reply_type', 'message')
                
                try:
                    if reply_type == 'reply':
                        # 回覆消息
                        await message.reply(reply_content, mention_author=rule.get('mention_user', False))
                    elif reply_type == 'dm':
                        # 私訊用戶
                        try:
                            await message.author.send(reply_content)
                        except:
                            pass  # 無法發送私訊時忽略
                    elif reply_type == 'react':
                        # 添加反應
                        try:
                            await message.add_reaction(rule.get('reaction', '👍'))
                        except:
                            pass
                    else:
                        # 發送正常消息
                        await message.channel.send(reply_content)
                    
                    # 記錄觸發次數
                    rule['triggered_count'] = rule.get('triggered_count', 0) + 1
                    rule['last_triggered'] = datetime.now().isoformat()
                    self.save_auto_replies(message.guild.id, data)
                    
                    # 如果設定為只觸發一次，則停止
                    if rule.get('trigger_once', False):
                        break
                
                except Exception as e:
                    print(f"自動回覆錯誤: {e}")
                    continue
    
    # Slash Commands
    auto_reply = app_commands.Group(name="自動回覆", description="自動回覆系統管理")
    
    @auto_reply.command(name="添加", description="添加自動回覆規則")
    @app_commands.describe(
        觸發詞="觸發自動回覆的關鍵詞",
        回覆內容="自動回覆的內容",
        匹配類型="匹配方式：exact(完全匹配), contains(包含), starts_with(開頭), ends_with(結尾), regex(正則)",
        回覆類型="回覆方式：message(普通消息), reply(回覆), dm(私訊), react(反應)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_rule(self, interaction: discord.Interaction, 觸發詞: str, 回覆內容: str,
                       匹配類型: str = "contains", 回覆類型: str = "message"):
        """添加自動回覆規則"""
        
        # 驗證匹配類型
        valid_match_types = ['exact', 'contains', 'starts_with', 'ends_with', 'regex']
        if 匹配類型 not in valid_match_types:
            await interaction.response.send_message(
                f"❌ 無效的匹配類型！請使用: {', '.join(valid_match_types)}",
                ephemeral=True
            )
            return
        
        # 驗證回覆類型
        valid_reply_types = ['message', 'reply', 'dm', 'react']
        if 回覆類型 not in valid_reply_types:
            await interaction.response.send_message(
                f"❌ 無效的回覆類型！請使用: {', '.join(valid_reply_types)}",
                ephemeral=True
            )
            return
        
        if 匹配類型 == 'regex':
            if len(觸發詞) > 200:
                await interaction.response.send_message("❌ 正則表達式長度不能超過 200 字符", ephemeral=True)
                return
            try:
                re.compile(觸發詞)
            except re.error as err:
                await interaction.response.send_message(f"❌ 無效的正則表達式: {err}", ephemeral=True)
                return
        
        # 載入現有規則
        data = self.load_auto_replies(interaction.guild_id)
        
        # 創建新規則
        new_rule = {
            'id': len(data.get('rules', [])) + 1,
            'trigger': 觸發詞,
            'reply': 回覆內容,
            'match_type': 匹配類型,
            'reply_type': 回覆類型,
            'enabled': True,
            'case_sensitive': False,
            'mention_user': False,
            'trigger_once': False,
            'channel_ids': [],
            'role_ids': [],
            'triggered_count': 0,
            'created_at': datetime.now().isoformat(),
            'created_by': str(interaction.user.id)
        }
        
        # 添加規則
        if 'rules' not in data:
            data['rules'] = []
        data['rules'].append(new_rule)
        
        # 保存
        self.save_auto_replies(interaction.guild_id, data)
        
        embed = discord.Embed(
            title="✅ 自動回覆規則已添加",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="觸發詞", value=f"`{觸發詞}`", inline=False)
        embed.add_field(name="回覆內容", value=回覆內容[:100], inline=False)
        embed.add_field(name="匹配類型", value=匹配類型, inline=True)
        embed.add_field(name="回覆類型", value=回覆類型, inline=True)
        embed.add_field(name="規則 ID", value=f"#{new_rule['id']}", inline=True)
        embed.set_footer(text=f"創建者: {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)
    
    @auto_reply.command(name="列表", description="查看所有自動回覆規則")
    async def list_rules(self, interaction: discord.Interaction):
        """列表所有自動回覆規則"""
        data = self.load_auto_replies(interaction.guild_id)
        rules = data.get('rules', [])
        
        if not rules:
            await interaction.response.send_message("📋 目前沒有任何自動回覆規則", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📋 自動回覆規則列表",
            description=f"系統狀態: {'🟢 啟用' if data.get('enabled', True) else '🔴 停用'}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        for rule in rules[:10]:  # 最多顯示10條
            status = "🟢" if rule.get('enabled', True) else "🔴"
            value = f"**觸發詞:** `{rule['trigger']}`\n"
            value += f"**回覆:** {rule['reply'][:50]}{'...' if len(rule['reply']) > 50 else ''}\n"
            value += f"**匹配:** {rule.get('match_type', 'contains')} | **類型:** {rule.get('reply_type', 'message')}\n"
            value += f"**觸發次數:** {rule.get('triggered_count', 0)} 次"
            
            embed.add_field(
                name=f"{status} 規則 #{rule['id']}",
                value=value,
                inline=False
            )
        
        if len(rules) > 10:
            embed.set_footer(text=f"顯示 10/{len(rules)} 條規則，更多規則請前往網頁後台查看")
        
        await interaction.response.send_message(embed=embed)
    
    @auto_reply.command(name="刪除", description="刪除自動回覆規則")
    @app_commands.describe(規則id="要刪除的規則 ID")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def delete_rule(self, interaction: discord.Interaction, 規則id: int):
        """刪除自動回覆規則"""
        data = self.load_auto_replies(interaction.guild_id)
        rules = data.get('rules', [])
        
        # 查找規則
        rule_to_delete = None
        for i, rule in enumerate(rules):
            if rule['id'] == 規則id:
                rule_to_delete = rules.pop(i)
                break
        
        if not rule_to_delete:
            await interaction.response.send_message(f"❌ 找不到 ID 為 {規則id} 的規則", ephemeral=True)
            return
        
        # 保存
        self.save_auto_replies(interaction.guild_id, data)
        
        embed = discord.Embed(
            title="✅ 規則已刪除",
            description=f"已刪除規則 #{規則id}",
            color=discord.Color.red()
        )
        embed.add_field(name="觸發詞", value=f"`{rule_to_delete['trigger']}`", inline=True)
        embed.add_field(name="觸發次數", value=f"{rule_to_delete.get('triggered_count', 0)} 次", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @auto_reply.command(name="開關", description="開啟/關閉自動回覆系統")
    @app_commands.describe(啟用="開啟或關閉")
    @app_commands.checks.has_permissions(administrator=True)
    async def toggle_system(self, interaction: discord.Interaction, 啟用: bool):
        """開關自動回覆系統"""
        data = self.load_auto_replies(interaction.guild_id)
        data['enabled'] = 啟用
        self.save_auto_replies(interaction.guild_id, data)
        
        status = "🟢 已啟用" if 啟用 else "🔴 已停用"
        await interaction.response.send_message(f"{status} 自動回覆系統")
    
    @auto_reply.command(name="啟用規則", description="啟用/停用特定規則")
    @app_commands.describe(
        規則id="規則 ID",
        啟用="開啟或關閉"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def toggle_rule(self, interaction: discord.Interaction, 規則id: int, 啟用: bool):
        """啟用/停用特定規則"""
        data = self.load_auto_replies(interaction.guild_id)
        rules = data.get('rules', [])
        
        # 查找規則
        found = False
        for rule in rules:
            if rule['id'] == 規則id:
                rule['enabled'] = 啟用
                found = True
                break
        
        if not found:
            await interaction.response.send_message(f"❌ 找不到 ID 為 {規則id} 的規則", ephemeral=True)
            return
        
        # 保存
        self.save_auto_replies(interaction.guild_id, data)
        
        status = "🟢 已啟用" if 啟用 else "🔴 已停用"
        await interaction.response.send_message(f"{status} 規則 #{規則id}")
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'📦 {self.__class__.__name__} cog已載入')

async def setup(bot):
    await bot.add_cog(AutoReply(bot))
