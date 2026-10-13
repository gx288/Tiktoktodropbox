import sys
import json
import time
sys.stdout.reconfigure(encoding='utf-8')

import gspread
import yt_dlp
from google.oauth2.service_account import Credentials
from config import SHEET_ID

def main():
    print("=" * 60)
    print("🚀 BẮT ĐẦU CẬP NHẬT TIÊU ĐỀ TIẾNG VIỆT & CHUYỂN DỮ LIỆU REELS2 -> REELS3")
    print("=" * 60)

    creds = Credentials.from_service_account_file('credentials.json', scopes=['https://www.googleapis.com/auth/spreadsheets'])
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SHEET_ID)

    ws2 = spreadsheet.worksheet('Reels2')
    ws3 = spreadsheet.worksheet('Reels3')

    rows2 = ws2.get_all_values()
    rows3 = ws3.get_all_values()

    # 1. Backup dữ liệu
    backup_data = {
        'reels2': rows2,
        'reels3': rows3,
        'timestamp': time.time()
    }
    with open('backup_reels2_reels3.json', 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    print("✔ Đã sao lưu dữ liệu hiện tại vào file 'backup_reels2_reels3.json'.")

    # 2. Quét map tiêu đề Tiếng Việt từ 2 kênh
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'extractor_args': {'youtube': {'lang': ['vi']}},
        'http_headers': {'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8'},
        'playlistend': 600
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        print("\n⏳ Đang lấy map tiêu đề Tiếng Việt kênh @TôiđilụmtrênThreads...")
        res_threads = ydl.extract_info('https://www.youtube.com/@TôiđilụmtrênThreads/shorts', download=False)
        map_threads = {e['id']: e['title'] for e in res_threads.get('entries', []) if 'id' in e and 'title' in e}
        print(f"✔ Đã lấy {len(map_threads)} tiêu đề kênh Threads.")

        print("\n⏳ Đang lấy map tiêu đề Tiếng Việt kênh @TaKhongNgu...")
        res_takhongngu = ydl.extract_info('https://www.youtube.com/@TaKhongNgu/shorts', download=False)
        map_takhongngu = {e['id']: e['title'] for e in res_takhongngu.get('entries', []) if 'id' in e and 'title' in e}
        print(f"✔ Đã lấy {len(map_takhongngu)} tiêu đề kênh TaKhongNgu.")

    full_map = {**map_threads, **map_takhongngu}

    # 3. Xử lý Reels2 (Hàng 2 -> 115 là Threads)
    print("\n⏳ Đang cập nhật tiêu đề Tiếng Việt cho Reels2 (114 video Threads)...")
    threads_updates = []
    for r_idx in range(2, 116): # row 2 to 115
        row_val = rows2[r_idx - 1]
        url = row_val[4] if len(row_val) > 4 else ''
        vid_id = url.split('/')[-1].split('?')[0]
        vi_title = full_map.get(vid_id, row_val[0])
        threads_updates.append({
            'range': f'A{r_idx}',
            'values': [[vi_title]]
        })

    ws2.batch_update(threads_updates)
    print(f"✔ Đã cập nhật thành công {len(threads_updates)} tiêu đề Tiếng Việt cho Reels2!")

    # 4. Chuyển các hàng TaKhongNgu (Hàng 116 -> 167 trong Reels2) sang Reels3
    takhongngu_rows = rows2[115:167]
    print(f"\n⏳ Chuẩn bị chuyển {len(takhongngu_rows)} hàng TaKhongNgu từ Reels2 sang Reels3...")

    # Cập nhật tiêu đề tiếng Việt cho các hàng TaKhongNgu này trước khi đưa vào Reels3
    formatted_takhongngu_rows = []
    for r in takhongngu_rows:
        # Chuẩn hóa độ dài 10 cột theo header Reels3: ['Title', 'Link file', 'thumbnail', 'length', 'link youtube videos', 'Đã đăng', 'Đã xóa', '', 'Link', '>90MB']
        row_10 = (r + [''] * 10)[:10]
        url = row_10[4]
        vid_id = url.split('/')[-1].split('?')[0]
        row_10[0] = full_map.get(vid_id, row_10[0]) # Cập nhật title tiếng Việt
        formatted_takhongngu_rows.append(row_10)

    # Thêm vào Reels3
    ws3.append_rows(formatted_takhongngu_rows, value_input_option='USER_ENTERED')
    print(f"✔ Đã thêm {len(formatted_takhongngu_rows)} hàng TaKhongNgu vào Reels3.")

    # Cập nhật tiêu đề tiếng Việt cho 4 hàng cũ sẵn có trong Reels3 (Hàng 2 -> 5)
    reels3_existing_updates = []
    for r_idx in range(2, len(rows3) + 1):
        if r_idx - 1 < len(rows3):
            r = rows3[r_idx - 1]
            if any(r):
                url = r[4] if len(r) > 4 else ''
                vid_id = url.split('/')[-1].split('?')[0]
                vi_title = full_map.get(vid_id, r[0])
                reels3_existing_updates.append({
                    'range': f'A{r_idx}',
                    'values': [[vi_title]]
                })
    if reels3_existing_updates:
        ws3.batch_update(reels3_existing_updates)
        print(f"✔ Đã cập nhật tiêu đề tiếng Việt cho {len(reels3_existing_updates)} hàng cũ trong Reels3.")

    # 5. Xóa các hàng TaKhongNgu khỏi Reels2 (từ hàng 116 đến 167)
    print("\n⏳ Đang xóa 52 hàng TaKhongNgu khỏi Reels2 để Reels2 chỉ giữ lại kênh Threads...")
    ws2.delete_rows(116, 167)
    print("✔ Đã xóa các hàng TaKhongNgu khỏi Reels2.")

    print("\n" + "=" * 60)
    print("🎉 HOÀN TẤT DỌN DẸP & ĐỒNG BỘ TIÊU ĐỀ TIẾNG VIỆT!")
    print("=" * 60)

if __name__ == '__main__':
    main()
