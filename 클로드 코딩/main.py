from __future__ import annotations

import customtkinter as ctk
from datetime import date as _Date
from app_controller import TodoController
from models import MemoManager
from ui_components import QuadrantFrame, AddEditDialog, CalendarView, FreeMatrixView, RepeatTasksView, HabitFullView
from tkinter import messagebox
import styles

_WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

_Q_ORDER = [
    (True,  True,  "#FFB800", "Q1  긴급 + 중요"),
    (False, True,  "#C47888", "Q2  중요"),
    (True,  False, "#6A9AB0", "Q3  긴급"),
    (False, False, "#9080B8", "Q4  기타"),
]


class TodoApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(styles.WINDOW_TITLE)
        self.geometry(styles.WINDOW_SIZE)
        self.minsize(800, 540)

        self._ctrl      = TodoController()
        self._memo_mgr  = MemoManager()
        self._cal_view:    CalendarView    | None = None
        self._free_view:   FreeMatrixView  | None = None
        self._repeat_view: RepeatTasksView | None = None
        self._habit_view:  HabitFullView   | None = None
        self._matrix_date: str = _Date.today().isoformat()
        self._memo_after_id = None
        self._refresh_pending = None

        self._build_header()

        self._content = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self._content.pack(fill="both", expand=True)

        # ── 매트릭스 컨테이너 ────────────────────────────────
        self._matrix_container = ctk.CTkFrame(self._content,
                                               fg_color="transparent",
                                               corner_radius=0)
        self._matrix_container.pack(fill="both", expand=True)

        # 날짜 표시 바 (상단)
        date_bar = ctk.CTkFrame(self._matrix_container, fg_color="transparent", height=30)
        date_bar.pack(fill="x", padx=8, pady=(6, 0))
        date_bar.pack_propagate(False)
        self._matrix_date_lbl = ctk.CTkLabel(
            date_bar, text="",
            font=("Malgun Gothic", 12, "bold"), text_color="gray40",
        )
        self._matrix_date_lbl.pack(side="left", padx=8)
        self._update_matrix_date_lbl()

        # 본문 = 왼쪽 사이드바 + 오른쪽 매트릭스
        body = ctk.CTkFrame(self._matrix_container, fg_color="transparent", corner_radius=0)
        body.pack(fill="both", expand=True)

        self._build_left_panel(body)

        right = ctk.CTkFrame(body, fg_color="transparent", corner_radius=0)
        right.pack(side="left", fill="both", expand=True)

        self._build_col_headers(right)
        self._build_matrix(right)

        self.after(50, self._refresh_matrix)
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ── 헤더 ──────────────────────────────────────────────

    def _build_header(self):
        header = ctk.CTkFrame(self, height=60, corner_radius=0,
                              fg_color=("gray92", "gray15"))
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="★ Todo Matrix",
                     font=styles.FONT_HEADER).pack(side="left", padx=16)

        # 햄버거 메뉴
        self._hamburger_btn = ctk.CTkButton(
            header, text="☰", width=36, height=36,
            font=("Malgun Gothic", 18),
            fg_color="transparent",
            text_color=("gray30", "gray80"),
            hover_color=("gray80", "gray30"),
            command=self._toggle_hamburger,
        )
        self._hamburger_btn.pack(side="left", padx=(0, 4))
        self._hamburger_menu = None

        today = _Date.today()
        wd    = _WEEKDAYS_KO[today.weekday()]
        ctk.CTkLabel(
            header,
            text=f"{today.year}년 {today.month}월 {today.day}일 ({wd})",
            font=styles.FONT_BODY, text_color="gray45",
        ).pack(side="left", padx=12)

        ctk.CTkButton(
            header, text="+ 새 할 일",
            width=120, height=40, font=styles.FONT_TITLE,
            command=self._on_add_click,
        ).pack(side="right", padx=(4, 16))

        self._btn_free = ctk.CTkButton(
            header, text="📝 전체 보기",
            width=110, height=40, font=styles.FONT_BODY,
            fg_color=("gray75", "gray35"),
            text_color=("gray10", "gray90"),
            hover_color=("gray65", "gray45"),
            command=self._show_free_view,
        )
        self._btn_free.pack(side="right", padx=4)

        self._btn_cal = ctk.CTkButton(
            header, text="📅 캘린더",
            width=100, height=40, font=styles.FONT_BODY,
            fg_color=("gray75", "gray35"),
            text_color=("gray10", "gray90"),
            hover_color=("gray65", "gray45"),
            command=self._show_calendar_view,
        )
        self._btn_cal.pack(side="right", padx=4)

        self._btn_matrix = ctk.CTkButton(
            header, text="📋 매트릭스",
            width=110, height=40, font=styles.FONT_BODY,
            fg_color=("gray60", "gray45"),
            text_color=("gray10", "gray90"),
            hover_color=("gray65", "gray45"),
            command=self._show_matrix_view,
        )
        self._btn_matrix.pack(side="right", padx=4)

        self._show_completed = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            header, text="완료된 항목 보기",
            variable=self._show_completed,
            font=styles.FONT_BODY,
            command=self._refresh_matrix,
        ).pack(side="right", padx=12)

    # ── 왼쪽 사이드바 ─────────────────────────────────────

    def _build_left_panel(self, parent):
        panel = ctk.CTkFrame(parent, width=220,
                              fg_color=("gray88", "gray18"), corner_radius=0)
        panel.pack(side="left", fill="y", padx=(4, 4), pady=4)
        panel.pack_propagate(False)

        # ── 메모 영역 ──────────────────────────────────────
        ctk.CTkLabel(panel, text="📝 메모",
                     font=("Malgun Gothic", 12, "bold"),
                     text_color="gray40", anchor="w").pack(
            fill="x", padx=10, pady=(10, 2))

        self._memo_box = ctk.CTkTextbox(
            panel, height=140,
            font=("Malgun Gothic", 12),
            corner_radius=6,
        )
        self._memo_box.pack(fill="x", padx=8, pady=(0, 4))
        self._load_memo_for_date()
        self._memo_box.bind("<KeyRelease>", self._on_memo_change)

        # 구분선
        ctk.CTkFrame(panel, height=1, fg_color="gray70").pack(
            fill="x", padx=8, pady=(4, 6))

        # ── 할일 요약 영역 ─────────────────────────────────
        ctk.CTkLabel(panel, text="📋 할일 목록",
                     font=("Malgun Gothic", 12, "bold"),
                     text_color="gray40", anchor="w").pack(
            fill="x", padx=10, pady=(0, 2))

        self._summary_frame = ctk.CTkScrollableFrame(
            panel, fg_color="transparent", corner_radius=0)
        self._summary_frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        # ── 새 할일 버튼 ───────────────────────────────────
        ctk.CTkButton(
            panel, text="+ 새 할 일",
            height=36, font=("Malgun Gothic", 12),
            command=self._on_add_click,
        ).pack(fill="x", padx=8, pady=(0, 8))

    # ── 할일 요약 갱신 ─────────────────────────────────────

    def _refresh_summary(self):
        if not hasattr(self, "_summary_frame"):
            return
        for w in self._summary_frame.winfo_children():
            w.destroy()

        show = self._show_completed.get()
        any_item = False

        for urgent, important, color, label in _Q_ORDER:
            items = self._ctrl.filter_by_quadrant(
                urgent, important, show_completed=show,
                date_filter=self._matrix_date,
            )
            if not items:
                continue
            any_item = True

            # 사분면 헤더 칩
            hdr = ctk.CTkFrame(self._summary_frame, fg_color=color,
                                corner_radius=5, height=24)
            hdr.pack(fill="x", padx=2, pady=(5, 1))
            hdr.pack_propagate(False)
            ctk.CTkLabel(hdr, text=label,
                         font=("Malgun Gothic", 10, "bold"),
                         text_color="white").pack(side="left", padx=8)

            for item in items:
                row = ctk.CTkFrame(self._summary_frame,
                                   fg_color="transparent", height=22)
                row.pack(fill="x", padx=2, pady=1)
                row.pack_propagate(False)

                # 색깔 점
                ctk.CTkFrame(row, width=7, height=7,
                              fg_color=color, corner_radius=4).pack(
                    side="left", padx=(6, 3))

                title = item.title[:20] + ("…" if len(item.title) > 20 else "")
                tc = "gray55" if item.completed else ("gray10", "gray90")
                lbl = ctk.CTkLabel(row, text=title,
                                   font=("Malgun Gothic", 11),
                                   text_color=tc, anchor="w")
                lbl.pack(side="left", fill="x", expand=True)

        if not any_item:
            ctk.CTkLabel(self._summary_frame, text="이 날의 할일이 없습니다",
                         font=("Malgun Gothic", 11),
                         text_color="gray60").pack(pady=24)

    # ── 메모 저장 ──────────────────────────────────────────

    def _on_memo_change(self, event=None):
        if self._memo_after_id:
            self.after_cancel(self._memo_after_id)
        self._memo_after_id = self.after(800, self._save_memo)

    def _save_memo(self):
        text = self._memo_box.get("1.0", "end-1c")
        self._memo_mgr.save(self._matrix_date, text)

    def _load_memo_for_date(self):
        self._memo_box.delete("1.0", "end")
        text = self._memo_mgr.load(self._matrix_date)
        if text:
            self._memo_box.insert("1.0", text)

    # ── 매트릭스 레이아웃 ─────────────────────────────────

    def _build_col_headers(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent", height=32)
        row.pack(fill="x", padx=8)
        row.pack_propagate(False)
        ctk.CTkFrame(row, width=64, fg_color="transparent").pack(side="left")
        for text in ["긴급함", "긴급하지 않음"]:
            ctk.CTkLabel(row, text=text,
                         font=("Malgun Gothic", 12, "bold"),
                         text_color="gray40").pack(side="left", expand=True, fill="x")

    def _build_matrix(self, parent):
        matrix = ctk.CTkFrame(parent, fg_color="transparent")
        matrix.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        matrix.grid_columnconfigure(0, weight=0, minsize=64)
        matrix.grid_columnconfigure(1, weight=1)
        matrix.grid_columnconfigure(2, weight=1)
        matrix.grid_rowconfigure(0, weight=1)
        matrix.grid_rowconfigure(1, weight=1)

        for r, text in enumerate(["중요함", "중요하지\n않음"]):
            ctk.CTkLabel(matrix, text=text,
                         font=("Malgun Gothic", 11, "bold"),
                         text_color="gray40").grid(row=r, column=0, sticky="nsew")

        self._quadrants: dict[tuple, QuadrantFrame] = {}
        config = [
            (0, 1, True,  True,  "#FFB800"),
            (0, 2, False, True,  "#C47888"),
            (1, 1, True,  False, "#6A9AB0"),
            (1, 2, False, False, "#9080B8"),
        ]
        for r, c, urgent, important, color in config:
            q = QuadrantFrame(
                matrix,
                urgent=urgent, important=important, color=color,
                on_toggle=self._on_toggle,
                on_edit=self._on_edit,
                on_delete=self._on_delete,
                on_add_quadrant=self._on_add_quadrant,
                on_move=self._on_move,
            )
            q.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)
            self._quadrants[(urgent, important)] = q

    # ── 갱신 ──────────────────────────────────────────────

    def _schedule_refresh(self):
        """중복 갱신 방지: 이전 예약이 있으면 취소 후 새로 예약."""
        if self._refresh_pending is not None:
            self.after_cancel(self._refresh_pending)
        self._refresh_pending = self.after(120, self._refresh_matrix)

    def _refresh_matrix(self):
        self._refresh_pending = None
        show = self._show_completed.get()
        for (urgent, important), q_frame in self._quadrants.items():
            items = self._ctrl.filter_by_quadrant(
                urgent, important,
                show_completed=show,
                date_filter=self._matrix_date,
            )
            q_frame.update_items(items)
        self._refresh_summary()

    # ── 이벤트 핸들러 ────────────────────────────────────

    def _on_add_click(self):
        categories = self._ctrl.get_categories(styles.DEFAULT_CATEGORIES)
        AddEditDialog(
            self, categories=categories, item=None, on_save=self._handle_add,
            default_urgent=False, default_important=True,
            default_due_date=self._matrix_date,
        )

    def _on_add_quadrant(self, urgent: bool, important: bool):
        categories = self._ctrl.get_categories(styles.DEFAULT_CATEGORIES)
        AddEditDialog(
            self, categories=categories, item=None, on_save=self._handle_add,
            default_urgent=urgent, default_important=important,
            default_due_date=self._matrix_date,
        )

    def _handle_add(self, data: dict):
        self._ctrl.add_item(**data)
        self._schedule_refresh()

    def _on_toggle(self, item_id: str):
        self._ctrl.toggle_complete(item_id)
        self._schedule_refresh()

    def _on_edit(self, item_id: str):
        item = next((i for i in self._ctrl.get_all() if i.id == item_id), None)
        if item is None:
            return
        categories = self._ctrl.get_categories(styles.DEFAULT_CATEGORIES)
        AddEditDialog(
            self, categories=categories, item=item,
            on_save=lambda data: self._handle_edit(item_id, data),
        )

    def _handle_edit(self, item_id: str, data: dict):
        self._ctrl.update_item(item_id, **data)
        self._schedule_refresh()

    def _on_delete(self, item_id: str):
        item = next((i for i in self._ctrl.get_all() if i.id == item_id), None)
        if item and messagebox.askyesno("삭제 확인", f"'{item.title}'을(를) 삭제할까요?"):
            self._ctrl.delete_item(item_id)
            self._schedule_refresh()

    def _on_move(self, item_id: str, x_root: int, y_root: int):
        for (urgent, important), qframe in self._quadrants.items():
            qx = qframe.winfo_rootx()
            qy = qframe.winfo_rooty()
            qw = qframe.winfo_width()
            qh = qframe.winfo_height()
            if qx <= x_root <= qx + qw and qy <= y_root <= qy + qh:
                self._ctrl.update_item(item_id, urgent=urgent, important=important)
                self._schedule_refresh()
                return

    # ── 햄버거 메뉴 ─────────────────────────────────────

    def _toggle_hamburger(self):
        if self._hamburger_menu and self._hamburger_menu.winfo_exists():
            self._hamburger_menu.destroy()
            self._hamburger_menu = None
            return

        import tkinter as tk
        menu = tk.Toplevel(self)
        menu.overrideredirect(True)
        menu.attributes("-topmost", True)

        x = self._hamburger_btn.winfo_rootx()
        y = self._hamburger_btn.winfo_rooty() + self._hamburger_btn.winfo_height() + 2
        menu.geometry(f"+{x}+{y}")

        frame = ctk.CTkFrame(menu, fg_color=("white", "gray20"),
                              corner_radius=8, border_width=1,
                              border_color=("gray80", "gray40"))
        frame.pack()

        def make_item(text, cmd):
            btn = ctk.CTkButton(
                frame, text=text, anchor="w",
                width=180, height=36,
                font=("Malgun Gothic", 12),
                fg_color="transparent",
                text_color=("gray15", "gray90"),
                hover_color=("gray90", "gray30"),
                command=lambda: (menu.destroy(), cmd()),
            )
            btn.pack(fill="x", padx=4, pady=2)

        make_item("🔁  반복 할 일 관리", self._show_repeat_view)
        make_item("✅  습관 체크 관리", self._show_habit_view)

        self._hamburger_menu = menu
        menu.bind("<FocusOut>", lambda e: menu.destroy())
        menu.focus_set()

    # ── 뷰 전환 ──────────────────────────────────────────

    def _set_active_btn(self, active: str):
        self._btn_matrix.configure(fg_color=("gray60","gray45") if active=="matrix" else ("gray75","gray35"))
        self._btn_cal.configure(fg_color=("gray60","gray45") if active=="cal" else ("gray75","gray35"))
        self._btn_free.configure(fg_color=("gray60","gray45") if active=="free" else ("gray75","gray35"))

    def _hide_all(self):
        self._matrix_container.pack_forget()
        if self._cal_view:
            self._cal_view.pack_forget()
        if self._free_view:
            self._free_view.pack_forget()
        if self._repeat_view:
            self._repeat_view.pack_forget()
        if self._habit_view:
            self._habit_view.pack_forget()

    def _update_matrix_date_lbl(self):
        try:
            d = _Date.fromisoformat(self._matrix_date)
            wd = _WEEKDAYS_KO[d.weekday()]
            self._matrix_date_lbl.configure(
                text=f"{d.year}년 {d.month}월 {d.day}일 ({wd}) 할일 목록"
            )
        except Exception:
            self._matrix_date_lbl.configure(text="")

    def _show_matrix_view(self, date_str: str | None = None):
        if date_str:
            self._matrix_date = date_str
        self._hide_all()
        self._matrix_container.pack(fill="both", expand=True)
        self._set_active_btn("matrix")
        self._update_matrix_date_lbl()
        self._load_memo_for_date()
        self._schedule_refresh()

    def _show_calendar_view(self):
        self._save_memo()
        self._hide_all()
        if self._cal_view is not None:
            self._cal_view.destroy()
            self._cal_view = None
        categories = self._ctrl.get_categories(styles.DEFAULT_CATEGORIES)
        self._cal_view = CalendarView(
            self._content,
            controller=self._ctrl,
            on_item_saved=self._handle_cal_add,
            categories=categories,
            on_back=self._show_matrix_view,
            on_date_select=self._show_matrix_view,
        )
        self._cal_view.pack(fill="both", expand=True)
        self._set_active_btn("cal")

    def _show_free_view(self):
        self._save_memo()
        self._hide_all()
        if self._free_view is None:
            self._free_view = FreeMatrixView(self._content)
        self._free_view.pack(fill="both", expand=True)
        self._set_active_btn("free")

    def _show_repeat_view(self):
        self._save_memo()
        self._hide_all()
        if self._repeat_view is not None:
            self._repeat_view.destroy()
        self._repeat_view = RepeatTasksView(
            self._content,
            controller=self._ctrl,
            on_refresh_matrix=self._refresh_matrix,
        )
        self._repeat_view.pack(fill="both", expand=True)
        self._set_active_btn("")  # 모든 탭 비활성

    def _show_habit_view(self):
        self._save_memo()
        self._hide_all()
        if self._habit_view is not None:
            self._habit_view.destroy()
        self._habit_view = HabitFullView(self._content)
        self._habit_view.pack(fill="both", expand=True)
        self._set_active_btn("")

    def _handle_cal_add(self, data: dict):
        self._ctrl.add_item(**data)
        self._schedule_refresh()
        if self._cal_view:
            self.after(150, self._cal_view.refresh_events)

    def _on_closing(self):
        self._save_memo()
        self._ctrl._save()
        self.destroy()


if __name__ == "__main__":
    app = TodoApp()
    app.mainloop()
