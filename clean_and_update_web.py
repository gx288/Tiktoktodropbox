# -*- coding: utf-8 -*-
"""
Script dọn dẹp video đã đăng và cập nhật trang web theo dõi trạng thái Google Drive & Google Sheet.
Hỗ trợ chạy cục bộ hoặc tự động qua GitHub Actions.
"""

import os
import sys
import json
import base64
import datetime
import traceback
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# 1. Hỗ trợ giải nén Secret từ GitHub Actions nếu chạy trên Cloud runner
def unpack_github_secrets():
    secrets_b64 = os.getenv("PROJECT_SECRETS_BASE64", "").strip()
    if not secrets_b64:
        return
    try:
        print("🔑 Đang giải nén secrets từ biến môi trường GitHub Actions...")
        decoded = base64.b64decode(secrets_b64).decode("utf-8")
        data = json.loads(decoded)
        
        # Tạo thư mục tokens nếu chưa có
        os.makedirs(os.path.join(BASE_DIR, "tokens"), exist_ok=True)
        
        # Ghi các file token và credentials
        for fname, content in data.items():
            if fname.startswith("token"):
                fpath = os.path.join(BASE_DIR, "tokens", fname)
            else:
                fpath = os.path.join(BASE_DIR, fname)
            with open(fpath, "w", encoding="utf-8") as f:
                if isinstance(content, (dict, list)):
                    json.dump(content, f, indent=2, ensure_ascii=False)
                else:
                    f.write(str(content))
        print(f"✔ Đã giải nén thành công {len(data)} file bí mật (credentials & tokens).")
    except Exception as e:
        print(f"⚠️ Lỗi giải nén PROJECT_SECRETS_BASE64: {e}")

unpack_github_secrets()

import drive_uploader
import auto_clean_posted

def get_drive_quotas():
    """Lấy thông tin dung lượng tất cả các tài khoản Google Drive."""
    tokens = drive_uploader.get_available_tokens()
    accounts = []
    total_limit = 0
    total_usage = 0
    
    for token_path in tokens:
        fname = os.path.basename(token_path)
        try:
            srv = drive_uploader.get_drive_service(token_path)
            about = srv.about().get(fields="user, storageQuota").execute()
            user = about.get("user", {})
            email = user.get("emailAddress", "unknown")
            photo = user.get("photoLink", "")
            
            quota = about.get("storageQuota", {})
            limit = int(quota.get("limit", 0))
            usage = int(quota.get("usage", 0))
            usage_drive = int(quota.get("usageInDrive", 0))
            free = max(0, limit - usage)
            
            total_limit += limit
            total_usage += usage
            
            limit_gb = limit / (1024**3)
            usage_gb = usage / (1024**3)
            free_gb = free / (1024**3)
            pct = (usage / limit * 100) if limit > 0 else 0
            
            status = "Sẵn sàng"
            status_color = "green"
            if pct > 95:
                status = "Gần đầy"
                status_color = "red"
            elif pct > 80:
                status = "Cảnh báo"
                status_color = "orange"
                
            accounts.append({
                "token_file": fname,
                "email": email,
                "photo": photo,
                "limit_gb": round(limit_gb, 2),
                "usage_gb": round(usage_gb, 2),
                "free_gb": round(free_gb, 2),
                "percent": round(pct, 1),
                "status": status,
                "status_color": status_color
            })
        except Exception as e:
            print(f"⚠️ Không thể đọc quota token {fname}: {e}")
            accounts.append({
                "token_file": fname,
                "email": "Lỗi kết nối",
                "photo": "",
                "limit_gb": 15.0,
                "usage_gb": 0.0,
                "free_gb": 15.0,
                "percent": 0.0,
                "status": "Lỗi",
                "status_color": "gray"
            })
            
    total_limit_gb = total_limit / (1024**3) if total_limit > 0 else (len(accounts) * 15.0)
    total_usage_gb = total_usage / (1024**3)
    total_free_gb = max(0, total_limit_gb - total_usage_gb)
    total_pct = (total_usage_gb / total_limit_gb * 100) if total_limit_gb > 0 else 0
    
    return {
        "accounts": accounts,
        "total_limit_gb": round(total_limit_gb, 2),
        "total_usage_gb": round(total_usage_gb, 2),
        "total_free_gb": round(total_free_gb, 2),
        "total_percent": round(total_pct, 1),
        "account_count": len(accounts)
    }

