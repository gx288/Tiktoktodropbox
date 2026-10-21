import sys
import os
import datetime

class Logger(object):
    def __init__(self, filename="app_run_log.txt"):
        self.terminal = sys.stdout
        # Mở nối tiếp (a) để lưu trữ lịch sử qua các lần tiếp tục
        self.log = open(filename, "a", encoding="utf-8")
        self.log.write(f"\n\n{'='*40}\n--- TIẾP TỤC CHẠY: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n{'='*40}\n")

    def write(self, message):
        if hasattr(self.terminal, 'write'):
            self.terminal.write(message)
            if hasattr(self.terminal, 'flush'):
                self.terminal.flush()
        self.log.write(message)
        self.log.flush()

    def flush(self):
        if hasattr(self.terminal, 'flush'):
            self.terminal.flush()
        self.log.flush()

sys.stdout.reconfigure(encoding='utf-8')
sys.stdout = Logger()
import json
import gspread
from google.oauth2.service_account import Credentials
import dropbox
import yt_dlp
import re
from time import sleep
import traceback
import subprocess
import threading
import concurrent.futures

sheet_lock = threading.Lock()
dropbox_lock = threading.Lock()

# ====================== CONFIG ======================
from config import SHEET_ID, DROPBOX_ACCOUNTS, DROPBOX_FOLDER_PATH, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, CLEANUP_ACCOUNTS

# Lưu trữ Cloud: "gdrive" (Google Drive 15GB lehungpharmacist5@gmail.com) hoặc "dropbox"
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "gdrive").lower()
GDRIVE_FOLDER_NAME = "Shorts"

# ====================== THÔNG SỐ ======================
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
RETRY_ATTEMPTS = 5
MAX_VIDEOS_PER_DAY = 20000
TEST_VIDEOS = 200000

TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
FULL_DOWNLOAD = os.getenv("FULL_DOWNLOAD", "false").lower() == "true"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
PRIMARY_FORMAT = "bestvideo+bestaudio[language=vi]/bestvideo+bestaudio[language^=vi]/bestvideo+bestaudio/best"
FALLBACK_FORMAT = "best[language=vi]/best[language^=vi]/best"
import shutil
NODE_PATH = shutil.which("node") or "node"

# Tự động tìm đường dẫn yt-dlp trong venv để đảm bảo khi đóng gói EXE chạy độc lập vẫn tìm thấy
YTDLP_BIN = "yt-dlp"
possible_ytdlp_paths = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../venv/Scripts/yt-dlp.exe"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv/Scripts/yt-dlp.exe"),
    r"C:\Users\Admin\PycharmProjects\yt-dlp\venv\Scripts\yt-dlp.exe"
]
for p in possible_ytdlp_paths:
    if os.path.exists(p):
        YTDLP_BIN = p
        break


import requests
import urllib.parse

def resolve_tiktok_channel_url(url):
    if "vm.tiktok.com" in url or "vt.tiktok.com" in url:
        try:
            r = requests.head(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}, allow_redirects=True, timeout=15)
            parsed = urllib.parse.urlparse(r.url)
            qs = urllib.parse.parse_qs(parsed.query)
            sec_uid = qs.get('sec_uid', [None])[0]
            if sec_uid:
                return f"https://www.tiktok.com/@{sec_uid}"
            username = parsed.path.split('/')[1] if len(parsed.path.split('/')) > 1 else ''
            if username:
                return f"https://www.tiktok.com/{username}"
        except Exception as e:
            print(f"Lỗi giải mã link rút gọn {url}: {e}")
    return url

# ====================== CHANNEL CONFIG ======================
CHANNEL_CONFIGS = [
    {
        "url": "https://www.youtube.com/@Aceshort-pro1/shorts",
        "platform": "youtube",
        "start_date": "2020-01-01",
        "name": "YouTube @Aceshort-pro1"
    }
]

SHEET_NAME = "Reels"


def get_credentials():
    if not os.path.exists("credentials.json"):
        raise FileNotFoundError("credentials.json not found!")
    with open("credentials.json", "r", encoding='utf-8') as f:
        return Credentials.from_service_account_info(json.load(f),
                                                     scopes=["https://www.googleapis.com/auth/spreadsheets"])


