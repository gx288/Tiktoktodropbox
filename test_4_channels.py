import yt_dlp
import sys
import io

sys.stdout.reconfigure(encoding='utf-8')

urls = [
    "https://youtube.com/shorts/_P13akdxLcc",
    "https://www.youtube.com/@youtubelovethreads/shorts",
    "https://www.youtube.com/@VGbrands/shorts",
    "https://www.youtube.com/@chuyentramkem/shorts"
]

ydl_opts = {
    "dump_single_json": True,
    "extract_flat": True,
    "quiet": True,
    "playlistend": 500
}

for u in urls:
    print(f"\n=== Testing: {u} ===")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(u, download=False)
            if "entries" in res:
                entries = list(res.get("entries", []))
                print(f"Channel title: {res.get('title')} | Total videos found: {len(entries)}")
                for e in entries[:3]:
                    print("  - ID:", e.get("id"), "| Title:", e.get("title"))
            else:
                print("Single video: ID:", res.get("id"), "| Title:", res.get("title"))
    except Exception as e:
        print("Error:", e)
