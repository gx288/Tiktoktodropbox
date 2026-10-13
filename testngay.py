import yt_dlp
from datetime import datetime


def test_date_extraction():
    print("=== TEST LẤY NGÀY TỪ TIKTOK ===\n")

    urls = [
        "https://www.tiktok.com/@dong_y_son_ha",
        "https://www.tiktok.com/@dongysonha"
    ]

    for url in urls:
        print(f"Đang test kênh: {url}")
        print("=" * 80)

        ydl_opts = {
            "dump_single_json": True,
            "extract_flat": False,  # Quan trọng: phải False để lấy full info
            "quiet": False,
            "no_warnings": True,
            "playlistend": 8,  # Chỉ lấy 8 video đầu để test
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=False)

            entries = result.get("entries", [])[:8]

            print(f"Tìm thấy {len(result.get('entries', []))} video")
            print(f"Test {len(entries)} video đầu tiên:\n")

            for i, entry in enumerate(entries, 1):
                title = entry.get("title", "No title")[:70]
                print(f"{i:2d}. {title}")

                print(f"   upload_date     : {entry.get('upload_date')}")
                print(f"   timestamp       : {entry.get('timestamp')}")
                print(f"   release_date    : {entry.get('release_date')}")
                print(f"   upload_timestamp: {entry.get('upload_timestamp')}")

                # Thử convert timestamp sang ngày
                ts = entry.get("timestamp")
                if ts:
                    try:
                        date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                        print(f"   → Converted     : {date_str}")
                    except:
                        print("   → Converted     : Lỗi")
                print("-" * 70)

        except Exception as e:
            print(f"Lỗi: {e}")
        print("\n")


if __name__ == "__main__":
    test_date_extraction()