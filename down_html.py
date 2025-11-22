import os
import json
import requests

# ===== ĐỌC CONFIG TỪ FILE =====

def load_config(path: str = "config.json") -> dict:
    """
    Đọc file config.json, trả về dict.
    Nếu không có file hoặc lỗi -> trả về {}.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                print("⚠️ config.json không phải dạng object {}, bỏ qua.")
                return {}
            return data
    except FileNotFoundError:
        print("⚠️ Không tìm thấy config.json, dùng giá trị mặc định trong code.")
        return {}
    except Exception as e:
        print(f"⚠️ Lỗi đọc config.json: {e}")
        return {}

config = load_config()

# ===== PHẦN THAM SỐ BẠN CUNG CẤP =====

cookies = {
    'ASP.NET_SessionId': 'xd4ueq1hlynzey1yhaxc0qvl',
}

headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'vi,en-US;q=0.9,en;q=0.8',
    'cache-control': 'no-cache',
    'content-type': 'application/x-www-form-urlencoded',
    'origin': 'https://sinhvien.epu.edu.vn',
    'pragma': 'no-cache',
    'priority': 'u=0, i',
    'referer': 'https://sinhvien.epu.edu.vn/XemLichHoc.aspx?k=1',
    'sec-ch-ua': '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0',
}

params = {
    'k': '1',
}

# data_template: copy nguyên data đang chạy được
data_template = {
    '__EVENTTARGET': '',
    '__EVENTARGUMENT': '',
    '__LASTFOCUS': '',
    '__VIEWSTATE': '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',
    '__VIEWSTATEGENERATOR': '147CF116',
    'ctl00$ucPhieuKhaoSat1$RadioButtonList1': '0',
    'ctl00$DdListMenu': '-1',
    'ctl00$ContentPlaceHolder$SearchType': 'radLopHoc',
    'ctl00$ContentPlaceHolder$txtMaLopHoc': '',  # sẽ override khi gọi
    'ctl00$ContentPlaceHolder$cboHocKy': '37',           # sẽ bị override bởi config nếu có
    'ctl00$ContentPlaceHolder$btnSearch': 'Xem lịch học',
    'ctl00$ucRight1$rdSinhVien': '1',
}

# === APPLY CONFIG (override các key có trong config.json) ===
for k, v in config.items():
    data_template[k] = v

# ===== HÀM GỬI REQUEST CHO TỪNG LỚP =====

def download_for_class(class_code: str):
    """
    Gửi 1 POST y hệt request mẫu, chỉ đổi tên lớp.
    Lưu HTML vào html_all_classes/<class_code>.html
    """
    data = data_template.copy()
    data['ctl00$ContentPlaceHolder$txtMaLopHoc'] = class_code

    print(f"\n=== Đang tải lịch cho lớp: {class_code} ===")
    resp = requests.post(
        'https://sinhvien.epu.edu.vn/XemLichHoc.aspx',
        params=params,
        cookies=cookies,
        headers=headers,
        data=data,
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"⛔ Lỗi {resp.status_code} cho lớp {class_code}")
        print("----- RESPONSE (trích) -----")
        print(resp.text[:400])
        print("----------------------------")
        return

    out_dir = "html_all_classes"
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{class_code}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(resp.text)
    print(f"✅ Đã lưu: {path}")


def main():
    print("Nhập danh sách lớp muốn tải (cách nhau bằng dấu phẩy), ví dụ:")
    print("  D18QTANM,D18CQCN01-N,D20CQAT01-N")
    raw = input("Lớp: ").strip()
    class_list = [c.strip() for c in raw.split(",") if c.strip()]

    if not class_list:
        print("⛔ Không có lớp nào.")
        return

    for cls in class_list:
        download_for_class(cls)


if __name__ == "__main__":
    main()
