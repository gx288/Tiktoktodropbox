import os
import json
import gspread
from google.oauth2.service_account import Credentials
import dropbox
import yt_dlp
import re
from time import sleep
import traceback
import subprocess

# Import config
from config import ANHMOE_API_KEY, SHEET_ID, DROPBOX_REFRESH_TOKEN, DROPBOX_APP_KEY, DROPBOX_APP_SECRET, \
    DROPBOX_FOLDER_PATH

# ====================== CONFIG ======================
CHANNELS = [
    "https://www.youtube.com/@dongysonha/shorts"
]
SHEET_NAME = "Reels"
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
FULL_DOWNLOAD = os.getenv("FULL_DOWNLOAD", "false").lower() == "true"
MAX_VIDEOS_PER_DAY = 20
TEST_VIDEOS = 30000
RETRY_ATTEMPTS = 30000
QUOTA_RETRY_ATTEMPTS = 3
QUOTA_RETRY_DELAY = 60
DOWNLOAD_RETRIES = 3
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
MAX_FILE_SIZE_MB = 50

# Format tối ưu hơn cho Shorts hiện tại (2026)
PRIMARY_FORMAT = "bestvideo+bestaudio[language=vi]/bestvideo+bestaudio[language^=vi]/bestvideo+bestaudio/best"
FALLBACK_FORMAT = "best[language=vi]/best[language^=vi]/best"

# Node.js path
NODE_PATH = r"C:\Program Files\nodejs\node.exe"


def debug_env():
    print(
        f"Debug: SHEET_ID={'set' if SHEET_ID else 'not set'}, DROPBOX_REFRESH_TOKEN={'set' if DROPBOX_REFRESH_TOKEN else 'not set'}, DROPBOX_FOLDER_PATH={DROPBOX_FOLDER_PATH}, TEST_MODE={TEST_MODE}, Node.js={'exists' if os.path.exists(NODE_PATH) else 'missing'}")


def get_credentials():
    print("Initializing Google Sheets credentials...")
    if not os.path.exists("credentials.json"):
        raise FileNotFoundError("Error: credentials.json not found.")
    try:
        with open("credentials.json", "r", encoding='utf-8') as f:
            credentials_info = json.load(f)
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        return Credentials.from_service_account_info(credentials_info, scopes=scopes)
    except Exception as e:
        print(f"Error loading credentials: {e}")
        raise


def clean_title(title):
    title = re.sub(r"#youtube|#shorts", "", title, flags=re.IGNORECASE).strip()
    if "#reels" not in title.lower():
        title += " #reels"
    if "#dongysonha" not in title.lower():
        title += " #dongysonha"
    return title


def get_dropbox_client():
    print("Initializing Dropbox client...")
    try:
        dbx = dropbox.Dropbox(
            oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
            app_key=DROPBOX_APP_KEY,
            app_secret=DROPBOX_APP_SECRET
        )
        dbx.check_user()
        return dbx
    except Exception as e:
        print(f"Error initializing Dropbox: {e}")
        raise


def get_pending_videos():
    print("Fetching pending videos from Google Sheets...")
    client = gspread.authorize(get_credentials())
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    records = sheet.get_all_records()
    pending = []
    for i, row in enumerate(records, start=2):
        youtube_url = row.get("link youtube videos", "").strip()
        anhmoe_url = row.get("Link file", "").strip()
        if youtube_url and not anhmoe_url and "youtube.com/shorts/" in youtube_url:
            video_id = youtube_url.split("shorts/")[-1].split("?")[0]
            pending.append({
                "id": video_id,
                "title": row.get("Title", "Untitled").strip(),
                "url": youtube_url,
            })
    print(f"Found {len(pending)} pending videos.")
    return pending


def get_downloaded_videos():
    print("Fetching downloaded video links...")
    client = gspread.authorize(get_credentials())
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    values = sheet.col_values(5)[1:]
    return [v.strip() for v in values if v.strip()]


