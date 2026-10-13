import os
import json
import subprocess
from pathlib import Path

# ==================== CONFIG TEST ====================
CHANNEL_URL = "https://www.tiktok.com/@dong_y_son_ha"
START_DATE = "2024-12-23"  # Lọc video từ ngày này
VIDEO_LIMIT = 8
DOWNLOAD_FORMAT = 'mp4'  # mp4 hoặc mp3

OUTPUT_DIR = "./test_tiktok_downloads"

# ==================== CẤU HÌNH YT-DLP ====================
YT_DLP_BASE = [
    'yt-dlp',
    '--no-warnings',
    '--retries', '3',
]


def main():
    print("=" * 70)
    print("          TEST TIKTOK - LỌC NGÀY (Style cũ)")
    print("=" * 70)
    print(f"Kênh: {CHANNEL_URL}")
    print(f"Lọc từ ngày: {START_DATE}")
    print(f"Giới hạn: {VIDEO_LIMIT} video\n")

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # ====================== LẤY DANH SÁCH ======================
    print("Đang lấy danh sách video...")
    cmd_info = YT_DLP_BASE + [
        '--dump-json',
        '--flat-playlist',
        '--dateafter', START_DATE.replace('-', ''),  # ← Lọc ngày
        '--playlist-items', f'1-{VIDEO_LIMIT + 30}',
        CHANNEL_URL
    ]

    try:
        result = subprocess.run(cmd_info, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            print("❌ Lỗi lấy danh sách:")
            print(result.stderr[:400])
            return

        videos = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                try:
                    videos.append(json.loads(line))
                except:
                    continue

        print(f"✅ Tìm thấy {len(videos)} video sau lọc ngày {START_DATE}\n")

    except Exception as e:
        print(f"Lỗi lấy thông tin: {e}")
        return

    # ====================== TẢI VIDEO ======================
    print("Bắt đầu tải video...\n")
    for idx, video in enumerate(videos[:VIDEO_LIMIT], 1):
        url = video.get('webpage_url') or video.get('url')
        title = video.get('title', 'video')[:60]
        duration = video.get('duration', 0)
        views = video.get('view_count', 0)
        upload_date = video.get('upload_date', 'N/A')

        print(f"[{idx}/{VIDEO_LIMIT}] {title}")
        print(f"    📅 {upload_date} | 👁️ {views:,} | ⏱️ {duration}s")

        try:
            if DOWNLOAD_FORMAT == 'mp3':
                cmd = YT_DLP_BASE + [
                    '-x', '--audio-format', 'mp3',
                    '--audio-quality', '192',
                    '-o', os.path.join(OUTPUT_DIR, '%(title)s.%(ext)s'),
                    url
                ]
            else:
                cmd = YT_DLP_BASE + [
                    '-f', 'best[ext=mp4]/best',
                    '--merge-output-format', 'mp4',
                    '-o', os.path.join(OUTPUT_DIR, '%(title)s.%(ext)s'),
                    url
                ]

            dl_result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

            if dl_result.returncode == 0:
                print("    ✅ Tải thành công\n")
            else:
                print(f"    ❌ Lỗi: {dl_result.stderr[:150]}\n")

        except Exception as e:
            print(f"    ❌ Exception: {e}\n")

    print("=" * 70)
    print(f"HOÀN TẤT! Kiểm tra thư mục: {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()