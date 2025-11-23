# main_gui.py
import os
import sys      # 👈 THÊM DÒNG NÀY
import json
from datetime import datetime

from tkinter import (
    Tk, Listbox, Text, Scrollbar, END, SINGLE,
    BOTH, VERTICAL, HORIZONTAL, BooleanVar,
    Toplevel, Entry
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

import webbrowser
from pathlib import Path
from read_ics import build_html_from_ics
from down_html import download_for_class  # dùng để tải html cho từng lớp


class ScheduleGUI:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Schedule Checker")
        self.root.geometry("1200x700")
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.focus_force()
        self.root.after(300, lambda: self.root.attributes('-topmost', False))
        self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.html_dir = os.path.join(self.base_dir, "html_all_classes")
        self.ics_dir = os.path.join(self.base_dir, "ics_output")
        self.config_path = os.path.join(self.base_dir, "config.json")
        os.makedirs(self.ics_dir, exist_ok=True)

        # ===== Set icon cho cửa sổ (dùng data file bên trong onefile) =====
        try:
            runtime_dir = os.path.dirname(__file__)  # thư mục code được Nuitka giải nén
        except NameError:
            runtime_dir = self.base_dir              # fallback khi chạy chưa compile

        icon_path = os.path.join(runtime_dir, "app.ico")  # trùng với target "app.ico"
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(default=icon_path)
            except Exception as e:
                print("Không set được icon:", e)
        else:
            print("Không tìm thấy icon:", icon_path)

        os.makedirs(self.ics_dir, exist_ok=True)
        os.makedirs(self.html_dir, exist_ok=True)


        os.makedirs(self.ics_dir, exist_ok=True)
        os.makedirs(self.html_dir, exist_ok=True)

        # ====== BIẾN TRẠNG THÁI ======
        self.config: dict = {}
        self.registered_classes: list[str] = []

        self.all_sessions = []
        self.options = {}
        self.all_keys: list[tuple] = []
        self.filtered_keys: list[tuple] = []
        self.selected_keys: list[tuple] = []
        self.current_key: tuple | None = None
        self.subject_names: list[str] = []
        # Để biết có đang trùng lịch không (tránh popup liên tục)
        self._had_conflict_popup = False

        # cửa sổ cấu hình lớp đăng ký
        self.reg_window = None
        self.lb_reg_classes = None
        self.entry_reg = None

        # ====== BUILD UI ======
        self._build_ui()

        # ====== LOAD CONFIG & BOOTSTRAP ======
        self._load_config_and_bootstrap()

    # ===================== CONFIG / DOWNLOAD =====================

    def _load_config_and_bootstrap(self):
        """Đọc config.json, lấy danh sách lớp, tải HTML và load lịch."""
        # 1) Đọc config.json
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    print("⚠ config.json không phải dạng object {}, bỏ qua.")
                    data = {}
                self.config = data
        except FileNotFoundError:
            print("⚠ Không tìm thấy config.json, dùng config rỗng.")
            self.config = {}
        except Exception as e:
            print(f"⚠ Lỗi đọc config.json: {e}")
            self.config = {}

        # 2) Đồng bộ danh sách lớp
        raw = self.config.get("classes", [])
        classes: list[str] = []
        if isinstance(raw, list):
            for c in raw:
                code = str(c).strip().upper()
                if code and code not in classes:
                    classes.append(code)
        self.registered_classes = classes
        self.config["classes"] = self.registered_classes

        # 3) Nếu có lớp -> tải html + load lịch
        if self.registered_classes:
            self._download_html_for_registered_classes()
            self._reload_sessions_from_html()
        else:
            # Không có lớp: vẫn load thử html hiện có (nếu có),
            # rồi mở cửa sổ "Lớp đăng ký" để nhắc người dùng.
            self._reload_sessions_from_html()
            messagebox.showinfo(
                "Chưa có lớp đăng ký",
                "config.json chưa có danh sách lớp ('classes').\n"
                "Hãy thêm các lớp đăng ký."
            )
            self._open_registered_classes_window(auto_open=True)

    def _save_config(self):
        """Ghi self.config ra config.json."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            print(f"✅ Đã lưu config vào {self.config_path}")
        except Exception as e:
            messagebox.showwarning(
                "Lỗi lưu config",
                f"Không lưu được config.json:\n{e}"
            )

    def _download_html_for_registered_classes(self):
        """Tải HTML lịch học cho toàn bộ lớp trong self.registered_classes (hiện màn loading đơn giản)."""
        if not self.registered_classes:
            return

        win = Toplevel(self.root)
        win.title("Đang tải lịch các lớp")
        win.resizable(False, False)

        lbl = ttk.Label(win, text="Đang chuẩn bị...", padding=10)
        lbl.pack(fill="x")

        pb = ttk.Progressbar(win, mode="determinate", maximum=len(self.registered_classes))
        pb.pack(fill="x", padx=10, pady=(0, 10))

        win.update_idletasks()

        total = len(self.registered_classes)
        for idx, cls in enumerate(self.registered_classes, start=1):
            lbl.config(text=f"Đang tải lịch cho lớp {cls} ({idx}/{total})...")
            pb["value"] = idx - 1
            win.update()

            try:
                download_for_class(cls)
            except Exception as e:
                print(f"⛔ Lỗi tải lớp {cls}: {e}")

        pb["value"] = total
        lbl.config(text="Hoàn tất tải lịch.")
        win.update()
        win.destroy()

    def _reload_sessions_from_html(self):
        """Đọc lại toàn bộ html_all_classes -> self.options, self.subject_names, ..."""
        print(f"Đang đọc các file HTML trong: {self.html_dir}")
        try:
            self.all_sessions = load_all_sessions(self.html_dir)
        except FileNotFoundError:
            self.all_sessions = []
        print(f"Đã load {len(self.all_sessions)} buổi học (session).")

        # build options
        if self.all_sessions:
            self.options = build_course_options(self.all_sessions)
            self.all_keys = sorted(
                self.options.keys(),
                key=lambda k: (k[1], k[2], k[3])  # subject_name, class_name, group
            )
            self.filtered_keys = list(self.all_keys)
            self.subject_names = sorted({k[1] for k in self.options.keys()})
        else:
            self.options = {}
            self.all_keys = []
            self.filtered_keys = []
            self.subject_names = []

        # reset chọn môn
        self.selected_keys.clear()
        self.current_key = None

        self._refresh_subject_combobox()
        self._update_course_list()
        self._clear_detail()
        self.lb_selected.delete(0, END)
        self._update_conflict_status()

    # ===================== UI SETUP =====================

    def _build_ui(self):
        paned_main = ttk.Panedwindow(self.root, orient="horizontal")
        paned_main.pack(fill=BOTH, expand=True)

        frame_left = ttk.Frame(paned_main, padding=5)
        frame_right = ttk.Frame(paned_main, padding=5)
        paned_main.add(frame_left, weight=1)
        paned_main.add(frame_right, weight=2)

        # ----- LEFT: filter môn + danh sách môn -----
        lbl_class = ttk.Label(frame_left, text="Lọc theo môn học:")
        lbl_class.pack(anchor="w")

        self.cmb_class = ttk.Combobox(
            frame_left,
            state="readonly"
        )
        self.cmb_class.pack(fill="x", pady=(0, 5))
        self.cmb_class.bind("<<ComboboxSelected>>", self._on_class_changed)

        # checkbox: chỉ hiện các lớp không trùng với các môn đã chọn
        self.var_filter_non_conflict = BooleanVar(value=False)
        chk_non_conflict = ttk.Checkbutton(
            frame_left,
            text="Chỉ hiện lớp không trùng với môn đã chọn",
            variable=self.var_filter_non_conflict,
            command=self._on_non_conflict_toggle,
        )
        chk_non_conflict.pack(anchor="w", pady=(0, 5))

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
        # phím tắt
        self.lb_courses.bind("<Double-Button-1>", self._on_course_double_click)
        self.lb_courses.bind("<Up>", self._on_course_key)
        self.lb_courses.bind("<Down>", self._on_course_key)
        self.lb_courses.bind("<Prior>", self._on_course_key)   # PageUp
        self.lb_courses.bind("<Next>", self._on_course_key)    # PageDown
        self.lb_courses.bind("<Return>", self._on_course_enter)  # Enter = thêm môn

        # --- KHU VỰC CẤU HÌNH LỚP ĐĂNG KÝ ---
        ttk.Label(
            frame_left,
            text="Lớp đăng ký (lưu trong config.json):"
        ).pack(anchor="w", pady=(5, 0))

        btn_reg_classes = ttk.Button(
            frame_left,
            text="📚 Lớp đăng ký...",
            command=self._open_registered_classes_window
        )
        btn_reg_classes.pack(anchor="w", pady=(0, 5))

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

        # phím tắt list đã chọn
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

        # Nút liên hệ
        btn_contact = ttk.Button(
            frame_btns, text="📞 Liên hệ", command=self._open_contact_page
        )
        btn_contact.pack(side="right")

        btn_export = ttk.Button(
            frame_btns, text="💾 Xuất ICS...", command=self._export_ics
        )
        btn_export.pack(side="right", padx=(5, 0))


        self.lbl_conflict = ttk.Label(
            frame_selected,
            text="Chưa chọn môn nào.",
            foreground="blue"
        )
        self.lbl_conflict.pack(anchor="w")

        # refresh combobox ban đầu (chưa có dữ liệu)
        self._refresh_subject_combobox()

    # ===================== LỚP ĐĂNG KÝ (UI) =====================

    # ===================== LỚP ĐĂNG KÝ (UI) =====================

    def _open_registered_classes_window(self, auto_open: bool = False):
        # Nếu cửa sổ đã mở rồi thì đưa lên trước
        if self.reg_window is not None and self.reg_window.winfo_exists():
            self.reg_window.lift()
            return

        win = Toplevel(self.root)
        win.title("Lớp đăng ký (config.json)")
        self.reg_window = win

        # 👉 Đặt kích thước và canh giữa so với cửa sổ chính
        width, height = 420, 320

        self.root.update_idletasks()
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_w = self.root.winfo_width()
        root_h = self.root.winfo_height()

        x = root_x + (root_w - width) // 2
        y = root_y + (root_h - height) // 2
        win.geometry(f"{width}x{height}+{x}+{y}")

        ttk.Label(
            win,
            text="Danh sách lớp đăng ký (mỗi mã 1 dòng):"
        ).pack(anchor="w", padx=10, pady=(10, 2))

        frame_lb = ttk.Frame(win)
        frame_lb.pack(fill=BOTH, expand=True, padx=10)

        self.lb_reg_classes = Listbox(frame_lb, selectmode=SINGLE)
        self.lb_reg_classes.grid(row=0, column=0, sticky="nsew")

        reg_scroll_y = Scrollbar(frame_lb, orient=VERTICAL,
                                 command=self.lb_reg_classes.yview)
        reg_scroll_y.grid(row=0, column=1, sticky="ns")
        self.lb_reg_classes.config(yscrollcommand=reg_scroll_y.set)

        frame_lb.rowconfigure(0, weight=1)
        frame_lb.columnconfigure(0, weight=1)

        self.lb_reg_classes.bind("<<ListboxSelect>>", self._on_reg_select)

        # ---- Ô nhập mã lớp ----
        frame_entry = ttk.Frame(win)
        frame_entry.pack(fill="x", padx=10, pady=(5, 5))
        ttk.Label(frame_entry, text="Mã lớp:").pack(side="left")

        self.entry_reg = Entry(frame_entry)
        self.entry_reg.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # 👉 Nhấn Enter trong ô nhập = thêm lớp luôn
        self.entry_reg.bind("<Return>", lambda event: self._reg_add())
        self.entry_reg.focus_set()

        # ---- Các nút thao tác ----
        frame_btns = ttk.Frame(win)
        frame_btns.pack(fill="x", padx=10, pady=(0, 10))

        btn_add = ttk.Button(frame_btns, text="➕ Thêm", command=self._reg_add)
        btn_add.pack(side="left")

        btn_update = ttk.Button(frame_btns, text="✏ Sửa", command=self._reg_update)
        btn_update.pack(side="left", padx=(5, 0))

        btn_delete = ttk.Button(frame_btns, text="🗑 Xoá", command=self._reg_delete)
        btn_delete.pack(side="left", padx=(5, 0))

        btn_save_reload = ttk.Button(
            frame_btns,
            text="💾 Lưu & tải lịch",
            command=self._reg_save_and_reload
        )
        btn_save_reload.pack(side="right")

        if auto_open:
            ttk.Label(
                win,
                text="⚠ Chưa có lớp trong config.json.\n"
                     "Hãy thêm ít nhất 1 lớp rồi bấm 'Lưu & tải lịch'.",
                foreground="red"
            ).pack(anchor="w", padx=10, pady=(0, 5))

        # Đổ dữ liệu list lớp vào listbox
        self._reg_refresh_listbox()

        win.transient(self.root)
        win.grab_set()


    def _reg_refresh_listbox(self):
        if not self.lb_reg_classes:
            return
        self.lb_reg_classes.delete(0, END)
        for code in self.registered_classes:
            self.lb_reg_classes.insert(END, code)

    def _on_reg_select(self, event=None):
        if not self.lb_reg_classes.curselection():
            return
        idx = self.lb_reg_classes.curselection()[0]
        if 0 <= idx < len(self.registered_classes):
            code = self.registered_classes[idx]
            self.entry_reg.delete(0, END)
            self.entry_reg.insert(0, code)

    def _save_registered_classes_to_config(self):
        # loại trùng, loại rỗng
        cleaned = []
        for c in self.registered_classes:
            c = str(c).strip().upper()
            if c and c not in cleaned:
                cleaned.append(c)
        self.registered_classes = cleaned
        self.config["classes"] = self.registered_classes
        self._save_config()
        self._reg_refresh_listbox()

    def _reg_add(self):
        code = self.entry_reg.get().strip().upper()
        if not code:
            messagebox.showinfo("Thiếu mã lớp", "Hãy nhập mã lớp.")
            return
        if code in self.registered_classes:
            messagebox.showinfo("Trùng", "Mã lớp này đã có trong danh sách.")
            return

        self.registered_classes.append(code)
        self.registered_classes.sort()
        self._save_registered_classes_to_config()

        # 👉 Sau khi thêm xong thì reset textbox + focus lại
        self.entry_reg.delete(0, END)
        self.entry_reg.focus_set()


    def _reg_update(self):
        if not self.lb_reg_classes.curselection():
            messagebox.showinfo("Chưa chọn lớp", "Hãy chọn 1 lớp để sửa.")
            return
        idx = self.lb_reg_classes.curselection()[0]
        code = self.entry_reg.get().strip().upper()
        if not code:
            messagebox.showinfo("Thiếu mã lớp", "Hãy nhập mã lớp.")
            return
        if code in self.registered_classes and self.registered_classes[idx] != code:
            messagebox.showinfo("Trùng", "Mã lớp này đã tồn tại.")
            return
        self.registered_classes[idx] = code
        self.registered_classes.sort()
        self._save_registered_classes_to_config()

    def _reg_delete(self):
        if not self.lb_reg_classes.curselection():
            messagebox.showinfo("Chưa chọn lớp", "Hãy chọn 1 lớp để xoá.")
            return

        idx = self.lb_reg_classes.curselection()[0]
        code = self.registered_classes[idx]

        if not messagebox.askyesno(
            "Xoá lớp",
            f"Bạn chắc chắn muốn xoá lớp {code} khỏi config và xoá cả file HTML?"
        ):
            return

        # --- XOÁ FILE HTML TƯƠNG ỨNG ---
        # file dạng: html_all_classes/<MÃ_LỚP>.html
        html_path = os.path.join(self.html_dir, f"{code}.html")
        try:
            if os.path.exists(html_path):
                os.remove(html_path)
                print(f"🗑 Đã xoá file HTML: {html_path}")
            else:
                print(f"ℹ Không tìm thấy file HTML để xoá: {html_path}")
        except Exception as e:
            print(f"⚠ Không xoá được file HTML {html_path}: {e}")

        # --- XOÁ KHỎI DANH SÁCH VÀ LƯU VÀO CONFIG ---
        del self.registered_classes[idx]
        self._save_registered_classes_to_config()


    def _reg_save_and_reload(self):
        if not self.registered_classes:
            messagebox.showinfo("Chưa có lớp", "Danh sách lớp đang trống, hãy thêm ít nhất 1 lớp.")
            return

        # đã _save_registered_classes_to_config nên chỉ cần tải lại
        self._save_registered_classes_to_config()

        # đóng cửa sổ
        if self.reg_window is not None and self.reg_window.winfo_exists():
            self.reg_window.destroy()
            self.reg_window = None

        # tải html + reload lịch
        self._download_html_for_registered_classes()
        self._reload_sessions_from_html()

    # ===================== helpers =====================

    def _refresh_subject_combobox(self):
        if not hasattr(self, "cmb_class"):
            return
        values = ["Tất cả môn"] + (self.subject_names or [])
        self.cmb_class["values"] = values
        if values:
            try:
                self.cmb_class.current(0)
            except Exception:
                pass

    def _format_option_label(self, key: tuple) -> str:
        course_code, subject_name, class_name, group = key
        sess_list = self.options[key]

        # Lấy danh sách giảng viên trong các buổi
        lecturers = sorted({s.lecturer_name for s in sess_list if s.lecturer_name})
        gv_desc = ", ".join(lecturers) if lecturers else ""

        if group == 0:
            # Môn không chia nhóm
            if gv_desc:
                return f"{subject_name} - {class_name} - {gv_desc}"
            else:
                return f"{subject_name} - {class_name}"
        else:
            # Môn có nhóm
            if gv_desc:
                return f"{subject_name} - {class_name} - Nhóm {group} - {gv_desc}"
            else:
                return f"{subject_name} - {class_name} - Nhóm {group}"

    def _update_course_list(self):
        self.lb_courses.delete(0, END)

        # Lọc theo combobox "Tất cả môn" / 1 môn cụ thể
        selected_subject = self.cmb_class.get()
        if selected_subject in ("", "Tất cả môn"):
            keys = list(self.all_keys)
        else:
            keys = [
                k for k in self.all_keys
                if k[1] == selected_subject  # k[1] = subject_name
            ]

        # Ẩn TẤT CẢ các lựa chọn của những môn đã chọn rồi (theo TÊN MÔN)
        if self.selected_keys:
            chosen_subject_names = {k[1] for k in self.selected_keys}
            keys = [k for k in keys if k[1] not in chosen_subject_names]

        # Nếu đang bật chế độ "chỉ hiện lớp không trùng" và đã có môn được chọn
        if getattr(self, "var_filter_non_conflict", None) is not None \
           and self.var_filter_non_conflict.get() and self.selected_keys:

            # Gom tất cả session của các môn đã chọn
            selected_sessions = []
            for sk in self.selected_keys:
                selected_sessions.extend(self.options[sk])

            non_conflicting_keys = []
            for k in keys:
                candidate_sessions = self.options[k]
                if not self._has_conflict_with_selected(
                    selected_sessions,
                    candidate_sessions,
                ):
                    non_conflicting_keys.append(k)

            keys = non_conflicting_keys

        self.filtered_keys = keys
        for key in self.filtered_keys:
            self.lb_courses.insert(END, self._format_option_label(key))

    def _has_conflict_with_selected(
        self,
        selected_sessions: list,
        candidate_sessions: list,
    ) -> bool:
        """
        Trả về True nếu candidate_sessions tạo thêm xung đột
        với selected_sessions (hoặc tự xung đột với chính nó).
        """
        if not candidate_sessions or not selected_sessions:
            return False

        combined = list(selected_sessions) + list(candidate_sessions)
        conflicts = find_conflicts(combined)
        if not conflicts:
            return False

        # chỉ quan tâm xung đột trong đó có ít nhất 1 buổi thuộc môn candidate
        for a, b in conflicts:
            in_candidate_a = a in candidate_sessions
            in_candidate_b = b in candidate_sessions
            if in_candidate_a or in_candidate_b:
                return True

        return False

    # ===================== event handlers =====================

    def _on_class_changed(self, event=None):
        self._update_course_list()
        self._clear_detail()

    def _on_non_conflict_toggle(self):
        """Bật/tắt chế độ chỉ hiện các lớp không trùng với môn đã chọn."""
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
        """Khi nhấn ↑ ↓ PageUp PageDown, Tkinter tự đổi selection -> update detail."""
        self.root.after(0, self._on_course_select)

    def _on_course_enter(self, event=None):
        """Nhấn Enter ở list bên trái = thêm môn hiện tại vào danh sách chọn."""
        self._add_current_course()
        return "break"

    def _on_course_double_click(self, event=None):
        """Click đúp vào một môn ở list bên trái = chọn + thêm vào danh sách đã chọn."""
        self._on_course_select()
        self._add_current_course()
        return "break"

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
            self.options.get(key, []),
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
        """Xoá toàn bộ các môn trong danh sách đã chọn."""
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
        """Nhấn Delete / Backspace ở list môn đã chọn = xoá môn đó."""
        self._remove_selected_course()
        return "break"

    def _refresh_selected_list(self):
        self.lb_selected.delete(0, END)
        for key in self.selected_keys:
            self.lb_selected.insert(END, self._format_option_label(key))

        self._update_conflict_status()
        # Sau khi thêm/bỏ môn, luôn cập nhật lại list bên trái
        self._update_course_list()

    # ---------- conflicts & export ----------
    def _format_conflicts_text(self, conflicts):
        """
        Tạo chuỗi text đẹp để hiện trong messagebox cho các cặp trùng lịch.
        """
        lines = []
        for idx, (a, b) in enumerate(conflicts, start=1):
            lines.append(
                f"{idx}. {a.date} - tiết {a.lesson_period}\n"
                f"   {a.subject_name} ({a.class_name}, nhóm {a.group}, phòng {a.room})\n"
                f"   ↔ {b.subject_name} ({b.class_name}, nhóm {b.group}, phòng {b.room})"
            )
            # Giới hạn cho đỡ dài, cần thì bỏ giới hạn này
            if idx >= 10:
                remaining = len(conflicts) - idx
                if remaining > 0:
                    lines.append(f"... và còn {remaining} cặp trùng khác.")
                break

        return "\n\n".join(lines)

    def _update_conflict_status(self):
        all_sessions = []
        for k in self.selected_keys:
            all_sessions.extend(self.options.get(k, []))

        if not all_sessions:
            self.lbl_conflict.config(
                text="Chưa chọn môn nào.",
                foreground="blue"
            )
            self._had_conflict_popup = False
            return

        conflicts = find_conflicts(all_sessions)
        if not conflicts:
            self.lbl_conflict.config(
                text="✅ Không trùng lịch.",
                foreground="green"
            )
            self._had_conflict_popup = False
        else:
            self.lbl_conflict.config(
                text=f"❌ Có {len(conflicts)} cặp trùng lịch (chi tiết in console).",
                foreground="red"
            )
            print_conflicts(conflicts)

            # 👉 Hiện messagebox + chi tiết các cặp trùng
            if not self._had_conflict_popup:
                detail_text = self._format_conflicts_text(conflicts)
                messagebox.showwarning(
                    "Trùng lịch",
                    f"Đang có {len(conflicts)} cặp buổi học trùng lịch:\n\n{detail_text}"
                )
                self._had_conflict_popup = True


    def _export_ics(self):
        all_sessions = []
        for k in self.selected_keys:
            all_sessions.extend(self.options.get(k, []))

        if not all_sessions:
            messagebox.showinfo(
                "Chưa có dữ liệu",
                "Bạn chưa chọn môn nào để xuất lịch."
            )
            return
        # Cảnh báo nếu có trùng lịch
        conflicts = find_conflicts(all_sessions)
        if conflicts:
            ans = messagebox.askyesno(
                "Có trùng lịch",
                "Lịch đang bị trùng. Bạn vẫn muốn xuất file ICS chứ?"
            )
            if not ans:
                return

        # Chọn nơi lưu ICS
        filename = filedialog.asksaveasfilename(
            title="Chọn nơi lưu file .ics",
            initialdir=self.ics_dir,
            defaultextension=".ics",
            filetypes=[("Lịch ICS", "*.ics"), ("Tất cả file", "*.*")],
        )
        if not filename:
            return

        # 1) Xuất ICS
        create_ics_from_sessions(all_sessions, filename)

        # 2) Đọc ICS -> tạo file HTML viewer (đặt cạnh file ICS)
        try:
            html_path = build_html_from_ics(
                filename,
                output_dir=os.path.dirname(filename) or ".",
            )
        except Exception as e:
            messagebox.showwarning(
                "Lỗi khi tạo HTML",
                f"Đã xuất file ICS:\n{filename}\n\n"
                f"Nhưng gặp lỗi khi đọc ICS để tạo file HTML:\n{e}"
            )
            return

        # Đường dẫn dạng URI để webbrowser mở được
        html_uri = Path(html_path).resolve().as_uri()

        msg = (
            "Đã xuất xong file ICS và file HTML.\n\n"
            f"ICS:\n{filename}\n\n"
            f"HTML:\n{html_path}\n\n"
            "Bạn có muốn mở file HTML ngay không?"
        )

        # 3) Hỏi người dùng có muốn mở HTML
        if messagebox.askyesno("Hoàn thành", msg):
            webbrowser.open(html_uri)
    # Mở contact
    def _open_contact_page(self):
        """Mở trang liên hệ trên trình duyệt mặc định."""
        url = "https://facebook.com/anbelucle25"  # 🔧 Đổi link này thành trang bạn muốn
        try:
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror(
                "Lỗi mở trang liên hệ",
                f"Không mở được trình duyệt.\n\nChi tiết: {e}"
            )

def main():
    root = Tk()
    app = ScheduleGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