def clean_title(title):
    # Thay thế tất cả hashtag liên quan đến short và youtube thành #reels
    t = re.sub(r'#\w*(?:short|youtube)\w*', '#reels', str(title), flags=re.IGNORECASE)
    t = re.sub(r'#dongysonha', '', t, flags=re.IGNORECASE)
    if '#reels' not in t.lower():
        t += ' #reels'
    # Gộp các hashtag #reels trùng lặp
    t = re.sub(r'(?:#reels\s*)+', '#reels ', t, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', t).strip()


def notify_telegram(message):
    try:
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            import requests
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            resp = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=15)
            if resp.json().get("ok"):
                print("   [Telegram Bot] Đã gửi thông báo thành công đến điện thoại (@hungleDKH) qua bot @N10notibot.")
                return
    except Exception as be:
        print(f"   [Telegram Bot Error] {be}")

    try:
        send_script = r"C:\Users\HungNhan\.gemini\config\telegram\send_telegram.py"
        if os.path.exists(send_script):
            subprocess.run([sys.executable, send_script, "-m", message], timeout=30)
            print("   [Telegram] Đã gửi thông báo đến Telegram (@hungleDKH).")
    except Exception as e:
        print(f"   [Telegram Error] Lỗi gửi tin nhắn Telegram: {e}")

# ====================== QUẢN LÝ ĐA TÀI KHOẢN DROPBOX ======================
current_account_idx = 0

def get_current_account():
    global current_account_idx
    return DROPBOX_ACCOUNTS[current_account_idx]

def get_dropbox_client(account=None):
    if account is None:
        account = get_current_account()
    return dropbox.Dropbox(
        oauth2_refresh_token=account["refresh_token"],
        app_key=account["app_key"],
        app_secret=account["app_secret"]
    )

def check_account_free_space_mb(account=None):
    try:
        dbx = get_dropbox_client(account)
        space = dbx.users_get_space_usage()
        if space.allocation.is_individual():
            allocated = space.allocation.get_individual().allocated
            used = space.used
            free_mb = (allocated - used) / (1024 * 1024)
            return free_mb
    except Exception as e:
        print(f"Lỗi kiểm tra dung lượng Dropbox: {e}")
    return 9999.0

def switch_to_next_account():
    global current_account_idx
    with dropbox_lock:
        old_acc = DROPBOX_ACCOUNTS[current_account_idx]
        if current_account_idx + 1 < len(DROPBOX_ACCOUNTS):
            current_account_idx += 1
            new_acc = DROPBOX_ACCOUNTS[current_account_idx]
            print(f"\n⚠️ [DROPBOX] '{old_acc['name']}' gần đầy -> Chuyển sang '{new_acc['name']}'")
            return True
        else:
            print(f"\n⚠️ [DROPBOX] Tất cả tài khoản Dropbox đã hết dung lượng trống.")
            return False

# ====================== DỌN DẸP ======================
def cleanup_dropbox_orphaned_files():
    print("\n=== DỌN DẸP FILE RÁC TRONG DROPBOX ===")
    try:
        existing_ids = set()
        for sname in ["Reels", "Reels2", "Reels3"]:
            try:
                s = gspread.authorize(get_credentials()).open_by_key(SHEET_ID).worksheet(sname)
                for l in s.col_values(5)[1:]:
                    if l: existing_ids.add(l.split("/")[-1].split("?")[0])
            except: pass

        all_accounts = DROPBOX_ACCOUNTS + CLEANUP_ACCOUNTS
        for acc in all_accounts:
            try:
                dbx = get_dropbox_client(acc)
                result = dbx.files_list_folder(DROPBOX_FOLDER_PATH)
                files = [entry for entry in result.entries if isinstance(entry, dropbox.files.FileMetadata)]

                deleted = 0
                for file in files:
                    file_id = file.name.replace(".mp4", "").strip()
                    if file_id not in existing_ids:
                        try:
                            dbx.files_delete_v2(file.path_lower)
                            print(f"   🗑️ [{acc['name']}] Xóa rác: {file.name}")
                            deleted += 1
                        except:
                            pass
                if deleted > 0:
                    print(f"→ [{acc['name']}] Đã xóa {deleted} file rác.")
            except:
                pass
    except Exception as e:
        print(f"Lỗi dọn dẹp: {e}")


