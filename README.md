# check_schedule_conflict
# Có sử dụng ChatGPT
# Video hướng dẫn
### https://www.youtube.com/watch?v=DwUryEY6-Dc
## 1. Cài thư viện
pip install -r requirements.txt

## 2. Tải HTML lịch các lớp
python down_html.py
## -> nhập danh sách mã lớp cần tải

## 3. Mở GUI chọn môn & xuất ICS
python main_gui.py
## -> xuất file: ./ics_output/<ten_file_ics>.ics

## 4. Đọc file ICS và tạo viewer HTML
python read_ics.py ./ics_output/<ten_file_ics>.ics




