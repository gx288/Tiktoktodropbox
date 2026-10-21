import os
import sys
import io
import glob
import time

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

import threading

# Bộ nhớ đệm Thread-Local cho Service để tránh lỗi SSL socket collision khi chạy đa luồng
_local = threading.local()
_folder_cache = {}

def get_available_tokens():
    """Lấy danh sách tất cả các file token Google Drive có sẵn (trong tokens/ hoặc thư mục gốc)."""
    tokens = []
    search_dirs = [os.path.join(BASE_DIR, "tokens"), BASE_DIR]
    for d in search_dirs:
        primary = os.path.join(d, "token.json")
        if os.path.exists(primary) and primary not in tokens:
            tokens.append(primary)
        pattern = os.path.join(d, "token_drive*.json")
        for f in sorted(glob.glob(pattern)):
            if f not in tokens:
                tokens.append(f)
    return tokens

def get_drive_service(token_path=None):
    """Khởi tạo hoặc lấy đối tượng Google Drive API service tự động làm mới token (Thread-Safe)."""
    if token_path is None:
        tokens = get_available_tokens()
        if not tokens:
            raise FileNotFoundError("Không tìm thấy bất kỳ file token.json hoặc token_drive*.json nào! Vui lòng chạy get_token.py để tạo.")
        token_path = tokens[0]

    if not os.path.exists(token_path):
        raise FileNotFoundError(f"Chưa tìm thấy file token tại: {token_path}")

    if not hasattr(_local, "services"):
        _local.services = {}

    # Trả về service từ cache riêng của từng thread nếu có
    if token_path in _local.services:
        return _local.services[token_path]

    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        try:
            with open(token_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        except Exception:
            pass

    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    _local.services[token_path] = service
    return service

def get_account_info(service):
    """Lấy thông tin tài khoản và dung lượng còn trống (MB)."""
    try:
        about = service.about().get(fields="user, storageQuota").execute()
        user = about.get("user", {})
        email = user.get("emailAddress", "unknown")
        
        quota = about.get("storageQuota", {})
        limit = int(quota.get("limit", 0))
        usage = int(quota.get("usage", 0))
        
        free_mb = (limit - usage) / (1024 * 1024) if limit > 0 else 999999.0
        return email, free_mb
    except Exception as e:
        return "unknown", 0.0

def get_or_create_folder(folder_name="Shorts", parent_id=None, service=None, token_path=None):
    """Tìm hoặc tạo thư mục trên Google Drive."""
    if service is None:
        service = get_drive_service(token_path)
        
    cache_key = f"{id(service)}_{folder_name}_{parent_id}"
    if cache_key in _folder_cache:
        return _folder_cache[cache_key]

    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    if files:
        f_id = files[0]['id']
        _folder_cache[cache_key] = f_id
        return f_id

    metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_id:
        metadata['parents'] = [parent_id]

    folder = service.files().create(body=metadata, fields='id').execute()
    f_id = folder.get('id')
    _folder_cache[cache_key] = f_id
    return f_id

def get_free_space_mb():
    """Kiểm tra dung lượng còn trống trên tài khoản Google Drive đầu tiên."""
    try:
        service = get_drive_service()
        _, free_mb = get_account_info(service)
        return free_mb
    except Exception:
        return 999999.0

def upload_file(local_path, folder_id=None, folder_name="Shorts"):
    """
    Tự động chọn tài khoản Google Drive còn trống dung lượng trong Multi-Drive Pool,
    upload file và cấp quyền công khai (Direct link Make.com).
    """
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Không tìm thấy file: {local_path}")

    file_size_mb = os.path.getsize(local_path) / (1024 * 1024)
    tokens = get_available_tokens()
    if not tokens:
        raise FileNotFoundError("Không có tài khoản Google Drive nào sẵn sàng!")

    selected_service = None
    selected_token = None
    selected_email = ""

    # Quét qua các tài khoản Google Drive tìm tài khoản còn đủ dung lượng
    for token_path in tokens:
        try:
            srv = get_drive_service(token_path)
            email, free_mb = get_account_info(srv)
            
            # Yêu cầu dung lượng còn lại > file + 50MB và > 200MB an toàn
            if free_mb > (file_size_mb + 50) and free_mb > 200:
                selected_service = srv
                selected_token = token_path
                selected_email = email
                t_name = os.path.basename(token_path)
                print(f"   📁 [Multi-Drive] Dùng '{t_name}' ({email}) - Còn trống: {free_mb:.1f} MB")
                break
            else:
                print(f"   ⚠️ [Multi-Drive] '{os.path.basename(token_path)}' ({email}) sắp đầy ({free_mb:.1f} MB còn lại). Chuyển tiếp...")
        except Exception as e:
            print(f"   ⚠️ Lỗi kiểm tra token {token_path}: {e}")
            continue

    if not selected_service:
        raise RuntimeError("❌ TẤT CẢ CÁC TÀI KHOẢN GOOGLE DRIVE ĐỀU ĐÃ HẾT DUNG LƯỢNG!")

    # Lấy thư mục đích tương ứng với tài khoản Google Drive được chọn
    if folder_name:
        target_folder_id = get_or_create_folder(folder_name=folder_name, service=selected_service)
    else:
        target_folder_id = folder_id

    filename = os.path.basename(local_path)
    file_metadata = {'name': filename}
    if target_folder_id:
        file_metadata['parents'] = [target_folder_id]

    media = MediaFileUpload(local_path, resumable=True)
    file = selected_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, name, webViewLink, webContentLink'
    ).execute()

    # Cấp quyền Anyone with link can view (để Make.com tải trực tiếp không bị 403)
    try:
        selected_service.permissions().create(
            fileId=file['id'],
            body={'role': 'reader', 'type': 'anyone'}
        ).execute()
    except Exception:
        pass

    file['account_email'] = selected_email
    file['token_file'] = os.path.basename(selected_token)
    return file

def delete_file_from_any_drive(file_id):
    """Thử xóa file trên tất cả các tài khoản Google Drive đã đăng ký (BẢO VỆ TUYỆT ĐỐI THƯ MỤC/FILE PROTHER)."""
    tokens = get_available_tokens()
    for token_path in tokens:
        try:
            srv = get_drive_service(token_path)
            srv.files().delete(fileId=file_id).execute()
            return True, os.path.basename(token_path)
        except HttpError as he:
            if he.resp.status == 404:
                continue
            else:
                continue
        except Exception:
            continue
    return False, None
    return False, None

if __name__ == '__main__':
    print("=" * 60)
    print("📊 KIỂM TRA HỆ THỐNG MULTI-DRIVE STORAGE POOL")
    print("=" * 60)
    tokens = get_available_tokens()
    print(f"Tìm thấy {len(tokens)} tài khoản Google Drive đã cấu hình:")
    for idx, t in enumerate(tokens, 1):
        try:
            srv = get_drive_service(t)
            email, free_mb = get_account_info(srv)
            print(f" {idx}. [{os.path.basename(t)}] - {email} : Còn trống {free_mb:.1f} MB")
        except Exception as e:
            print(f" {idx}. [{os.path.basename(t)}] - LỖI: {e}")
    print("=" * 60)