def delete_dropbox_file_if_posted():
    print("=== XÓA FILE ĐÃ ĐĂNG TRÊN CLOUD (GDRIVE / DROPBOX) ===")
    try:
        sheet = gspread.authorize(get_credentials()).open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        records = sheet.get_all_records()
        updates = []
        deleted_count = 0

        all_accounts = DROPBOX_ACCOUNTS + CLEANUP_ACCOUNTS
        drive_service = None

        for i, row in enumerate(records, start=2):
            da_dang = str(row.get("Đã đăng", "")).strip().lower()
            da_xoa = str(row.get("Đã xóa", "")).strip()

            if da_dang == "đã đăng" and da_xoa != "Đã xóa":
                link = str(row.get("link youtube videos", "")).strip()
                file_link = str(row.get("Link file", "")).strip()
                if not link: continue

                video_id = link.split("/")[-1].split("?")[0]

                # Xóa file trên Google Drive nếu link là drive.google.com
                if "drive.google.com" in file_link:
                    import re
                    m = re.search(r'id=([a-zA-Z0-9_-]+)', file_link)
                    if m:
                        gfile_id = m.group(1)
                        try:
                            if not drive_service:
                                from drive_uploader import get_drive_service
                                drive_service = get_drive_service()
                            drive_service.files().delete(fileId=gfile_id).execute()
                            print(f"   🗑️ [Google Drive] Đã xóa: {video_id} ({gfile_id})")
                            deleted_count += 1
                        except Exception as de:
                            print(f"   Lỗi xóa Drive {video_id}: {de}")
                else:
                    # Xóa file trên Dropbox
                    dropbox_path = f"{DROPBOX_FOLDER_PATH}/{video_id}.mp4"
                    for acc in all_accounts:
                        try:
                            dbx = get_dropbox_client(acc)
                            dbx.files_delete_v2(dropbox_path)
                            print(f"   🗑️ [{acc['name']}] Đã xóa: {video_id}.mp4")
                            deleted_count += 1
                            break
                        except dropbox.exceptions.ApiError:
                            continue

                updates.append({"range": f"G{i}", "values": [["Đã xóa"]]})

        if updates:
            sheet.batch_update(updates, value_input_option="USER_ENTERED")
            print(f"→ Đã xóa {deleted_count} file và đánh dấu {len(updates)} dòng.\n")
    except Exception as e:
        print(f"Lỗi xóa file đã đăng: {e}")


