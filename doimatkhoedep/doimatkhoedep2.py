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
import shutil

# ==================== TỰ ĐỘNG TÌM FFMPEG ====================
def get_ffmpeg_path():
    custom_path = r"C:\ffmpeg\bin\ffmpeg.exe"
    if os.path.isfile(custom_path):
        print(f"→ Tìm thấy ffmpeg tại: {custom_path}")
        return custom_path
    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        print(f"→ Tìm thấy ffmpeg trong PATH: {ffmpeg_in_path}")
        return ffmpeg_in_path
    raise FileNotFoundError(
        "KHÔNG TÌM THẤY ffmpeg.exe!\n"
        "Tải và giải nén vào: C:\\ffmpeg\\bin\\ffmpeg.exe\n"
        "Link: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    )

FFMPEG_PATH = get_ffmpeg_path()

# ==================== NODE.JS PATH (quan trọng để tránh warning JS) ====================
NODE_PATH = r"C:\Program Files\nodejs\node.exe"
if not os.path.exists(NODE_PATH):
    print(f"⚠️  Không tìm thấy Node.js tại {NODE_PATH}. Script vẫn chạy nhưng có thể bị warning nhiều hơn.")

# ==================== CONFIG ====================
from config import SHEET_ID, DROPBOX_REFRESH_TOKEN, DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_FOLDER_PATH

CHANNELS = ["https://www.youtube.com/@doimatkhoedep/shorts"]
SHEET_NAME = "Doimatkhoedep"
TEST_MODE = False        # True = chỉ xử lý 5 video đầu để test
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"

# ==================== GOOGLE SHEETS ====================
def get_credentials():
    if not os.path.exists("credentials.json"):
        raise FileNotFoundError("Không thấy file credentials.json!")
    with open("credentials.json", "r", encoding="utf-8") as f:
        info = json.load(f)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    return Credentials.from_service_account_info(info, scopes=scopes)

def get_sheet():
    client = gspread.authorize(get_credentials())
    spreadsheet = client.open_by_key(SHEET_ID)
    try:
        sheet = spreadsheet.worksheet(SHEET_NAME)
        print(f"→ Tìm thấy tab: {SHEET_NAME}")
    except gspread.exceptions.WorksheetNotFound:
        print(f"→ Tạo tab mới: {SHEET_NAME}")
        sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=10)
        sheet.append_row([
            "Title", "Link file", "thumbnail", "length", "link youtube videos",
            "Đã đăng", "Đã xóa", "Thời lượng", "Kích thước (MB)"
        ])
        print("→ Đã tạo tab mới + header!")
    return sheet

def clean_title(title):
    if not title:
        title = "No Title"
    title = re.sub(r"#youtube|#shorts|#reel", "", title, flags=re.IGNORECASE).strip()
    title = title.split("|")[0].strip()
    if not title.lower().endswith("#reels"):
        title += " #reels"
    if "#doimatkhoedep" not in title.lower():
        title += " #doimatkhoedep"
    return title.strip()

# ==================== DROPBOX ====================
def get_dropbox_client():
    dbx = dropbox.Dropbox(
        oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
        app_key=DROPBOX_APP_KEY,
        app_secret=DROPBOX_APP_SECRET
    )
    dbx.check_user()
    return dbx

