# parser_html.py
import os
import re
from bs4 import BeautifulSoup

from models import Session


def parse_schedule_html(html: str, class_name: str) -> list[Session]:
    """
    Parse HTML lịch học của 1 lớp thành danh sách Session.
    """

    def fresh(tag):
        # Gộp các <br> bằng khoảng trắng để text liền mạch, dễ tách
        return tag.get_text(" ", strip=True)

    def extract_subject_type(text_tag):
        s = fresh(text_tag)
        return 'Lý thuyết' if 'Lý thuyết' in s else 'Thực hành'

    def extract_subject_name_and_group(text_tag):
        """
        Tách tên môn + nhóm từ chuỗi ở cột 'Tên môn'.
        Ví dụ:
          "Quản trị mạng (Thực hành: 48 tiết) Nhóm 2"
        """
        s = fresh(text_tag)
        s_lower = s.lower()
        words = [w.strip() for w in s.split(' ') if w.strip()]

        if 'nhóm' not in s_lower:
            # Không có từ "nhóm" => không có nhóm
            # Bỏ 4 từ cuối: "(Lý", "thuyết:", "30", "tiết)" hoặc "(Thực", "hành:", "48", "tiết)"
            return ' '.join(words[:-4]), 0
        else:
            # Có "nhóm" => nhóm ở từ cuối cùng
            try:
                group = int(words[-1])
            except ValueError:
                group = 0
            # Đuôi thường là: "(Thực", "hành:", "48", "tiết)", "Nhóm", "2" => bỏ 6 từ
            return ' '.join(words[:-6]), group

    def extract_date(text_tag):
        """
        Lấy ngày học (đầu tiên) dạng 'dd-mm-yyyy' từ cột 'Thời gian học'.

        Ví dụ:
          "Từ: 06-04-2026 Đến: 06-04-2026" -> "06-04-2026"
          "Thứ 2 (11-08-2025)"            -> "11-08-2025"
        """
        s = fresh(text_tag)
        m = re.search(r"\d{2}-\d{2}-\d{4}", s)
        if m:
            return m.group(0)
        return s  # fallback nếu format lạ, đỡ bị crash

    def convert_lesson_period_to_time(lesson_period: str):
        """
        Map từ tiết sang giờ bắt đầu / kết thúc.
        Dùng y như code cũ.
        """
        time_table = {
            1: ("070000", "075000"),
            2: ("075500", "084500"),
            3: ("085000", "094000"),
            4: ("095000", "104000"),
            5: ("104500", "113500"),
            6: ("123000", "132000"),
            7: ("132500", "141500"),
            8: ("142000", "151000"),
            9: ("152000", "161000"),
            10: ("161500", "170500"),
            11: ("173000", "182000"),
            12: ("182500", "191500"),
            13: ("192000", "201000"),
            14: ("201500", "210500"),
        }
        try:
            p1, p2 = lesson_period.split(" -> ")
            start_lesson = int(p1)
            end_lesson = int(p2)
            start_time = time_table[start_lesson][0]
            end_time = time_table[end_lesson][1]
            return start_time, end_time
        except Exception:
            # fallback nếu có lỗi format
            return "070000", "074500"

    soup = BeautifulSoup(html, 'html.parser')
    all_tables = soup.find_all('table', class_='table-lich_hoc')

    sessions: list[Session] = []

    for table in all_tables:
        lectures = table.find_all('tr')
        for lecture in lectures:
            in4 = lecture.find_all('td')
            if not in4:
                continue

            # Bỏ dòng "kết thúc" như code gốc
            if 'kết thúc' in fresh(in4[1]).lower():
                continue

            course_code = fresh(in4[0])
            subject_name, group = extract_subject_name_and_group(in4[1])
            subject_type = extract_subject_type(in4[1])
            lesson_period = fresh(in4[2])
            lecturer_name = fresh(in4[3])
            room = fresh(in4[4])
            date = extract_date(in4[5])
            start, end = convert_lesson_period_to_time(lesson_period)

            sessions.append(Session(
                course_code=course_code,
                subject_name=subject_name,
                subject_type=subject_type,
                group=group,
                lesson_period=lesson_period,
                lecturer_name=lecturer_name,
                room=room,
                date=date,
                start=start,
                end=end,
                class_name=class_name
            ))

    return sessions


def parse_html_file(path: str, class_name: str) -> list[Session]:
    """
    Đọc file HTML từ disk rồi parse.
    """
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    return parse_schedule_html(html, class_name)


def load_all_sessions(html_dir: str) -> list[Session]:
    """
    Đọc tất cả file .html trong thư mục html_dir,
    mỗi file coi như lịch của 1 lớp.
    Tên lớp = tên file (bỏ .html).
    """
    all_sessions: list[Session] = []

    for filename in os.listdir(html_dir):
        if not filename.lower().endswith('.html'):
            continue

        class_name = os.path.splitext(filename)[0]
        path = os.path.join(html_dir, filename)

        sessions = parse_html_file(path, class_name)
        all_sessions.extend(sessions)

    return all_sessions
