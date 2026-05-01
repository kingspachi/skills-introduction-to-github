#!/usr/bin/env python3
"""
一次性設定工具：取得 Gmail OAuth2 Token
執行此腳本後，將輸出嘅 JSON 複製到 GitHub Secrets → GMAIL_TOKEN_JSON

用法：
    python get_gmail_token.py --credentials /path/to/credentials.json
"""

import argparse
import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def main():
    parser = argparse.ArgumentParser(
        description="取得 Gmail OAuth2 Token，用於 Gmail Daily Digest Bot"
    )
    parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Google Cloud OAuth2 credentials.json 路徑（預設：./credentials.json）",
    )
    args = parser.parse_args()

    if not os.path.exists(args.credentials):
        print(f"❌  找不到 credentials 檔案：{args.credentials}")
        print()
        print("請先完成以下步驟：")
        print("  1. 前往 https://console.cloud.google.com/")
        print("  2. 建立新專案（或選擇現有專案）")
        print("  3. 啟用 Gmail API")
        print("  4. 建立 OAuth 2.0 用戶端 ID（應用程式類型：桌面應用程式）")
        print("  5. 下載 JSON 並儲存為 credentials.json")
        return

    print("🔐  開始 Gmail OAuth2 授權流程...")
    print("   瀏覽器將自動打開，請登入你的 Google 帳戶並授予權限。")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(args.credentials, SCOPES)
    creds: Credentials = flow.run_local_server(port=0)

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
    }

    print("✅  授權成功！")
    print()
    print("=" * 60)
    print("請將以下 JSON 複製並儲存到 GitHub Secrets")
    print("Secret 名稱：GMAIL_TOKEN_JSON")
    print("=" * 60)
    print(json.dumps(token_data, ensure_ascii=False, indent=2))
    print("=" * 60)
    print()
    print("下一步：")
    print("  1. 前往你的 GitHub Repo → Settings → Secrets and variables → Actions")
    print("  2. 點擊 New repository secret")
    print("  3. Name: GMAIL_TOKEN_JSON")
    print("  4. Secret: 貼上上面輸出嘅 JSON（整個 { ... } 內容）")
    print("  5. 同樣加入 ANTHROPIC_API_KEY（你的 Claude API Key）")
    print()

    # Also save locally for reference
    output_path = "gmail_token.json"
    with open(output_path, "w") as f:
        json.dump(token_data, f, ensure_ascii=False, indent=2)
    print(f"💾  Token 亦已儲存到本地：{output_path}（請勿上傳到 git！）")


if __name__ == "__main__":
    main()