def fetch_shorts_metadata():
    print("Fetching YouTube Shorts metadata...")
    ydl_opts = {
        "dump_single_json": True,
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
        "user_agent": USER_AGENT,
        "sleep_requests": 2,
        "js_runtimes": {"node": {"path": NODE_PATH}},
        "extractor_args": {"youtube": {"player_client": ["web", "android", "ios"], "lang": ["vi"]}},
        "http_headers": {"Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"},
    }
    videos = []
    for channel in CHANNELS:
        print(f"Processing channel: {channel}")
        for attempt in range(DOWNLOAD_RETRIES):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    result = ydl.extract_info(channel, download=False)
                    for entry in result["entries"]:
                        videos.append({
                            "id": entry.get("id", ""),
                            "title": entry.get("title", "Untitled"),
                            "url": f"https://www.youtube.com/shorts/{entry.get('id')}",
                        })
                    print(f"Found {len(result['entries'])} videos in {channel}")
                    break
            except Exception as e:
                print(f"Error fetching {channel}, attempt {attempt + 1}/{DOWNLOAD_RETRIES}: {e}")
                if attempt < DOWNLOAD_RETRIES - 1:
                    sleep(5)
    print(f"Total videos fetched: {len(videos)}")
    return videos


def save_metadata_to_sheets(videos, existing_urls):
    print("Saving new video metadata to Google Sheets...")
    client = gspread.authorize(get_credentials())
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    if not sheet.row_values(1):
        sheet.append_row(["Title", "Link file", "thumbnail", "length", "link youtube videos", "Đã đăng", "Đã xóa"])
    rows = []
    new_videos = []
    for video in videos:
        if video["url"] not in existing_urls:
            rows.append([clean_title(video["title"]), "", "", 0, video["url"], "", ""])
            new_videos.append(video)
    if rows:
        for attempt in range(QUOTA_RETRY_ATTEMPTS):
            try:
                sheet.append_rows(rows)
                print(f"Saved {len(rows)} new videos.")
                break
            except gspread.exceptions.APIError as e:
                if "Quota exceeded" in str(e):
                    print(f"Quota error, retrying in {QUOTA_RETRY_DELAY}s...")
                    sleep(QUOTA_RETRY_DELAY)
                else:
                    raise
    return new_videos


def upload_to_dropbox(video_path, title):
    dbx = get_dropbox_client()
    file_name = title + '.mp4'
    dropbox_path = f"{DROPBOX_FOLDER_PATH}/{file_name}"
    for attempt in range(RETRY_ATTEMPTS):
        try:
            with open(video_path, "rb") as f:
                dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode("overwrite"))
            shared_link = dbx.sharing_create_shared_link_with_settings(dropbox_path).url
            direct_link = shared_link.replace("www.dropbox.com", "dl.dropboxusercontent.com").replace("?dl=0", "?dl=1")
            return direct_link
        except dropbox.exceptions.ApiError as e:
            if "shared_link_already_exists" in str(e):
                shared_links = dbx.sharing_list_shared_links(path=dropbox_path).links
                if shared_links:
                    shared_link = shared_links[0].url
                    return shared_link.replace("www.dropbox.com", "dl.dropboxusercontent.com").replace("?dl=0", "?dl=1")
            if attempt < RETRY_ATTEMPTS - 1:
                sleep(5)
    return ""


