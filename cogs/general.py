import discord
from discord import app_commands
from discord.ext import commands
from discord import ui
import psutil
import platform

class HelpSelect(ui.Select):
    """幫助選單下拉菜單"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="主頁",
                description="返回幫助主頁",
                emoji="🏠",
                value="home"
            ),
            discord.SelectOption(
                label="一般指令",
                description="查看一般功能指令",
                emoji="📌",
                value="general"
            ),
            discord.SelectOption(
                label="管理指令",
                description="查看管理功能指令",
                emoji="🛡️",
                value="moderation"
            ),
            discord.SelectOption(
                label="娛樂指令",
                description="查看娛樂功能指令",
                emoji="🎮",
                value="fun"
            ),
            discord.SelectOption(
                label="伺服器指令",
                description="查看伺服器相關指令",
                emoji="🏰",
                value="server"
            ),
            discord.SelectOption(
                label="工具指令",
                description="查看實用工具指令",
                emoji="🔧",
                value="utility"
            ),
            discord.SelectOption(
                label="等級系統",
                description="查看等級系統指令",
                emoji="⭐",
                value="leveling"
            ),
            discord.SelectOption(
                label="歡迎系統",
                description="查看歡迎系統指令",
                emoji="👋",
                value="welcome"
            ),
            discord.SelectOption(
                label="反應角色",
                description="查看反應角色指令",
                emoji="👆",
                value="reaction"
            ),
            discord.SelectOption(
                label="簽到系統",
                description="查看簽到系統指令",
                emoji="📅",
                value="daily"
            ),
            discord.SelectOption(
                label="生日系統",
                description="查看生日系統指令",
                emoji="🎂",
                value="birthday"
            ),
            discord.SelectOption(
                label="遊戲系統",
                description="查看遊戲系統指令",
                emoji="🎯",
                value="games"
            ),
            discord.SelectOption(
                label="統計分析",
                description="查看統計分析指令",
                emoji="📊",
                value="statistics"
            ),
            discord.SelectOption(
                label="自定義命令",
                description="查看自定義命令指令",
                emoji="📝",
                value="custom"
            ),
            discord.SelectOption(
                label="臨時語音",
                description="查看臨時語音系統指令",
                emoji="🎤",
                value="tempvoice"
            ),
            discord.SelectOption(
                label="個人資料",
                description="查看個人資料卡片指令",
                emoji="📋",
                value="profile"
            ),
            discord.SelectOption(
                label="成就系統",
                description="查看成就系統指令",
                emoji="🏆",
                value="achievements"
            ),
            discord.SelectOption(
                label="AI 聊天",
                description="查看 AI 智慧對話指令",
                emoji="🤖",
                value="ai_chat"
            ),
            discord.SelectOption(
                label="抽獎系統",
                description="查看伺服器抽獎活動指令",
                emoji="🎁",
                value="giveaway"
            ),
        ]
        super().__init__(
            placeholder="選擇要查看的指令分類...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """處理選單選擇"""
        embed = discord.Embed(
            color=discord.Color.from_rgb(37, 99, 235),
            timestamp=discord.utils.utcnow()
        )
        
        if self.values[0] == "home":
            embed.title = "📚 指令幫助"
            embed.description = (
                "歡迎使用機器人幫助系統！\n\n"
                "使用下方選單選擇要查看的指令分類\n"
                "所有指令都以 `/` 開頭\n\n"
                "**可用分類：**\n"
                "📌 一般指令\n"
                "🛡️ 管理指令\n"
                "🎮 娛樂指令\n"
                "🏰 伺服器指令\n"
                "🔧 工具指令\n"
                "⭐ 等級系統\n"
                "👋 歡迎系統\n"
                "👆 反應角色\n"
                "📅 簽到系統\n"
                "🎂 生日系統\n"
                "🎯 遊戲系統\n"
                "📊 統計分析\n"
                "📝 自定義命令\n"
                "🎤 臨時語音\n"
                "📋 個人資料\n"
                "🏆 成就系統\n"
                "🤖 AI 聊天\n"
                "🎁 抽獎系統"
            )
            embed.set_footer(text="此在 Github 中開源")
            
        elif self.values[0] == "general":
            embed.title = "📌 一般指令"
            embed.description = "基本功能指令"
            embed.add_field(
                name="指令列表",
                value=(
                    "`/一般 延遲檢查` - 檢查機器人延遲\n"
                    "`/一般 打招呼` - 打個招呼\n"
                    "`/一般 查看用戶資訊` - 查看用戶詳細資訊\n"
                    "`/一般 機器人信息` - 查看機器人系統資訊\n"
                    "`/一般 幫助` - 顯示此幫助訊息"
                ),
                inline=False
            )
            
        elif self.values[0] == "moderation":
            embed.title = "🛡️ 管理指令"
            embed.description = "伺服器管理功能（需要相應權限）"
            embed.add_field(
                name="基礎管理",
                value=(
                    "`/管理 踢出用戶` - 踢出指定用戶\n"
                    "`/管理 封禁用戶` - 封禁指定用戶\n"
                    "`/管理 清除消息` - 清除指定數量的消息"
                ),
                inline=False
            )
            embed.add_field(
                name="⚠️ 警告系統",
                value=(
                    "`/管理 警告 [用戶] [理由]` - 警告用戶\n"
                    "`/管理 取消警告 [用戶]` - 取消最近一次警告\n"
                    "`/管理 警告記錄 [用戶]` - 查看警告歷史\n"
                    "`/管理 清除警告 [用戶]` - 清除所有警告"
                ),
                inline=False
            )
            embed.add_field(
                name="自動處罰規則",
                value="• 3次警告 = 自動踢出\n• 5次警告 = 自動封禁",
                inline=False
            )
            
        elif self.values[0] == "fun":
            embed.title = "🎮 娛樂指令"
            embed.description = "趣味互動指令"
            embed.add_field(
                name="指令列表",
                value=(
                    "`/娛樂 擲骰子` - 擲一個骰子 (1-6)\n"
                    "`/娛樂 拋硬幣` - 拋硬幣 (正面/反面)\n"
                    "`/娛樂 8ball` - 問一個問題，獲得隨機答案\n"
                    "`/娛樂 選擇` - 從多個選項中隨機選擇"
                ),
                inline=False
            )
            
        elif self.values[0] == "server":
            embed.title = "🏰 伺服器指令"
            embed.description = "伺服器資訊查詢"
            embed.add_field(
                name="指令列表",
                value=(
                    "`/伺服器 資訊` - 查看伺服器詳細資訊\n"
                    "`/伺服器 圖標` - 顯示伺服器圖標\n"
                    "`/伺服器 統計` - 查看伺服器統計數據\n"
                    "`/伺服器 身分組列表` - 查看所有身分組"
                ),
                inline=False
            )
            
        elif self.values[0] == "utility":
            embed.title = "🔧 工具指令"
            embed.description = "實用工具指令"
            embed.add_field(
                name="指令列表",
                value=(
                    "`/工具 頭像` - 查看用戶頭像\n"
                    "`/工具 計算機` - 進行數學計算\n"
                    "`/工具 投票` - 創建投票\n"
                    "`/工具 提醒` - 設定提醒\n"
                    "`/工具 翻譯` - 翻譯文字\n"
                    "`/工具 縮短網址` - 縮短長網址\n"
                    "`/工具 二維碼` - 生成QR碼\n"
                    "`/工具 天氣` - 查看天氣資訊"
                ),
                inline=False
            )
            
        elif self.values[0] == "leveling":
            embed.title = "⭐ 等級系統"
            embed.description = "用戶等級與經驗系統"
            embed.add_field(
                name="指令列表",
                value=(
                    "`/等級 查看` - 查看自己或其他用戶的等級\n"
                    "`/等級 排行榜` - 查看等級排行榜\n"
                    "`/等級 重置` - 重置用戶等級 (需要管理權限)"
                ),
                inline=False
            )
            embed.add_field(
                name="📊 如何獲得經驗",
                value="發送消息自動獲得 15-25 經驗（60秒冷卻）",
                inline=False
            )
            
        elif self.values[0] == "welcome":
            embed.title = "👋 歡迎系統"
            embed.description = "自動歡迎新成員與離開提醒"
            embed.add_field(
                name="設定指令（需要管理員權限）",
                value=(
                    "`/歡迎系統 設定歡迎頻道` - 設定歡迎訊息頻道\n"
                    "`/歡迎系統 設定歡迎訊息` - 自訂歡迎訊息\n"
                    "`/歡迎系統 設定離開頻道` - 設定離開訊息頻道\n"
                    "`/歡迎系統 設定離開訊息` - 自訂離開訊息\n"
                    "`/歡迎系統 開關` - 開啟或關閉系統\n"
                    "`/歡迎系統 查看設定` - 查看當前設定"
                ),
                inline=False
            )
            embed.add_field(
                name="💡 提示",
                value="訊息可使用 `{user}` 代表用戶，`{server}` 代表伺服器名稱",
                inline=False
            )
            
        elif self.values[0] == "reaction":
            embed.title = "👆 反應角色系統"
            embed.description = "點擊表情符號自動獲取身分組"
            embed.add_field(
                name="指令列表（需要管理員權限）",
                value=(
                    "`/反應角色 創建` - 創建反應角色訊息\n"
                    "`/反應角色 添加` - 為訊息添加反應角色\n"
                    "`/反應角色 移除` - 移除反應角色\n"
                    "`/反應角色 列表` - 查看所有反應角色訊息"
                ),
                inline=False
            )
            
        elif self.values[0] == "daily":
            embed.title = "📅 簽到系統"
            embed.description = "每日簽到獲取積分獎勵"
            embed.add_field(
                name="指令列表",
                value=(
                    "`/簽到 打卡` - 每日簽到獲取積分\n"
                    "`/簽到 查看` - 查看簽到資訊\n"
                    "`/簽到 排行榜` - 查看簽到積分排行榜\n"
                    "`/簽到 重置` - 重置用戶簽到數據（管理員）"
                ),
                inline=False
            )
            embed.add_field(
                name="🎁 獎勵機制",
                value=(
                    "基礎獎勵：50-100 積分\n"
                    "連續簽到：每天額外 +5 積分（最多 +100）"
                ),
                inline=False
            )
            
        elif self.values[0] == "birthday":
            embed.title = "🎂 生日系統"
            embed.description = "記錄生日並自動發送祝福"
            embed.add_field(
                name="用戶指令",
                value=(
                    "`/生日 設定` - 設定你的生日\n"
                    "`/生日 查看` - 查看生日\n"
                    "`/生日 列表` - 查看本月壽星\n"
                    "`/生日 刪除` - 刪除你的生日"
                ),
                inline=False
            )
            embed.add_field(
                name="管理員指令",
                value=(
                    "`/生日 設定頻道` - 設定生日提醒頻道\n"
                    "`/生日 開關` - 開啟或關閉生日提醒"
                ),
                inline=False
            )
        
        elif self.values[0] == "games":
            embed.title = "🎯 遊戲系統"
            embed.description = "與機器人玩小遊戲並累積積分"
            embed.add_field(
                name="可用遊戲",
                value=(
                    "`/遊戲 猜數字` - 猜數字遊戲（7次機會）\n"
                    "`/遊戲 猜拳` - 和機器人猜拳\n"
                    "`/遊戲 21點` - 21點撲克遊戲"
                ),
                inline=False
            )
            embed.add_field(
                name="統計指令",
                value=(
                    "`/遊戲 統計` - 查看你的遊戲統計\n"
                    "`/遊戲 排行榜` - 查看伺服器排行榜"
                ),
                inline=False
            )
            embed.add_field(
                name="獎勵",
                value="勝利：+10 XP +5 積分 | 失敗：+3 XP +1 積分",
                inline=False
            )
        
        elif self.values[0] == "statistics":
            embed.title = "📊 統計分析"
            embed.description = "查看伺服器活躍度分析"
            embed.add_field(
                name="可用指令",
                value=(
                    "`/統計 活躍度` - 查看伺服器整體活躍度\n"
                    "`/統計 熱門頻道` - 查看最活躍的頻道\n"
                    "`/統計 我的統計` - 查看你的個人統計\n"
                    "`/統計 活躍排行` - 查看活躍用戶排行榜\n"
                    "`/統計 時段分析` - 查看各時段活躍度"
                ),
                inline=False
            )
            embed.add_field(
                name="追蹤內容",
                value="訊息數量、頻道活躍度、用戶活動、時段分布",
                inline=False
            )
        
        elif self.values[0] == "custom":
            embed.title = "📝 自定義命令系統"
            embed.description = "創建簡單的文字回覆命令"
            embed.add_field(
                name="管理員指令",
                value=(
                    "`/自定義 添加` - 添加新的自定義命令\n"
                    "`/自定義 編輯` - 編輯現有命令\n"
                    "`/自定義 刪除` - 刪除命令\n"
                    "`/自定義 列表` - 查看所有自定義命令"
                ),
                inline=False
            )
            embed.add_field(
                name="使用方式",
                value="在聊天中輸入 `!命令名稱` 觸發自定義命令",
                inline=False
            )
            embed.add_field(
                name="網頁管理",
                value="可在網頁控制台直接創建和管理命令",
                inline=False
            )
        
        elif self.values[0] == "tempvoice":
            embed.title = "🎤 臨時語音頻道系統"
            embed.description = "自動創建和管理臨時語音頻道"
            embed.add_field(
                name="管理員指令",
                value=(
                    "`/臨時語音 設定` - 設定觸發頻道和分類\n"
                    "`/臨時語音 停用` - 停用系統\n"
                    "`/臨時語音 狀態` - 查看系統狀態"
                ),
                inline=False
            )
            embed.add_field(
                name="用戶指令",
                value=(
                    "`/臨時語音 限制人數` - 設定頻道人數上限\n"
                    "`/臨時語音 重命名` - 重命名你的臨時頻道"
                ),
                inline=False
            )
            embed.add_field(
                name="使用方式",
                value=(
                    "1. 加入設定的觸發頻道\n"
                    "2. 系統自動創建專屬語音頻道\n"
                    "3. 所有人離開後自動刪除"
                ),
                inline=False
            )
            embed.add_field(
                name="網頁管理",
                value="可在網頁控制台配置觸發頻道和頻道名稱格式",
                inline=False
            )
        
        elif self.values[0] == "profile":
            embed.title = "📋 個人資料卡片系統"
            embed.description = "自定義並展示你的個人資料"
            embed.add_field(
                name="指令列表",
                value=(
                    "`/個人資料 查看` - 查看個人資料卡片\n"
                    "`/個人資料 設定簡介` - 設定個人簡介（最多100字）\n"
                    "`/個人資料 設定標題` - 設定個人標題（最多30字）\n"
                    "`/個人資料 設定顏色` - 設定資料卡顏色（十六進位）\n"
                    "`/個人資料 清除` - 清除自定義設定"
                ),
                inline=False
            )
            embed.add_field(
                name="卡片內容",
                value=(
                    "• 等級和經驗值\n"
                    "• 活躍統計（訊息數、簽到）\n"
                    "• 遊戲統計和勝率\n"
                    "• 已解鎖成就數量\n"
                    "• 自定義簡介和標題"
                ),
                inline=False
            )
        
        elif self.values[0] == "achievements":
            embed.title = "🏆 成就系統"
            embed.description = "完成任務解鎖成就和獎勵"
            embed.add_field(
                name="指令列表",
                value=(
                    "`/成就 列表` - 查看所有可用成就\n"
                    "`/成就 我的成就` - 查看已解鎖的成就\n"
                    "`/成就 進度` - 查看成就進度統計"
                ),
                inline=False
            )
            embed.add_field(
                name="成就類型",
                value=(
                    "⚪ **普通**：基礎成就\n"
                    "🔵 **稀有**：進階成就\n"
                    "🟣 **史詩**：困難成就\n"
                    "🟡 **傳奇**：極難成就"
                ),
                inline=False
            )
            embed.add_field(
                name="成就分類",
                value=(
                    "📝 訊息成就\n"
                    "⭐ 等級成就\n"
                    "🎮 遊戲成就\n"
                    "📅 簽到成就\n"
                    "🌟 特殊成就"
                ),
                inline=False
            )
        
        elif self.values[0] == "ai_chat":
            embed.title = "🤖 AI 聊天系統"
            embed.description = "整合 OpenRouter (Gemini 3.7 / Claude / Kimi / OpenAI / Qwen / Grok) 與 DeepSeek (V3 / R1)，支援多輪智慧對話、圖片辨識分析、記憶管理與模型自由切換"
            embed.add_field(
                name="對話觸發方式",
                value=(
                    "• 在伺服器任意文字頻道 **@機器人 [你的問題/附帶圖片]**\n"
                    "• 直接回覆機器人的訊息進行多輪互動（亦支援附加圖片）\n"
                    "• 使用 `/ai 聊天 [訊息] [圖片]` 斜線指令"
                ),
                inline=False
            )
            embed.add_field(
                name="一般成員指令",
                value=(
                    "`/ai 聊天` - 發送訊息或圖片與 AI 進行對話/辨識\n"
                    "`/ai 模型` (`/模型`) - 切換個人偏好或全服預設 AI 模型（亦可在對話中直接說「換成gemini 3.7」、「換成claude」、「換成kimi」、「換成grok」等）\n"
                    "`/ai 人設` (`/人設`) - 切換個人或全服 AI 說話風格與人設\n"
                    "`/ai 瀏覽器` (`/瀏覽器`) - 召喚瀏覽器代理人深入分析網頁\n"
                    "`/ai 搜尋` (`/搜尋`) - 互聯網即時聯網檢索與總結\n"
                    "`/ai 清空記憶` - 清空個人與 AI 的對話上下文紀錄\n"
                    "`/ai 額度` - 查看目前生效模型、全服今日用量與個人剩餘額度"
                ),
                inline=False
            )
            embed.add_field(
                name="管理員專用指令",
                value=(
                    "`/ai 管理 開啟` - 開啟本伺服器的 AI 聊天功能\n"
                    "`/ai 管理 關閉` - 關閉本伺服器的 AI 聊天功能\n"
                    "`/ai 管理 設定提示詞` - 新增伺服器專屬 prompt (累加不覆蓋，存於 server-memory.db)\n"
                    "`/ai 管理 查看提示詞` - 查看本伺服器所有已設定 prompt (含編號)\n"
                    "`/ai 管理 刪除提示詞` - 刪除指定編號的自訂 prompt\n"
                    "`/ai 管理 清除提示詞` - 清空所有自訂 prompt 恢復開發者預設人設\n"
                    "`/ai 管理 清空用戶記憶` - 清空指定成員的對話紀錄\n"
                    "`/ai 管理 封禁用戶` - 禁止指定成員使用本服 AI 功能\n"
                    "`/ai 管理 解封用戶` - 解除成員的 AI 聊天封禁\n"
                    "`/ai 管理 伺服器上限` - 設定每日全服上限 (範圍 200-2000 條，預設 500 條)"
                ),
                inline=False
            )
            embed.add_field(
                name="開發者專用指令",
                value=(
                    "`/ai 開發者 寫入記憶` - 寫入持久背景記憶至 bot-memory.db\n"
                    "`/ai 開發者 查看記憶` - 查看已記錄之全域核心記憶\n"
                    "`/ai 開發者 刪除記憶` - 刪除指定主題核心記憶\n"
                    "`/ai 開發者 清空記憶庫` - 清空所有核心記憶庫\n"
                    "`/ai 開發者 待審批上限` - 查看待審批的伺服器上限提升申請\n"
                    "`/ai 開發者 審核上限` - 批准或駁回上限申請 (可自訂額度)\n"
                    "`/ai 開發者 設定群上限` - 直接指定伺服器每日上限 (範圍 200-2000 條)"
                ),
                inline=False
            )
            embed.add_field(
                name="Web 控制台設定",
                value="伺服器管理員可前往 Web 控制台自訂各身分組配額、系統提示詞及黑名單。",
                inline=False
            )
            
        elif self.values[0] == "giveaway":
            embed.title = "🎁 抽獎系統"
            embed.description = "伺服器福利與抽獎活動管理，支援動態倒數、按鈕一鍵參加與自動開獎"
            embed.add_field(
                name="抽獎指令清單 (管理權限)",
                value=(
                    "`/抽獎 發起` - 發起新抽獎 (可設定獎品、時長、名額、門檻身分組/等級/今日發言數與說明)\n"
                    "`/抽獎 結束` - 提前手動結束指定抽獎並立即抽出得主\n"
                    "`/抽獎 重抽` - 為已結束的抽獎重新抽選 1 位或多位新得獎者\n"
                    "`/抽獎 取消` - 取消進行中的抽獎活動 (不開獎)\n"
                    "`/抽獎 列表` - 查看本伺服器目前進行中的所有抽獎清單"
                ),
                inline=False
            )
            embed.add_field(
                name="多樣化參加門檻 (發起時選填)",
                value=(
                    "• **資格身分組**：限定持有特定身分組之成員才能參加\n"
                    "• **最低等級**：需達到指定等級門檻 (例如: Lv.5)\n"
                    "• **今日發言要求**：當天在伺服器發言需達指定句數 (例如: 3 句)\n"
                    "• **歷史發言要求**：累積總發言需達到指定句數"
                ),
                inline=False
            )
            embed.add_field(
                name="時長格式範例",
                value="• `30s` (30秒) • `10m` (10分鐘) • `2h` (2小時) • `1d` (1天) • `1w` (1週)",
                inline=False
            )
            embed.add_field(
                name="互動特色",
                value="成員點擊卡片下方的 **「🎉 參加抽獎」** 按鈕系統將自動驗證所有門檻，資格不符者將清楚私密提示不足之處；亦可點擊 **「👥 參加名單」** 查看成員。重啟後按鈕依然有效！",
                inline=False
            )
        
        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpView(ui.View):
    """幫助視圖"""
    
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(HelpSelect())
    
    async def on_timeout(self):
        """超時處理"""
        for item in self.children:
            item.disabled = True

class General(commands.Cog):
    """通用指令"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # 創建指令組
    general_group = app_commands.Group(name="一般", description="一般功能指令")
    
    @general_group.command(name="延遲檢查", description="檢查機器人延遲")
    async def ping(self, interaction: discord.Interaction):
        """Ping指令 - 顯示機器人延遲"""
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f'🏓 Pong! 延遲: {latency}ms')
    
    @general_group.command(name="打招呼", description="打個招呼")
    async def hello(self, interaction: discord.Interaction):
        """Say hello"""
        await interaction.response.send_message(f'👋 你好, {interaction.user.mention}!')
    
    @general_group.command(name="查看用戶資訊", description="查看用戶資訊")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        """顯示用戶資訊"""
        member = member or interaction.user
        
        embed = discord.Embed(
            title=f"{member.name} 的資訊",
            color=member.color
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="📛 用戶名", value=str(member), inline=True)
        embed.add_field(name="🆔 ID", value=member.id, inline=True)
        embed.add_field(name="📅 加入時間", value=discord.utils.format_dt(member.joined_at, style='R'), inline=False)
        embed.add_field(name="📅 帳號創建時間", value=discord.utils.format_dt(member.created_at, style='R'), inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @general_group.command(name="機器人信息", description="查看機器人系統資訊")
    async def botinfo(self, interaction: discord.Interaction):
        """顯示機器人系統資訊"""
        # 獲取系統資訊
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        embed = discord.Embed(
            title="🤖 機器人系統資訊",
            color=discord.Color.blue(),
            description=f"**系統：** {platform.system()} {platform.release()}"
        )
        
        # CPU 使用率
        embed.add_field(
            name="💻 CPU 使用率",
            value=f"```{cpu_percent}%```",
            inline=True
        )
        
        # 記憶體使用率
        embed.add_field(
            name="🧠 記憶體使用率",
            value=f"```{memory.percent}%\n{memory.used / (1024**3):.2f}GB / {memory.total / (1024**3):.2f}GB```",
            inline=True
        )
        
        # 磁碟使用率
        embed.add_field(
            name="💾 儲存空間使用率",
            value=f"```{disk.percent}%\n{disk.used / (1024**3):.2f}GB / {disk.total / (1024**3):.2f}GB```",
            inline=True
        )
        
        # Python 版本
        embed.add_field(
            name="🐍 Python 版本",
            value=f"```{platform.python_version()}```",
            inline=True
        )
        
        # Discord.py 版本
        embed.add_field(
            name="📚 Discord.py 版本",
            value=f"```{discord.__version__}```",
            inline=True
        )
        
        # 伺服器數量
        embed.add_field(
            name="🌐 服務伺服器數",
            value=f"```{len(self.bot.guilds)}```",
            inline=True
        )
        
        # GitHub 開源資訊
        embed.add_field(
            name="\u200b",
            value="本機器人在 Github 上開源，[Github](https://github.com/catrix-dev/curl) 可點擊",
            inline=False
        )
        
        embed.set_footer(text=f"請求者：{interaction.user.name}")
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.response.send_message(embed=embed)
    
    @general_group.command(name="幫助", description="顯示所有可用指令")
    async def help(self, interaction: discord.Interaction):
        """顯示幫助資訊"""
        embed = discord.Embed(
            title="📚 指令幫助",
            description=(
                "歡迎使用機器人幫助系統！\n\n"
                "使用下方選單選擇要查看的指令分類\n"
                "所有指令都以 `/` 開頭\n\n"
                "**可用分類：**\n"
                "📌 一般指令\n"
                "🛡️ 管理指令\n"
                "🎮 娛樂指令\n"
                "🏰 伺服器指令\n"
                "🔧 工具指令\n"
                "⭐ 等級系統\n"
                "👋 歡迎系統\n"
                "👆 反應角色\n"
                "📅 簽到系統\n"
                "🎂 生日系統\n"
                "🎯 遊戲系統\n"
                "📊 統計分析\n"
                "📝 自定義命令\n"
                "🎤 臨時語音\n"
                "📋 個人資料\n"
                "🏆 成就系統"
            ),
            color=discord.Color.from_rgb(37, 99, 235),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="此在 Github 中開源")
        
        view = HelpView()
        await interaction.response.send_message(embed=embed, view=view)

    # ---------------- 頂層常用指令捷徑 (/help, /ping, /botinfo) ----------------

    @app_commands.command(name="help", description="顯示所有可用指令幫助手冊")
    async def top_help(self, interaction: discord.Interaction):
        """頂層斜線指令：/help"""
        await self.help.callback(self, interaction)

    @app_commands.command(name="幫助", description="顯示所有可用指令幫助手冊")
    async def top_help_zh(self, interaction: discord.Interaction):
        """頂層斜線指令：/幫助"""
        await self.help.callback(self, interaction)

    @app_commands.command(name="ping", description="檢查機器人當前延遲")
    async def top_ping(self, interaction: discord.Interaction):
        """頂層斜線指令：/ping"""
        await self.ping.callback(self, interaction)

    @app_commands.command(name="botinfo", description="查看機器人系統狀態與資訊")
    async def top_botinfo(self, interaction: discord.Interaction):
        """頂層斜線指令：/botinfo"""
        await self.botinfo.callback(self, interaction)

    # ---------------- 前綴指令 (!help, !ping) ----------------

    @commands.command(name="help", aliases=["幫助"])
    async def prefix_help(self, ctx: commands.Context):
        """前綴指令 !help"""
        embed = discord.Embed(
            title="📚 指令幫助",
            description=(
                "歡迎使用機器人幫助系統！\n\n"
                "使用下方選單選擇要查看的指令分類\n"
                "建議使用斜線指令 `/help` 獲得最佳體驗！\n\n"
                "**可用分類：**\n"
                "📌 一般指令 • 🛡️ 管理指令 • 🎮 娛樂指令\n"
                "🏰 伺服器指令 • 🔧 工具指令 • ⭐ 等級系統\n"
                "👋 歡迎系統 • 👆 反應角色 • 📅 簽到系統\n"
                "🎂 生日系統 • 🎯 遊戲系統 • 📊 統計分析\n"
                "📝 自定義命令 • 🎤 臨時語音 • 📋 個人資料"
            ),
            color=discord.Color.from_rgb(37, 99, 235),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="輸入 /help 查看完整互動功能")
        view = HelpView()
        await ctx.send(embed=embed, view=view)

    @commands.command(name="ping", aliases=["延遲"])
    async def prefix_ping(self, ctx: commands.Context):
        """前綴指令 !ping"""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f'🏓 Pong! 延遲: {latency}ms')
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'📦 {self.__class__.__name__} cog已載入')

async def setup(bot):
    await bot.add_cog(General(bot))
