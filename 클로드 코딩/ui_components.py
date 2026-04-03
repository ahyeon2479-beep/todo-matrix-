from __future__ import annotations

import calendar as _cal
import tkinter as _tk


def _month_grid(year: int, month: int) -> list[list[tuple]]:
    """일요일 시작 6×7 그리드. 각 셀: (day, year, month, overflow:bool)
    _Date.weekday()는 월=0~일=6 이므로 일요일 열 = (weekday+1)%7 로 변환."""
    import calendar as _c
    first      = _Date(year, month, 1)
    first_col  = (first.weekday() + 1) % 7          # 0=일 1=월 … 6=토
    days_in    = _c.monthrange(year, month)[1]

    pm = (year - 1, 12) if month == 1  else (year, month - 1)
    nm = (year + 1,  1) if month == 12 else (year, month + 1)
    prev_days  = _c.monthrange(*pm)[1]

    grid, cur, nxt = [], 1, 1
    for r in range(6):
        week = []
        for c in range(7):
            idx = r * 7 + c
            if idx < first_col:
                week.append((prev_days - first_col + 1 + idx, *pm, True))
            elif cur <= days_in:
                week.append((cur, year, month, False)); cur += 1
            else:
                week.append((nxt, *nm, True));          nxt += 1
        grid.append(week)
    if all(ov for *_, ov in grid[5]):   # 6번째 줄 전체 다음달이면 제거
        grid = grid[:5]
    return grid
import customtkinter as ctk
from datetime import date as _Date
from tkinter import messagebox
from datetime import timedelta as _Timedelta
from models import TodoItem, HabitManager
import styles
from holidays_kr import HOLIDAYS_KR


# ── 상세보기 팝업 ─────────────────────────────────────────

class ItemDetailDialog(ctk.CTkToplevel):
    """할 일 상세 정보를 보여주는 읽기 전용 팝업."""

    _Q_LABELS = {
        (True,  True):  ("#FFB800", "Q1 · 긴급하고 중요함"),
        (False, True):  ("#C47888", "Q2 · 중요하지만 긴급하지 않음"),
        (True,  False): ("#6A9AB0", "Q3 · 긴급하지만 중요하지 않음"),
        (False, False): ("#9080B8", "Q4 · 긴급하지도 중요하지도 않음"),
    }

    def __init__(self, parent, item: TodoItem, on_edit, on_delete):
        super().__init__(parent)
        self.title("할 일 상세")
        self.geometry("360x360")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus_force()

        self._item = item
        self._on_edit   = on_edit
        self._on_delete = on_delete

        self._build(item)

    def _build(self, item: TodoItem):
        pad = {"padx": 20, "pady": 4}

        # 사분면 색 배지
        color, qlabel = self._Q_LABELS[(item.urgent, item.important)]
        ctk.CTkLabel(
            self, text=f"  {qlabel}  ",
            fg_color=color, text_color="white",
            corner_radius=8,
            font=("Malgun Gothic", 11, "bold"),
            height=30,
        ).pack(fill="x", padx=20, pady=(16, 4))

        # 제목
        ctk.CTkLabel(
            self, text=item.title,
            font=styles.FONT_TITLE,
            anchor="w", wraplength=300,
            justify="left",
        ).pack(fill="x", **pad)

        # 구분선
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray40")).pack(
            fill="x", padx=20, pady=6)

        # 카테고리 / 마감일
        info_rows = []
        if item.category:
            info_rows.append(("카테고리", item.category))
        if item.due_date:
            info_rows.append(("마감일", f"📅 {item.due_date}"))
        if item.tags:
            info_rows.append(("태그", "  ".join(f"#{t}" for t in item.tags)))
        status = "✅ 완료" if item.completed else "⬜ 미완료"
        info_rows.append(("상태", status))
        if getattr(item, "repeat", False):
            info_rows.append(("반복", "🔁 반복 할 일"))

        for label, value in info_rows:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=1)
            ctk.CTkLabel(row, text=f"{label}:", font=styles.FONT_SMALL,
                         text_color="gray50", width=56, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, font=styles.FONT_SMALL,
                         anchor="w").pack(side="left")

        # 메모 (있을 때만)
        if item.note:
            ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray40")).pack(
                fill="x", padx=20, pady=6)
            ctk.CTkLabel(self, text="메모", font=styles.FONT_SMALL,
                         text_color="gray50", anchor="w").pack(fill="x", padx=20)
            note_box = ctk.CTkTextbox(
                self, height=72,
                font=styles.FONT_BODY,
                fg_color=("gray95", "gray18"),
                border_width=0,
                wrap="word",
            )
            note_box.pack(fill="x", padx=20, pady=(2, 4))
            note_box.insert("1.0", item.note)
            note_box.configure(state="disabled")

        # 버튼 행
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(8, 12))
        ctk.CTkButton(
            btn_row, text="수정", width=120, height=34,
            font=styles.FONT_BODY,
            command=self._edit,
        ).pack(side="left", expand=True, padx=(0, 4))
        ctk.CTkButton(
            btn_row, text="삭제", width=120, height=34,
            font=styles.FONT_BODY,
            fg_color=("#CC4444", "#992222"),
            hover_color=("#AA2222", "#771111"),
            command=self._delete,
        ).pack(side="left", expand=True, padx=(4, 0))

    def _edit(self):
        self.destroy()
        self._on_edit(self._item.id)

    def _delete(self):
        self.destroy()
        self._on_delete(self._item.id)


# ── 매트릭스 카드 (사분면 내부 항목) ─────────────────────

class MatrixCard(ctk.CTkFrame):
    def __init__(self, parent, item: TodoItem, on_toggle, on_edit, on_delete,
                 on_drag_end=None):
        super().__init__(parent, fg_color="transparent", corner_radius=6)
        self.configure(height=46)
        self.pack_propagate(False)

        item_id    = item.id
        self._item      = item
        self._item_id    = item_id
        self._item_title = item.title
        self._on_edit    = on_edit
        self._on_delete  = on_delete
        self._on_drag_end = on_drag_end
        self._drag_x   = 0
        self._drag_y   = 0
        self._dragging = False
        self._ghost: _tk.Toplevel | None = None

        # ── 오른쪽 버튼부터 pack ──────────────────────────
        ctk.CTkButton(
            self, text="✕", width=22, height=22,
            fg_color="transparent",
            hover_color=("gray70", "gray40"),
            text_color="gray20",
            font=styles.FONT_SMALL,
            command=lambda: on_delete(item_id),
        ).pack(side="right", padx=(0, 4))

        ctk.CTkButton(
            self, text="✎", width=22, height=22,
            fg_color="transparent",
            hover_color=("gray70", "gray40"),
            text_color="gray20",
            font=styles.FONT_SMALL,
            command=lambda: on_edit(item_id),
        ).pack(side="right", padx=2)

        if getattr(item, "repeat", False):
            ctk.CTkLabel(
                self, text="🔁",
                font=styles.FONT_SMALL,
                text_color="gray20",
            ).pack(side="right", padx=2)

        # ── 클릭/더블클릭 전파 차단 ──────────────────────
        self.bind("<Button-1>",        lambda e: "break")
        self.bind("<Double-Button-1>", lambda e: "break")

        # ── 드래그 핸들 (⠿ 아이콘) ───────────────────────
        handle = ctk.CTkLabel(
            self, text="⠿", width=18,
            font=("Malgun Gothic", 15),
            text_color="gray55",
            cursor="fleur",
        )
        handle.pack(side="left", padx=(4, 0))
        handle.bind("<ButtonPress-1>",   self._drag_press)
        handle.bind("<B1-Motion>",       self._drag_motion)
        handle.bind("<ButtonRelease-1>", self._drag_release)

        # ── 왼쪽: 완료 버튼 + 제목 ───────────────────────
        check_text = "☑" if item.completed else "☐"
        ctk.CTkButton(
            self, text=check_text, width=28, height=28,
            font=("Malgun Gothic", 16),
            fg_color="transparent",
            hover_color=("gray75", "gray35"),
            text_color="gray30",
            command=lambda: on_toggle(item_id),
        ).pack(side="left", padx=(2, 0))

        title_color = "gray50" if item.completed else "gray10"
        title_lbl = ctk.CTkLabel(
            self, text=item.title,
            font=styles.FONT_BODY,
            text_color=title_color,
            anchor="w",
            cursor="hand2",
        )
        title_lbl.pack(side="left", fill="x", expand=True, padx=6)
        title_lbl.bind("<Button-1>", lambda e: self._open_detail())

    # ── 상세보기 ──────────────────────────────────────────

    def _open_detail(self):
        ItemDetailDialog(
            self, self._item,
            on_edit=self._on_edit,
            on_delete=self._on_delete,
        )

    # ── 드래그 구현 ───────────────────────────────────────

    def _drag_press(self, event):
        self._drag_x   = event.x_root
        self._drag_y   = event.y_root
        self._dragging = False
        self._ghost    = None

    def _drag_motion(self, event):
        dx = abs(event.x_root - self._drag_x)
        dy = abs(event.y_root - self._drag_y)
        if not self._dragging and (dx > 6 or dy > 6):
            self._dragging = True
            self._create_ghost(event.x_root, event.y_root)
        if self._ghost:
            self._ghost.geometry(f"+{event.x_root + 14}+{event.y_root + 10}")

    def _create_ghost(self, x: int, y: int):
        self._ghost = _tk.Toplevel(self)
        self._ghost.overrideredirect(True)
        self._ghost.attributes("-alpha", 0.78)
        self._ghost.attributes("-topmost", True)
        short = self._item_title[:22] + ("…" if len(self._item_title) > 22 else "")
        _tk.Label(
            self._ghost, text=f"  {short}  ",
            bg="#444444", fg="white",
            font=("Malgun Gothic", 11),
            relief="flat", pady=5, padx=6,
        ).pack()
        self._ghost.geometry(f"+{x + 14}+{y + 10}")

    def _drag_release(self, event):
        if self._ghost:
            self._ghost.destroy()
            self._ghost = None
        if self._dragging and self._on_drag_end:
            self._on_drag_end(self._item_id, event.x_root, event.y_root)
        self._dragging = False


