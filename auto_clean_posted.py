import os
import sys
import io
import re
import time
import datetime
import argparse
import requests
import gspread
from google.oauth2.service_account import Credentials
import dropbox
from googleapiclient.errors import HttpError

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

from config import SHEET_ID, DROPBOX_ACCOUNTS, CLEANUP_ACCOUNTS, DROPBOX_FOLDER_PATH, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

TARGET_SHEETS = ["Reels", "Reels2", "Reels3"]
PROTECTED_SHEETS = ["Prother"]

def get_sheets_client():
    creds_path = os.path.join(BASE_DIR, "credentials.json")
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"Không tìm thấy credentials.json tại: {creds_path}")
    creds = Credentials.from_service_account_file(
        creds_path,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)

def get_drive_service():
    try:
        sys.path.append(BASE_DIR)
        sys.path.append(r"D:\AT\GoogleDrive_OAuth")
        import drive_uploader
        return drive_uploader.get_drive_service()
    except Exception as e:
        print(f"[Cảnh báo] Không thể khởi tạo Google Drive Service: {e}")
        return None

def get_dropbox_client(account):
    return dropbox.Dropbox(
        oauth2_refresh_token=account["refresh_token"],
        app_key=account["app_key"],
        app_secret=account["app_secret"]
    )

def notify_telegram(message):
    try:
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            resp = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=15)
            if resp.json().get("ok"):
                print("   [Telegram] Đã gửi thông báo thành công đến @hungleDKH.")
                return
    except Exception as e:
        print(f"   [Telegram Error] {e}")

def clean_sheet_posted_files(ss, sheet_name, drive_service):
    if sheet_name in PROTECTED_SHEETS:
        print(f"🔒 [BẢO VỆ TUYỆT ĐỐI] Sheet '{sheet_name}' nằm trong danh sách cấm xóa vĩnh viễn!")
        return 0, 0

    try:
        sheet = ss.worksheet(sheet_name)
    except Exception:
        print(f"[-] Bỏ qua: Không tìm thấy sheet '{sheet_name}'.")
        return 0, 0

    records = sheet.get_all_records()
    if not records:
        print(f"[-] Sheet '{sheet_name}' không có dữ liệu.")
        return 0, 0

    updates = []
    gdrive_deleted = 0
    dropbox_deleted = 0
    all_dropbox_accounts = DROPBOX_ACCOUNTS + CLEANUP_ACCOUNTS

    print(f"\n🔍 Đang quét sheet: '{sheet_name}' ({len(records)} dòng)...")

    for i, row in enumerate(records, start=2):
        da_dang = str(row.get("Đã đăng", "")).strip()
        da_xoa = str(row.get("Đã xóa", "")).strip().lower()
        link_fb = str(row.get("Link", "")).strip()
        link_file = str(row.get("Link file", "")).strip()
        yt_link = str(row.get("link youtube videos", "")).strip()
        title = str(row.get("Title", "Untitled"))[:40]

        if "prother" in title.lower() or "prother" in link_file.lower():
            continue

        is_posted = bool(da_dang or (link_fb and "facebook.com" in link_fb.lower()))

        if is_posted and da_xoa != "đã xóa":
            deleted_ok = False
            video_id = yt_link.split("/")[-1].split("?")[0] if yt_link else ""

            # 1. Nếu là file Google Drive
            if "drive.google.com" in link_file:
                m = re.search(r'id=([a-zA-Z0-9_-]+)', link_file) or re.search(r'/d/([a-zA-Z0-9_-]+)', link_file)
                if m:
                    file_id = m.group(1)
                    try:
                        import drive_uploader
                        ok, token_used = drive_uploader.delete_file_from_any_drive(file_id)
                        if ok:
                            print(f"   🗑️ [Google Drive - {token_used}] Đã xóa: {title} (ID: {file_id})")
                            gdrive_deleted += 1
                            deleted_ok = True
                        else:
                            print(f"   ℹ️ [Google Drive] Không tìm thấy file hoặc đã bị xóa trước: {title}")
                            deleted_ok = True
                    except Exception as e:
                        print(f"   ❌ [Google Drive] Lỗi: {e}")

            # 2. Nếu là file Dropbox
            elif "dropbox" in link_file or (not link_file and video_id):
                if video_id:
                    possible_paths = [
                        f"{DROPBOX_FOLDER_PATH}/{video_id}.mp4",
                        f"/{video_id}.mp4"
                    ]
                    for acc in all_dropbox_accounts:
                        try:
                            dbx = get_dropbox_client(acc)
                            for path in possible_paths:
                                try:
                                    dbx.files_delete_v2(path)
                                    print(f"   🗑️ [Dropbox - {acc['name']}] Đã xóa: {video_id}.mp4")
                                    dropbox_deleted += 1
                                    deleted_ok = True
                                    break
                                except dropbox.exceptions.ApiError as ae:
                                    if "not_found" in str(ae).lower():
                                        continue
                                    else:
                                        break
                            if deleted_ok:
                                break
                        except Exception:
                            continue
                else:
                    deleted_ok = True

            # Đánh dấu đã xóa vào Cột G
            updates.append({"range": f"G{i}", "values": [["Đã xóa"]]})

    if updates:
        sheet.batch_update(updates, value_input_option="USER_ENTERED")
        print(f"   ✔ Đã cập nhật trạng thái 'Đã xóa' cho {len(updates)} dòng trong '{sheet_name}'.")

    return gdrive_deleted, dropbox_deleted