# ====================== FETCH METADATA (ĐÃ CẢI TIẾN TIKTOK) ======================
def fetch_all_metadata():
    print("=== ĐANG QUÉT KÊNH MỚI ===\n")
    all_videos = []
    seen_ids = set()

    for config in CHANNEL_CONFIGS:
        print(f"→ Quét {config['name']}")
        try:
            if config["platform"] == "youtube":
                # Đã đổi extract_flat thành True để quét nhanh và không dính JS Challenge
                ydl_opts = {
                    "dump_single_json": True,
                    "extract_flat": True,
                    "quiet": True,
                    "user_agent": USER_AGENT,
                    "playlistend": 500,
                    "js_runtimes": {"node": {"path": NODE_PATH}},
                    "extractor_args": {"youtube": {"lang": ["vi"]}},
                    "http_headers": {"Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"},
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    result = ydl.extract_info(config["url"], download=False)
                if "entries" in result and result.get("entries") is not None:
                    entries = result.get("entries", [])
                else:
                    entries = [result]
            else:
                # TikTok dùng subprocess với impersonate chrome (chuẩn mới nhất yt-dlp)
                cmd = [
                    YTDLP_BIN,
                    '--impersonate', 'chrome',
                    '--add-header', 'Accept-Language:vi-VN,vi;q=0.9,en;q=0.8',
                    '--dump-json',
                    '--flat-playlist',
                    '--playlist-items', '1-500',
                    '--no-warnings',
                    config["url"]
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    print(f"   Lỗi TikTok: {result.stderr[:200]}")
                    continue
                entries = [json.loads(line) for line in result.stdout.strip().split('\n') if line.strip()]

            # Tính toán timestamp ngày bắt đầu
            start_date_ts = 0
            try:
                start_date_ts = datetime.datetime.strptime(str(config["start_date"]), "%Y-%m-%d").timestamp()
            except Exception:
                pass

            filtered_count = 0
            for entry in entries:
                vid_id = entry.get("id")
                if not vid_id or vid_id in seen_ids:
                    continue

                # Lọc ngày thủ công cực chuẩn cho TikTok dựa vào ID
                if config["platform"] == "tiktok" and str(vid_id).isdigit():
                    vid_ts = int(vid_id) >> 32
                    if vid_ts < start_date_ts:
                        continue # Bỏ qua video cũ hơn ngày cấu hình

                seen_ids.add(vid_id)
                filtered_count += 1
                url = f"https://www.youtube.com/shorts/{vid_id}" if config["platform"] == "youtube" else entry.get("webpage_url") or entry.get("url")

                all_videos.append({
                    "id": vid_id,
                    "title": entry.get("title", "Untitled"),
                    "url": url,
                })
            print(f"   Tổng sau khi lọc ngày: {filtered_count} video\n")
        except Exception as e:
            print(f"   Lỗi {config['name']}: {e}\n")
    return all_videos


# ====================== CÁC HÀM CHÍNH (GIỮ NGUYÊN) ======================
def get_pending_videos():
    print("Fetching pending videos...")
    sheet = gspread.authorize(get_credentials()).open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    records = sheet.get_all_records()
    pending = []
    for row in records:
        link = str(row.get("link youtube videos", "")).strip()
        link_file = str(row.get("Link file", "")).strip()
        over_90mb = str(row.get(">90MB", "")).strip()
        
        # Nếu chưa có Link file và chưa bị đánh dấu >90MB thì cần xử lý
        if link and not link_file and over_90mb != ">90MB":
            pending.append({
                "id": link.split("/")[-1].split("?")[0],
                "title": str(row.get("Title", "Untitled")).strip(),
                "url": link,
            })
    print(f"Found {len(pending)} pending videos.")
    return pending


def save_metadata_to_sheets(videos, existing_urls):
    sheet = gspread.authorize(get_credentials()).open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    if not sheet.row_values(1):
        sheet.append_row(["Title", "Link file", "thumbnail", "length", "link youtube videos", "Đã đăng", "Đã xóa", "", "Link", ">90MB"])

    rows = [[clean_title(v["title"]), "", "", 0, v["url"], "", "", "", "", ""] for v in videos if v["url"] not in existing_urls]
    if rows:
        sheet.append_rows(rows)
        print(f"✅ Đã thêm {len(rows)} video mới vào sheet.")
    return [v for v in videos if v["url"] not in existing_urls]


def upload_to_dropbox(video_path, video_id):
    global current_account_idx
    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)

    # Kiểm tra dung lượng tài khoản hiện tại trước khi upload (đảm bảo file + 15MB an toàn)
    free_space = check_account_free_space_mb()
    account = get_current_account()
    print(f"   ☁️ Dropbox: {account['name']} (Còn trống: {free_space:.1f} MB) - File: {file_size_mb:.2f} MB")

    if free_space < (file_size_mb + 15):
        print(f"   ⚠️ Dung lượng còn lại ({free_space:.1f} MB) không đủ an toàn. Đang chuyển tài khoản...")
        if switch_to_next_account():
            return upload_to_dropbox(video_path, video_id)
        else:
            return ""

    dbx = get_dropbox_client(account)
    path = f"{DROPBOX_FOLDER_PATH}/{video_id}.mp4"

    for _ in range(RETRY_ATTEMPTS):
        try:
            with open(video_path, "rb") as f:
                dbx.files_upload(f.read(), path, mode=dropbox.files.WriteMode("overwrite"))
            link = dbx.sharing_create_shared_link_with_settings(path).url
            direct_link = link.replace("www.dropbox.com", "dl.dropboxusercontent.com")
            direct_link = re.sub(r'([?&])dl=0', r'\1dl=1', direct_link)
            return direct_link
        except dropbox.exceptions.ApiError as e:
            err_str = str(e)
            if "insufficient_space" in err_str:
                print(f"   ❌ Lỗi: Tài khoản {account['name']} hết dung lượng!")
                if switch_to_next_account():
                    return upload_to_dropbox(video_path, video_id)
                else:
                    return ""
            elif "shared_link_already_exists" in err_str:
                try:
                    links = dbx.sharing_list_shared_links(path=path).links
                    if links:
                        direct_link = links[0].url.replace("www.dropbox.com", "dl.dropboxusercontent.com")
                        direct_link = re.sub(r'([?&])dl=0', r'\1dl=1', direct_link)
                        return direct_link
                except:
                    pass
            sleep(3)
        except Exception as e:
            print(f"   Lỗi upload: {e}")
            sleep(3)
    return ""


gdrive_folder_id = None
gdrive_lock = threading.Lock()

def upload_to_gdrive(video_path, video_id):
    """Upload video lên Google Drive (Multi-Drive) và trả về direct download link cho Make.com"""
    for attempt in range(RETRY_ATTEMPTS):
        try:
            import drive_uploader
            file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
            print(f"   📁 Google Drive: Thư mục '{GDRIVE_FOLDER_NAME}' - File: {file_size_mb:.2f} MB")
            res = drive_uploader.upload_file(video_path, folder_name=GDRIVE_FOLDER_NAME)
            file_id = res['id']
            # Link direct download cho Make.com (<100MB tải trực tiếp video/mp4 HTTP 200)
            direct_link = f"https://drive.google.com/uc?export=download&id={file_id}"
            return direct_link
        except Exception as e:
            print(f"   ❌ Lỗi upload Google Drive (lần {attempt+1}/{RETRY_ATTEMPTS}): {e}")
            sleep(3)
    return ""


storage_full_alerted = False
storage_pause_flag = False
storage_lock = threading.Lock()

def upload_video_file(video_path, video_id):
    global storage_full_alerted, storage_pause_flag
    if storage_pause_flag:
        return ""

    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)

    # Nếu chọn lưu trữ mặc định là Google Drive
    if STORAGE_BACKEND == "gdrive":
        link = upload_to_gdrive(video_path, video_id)
        if link:
            return link
        with storage_lock:
            if not storage_full_alerted:
                storage_full_alerted = True
                storage_pause_flag = True
                msg = (
                    f"🚨 [CẢNH BÁO BỘ NHỚ ĐẦY]\n"
                    f"Tất cả tài khoản Google Drive đều không thể upload video ({file_size_mb:.1f} MB)!\n"
                    f"➡️ Hệ thống ĐÃ TỰ ĐỘNG TẠM NGỪNG để tránh lỗi."
                )
                print("\n" + "=" * 60)
                print(msg)
                print("=" * 60 + "\n")
                notify_telegram(msg)
            else:
                storage_pause_flag = True
        return ""

    # 1. Tận dụng Dropbox trống trước (lần lượt từng tài khoản Dropbox)
    for acc in DROPBOX_ACCOUNTS:
        try:
            free_dbx = check_account_free_space_mb(acc)
            if free_dbx > (file_size_mb + 10):
                print(f"   ☁️ [Dropbox] {acc['name']} (Còn {free_dbx:.1f} MB) -> Đang upload...")
                dbx = get_dropbox_client(acc)
                path = f"{DROPBOX_FOLDER_PATH}/{video_id}.mp4"
                with open(video_path, "rb") as f:
                    dbx.files_upload(f.read(), path, mode=dropbox.files.WriteMode("overwrite"))
                link = dbx.sharing_create_shared_link_with_settings(path).url
                direct_link = link.replace("www.dropbox.com", "dl.dropboxusercontent.com")
                direct_link = re.sub(r'([?&])dl=0', r'\1dl=1', direct_link)
                return direct_link
        except dropbox.exceptions.ApiError as ae:
            if "shared_link_already_exists" in str(ae):
                try:
                    links = dbx.sharing_list_shared_links(path=path).links
                    if links:
                        direct_link = links[0].url.replace("www.dropbox.com", "dl.dropboxusercontent.com")
                        direct_link = re.sub(r'([?&])dl=0', r'\1dl=1', direct_link)
                        return direct_link
                except:
                    pass
            print(f"   ⚠️ Dropbox ({acc['email']}) không đủ dung lượng hoặc lỗi: {ae}")
        except Exception as e:
            print(f"   ⚠️ Dropbox ({acc['email']}) lỗi: {e}")

    # 2. Nếu Dropbox đã đầy, chuyển sang Google Drive 15GB
    try:
        import drive_uploader
        free_drive = drive_uploader.get_free_space_mb()
        if free_drive > (file_size_mb + 50):
            print(f"   📁 [Google Drive] (Còn trống {free_drive:.1f} MB) -> Đang upload Drive...")
            return upload_to_gdrive(video_path, video_id)
    except Exception as gde:
        print(f"   ⚠️ Lỗi kiểm tra/upload Drive: {gde}")

    # 3. Cả Dropbox và Google Drive đều hết dung lượng -> Tạm dừng và báo Telegram 1 lần duy nhất
    with storage_lock:
        if not storage_full_alerted:
            storage_full_alerted = True
            storage_pause_flag = True
            free_drive_str = f"{free_drive:.1f} MB" if 'free_drive' in locals() else "hết"
            msg = (
                f"🚨 [CẢNH BÁO BỘ NHỚ ĐẦY]\n"
                f"Cả Dropbox và Google Drive đều không còn đủ dung lượng để lưu video tiếp theo ({file_size_mb:.1f} MB)!\n"
                f"- Dropbox: Đã đầy dung lượng trống\n"
                f"- Google Drive: Còn {free_drive_str}\n"
                f"➡️ Hệ thống ĐÃ TỰ ĐỘNG TẠM NGỪNG để tránh lỗi và không spam thông báo."
            )
            print("\n" + "=" * 60)
            print(msg)
            print("=" * 60 + "\n")
            notify_telegram(msg)
        else:
            storage_pause_flag = True

    return ""