# ── 사분면 프레임 ─────────────────────────────────────────

class QuadrantFrame(ctk.CTkFrame):
    def __init__(self, parent, urgent: bool, important: bool, color: str,
                 on_toggle, on_edit, on_delete, on_add_quadrant, on_move=None):
        super().__init__(parent, fg_color=color, corner_radius=14)
        self._urgent = urgent
        self._important = important
        self._on_toggle = on_toggle
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._on_add_quadrant = on_add_quadrant
        self._on_move = on_move

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=color,
            scrollbar_button_hover_color=color,
        )
        self._scroll.pack(fill="both", expand=True, padx=6, pady=6)

        # 사분면 배경 더블클릭 → 새 항목 추가
        self.bind("<Double-Button-1>", self._on_bg_click)
        self._scroll.bind("<Double-Button-1>", self._on_bg_click)
        self.after(200, self._bind_canvas)

    def _bind_canvas(self):
        try:
            self._scroll._parent_canvas.bind("<Double-Button-1>", self._on_bg_click)
        except Exception:
            pass

    def _on_bg_click(self, event):
        self._on_add_quadrant(self._urgent, self._important)

    def _handle_drag_end(self, item_id: str, x_root: int, y_root: int):
        if self._on_move:
            self._on_move(item_id, x_root, y_root)

    def update_items(self, items: list):
        for w in list(self._scroll.winfo_children()):
            w.destroy()

        if not items:
            ctk.CTkLabel(
                self._scroll, text="더블클릭하여 추가",
                font=styles.FONT_SMALL,
                text_color="gray30",
            ).pack(pady=20)
            return

        for item in items:
            MatrixCard(
                self._scroll, item,
                on_toggle=self._on_toggle,
                on_edit=self._on_edit,
                on_delete=self._on_delete,
                on_drag_end=self._handle_drag_end if self._on_move else None,
            ).pack(fill="x", pady=1)


# ── 추가/수정 다이얼로그 ──────────────────────────────────

class AddEditDialog(ctk.CTkToplevel):
    def __init__(self, parent, categories: list[str],
                 item: TodoItem | None = None, on_save=None,
                 default_urgent: bool = False, default_important: bool = True,
                 default_due_date: str = "", default_repeat: bool = False):
        super().__init__(parent)
        self._item = item
        self._on_save = on_save
        self._default_repeat = default_repeat
        self._categories = categories if categories else ["개인"]
        self._default_urgent = default_urgent
        self._default_important = default_important
        self._default_due_date = default_due_date

        self.title("할 일 수정" if item else "새 할 일 추가")
        self.geometry("420x440")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus_force()

        self._build()
        if item:
            self._populate(item)

    def _build(self):
        pad = {"padx": 16, "pady": 4}

        # ── 저장 버튼을 먼저 bottom에 고정 ───────────────────
        btn_bar = ctk.CTkFrame(self, fg_color="transparent", height=60)
        btn_bar.pack(side="bottom", fill="x")
        btn_bar.pack_propagate(False)
        ctk.CTkButton(
            btn_bar, text="저장", height=40,
            font=styles.FONT_TITLE,
            command=self._save,
        ).pack(fill="x", padx=16, pady=10)

        # ── 나머지 폼은 스크롤 가능 영역에 ──────────────────
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(scroll, text="제목 *", font=styles.FONT_BODY, anchor="w").pack(fill="x", **pad)
        self._title_entry = ctk.CTkEntry(scroll, placeholder_text="할 일을 입력하세요", height=34)
        self._title_entry.pack(fill="x", **pad)

        ctk.CTkLabel(scroll, text="분류", font=styles.FONT_BODY, anchor="w").pack(fill="x", **pad)
        clf = ctk.CTkFrame(scroll, fg_color="transparent")
        clf.pack(fill="x", padx=16, pady=(4, 2))

        self._urgent_var = ctk.BooleanVar(value=self._default_urgent)
        self._important_var = ctk.BooleanVar(value=self._default_important)
        ctk.CTkCheckBox(clf, text="긴급함", variable=self._urgent_var,
                        font=styles.FONT_BODY,
                        command=self._update_quadrant_preview).pack(side="left")
        ctk.CTkCheckBox(clf, text="중요함", variable=self._important_var,
                        font=styles.FONT_BODY,
                        command=self._update_quadrant_preview).pack(side="left", padx=20)

        # 사분면 미리보기
        self._preview = ctk.CTkLabel(
            scroll, text="", height=36, corner_radius=8,
            font=("Malgun Gothic", 11, "bold"),
        )
        self._preview.pack(fill="x", padx=16, pady=(2, 6))
        self._update_quadrant_preview()

        ctk.CTkLabel(scroll, text="카테고리", font=styles.FONT_BODY, anchor="w").pack(fill="x", **pad)
        self._cat_var = ctk.StringVar(value=self._categories[0])
        ctk.CTkOptionMenu(scroll, variable=self._cat_var, values=self._categories).pack(fill="x", **pad)

        ctk.CTkLabel(scroll, text="메모", font=styles.FONT_BODY, anchor="w").pack(fill="x", **pad)
        self._note_entry = ctk.CTkEntry(scroll, placeholder_text="추가 메모")
        self._note_entry.pack(fill="x", **pad)

        # ── 반복 할 일 ────────────────────────────────────────
        ctk.CTkFrame(scroll, height=1, fg_color=("gray80", "gray40")).pack(
            fill="x", padx=16, pady=(8, 4))

        repeat_row = ctk.CTkFrame(scroll, fg_color="transparent")
        repeat_row.pack(fill="x", padx=16, pady=(0, 4))

        ctk.CTkLabel(repeat_row, text="반복 할 일",
                     font=styles.FONT_BODY, anchor="w").pack(side="left")

        self._repeat_var = ctk.BooleanVar(value=self._default_repeat)
        self._repeat_switch = ctk.CTkSwitch(
            repeat_row, text="",
            variable=self._repeat_var,
            width=46, height=24,
            command=self._update_repeat_label,
        )
        self._repeat_switch.pack(side="right")

        self._repeat_lbl = ctk.CTkLabel(
            scroll, text="",
            font=styles.FONT_SMALL, text_color="gray50", anchor="w",
        )
        self._repeat_lbl.pack(fill="x", padx=16, pady=(0, 4))
        self._update_repeat_label()

    def _update_repeat_label(self):
        if self._repeat_var.get():
            self._repeat_lbl.configure(
                text="✔ 매일 모든 날짜에 반복 표시됩니다",
                text_color="#1A73E8")
        else:
            self._repeat_lbl.configure(text="", text_color="gray50")

    def _update_quadrant_preview(self):
        urgent = self._urgent_var.get()
        important = self._important_var.get()
        info = {
            (True,  True):  ("#FFB800", "⬛ Q1 · 긴급하고 중요함 → 즉시 처리"),
            (False, True):  ("#C47888", "⬛ Q2 · 중요하지만 긴급하지 않음 → 일정 수립"),
            (True,  False): ("#6A9AB0", "⬛ Q3 · 긴급하지만 중요하지 않음 → 위임"),
            (False, False): ("#9080B8", "⬛ Q4 · 긴급하지도 중요하지도 않음 → 제거"),
        }
        color, label = info[(urgent, important)]
        self._preview.configure(fg_color=color, text=label, text_color="white")

    def _populate(self, item: TodoItem):
        self._title_entry.insert(0, item.title)
        if item.category in self._categories:
            self._cat_var.set(item.category)
        self._urgent_var.set(item.urgent)
        self._important_var.set(item.important)
        self._note_entry.insert(0, item.note)
        self._repeat_var.set(getattr(item, "repeat", False))
        self._update_repeat_label()

    def _save(self):
        title = self._title_entry.get().strip()
        if not title:
            messagebox.showwarning("입력 오류", "제목을 입력해주세요.", parent=self)
            return

        result = {
            "title": title,
            "category": self._cat_var.get(),
            "urgent": self._urgent_var.get(),
            "important": self._important_var.get(),
            "note": self._note_entry.get().strip(),
            "repeat": self._repeat_var.get(),
            "due_date": self._default_due_date,
        }

        if self._on_save:
            self._on_save(result)
        self.destroy()


# ── 전체 보기 (독립 매트릭스) ────────────────────────────

