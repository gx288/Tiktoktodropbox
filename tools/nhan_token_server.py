import os
import sys
import json
import datetime
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == "tools" else BASE_DIR
TOKENS_DIR = os.path.join(PROJECT_ROOT, "tokens")
os.makedirs(TOKENS_DIR, exist_ok=True)
CLIENT_SECRET_FILE = os.path.join(PROJECT_ROOT, "client_secret.json")

with open(CLIENT_SECRET_FILE, "r", encoding="utf-8") as f:
    cs_data = json.load(f)
    client_info = cs_data.get("installed") or cs_data.get("web")
    CLIENT_ID = client_info["client_id"]
    CLIENT_SECRET = client_info["client_secret"]

REDIRECT_URI = "http://localhost:8888/"
SCOPES = "https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/spreadsheets"

AUTH_URL = (
    "https://accounts.google.com/o/oauth2/auth?"
    + urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent"
    })
)

def get_next_token_filename(email):
    # Kiểm tra xem email này đã có file token nào chưa
    for i in range(2, 20):
        fname = f"token_drive{i}.json"
        fpath = os.path.join(TOKENS_DIR, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    if d.get("account") == email:
                        return fname
            except Exception:
                pass
    # Nếu chưa có, lấy số thứ tự trống đầu tiên
    for i in range(2, 50):
        fname = f"token_drive{i}.json"
        fpath = os.path.join(TOKENS_DIR, fname)
        if not os.path.exists(fpath):
            return fname
    return "token_drive_new.json"

class OAuthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Giảm bớt log rác
        return

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        # 1. Đường dẫn chuyển hướng đăng nhập
        if parsed.path == "/login":
            self.send_response(302)
            self.send_header("Location", AUTH_URL)
            self.end_headers()
            return

        # 2. Xử lý khi Google trả mã code về
        if "code" in qs:
            code = qs["code"][0]
            # Đổi code lấy token
            token_resp = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "redirect_uri": REDIRECT_URI,
                    "grant_type": "authorization_code"
                },
                timeout=15
            )

            if token_resp.status_code != 200:
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"<h1>❌ Lỗi đổi token: {token_resp.text}</h1>".encode("utf-8"))
                return

            tokens = token_resp.json()
            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")

            # Lấy thông tin email từ Google Drive API
            email = "unknown"
            try:
                about_resp = requests.get(
                    "https://www.googleapis.com/drive/v3/about?fields=user",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=15
                )
                if about_resp.status_code == 200:
                    email = about_resp.json().get("user", {}).get("emailAddress", "unknown")
            except Exception:
                pass

            target_filename = get_next_token_filename(email)
            target_path = os.path.join(TOKENS_DIR, target_filename)

            # Lưu file token chuẩn format google-auth
            token_data = {
                "token": access_token,
                "refresh_token": refresh_token,
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "scopes": [
                    "https://www.googleapis.com/auth/drive",
                    "https://www.googleapis.com/auth/spreadsheets"
                ],
                "universe_domain": "googleapis.com",
                "account": email,
                "expiry": (datetime.datetime.utcnow() + datetime.timedelta(seconds=tokens.get("expires_in", 3600))).isoformat() + "Z"
            }

            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(token_data, f, indent=2)

            print(f"\n✔ [THÀNH CÔNG] Đã nhận và lưu token cho '{email}' vào '{target_filename}'!")

            # Trả về trang thông báo đẹp
            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Thành Công</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; text-align: center; padding: 40px 20px; background: #f8f9fa; }}
        .card {{ max-width: 550px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); }}
        h1 {{ color: #28a745; margin-bottom: 10px; font-size: 26px; }}
        .email {{ font-size: 20px; color: #1a73e8; font-weight: bold; margin: 15px 0; }}
        .file {{ font-size: 15px; color: #6c757d; background: #e9ecef; padding: 8px 16px; border-radius: 6px; display: inline-block; }}
        .btn {{ display: inline-block; margin-top: 25px; padding: 12px 24px; background: #1a73e8; color: white; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px; transition: background 0.2s; }}
        .btn:hover {{ background: #1557b0; }}
        .note {{ margin-top: 20px; font-size: 14px; color: #888; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>🎉 CẤP QUYỀN THÀNH CÔNG!</h1>
        <p>Đã lưu Token vĩnh viễn cho tài khoản:</p>
        <div class="email">{email}</div>
        <div>Tệp lưu trữ: <span class="file">{target_filename}</span></div>
        <hr style="margin: 25px 0; border: 0; border-top: 1px solid #eee;">
        <p style="font-size: 15px; color: #333;">Nếu bạn muốn thêm nick tiếp theo, chỉ cần bấm nút bên dưới:</p>
        <a href="/login" class="btn">👉 Bấm để thêm tài khoản tiếp theo</a>
        <div class="note">(Hoặc bạn có thể đóng tab này lại)</div>
    </div>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        # 3. Trang chủ localhost:8888
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>OAuth Server</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
    <h2>Máy chủ nhận Token Google Drive đang chạy sẵn sàng!</h2>
    <p><a href="/login" style="display:inline-block; padding:12px 24px; background:#1a73e8; color:white; border-radius:6px; text-decoration:none; font-weight:bold;">👉 Bấm vào đây để Đăng Nhập & Cấp Quyền</a></p>
</body>
</html>"""
        self.wfile.write(html.encode("utf-8"))

def run():
    server = HTTPServer(("localhost", 8888), OAuthHandler)
    print("=" * 65)
    print("🚀 MÁY CHỦ NHẬN TOKEN TỰ ĐỘNG ĐÃ KHỞI ĐỘNG (PORT 8888)")
    print("=" * 65)
    print("👉 Link cấp quyền trực tiếp:")
    print(AUTH_URL)
    print("=" * 65)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    run()
