import webbrowser
import urllib.parse
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# === BƯỚC 1: ĐIỀN THÔNG TIN APP CỦA BẠN VÀO ĐÂY ===
APP_KEY = "mkowbqfz4ykqh6f"  # Ví dụ: abc123xyz
APP_SECRET = "j8288shsvjf6bg0"  # Ví dụ: 9k8j7h6g5f4d
REDIRECT_URI = "http://localhost:3020"  # Không cần thay đổi nếu dùng code này
# ====================================
auth_code = None

# Mở link tự động
auth_url = (
    f"https://www.dropbox.com/oauth2/authorize?"
    f"client_id={APP_KEY}"
    f"&response_type=code"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&token_access_type=offline"
)
print("Đang mở trình duyệt để bạn cấp quyền Dropbox...")
webbrowser.open(auth_url)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            message = """
            <h1>Thành công!</h1>
            <p>Bạn đã cấp quyền thành công. Refresh token đã được in ra ở Terminal.</p>
            <p>Bây giờ bạn có thể đóng tab này.</p>
            <script>window.close();</script>
            """
            self.wfile.write(message.encode('utf-8'))
        else:
            self.send_response(400)
            self.end_headers()


def start_server():
    server = HTTPServer(('localhost', 3020), Handler)
    server.handle_request()


threading.Thread(target=start_server, daemon=True).start()
print("Đang chờ bạn bấm Allow trên trình duyệt...")

while auth_code is None:
    pass

print("\nĐã nhận được authorization code!")

# Đổi code lấy refresh token
token_url = "https://api.dropboxapi.com/oauth2/token"
data = {
    "code": auth_code,
    "grant_type": "authorization_code",
    "client_id": APP_KEY,
    "client_secret": APP_SECRET,
    "redirect_uri": REDIRECT_URI
}
print("Đang đổi lấy refresh token...")
r = requests.post(token_url, data=data)
result = r.json()

if "refresh_token" in result:
    print("\n=== THÀNH CÔNG 100% ===")
    print("REFRESH_TOKEN của bạn (lưu ngay, chỉ hiện 1 lần):")
    print(result["refresh_token"])
    print("\n(Access token thì không cần lưu nữa)")
else:
    print("Lỗi:", result)

input("\nNhấn Enter để thoát...")