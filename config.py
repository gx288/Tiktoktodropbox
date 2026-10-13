ANHMOE_API_KEY = "chv_pqYs_31b5ab2fdf61acc3b217b0a5e6a53336cad60a3cd3addc9bd84933b50f680e0a7576da2a52bfffab2ae47531e5c0dd366f4c090390a65535fa218c06b081ff07"
SHEET_ID = "14tqKftTqlesnb0NqJZU-_f1EsWWywYqO36NiuDdmaTo"       # ID của Google Sheet
DROPBOX_FOLDER_PATH = "/Shorts"                              # Thư mục lưu trữ trên Dropbox

# Tận dụng dung lượng trống trên cả 2 tài khoản Dropbox
DROPBOX_ACCOUNTS = [
    {
        "name": "Tài khoản lehungpharmacist@gmail.com",
        "email": "lehungpharmacist@gmail.com",
        "app_key": "mkowbqfz4ykqh6f",
        "app_secret": "j8288shsvjf6bg0",
        "refresh_token": "-WxNmq_vnZkAAAAAAAAAATV1UHUizL691UMSe2c0FWiFTyXH0hFyg_fu4bpBWrGn"
    },
    {
        "name": "Tài khoản lehunghup@gmail.com",
        "email": "lehunghup@gmail.com",
        "app_key": "h41qr1gug3igboo",
        "app_secret": "1bpklzevtqsgi2k",
        "refresh_token": "p-ZJQ2Ji9aoAAAAAAAAAAUwKjZIa7LoaLtKID9_Uk1p_wdfdjr2-Ea6d2raWNrsB"
    }
]

CLEANUP_ACCOUNTS = []

# Tương thích ngược với các hàm đơn lẻ
DROPBOX_APP_KEY = DROPBOX_ACCOUNTS[0]["app_key"]
DROPBOX_APP_SECRET = DROPBOX_ACCOUNTS[0]["app_secret"]
DROPBOX_REFRESH_TOKEN = DROPBOX_ACCOUNTS[0]["refresh_token"]

# ====================== CẤU HÌNH THÔNG BÁO TELEGRAM BOT ======================
TELEGRAM_BOT_TOKEN = "8089272012:AAGp985KCEFOdMe1iJO_pp2hb8gFD-rV3c4"  # Bot CẤP BÁO (@N10notibot)
TELEGRAM_CHAT_ID = 1900957785                                          # @hungleDKH (User ID)