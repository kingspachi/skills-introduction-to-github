#!/usr/bin/env python3
"""Gmail Daily Digest Bot - 每日 Gmail 早上 11 點自動簡報"""

import os
import sys
import json
import base64
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

HKT = timezone(timedelta(hours=8))
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_gmail_service():
    token_json = os.environ.get("GMAIL_TOKEN_JSON")
    if not token_json:
        raise ValueError("環境變數 GMAIL_TOKEN_JSON 未設定，請參閱 README 進行設定。")

    token_data = json.loads(token_json)
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data["refresh_token"],
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=SCOPES,
    )

    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return build("gmail", "v1", credentials=creds)


def get_today_unread_threads(service):
    today_hkt = datetime.now(HKT).date()
    query = (
        f"is:unread after:{today_hkt.strftime('%Y/%m/%d')} "
        "-category:promotions -category:social -in:spam -in:trash"
    )

    threads = []
    page_token = None

    while True:
        params = {"userId": "me", "q": query, "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token

        result = service.users().threads().list(**params).execute()
        threads.extend(result.get("threads", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return threads


def decode_body(data: str) -> str:
    return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")


def extract_body(payload: dict) -> str:
    """Extract plain text from a message payload, falling back to HTML."""

    def find_part(parts, mime):
        for part in parts:
            if part.get("mimeType") == mime:
                data = part.get("body", {}).get("data", "")
                if data:
                    return decode_body(data)
            if "parts" in part:
                found = find_part(part["parts"], mime)
                if found:
                    return found
        return None

    mime = payload.get("mimeType", "")
    if mime.startswith("multipart"):
        body = find_part(payload.get("parts", []), "text/plain")
        if not body:
            body = find_part(payload.get("parts", []), "text/html")
    else:
        data = payload.get("body", {}).get("data", "")
        body = decode_body(data) if data else ""

    # Strip HTML tags for readability and limit length
    if body:
        import re
        body = re.sub(r"<[^>]+>", " ", body)
        body = re.sub(r"\s+", " ", body).strip()

    return (body or "（無法讀取郵件內容）")[:4000]


def get_thread_emails(service, thread_id: str) -> list[dict]:
    thread = service.users().threads().get(
        userId="me", id=thread_id, format="full"
    ).execute()

    emails = []
    for msg in thread.get("messages", []):
        headers = {
            h["name"].lower(): h["value"]
            for h in msg.get("payload", {}).get("headers", [])
        }
        emails.append(
            {
                "msg_id": msg["id"],
                "thread_id": thread_id,
                "from": headers.get("from", "未知"),
                "to": headers.get("to", ""),
                "subject": headers.get("subject", "（無主題）"),
                "date": headers.get("date", ""),
                "body": extract_body(msg.get("payload", {})),
            }
        )
    return emails


def build_claude_prompt(all_emails: list[dict], today_str: str) -> str:
    parts = []
    for i, email in enumerate(all_emails, 1):
        parts.append(
            f"【電郵 {i}】\n"
            f"寄件人：{email['from']}\n"
            f"主題：{email['subject']}\n"
            f"時間：{email['date']}\n"
            f"內容：\n{email['body']}\n"
        )

    emails_block = "\n---\n".join(parts)

    return f"""你係用家嘅個人助理，負責整理今日（{today_str}）嘅 Gmail 未讀電郵簡報。

以下係今日所有未讀電郵（共 {len(all_emails)} 封）：

{emails_block}

請按以下格式，用繁體中文輸出完整簡報：

## 今日電郵總覽
（一句總結今日郵件重點）

---

對每封電郵，請提供：

### 電郵 [編號]：[主題]
**寄件人**：[寄件人]
**時間**：[時間]

**摘要**：（2-3 句，說明郵件重點）

**需要回覆**：[是 / 否 / 可選]

**建議回覆**：（如需回覆，提供一段簡短、有禮貌嘅繁體中文回覆草稿；如不需回覆則寫「不需要」）

---

## 優先處理清單
（列出最需要跟進嘅電郵，按重要程度排序）

最後問：「以上電郵，你需要我幫你回覆哪幾封？請告訴我電郵編號。」"""


def create_briefing(all_emails: list[dict], today_str: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("環境變數 ANTHROPIC_API_KEY 未設定。")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_claude_prompt(all_emails, today_str)

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system="你係一個專業、細心嘅個人助理，善於整理郵件同提供建議。請用繁體中文回覆。",
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def briefing_to_html(briefing_text: str, thread_count: int, today_str: str) -> str:
    import re

    # Convert markdown-ish text to basic HTML
    text = briefing_text
    text = re.sub(r"^## (.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
    text = re.sub(r"^### (.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"^---$", "<hr>", text, flags=re.MULTILINE)
    text = text.replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<style>
  body {{
    font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
    max-width: 680px; margin: 0 auto; padding: 20px;
    color: #202124; line-height: 1.6;
  }}
  .header {{
    background: linear-gradient(135deg, #1a73e8, #0d47a1);
    color: #fff; padding: 24px; border-radius: 12px; margin-bottom: 24px;
  }}
  .header h1 {{ margin: 0 0 6px; font-size: 20px; }}
  .header p {{ margin: 0; opacity: 0.85; font-size: 14px; }}
  .badge {{
    display: inline-block; background: rgba(255,255,255,0.2);
    border-radius: 20px; padding: 4px 12px; font-size: 13px; margin-top: 8px;
  }}
  .body {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 12px; padding: 24px; }}
  h2 {{ color: #1a73e8; margin-top: 24px; }}
  h3 {{ color: #333; border-left: 4px solid #1a73e8; padding-left: 10px; }}
  hr {{ border: none; border-top: 1px solid #e0e0e0; margin: 20px 0; }}
  .footer {{ margin-top: 20px; font-size: 12px; color: #999; text-align: center; }}
</style>
</head>
<body>
  <div class="header">
    <h1>📧 Gmail 每日簡報</h1>
    <p>{today_str}</p>
    <span class="badge">今日未讀：{thread_count} 個郵件串</span>
  </div>
  <div class="body">{text}</div>
  <div class="footer">
    此簡報由 Gmail Daily Digest Bot 自動生成，由 Claude AI 分析整理。
  </div>
</body>
</html>"""


def send_digest_email(service, recipient: str, subject: str, html: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["To"] = recipient
    msg["From"] = "me"
    msg.attach(MIMEText(html, "html", "utf-8"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def interactive_reply_loop(service, all_emails: list[dict]):
    """Ask the user which emails to reply to, then send the replies."""
    print("\n" + "=" * 60)
    reply_input = input(
        "\n📝 請輸入你想回覆嘅電郵編號（例如：1,3,5），或按 Enter 跳過：\n> "
    ).strip()

    if not reply_input:
        print("✅ 唔需要回覆任何電郵。")
        return

    indices = []
    for part in reply_input.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(all_emails):
                indices.append(idx)

    if not indices:
        print("⚠️  未找到有效編號，跳過回覆。")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    for idx in indices:
        email = all_emails[idx]
        print(f"\n--- 電郵 {idx + 1}：{email['subject']} ---")

        draft_prompt = (
            f"請為以下電郵撰寫一封有禮貌、簡潔嘅繁體中文回覆草稿：\n\n"
            f"寄件人：{email['from']}\n"
            f"主題：{email['subject']}\n"
            f"內容：{email['body'][:1500]}"
        )
        draft_msg = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=512,
            messages=[{"role": "user", "content": draft_prompt}],
        )
        draft = draft_msg.content[0].text

        print(f"\n📝 建議回覆草稿：\n{draft}")
        confirm = input("\n發送此回覆？[y/N] ").strip().lower()

        if confirm == "y":
            reply_msg = MIMEText(draft, "plain", "utf-8")
            reply_msg["Subject"] = f"Re: {email['subject']}"
            reply_msg["To"] = email["from"]
            reply_msg["From"] = "me"
            raw = base64.urlsafe_b64encode(reply_msg.as_bytes()).decode()
            service.users().messages().send(
                userId="me",
                body={"raw": raw, "threadId": email["thread_id"]},
            ).execute()
            print(f"✅ 回覆已發送至 {email['from']}")
        else:
            print("⏭️  已跳過。")


def main():
    print("🌅  Gmail 每日簡報 Bot 啟動...")

    today_hkt = datetime.now(HKT)
    today_str = today_hkt.strftime("%Y年%m月%d日")
    print(f"📅  日期：{today_str}（香港時間）")

    print("🔐  連接 Gmail API...")
    service = get_gmail_service()

    profile = service.users().getProfile(userId="me").execute()
    user_email = profile.get("emailAddress", "")
    print(f"👤  帳戶：{user_email}")

    print("📬  搜尋今日未讀電郵...")
    threads = get_today_unread_threads(service)

    if not threads:
        print("✅  今日沒有未讀電郵！")
        return

    print(f"📩  找到 {len(threads)} 個郵件串，正在讀取內容...")

    all_emails: list[dict] = []
    for i, thread in enumerate(threads[:20], 1):  # cap at 20 threads
        try:
            emails = get_thread_emails(service, thread["id"])
            all_emails.extend(emails)
            print(f"   [{i}/{min(len(threads), 20)}] 已讀取：{emails[-1]['subject']}")
        except HttpError as e:
            print(f"   ⚠️  無法讀取郵件串 {thread['id']}：{e}")

    print(f"\n🤖  使用 Claude AI 分析 {len(all_emails)} 封電郵，生成簡報...")
    briefing = create_briefing(all_emails, today_str)

    is_interactive = sys.stdin.isatty()

    if is_interactive:
        # ── Interactive (local) mode ────────────────────────────────────────
        print("\n" + "=" * 60)
        print(f"  📋  {today_str} 電郵簡報")
        print("=" * 60 + "\n")
        print(briefing)
        print("\n" + "=" * 60)

        send_choice = input(
            f"\n📤  是否將簡報發送到你的郵箱 ({user_email})？[y/N] "
        ).strip().lower()

        if send_choice == "y":
            html = briefing_to_html(briefing, len(threads), today_str)
            send_digest_email(
                service,
                user_email,
                f"📧 Gmail 每日簡報 - {today_str}",
                html,
            )
            print(f"✅  簡報已發送至 {user_email}")

        interactive_reply_loop(service, all_emails)

    else:
        # ── Automated (GitHub Actions) mode ────────────────────────────────
        print("📤  自動模式：將簡報發送至郵箱...")
        html = briefing_to_html(briefing, len(threads), today_str)
        send_digest_email(
            service,
            user_email,
            f"📧 Gmail 每日簡報 - {today_str}",
            html,
        )
        print(f"✅  簡報已成功發送至 {user_email}！")
        print("\n簡報預覽（純文字）：")
        print("-" * 60)
        print(briefing)

    print("\n🎉  完成！")


if __name__ == "__main__":
    main()
