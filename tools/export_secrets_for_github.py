# -*- coding: utf-8 -*-
"""
Công cụ xuất toàn bộ file cấu hình và token Google Drive thành 1 chuỗi Base64 duy nhất
để bạn dán vào GitHub Repository Secrets (PROJECT_SECRETS_BASE64).
"""

import os
import sys
import json
import base64
import glob

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == "tools" else BASE_DIR

def main():
    print("=" * 65)
    print("🔐 CÔNG CỤ TẠO GITHUB SECRET DUY NHẤT (PROJECT_SECRETS_BASE64)")
    print("=" * 65)
    
    bundle = {}
    
    # 1. Credentials & Client Secret
    for fname in ["credentials.json", "client_secret.json"]:
        p = os.path.join(PROJECT_ROOT, fname)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                bundle[fname] = json.load(f)
            print(f"✔ Đã đóng gói: {fname}")
        else:
            print(f"⚠️ Thiếu file: {fname}")
            
    # 2. Toàn bộ file token
    tokens_dir = os.path.join(PROJECT_ROOT, "tokens")
    token_files = glob.glob(os.path.join(tokens_dir, "*.json"))
    # Cả tokens ở root nếu có
    token_files += glob.glob(os.path.join(PROJECT_ROOT, "token*.json"))
    
    added_tokens = set()
    for tf in token_files:
        basename = os.path.basename(tf)
        if basename in added_tokens:
            continue
        try:
            with open(tf, "r", encoding="utf-8") as f:
                bundle[basename] = json.load(f)
            print(f"✔ Đã đóng gói token: {basename}")
            added_tokens.add(basename)
        except Exception as e:
            print(f"⚠️ Lỗi đọc {tf}: {e}")
            
    if not bundle:
        print("❌ Không tìm thấy file bí mật nào để đóng gói!")
        return

    # Mã hóa sang Base64
    json_bytes = json.dumps(bundle, ensure_ascii=False).encode("utf-8")
    b64_str = base64.b64encode(json_bytes).decode("utf-8")
    
    # Lưu ra file tạm để copy nếu chuỗi quá dài
    out_txt = os.path.join(PROJECT_ROOT, "PROJECT_SECRETS_BASE64.txt")
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(b64_str)
        
    print("\n" + "=" * 65)
    print("🎉 ĐÃ TẠO CHUỖI SECRET THÀNH CÔNG!")
    print(f"📁 Chuỗi secret đã được lưu vào file tạm: PROJECT_SECRETS_BASE64.txt")
    print("=" * 65)
    print("\n👉 CÁCH DÙNG TRÊN GITHUB:")
    print("1. Vào GitHub repo của bạn -> Bấm tab 'Settings' -> 'Secrets and variables' -> 'Actions'")
    print("2. Bấm nút 'New repository secret'")
    print("3. Điền:")
    print("   - Name : PROJECT_SECRETS_BASE64")
    print("   - Secret: [Copy toàn bộ nội dung trong file PROJECT_SECRETS_BASE64.txt dán vào đây]")
    print("4. Bấm 'Add secret' là XONG!")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()
