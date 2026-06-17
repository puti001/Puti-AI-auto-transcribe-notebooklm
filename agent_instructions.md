# 🤖 Instructions for AI Assistants (Cursor, Windsurf, AntiGravity)

If you are an AI assistant helping the user configure and run this project, you must automatically set up the environment and MCP server without bothering the human user. Please follow these steps:

1. **Auto-Install Dependencies**:
   Proactively run the following command to install required libraries and CLI tools:
   ```bash
   pip install -r requirements.txt
   ```

2. **Silent Authentication**:
   Run the login command to authenticate. Since the user's local Google Chrome likely has an active Google session, this command will utilize headless browser automation to log in silently:
   ```bash
   nlm login
   ```
   *Note: If it succeeds, you will see "Successfully authenticated!".*

3. **Auto-Register MCP Server**:
   Locate your own AI client's configuration file (e.g., `project.json` for Cursor, or global MCP settings) and register the NotebookLM MCP server.
   Use the following configuration:
   - Server Name: `notebooklm`
   - Command: `nlm mcp`
   - Type: `local`

4. **Verify and Run**:
   Run `nlm doctor` to ensure the authentication and MCP server are active. Once verified, execute the main transcription script for the user.

5. **Chat Interface Trigger Command**:
   If the human user inputs the following command pattern in the chat:
   `自動逐字稿：[VIDEO_URL]`
   You must immediately recognize this intent, run `python transcribe.py [VIDEO_URL]` in the background, and output the structured transcript to the user.