class FreeMatrixView(ctk.CTkFrame):
    """캘린더·매트릭스와 완전히 독립된 아이젠하워 매트릭스.
    별도 파일(todos_free.json)에 저장되어 연동되지 않는다."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent", corner_radius=0)

        # 독립 컨트롤러 (별도 JSON)
        from models import StorageManager
        from app_controller import TodoController
        from pathlib import Path
        _storage = StorageManager(Path(__file__).parent / "todos_free.json")
        self._ctrl = TodoController(_storage)

        self._show_completed = ctk.BooleanVar(value=False)
        self._build()

    def _build(self):
        # ── 서브 헤더 (전체 보기 레이블 + 버튼) ──────────────
        sub = ctk.CTkFrame(self, fg_color=("gray92", "gray15"),
                           height=40, corner_radius=0)
        sub.pack(fill="x")
        sub.pack_propagate(False)

        ctk.CTkLabel(sub, text="전체 보기",
                     font=("Malgun Gothic", 13, "bold"),
                     text_color="gray45").pack(side="left", padx=12)

        ctk.CTkButton(
            sub, text="+ 새 할 일", width=110, height=30,
            font=styles.FONT_BODY,
            command=lambda: self._on_add_quadrant(False, True),
        ).pack(side="right", padx=(4, 12))

        ctk.CTkCheckBox(
            sub, text="완료된 항목 보기",
            variable=self._show_completed,
            font=styles.FONT_BODY,
            command=self._refresh,
        ).pack(side="right", padx=12)

        # ── 열 헤더 ───────────────────────────────────────────
        col_hdr = ctk.CTkFrame(self, fg_color="transparent", height=32)
        col_hdr.pack(fill="x", padx=8)
        col_hdr.pack_propagate(False)
        ctk.CTkFrame(col_hdr, width=64, fg_color="transparent").pack(side="left")
        for text in ["긴급함", "긴급하지 않음"]:
            ctk.CTkLabel(col_hdr, text=text,
                         font=("Malgun Gothic", 12, "bold"),
                         text_color="gray40").pack(side="left", expand=True, fill="x")

        # ── 사분면 그리드 ─────────────────────────────────────
        matrix = ctk.CTkFrame(self, fg_color="transparent")
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
            (0, 1, True,  True,  "#A8D8A8"),   # 파스텔 민트그린
            (0, 2, False, True,  "#A8C8E8"),   # 파스텔 스카이블루
            (1, 1, True,  False, "#F4C2A1"),   # 파스텔 피치
            (1, 2, False, False, "#D4A8D8"),   # 파스텔 라벤더
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

        self.after(50, self._refresh)

    # ── 갱신 ─────────────────────────────────────────────

    def _refresh(self):
        show = self._show_completed.get()
        for (urgent, important), q_frame in self._quadrants.items():
            items = self._ctrl.filter_by_quadrant(urgent, important, show_completed=show)
            q_frame.update_items(items)

    # ── 이벤트 핸들러 ─────────────────────────────────────

    def _on_add_quadrant(self, urgent: bool, important: bool):
        categories = self._ctrl.get_categories(styles.DEFAULT_CATEGORIES)
        def _save(data):
            self._ctrl.add_item(**data)
            self.after(20, self._refresh)
        AddEditDialog(self, categories=categories, item=None, on_save=_save,
                      default_urgent=urgent, default_important=important)

    def _on_toggle(self, item_id: str):
        self._ctrl.toggle_complete(item_id)
        self.after(20, self._refresh)

    def _on_edit(self, item_id: str):
        item = next((i for i in self._ctrl.get_all() if i.id == item_id), None)
        if item is None:
            return
        categories = self._ctrl.get_categories(styles.DEFAULT_CATEGORIES)
        def _save(data):
            self._ctrl.update_item(item_id, **data)
            self.after(20, self._refresh)
        AddEditDialog(self, categories=categories, item=item, on_save=_save)

    def _on_delete(self, item_id: str):
        from tkinter import messagebox
        item = next((i for i in self._ctrl.get_all() if i.id == item_id), None)
        if item and messagebox.askyesno("삭제 확인", f"'{item.title}'을(를) 삭제할까요?"):
            self._ctrl.delete_item(item_id)
            self.after(20, self._refresh)

    def _on_move(self, item_id: str, x_root: int, y_root: int):
        for (urgent, important), qframe in self._quadrants.items():
            qx = qframe.winfo_rootx()
            qy = qframe.winfo_rooty()
            if qx <= x_root <= qx + qframe.winfo_width() and \
               qy <= y_root <= qy + qframe.winfo_height():
                self._ctrl.update_item(item_id, urgent=urgent, important=important)
                self.after(20, self._refresh)
                return


# ── 날짜 상세 팝업 (캘린더 날짜 클릭) ────────────────────

class DayDetailDialog(ctk.CTkToplevel):
    """특정 날짜의 할일 목록을 보여주는 팝업."""

    _Q_COLORS = {
        (True,  True):  "#FFB800",
        (False, True):  "#C47888",
        (True,  False): "#6A9AB0",
        (False, False): "#9080B8",
    }
    _Q_LABELS = {
        (True,  True):  "Q1",
        (False, True):  "Q2",
        (True,  False): "Q3",
        (False, False): "Q4",
    }

    def __init__(self, parent, date_str: str, items: list,
                 on_add, on_edit, on_delete, on_view_matrix=None):
        super().__init__(parent)
        self._on_add         = on_add
        self._on_edit        = on_edit
        self._on_delete      = on_delete
        self._on_view_matrix = on_view_matrix
        self._items          = items
        self._date_str       = date_str

        # 날짜 표시 변환 (YYYY-MM-DD → YYYY년 M월 D일)
        try:
            from datetime import datetime as _dt
            d = _dt.strptime(date_str, "%Y-%m-%d")
            display = f"{d.year}년 {d.month}월 {d.day}일"
        except Exception:
            display = date_str

        self.title(f"📅 {display}")
        self.geometry("400x460")
        self.resizable(False, True)
        self.grab_set()
        self.lift()
        self.focus_force()

        self._build(display)

    def _build(self, display: str):
        # 헤더
        hdr = ctk.CTkFrame(self, fg_color=("gray92", "gray18"), height=52,
                           corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text=display,
                     font=styles.FONT_TITLE).pack(side="left", padx=16)
        ctk.CTkButton(
            hdr, text="+ 추가", width=76, height=34,
            font=styles.FONT_BODY,
            command=self._add_new,
        ).pack(side="right", padx=4)
        if self._on_view_matrix:
            ctk.CTkButton(
                hdr, text="📋 매트릭스", width=96, height=34,
                font=styles.FONT_SMALL,
                fg_color=("gray75", "gray35"),
                text_color=("gray10", "gray90"),
                hover_color=("gray60", "gray45"),
                command=self._view_matrix,
            ).pack(side="right", padx=4)

        # 아이템 목록
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=8, pady=8)

        for item in self._items:
            self._make_row(scroll, item)

    def _make_row(self, parent, item):
        color = self._Q_COLORS[(item.urgent, item.important)]
        qlabel = self._Q_LABELS[(item.urgent, item.important)]

        row = ctk.CTkFrame(parent, fg_color=("white", "gray22"),
                           corner_radius=8, border_width=1,
                           border_color=("gray85", "gray35"))
        row.pack(fill="x", pady=3)

        # 왼쪽 색 바
        ctk.CTkFrame(row, width=6, fg_color=color,
                     corner_radius=4).pack(side="left", fill="y", padx=(4, 0), pady=4)

        # 본문
        body = ctk.CTkFrame(row, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=8, pady=6)

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=f"[{qlabel}]",
                     font=("Malgun Gothic", 10, "bold"),
                     text_color=color).pack(side="left")
        status = "  ✅" if item.completed else ""
        ctk.CTkLabel(top, text=item.title + status,
                     font=styles.FONT_BODY,
                     text_color="gray50" if item.completed else "gray10",
                     anchor="w").pack(side="left", padx=6, fill="x", expand=True)

        # 메모 미리보기
        if item.note:
            ctk.CTkLabel(body,
                         text=item.note[:60] + ("…" if len(item.note) > 60 else ""),
                         font=styles.FONT_SMALL,
                         text_color="gray55", anchor="w").pack(fill="x")

        # 카테고리 / 태그
        meta_parts = []
        if item.category:
            meta_parts.append(item.category)
        if item.tags:
            meta_parts += [f"#{t}" for t in item.tags]
        if meta_parts:
            ctk.CTkLabel(body, text="  ".join(meta_parts),
                         font=styles.FONT_SMALL,
                         text_color="gray60", anchor="w").pack(fill="x")

        # 수정/삭제 버튼
        btn_row = ctk.CTkFrame(row, fg_color="transparent")
        btn_row.pack(side="right", padx=6)
        ctk.CTkButton(
            btn_row, text="✎", width=26, height=26,
            fg_color="transparent",
            hover_color=("gray80", "gray35"),
            text_color="gray30",
            font=styles.FONT_SMALL,
            command=lambda i=item: self._edit(i.id),
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            btn_row, text="✕", width=26, height=26,
            fg_color="transparent",
            hover_color=("gray80", "gray35"),
            text_color="gray30",
            font=styles.FONT_SMALL,
            command=lambda i=item: self._delete(i.id),
        ).pack(side="left")

    def _add_new(self):
        self.destroy()
        self._on_add()

    def _view_matrix(self):
        self.destroy()
        if self._on_view_matrix:
            self._on_view_matrix(self._date_str)

    def _edit(self, item_id: str):
        self.destroy()
        self._on_edit(item_id)

    def _delete(self, item_id: str):
        self.destroy()
        self._on_delete(item_id)


# ── 캘린더 뷰 (인페이지 임베드) ───────────────────────────

class CalendarView(ctk.CTkFrame):
    """Google Calendar 스타일의 월별 뷰 — 메인 창 안에 pack/pack_forget으로 삽입."""

    _WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"]
    _MONTHS   = ["1월","2월","3월","4월","5월","6월",
                 "7월","8월","9월","10월","11월","12월"]

    def __init__(self, parent, controller, on_item_saved, categories,
                 on_back=None, on_date_select=None):
        super().__init__(parent, fg_color=("gray95", "gray12"), corner_radius=0)
        self._ctrl            = controller
        self._on_item_saved   = on_item_saved
        self._categories      = categories
        self._on_back         = on_back
        self._on_date_select  = on_date_select  # (date_str) → 매트릭스 필터 연동

        today = _Date.today()
        self._year  = today.year
        self._month = today.month
        self._today = today

        # ── 레이아웃: 사이드바 | 메인 ──────────────────────
        self._sidebar = ctk.CTkFrame(self, width=220,
                                     fg_color=("gray90", "gray15"),
                                     corner_radius=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        self._main = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self._main.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._build_main_nav()
        self._build_weekday_row()

        self._grid = ctk.CTkFrame(self._main, fg_color="transparent")
        self._grid.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._refresh()

    # ── 사이드바 ─────────────────────────────────────────

    def _build_sidebar(self):
        sb = self._sidebar

        # 뒤로가기 버튼 (매트릭스로)
        if self._on_back:
            ctk.CTkButton(
                sb, text="← 매트릭스",
                height=36, font=("Malgun Gothic", 12),
                fg_color="transparent",
                text_color=("gray20", "gray80"),
                hover_color=("gray80", "gray25"),
                anchor="w",
                command=self._on_back,
            ).pack(fill="x", padx=8, pady=(10, 2))

        # 만들기 버튼
        ctk.CTkButton(
            sb, text="+ 만들기",
            height=40, font=("Malgun Gothic", 13, "bold"),
            corner_radius=20,
            command=lambda: self._on_day_click(
                _Date.today().strftime("%Y-%m-%d")),
        ).pack(fill="x", padx=12, pady=(8, 12))

        # 미니 캘린더 레이블
        self._mini_lbl = ctk.CTkLabel(
            sb, text="",
            font=("Malgun Gothic", 12, "bold"),
        )
        self._mini_lbl.pack(pady=(4, 2))

        mini_nav = ctk.CTkFrame(sb, fg_color="transparent", height=28)
        mini_nav.pack(fill="x", padx=8)
        mini_nav.pack_propagate(False)
        ctk.CTkButton(mini_nav, text="‹", width=26, height=26,
                      fg_color="transparent",
                      text_color=("gray20", "gray80"),
                      hover_color=("gray80", "gray25"),
                      command=lambda: self._mini_navigate(-1)).pack(side="left")
        ctk.CTkButton(mini_nav, text="›", width=26, height=26,
                      fg_color="transparent",
                      text_color=("gray20", "gray80"),
                      hover_color=("gray80", "gray25"),
                      command=lambda: self._mini_navigate(1)).pack(side="right")

        # 미니 캘린더 요일 헤더
        wd_row = ctk.CTkFrame(sb, fg_color="transparent", height=22)
        wd_row.pack(fill="x", padx=6, pady=(2, 0))
        wd_row.pack_propagate(False)
        for i, d in enumerate(["일","월","화","수","목","금","토"]):
            col = "#CC4444" if i == 0 else ("#2277CC" if i == 6 else "gray50")
            ctk.CTkLabel(wd_row, text=d,
                         font=("Malgun Gothic", 10, "bold"),
                         text_color=col).pack(side="left", expand=True)

        self._mini_grid = ctk.CTkFrame(sb, fg_color="transparent")
        self._mini_grid.pack(fill="x", padx=6, pady=(0, 8))

        # 구분선
        ctk.CTkFrame(sb, height=1, fg_color="gray70").pack(
            fill="x", padx=8, pady=(0, 2))

        # 습관 트래커
        self._habit_tracker = HabitTracker(sb, self._year, self._month)
        self._habit_tracker.pack(fill="both", expand=True, padx=2, pady=(0, 4))

    def _mini_navigate(self, delta: int):
        self._month += delta
        if self._month > 12:
            self._month, self._year = 1, self._year + 1
        elif self._month < 1:
            self._month, self._year = 12, self._year - 1
        self._refresh()

    def _build_mini_cal(self):
        self._mini_lbl.configure(
            text=f"{self._year}년 {self._MONTHS[self._month - 1]}")

        for w in self._mini_grid.winfo_children():
            w.destroy()

        # 7열 균등 배분
        for c in range(7):
            self._mini_grid.grid_columnconfigure(c, weight=1)

        grid = _month_grid(self._year, self._month)
        for r in range(len(grid)):
            self._mini_grid.grid_rowconfigure(r, weight=1)

        for r, week in enumerate(grid):
            for c, (day, yr, mo, overflow) in enumerate(week):
                is_today = (not overflow
                            and day == self._today.day
                            and mo  == self._today.month
                            and yr  == self._today.year)
                ds = f"{yr:04d}-{mo:02d}-{day:02d}"
                is_holiday = not overflow and ds in HOLIDAYS_KR
                fg = "#1A73E8" if is_today else "transparent"
                if is_today:
                    tc = "white"
                elif overflow:
                    tc = "gray70"
                elif c == 0 or is_holiday:
                    tc = "#CC4444"
                elif c == 6:
                    tc = "#2277CC"
                else:
                    tc = ("gray10", "gray90")
                btn = ctk.CTkButton(
                    self._mini_grid, text=str(day),
                    width=22, height=22,
                    font=("Malgun Gothic", 9),
                    fg_color=fg, text_color=tc,
                    hover_color=("gray80", "gray30"),
                    corner_radius=11,
                    command=lambda d=ds: self._on_day_click(d),
                )
                btn.grid(row=r, column=c, padx=0, pady=1, sticky="nsew")

    # ── 메인 영역 네비게이션 ──────────────────────────────

    def _build_main_nav(self):
        nav = ctk.CTkFrame(self._main, fg_color="transparent", height=56)
        nav.pack(fill="x", padx=12, pady=(10, 2))
        nav.pack_propagate(False)

        ctk.CTkButton(nav, text="오늘", width=64, height=36,
                      font=("Malgun Gothic", 12),
                      command=self._go_today).pack(side="left", padx=(0, 8))

        ctk.CTkButton(nav, text="◀", width=34, height=36,
                      command=lambda: self._navigate(-1)).pack(side="left")

        ctk.CTkButton(nav, text="▶", width=34, height=36,
                      command=lambda: self._navigate(1)).pack(side="left", padx=(2, 0))

        self._main_lbl = ctk.CTkLabel(nav, text="",
                                       font=("Malgun Gothic", 20, "bold"))
        self._main_lbl.pack(side="left", padx=16)

    def _build_weekday_row(self):
        row = ctk.CTkFrame(self._main, fg_color="transparent", height=28)
        row.pack(fill="x", padx=8)
        row.pack_propagate(False)
        for i, d in enumerate(self._WEEKDAYS):
            color = "#CC4444" if i == 0 else ("#2277CC" if i == 6 else "gray40")
            ctk.CTkLabel(row, text=d,
                         font=("Malgun Gothic", 12, "bold"),
                         text_color=color).pack(side="left", expand=True, fill="x")

    # ── 월 이동 ───────────────────────────────────────────

    def _navigate(self, delta: int):
        self._month += delta
        if self._month > 12:
            self._month, self._year = 1, self._year + 1
        elif self._month < 1:
            self._month, self._year = 12, self._year - 1
        self._refresh()

    def _go_today(self):
        t = _Date.today()
        self._year, self._month = t.year, t.month
        self._refresh()

    # ── 캘린더 그리드 ─────────────────────────────────────

    def _refresh(self):
        self._main_lbl.configure(
            text=f"{self._year}년 {self._MONTHS[self._month - 1]}")
        self._build_mini_cal()
        # 습관 트래커 월 동기화
        if hasattr(self, "_habit_tracker"):
            self._habit_tracker.set_month(self._year, self._month)

        for w in self._grid.winfo_children():
            w.destroy()

        all_items = self._ctrl.get_all()
        by_date: dict[str, list] = {}
        for item in all_items:
            if item.due_date and not item.repeat:
                by_date.setdefault(item.due_date, []).append(item)


        full_weeks = _month_grid(self._year, self._month)
        for r in range(len(full_weeks)):
            self._grid.grid_rowconfigure(r, weight=1)
        for c in range(7):
            self._grid.grid_columnconfigure(c, weight=1)

        for r, week in enumerate(full_weeks):
            for c, cell_data in enumerate(week):
                cell = self._make_cell(cell_data, c, by_date)
                cell.grid(row=r, column=c, sticky="nsew", padx=2, pady=2)

    def _make_cell(self, cell_data: tuple, col: int, by_date: dict):
        day, yr, mo, overflow = cell_data
        is_today = (not overflow
                    and day == self._today.day
                    and mo == self._today.month
                    and yr == self._today.year)

        cell = ctk.CTkFrame(
            self._grid, corner_radius=8,
            fg_color=("gray94", "gray17") if overflow else ("white", "gray20"),
            border_width=1,
            border_color=("gray85", "gray30"),
        )

        date_str = f"{yr:04d}-{mo:02d}-{day:02d}"
        holiday_name = HOLIDAYS_KR.get(date_str) if not overflow else None

        # 날짜 숫자 색상 (overflow면 더 연하게)
        if overflow:
            num_color = "#E08888" if col == 0 else ("#88AADD" if col == 6 else "gray65")
        else:
            num_color = "#CC4444" if (col == 0 or holiday_name) else ("#2277CC" if col == 6 else ("gray10", "gray90"))

        num_frame = ctk.CTkFrame(cell, fg_color="transparent", height=28)
        num_frame.pack(fill="x", padx=4, pady=(4, 1))
        num_frame.pack_propagate(False)

        if is_today:
            num_btn = ctk.CTkButton(
                num_frame, text=str(day),
                width=26, height=26,
                font=("Malgun Gothic", 13, "bold"),
                fg_color="#1A73E8", text_color="white",
                hover_color="#1557b0", corner_radius=13,
                command=lambda d=date_str: self._on_day_click(d),
            )
            num_btn.pack(side="left", padx=2)
        else:
            num_lbl = ctk.CTkLabel(num_frame, text=str(day),
                                   font=("Malgun Gothic", 13, "bold"),
                                   text_color=num_color, anchor="w")
            num_lbl.pack(side="left", padx=6)
            num_lbl.bind("<Button-1>", lambda e, d=date_str: self._on_day_click(d))

        # 공휴일 이름 표시
        if holiday_name:
            h_lbl = ctk.CTkLabel(cell, text=holiday_name,
                                 font=("Malgun Gothic", 9),
                                 text_color="#CC4444", anchor="w")
            h_lbl.pack(fill="x", padx=5, pady=0)
            h_lbl.bind("<Button-1>", lambda e, d=date_str: self._on_day_click(d))

        cell.bind("<Button-1>", lambda e, d=date_str: self._on_day_click(d))

        # 해당 날짜 항목 표시 (반복 할일 제외)
        items = by_date.get(date_str, [])
        for item in items[:3]:
            color = styles.Q_COLORS.get((item.urgent, item.important), "#888888")
            short = item.title[:11] + ("…" if len(item.title) > 11 else "")
            chip = ctk.CTkLabel(cell, text=f" {short} ",
                                fg_color=color, corner_radius=4,
                                font=("Malgun Gothic", 10),
                                text_color="white", anchor="w")
            chip.pack(fill="x", padx=4, pady=1)
            chip.bind("<Button-1>", lambda e, d=date_str: self._on_day_click(d))

        if len(items) > 3:
            extra = items[3:]
            extra_chips = []
            for item in extra:
                color = styles.Q_COLORS.get((item.urgent, item.important), "#888888")
                short = item.title[:11] + ("…" if len(item.title) > 11 else "")
                chip = ctk.CTkLabel(cell, text=f" {short} ",
                                    fg_color=color, corner_radius=4,
                                    font=("Malgun Gothic", 10),
                                    text_color="white", anchor="w")
                chip.bind("<Button-1>", lambda e, d=date_str: self._on_day_click(d))
                extra_chips.append(chip)

            more_lbl = ctk.CTkLabel(cell, text=f"+{len(extra)}개 더",
                                     font=("Malgun Gothic", 10),
                                     text_color="#1A73E8", cursor="hand2")
            more_lbl.pack(anchor="w", padx=6)

            def toggle_extra(event=None, chips=extra_chips, lbl=more_lbl):
                if chips[0].winfo_manager():
                    for c in chips:
                        c.pack_forget()
                    lbl.configure(text=f"+{len(chips)}개 더")
                else:
                    for c in chips:
                        c.pack(fill="x", padx=4, pady=1)
                    lbl.configure(text="접기")

            more_lbl.bind("<Button-1>", toggle_extra)
        return cell

    def _on_day_click(self, date_str: str):
        items_on_date = [i for i in self._ctrl.get_all()
                         if i.due_date == date_str and not i.repeat]

        def save_and_refresh(data):
            self._on_item_saved(data)
            self.after(80, self._refresh)

        def edit_item(item_id):
            item = next((i for i in self._ctrl.get_all() if i.id == item_id), None)
            if item is None:
                return
            def on_edit_save(data):
                self._ctrl.update_item(item_id, **data)
                self.after(80, self._refresh)
            AddEditDialog(self, categories=self._categories,
                          item=item, on_save=on_edit_save)

        def delete_item(item_id):
            item = next((i for i in self._ctrl.get_all() if i.id == item_id), None)
            if item and messagebox.askyesno("삭제 확인", f"'{item.title}'을(를) 삭제할까요?"):
                self._ctrl.delete_item(item_id)
                self.after(80, self._refresh)

        if items_on_date:
            DayDetailDialog(
                self, date_str=date_str, items=items_on_date,
                on_add=lambda: AddEditDialog(
                    self, categories=self._categories,
                    item=None, on_save=save_and_refresh,
                    default_due_date=date_str,
                ),
                on_edit=edit_item,
                on_delete=delete_item,
                on_view_matrix=self._on_date_select,
            )
        else:
            AddEditDialog(self, categories=self._categories,
                          item=None, on_save=save_and_refresh,
                          default_due_date=date_str)

    def refresh_events(self):
        """외부에서 데이터 갱신 후 호출."""
        self._refresh()


# ── 반복 할 일 전용 다이얼로그 ────────────────────────────

_WEEKDAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]

class RepeatEditDialog(ctk.CTkToplevel):
    """반복 할 일 추가/수정 전용 다이얼로그.
    요일 선택 + 일자 선택 + 사분면 지정."""

    def __init__(self, parent, categories: list[str],
                 item: TodoItem | None = None, on_save=None):
        super().__init__(parent)
        self._item = item
        self._on_save = on_save
        self._categories = categories or ["개인"]

        self.title("반복 할 일 수정" if item else "반복 할 일 추가")
        self.geometry("440x580")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus_force()

        self._build()
        if item:
            self._load_item(item)

    def _build(self):
        # 저장 버튼 (항상 하단 고정)
        ctk.CTkButton(
            self, text="저장", height=44, font=("Malgun Gothic", 15, "bold"),
            command=self._save,
        ).pack(side="bottom", fill="x", padx=16, pady=(8, 12))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        pad = {"padx": 16, "pady": (4, 2)}

        # 제목
        ctk.CTkLabel(scroll, text="제목 *", font=styles.FONT_BODY,
                     anchor="w").pack(fill="x", **pad)
        self._title_entry = ctk.CTkEntry(scroll, height=38,
                                          font=("Malgun Gothic", 14),
                                          placeholder_text="반복 할 일 제목")
        self._title_entry.pack(fill="x", **pad)

        # ── 반복 요일 ──────────────────────────────────────
        ctk.CTkFrame(scroll, height=1, fg_color=("gray80", "gray40")).pack(
            fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(scroll, text="반복 요일", font=("Malgun Gothic", 13, "bold"),
                     anchor="w").pack(fill="x", **pad)
        ctk.CTkLabel(scroll, text="선택한 요일에 매주 반복됩니다",
                     font=("Malgun Gothic", 10), text_color="gray50",
                     anchor="w").pack(fill="x", padx=16, pady=(0, 4))

        wd_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        wd_frame.pack(fill="x", padx=16, pady=(0, 6))
        self._wd_vars: list[ctk.BooleanVar] = []
        for i, name in enumerate(_WEEKDAY_NAMES):
            var = ctk.BooleanVar(value=False)
            self._wd_vars.append(var)
            color = "#CC4444" if i == 6 else ("#2277CC" if i == 5 else ("gray15", "gray90"))
            ctk.CTkCheckBox(
                wd_frame, text=name, variable=var,
                font=("Malgun Gothic", 13, "bold"),
                text_color=color,
                width=48, height=32,
            ).pack(side="left", padx=(0, 4))

        # ── 반복 일자 (매월) ───────────────────────────────
        ctk.CTkFrame(scroll, height=1, fg_color=("gray80", "gray40")).pack(
            fill="x", padx=16, pady=(6, 4))
        ctk.CTkLabel(scroll, text="반복 일자 (매월)", font=("Malgun Gothic", 13, "bold"),
                     anchor="w").pack(fill="x", **pad)
        ctk.CTkLabel(scroll, text="선택한 일자에 매월 반복됩니다 (복수 선택 가능)",
                     font=("Malgun Gothic", 10), text_color="gray50",
                     anchor="w").pack(fill="x", padx=16, pady=(0, 4))

        days_container = ctk.CTkFrame(scroll, fg_color="transparent")
        days_container.pack(fill="x", padx=16, pady=(0, 6))
        self._day_vars: dict[int, ctk.BooleanVar] = {}
        for row_start in range(1, 32, 7):
            row_frame = ctk.CTkFrame(days_container, fg_color="transparent")
            row_frame.pack(fill="x", pady=1)
            for d in range(row_start, min(row_start + 7, 32)):
                var = ctk.BooleanVar(value=False)
                self._day_vars[d] = var
                ctk.CTkCheckBox(
                    row_frame, text=str(d), variable=var,
                    font=("Malgun Gothic", 11),
                    width=42, height=26,
                    checkbox_width=18, checkbox_height=18,
                ).pack(side="left", padx=1)

        # ── 사분면 분류 ────────────────────────────────────
        ctk.CTkFrame(scroll, height=1, fg_color=("gray80", "gray40")).pack(
            fill="x", padx=16, pady=(6, 4))
        ctk.CTkLabel(scroll, text="분류", font=("Malgun Gothic", 13, "bold"),
                     anchor="w").pack(fill="x", **pad)

        q_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        q_frame.pack(fill="x", padx=16, pady=(0, 4))
        self._urgent_var = ctk.BooleanVar(value=False)
        self._important_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(q_frame, text="긴급함", variable=self._urgent_var,
                        font=styles.FONT_BODY, command=self._update_q_preview).pack(side="left", padx=(0, 16))
        ctk.CTkCheckBox(q_frame, text="중요함", variable=self._important_var,
                        font=styles.FONT_BODY, command=self._update_q_preview).pack(side="left")

        self._q_preview = ctk.CTkLabel(scroll, text="", font=("Malgun Gothic", 11),
                                        corner_radius=6, height=28)
        self._q_preview.pack(fill="x", padx=16, pady=(0, 4))
        self._update_q_preview()

        # 카테고리
        ctk.CTkLabel(scroll, text="카테고리", font=styles.FONT_BODY,
                     anchor="w").pack(fill="x", **pad)
        self._cat_menu = ctk.CTkOptionMenu(scroll, values=self._categories,
                                            font=styles.FONT_BODY)
        self._cat_menu.pack(fill="x", **pad)

        # 메모
        ctk.CTkLabel(scroll, text="메모", font=styles.FONT_BODY,
                     anchor="w").pack(fill="x", **pad)
        self._note_entry = ctk.CTkEntry(scroll, placeholder_text="추가 메모")
        self._note_entry.pack(fill="x", **pad)

    _Q_LABELS = {
        (True,  True):  ("#FFB800", "Q1 · 긴급하고 중요함"),
        (False, True):  ("#C47888", "Q2 · 중요하지만 긴급하지 않음"),
        (True,  False): ("#6A9AB0", "Q3 · 긴급하지만 중요하지 않음"),
        (False, False): ("#9080B8", "Q4 · 긴급하지도 중요하지도 않음"),
    }

    def _update_q_preview(self):
        key = (self._urgent_var.get(), self._important_var.get())
        color, text = self._Q_LABELS[key]
        self._q_preview.configure(text=f"  {text}", fg_color=color, text_color="white")

    def _load_item(self, item: TodoItem):
        self._title_entry.insert(0, item.title)
        self._urgent_var.set(item.urgent)
        self._important_var.set(item.important)
        self._update_q_preview()
        if item.category in self._categories:
            self._cat_menu.set(item.category)
        self._note_entry.insert(0, item.note)
        # 요일 복원
        for wd in getattr(item, "repeat_weekdays", []):
            if 0 <= wd < 7:
                self._wd_vars[wd].set(True)
        # 일자 복원
        for d in getattr(item, "repeat_days", []):
            if d in self._day_vars:
                self._day_vars[d].set(True)

    def _save(self):
        title = self._title_entry.get().strip()
        if not title:
            self._title_entry.configure(border_color="red")
            return

        weekdays = [i for i, v in enumerate(self._wd_vars) if v.get()]
        days = [d for d, v in self._day_vars.items() if v.get()]

        data = {
            "title": title,
            "category": self._cat_menu.get(),
            "urgent": self._urgent_var.get(),
            "important": self._important_var.get(),
            "note": self._note_entry.get().strip(),
            "repeat": True,
            "repeat_weekdays": weekdays,
            "repeat_days": days,
            "due_date": "",
        }

        if self._on_save:
            self._on_save(data)
        self.destroy()


# ── 반복 할 일 관리 뷰 ───────────────────────────────────

class RepeatTasksView(ctk.CTkFrame):
    """반복 할 일만 모아서 관리하는 뷰."""

    _Q_COLORS = {
        (True,  True):  ("#FFB800", "Q1  긴급 + 중요"),
        (False, True):  ("#C47888", "Q2  중요"),
        (True,  False): ("#6A9AB0", "Q3  긴급"),
        (False, False): ("#9080B8", "Q4  기타"),
    }

    def __init__(self, parent, controller, on_refresh_matrix=None):
        super().__init__(parent, fg_color=("gray95", "gray12"), corner_radius=0)
        self._ctrl = controller
        self._on_refresh_matrix = on_refresh_matrix
        self._build()
        self.after(50, self._refresh)

    def _build(self):
        sub = ctk.CTkFrame(self, fg_color=("gray92", "gray15"),
                           height=44, corner_radius=0)
        sub.pack(fill="x")
        sub.pack_propagate(False)

        ctk.CTkLabel(sub, text="🔁 반복 할 일 관리",
                     font=("Malgun Gothic", 14, "bold"),
                     text_color=("gray20", "gray80")).pack(side="left", padx=16)

        ctk.CTkButton(
            sub, text="+ 반복 할 일 추가",
            width=140, height=32, font=styles.FONT_BODY,
            command=self._on_add,
        ).pack(side="right", padx=12)

        ctk.CTkLabel(self, text="지정한 요일/일자에 해당 사분면에서 자동 반복됩니다.  (요일·일자 미지정 시 매일 반복)",
                     font=("Malgun Gothic", 11), text_color="gray50",
                     anchor="w").pack(fill="x", padx=16, pady=(8, 4))

        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0)
        self._list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _refresh(self):
        for w in self._list_frame.winfo_children():
            w.destroy()

        items = self._ctrl.get_repeat_items()
        if not items:
            ctk.CTkLabel(self._list_frame,
                         text="반복 할 일이 없습니다.\n'+ 반복 할 일 추가' 버튼으로 추가하세요.",
                         font=("Malgun Gothic", 12),
                         text_color="gray55").pack(pady=40)
            return

        for item in items:
            color, q_label = self._Q_COLORS.get(
                (item.urgent, item.important), ("#888", "기타"))
            self._make_row(item, color, q_label)

    def _make_row(self, item, color: str, q_label: str):
        row = ctk.CTkFrame(self._list_frame, fg_color=("white", "gray20"),
                           corner_radius=8, height=72)
        row.pack(fill="x", padx=4, pady=3)
        row.pack_propagate(False)

        ctk.CTkFrame(row, width=6, fg_color=color,
                     corner_radius=3).pack(side="left", fill="y", padx=(6, 8), pady=8)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, pady=4)

        ctk.CTkLabel(info, text=f"🔁  {item.title}",
                     font=("Malgun Gothic", 13, "bold"),
                     anchor="w").pack(fill="x")

        # 스케줄 설명
        schedule = self._describe_schedule(item)
        ctk.CTkLabel(info, text=f"{q_label}  ·  {schedule}",
                     font=("Malgun Gothic", 10),
                     text_color="gray50", anchor="w").pack(fill="x")

        btn_frame = ctk.CTkFrame(row, fg_color="transparent")
        btn_frame.pack(side="right", padx=8, pady=4)

        ctk.CTkButton(
            btn_frame, text="수정", width=50, height=28,
            font=("Malgun Gothic", 11),
            fg_color=("gray70", "gray40"),
            hover_color=("gray60", "gray50"),
            command=lambda iid=item.id: self._on_edit(iid),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_frame, text="삭제", width=50, height=28,
            font=("Malgun Gothic", 11),
            fg_color=("#DD5555", "#CC4444"),
            hover_color=("#CC3333", "#BB3333"),
            text_color="white",
            command=lambda iid=item.id: self._on_delete(iid),
        ).pack(side="left", padx=2)

    @staticmethod
    def _describe_schedule(item) -> str:
        weekdays = getattr(item, "repeat_weekdays", [])
        days = getattr(item, "repeat_days", [])
        parts = []
        if weekdays:
            names = [_WEEKDAY_NAMES[w] for w in sorted(weekdays) if w < 7]
            parts.append("매주 " + "·".join(names))
        if days:
            parts.append("매월 " + ", ".join(f"{d}일" for d in sorted(days)))
        return " / ".join(parts) if parts else "매일 반복"

    def _on_add(self):
        categories = self._ctrl.get_categories(styles.DEFAULT_CATEGORIES)

        def _save(data):
            self._ctrl.add_item(**data)
            self.after(20, self._refresh)
            if self._on_refresh_matrix:
                self.after(40, self._on_refresh_matrix)

        RepeatEditDialog(self, categories=categories, item=None, on_save=_save)

    def _on_edit(self, item_id: str):
        item = next((i for i in self._ctrl.get_all() if i.id == item_id), None)
        if item is None:
            return
        categories = self._ctrl.get_categories(styles.DEFAULT_CATEGORIES)

        def _save(data):
            self._ctrl.update_item(item_id, **data)
            self.after(20, self._refresh)
            if self._on_refresh_matrix:
                self.after(40, self._on_refresh_matrix)

        RepeatEditDialog(self, categories=categories, item=item, on_save=_save)

    def _on_delete(self, item_id: str):
        item = next((i for i in self._ctrl.get_all() if i.id == item_id), None)
        if item and messagebox.askyesno("삭제 확인",
                                         f"반복 할 일 '{item.title}'을(를) 삭제할까요?"):
            self._ctrl.delete_item(item_id)
            self.after(20, self._refresh)
            if self._on_refresh_matrix:
                self.after(40, self._on_refresh_matrix)


# ── 주간 습관 트래커 ─────────────────────────────────────────

def _habit_get_weeks(year: int, month: int) -> list[tuple[str, list[str]]]:
    """해당 월의 주차별 (label, [날짜문자열 7개]) 리스트 반환. 월요일 시작."""
    first = _Date(year, month, 1)
    mon = first - _Timedelta(days=first.weekday())
    weeks = []
    week_num = 1
    while True:
        dates = [mon + _Timedelta(days=i) for i in range(7)]
        if dates[0].month > month and dates[0].year >= year:
            break
        if dates[6] >= first:
            label = f"{week_num}주차"
            weeks.append((label, [d.isoformat() for d in dates]))
            week_num += 1
        mon += _Timedelta(days=7)
        if week_num > 6:
            break
    return weeks


def _habit_current_week_index(weeks: list[tuple[str, list[str]]]) -> int:
    """오늘이 포함된 주차의 인덱스를 반환. 없으면 0."""
    today = _Date.today().isoformat()
    for i, (_, dates) in enumerate(weeks):
        if dates[0] <= today <= dates[6]:
            return i
    return 0


class HabitTracker(ctk.CTkFrame):
    """캘린더 사이드바 하단에 표시되는 주간 습관 체크 위젯 (현재 주차만)."""

    _WD = ["월", "화", "수", "목", "금", "토", "일"]

    def __init__(self, parent, year: int, month: int):
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self._habit_mgr = HabitManager()
        self._year = year
        self._month = month
        self._tips: dict[str, object] = {}
        self._build()

    def set_month(self, year: int, month: int):
        self._year = year
        self._month = month
        self._build()

    # ── UI 빌드 ──────────────────────────────────────────

    def _build(self):
        for w in self.winfo_children():
            w.destroy()
        self._tips.clear()

        habits = self._habit_mgr.get_habits()
        weeks = _habit_get_weeks(self._year, self._month)

        # 헤더
        hdr = ctk.CTkFrame(self, fg_color="transparent", height=28)
        hdr.pack(fill="x", padx=4, pady=(6, 2))
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="✅ 습관 체크",
                     font=("Malgun Gothic", 12, "bold"),
                     text_color="gray40").pack(side="left", padx=4)
        ctk.CTkButton(hdr, text="+", width=24, height=24,
                      font=("Malgun Gothic", 12, "bold"),
                      fg_color=("gray75", "gray35"),
                      hover_color=("gray65", "gray45"),
                      corner_radius=12,
                      command=self._on_add_habit).pack(side="right", padx=4)

        if not habits:
            ctk.CTkLabel(self, text="+ 버튼으로 습관을 추가하세요",
                         font=("Malgun Gothic", 10),
                         text_color="gray55").pack(pady=8)
            return

        if not weeks:
            return

        # 현재 주차만 표시
        idx = _habit_current_week_index(weeks)
        week_label, week_dates = weeks[idx]

        self._build_week_table(self, week_label, week_dates, habits)

    def _build_week_table(self, parent, week_label: str,
                          week_dates: list[str], habits: list[str]):
        wf = ctk.CTkFrame(parent, fg_color=("gray85", "gray22"), corner_radius=6)
        wf.pack(fill="x", padx=2, pady=(6, 2))

        ctk.CTkLabel(wf, text=week_label,
                     font=("Malgun Gothic", 10, "bold"),
                     text_color="gray50").pack(anchor="w", padx=6, pady=(4, 2))

        tbl = ctk.CTkFrame(wf, fg_color="transparent")
        tbl.pack(fill="x", padx=4, pady=(0, 4))

        cols = len(self._WD) + 1
        for c in range(cols):
            tbl.grid_columnconfigure(c, weight=1 if c == 0 else 0,
                                     minsize=22 if c > 0 else 60)

        # 요일 헤더
        for c, wd in enumerate(self._WD):
            color = "#CC4444" if c == 6 else ("#2277CC" if c == 5 else "gray50")
            ctk.CTkLabel(tbl, text=wd,
                         font=("Malgun Gothic", 9, "bold"),
                         text_color=color,
                         width=22).grid(row=0, column=c + 1, padx=1, pady=1)

        # 습관 행
        for r, habit in enumerate(habits):
            name = habit[:6] + ("…" if len(habit) > 6 else "")
            name_lbl = ctk.CTkLabel(tbl, text=name,
                                     font=("Malgun Gothic", 9),
                                     text_color=("gray20", "gray80"),
                                     anchor="w")
            name_lbl.grid(row=r + 1, column=0, sticky="w", padx=(2, 4), pady=1)
            name_lbl.bind("<Button-3>",
                          lambda e, h=habit: self._on_remove_habit(h))

            for c, date_str in enumerate(week_dates):
                checked = self._habit_mgr.is_checked(habit, date_str)
                d = _Date.fromisoformat(date_str)
                in_month = (d.month == self._month and d.year == self._year)

                if not in_month:
                    ctk.CTkLabel(tbl, text="·",
                                 font=("Malgun Gothic", 9),
                                 text_color="gray75",
                                 width=22).grid(row=r + 1, column=c + 1,
                                                padx=1, pady=1)
                    continue

                cell = ctk.CTkFrame(tbl, width=22, height=22,
                                    fg_color="transparent", corner_radius=4)
                cell.grid(row=r + 1, column=c + 1, padx=1, pady=1)
                cell.grid_propagate(False)

                if checked:
                    stamp = ctk.CTkLabel(
                        cell, text="◎",
                        font=("Malgun Gothic", 13, "bold"),
                        text_color="#E8453C",
                        width=22, height=22,
                    )
                    stamp.place(relx=0.5, rely=0.5, anchor="center")
                    stamp.bind("<Button-1>",
                               lambda e, h=habit, ds=date_str: self._toggle(h, ds))
                    stamp.bind("<Enter>",
                               lambda e, w=stamp: self._show_stamp_tip(e, w))
                    stamp.bind("<Leave>",
                               lambda e, w=stamp: self._hide_stamp_tip(w))
                else:
                    btn = ctk.CTkLabel(
                        cell, text="□",
                        font=("Malgun Gothic", 12),
                        text_color="gray60",
                        width=22, height=22,
                        cursor="hand2",
                    )
                    btn.place(relx=0.5, rely=0.5, anchor="center")
                    btn.bind("<Button-1>",
                             lambda e, h=habit, ds=date_str: self._toggle(h, ds))

    # ── 도장 툴팁 ─────────────────────────────────────────

    def _show_stamp_tip(self, event, widget):
        tip = _tk.Toplevel(widget)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        x = widget.winfo_rootx() - 20
        y = widget.winfo_rooty() - 30
        tip.geometry(f"+{x}+{y}")
        lbl = _tk.Label(tip, text=" 참잘했어요! ",
                        font=("Malgun Gothic", 9, "bold"),
                        fg="#E8453C", bg="#FFF8F0",
                        relief="solid", borderwidth=1)
        lbl.pack()
        self._tips[str(id(widget))] = tip

    def _hide_stamp_tip(self, widget):
        key = str(id(widget))
        tip = self._tips.pop(key, None)
        if tip and tip.winfo_exists():
            tip.destroy()

    # ── 이벤트 ────────────────────────────────────────────

    def _toggle(self, habit: str, date_str: str):
        self._habit_mgr.toggle_check(habit, date_str)
        self._build()

    def _on_add_habit(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("습관 추가")
        dialog.geometry("300x150")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.lift()
        dialog.focus_force()

        ctk.CTkLabel(dialog, text="새 습관 이름",
                     font=("Malgun Gothic", 13, "bold")).pack(pady=(16, 4))
        entry = ctk.CTkEntry(dialog, width=240, height=36,
                              font=("Malgun Gothic", 13),
                              placeholder_text="예: 물 마시기, 운동, 독서")
        entry.pack(pady=4)
        entry.focus()

        def save():
            name = entry.get().strip()
            if name:
                self._habit_mgr.add_habit(name)
                dialog.destroy()
                self._build()

        ctk.CTkButton(dialog, text="추가", height=36,
                      font=("Malgun Gothic", 13, "bold"),
                      command=save).pack(pady=(8, 4))
        entry.bind("<Return>", lambda e: save())

    def _on_remove_habit(self, habit: str):
        if messagebox.askyesno("습관 삭제",
                               f"'{habit}' 습관을 삭제할까요?\n(체크 기록도 함께 삭제됩니다)"):
            self._habit_mgr.remove_habit(habit)
            self._build()


# ── 습관 체크 전체 뷰 (년/월/주차별 조회) ─────────────────────

class HabitFullView(ctk.CTkFrame):
    """햄버거 메뉴에서 접근하는 전체 습관 관리 뷰."""

    _WD = ["월", "화", "수", "목", "금", "토", "일"]
    _MONTHS = [f"{m}월" for m in range(1, 13)]

    def __init__(self, parent):
        super().__init__(parent, fg_color=("gray95", "gray12"), corner_radius=0)
        self._habit_mgr = HabitManager()
        self._tips: dict[str, object] = {}

        today = _Date.today()
        self._year = today.year
        self._month = today.month

        self._build_header()
        self._content = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                                corner_radius=0)
        self._content.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._refresh()

    def _build_header(self):
        sub = ctk.CTkFrame(self, fg_color=("gray92", "gray15"),
                           height=44, corner_radius=0)
        sub.pack(fill="x")
        sub.pack_propagate(False)

        ctk.CTkLabel(sub, text="✅ 습관 체크 관리",
                     font=("Malgun Gothic", 14, "bold"),
                     text_color=("gray20", "gray80")).pack(side="left", padx=16)

        ctk.CTkButton(
            sub, text="+ 습관 추가",
            width=110, height=32, font=("Malgun Gothic", 12),
            command=self._on_add_habit,
        ).pack(side="right", padx=12)

        # 년/월 선택 바
        nav = ctk.CTkFrame(self, fg_color="transparent", height=46)
        nav.pack(fill="x", padx=12, pady=(10, 4))
        nav.pack_propagate(False)

        ctk.CTkButton(nav, text="◀", width=34, height=34,
                      command=lambda: self._navigate(-1)).pack(side="left")
        ctk.CTkButton(nav, text="▶", width=34, height=34,
                      command=lambda: self._navigate(1)).pack(side="left", padx=(2, 8))

        self._nav_lbl = ctk.CTkLabel(nav, text="",
                                      font=("Malgun Gothic", 16, "bold"))
        self._nav_lbl.pack(side="left", padx=8)

        ctk.CTkButton(nav, text="오늘", width=60, height=34,
                      font=("Malgun Gothic", 12),
                      command=self._go_today).pack(side="left", padx=8)

    def _navigate(self, delta: int):
        self._month += delta
        if self._month > 12:
            self._month, self._year = 1, self._year + 1
        elif self._month < 1:
            self._month, self._year = 12, self._year - 1
        self._refresh()

    def _go_today(self):
        today = _Date.today()
        self._year, self._month = today.year, today.month
        self._refresh()

    def _refresh(self):
        self._nav_lbl.configure(
            text=f"{self._year}년 {self._MONTHS[self._month - 1]}")

        for w in self._content.winfo_children():
            w.destroy()
        self._tips.clear()

        habits = self._habit_mgr.get_habits()
        weeks = _habit_get_weeks(self._year, self._month)

        if not habits:
            ctk.CTkLabel(self._content,
                         text="등록된 습관이 없습니다.\n'+ 습관 추가' 버튼으로 추가하세요.",
                         font=("Malgun Gothic", 13),
                         text_color="gray55").pack(pady=40)
            return

        # 습관 목록 표시
        habit_bar = ctk.CTkFrame(self._content, fg_color="transparent")
        habit_bar.pack(fill="x", padx=4, pady=(4, 8))
        ctk.CTkLabel(habit_bar, text="등록된 습관:",
                     font=("Malgun Gothic", 11),
                     text_color="gray50").pack(side="left", padx=(4, 8))
        for habit in habits:
            chip = ctk.CTkFrame(habit_bar, fg_color=("gray82", "gray28"),
                                corner_radius=12)
            chip.pack(side="left", padx=2)
            ctk.CTkLabel(chip, text=f" {habit} ",
                         font=("Malgun Gothic", 11),
                         text_color=("gray20", "gray80")).pack(side="left", padx=(6, 2))
            ctk.CTkButton(chip, text="✕", width=20, height=20,
                          font=("Malgun Gothic", 9),
                          fg_color="transparent",
                          text_color="gray50",
                          hover_color=("gray70", "gray40"),
                          command=lambda h=habit: self._on_remove_habit(h)).pack(
                side="left", padx=(0, 4))

        # 주차별 테이블
        cur_week_idx = _habit_current_week_index(weeks)
        for i, (week_label, week_dates) in enumerate(weeks):
            is_current = (i == cur_week_idx
                          and self._year == _Date.today().year
                          and self._month == _Date.today().month)
            self._build_week_table(week_label, week_dates, habits, is_current)

    def _build_week_table(self, week_label: str, week_dates: list[str],
                          habits: list[str], is_current: bool):
        border_color = "#1A73E8" if is_current else ("gray80", "gray35")
        wf = ctk.CTkFrame(self._content,
                          fg_color=("white", "gray20"),
                          corner_radius=8,
                          border_width=2 if is_current else 1,
                          border_color=border_color)
        wf.pack(fill="x", padx=4, pady=(0, 8))

        # 주차 헤더
        hdr = ctk.CTkFrame(wf, fg_color="transparent", height=32)
        hdr.pack(fill="x", padx=8, pady=(6, 2))
        hdr.pack_propagate(False)

        label_text = week_label
        if is_current:
            label_text += "  (이번 주)"
        ctk.CTkLabel(hdr, text=label_text,
                     font=("Malgun Gothic", 12, "bold"),
                     text_color="#1A73E8" if is_current else ("gray30", "gray70")
                     ).pack(side="left", padx=4)

        # 날짜 범위 표시
        d0 = _Date.fromisoformat(week_dates[0])
        d6 = _Date.fromisoformat(week_dates[6])
        range_text = f"{d0.month}/{d0.day} ~ {d6.month}/{d6.day}"
        ctk.CTkLabel(hdr, text=range_text,
                     font=("Malgun Gothic", 10),
                     text_color="gray50").pack(side="left", padx=8)

        # 테이블
        tbl = ctk.CTkFrame(wf, fg_color="transparent")
        tbl.pack(fill="x", padx=12, pady=(0, 8))

        cols = len(self._WD) + 1
        for c in range(cols):
            tbl.grid_columnconfigure(c, weight=1 if c == 0 else 0,
                                     minsize=36 if c > 0 else 100)

        # 요일 헤더 + 날짜
        for c, wd in enumerate(self._WD):
            d = _Date.fromisoformat(week_dates[c])
            color = "#CC4444" if c == 6 else ("#2277CC" if c == 5 else "gray50")
            header_text = f"{wd}\n{d.day}일"
            ctk.CTkLabel(tbl, text=header_text,
                         font=("Malgun Gothic", 10, "bold"),
                         text_color=color,
                         width=36).grid(row=0, column=c + 1, padx=2, pady=(2, 4))

        # 습관 행
        for r, habit in enumerate(habits):
            name_lbl = ctk.CTkLabel(tbl, text=habit,
                                     font=("Malgun Gothic", 11),
                                     text_color=("gray20", "gray80"),
                                     anchor="w")
            name_lbl.grid(row=r + 1, column=0, sticky="w", padx=(4, 8), pady=2)

            for c, date_str in enumerate(week_dates):
                checked = self._habit_mgr.is_checked(habit, date_str)
                d = _Date.fromisoformat(date_str)
                in_month = (d.month == self._month and d.year == self._year)

                if not in_month:
                    ctk.CTkLabel(tbl, text="·",
                                 font=("Malgun Gothic", 11),
                                 text_color="gray75",
                                 width=36).grid(row=r + 1, column=c + 1,
                                                padx=2, pady=2)
                    continue

                cell = ctk.CTkFrame(tbl, width=36, height=28,
                                    fg_color="transparent", corner_radius=4)
                cell.grid(row=r + 1, column=c + 1, padx=2, pady=2)
                cell.grid_propagate(False)

                if checked:
                    stamp = ctk.CTkLabel(
                        cell, text="◎",
                        font=("Malgun Gothic", 16, "bold"),
                        text_color="#E8453C",
                        width=36, height=28,
                        cursor="hand2",
                    )
                    stamp.place(relx=0.5, rely=0.5, anchor="center")
                    stamp.bind("<Button-1>",
                               lambda e, h=habit, ds=date_str: self._toggle(h, ds))
                    stamp.bind("<Enter>",
                               lambda e, w=stamp: self._show_stamp_tip(e, w))
                    stamp.bind("<Leave>",
                               lambda e, w=stamp: self._hide_stamp_tip(w))
                else:
                    btn = ctk.CTkLabel(
                        cell, text="□",
                        font=("Malgun Gothic", 14),
                        text_color="gray55",
                        width=36, height=28,
                        cursor="hand2",
                    )
                    btn.place(relx=0.5, rely=0.5, anchor="center")
                    btn.bind("<Button-1>",
                             lambda e, h=habit, ds=date_str: self._toggle(h, ds))

    # ── 도장 툴팁 ─────────────────────────────────────────

    def _show_stamp_tip(self, event, widget):
        tip = _tk.Toplevel(widget)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        x = widget.winfo_rootx() - 20
        y = widget.winfo_rooty() - 30
        tip.geometry(f"+{x}+{y}")
        lbl = _tk.Label(tip, text=" 참잘했어요! ",
                        font=("Malgun Gothic", 9, "bold"),
                        fg="#E8453C", bg="#FFF8F0",
                        relief="solid", borderwidth=1)
        lbl.pack()
        self._tips[str(id(widget))] = tip

    def _hide_stamp_tip(self, widget):
        key = str(id(widget))
        tip = self._tips.pop(key, None)
        if tip and tip.winfo_exists():
            tip.destroy()

    # ── 이벤트 ────────────────────────────────────────────

    def _toggle(self, habit: str, date_str: str):
        self._habit_mgr.toggle_check(habit, date_str)
        self._refresh()

    def _on_add_habit(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("습관 추가")
        dialog.geometry("300x150")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.lift()
        dialog.focus_force()

        ctk.CTkLabel(dialog, text="새 습관 이름",
                     font=("Malgun Gothic", 13, "bold")).pack(pady=(16, 4))
        entry = ctk.CTkEntry(dialog, width=240, height=36,
                              font=("Malgun Gothic", 13),
                              placeholder_text="예: 물 마시기, 운동, 독서")
        entry.pack(pady=4)
        entry.focus()

        def save():
            name = entry.get().strip()
            if name:
                self._habit_mgr.add_habit(name)
                dialog.destroy()
                self._refresh()

        ctk.CTkButton(dialog, text="추가", height=36,
                      font=("Malgun Gothic", 13, "bold"),
                      command=save).pack(pady=(8, 4))
        entry.bind("<Return>", lambda e: save())

    def _on_remove_habit(self, habit: str):
        if messagebox.askyesno("습관 삭제",
                               f"'{habit}' 습관을 삭제할까요?\n(체크 기록도 함께 삭제됩니다)"):
            self._habit_mgr.remove_habit(habit)
            self._refresh()
