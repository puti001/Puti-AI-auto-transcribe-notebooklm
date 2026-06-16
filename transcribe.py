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

def transcribe_and_sync(video_url):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: 請先設定 GEMINI_API_KEY 環境變數。")
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
        # 下載最佳品質的 mp4 影片
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
        # 3. 呼叫 Gemini 2.5 進行多模態轉寫
        print("🧠 步驟 2: 正在上傳影片至 Gemini 並進行視聽雙重辨識...")
        client = genai.Client(api_key=api_key)
        
        # 上傳視訊檔案
        video_file = client.files.upload(file=video_path)
        
        # 等待處理完成
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = client.files.get(name=video_file.name)

        if video_file.state.name == "FAILED":
            raise RuntimeError("Gemini 伺服器端影片解析失敗。")

        # 設定提示詞：進行精準辨識並去口語化提煉書面報告
        prompt = (
            "你是一個專業的影音知識庫整理專家。請針對這段影片進行「視聽雙重辨識」與「結構化提煉」：\n"
            "1. 一字不漏地辨識出影片中的所有說話內容。因為影片可能包含雜音或背景音樂，請務必結合畫面上的中文字幕（OCR）與聲音（ASR）進行交叉對齊，以確保 100% 精準度。\n"
            "2. 自動消除口語贅字，將口說對白重寫為語句通順、排版美觀、邏輯清晰的「繁體中文書面知識報告」。\n"
            "3. 報告內應將核心名詞以加粗標示，並分為多個結構化的章節段落。\n"
            "4. 以 Markdown 格式輸出。"
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[video_file, prompt]
        )
        
        # 寫入本地 Markdown
        output_title = "【研究】影片知識提煉報告"
        output_filename = "video_transcript_report.md"
        output_path = os.path.join(script_dir, output_filename)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response.text)
            
        print(f"✓ 步驟 3: 報告已成功儲存至本地: {output_path}")

        # 4. 同步至 NotebookLM
        if nlm_cmd:
            print("📓 步驟 4: 正在自動同步至 NotebookLM...")
            # 建立新筆記本
            notebook_title = "【影片分析】" + video_url.split("/")[-1][:15]
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

        # 清理雲端暫存檔
        client.files.delete(name=video_file.name)

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