def upload_to_dropbox(local_path, title):
    dbx = get_dropbox_client()
    filename = f"{title}.mp4"
    remote_path = f"{DROPBOX_FOLDER_PATH}/{filename}"

    try:
        with open(local_path, "rb") as f:
            dbx.files_upload(f.read(), remote_path, mode=dropbox.files.WriteMode("overwrite"))
        print(f" ✅ Đã upload/overwrite: {title[:40]}...")
    except Exception as e:
        print(f" ❌ Upload lỗi: {e}")
        return ""

    # Lấy shared link (cải thiện một chút)
    try:
        shared_links = dbx.sharing_list_shared_links(path=remote_path).links
        if shared_links:
            link = shared_links[0].url
            print(" → Dùng lại link cũ")
        else:
            link = dbx.sharing_create_shared_link_with_settings(remote_path).url
            print(" → Tạo link mới")
    except dropbox.exceptions.ApiError as e:
        if hasattr(e.error, 'is_shared_link_already_exists') and e.error.is_shared_link_already_exists():
            try:
                link = dbx.sharing_get_shared_link_metadata(remote_path).url
                print(" → Lấy link từ file cũ")
            except:
                print(f" ❌ Lỗi lấy link: {e}")
                return ""
        else:
            print(f" ❌ Lỗi tạo link: {e}")
            return ""

    direct = link.replace("www.dropbox.com", "dl.dropboxusercontent.com").replace("?dl=0", "?dl=1")
    return direct

# ==================== NÉN VIDEO ====================
def compress_and_get_size(input_path, max_bitrate="500k"):
    output_path = input_path.rsplit(".", 1)[0] + "_reels.mp4"
    cmd = [
        FFMPEG_PATH, "-i", input_path,
        "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-c:v", "libx264", "-b:v", max_bitrate, "-maxrate", max_bitrate, "-bufsize", "1000k",
        "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart", "-y", output_path
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        if os.path.getsize(output_path) > 0:
            os.remove(input_path)
            os.rename(output_path, input_path)
        size_mb = round(os.path.getsize(input_path) / (1024*1024), 2)
        return input_path, size_mb
    except Exception as e:
        print(f" Nén video lỗi (vẫn dùng file gốc): {e}")
        size_mb = round(os.path.getsize(input_path) / (1024*1024), 2)
        return input_path, size_mb

# ==================== DỌN DẸP DROPBOX ====================
def delete_posted_files():
    print("\n=== DỌN DẸP: XÓA FILE ĐÃ ĐĂNG ===")
    sheet = get_sheet()
    records = sheet.get_all_records()
    dbx = get_dropbox_client()
    updates = []

    for idx, row in enumerate(records, start=2):
        da_dang = str(row.get("Đã đăng", "")).strip().lower()
        da_xoa = str(row.get("Đã xóa", "")).strip()
        title = str(row.get("Title", "")).strip()

        if da_dang == "đã đăng" and da_xoa != "Đã xóa" and title:
            remote_path = f"{DROPBOX_FOLDER_PATH}/{title}.mp4"
            try:
                dbx.files_delete_v2(remote_path)
                print(f" ✅ Đã xóa trên Dropbox: {title[:50]}...")
            except:
                pass

            updates.append({
                "range": f"G{idx}",
                "values": [["Đã xóa"]]
            })

    if updates:
        sheet.batch_update(updates, value_input_option="USER_ENTERED")
        print(f"→ Đã đánh dấu {len(updates)} file là ĐÃ XÓA trên Sheet")
    else:
        print("→ Không có file nào cần xóa")

# ==================== QUÉT VIDEO MỚI ====================
def fetch_and_add_new_videos():
    print("\nĐang quét video mới từ kênh YouTube...")
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "user_agent": USER_AGENT,
        "js_runtimes": {"node": {"path": NODE_PATH}},
        "extractor_args": {"youtube": {"player_client": ["web", "android"]}},
    }
    all_videos = []

    for channel in CHANNELS:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(channel, download=False)
                if info and "entries" in info:
                    for e in info["entries"]:
                        if e and e.get("id"):
                            all_videos.append({
                                "id": e["id"],
                                "title": clean_title(e.get("title", "No Title")),
                                "url": f"https://www.youtube.com/shorts/{e['id']}"
                            })
        except Exception as e:
            print(f" Lỗi quét kênh: {e}")

    sheet = get_sheet()
    all_values = sheet.get_all_values()
    existing_urls = {row[4] for row in all_values[1:] if len(row) > 4 and row[4]}

    new_videos = [v for v in all_videos if v["url"] not in existing_urls]

    if new_videos:
        rows = [[v["title"], "", "", 0, v["url"], "", "", "", ""] for v in new_videos]
        sheet.insert_rows(rows, row=2)
        print(f"→ ĐÃ THÊM {len(new_videos)} VIDEO MỚI LÊN ĐẦU SHEET!")
    else:
        print("→ Không có video mới.")
    return len(new_videos)

