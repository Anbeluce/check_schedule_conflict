# models.py
from dataclasses import dataclass

@dataclass
class Session:
    """
    Đại diện cho 1 buổi học (một dòng trong lịch).
    """
    course_code: str      # Mã học phần
    subject_name: str     # Tên môn
    subject_type: str     # Lý thuyết / Thực hành
    group: int            # Nhóm (0 nếu không có)
    lesson_period: str    # Chuỗi tiết, vd: "1 -> 3"
    lecturer_name: str    # Tên giảng viên
    room: str             # Phòng học
    date: str             # "dd-mm-yyyy"
    start: str            # "HHMMSS" - giờ bắt đầu
    end: str              # "HHMMSS" - giờ kết thúc
    class_name: str       # Tên lớp hành chính (vd: D20CQCN01-N)
