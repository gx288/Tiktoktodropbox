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

def main():
    print("=" * 60)
    print("🚀 BẮT ĐẦU QUÁ TRÌNH LẤY TOKEN GOOGLE DRIVE / SHEETS VĨNH VIỄN")
    print("=" * 60)
    
    flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
    
    print("\n👉 Đang mở trình duyệt để bạn đăng nhập và cấp quyền...")
    print("👉 Hãy chọn tài khoản Gmail của bạn trên trình duyệt vừa mở ra.")
    print("👉 Bấm: 'Nâng cao' (Advanced) -> 'Đi tới MyDrive (không an toàn)' -> Tích chọn các quyền -> Bấm 'Tiếp tục' (Continue).\n")
    
    creds = flow.run_local_server(port=8080, prompt='consent', access_type='offline')
    
    with open('token.json', 'w', encoding='utf-8') as token_file:
        token_file.write(creds.to_json())
        
    print("\n" + "=" * 60)
    print("🎉 CHÚC MỪNG! ĐÃ LẤY ĐƯỢC TOKEN FULL QUYỀN VĨNH VIỄN THÀNH CÔNG!")
    print("File 'token.json' đã được tạo thành công.")
    print("=" * 60)

if __name__ == '__main__':
    main()