# ==================== TẢI + UPLOAD ====================
def get_pending_videos():
    sheet = get_sheet()
    records = sheet.get_all_records()
    pending = []
    for idx, row in enumerate(records, start=2):
        yt_url = str(row.get("link youtube videos", "")).strip()
        dropbox_link = str(row.get("Link file", "")).strip()
        if yt_url and "shorts/" in yt_url and not dropbox_link:
            video_id = yt_url.split("shorts/")[-1].split("?")[0]
            pending.append({
                "row": idx,
                "id": video_id,
                "title": clean_title(row.get("Title", "No Title")),
                "url": yt_url
            })
    print(f"→ Có {len(pending)} video đang chờ upload Dropbox")
    return pending

def download_and_upload(video):
    video_id = video["id"]
    final_path = f"temp/{video_id}.mp4"
    os.makedirs("temp", exist_ok=True)

    if not os.path.exists(final_path):
        ydl_opts = {
            "format": "bestvideo+bestaudio/best",   # linh hoạt hơn, giảm lỗi "only images"
            "outtmpl": f"temp/{video_id}.%(ext)s",
            "merge_output_format": "mp4",
            "quiet": True,
            "user_agent": USER_AGENT,
            "js_runtimes": {"node": {"path": NODE_PATH}},
            "extractor_args": {"youtube": {"player_client": ["web", "android"]}},
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video["url"]])
            # Đổi tên file về chuẩn
            for f in os.listdir("temp"):
                if f.startswith(video_id + "."):
                    os.rename(os.path.join("temp", f), final_path)
                    break
        except Exception as e:
            print(f" ❌ Tải lỗi {video_id}: {e}")
            return

    final_path, size_mb = compress_and_get_size(final_path, "500k")
    direct_link = upload_to_dropbox(final_path, video["title"])

    if direct_link:
        sheet = get_sheet()
        sheet.update_cell(video["row"], 2, direct_link)   # Cột B = Link file
        sheet.update_cell(video["row"], 9, f"{size_mb} MB")  # Cột I
        print(f" ✅ HOÀN TẤT [{size_mb} MB] {video['title'][:50]}...")
        if os.path.exists(final_path):
            os.remove(final_path)

# ==================== MAIN ====================
def main():
    print("=" * 60)
    print("   ĐỔI MẬT KHẨU ĐẸP – AUTO REELS – BẢN ĐÃ SỬA")
    print("=" * 60 + "\n")

    os.makedirs("temp", exist_ok=True)

    delete_posted_files()

    pending = get_pending_videos()
    if pending:
        print(f"\nBắt đầu xử lý {len(pending)} video đang chờ...\n")
        for i, v in enumerate(pending):
            if TEST_MODE and i >= 5:
                break
            print(f"[{i+1}/{len(pending)}]", end=" ")
            download_and_upload(v)
            sleep(5)

    print("\nĐang quét video mới (luôn chạy mỗi lần mở tool)...")
    new_count = fetch_and_add_new_videos()

    if new_count > 0 and not TEST_MODE:
        print(f"\nTự động xử lý {new_count} video mới vừa quét được...")
        sleep(3)
        pending = get_pending_videos()
        for i, v in enumerate(pending):
            print(f"[{i+1}/{len(pending)}] (mới)", end=" ")
            download_and_upload(v)
            sleep(5)

    print("\nHOÀN TẤT 100%! Tool đã làm hết việc rồi!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nLỖI: {traceback.format_exc()}")