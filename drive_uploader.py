import os
import sys
import io

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

TOKEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

def get_drive_service():
    """Lấy đối tượng Google Drive API service tự động làm mới token vĩnh viễn."""
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError(f"Chưa tìm thấy file token tại '{TOKEN_PATH}'! Vui lòng chạy 'get_token.py' để đăng nhập trước.")
        
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
            
    return build('drive', 'v3', credentials=creds)

def get_or_create_folder(folder_name, parent_id=None):
    """Tìm hoặc tạo thư mục trên Google Drive."""
    service = get_drive_service()
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
        
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']
        
    metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_id:
        metadata['parents'] = [parent_id]
        
    folder = service.files().create(body=metadata, fields='id').execute()
    return folder.get('id')

def get_free_space_mb():
    """Kiểm tra dung lượng còn trống trên Google Drive (đơn vị MB)."""
    try:
        service = get_drive_service()
        about = service.about().get(fields="storageQuota").execute()
        quota = about.get("storageQuota", {})
        limit = int(quota.get("limit", 0))
        usage = int(quota.get("usage", 0))
        if limit == 0:
            return 999999.0
        return (limit - usage) / (1024 * 1024)
    except Exception as e:
        print(f"Lỗi kiểm tra dung lượng Drive: {e}")
        return 999999.0

def upload_file(local_path, folder_id=None):
    """Upload một file lên Google Drive và trả về file_id, web_link."""
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Không tìm thấy file: {local_path}")
        
    service = get_drive_service()
    filename = os.path.basename(local_path)
    file_metadata = {'name': filename}
    if folder_id:
        file_metadata['parents'] = [folder_id]
        
    media = MediaFileUpload(local_path, resumable=True)
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, name, webViewLink, webContentLink'
    ).execute()
    
    # Chia sẻ công khai hoặc xem bất cứ ai có link (nếu cần)
    try:
        service.permissions().create(
            fileId=file['id'],
            body={'role': 'reader', 'type': 'anyone'}
        ).execute()
    except Exception:
        pass
        
    return file

if __name__ == '__main__':
    if len(sys.argv) > 1:
        target = sys.argv[1]
        print(f"[*] Đang tải file lên Google Drive: {target} ...")
        res = upload_file(target)
        print("✔ UPLOAD THÀNH CÔNG!")
        print(f"File ID: {res.get('id')}")
        print(f"Link xem: {res.get('webViewLink')}")
        print(f"Link tải: {res.get('webContentLink')}")
    else:
        print("Cách dùng: python drive_uploader.py <duong_dan_file_can_upload>")
