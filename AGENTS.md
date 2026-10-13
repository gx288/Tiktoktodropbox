# AGENTS.MD - HƯỚNG DẪN DÀNH CHO AI AGENT TIẾP QUẢN DỰ ÁN

Tài liệu này được thiết kế để bất kỳ AI Agent nào khi tiếp quản dự án này đều nắm rõ toàn bộ kiến trúc, cơ chế hoạt động, quy tắc an toàn và cách mở rộng hệ thống mà không làm gián đoạn luồng vận hành hiện tại.

---

## 1. 🎯 MỤC TIÊU DỰ ÁN (PROJECT OVERVIEW)
Xây dựng pipeline tự động hóa từ đầu đến cuối (End-to-End Automation):
1. Tải video ngắn từ **TikTok** và **YouTube Shorts** (tự động chuẩn hóa hashtag `#short*` / `#youtube*` thành `#reels`).
2. Tải video lên **Google Drive 15GB** (hoặc Dropbox cho dữ liệu cũ).
3. Sinh link download trực tiếp chuẩn Make.com (`https://drive.google.com/uc?export=download&id={FILE_ID}`) và ghi vào **Google Sheet**.
4. Make.com đọc Google Sheet và tự động đăng Facebook Reels.
5. Khi video đã đăng, hệ thống dọn dẹp tự động xóa file trên Cloud storage để giải phóng dung lượng.
6. Cảnh báo lỗi và báo cáo qua **Telegram Bot**.

---

## 2. 🔑 BẢO MẬT & QUY TẮC BẮT BUỘC (CRITICAL SECURITY RULES)
1. **Tuyệt đối KHÔNG commit các file bí mật lên Git:**
   - `client_secret.json`
   - `credentials.json`
   - `drive-credentials.json`
   - `token.json` và mọi file `token*.json`
   - Thư mục `temp/`, log files.
   - File `.gitignore` đã được cấu hình chặt chẽ, Agent cần giữ nguyên.
2. **Chuẩn link Make.com:**
   - Link Google Drive ghi vào Cột B của Sheet BẮT BUỘC phải ở định dạng direct binary stream:
     `https://drive.google.com/uc?export=download&id={FILE_ID}`
   - File tải lên Drive PHẢI set permission `anyone with link can view` để Make.com không bị chặn 403.
3. **Cột J (>90MB):**
   - Video tải lên Facebook Reels bị giới hạn dung lượng. Nếu file $> 90$ MB, bỏ qua hoặc đánh dấu `>90MB` ở cột J.

---

## 3. 🏗️ KIẾN TRÚC HỆ THỐNG & CÁC SCRIPT CHÍNH

### A. Tải & Đồng bộ Video:
* `yt-tt-to-sheet-date.py`: Script chính tải video từ TikTok / YouTube Shorts, upload lên Drive và cập nhật Google Sheet.
* `drive_uploader.py`: Module upload file lên Google Drive, tự động refresh token, set quyền công khai và trả về link direct download.

### B. Dọn dẹp tự động (Cloud Cleaner):
* `auto_clean_posted.py`: Quét 3 sheet (`Reels`, `Reels2`, `Reels3`), tìm các dòng đã đăng (Cột F có dữ liệu hoặc Cột I có link Facebook), xóa file trên Google Drive / Dropbox, đánh dấu Cột G là "Đã xóa" và gửi báo cáo Telegram.
* `CHAY_XOA_FILE_DA_DANG.bat`: Batch file chạy dọn dẹp 1 lần.
* `CHAY_NGAM_DINH_KY_XOA_FILE.bat`: Batch file chạy ngầm định kỳ mỗi 30 phút.
* Shortcut Desktop: `D:\Files\Desktop\Don_Dep_File_Da_Dang.lnk`.

### C. Quản lý Token & OAuth:
* `get_token.py`: Script OAuth 2.0 Web Server nhận token Google Drive & Google Sheets vĩnh viễn (Production).
  - Hỗ trợ tham số `--output <tên_file>` (mặc định `token.json`).

---

## 4. 🚀 HƯỚNG DẪN MỞ RỘNG MULTI-ACCOUNT GOOGLE DRIVE (TĂNG DUNG LƯỢNG)

Khi người dùng muốn thêm tài khoản Google Drive mới (mỗi nick +15GB miễn phí):

### Bước 1: Nguyên lý hoạt động
* Project Google Cloud: `fb-storage-511417`
* Trạng thái OAuth: **In Production (Vĩnh viễn)** với website xác thực `https://comil.site`.
* Dùng chung `client_secret.json` hiện tại cho TẤT CẢ các tài khoản Google khác.
* Không cần tạo mới project hay cài lại domain.

### Bước 2: Lấy Token cho tài khoản mới
AI Agent chạy lệnh:
```powershell
# Ví dụ thêm nick số 2:
python get_token.py --output token_drive2.json

# Hoặc nick số 3:
python get_token.py --output token_drive3.json
```
Hướng dẫn người dùng:
1. Trình duyệt tự mở, người dùng chọn tài khoản Gmail mới.
2. Bấm **Nâng cao (Advanced)** $\rightarrow$ **Đi tiếp tới MyDrive (không an toàn)**.
3. Tích chọn đủ 2 quyền $\rightarrow$ Bấm **Tiếp tục**.
4. File `token_drive2.json` sẽ được tạo và đồng bộ tự động.

### Bước 3: Tích hợp vào Pipeline
Trong `drive_uploader.py`:
* `GoogleDriveUploader(token_file='token_drive2.json')`
* Khi xây dựng Multi-Drive Storage Pool:
  1. Kiểm tra dung lượng còn trống của `token.json` (Drive 1):
     `service.about().get(fields="storageQuota").execute()`
  2. Nếu dung lượng còn lại $< 500$ MB $\rightarrow$ tự động chuyển sang upload bằng `token_drive2.json`.

---

## 5. 📊 CẤU TRÚC GOOGLE SHEET (ID: `14tqKftTqlesnb0NqJZU-_f1EsWWywYqO36NiuDdmaTo`)
* **Sheet `Reels`:** Video TikTok cũ (Dropbox).
* **Sheet `Reels2`:** Video YouTube Shorts chính (Google Drive + Dropbox cũ).
* **Sheet `Reels3`:** Video phân luồng mới / dự phòng (Google Drive).

### 10 Cột Chuẩn:
| Cột | Tên Cột | Mô tả |
| :---: | :--- | :--- |
| **A** | `Title` | Tiêu đề video (gắn `#reels`) |
| **B** | `Link file` | Direct download link (`uc?export=download&id=...`) |
| **C** | `thumbnail` | Link thumbnail ảnh |
| **D** | `length` | Thời lượng video (giây) |
| **E** | `link youtube videos` | Link video gốc |
| **F** | `Đã đăng` | Ngày giờ đã đăng FB |
| **G** | `Đã xóa` | Đánh dấu đã xóa file trên Cloud |
| **H** | *(Trống)* | Phân tách |
| **I** | `Link` | Link bài đăng Facebook Reels |
| **J** | `>90MB` | Đánh dấu file vượt quá 90MB |
