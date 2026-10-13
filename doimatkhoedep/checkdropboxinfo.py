import dropbox
import os
from config import DROPBOX_REFRESH_TOKEN, DROPBOX_APP_KEY, DROPBOX_APP_SECRET


def check_dropbox_account():
    print("=" * 60)
    print("KIỂM TRA TÀI KHOẢN DROPBOX")
    print("=" * 60)

    if not DROPBOX_REFRESH_TOKEN:
        print("❌ LỖI: DROPBOX_REFRESH_TOKEN chưa được thiết lập trong config.py")
        return

    try:
        # Khởi tạo Dropbox client
        dbx = dropbox.Dropbox(
            oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
            app_key=DROPBOX_APP_KEY,
            app_secret=DROPBOX_APP_SECRET
        )

        print("Đang kết nối đến Dropbox...")

        # Lấy thông tin tài khoản hiện tại
        account = dbx.users_get_current_account()

        print("\n✅ KẾT NỐI THÀNH CÔNG!")
        print("-" * 50)
        print(f"Tên hiển thị     : {account.name.display_name}")
        print(f"Email            : {account.email}")
        print(f"Account ID       : {account.account_id}")
        print(f"Loại tài khoản   : {account.account_type}")

        if account.country:
            print(f"Quốc gia         : {account.country}")

        # Kiểm tra xem có thuộc Team (Business) không
        if hasattr(account, 'team') and account.team and account.team.name:
            print(f"Team             : {account.team.name}")

        # Thông tin dung lượng (nếu cần)
        space_usage = dbx.users_get_space_usage()
        used = space_usage.used / (1024 ** 3)  # GB
        allocation = space_usage.allocation

        print(f"Dung lượng đã dùng: {used:.2f} GB")

        if hasattr(allocation, 'get_individual'):
            total = allocation.get_individual().allocated / (1024 ** 3)
            print(f"Tổng dung lượng   : {total:.2f} GB")

        print("\nNếu bạn thấy thông tin Email và Tên hiển thị ở trên → Đây chính là tài khoản Dropbox đang được dùng.")

    except dropbox.exceptions.AuthError as e:
        print("❌ LỖI XÁC THỰC: Refresh Token không hợp lệ hoặc đã hết hạn.")
        print(f"Chi tiết: {e}")
    except dropbox.exceptions.ApiError as e:
        print(f"❌ LỖI API Dropbox: {e}")
    except Exception as e:
        print(f"❌ Lỗi không xác định: {e}")
        print("Kiểm tra lại DROPBOX_REFRESH_TOKEN, APP_KEY, APP_SECRET trong file config.py")


if __name__ == "__main__":
    check_dropbox_account()

    input("\nNhấn Enter để thoát...")