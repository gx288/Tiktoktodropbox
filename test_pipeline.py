import os
import sys
import json
import re
import subprocess
import dropbox
import gspread
from google.oauth2.service_account import Credentials

sys.stdout.reconfigure(encoding='utf-8')

from config import SHEET_ID, DROPBOX_REFRESH_TOKEN, DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_FOLDER_PATH

SHEET_NAME = "Reels"
YTDLP_BIN = "yt-dlp"

CHANNELS = [
    {"name": "TikTok @hang_zhou102", "url": "https://www.tiktok.com/@hang_zhou102"},
    {"name": "TikTok @funnyclip.viral", "url": "https://www.tiktok.com/@funnyclip.viral"},
    {"name": "TikTok @catorahub", "url": "https://www.tiktok.com/@catorahub"}
]

def get_credentials():
    with open("credentials.json", "r", encoding='utf-8') as f:
        return Credentials.from_service_account_info(json.load(f), scopes=["https://www.googleapis.com/auth/spreadsheets"])

def get_dropbox_client():
    return dropbox.Dropbox(oauth2_refresh_token=DROPBOX_REFRESH_TOKEN, app_key=DROPBOX_APP_KEY, app_secret=DROPBOX_APP_SECRET)

def upload_to_dropbox(video_path, video_id):
    dbx = get_dropbox_client()
    path = f"{DROPBOX_FOLDER_PATH}/{video_id}.mp4"
    print(f"   ☁️ Đang upload lên Dropbox: {path}...")
    with open(video_path, "rb") as f:
        dbx.files_upload(f.read(), path, mode=dropbox.files.WriteMode("overwrite"))
    
    link = dbx.sharing_create_shared_link_with_settings(path).url
    direct_link = link.replace("www.dropbox.com", "dl.dropboxusercontent.com")
    direct_link = re.sub(r'([?&])dl=0', r'\1dl=1', direct_link)
    return direct_link

def clean_title(title):
    title = re.sub(r"#youtube|#shorts", "", str(title), flags=re.IGNORECASE).strip()
    if "#reels" not in title.lower():
        title += " #reels"
    return re.sub(r"\s+", " ", title).strip()

def main():
    print("=" * 60)
    print("🚀 BẮT ĐẦU TEST PIPELINE: 3 KÊNH TIKTOK MỚI")
    print("=" * 60)

    gc = gspread.authorize(get_credentials())
    sheet = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    os.makedirs("temp", exist_ok=True)

    test_videos = []

    for ch in CHANNELS:
        print(f"\n🔍 Đang quét kênh: {ch['name']} ({ch['url']})...")
        cmd = [
            YTDLP_BIN,
            '--impersonate', 'chrome',
            '--dump-json',
            '--flat-playlist',
            '--playlist-items', '1-2',
            '--no-warnings',
            ch["url"]
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode == 0:
            lines = [l for l in res.stdout.strip().split('\n') if l.strip()]
            for l in lines:
                data = json.loads(l)
                vid_id = data.get("id")
                if vid_id:
                    v_url = data.get("webpage_url") or data.get("url") or f"https://www.tiktok.com/@{ch['name'].split('@')[-1]}/video/{vid_id}"
                    test_videos.append({
                        "channel": ch["name"],
                        "id": vid_id,
                        "title": clean_title(data.get("title", "Video " + vid_id)),
                        "url": v_url
                    })
                    break # Lấy 1 video cho mỗi kênh để test
        else:
            print(f"❌ Lỗi quét {ch['name']}: {res.stderr[:200]}")

    print(f"\n📦 Tìm thấy {len(test_videos)} video để test:")
    for v in test_videos:
        print(f"  - [{v['channel']}] ID: {v['id']} | {v['title'][:40]}")

    # Tiến hành tải, upload Dropbox, ghi vào Google Sheet
    for i, video in enumerate(test_videos, 1):
        print(f"\n--- [{i}/{len(test_videos)}] Xử lý: {video['title'][:50]} ---")
        video_id = video["id"]
        video_url = video["url"]
        video_path = f"temp/{video_id}.mp4"

        print(f"   ⬇️ Đang tải video từ TikTok...")
        dl_cmd = [
            YTDLP_BIN,
            '--impersonate', 'chrome',
            '-f', 'best[ext=mp4]/best',
            '--merge-output-format', 'mp4',
            '--no-warnings',
            '-o', video_path,
            video_url
        ]
        dl_res = subprocess.run(dl_cmd, capture_output=True, text=True, timeout=120)
        if dl_res.returncode == 0 and os.path.exists(video_path) and os.path.getsize(video_path) > 10_000:
            size_mb = os.path.getsize(video_path) / (1024 * 1024)
            print(f"   ✅ Tải thành công! Kích thước: {size_mb:.2f} MB")
            
            # Upload lên Dropbox
            direct_link = upload_to_dropbox(video_path, video_id)
            print(f"   🔗 Direct Link Dropbox: {direct_link}")

            # Thêm dòng vào Google Sheet
            # Cấu trúc: ['Title', 'Link file', 'thumbnail', 'length', 'link youtube videos', 'Đã đăng', 'Đã xóa']
            new_row = [video["title"], direct_link, "", "", video_url, "", ""]
            sheet.append_row(new_row)
            print(f"   📝 Đã ghi vào Google Sheet 'Reels'!")

            # Xóa file tạm máy tính cục bộ
            if os.path.exists(video_path):
                os.remove(video_path)
                print(f"   🧹 Đã dọn dẹp file tạm trên máy cục bộ.")
        else:
            print(f"   ❌ Tải thất bại: {dl_res.stderr[:200]}")

    print("\n" + "=" * 60)
    print("🎉 HOÀN THÀNH TEST PIPELINE!")
    print("=" * 60)

if __name__ == "__main__":
    main()