def run_cleanup():
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 65)
    print(f"🧹 BẮT ĐẦU DỌN DẸP FILE ĐÃ ĐĂNG: {now_str}")
    print("=" * 65)

    try:
        ss_client = get_sheets_client()
        ss = ss_client.open_by_key(SHEET_ID)
    except Exception as e:
        print(f"❌ Lỗi kết nối Google Sheets: {e}")
        return

    drive_service = get_drive_service()

    total_gdrive = 0
    total_dropbox = 0

    for sheet_name in TARGET_SHEETS:
        g_del, d_del = clean_sheet_posted_files(ss, sheet_name, drive_service)
        total_gdrive += g_del
        total_dropbox += d_del

    total_deleted = total_gdrive + total_dropbox
    print("\n" + "=" * 65)
    print(f"🎉 TỔNG KẾT DỌN DẸP:")
    print(f"   - Google Drive : Đã xóa {total_gdrive} file")
    print(f"   - Dropbox      : Đã xóa {total_dropbox} file")
    print(f"   - Tổng số file : {total_deleted} file đã được dọn sạch!")
    print("=" * 65)

    if total_deleted > 0:
        msg = (
            f"🧹 [BÁO CÁO DỌN DẸP CLOUD]\n"
            f"Đã tự động xóa {total_deleted} video đã đăng thành công:\n"
            f"• Google Drive: {total_gdrive} file\n"
            f"• Dropbox: {total_dropbox} file\n"
            f"Bộ nhớ lưu trữ đã được giải phóng!"
        )
        notify_telegram(msg)
    else:
        print("ℹ️ Không có file nào mới cần xóa.")

def main():
    parser = argparse.ArgumentParser(description="Tool tự động xóa video đã đăng trên Cloud Storage")
    parser.add_argument("--loop", action="store_true", help="Chạy định kỳ lặp lại liên tục")
    parser.add_argument("--interval", type=int, default=1800, help="Thời gian nghỉ giữa các lần quét (giây), mặc định 1800s (30 phút)")
    args = parser.parse_args()

    if args.loop:
        print(f"🔄 Chế độ chạy lặp định kỳ kích hoạt. Khoảng cách kiểm tra: {args.interval} giây ({args.interval // 60} phút).")
        print("Nhấn Ctrl + C để dừng bất cứ lúc nào.\n")
        while True:
            try:
                run_cleanup()
            except Exception as e:
                print(f"Lỗi trong quá trình dọn dẹp: {e}")
            print(f"\n⏳ Đang chờ {args.interval} giây cho lần quét tiếp theo...")
            time.sleep(args.interval)
    else:
        run_cleanup()

if __name__ == '__main__':
    main()
