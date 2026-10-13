import requests
import re
resp = requests.get('https://www.tiktok.com/@dong_y_son_ha/video/7530158972507163912', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
print("Final URL:", resp.url)
match = re.search(r'<link rel="canonical" href="(.*?)"', resp.text)
if match:
    print("Canonical:", match.group(1))