def download_and_upload_video(video, idx=0, total=0):
    global storage_pause_flag
    if storage_pause_flag:
        return
    tag = f"[{idx}/{total}] " if total > 0 else ""
    print(f"{tag}Đang tải: {video['title'][:70]}...")
    try:
        video_id = video['id']
        video_url = video["url"]
        video_path = f"temp/{video_id}.mp4"
        os.makedirs("temp", exist_ok=True)

        downloaded = False

        cookie_args = []
        if os.path.exists("cookies.txt"):
            cookie_args = ["--cookies", "cookies.txt"]
        elif os.path.exists("../cookies.txt"):
            cookie_args = ["--cookies", "../cookies.txt"]

        # ==================== TIKTOK ====================
        if "tiktok.com" in video_url.lower():
            # subprocess với impersonate (chuẩn yt-dlp 2026 với curl_cffi)
            targets = ['chrome', 'chrome-131', 'chrome:windows']

            # --- KIỂM TRA ẢNH TRƯỚC KHI TẢI ---
            check_cmd = [YTDLP_BIN, '--dump-json', '--impersonate', targets[0], '--add-header', 'Accept-Language:vi-VN,vi;q=0.9,en;q=0.8', '--no-warnings'] + cookie_args + [video_url]
            try:
                check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=45)
                if check_result.returncode == 0:
                    info = json.loads(check_result.stdout.strip().split('\n')[-1])
                    if info.get("vcodec") == "none" or info.get("video_ext") == "none" or "photo" in info.get("webpage_url", ""):
                        print(f"   ⏩ {tag}Phát hiện video dạng ẢNH. Đang bỏ qua...")
                        with sheet_lock:
                            try:
                                sheet = gspread.authorize(get_credentials()).open_by_key(SHEET_ID).worksheet(SHEET_NAME)
                                cell = sheet.find(video_url, in_column=5)
                                if cell:
                                    sheet.update_cell(cell.row, 2, "Bỏ qua (Ảnh)")
                                    sheet.update_cell(cell.row, 6, "Đã đăng")
                                    sheet.update_cell(cell.row, 7, "Đã xóa")
                            except: pass
                        return
                else:
                    err_msg = check_result.stderr.lower()
                    if "unable to extract webpage video data" in err_msg or "no video formats found" in err_msg:
                        print(f"   ⏩ {tag}Không thể trích xuất dữ liệu. Đang bỏ qua...")
                        with sheet_lock:
                            try:
                                sheet = gspread.authorize(get_credentials()).open_by_key(SHEET_ID).worksheet(SHEET_NAME)
                                cell = sheet.find(video_url, in_column=5)
                                if cell:
                                    sheet.update_cell(cell.row, 2, "Bỏ qua (Lỗi trích xuất)")
                                    sheet.update_cell(cell.row, 6, "Đã đăng")
                                    sheet.update_cell(cell.row, 7, "Đã xóa")
                            except: pass
                        return
            except Exception as e:
                pass
            # -----------------------------------

            for target in targets:
                cmd = [
                    YTDLP_BIN,
                    '--impersonate', target,
                    '--add-header', 'Accept-Language:vi-VN,vi;q=0.9,en;q=0.8',
                    '-f', 'best[ext=mp4]/best',
                    '--merge-output-format', 'mp4',
                    '--no-warnings',
                ] + cookie_args + [
                    '-o', video_path,
                    video_url
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

                if result.returncode == 0 and os.path.exists(video_path) and os.path.getsize(video_path) > 20_000:
                    downloaded = True
                    break
                else:
                    if os.path.exists(video_path):
                        os.remove(video_path)

            # Fallback
            if not downloaded:
                try:
                    ydl_opts = {
                        "format": "best[ext=mp4]/best",
                        "outtmpl": video_path,
                        "quiet": True,
                        "http_headers": {"Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"},
                    }
                    if os.path.exists("cookies.txt"):
                        ydl_opts["cookiefile"] = "cookies.txt"
                    elif os.path.exists("../cookies.txt"):
                        ydl_opts["cookiefile"] = "../cookies.txt"
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([video_url])

                    if os.path.exists(video_path) and os.path.getsize(video_path) > 20_000:
                        downloaded = True
                except Exception as e2:
                    pass

        # ==================== YOUTUBE ====================
        else:
            if os.path.exists(video_path) and os.path.getsize(video_path) > 20_000:
                downloaded = True
            else:
                for fmt in [PRIMARY_FORMAT, FALLBACK_FORMAT]:
                    cmd = [
                        YTDLP_BIN,
                        '--js-runtimes', f"node:{NODE_PATH}",
                        '--extractor-args', 'youtube:player_client=android,web;lang=vi',
                        '--add-header', 'Accept-Language:vi-VN,vi;q=0.9,en;q=0.8',
                        '-f', fmt,
                        '--merge-output-format', 'mp4',
                        '--no-warnings',
                    ] + cookie_args + [
                        '-o', f"temp/{video_id}.%(ext)s",
                        video_url
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if "429" in result.stderr or "robot" in result.stderr.lower() or "sign in to confirm you're not a bot" in result.stderr.lower():
                        with storage_lock:
                            if not storage_full_alerted:
                                storage_full_alerted = True
                                storage_pause_flag = True
                                print(f"\n⚠️ {tag}YouTube phát hiện tải nhanh và tạm thời giới hạn IP (HTTP 429 / Bot check).")
                                print("➡️ Hệ thống đã TỰ ĐỘNG TẠM NGỪNG để IP hạ nhiệt (không spam request).\n")
                        break
                    for ext in ["mp4", "mkv", "webm"]:
                        tmp = f"temp/{video_id}.{ext}"
                        if os.path.exists(tmp):
                            if ext != "mp4":
                                subprocess.run(["ffmpeg", "-i", tmp, video_path, "-y"], capture_output=True)
                                os.remove(tmp)
                            else:
                                if tmp != video_path:
                                    os.rename(tmp, video_path)
                            break
                    if os.path.exists(video_path) and os.path.getsize(video_path) > 20_000:
                        downloaded = True
                        break

        # ==================== KIỂM TRA DUNG LƯỢNG & UPLOAD CLOUD ====================
        if downloaded and os.path.exists(video_path):
            file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
            
            # Đánh giá dung lượng: Nếu > 90MB thì bỏ qua và đánh dấu vào cột J
            if file_size_mb > 90:
                print(f"   {tag}⚠️ File {video_id} có dung lượng {file_size_mb:.2f} MB > 90MB! Bỏ qua không upload.")
                with sheet_lock:
                    for _ in range(3):
                        try:
                            sheet = gspread.authorize(get_credentials()).open_by_key(SHEET_ID).worksheet(SHEET_NAME)
                            cell = sheet.find(video_url, in_column=5)
                            if cell:
                                sheet.update_cell(cell.row, 10, ">90MB")  # Cột J
                            break
                        except Exception:
                            sleep(2)
            else:
                direct_link = upload_video_file(video_path, video_id)
                if direct_link:
                    with sheet_lock:
                        for _ in range(3):
                            try:
                                sheet = gspread.authorize(get_credentials()).open_by_key(SHEET_ID).worksheet(SHEET_NAME)
                                cell = sheet.find(video_url, in_column=5)
                                if cell:
                                    sheet.update_cell(cell.row, 2, direct_link)   # Cột B = Link file
                                    sheet.update_cell(cell.row, 10, "")            # Cột J để trống nếu <= 90MB
                                break
                            except Exception:
                                sleep(2)
                    print(f"   {tag}✓ HOÀN THÀNH & UPLOAD ({file_size_mb:.1f} MB): {video['title'][:60]}")
                else:
                    print(f"   {tag}✗ Upload thất bại")
        else:
            print(f"   {tag}✗ Không tải được file video")

        # Dọn dẹp
        if os.path.exists(video_path):
            os.remove(video_path)

    except Exception as e:
        print(f"   {tag}✗ Lỗi: {e}")




def reorder_sheet_rows(sheet_name=SHEET_NAME):
    """
    Sắp xếp lại sheet:
    - Các dòng có Link file hợp lệ (sẵn sàng đăng Reels) đưa lên ĐẦU.
    - Các dòng không tải được / lỗi / >90MB / chưa có link đưa xuống CUỐI để Make.com không bị lỗi.
    """
    print(f"\n🔄 Đang sắp xếp lại thứ tự dòng trong sheet '{sheet_name}'...")
    try:
        sheet = gspread.authorize(get_credentials()).open_by_key(SHEET_ID).worksheet(sheet_name)
        rows = sheet.get_all_values()
        if len(rows) <= 1:
            return
        
        header = rows[0]
        data_rows = [r for r in rows[1:] if any(r)]
        
        valid_rows = []
        pending_failed_rows = []
        
        for r in data_rows:
            link_file = r[1].strip() if len(r) > 1 else ""
            over_90 = r[9].strip() if len(r) > 9 else ""
            
            # Tiêu chí dòng hợp lệ: có link file, không phải 'bỏ qua', không phải >90MB
            if link_file and not link_file.lower().startswith("bỏ qua") and ">90" not in over_90:
                valid_rows.append(r)
            else:
                pending_failed_rows.append(r)
                
        sorted_rows = [header] + valid_rows + pending_failed_rows
        max_cols = max(len(r) for r in sorted_rows)
        padded_rows = [r + [""] * (max_cols - len(r)) for r in sorted_rows]
        
        sheet.update(range_name="A1", values=padded_rows, value_input_option="USER_ENTERED")
        print(f"✔ Đã sắp xếp xong: {len(valid_rows)} dòng có link ở đầu, {len(pending_failed_rows)} dòng chưa có link/lỗi ở cuối.")
    except Exception as e:
        print(f"Lỗi khi sắp xếp sheet: {e}")

def main():
    print(f"=== YouTube & TikTok Auto Downloader Started (ĐA LUỒNG: {MAX_WORKERS} Workers) ===")
    try:
        delete_dropbox_file_if_posted()
        cleanup_dropbox_orphaned_files()

        pending = get_pending_videos()
        limit = TEST_VIDEOS if TEST_MODE else (len(pending) if FULL_DOWNLOAD else MAX_VIDEOS_PER_DAY)

        if pending:
            target_pending = pending[:limit]
            tot = len(target_pending)
            print(f"\n🚀 Đang xử lý {tot} video pending với {MAX_WORKERS} luồng đồng thời...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [executor.submit(download_and_upload_video, v, i, tot) for i, v in enumerate(target_pending, 1)]
                concurrent.futures.wait(futures)

        if not storage_pause_flag:
            print("\n=== QUÉT KÊNH MỚI ===")
            videos = fetch_all_metadata()
            existing = {v.strip() for v in gspread.authorize(get_credentials())
                                           .open_by_key(SHEET_ID).worksheet(SHEET_NAME).col_values(5)[1:]}
            new_videos = save_metadata_to_sheets(videos, existing)

            if new_videos and not storage_pause_flag:
                target_new = new_videos[:limit]
                tot = len(target_new)
                print(f"\n🚀 Đang tải và upload {tot} video mới với {MAX_WORKERS} luồng đồng thời...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    futures = [executor.submit(download_and_upload_video, v, i, tot) for i, v in enumerate(target_new, 1)]
                    concurrent.futures.wait(futures)

        if storage_pause_flag:
            print("\n⚠️ [TẠM DỪNG] Hệ thống tạm ngừng do dung lượng Cloud đã đầy.")
        else:
            finish_msg = "🎉 [HOÀN THÀNH TẤT CẢ]\nĐã tải và upload video YouTube Shorts lên Cloud và Google Sheet thành công!"
            print(f"\n=== {finish_msg} ===")
            reorder_sheet_rows(SHEET_NAME)
            notify_telegram(finish_msg)
    except Exception as e:
        print(f"Lỗi lớn: {traceback.format_exc()}")


if __name__ == "__main__":
    main()