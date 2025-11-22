# main_gui.py
import os
from datetime import datetime
from tkinter import (
    Tk, Listbox, Text, Scrollbar, END, SINGLE,
    BOTH, VERTICAL, HORIZONTAL
)
from tkinter import messagebox, filedialog
from tkinter import ttk

from parser_html import load_all_sessions
from logic import (
    build_course_options,
    find_conflicts,
    print_conflicts,
    create_ics_from_sessions,
)


class ScheduleGUI:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Schedule Checker - chọn môn & xuất ICS")
        self.root.geometry("1200x700")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.html_dir = os.path.join(base_dir, "html_all_classes")
        self.ics_dir = os.path.join(base_dir, "ics_output")
        os.makedirs(self.ics_dir, exist_ok=True)

        # ====== LOAD DATA ======
        print(f"Đang đọc các file HTML trong: {self.html_dir}")
        self.all_sessions = load_all_sessions(self.html_dir)
        print(f"Đã load {len(self.all_sessions)} buổi học (session).")

        self.options = build_course_options(self.all_sessions)
        # key = (course_code, subject_name, class_name, group)
        self.all_keys = sorted(
        self.options.keys(),
        key=lambda k: (k[1], k[2], k[3])  # subject_name, class_name, group
    )


        self.filtered_keys = list(self.all_keys)
        self.selected_keys: list[tuple] = []
        self.current_key = None

        self.subject_names = sorted({k[1] for k in self.options.keys()})


        # ====== BUILD UI ======
        self._build_ui()
        self._update_course_list()

    # ---------- UI setup ----------

    def _build_ui(self):
        paned_main = ttk.Panedwindow(self.root, orient="horizontal")
        paned_main.pack(fill=BOTH, expand=True)

        frame_left = ttk.Frame(paned_main, padding=5)
        frame_right = ttk.Frame(paned_main, padding=5)
        paned_main.add(frame_left, weight=1)
        paned_main.add(frame_right, weight=2)

        # ----- LEFT: filter lớp + danh sách môn -----
        lbl_class = ttk.Label(frame_left, text="Lọc theo môn học:")
        lbl_class.pack(anchor="w")

        self.cmb_class = ttk.Combobox(
            frame_left,
            values=["Tất cả môn"] + self.subject_names,
            state="readonly"
        )
        self.cmb_class.current(0)
        self.cmb_class.pack(fill="x", pady=(0, 5))
        self.cmb_class.bind("<<ComboboxSelected>>", self._on_class_changed)

        lbl_courses = ttk.Label(
            frame_left,
            text="Môn học (gộp LT + TH, chia theo lớp & nhóm):"
        )
        lbl_courses.pack(anchor="w")

        frame_lb = ttk.Frame(frame_left)
        frame_lb.pack(fill=BOTH, expand=True)

        self.lb_courses = Listbox(frame_lb, selectmode=SINGLE)
        self.lb_courses.grid(row=0, column=0, sticky="nsew")

        scroll_y = Scrollbar(frame_lb, orient=VERTICAL, command=self.lb_courses.yview)
        scroll_y.grid(row=0, column=1, sticky="ns")

        scroll_x = Scrollbar(frame_lb, orient=HORIZONTAL, command=self.lb_courses.xview)
        scroll_x.grid(row=1, column=0, sticky="ew")

        self.lb_courses.config(
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set
        )

        frame_lb.rowconfigure(0, weight=1)
        frame_lb.columnconfigure(0, weight=1)

        self.lb_courses.bind("<<ListboxSelect>>", self._on_course_select)
                # --- phím tắt cho list môn ---
        self.lb_courses.bind("<Up>", self._on_course_key)
        self.lb_courses.bind("<Down>", self._on_course_key)
        self.lb_courses.bind("<Prior>", self._on_course_key)   # PageUp
        self.lb_courses.bind("<Next>", self._on_course_key)    # PageDown
        self.lb_courses.bind("<Return>", self._on_course_enter)  # Enter = thêm môn

        # ----- RIGHT: paned vertical (preview + selected) -----
        paned_right = ttk.Panedwindow(frame_right, orient="vertical")
        paned_right.pack(fill=BOTH, expand=True)

        frame_detail = ttk.Frame(paned_right, padding=(0, 0, 0, 5))
        frame_selected = ttk.Frame(paned_right)
        paned_right.add(frame_detail, weight=2)
        paned_right.add(frame_selected, weight=1)

        # -- detail of current course --
        lbl_detail = ttk.Label(frame_detail, text="Lịch chi tiết của môn đang chọn:")
        lbl_detail.pack(anchor="w")

        frame_text = ttk.Frame(frame_detail)
        frame_text.pack(fill=BOTH, expand=True, pady=(2, 5))

        self.txt_detail = Text(frame_text, height=10, wrap="none")
        self.txt_detail.grid(row=0, column=0, sticky="nsew")

        d_scroll_y = Scrollbar(frame_text, orient=VERTICAL, command=self.txt_detail.yview)
        d_scroll_y.grid(row=0, column=1, sticky="ns")
        d_scroll_x = Scrollbar(frame_text, orient=HORIZONTAL, command=self.txt_detail.xview)
        d_scroll_x.grid(row=1, column=0, sticky="ew")

        self.txt_detail.config(
            yscrollcommand=d_scroll_y.set,
            xscrollcommand=d_scroll_x.set,
            state="disabled"
        )

        frame_text.rowconfigure(0, weight=1)
        frame_text.columnconfigure(0, weight=1)

        btn_add = ttk.Button(
            frame_detail,
            text="➕ Thêm môn này vào danh sách",
            command=self._add_current_course
        )
        btn_add.pack(anchor="e")

        # -- selected courses & export --
        lbl_sel = ttk.Label(frame_selected, text="Các môn đã chọn:")
        lbl_sel.pack(anchor="w")

        frame_sel_lb = ttk.Frame(frame_selected)
        frame_sel_lb.pack(fill=BOTH, expand=True)

        self.lb_selected = Listbox(frame_sel_lb, selectmode=SINGLE)
        self.lb_selected.grid(row=0, column=0, sticky="nsew")

        sel_scroll_y = Scrollbar(
            frame_sel_lb, orient=VERTICAL, command=self.lb_selected.yview
        )
        sel_scroll_y.grid(row=0, column=1, sticky="ns")
        self.lb_selected.config(yscrollcommand=sel_scroll_y.set)
                # --- phím tắt cho list môn đã chọn ---
        self.lb_selected.bind("<Delete>", self._on_selected_delete)
        self.lb_selected.bind("<BackSpace>", self._on_selected_delete)

        frame_sel_lb.rowconfigure(0, weight=1)
        frame_sel_lb.columnconfigure(0, weight=1)

        frame_btns = ttk.Frame(frame_selected)
        frame_btns.pack(fill="x", pady=5)

        btn_remove = ttk.Button(
            frame_btns, text="🗑 Bỏ môn đã chọn", command=self._remove_selected_course
        )
        btn_remove.pack(side="left")

        btn_clear = ttk.Button(
            frame_btns, text="🧹 Xoá tất cả", command=self._clear_all_courses
        )
        btn_clear.pack(side="left", padx=(5, 0))

        btn_export = ttk.Button(
            frame_btns, text="💾 Xuất ICS...", command=self._export_ics
        )
        btn_export.pack(side="right")


        self.lbl_conflict = ttk.Label(
            frame_selected,
            text="Chưa chọn môn nào.",
            foreground="blue"
        )
        self.lbl_conflict.pack(anchor="w")

    # ---------- helpers ----------

    def _format_option_label(self, key: tuple) -> str:
        course_code, subject_name, class_name, group = key
        sess_list = self.options[key]

        types = sorted({s.subject_type for s in sess_list if s.subject_type})
        if len(types) == 0:
            type_desc = "Không rõ loại"
        elif len(types) == 1:
            type_desc = types[0]
        else:
            type_desc = " + ".join(types)

        group_str = f"Nhóm {group}" if group != 0 else "Không nhóm / chung lớp"

        lecturers = sorted({s.lecturer_name for s in sess_list if s.lecturer_name})
        gv_desc = ", ".join(lecturers) if lecturers else "Chưa ghi GV"

        # 👉 KHÔNG còn mã học phần nữa
        return (
            f"{subject_name} "
            f"({type_desc}) - {group_str} - lớp {class_name} - GV: {gv_desc}"
        )


    def _update_course_list(self):
        self.lb_courses.delete(0, END)
        selected_subject = self.cmb_class.get()
        if selected_subject in ("", "Tất cả môn"):
            self.filtered_keys = list(self.all_keys)
        else:
            self.filtered_keys = [
                k for k in self.all_keys if k[1] == selected_subject
            ]

        for key in self.filtered_keys:
            self.lb_courses.insert(END, self._format_option_label(key))


    # ---------- event handlers ----------

    def _on_class_changed(self, event=None):
        self._update_course_list()
        self._clear_detail()

    def _on_course_select(self, event=None):
        if not self.lb_courses.curselection():
            return
        idx = self.lb_courses.curselection()[0]
        if idx < 0 or idx >= len(self.filtered_keys):
            return
        key = self.filtered_keys[idx]
        self.current_key = key
        self._show_course_detail(key)
    def _on_course_key(self, event=None):
        """
        Khi nhấn ↑ ↓ PageUp PageDown, Tkinter tự đổi selection.
        Mình gọi lại _on_course_select để update phần chi tiết.
        """
        self.root.after(0, self._on_course_select)

    def _on_course_enter(self, event=None):
        """
        Nhấn Enter ở list bên trái = thêm môn hiện tại vào danh sách chọn.
        """
        self._add_current_course()
        return "break"   # tránh tiếng 'bíp' mặc định

    # ---------- detail preview ----------

    @staticmethod
    def _buoi_from_lesson(lesson_period: str) -> str:
        try:
            left = lesson_period.split("->")[0]
            first = int(left.replace("Tiết", "").replace("(", "")
                        .replace(")", "").replace("-", "").strip())
        except Exception:
            return "Không rõ buổi"

        if 1 <= first <= 5:
            return "Sáng"
        if 6 <= first <= 10:
            return "Chiều"
        if 11 <= first <= 14:
            return "Tối"
        return "Khác"

    @staticmethod
    def _weekday_vi(date_str: str) -> str:
        d = datetime.strptime(date_str, "%d-%m-%Y")
        mapping = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
        return mapping[d.weekday()]

    def _clear_detail(self):
        self.txt_detail.config(state="normal")
        self.txt_detail.delete("1.0", END)
        self.txt_detail.config(state="disabled")

    def _show_course_detail(self, key: tuple):
        sessions = sorted(
            self.options[key],
            key=lambda s: (
                self._date_sort_key(s.date),
                s.start,
            ),
        )

        course_code, subject_name, class_name, group = key
        group_str = f"Nhóm {group}" if group != 0 else "Không nhóm / chung lớp"
        lecturers = sorted({s.lecturer_name for s in sessions if s.lecturer_name})
        gv_desc = ", ".join(lecturers) if lecturers else "Chưa ghi GV"

        self.txt_detail.config(state="normal")
        self.txt_detail.delete("1.0", END)

        self.txt_detail.insert(END, f"Môn: {subject_name} [{course_code}]\n")
        self.txt_detail.insert(END, f"Lớp: {class_name}  |  {group_str}\n")
        self.txt_detail.insert(END, f"Giảng viên: {gv_desc}\n")
        self.txt_detail.insert(END, "-" * 70 + "\n")

        for s in sessions:
            weekday = self._weekday_vi(s.date)
            buoi = self._buoi_from_lesson(s.lesson_period)
            time_range = f"{s.start[:2]}:{s.start[2:4]} - {s.end[:2]}:{s.end[2:4]}"
            line = (
                f"{weekday} ({s.date}) - {buoi} - {s.subject_type}, "
                f"Tiết {s.lesson_period}, {time_range}, Phòng {s.room}\n"
            )
            self.txt_detail.insert(END, line)

        self.txt_detail.config(state="disabled")

    @staticmethod
    def _date_sort_key(date_str: str):
        d, m, y = date_str.split("-")
        return int(y), int(m), int(d)

    # ---------- add/remove course ----------

    def _add_current_course(self):
        if self.current_key is None:
            messagebox.showinfo("Chưa chọn môn", "Hãy chọn 1 môn bên trái trước.")
            return
        if self.current_key not in self.selected_keys:
            self.selected_keys.append(self.current_key)
            self._refresh_selected_list()

    def _remove_selected_course(self):
        if not self.lb_selected.curselection():
            messagebox.showinfo("Bỏ môn", "Hãy chọn 1 môn trong danh sách đã chọn.")
            return
        idx = self.lb_selected.curselection()[0]
        if 0 <= idx < len(self.selected_keys):
            del self.selected_keys[idx]
            self._refresh_selected_list()
    def _clear_all_courses(self):
        """
        Xoá toàn bộ các môn trong danh sách đã chọn.
        """
        if not self.selected_keys:
            messagebox.showinfo("Xoá tất cả", "Danh sách đang trống, không có gì để xoá.")
            return

        ans = messagebox.askyesno(
            "Xoá tất cả",
            "Bạn có chắc muốn xoá toàn bộ các môn đã chọn không?"
        )
        if not ans:
            return

        self.selected_keys.clear()
        self._refresh_selected_list()

    def _on_selected_delete(self, event=None):
        """
        Nhấn Delete / Backspace ở list môn đã chọn = xoá môn đó.
        """
        self._remove_selected_course()
        return "break"

    def _refresh_selected_list(self):
        self.lb_selected.delete(0, END)
        for key in self.selected_keys:
            self.lb_selected.insert(END, self._format_option_label(key))
        self._update_conflict_status()

    # ---------- conflicts & export ----------

    def _update_conflict_status(self):
        all_sessions = []
        for k in self.selected_keys:
            all_sessions.extend(self.options[k])

        if not all_sessions:
            self.lbl_conflict.config(
                text="Chưa chọn môn nào.",
                foreground="blue"
            )
            return

        conflicts = find_conflicts(all_sessions)
        if not conflicts:
            self.lbl_conflict.config(
                text="✅ Không trùng lịch.",
                foreground="green"
            )
        else:
            self.lbl_conflict.config(
                text=f"❌ Có {len(conflicts)} cặp trùng lịch (chi tiết in console).",
                foreground="red"
            )
            print_conflicts(conflicts)

    def _export_ics(self):
        all_sessions = []
        for k in self.selected_keys:
            all_sessions.extend(self.options[k])

        if not all_sessions:
            messagebox.showinfo(
                "Chưa có dữ liệu",
                "Bạn chưa chọn môn nào để xuất lịch."
            )
            return

        conflicts = find_conflicts(all_sessions)
        if conflicts:
            ans = messagebox.askyesno(
                "Có trùng lịch",
                "Lịch đang bị trùng. Bạn vẫn muốn xuất file ICS chứ?"
            )
            if not ans:
                return

        filename = filedialog.asksaveasfilename(
            title="Chọn nơi lưu file .ics",
            initialdir=self.ics_dir,
            defaultextension=".ics",
            filetypes=[("Lịch ICS", "*.ics"), ("Tất cả file", "*.*")],
        )
        if not filename:
            return

        create_ics_from_sessions(all_sessions, filename)
        messagebox.showinfo("Hoàn thành", f"Đã xuất file ICS:\n{filename}")


def main():
    root = Tk()
    app = ScheduleGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
