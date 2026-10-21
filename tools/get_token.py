import os
import sys
import io

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

import argparse

def main():
    parser = argparse.ArgumentParser(description="Lấy Token Google Drive OAuth vĩnh viễn (Production)")
    parser.add_argument("--output", "-o", default="token.json", help="Tên file token cần lưu (VD: token_drive2.json)")
    args = parser.parse_args()

    output_file = args.output
    # Tự động lưu vào thư mục tokens/ nếu chưa chỉ định thư mục
    if not os.path.dirname(output_file):
        tokens_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tokens")
        if not os.path.exists(tokens_dir):
            tokens_dir = "tokens"
        output_file = os.path.join(tokens_dir, output_file)
        
    print("=" * 60)
    print("🚀 BẮT ĐẦU QUÁ TRÌNH LẤY TOKEN GOOGLE DRIVE / SHEETS VĨNH VIỄN")
    print(f"📁 File token sẽ được lưu vào: {output_file}")
    print("=" * 60)
    
    secret_path = "client_secret.json"
    if not os.path.exists(secret_path):
        secret_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "client_secret.json")
    
    flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)
    
    prompt_msg = (
        "\n🔗 LINK XÁC THỰC (Nếu trình duyệt mở sai cửa sổ, hãy COPY link này dán vào đúng cửa sổ Chrome bạn đã đăng nhập sẵn nick):\n"
        "{url}\n"
    )
    creds = flow.run_local_server(
        port=0,
        prompt='select_account consent',
        access_type='offline',
        authorization_prompt_message=prompt_msg
    )
    
    with open(output_file, 'w', encoding='utf-8') as token_file:
        token_file.write(creds.to_json())
        
    print("\n" + "=" * 60)
    print("🎉 CHÚC MỪNG! ĐÃ LẤY ĐƯỢC TOKEN FULL QUYỀN VĨNH VIỄN THÀNH CÔNG!")
    print(f"File '{output_file}' đã được tạo thành công.")
    print("=" * 60)

if __name__ == '__main__':
    main()