def get_sheets_stats():
    """Lấy thống kê số lượng video từ Google Sheet."""
    stats = {}
    try:
        ss = auto_clean_posted.get_sheets_client().open_by_key(auto_clean_posted.SHEET_ID)
        sheets_to_check = ["Reels", "Reels2", "Reels3", "Prother"]
        
        for name in sheets_to_check:
            try:
                ws = ss.worksheet(name)
                records = ws.get_all_records()
                tot = len(records)
                ready = 0
                posted = 0
                cleaned = 0
                pending = 0
                
                for r in records:
                    link_file = str(r.get("Link file", "")).strip()
                    da_dang = str(r.get("Đã đăng", "")).strip()
                    da_xoa = str(r.get("Đã xóa", "")).strip().lower()
                    link_fb = str(r.get("Link", "")).strip()
                    yt_link = str(r.get("link youtube videos", "")).strip()
                    over90 = str(r.get(">90MB", "")).strip()
                    
                    is_p = bool(da_dang or (link_fb and "facebook.com" in link_fb.lower()))
                    if is_p:
                        posted += 1
                    if da_xoa == "đã xóa":
                        cleaned += 1
                    if link_file and not link_file.lower().startswith("bỏ qua") and over90 != ">90MB":
                        ready += 1
                    elif yt_link and not link_file and over90 != ">90MB":
                        pending += 1
                        
                stats[name] = {
                    "total": tot,
                    "ready": ready,
                    "posted": posted,
                    "cleaned": cleaned,
                    "pending": pending,
                    "protected": (name == "Prother")
                }
            except Exception as e:
                print(f"⚠️ Lỗi đọc sheet {name}: {e}")
                stats[name] = {"total": 0, "ready": 0, "posted": 0, "cleaned": 0, "pending": 0, "protected": (name == "Prother")}
    except Exception as e:
        print(f"⚠️ Lỗi kết nối Google Sheets: {e}")
    return stats

