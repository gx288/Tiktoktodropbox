import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import json
import gspread
from google.oauth2.service_account import Credentials
import dropbox
import datetime
from config import SHEET_ID, DROPBOX_REFRESH_TOKEN, DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_FOLDER_PATH

SHEET_NAME = "Reels"
CHANNEL_CONFIGS = [
    {"url": "https://www.youtube.com/@dongysonha/shorts", "platform": "youtube", "start_date": "2024-12-23", "name": "YouTube Main"},
    {"url": "https://www.tiktok.com/@dong_y_son_ha", "platform": "tiktok", "start_date": "2024-12-23", "name": "TikTok @dong_y_son_ha"},
    {"url": "https://www.tiktok.com/@dongysonha", "platform": "tiktok", "start_date": "2025-01-20", "name": "TikTok @dongysonha"},
]

def get_credentials():
    with open("credentials.json", "r", encoding='utf-8') as f:
        return Credentials.from_service_account_info(json.load(f), scopes=["https://www.googleapis.com/auth/spreadsheets"])

def get_dropbox_client():
    return dropbox.Dropbox(oauth2_refresh_token=DROPBOX_REFRESH_TOKEN, app_key=DROPBOX_APP_KEY, app_secret=DROPBOX_APP_SECRET)

def main():
    print("Bắt đầu quét Sheet để xóa các video quá hạn (cũ hơn start_date)...")
    dbx = get_dropbox_client()
    gc = gspread.authorize(get_credentials())
    sheet = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    records = sheet.get_all_records()
    
    updates = []
    
    # Map username to start_date_ts
    tiktok_limits = {}
    for cfg in CHANNEL_CONFIGS:
        if cfg["platform"] == "tiktok":
            username = cfg["url"].rstrip("/").split("/")[-1]
            ts = datetime.datetime.strptime(cfg["start_date"], "%Y-%m-%d").timestamp()
            tiktok_limits[username] = ts

    deleted_count = 0
    skipped_count = 0

    for i, row in enumerate(records, start=2):
        da_xoa = str(row.get("Đã xóa", "")).strip()
        if da_xoa == "Đã xóa":
            continue
            
        link = str(row.get("link youtube videos", "")).strip()
        if not link or "tiktok.com" not in link:
            continue
            
        try:
            parts = link.split("/")
            video_id_str = parts[-1].split("?")[0]
            if not video_id_str.isdigit():
                continue
                
            vid_ts = int(video_id_str) >> 32
            
            limit_ts = 0
            for uname, ts in tiktok_limits.items():
                if uname in link:
                    limit_ts = ts
                    break
                    
            if limit_ts > 0 and vid_ts < limit_ts:
                print(f"Phát hiện video quá hạn (timestamp {vid_ts} < {limit_ts}): {link}")
                
                # Xóa trên dropbox
                dropbox_path = f"{DROPBOX_FOLDER_PATH}/{video_id_str}.mp4"
                try:
                    dbx.files_delete_v2(dropbox_path)
                    print(f"   🗑️ Đã xóa file trên Dropbox: {video_id_str}.mp4")
                    deleted_count += 1
                except Exception as e:
                    if "not_found" not in str(e):
                        pass
                
                # Cập nhật sheet
                updates.append({"range": f"G{i}", "values": [["Đã xóa"]]})
                updates.append({"range": f"F{i}", "values": [["Đã đăng"]]})
                updates.append({"range": f"B{i}", "values": [["Bỏ qua (Quá hạn)"]]})
                skipped_count += 1
        except Exception as e:
            print(f"Lỗi phân tích {link}: {e}")
            
    if updates:
        sheet.batch_update(updates, value_input_option="USER_ENTERED")
        print(f"Đã cập nhật {skipped_count} dòng trên Sheet.")
        
    print(f"\n✅ Tổng kết: Đã xóa {deleted_count} file rác trên Dropbox, Đánh dấu bỏ qua {skipped_count} video trên Sheet.")

if __name__ == "__main__":
    main()
