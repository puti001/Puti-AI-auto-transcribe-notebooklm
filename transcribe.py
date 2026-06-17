import os
import sys
import time
import subprocess
import shutil
from google import genai

def check_env():
    """檢測並登入 NotebookLM 環境"""
    nlm_path = shutil.which("nlm")
    if not nlm_path:
        # 嘗試在預設的 Python Scripts 目錄搜尋
        appdata = os.environ.get("APPDATA", "")
        fallback_path = os.path.join(appdata, "Python", "Python314", "Scripts", "nlm.exe")
        if os.path.exists(fallback_path):
            nlm_path = fallback_path
        else:
            return False, "未偵測到 nlm CLI 工具，請先安裝：pip install notebooklm-mcp-cli"

    # 檢查是否已登入
    res = subprocess.run([nlm_path, "login", "--check"], capture_output=True, text=True)
    if "expired" in res.stderr or res.returncode != 0:
        print("偵測到 NotebookLM 憑證已過期，正在嘗試背景自動登入...")
        # 呼叫 nlm login 進行 headless 登入
        login_res = subprocess.run([nlm_path, "login"], capture_output=True, text=True)
        if "Successfully authenticated" not in login_res.stdout and login_res.returncode != 0:
            return False, "NotebookLM 自動登入失敗，請手動在終端機執行 'nlm login' 重新授權。"
            
    return True, nlm_path

def get_transcription_from_gemini(client, video_path):
    """使用 Google Gemini 2.5 Flash 進行視聽雙模態高精度轉寫與提煉"""
    print("🧠 正在上傳影片至 Gemini 並進行視聽雙重辨識 (Gemini 2.5)...")
    video_file = client.files.upload(file=video_path)
    
    # 等待處理完成
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)

    if video_file.state.name == "FAILED":
        raise RuntimeError("Gemini 伺服器端影片解析失敗。")

    prompt = (
        "你是一個專業的影音知識庫整理專家。請針對這段影片進行「視聽雙重辨識」與「結構化提煉」：\n"
        "1. 一字不漏地辨識出影片中的所有說話內容。因為影片可能包含雜音或背景音樂，請務必結合畫面上的中文字幕（OCR）與聲音（ASR）進行交叉對齊，以確保 100% 精準度。\n"
        "2. 自動消除口語贅字，將口說對白重寫為語句通順、排版美觀、邏輯清晰的「繁體中文書面知識報告」。\n"
        "3. 報告內應將核心名詞以加粗標示，並分為多個結構化的章節段落。\n"
        "4. 以 Markdown 格式輸出。"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[video_file, prompt]
        )
        return response.text
    finally:
        # 清理雲端暫存檔
        client.files.delete(name=video_file.name)

