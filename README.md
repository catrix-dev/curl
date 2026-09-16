# curl Discord Bot (v7.1.2)

<div align="center">

[![Version](https://img.shields.io/badge/version-v7.1.2-blue.svg)](https://github.com/catrix-dev/curl)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.0%2B-green.svg)](https://github.com/Rapptz/discord.py)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)
[![GitHub Repo](https://img.shields.io/badge/GitHub-catrix--dev%2Fcurl-black?logo=github)](https://github.com/catrix-dev/curl)

**一體化全功能現代 Discord 機器人**  
整合 AI 智慧對話、客服工單系統、抽獎活動、社群成就、自動回覆與網頁管理後台。

[📖 隱私政策](PRIVACY.md) • [🚀 快速開始](#安裝與配置步驟) • [💬 指令清單](#-指令完整清單)

</div>

---

## 🌟 核心特色 (v7.1.2)

- 🤖 **AI 智慧聊天系統**：
  - 支援多模型架構：Google Gemini 3.5 Flash Lite（極速 1.1s 響應）、Gemini 3.5 Flash、Gemini 3.8 Flash、OpenRouter 自動輪替、DeepSeek (V3-Chat / Reasoner)。
  - 4 大深度人設引擎：貓娘、可愛貓貓、頂級工程師、一般助理，具備跨人格切換全量記憶繼承與語氣重置隔離。
  - 支援圖片視覺辨識（Vision 多模態）、原生 Google Imagen 3 與 OpenRouter 繪圖生成、檔案分析、獨立頻道常駐免 @ 對話。
  - 獨立記憶庫機制：群體上下文對話記憶、全域持久記憶與專屬人設 Prompt 自訂。
  - 智慧頻率與防浪費安全保護：30 秒窗口超快速發送階梯處罰（>5則停30s、>3則停2m、>3則停10m、>3則停1h、第5次永久凍結須開發者解封），冷卻期直接拒絕回答，0 Token 浪費。
  - 每日 AI 呼叫額度配置、繪圖/生圖額度限制、黑名單封禁管理。
- 🎫 **專業客服工單系統 (Tickets)**：
  - 一鍵創建獨立工單頻道、支援自訂面板、邀請協作成員。
  - 工單關閉時自動生成完整 HTML Transcript 歷史對話備查。
- 🎁 **進階抽獎系統 (Giveaways)**：
  - 支援身分組門檻、發言次數限制。
  - 支援即時開獎、提早結案、自動重新抽選與名單公佈。
- 💬 **關鍵字自動回覆 (Auto Reply)**：
  - 支援完全符合、包含關鍵詞、正則表達式 (Regex) 匹配。
  - 支援普通訊息、回覆 (Reply)、私訊 (DM)、表情反應等多種模式。
- 🛡️ **安全防護與警告系統**：
  - 防刷屏、釣魚連結攔截、封禁名單管理。
  - 智慧累進警告懲罰（達上限自動執行踢出或封禁）。
- 📊 **社群互動與成就系統**：
  - 40+ 項成就自動追蹤與成就卡片展示。
  - 活躍度數據統計、每日簽到排行榜、生日定時祝福提醒。
- 🌐 **Web 控制台 (Dashboard)** (`web/`)：
  - 支援 Discord OAuth2 登入，即時監控機器人統計數據、查看用戶工單、管理伺服器配置與各模組設定。
- 🔄 **自動更新檢測**：
  - 內建與 `catrix-dev/curl` 倉庫比對版本，自動提醒更新。

---

## 📋 指令完整清單

### 🤖 AI 智慧對話系統 (`/ai`, `/ai 管理`)

#### 💬 對話與多模態分析
- `/ai 聊天 [問題] [公開回應] [圖片] [檔案]` - 與 AI 進行對話，支援附加圖片進行視覺解析，或上傳程式碼/文字檔案（.txt, .py, .json, .md 等，最大 2MB）進行深度分析
- `/ai 回答 [問題] [公開回應] [圖片] [檔案]` - 呼叫 AI 智慧回答（支援使用者個人安裝，在未邀請機器人的伺服器或個人私聊中亦可使用）
- `/ai 清空記憶` - 清空個人與 AI 的對話上下文歷史記憶
- `/ai 額度` / `/ai 狀態` - 查詢本伺服器 AI 每日呼叫配額用量、剩餘額度與重置倒數

#### 🎨 繪圖、搜尋與瀏覽器代理
- `/ai 繪圖 [提示詞] [風格] [寬高比] [公開回應] [參考圖]` - 使用 AI 生成藝術圖像（支援指定風格、1:1 / 16:9 / 9:16 等自訂比例與 Image-to-Image 參考圖）
- `/ai 搜尋 [查詢] [公開回應]` - 即時檢索網際網路最新資訊並由 AI 深度歸納總結
- `/ai 瀏覽器 [網址] [分析重點] [公開回應]` - 召喚網頁解析代理人，檢視並深度分析指定網頁內容
- 🖼️ **圖片右鍵創作**：對任一圖片訊息按右鍵「Apps」>「🎨 參考圖片修改創作」，即可彈窗輸入指令重繪圖片

#### ⚙️ 模型切換與人設風格
- `/ai 模型 [選擇] [範圍]` - 切換使用的 AI 核心引擎（支援 Gemini 3.7 Flash、Claude Sonnet 5、Kimi K2.5、GPT-4o、GPT-4o-mini、Qwen 2.5 72B、Grok 4.20、DeepSeek V3 / R1 等；範圍可選個人偏好或全服預設）
- `/ai 人設 [風格] [範圍]` - 切換 AI 說話風格（🐱 可愛貓貓、🤖 一般專業助手、💻 頂級架構師、🐾 貼心貓娘，或跟隨伺服器預設/重置）

#### 📢 頻道管理
- `/ai 設定頻道 [頻道]` - 設定專屬免 @ AI 對話頻道（在頻道內發送訊息即自動與 AI 互動）
- `/ai 移除頻道 [頻道]` - 將指定頻道從 AI 專屬清單中移除
- `/ai 專屬頻道清單` - 查看目前伺服器所有已啟用的 AI 專屬頻道
- `/ai 頻道記憶重置 [頻道]` - 清空指定頻道的群體對話記憶

#### 🛡️ 管理員專用指令 (`/ai 管理`)
- `/ai 管理 開啟` / `/ai 管理 關閉` - 啟用或停用本伺服器的 AI 聊天功能
- `/ai 管理 伺服器上限 [上限]` - 設定伺服器每日 AI 對話總額度 (200~2000 條)
- `/ai 管理 圖片額度 [身分組] [每日額度]` - 配置伺服器成員或指定身分組每日圖片解析次數
- `/ai 管理 繪圖額度 [身分組] [每日額度]` - 配置伺服器成員或指定身分組每日 AI 生圖額度
- `/ai 頻率狀態 [成員]` - 查看個人或成員當前 AI 頻率冷卻與超速違規狀態
- `/ai 管理 解封頻率 [用戶]` - [官方開發者專用] 解封因超快速刷屏被限制的用戶
- `/ai 管理 設定提示詞 [提示詞]` - 為伺服器自訂專屬系統 Prompt（累加儲存於資料庫）
- `/ai 管理 查看提示詞` / `/ai 管理 刪除提示詞 [編號]` / `/ai 管理 清除提示詞` - 管理自訂提示詞
- `/ai 管理 封禁用戶 [成員] [原因]` / `/ai 管理 解封用戶 [成員]` / `/ai 管理 封禁名單` - 黑名單管理
- `/ai 管理 清空用戶記憶 [成員]` - 管理員強制清空指定成員與 AI 的對話歷史


### 🎁 抽獎系統 (`/抽獎`)
- `/抽獎 發起` - 發起抽獎活動（自訂獎品、時間、中獎人數、身分組/發言次數門檻）
- `/抽獎 結束 [抽獎ID]` - 提早結束抽獎並立即抽選得獎者
- `/抽獎 重抽 [訊息ID]` - 重新抽選中獎者
- `/抽獎 取消 [訊息ID]` - 取消進行中的抽獎活動
- `/抽獎 列表` - 查看目前伺服器進行中的所有抽獎活動

### 💬 自動回覆 (`/自動回覆`)
- `/自動回覆 添加` - 新增自動回覆規則（支援包含、開頭、結尾、正則表達式）
- `/自動回覆 列表` - 查看伺服器內所有生效的自動回覆規則
- `/自動回覆 刪除 [規則ID]` - 刪除指定的自動回覆規則
- `/自動回覆 開關 [狀態]` - 啟用或停用自動回覆系統
- `/自動回覆 清除` - 清空伺服器所有自動回覆規則

### 🎫 客服工單 (`/工單`)
- `/工單 面板` - 在指定頻道發送工單創建面板
- `/工單 設定` - 配置工單分類、日誌記錄頻道與管理員身分組
- `/工單 開關` - 啟用或停用工單系統
- `/工單 添加 [成員]` - 添加成員至當前工單頻道
- `/工單 移除 [成員]` - 從當前工單頻道移除成員
- `/工單 列表` - 查看當前進行中的所有工單

### 🛡️ 伺服器管理 (`/管理`)
- `/管理 警告 [成員] [原因]` - 對成員發出警告
- `/管理 取消警告 [成員]` - 撤回成員最近一次的警告記錄
- `/管理 警告記錄 [成員]` - 查詢成員的警告歷史與累計次數
- `/管理 清除警告 [成員]` - 清空成員的所有警告記錄
- `/管理 踢出用戶 [成員]` - 將成員踢出伺服器
- `/管理 封鎖用戶 [成員]` - 封鎖指定成員
- `/管理 清除訊息 [數量]` - 批量清理頻道內的歷史訊息

### 👤 個人卡片與社交 (`/個人資料`, `/簽到`, `/生日`)
- `/個人資料 查看` - 查看個人特色個人檔案卡
- `/個人資料 設定簡介` / `設定標題` / `設定顏色` - 自訂卡片風格
- `/簽到 打卡` - 每日簽到領取點數與累積天數
- `/簽到 排行榜` - 查看伺服器簽到積分總排行
- `/生日 設定 [月] [日]` - 記錄個人生日資訊
- `/生日 列表` - 查看本月份過生日的成員清單

### 🏆 成就系統 (`/成就`)
- `/成就 我的成就` - 檢視個人已解鎖之榮譽成就
- `/成就 列表` - 瀏覽伺服器所有成就與獲取條件
- `/成就 進度` - 查詢當前各項成就的達成百分比

### 🎭 娛樂與小遊戲 (`/遊戲`, `/娛樂`, `/匿名`)
- `/遊戲 21點` - 經典 Blackjack 撲克對決
- `/遊戲 猜拳` - 剪刀石頭布對戰
- `/遊戲 猜數字` - 1-100 數字猜謎挑戰
- `/娛樂 投擲骰子` / `擲硬幣` / `魔法8球` / `幫你選擇` - 派對與隨機決策工具
- `/匿名 發言 [內容]` - 在授權頻道內以匿名身分發布訊息

### 🔧 實用工具與伺服器資訊 (`/工具`, `/伺服器`, `/一般`)
- `/工具 計算器 [表達式]` - 即時計算數學算式
- `/工具 倒數計時 [時間]` - 建立定時倒數器
- `/工具 投票 [標題] [選項...]` - 建立互動投票面板
- `/伺服器 資訊` / `成員統計` / `角色列表` - 伺服器概況
- `/一般 延遲檢查` / `機器人信息` - 系統運行指標

---

## 🛠️ 安裝與配置步驟

### 1. 克隆倉庫與安裝依賴

環境需求：**Python 3.10+**

```bash
git clone https://github.com/catrix-dev/curl.git
cd curl
pip install -r requirements.txt
```

### 2. 環境變數設定

複製 `.env.example` 為 `.env`：

```bash
cp .env.example .env
```

編輯 `.env` 並配置核心參數：

```env
# Discord 核心金鑰（必填）
DISCORD_TOKEN=你的_DISCORD_BOT_TOKEN
DEV_ID=你的_DISCORD_USER_ID
LOG_CHANNEL_ID=日誌頻道的_CHANNEL_ID

# 網頁後台與 OAuth2
WEB_PORT=8080
DISCORD_CLIENT_ID=你的_CLIENT_ID
DISCORD_CLIENT_SECRET=你的_CLIENT_SECRET
DISCORD_REDIRECT_URI=http://localhost:8080/callback
SESSION_SECRET=隨機產生的44位安全字串

# AI 服務供應商 (可選: openrouter / deepseek / gemini)
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=你的_OPENROUTER_API_KEY
OPENROUTER_MODEL=google/gemini-2.5-flash
OPENROUTER_MODELS=google/gemini-2.5-flash,google/gemini-3.7-flash,anthropic/claude-sonnet-5
OPENROUTER_VISION_MODELS=google/gemini-2.5-flash,google/gemini-3.7-flash

# Google Gemini 直接連線（多 Key 備援）
GEMINI_API_KEYS=key1,key2
GEMINI_MODEL=gemini-2.5-flash-lite

# DeepSeek 備援連線
DEEPSEEK_API_KEY=你的_DEEPSEEK_API_KEY
DEEPSEEK_MODEL=deepseek-chat

# Lavalink 音樂服務節點（選填）
LAVALINK_HOST=127.0.0.1
LAVALINK_PORT=2333
LAVALINK_PASSWORD=youshallnotpass
LAVALINK_SECURE=false

# 閘道特權意圖 (Privileged Gateway Intents)
INTENT_MESSAGE_CONTENT=true
INTENT_MEMBERS=true
INTENT_PRESENCES=false
```

### 3. 開啟 Discord 開發者意圖

至 [Discord Developer Portal](https://discord.com/developers/applications)：
1. 進入您的應用 > **Bot** 頁面。
2. 在 **Privileged Gateway Intents** 區域勾選：
   - **PRESENCE INTENT**
   - **SERVER MEMBERS INTENT**
   - **MESSAGE CONTENT INTENT**
3. 進入 **OAuth2** > **General** > 添加 Redirect: `http://localhost:8080/callback`（部署至伺服器請替換為真實域名或公網 IP）。

### 4. 啟動機器人

```bash
python bot.py
```

終端將顯示啟動 Banner，並在指定端口（預設 8080）啟動 Web Dashboard。

---

## 💻 終端即時互動控制

機器人運行時，您可直接在啟動的終端輸入下列快捷指令：

- `status` / `狀態` - 檢視目前連線延遲、記憶體占用、伺服器數與用戶數。
- `restart` / `重啟` - 平滑重啟機器人連線與模組。
- `stop` / `關閉` - 安全關閉機器人並儲存所有數據。
- `help` / `幫助` - 顯示終端控制說明。

---

## 📂 專案架構目錄

```
.
├── bot.py                  # 機器人主入口程式（狀態監控、Cogs 自動載入、終端監聽）
├── storage.py              # 資料持久化存取抽象層
├── version.txt             # 版本號檔案 (7.0.0)
├── requirements.txt        # Python 依賴套件清單
├── README.md               # 專案說明與指南文檔
├── PRIVACY.md              # 隱私權政策條款
├── LICENSE                 # MIT 開源授權
├── .env.example            # 環境變數範例配置
├── .gitignore              # Git 版本控制忽略清單
├── web/                    # 網頁控制台 (Web Dashboard)
│   ├── server.py           # Aiohttp Web 伺服器與 OAuth2 認證模組
│   ├── index.html          # 後台登入首頁
│   ├── select_server.html  # 伺服器切換選擇面板
│   ├── dashboard.html      # 主管理儀表板
│   ├── dev-panel.html      # 開發者高權限管理面板
│   ├── my-tickets.html     # 用戶工單檢視中心
│   ├── privacy.html        # 儀表板端隱私條款
│   └── 404.html            # 404 導向頁
├── data/                   # 數據儲存目錄 (按伺服器 ID 隔離，已忽略上傳)
└── cogs/                   # 模組化功能擴展庫
    ├── ai_chat.py          # AI 智慧對話、視覺辨識與記憶管理
    ├── giveaway.py         # 抽獎活動管理
    ├── auto_reply.py       # 關鍵字自動回覆規則系統
    ├── tickets.py          # 客服工單與 HTML 紀錄存檔
    ├── moderation.py       # 警告系統與管理指令
    ├── security.py         # 防刷屏、防釣魚與安全過濾
    ├── achievements.py     # 成就解鎖追蹤
    ├── daily.py            # 每日打卡簽到
    ├── birthday.py         # 生日自動提醒
    ├── anonymous.py        # 匿名發言與投遞
    ├── feedback.py         # 意見回饋與工單派送
    ├── temp_voice.py       # 動態臨時語音頻道
    ├── custom_commands.py  # 自訂文字命令
    ├── reaction_roles.py   # 反應身分組綁定
    ├── general.py          # 一般互動與幫助選單
    ├── fun.py              # 趣味娛樂指令
    ├── games.py            # 迷你休閒遊戲
    ├── utilities.py        # 實用輔助小工具
    ├── serverinfo.py       # 伺服器統計概況
    ├── statistics.py       # 活躍度數據分析
    ├── logging_system.py   # 系統事件日誌記錄
    └── updater.py          # 自動版本檢查更新
```

---

## 🔒 數據安全與隱私

- 本機器人注重隱私與伺服器數據隔離，所有伺服器設定皆獨立保存在 `./data/<Guild_ID>/` 目錄下。
- 專案嚴格遵循隱私安全政策，不收集個人敏感私鑰與通訊明文，詳細條款請參閱 [PRIVACY.md](PRIVACY.md)。

---

## 📄 授權條款

本專案基於 [MIT License](LICENSE) 條款開源。歡迎自由 Fork、客製化或提交 Pull Request。
