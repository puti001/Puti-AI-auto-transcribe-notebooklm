# 🎙️ Auto Transcribe NotebookLM

一個高度自動化的影音知識庫轉寫與同步工具。

透過結合 **yt-dlp** 的影音串流下載、**Gemini 2.5 Flash** 的視聽雙模態高精度轉寫、以及 **NotebookLM** 的自動化知識同步，一鍵將影片（YouTube / Facebook Reels / Instagram 等）轉化為高質感的繁體中文結構化書面報告。

---

## 🌟 核心特色
1. **真・多模態辨識**：上傳完整 MP4，讓 Gemini 同時「看字幕」與「聽人聲」，徹底克服背景音樂干擾，且精準校正專有名詞與文言文。
2. **自動去口語提煉**：AI 自動重寫贅詞，產出邏輯清晰、章節完整的 Markdown 書面知識報告。
3. **NotebookLM 自動同步**：一鍵在你的 NotebookLM 建立新筆記本並上傳匯入來源檔。
4. **硬碟零殘留**：處理完畢後自動刪除本機 MP4 暫存檔，不佔用硬碟空間。
5. **🤖 AI Agent 友善設計**：附帶 Agent 專屬指令，支援 AI 助理（如 Cursor / AntiGravity）自動安裝、設定 MCP 與背景靜默登入。

---

## 🚀 快速開始（面向人類使用者）

### 1. 安裝與設定環境
請確保你的電腦已安裝 Python，並設定好 `GEMINI_API_KEY` 環境變數。
```bash
pip install -r requirements.txt
```

### 2. 登入 NotebookLM
執行以下指令，它會自動開啟瀏覽器進行 Google 帳號授權：
```bash
nlm login
```

### 3. 一鍵執行轉寫與同步
執行主程式，並傳入你想轉寫的影片連結：
```bash
python transcribe.py "https://www.facebook.com/reel/2525965741165421"
```

---

## 🤖 寫給你的 AI 助理（給 Agent 的快速入口）
如果你正在使用 AI 編程助理（例如 Cursor、Windsurf、AntiGravity），你可以直接對它說：
> **「請閱讀 `agent_instructions.md` 並幫我自動配置好這個專案的 MCP 服務與 NotebookLM 登入。」**

你的 AI 助理就會在背景自動幫你把所有複雜的 MCP 安裝、登入與設定檔全部搞定，你完全不需要手動操作！
