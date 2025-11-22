# logic.py
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple

from models import Session


# ====== BUILD OPTIONS ======

def build_course_options(sessions: List[Session]) -> Dict[Tuple, List[Session]]:
    """
    Gom lịch theo từng MÔN + LỚP + NHÓM, trong đó:

    - Nếu môn có cả lý thuyết (group = 0) và nhiều nhóm thực hành (group > 0)
      => mỗi option = (tất cả buổi LT chung + tất cả buổi TH của 1 nhóm).

    - Nếu môn KHÔNG có nhóm (chỉ LT hoặc chỉ TH)
      => 1 option duy nhất, group = 0, chứa toàn bộ buổi học.

    Trả về:
        {
          (course_code, subject_name, class_name, group): [Session, ...],
          ...
        }
    """
    # Tạm thời gom theo khóa KHÔNG có group
    # by_course[(code, name, class)][group] = [Session, ...]
    by_course = defaultdict(lambda: defaultdict(list))

    for s in sessions:
        course_key = (s.course_code, s.subject_name, s.class_name)
        by_course[course_key][s.group].append(s)

    options: Dict[Tuple, List[Session]] = {}

    for (course_code, subject_name, class_name), groups in by_course.items():
        common_sessions = groups.get(0, [])  # LT chung / không nhóm
        group_ids = sorted(g for g in groups.keys() if g != 0)

        if group_ids:
            # Có nhiều nhóm thực hành:
            # mỗi option = LT (group 0) + TH của đúng 1 nhóm
            for g in group_ids:
                sessions_for_option = common_sessions + groups[g]
                key = (course_code, subject_name, class_name, g)
                options[key] = sessions_for_option
        else:
            # Không có nhóm: chỉ một option duy nhất (group = 0)
            key = (course_code, subject_name, class_name, 0)
            options[key] = common_sessions

    return options


def list_options(options: Dict[Tuple, List[Session]]) -> Dict[int, Tuple]:
    """
    In ra danh sách option để user chọn, đánh số 1..N.
    Mỗi option = 1 môn (có thể gồm cả LT + TH).

    Ví dụ:
    1. [010100472805] Quản lý vận hành (Lý thuyết, Thực hành) - Nhóm 1 - lớp D20... - GV: ...
    """
    index_to_key = {}
    print("=== DANH SÁCH MÔN CÓ THỂ CHỌN (FULL LT+TH) ===")

    for i, (key, sess_list) in enumerate(options.items(), start=1):
        course_code, subject_name, class_name, group = key
        group_str = f"nhóm {group}" if group != 0 else "không nhóm / chung lớp"

        # Các loại buổi (LT/TH) trong môn này
        types = sorted({s.subject_type for s in sess_list if s.subject_type})
        if len(types) == 0:
            type_desc = "Không rõ loại"
        elif len(types) == 1:
            type_desc = types[0]
        else:
            type_desc = " + ".join(types)

        # Danh sách giảng viên
        lecturers = sorted({s.lecturer_name for s in sess_list if s.lecturer_name})
        gv_desc = ", ".join(lecturers) if lecturers else "Chưa ghi giảng viên"

        print(
            f"{i}. [{course_code}] {subject_name} "
            f"({type_desc}) - {group_str} - lớp {class_name} - GV: {gv_desc}"
        )

        index_to_key[i] = key

    print("=============================================")
    return index_to_key


def get_sessions_from_selected(
    options: Dict[Tuple, List[Session]],
    index_to_key: Dict[int, Tuple],
    selected_indices: List[int]
) -> List[Session]:
    """
    Từ các index người dùng chọn, lấy ra list Session tương ứng.
    """
    selected_sessions: List[Session] = []
    for idx in selected_indices:
        key = index_to_key[idx]
        selected_sessions.extend(options[key])
    return selected_sessions


# ====== FIND CONFLICTS ======

def _date_sort_key(date_str: str):
    """
    date_str: 'dd-mm-yyyy' -> key (yyyy, mm, dd) để sort đúng.
    """
    d, m, y = date_str.split('-')
    return int(y), int(m), int(d)


def find_conflicts(sessions: List[Session]) -> List[Tuple[Session, Session]]:
    """
    Tìm các cặp buổi học bị trùng.
    Điều kiện trùng: cùng ngày + khoảng thời gian overlap.
    """
    sessions_sorted = sorted(
        sessions,
        key=lambda s: (_date_sort_key(s.date), s.start, s.end)
    )

    conflicts: List[Tuple[Session, Session]] = []
    n = len(sessions_sorted)

    for i in range(n):
        si = sessions_sorted[i]
        for j in range(i + 1, n):
            sj = sessions_sorted[j]

            # khác ngày thì không cần xét tiếp cho si
            if sj.date != si.date:
                break

            # Kiểm tra overlap: start_j < end_i và end_j > start_i
            if sj.start < si.end and sj.end > si.start:
                conflicts.append((si, sj))

    return conflicts


def print_conflicts(conflicts: List[Tuple[Session, Session]]):
    if not conflicts:
        print("✅ Không trùng lịch!")
        return

    print("❌ Có các cặp trùng lịch sau:")
    for a, b in conflicts:
        print(
            f"- {a.subject_name} ({a.class_name}, nhóm {a.group}, {a.date}, {a.lesson_period}, phòng {a.room}) "
            f"trùng với {b.subject_name} ({b.class_name}, nhóm {b.group}, {b.date}, {b.lesson_period}, phòng {b.room})"
        )


# ====== ICS EXPORT ======

def convert_date_format(date_str: str) -> str:
    """
    'dd-mm-yyyy' -> 'yyyymmdd'
    """
    d, m, y = date_str.split('-')
    return f"{y}{m.zfill(2)}{d.zfill(2)}"


def create_ics_from_sessions(sessions: List[Session], output_file: str) -> None:
    """
    Xuất list Session ra file .ics (import cho Google Calendar, v.v).
    """
    current_time = datetime.now().strftime("%Y%m%dT%H%M%SZ")

    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Python//Schedule Converter//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VTIMEZONE",
        "TZID:Asia/Bangkok",
        "BEGIN:STANDARD",
        "DTSTART:19700101T000000",
        "TZOFFSETFROM:+0700",
        "TZOFFSETTO:+0700",
        "TZNAME:ICT",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]

    for idx, s in enumerate(sessions, start=1):
        date_formatted = convert_date_format(s.date)

        ics_content.append("BEGIN:VEVENT")
        ics_content.append(f"UID:event{idx}@schedule.local")
        ics_content.append(f"DTSTAMP:{current_time}")
        ics_content.append(f"LAST-MODIFIED:{current_time}")
        ics_content.append("SEQUENCE:0")
        ics_content.append(f"DTSTART;TZID=Asia/Bangkok:{date_formatted}T{s.start}")
        ics_content.append(f"DTEND;TZID=Asia/Bangkok:{date_formatted}T{s.end}")
        ics_content.append(f"SUMMARY:{s.subject_name}")

        desc = (
            f"Loại: {s.subject_type}\\n"
            f"Lớp: {s.class_name}\\n"
            f"Nhóm: {s.group}\\n"
            f"Giảng viên: {s.lecturer_name}\\n"
            f"Phòng: {s.room}\\n"
            f"Tiết: {s.lesson_period}"
        )

        ics_content.append(f"DESCRIPTION:{desc}")
        ics_content.append(f"LOCATION:{s.room}")
        ics_content.append("END:VEVENT")

    ics_content.append("END:VCALENDAR")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(ics_content))

    print(f"✅ Đã tạo file ICS: {output_file}")
