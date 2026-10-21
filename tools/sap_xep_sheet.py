import sys
sys.stdout.reconfigure(encoding='utf-8')
import gspread
from google.oauth2.service_account import Credentials
from config import SHEET_ID

def reorder_sheet(sheet_name="Reels"):
    print(f"\n🔄 Đang sắp xếp sheet: '{sheet_name}'...")
    creds = Credentials.from_service_account_file('credentials.json', scopes=['https://www.googleapis.com/auth/spreadsheets'])
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(sheet_name)
    rows = sheet.get_all_values()
    if len(rows) <= 1:
        print("Sheet trống.")
        return

    header = rows[0]
    data_rows = [r for r in rows[1:] if any(r)]

    valid_rows = []
    failed_or_empty_rows = []

    for r in data_rows:
        link_file = r[1].strip() if len(r) > 1 else ""
        over_90 = r[9].strip() if len(r) > 9 else ""

        # Tiêu chí: có link file, không phải 'Bỏ qua', không phải '>90MB'
        if link_file and not link_file.lower().startswith("bỏ qua") and ">90" not in over_90:
            valid_rows.append(r)
        else:
            failed_or_empty_rows.append(r)

    sorted_rows = [header] + valid_rows + failed_or_empty_rows
    max_cols = max(len(r) for r in sorted_rows)
    padded_rows = [r + [""] * (max_cols - len(r)) for r in sorted_rows]

    sheet.update(range_name="A1", values=padded_rows, value_input_option="USER_ENTERED")
    print(f"✔ Hoàn thành sắp xếp '{sheet_name}':")
    print(f"  - {len(valid_rows)} dòng CÓ LINK sẵn sàng đăng ở ĐẦU BẢNG.")
    print(f"  - {len(failed_or_empty_rows)} dòng chưa tải/lỗi/>90MB được chuyển xuống CUỐI BẢNG.")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "Reels"
    reorder_sheet(target)