def get_transcription_from_openai(video_path):
    """使用 OpenAI Whisper 進行語音轉寫，並使用 GPT-4o 進行去口語化與書面提煉"""
    print("🧠 正在提取音訊並使用 OpenAI (Whisper + GPT-4o) 進行轉寫與提煉...")
    from openai import OpenAI
    client = OpenAI() # 會自動讀取 OPENAI_API_KEY
    
    script_dir = os.path.dirname(os.path.abspath(video_path))
    temp_audio_path = os.path.join(script_dir, "temp_extracted_audio.mp3")
    
    # 使用 yt-dlp/ffmpeg 提取音訊 (通常 yt-dlp 本身就支援提取)
    print("   - 正在提取影片音軌...")
    subprocess.run([
        "python", "-m", "yt_dlp",
        "--extract-audio", "--audio-format", "mp3",
        "-o", os.path.join(script_dir, "temp_extracted_audio.%(ext)s"),
        video_path
    ], capture_output=True)
    
    if not os.path.exists(temp_audio_path):
        # 降級備用：如果沒裝 ffmpeg 導致提取失敗，嘗試用音訊辨識
        raise RuntimeError("OpenAI 轉寫需要安裝 ffmpeg 以提取音訊。請確保系統已配置 ffmpeg。")

    try:
        # 1. 呼叫 Whisper 進行語音轉寫
        print("   - 正在呼叫 OpenAI Whisper 語音轉寫...")
        with open(temp_audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
            
        # 2. 呼叫 GPT-4o 進行書面精煉與格式化
        print("   - 正在呼叫 OpenAI GPT-4o 進行去口語化與 Markdown 書面排版...")
        prompt = (
            "你是一個專業的影音知識庫整理專家。下面是一段由語音辨識產生的逐字稿原始文字。\n"
            "請將這段文字進行「結構化提煉」與「去口語化」：\n"
            "1. 自動消除口語贅字，將口說對話重寫為語句通順、排版美觀、邏輯清晰的「繁體中文書面知識報告」。\n"
            "2. 報告內應將核心名詞以加粗標示，並分為多個結構化的章節段落。\n"
            "3. 以 Markdown 格式輸出。\n\n"
            f"原始逐字稿內容：\n{transcript}"
        )
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

def transcribe_and_sync(video_url):
    # 偵測可用的 API Key 後端
    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    
    if not gemini_key and not openai_key:
        print("Error: 請先設定 GEMINI_API_KEY 或 OPENAI_API_KEY 環境變數。")
        sys.exit(1)

    # 1. 偵測 NotebookLM 環境
    has_nlm, nlm_cmd = check_env()
    if not has_nlm:
        print(f"⚠️ 警告: {nlm_cmd}")
        print("工作流將會『降級』執行：僅在本地生成 Markdown 逐字稿，不進行 NotebookLM 自動同步。")
        nlm_cmd = None

    script_dir = os.path.dirname(os.path.abspath(__file__))
    video_path = os.path.join(script_dir, "temp_video.mp4")

    # 2. 用 yt-dlp 下載 MP4 影片
    print("🎬 步驟 1: 正在下載影片串流 (MP4)...")
    try:
        subprocess.run([
            "python", "-m", "yt_dlp", 
            "-f", "mp4", 
            "-o", video_path, 
            video_url
        ], check=True)
    except Exception as e:
        print(f"Error 下載影片失敗: {e}")
        sys.exit(1)

    # 用 try...finally 確保本地影片一定會被清理刪除
    try:
        # 3. 呼叫相應的 AI 後端進行轉寫與提煉
        if gemini_key:
            client = genai.Client(api_key=gemini_key)
            report_text = get_transcription_from_gemini(client, video_path)
        else:
            report_text = get_transcription_from_openai(video_path)
        
        # 寫入本地 Markdown
        output_filename = "video_transcript_report.md"
        output_path = os.path.join(script_dir, output_filename)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_text)
            
        print(f"✓ 步驟 3: 報告已成功儲存至本地: {output_path}")

        # 4. 同步至 NotebookLM
        if nlm_cmd:
            print("📓 步驟 4: 正在自動同步至 NotebookLM...")
            
            # 動態讀取報告的第一行標題（例如 # 中華席禮與相撲起源考），作為筆記本標題
            notebook_title = "【影片分析】"
            try:
                with open(output_path, "r", encoding="utf-8") as rf:
                    first_line = rf.readline().strip()
                    if first_line.startswith("#"):
                        extracted_title = first_line.lstrip("#").strip()
                        notebook_title = "【影片分析】" + extracted_title[:30] # 限制字數以防 API 限制
                    else:
                        notebook_title = "【影片分析】" + video_url.split("/")[-1][:15]
            except Exception:
                notebook_title = "【影片分析】" + video_url.split("/")[-1][:15]

            # 建立新筆記本
            create_res = subprocess.run(
                [nlm_cmd, "notebook", "create", notebook_title],
                capture_output=True, text=True
            )
            
            # 從輸出中解析 Notebook ID
            notebook_id = None
            for line in create_res.stdout.split("\n"):
                if "ID:" in line:
                    notebook_id = line.split("ID:")[-1].strip()
                    break

            if notebook_id:
                print(f"✓ 成功建立 NotebookLM 筆記本! (ID: {notebook_id})")
                # 匯入 Markdown 作為 Source
                sync_res = subprocess.run([
                    nlm_cmd, "source", "add", notebook_id, 
                    "--file", output_path, 
                    "--wait"
                ], capture_output=True, text=True)
                
                if "Added source" in sync_res.stdout:
                    print("✓ 成功將報告匯入至 NotebookLM 筆記本中！")
                else:
                    print(f"⚠️ 匯入來源失敗: {sync_res.stderr}")
            else:
                print(f"⚠️ 建立筆記本失敗: {create_res.stderr}")

    finally:
        # 5. 硬碟零殘留清理
        if os.path.exists(video_path):
            os.remove(video_path)
            print("🧹 步驟 5: 本地 MP4 影片暫存檔已自動刪除清理。")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python transcribe.py [VIDEO_URL]")
        sys.exit(1)
        
    url = sys.argv[1]
    transcribe_and_sync(url)