def run_cleanup():
    """Chạy dọn dẹp các video đã đăng trên Cloud."""
    print("\n" + "=" * 60)
    print("🧹 BẮT ĐẦU QUÉT VÀ DỌN DẸP FILE ĐÃ ĐĂNG")
    print("=" * 60)
    try:
        drive_service = auto_clean_posted.get_drive_service()
        ss = auto_clean_posted.get_sheets_client().open_by_key(auto_clean_posted.SHEET_ID)
        
        total_gdrive = 0
        total_dropbox = 0
        sheet_results = {}
        
        # Chỉ quét trên các target sheets (Loại trừ Prother tuyệt đối)
        for sname in auto_clean_posted.TARGET_SHEETS:
            gd, db = auto_clean_posted.clean_sheet_posted_files(ss, sname, drive_service)
            total_gdrive += gd
            total_dropbox += db
            sheet_results[sname] = {"gdrive": gd, "dropbox": db}
            
        print(f"✔ Dọn dẹp hoàn tất: {total_gdrive} file GDrive, {total_dropbox} file Dropbox.")
        return {
            "status": "success",
            "gdrive_deleted": total_gdrive,
            "dropbox_deleted": total_dropbox,
            "sheets": sheet_results,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        print(f"❌ Lỗi khi dọn dẹp: {e}")
        return {
            "status": "error",
            "error": str(e),
            "gdrive_deleted": 0,
            "dropbox_deleted": 0,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

def generate_html(data):
    """Tạo file HTML dashboard hoàn chỉnh và hiện đại."""
    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    pool = data["pool"]
    accounts = pool["accounts"]
    sheets = data["sheets"]
    cleanup = data["cleanup"]
    
    # Render các card tài khoản
    acc_cards_html = ""
    for a in accounts:
        bar_color = "#10b981" if a["percent"] < 70 else ("#f59e0b" if a["percent"] < 90 else "#ef4444")
        badge_class = "badge-green" if a["status_color"] == "green" else ("badge-orange" if a["status_color"] == "orange" else "badge-red")
        acc_cards_html += f"""
        <div class="card account-card">
            <div class="card-header">
                <div class="account-meta">
                    <div class="avatar">{(a['email'][:2]).upper()}</div>
                    <div>
                        <div class="account-email">{a['email']}</div>
                        <div class="token-name">{a['token_file']}</div>
                    </div>
                </div>
                <span class="badge {badge_class}">{a['status']}</span>
            </div>
            <div class="quota-stats">
                <div><span>Đã dùng:</span> <strong>{a['usage_gb']} GB</strong></div>
                <div><span>Còn trống:</span> <strong>{a['free_gb']} GB</strong></div>
                <div><span>Tổng:</span> <strong>{a['limit_gb']} GB</strong></div>
            </div>
            <div class="progress-container">
                <div class="progress-bar" style="width: {a['percent']}%; background-color: {bar_color};"></div>
            </div>
            <div class="progress-label">
                <span>{a['percent']}% đã dùng</span>
                <span>{a['free_gb']} GB trống</span>
            </div>
        </div>
        """

    # Render bảng Sheet
    sheet_rows_html = ""
    for sname, s in sheets.items():
        is_prot = s.get("protected", False)
        badge = '<span class="badge badge-purple">🔒 Bảo vệ vĩnh viễn</span>' if is_prot else '<span class="badge badge-blue">Tự động xóa</span>'
        sheet_rows_html += f"""
        <tr>
            <td><strong>{sname}</strong></td>
            <td>{badge}</td>
            <td><span class="pill pill-green">{s['ready']}</span></td>
            <td><span class="pill pill-yellow">{s['pending']}</span></td>
            <td><span class="pill pill-blue">{s['posted']}</span></td>
            <td><span class="pill pill-gray">{s['cleaned']}</span></td>
            <td><strong>{s['total']}</strong></td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Google Drive Storage Pool & Auto Cleaner Monitor</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: #111827;
            --border-color: #1f2937;
            --text-main: #f9fafb;
            --text-sub: #9ca3af;
            --primary: #3b82f6;
            --primary-light: #60a5fa;
            --green: #10b981;
            --orange: #f59e0b;
            --red: #ef4444;
            --purple: #8b5cf6;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            padding: 24px 16px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        /* Header */
        .header {{
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            margin-bottom: 28px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
        }}
        .header-title h1 {{
            font-size: 26px;
            font-weight: 800;
            background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .header-title p {{
            color: var(--text-sub);
            font-size: 14px;
            margin-top: 4px;
        }}
        .header-meta {{
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 13px;
            color: var(--text-sub);
        }}
        .refresh-pill {{
            background: #1f2937;
            padding: 8px 14px;
            border-radius: 999px;
            display: flex;
            align-items: center;
            gap: 8px;
            border: 1px solid #374151;
        }}
        .live-dot {{
            width: 8px;
            height: 8px;
            background-color: var(--green);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
            70% {{ box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
        }}

        /* Pool Overview */
        .overview-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
        }}
        .stat-card .label {{
            font-size: 13px;
            color: var(--text-sub);
            font-weight: 500;
            margin-bottom: 8px;
        }}
        .stat-card .val {{
            font-size: 28px;
            font-weight: 800;
        }}
        .stat-card .sub {{
            font-size: 12px;
            margin-top: 6px;
            color: var(--text-sub);
        }}

        /* Progress Bar */
        .progress-container {{
            width: 100%;
            height: 10px;
            background-color: #1f2937;
            border-radius: 999px;
            overflow: hidden;
            margin: 12px 0 6px 0;
        }}
        .progress-bar {{
            height: 100%;
            border-radius: 999px;
            transition: width 0.5s ease;
        }}
        .progress-label {{
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: var(--text-sub);
        }}

        /* Account Cards */
        .section-title {{
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .accounts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .account-card .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 14px;
        }}
        .account-meta {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .avatar {{
            width: 38px;
            height: 38px;
            border-radius: 10px;
            background: linear-gradient(135deg, #2563eb, #7c3aed);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 700;
        }}
        .account-email {{
            font-size: 14px;
            font-weight: 600;
            color: var(--text-main);
            word-break: break-all;
        }}
        .token-name {{
            font-size: 11px;
            color: var(--text-sub);
            font-family: monospace;
        }}
        .quota-stats {{
            display: flex;
            justify-content: space-between;
            background: #161f30;
            padding: 10px 12px;
            border-radius: 10px;
            font-size: 12px;
            margin-bottom: 12px;
        }}
        .quota-stats span {{ color: var(--text-sub); }}

        /* Badges */
        .badge {{
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 600;
        }}
        .badge-green {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }}
        .badge-orange {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }}
        .badge-red {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }}
        .badge-blue {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }}
        .badge-purple {{ background: rgba(139, 92, 246, 0.15); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.3); }}

        /* Table */
        .table-card {{
            overflow-x: auto;
            margin-bottom: 32px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            text-align: left;
        }}
        th {{
            padding: 12px 16px;
            color: var(--text-sub);
            font-weight: 600;
            border-bottom: 1px solid var(--border-color);
            background: #161f30;
        }}
        td {{
            padding: 14px 16px;
            border-bottom: 1px solid var(--border-color);
        }}
        tr:last-child td {{ border-bottom: none; }}
        .pill {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
        }}
        .pill-green {{ background: #064e3b; color: #6ee7b7; }}
        .pill-yellow {{ background: #78350f; color: #fde68a; }}
        .pill-blue {{ background: #1e3a8a; color: #93c5fd; }}
        .pill-gray {{ background: #374151; color: #d1d5db; }}

        /* Footer */
        .footer {{
            text-align: center;
            font-size: 13px;
            color: var(--text-sub);
            padding: 24px 0 12px 0;
            border-top: 1px solid var(--border-color);
        }}
        .footer a {{ color: var(--primary-light); text-decoration: none; }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="header">
            <div class="header-title">
                <h1>⚡ Multi-Drive Pool & Reels Cleaner</h1>
                <p>Hệ thống giám sát dung lượng Google Drive và tự động dọn dẹp video đã đăng</p>
            </div>
            <div class="header-meta">
                <div class="refresh-pill">
                    <div class="live-dot"></div>
                    <span>Cập nhật: <strong id="last-update">{now_str}</strong></span>
                </div>
            </div>
        </header>

        <!-- Overview Stats -->
        <section class="overview-grid">
            <div class="card stat-card">
                <div class="label">TỔNG BỘ NHỚ MULTI-DRIVE</div>
                <div class="val" style="color: #60a5fa;">{pool['total_limit_gb']} <span style="font-size: 16px;">GB</span></div>
                <div class="sub">Gộp từ {pool['account_count']} tài khoản Google Drive</div>
            </div>
            <div class="card stat-card">
                <div class="label">DUNG LƯỢNG ĐÃ DÙNG</div>
                <div class="val" style="color: #f59e0b;">{pool['total_usage_gb']} <span style="font-size: 16px;">GB</span></div>
                <div class="sub">Tỷ lệ sử dụng: {pool['total_percent']}%</div>
            </div>
            <div class="card stat-card">
                <div class="label">DUNG LƯỢNG CÒN TRỐNG</div>
                <div class="val" style="color: #10b981;">{pool['total_free_gb']} <span style="font-size: 16px;">GB</span></div>
                <div class="sub">Sẵn sàng lưu thêm hàng trăm video</div>
            </div>
            <div class="card stat-card">
                <div class="label">TRẠNG THÁI DỌN DẸP GẦN NHẤT</div>
                <div class="val" style="font-size: 20px; color: #a78bfa;">{cleanup.get('gdrive_deleted', 0)} Drive / {cleanup.get('dropbox_deleted', 0)} Dbx</div>
                <div class="sub">Lúc: {cleanup.get('timestamp', now_str)}</div>
            </div>
        </section>

        <!-- Google Drive Accounts Breakdown -->
        <h2 class="section-title">📁 Chi tiết {pool['account_count']} tài khoản Google Drive Storage Pool</h2>
        <section class="accounts-grid">
            {acc_cards_html}
        </section>

        <!-- Google Sheets Status -->
        <h2 class="section-title">📊 Trạng thái Video trên Google Sheets</h2>
        <section class="card table-card">
            <table>
                <thead>
                    <tr>
                        <th>Tên Sheet</th>
                        <th>Chế độ dọn dẹp</th>
                        <th>Sẵn sàng đăng</th>
                        <th>Chờ tải</th>
                        <th>Đã đăng FB</th>
                        <th>Đã xóa Cloud</th>
                        <th>Tổng dòng</th>
                    </tr>
                </thead>
                <tbody>
                    {sheet_rows_html}
                </tbody>
            </table>
        </section>

        <!-- Footer -->
        <footer class="footer">
            <p>Hệ thống tự động hóa Make.com & Google Drive Multi-Pool • Tự động dọn dẹp bảo vệ dung lượng</p>
            <p style="margin-top: 6px; font-size: 11px;">Trang web tự động cập nhật định kỳ qua GitHub Actions.</p>
        </footer>
    </div>

    <script>
        // Tự động tải lại trang sau mỗi 60 giây để cập nhật trạng thái mới nhất
        setTimeout(function() {{
            window.location.reload();
        }}, 60000);
    </script>
</body>
</html>
"""
    return html

def main():
    print("=" * 60, flush=True)
    print("🚀 BẮT ĐẦU QUY TRÌNH: DỌN DẸP FILE & CẬP NHẬT TRANG WEB", flush=True)
    print("=" * 60, flush=True)
    
    # 1. Lấy dữ liệu Drive Quota & Google Sheets trước
    print("\n📊 Đang lấy thông tin dung lượng Multi-Drive Pool...", flush=True)
    pool_data = get_drive_quotas()
    
    print("📊 Đang đọc thống kê từ Google Sheets...", flush=True)
    sheets_data = get_sheets_stats()
    
    # Xuất bản HTML lần 1 ngay lập tức để trang web có dữ liệu ngay
    full_data = {
        "pool": pool_data,
        "sheets": sheets_data,
        "cleanup": {"status": "Đang dọn dẹp...", "gdrive_deleted": 0, "dropbox_deleted": 0, "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    os.makedirs(os.path.join(BASE_DIR, "docs"), exist_ok=True)
    html_content = generate_html(full_data)
    
    docs_html_path = os.path.join(BASE_DIR, "docs", "index.html")
    with open(docs_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    root_html_path = os.path.join(BASE_DIR, "index.html")
    with open(root_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✔ Đã tạo trang web thành công tại: {docs_html_path}", flush=True)
        
    # 2. Chạy dọn dẹp các video đã đăng
    cleanup_result = run_cleanup()
    
    # 3. Cập nhật lại HTML và JSON với kết quả dọn dẹp mới nhất
    full_data["cleanup"] = cleanup_result
    html_content = generate_html(full_data)
    with open(docs_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    with open(root_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    json_path = os.path.join(BASE_DIR, "docs", "status.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_data, f, indent=2, ensure_ascii=False)
    print(f"✔ Đã lưu dữ liệu JSON tại: {json_path}", flush=True)
    
    print("\n🎉 HOÀN THÀNH TẤT CẢ!", flush=True)

if __name__ == "__main__":
    main()