def delete_dropbox_file_if_posted():
    print("=== DỌN DẸP DROPBOX: XÓA FILE ĐÃ ĐĂNG ===")
    client = gspread.authorize(get_credentials())
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    records = sheet.get_all_records()
    dbx = get_dropbox_client()

    rows_to_process = []
    for row_idx, row in enumerate(records, start=2):
        col_F = str(row.get("Đã đăng", "")).strip().lower()
        col_G = str(row.get("Đã xóa", "")).strip()
        if col_F == "đã đăng" and col_G != "Đã xóa":
            rows_to_process.append((row_idx, row))

    if not rows_to_process:
        print("→ Không có video nào cần xóa.")
        return

    print(f"→ Tìm thấy {len(rows_to_process)} video cần xử lý.")

    try:
        result = dbx.files_list_folder(DROPBOX_FOLDER_PATH)
        dropbox_files = {entry.name for entry in result.entries if isinstance(entry, dropbox.files.FileMetadata)}
        print(f"→ Có {len(dropbox_files)} file trong Dropbox.")
    except Exception as e:
        print(f"→ Lỗi liệt kê Dropbox: {e}")
        return

    updates = []
    for row_number, row in rows_to_process:
        title = str(row.get("Title", "")).strip()
        if not title:
            print(f"Row {row_number}: Title trống → Bỏ qua")
            continue

        file_name = title + ".mp4"
        dropbox_path = f"{DROPBOX_FOLDER_PATH}/{file_name}"

        print(f"\n→ Row {row_number}: '{title}'")

        if file_name in dropbox_files:
            try:
                print(f"   Đang xóa file: {file_name}")
                dbx.files_delete_v2(dropbox_path)
                print(f"   Xóa thành công!")
            except Exception as e:
                print(f"   XÓA THẤT BẠI: {e}")

        updates.append({
            "range": f"G{row_number}",
            "values": [["Đã xóa"]]
        })

    if updates:
        try:
            sheet.batch_update({
                "value_input_option": "USER_ENTERED",
                "data": updates
            })
            print(f"→ ĐÃ CẬP NHẬT THÀNH CÔNG {len(updates)} dòng!")
        except Exception as e:
            print(f"→ Batch update thất bại: {e}")
            print("→ Chuyển sang ghi từng dòng...")
            for update in updates:
                try:
                    sheet.update(
                        range_name=update["range"],
                        values=update["values"],
                        value_input_option="USER_ENTERED"
                    )
                    print(f"   Đã ghi: {update['range']}")
                except Exception as e2:
                    print(f"   Ghi lỗi tại {update['range']}: {e2}")


def convert_to_mp4(input_path, output_path):
    if input_path.endswith(".mp4"):
        return input_path
    try:
        subprocess.run(["ffmpeg", "-i", input_path, "-c:v", "libx264", "-c:a", "aac", output_path], check=True,
                       capture_output=True)
        os.remove(input_path)
        return output_path
    except Exception:
        return None


def download_and_upload_video(video):
    video_id = video['id']
    video_path = f"temp/{video_id}.mp4"
    temp_path = f"temp/{video_id}.%(ext)s"
    if not os.path.exists(video_path):
        ydl_opts = {
            "format": PRIMARY_FORMAT,
            "outtmpl": temp_path,
            "quiet": True,
            "user_agent": USER_AGENT,
            "js_runtimes": {"node": {"path": NODE_PATH}},
            "extractor_args": {"youtube": {"player_client": ["web", "android", "ios"], "lang": ["vi"]}},
            "http_headers": {"Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"},
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video["url"]])
        except:
            print(f"Primary format failed for {video_id}, trying fallback...")
            ydl_opts["format"] = FALLBACK_FORMAT
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video["url"]])

        for ext in ["mp4", "mkv", "webm"]:
            temp_file = f"temp/{video_id}.{ext}"
            if os.path.exists(temp_file):
                if ext != "mp4":
                    convert_to_mp4(temp_file, video_path)
                else:
                    os.rename(temp_file, video_path)
                break

    direct_link = upload_to_dropbox(video_path, video["title"])
    if direct_link:
        client = gspread.authorize(get_credentials())
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        cell = sheet.find(video["url"], in_column=5)
        if cell:
            sheet.update_cell(cell.row, 2, direct_link)
        if os.path.exists(video_path):
            os.remove(video_path)


def main():
    print("Starting YouTube Shorts Downloader...")
    try:
        debug_env()
        os.makedirs("temp", exist_ok=True)
        delete_dropbox_file_if_posted()  # ← Đã có hàm này
        pending_videos = get_pending_videos()
        limit = TEST_VIDEOS if TEST_MODE else (len(pending_videos) if FULL_DOWNLOAD else MAX_VIDEOS_PER_DAY)
        if pending_videos:
            for video in pending_videos[:limit]:
                download_and_upload_video(video)
                sleep(5)
        else:
            videos = fetch_shorts_metadata()
            downloaded = get_downloaded_videos()
            new_videos = save_metadata_to_sheets(videos, downloaded)
            for video in new_videos[:limit]:
                download_and_upload_video(video)
                sleep(5)
        print("Script completed successfully.")
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")


if __name__ == "__main__":
    main()