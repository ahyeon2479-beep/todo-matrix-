import os
import json
import time
from datetime import datetime, date

from flask import Flask, render_template, redirect, url_for, request, jsonify, session, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

from models_db import db, User, Todo, Memo, Habit, HabitCheck, BucketItem, Diary, FreeMemo, StickyNote, MemoFolder, PayAccount, FinanceRecord, FixedExpense, Loan
from holidays_kr import HOLIDAYS_KR

from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config["PREFERRED_URL_SCHEME"] = "https"
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")
_db_url = os.getenv("DATABASE_URL", "")
if _db_url:
    # Render/Heroku에서 postgres:// 를 postgresql:// 로 변환
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = _db_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///todos.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True, "pool_recycle": 300}

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
def cache_bust():
    return str(int(time.time()))

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login_page"

# ── Google OAuth ─────────────────────────────────────────

_GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
_GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=_GOOGLE_CLIENT_ID,
    client_secret=_GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


# ── 인증 라우트 ──────────────────────────────────────────

@app.route("/")
def index():
    if current_user.is_authenticated:
        return render_template("index.html", user=current_user, cache_bust=cache_bust())
    return redirect(url_for("login_page"))


@app.route("/login")
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("login.html", dev_mode=DEV_MODE)


@app.route("/auth/google")
def auth_google():
    redirect_uri = url_for("auth_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/callback")
def auth_callback():
    token = google.authorize_access_token()
    userinfo = token.get("userinfo")
    if not userinfo:
        return redirect(url_for("login_page"))

    user = db.session.get(User, userinfo["sub"])
    if user:
        user.name = userinfo.get("name", user.name)
        user.picture = userinfo.get("picture", user.picture)
    else:
        user = User(
            id=userinfo["sub"],
            email=userinfo["email"],
            name=userinfo.get("name", ""),
            picture=userinfo.get("picture", ""),
        )
        db.session.add(user)
    db.session.commit()
    login_user(user)
    return redirect(url_for("index"))


@app.route("/auth/dev-login", methods=["GET", "POST"])
def dev_login():
    if not DEV_MODE:
        return jsonify({"error": "Not allowed"}), 403
    user = db.session.get(User, "dev-user")
    if not user:
        user = User(id="dev-user", email="dev@local", name="개발자", picture="")
        db.session.add(user)
        db.session.commit()
    login_user(user)
    return redirect(url_for("index"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login_page"))


# ── Todo API ─────────────────────────────────────────────

@app.route("/api/todos")
@login_required
def get_todos():
    date_filter = request.args.get("date")
    todos = Todo.query.filter_by(user_id=current_user.id).all()
    results = []
    for t in todos:
        if date_filter:
            if t.repeat:
                if _matches_repeat(t, date_filter):
                    results.append(t.to_dict())
            elif t.due_date == date_filter:
                results.append(t.to_dict())
        else:
            results.append(t.to_dict())
    return jsonify(results)


@app.route("/api/todos", methods=["POST"])
@login_required
def create_todo():
    data = request.json
    todo = Todo(
        user_id=current_user.id,
        title=data["title"],
        note=data.get("note", ""),
        category=data.get("category", "개인"),
        urgent=data.get("urgent", False),
        important=data.get("important", True),
        due_date=data.get("due_date", ""),
        repeat=data.get("repeat", False),
        repeat_weekdays=json.dumps(data.get("repeat_weekdays", [])),
        repeat_days=json.dumps(data.get("repeat_days", [])),
    )
    db.session.add(todo)
    db.session.commit()
    return jsonify(todo.to_dict()), 201


@app.route("/api/todos/<int:todo_id>", methods=["PUT"])
@login_required
def update_todo(todo_id):
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
    data = request.json
    for key in ["title", "note", "category", "urgent", "important",
                "completed", "due_date", "repeat"]:
        if key in data:
            setattr(todo, key, data[key])
    if "repeat_weekdays" in data:
        todo.repeat_weekdays = json.dumps(data["repeat_weekdays"])
    if "repeat_days" in data:
        todo.repeat_days = json.dumps(data["repeat_days"])
    todo.updated_at = datetime.now()
    db.session.commit()
    return jsonify(todo.to_dict())


@app.route("/api/todos/<int:todo_id>", methods=["DELETE"])
@login_required
def delete_todo(todo_id):
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
    db.session.delete(todo)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/todos/<int:todo_id>/toggle", methods=["POST"])
@login_required
def toggle_todo(todo_id):
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
    if todo.repeat:
        return jsonify(todo.to_dict())
    todo.completed = not todo.completed
    todo.updated_at = datetime.now()
    db.session.commit()
    return jsonify(todo.to_dict())


# ── Memo API ─────────────────────────────────────────────

@app.route("/api/memos/<date_str>")
@login_required
def get_memo(date_str):
    memo = Memo.query.filter_by(user_id=current_user.id, date_str=date_str).first()
    return jsonify({"text": memo.text if memo else ""})


@app.route("/api/memos/<date_str>", methods=["PUT"])
@login_required
def save_memo(date_str):
    text = request.json.get("text", "")
    memo = Memo.query.filter_by(user_id=current_user.id, date_str=date_str).first()
    if memo:
        memo.text = text
    else:
        memo = Memo(user_id=current_user.id, date_str=date_str, text=text)
        db.session.add(memo)
    db.session.commit()
    return jsonify({"ok": True})


# ── Habit API ────────────────────────────────────────────

@app.route("/api/habits")
@login_required
def get_habits():
    habits = Habit.query.filter_by(user_id=current_user.id).order_by(Habit.order).all()
    return jsonify([{"id": h.id, "name": h.name} for h in habits])


@app.route("/api/habits", methods=["POST"])
@login_required
def add_habit():
    name = request.json.get("name", "").strip()
    if not name:
        return jsonify({"error": "이름 필요"}), 400
    max_order = db.session.query(db.func.max(Habit.order)).filter_by(
        user_id=current_user.id).scalar() or 0
    habit = Habit(user_id=current_user.id, name=name, order=max_order + 1)
    db.session.add(habit)
    # Q4 반복 할일 자동 생성
    todo = Todo(
        user_id=current_user.id,
        title=f"[습관] {name}",
        category="개인",
        urgent=False,
        important=False,
        repeat=True,
        repeat_weekdays="[]",
        repeat_days="[]",
    )
    db.session.add(todo)
    db.session.commit()
    return jsonify({"id": habit.id, "name": habit.name}), 201


@app.route("/api/habits/reorder", methods=["POST"])
@login_required
def reorder_habits():
    ids = request.json.get("ids", [])
    for i, hid in enumerate(ids):
        habit = Habit.query.filter_by(id=hid, user_id=current_user.id).first()
        if habit:
            habit.order = i
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/habits/<int:habit_id>", methods=["DELETE"])
@login_required
def delete_habit(habit_id):
    habit = Habit.query.filter_by(id=habit_id, user_id=current_user.id).first_or_404()
    # 연결된 Q4 반복 할일도 삭제
    linked_todo = Todo.query.filter_by(
        user_id=current_user.id, title=f"[습관] {habit.name}", repeat=True
    ).first()
    if linked_todo:
        db.session.delete(linked_todo)
    db.session.delete(habit)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/habits/<int:habit_id>/toggle", methods=["POST"])
@login_required
def toggle_habit(habit_id):
    habit = Habit.query.filter_by(id=habit_id, user_id=current_user.id).first_or_404()
    date_str = request.json.get("date")
    if not date_str:
        return jsonify({"error": "날짜 필요"}), 400
    check = HabitCheck.query.filter_by(habit_id=habit_id, date_str=date_str).first()
    if check:
        db.session.delete(check)
        checked = False
    else:
        db.session.add(HabitCheck(habit_id=habit_id, date_str=date_str))
        checked = True
    db.session.commit()
    return jsonify({"checked": checked})


@app.route("/api/habits/checks")
@login_required
def get_habit_checks():
    habits = Habit.query.filter_by(user_id=current_user.id).all()
    habit_ids = [h.id for h in habits]
    dates = request.args.get("dates", "").split(",")
    checks = HabitCheck.query.filter(
        HabitCheck.habit_id.in_(habit_ids),
        HabitCheck.date_str.in_(dates),
    ).all()
    result = {}
    for c in checks:
        result[f"{c.habit_id}|{c.date_str}"] = True
    return jsonify(result)


# ── Holidays API ─────────────────────────────────────────

@app.route("/api/holidays")
def get_holidays():
    return jsonify(HOLIDAYS_KR)


# ── 헬퍼 ─────────────────────────────────────────────────

# ── Bucket List API ───────────────────────────────────────

@app.route("/api/bucket")
@login_required
def get_bucket():
    year = request.args.get("year", date.today().year, type=int)
    items = BucketItem.query.filter_by(user_id=current_user.id, year=year).order_by(BucketItem.order).all()
    return jsonify([i.to_dict() for i in items])


@app.route("/api/bucket", methods=["POST"])
@login_required
def add_bucket():
    data = request.json
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "내용 필요"}), 400
    year = data.get("year", date.today().year)
    max_order = db.session.query(db.func.max(BucketItem.order)).filter_by(
        user_id=current_user.id, year=year).scalar() or 0
    item = BucketItem(user_id=current_user.id, text=text, year=year, order=max_order + 1)
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@app.route("/api/bucket/<int:item_id>", methods=["PUT"])
@login_required
def update_bucket(item_id):
    item = BucketItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    data = request.json
    if "text" in data:
        item.text = data["text"]
    if "completed" in data:
        item.completed = data["completed"]
    db.session.commit()
    return jsonify(item.to_dict())


@app.route("/api/bucket/<int:item_id>", methods=["DELETE"])
@login_required
def delete_bucket(item_id):
    item = BucketItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


# ── Diary API ─────────────────────────────────────────────

@app.route("/api/diary")
@login_required
def get_diaries():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    q = Diary.query.filter_by(user_id=current_user.id).filter(Diary.deleted != True)
    if year:
        q = q.filter(db.extract("year", Diary.created_at) == year)
    if month:
        q = q.filter(db.extract("month", Diary.created_at) == month)
    entries = q.order_by(Diary.date_str.desc()).all()
    return jsonify([e.to_dict() for e in entries])


@app.route("/api/diary/trash")
@login_required
def get_diary_trash():
    entries = Diary.query.filter_by(user_id=current_user.id, deleted=True)\
        .order_by(Diary.deleted_at.desc()).all()
    return jsonify([e.to_dict() for e in entries])


@app.route("/api/diary/restore/<int:diary_id>", methods=["POST"])
@login_required
def restore_diary(diary_id):
    entry = Diary.query.filter_by(id=diary_id, user_id=current_user.id, deleted=True).first_or_404()
    entry.deleted = False
    entry.deleted_at = None
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/diary/permanent/<int:diary_id>", methods=["DELETE"])
@login_required
def permanent_delete_diary(diary_id):
    entry = Diary.query.filter_by(id=diary_id, user_id=current_user.id, deleted=True).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/diary", methods=["POST"])
@login_required
def create_diary():
    try:
        data = request.json
        entry = Diary(
            user_id=current_user.id, date_str=data.get("date_str", ""),
            title=data.get("title", ""), content=data.get("content", ""),
            mood=data.get("mood", ""), event=data.get("event", ""),
        )
        db.session.add(entry)
        db.session.commit()
        return jsonify(entry.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route("/api/diary/<int:diary_id>", methods=["PUT"])
@login_required
def update_diary(diary_id):
    try:
        data = request.json
        entry = Diary.query.filter_by(id=diary_id, user_id=current_user.id).first_or_404()
        entry.title = data.get("title", entry.title)
        entry.content = data.get("content", entry.content)
        entry.mood = data.get("mood", entry.mood)
        entry.event = data.get("event", entry.event)
        entry.updated_at = datetime.now()
        db.session.commit()
        return jsonify(entry.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route("/api/diary/<int:diary_id>", methods=["DELETE"])
@login_required
def delete_diary(diary_id):
    entry = Diary.query.filter_by(id=diary_id, user_id=current_user.id).first_or_404()
    entry.deleted = True
    entry.deleted_at = datetime.now()
    db.session.commit()
    return jsonify({"ok": True})


# ── Fixed Memo (고정 메모) API ─────────────────────────────

@app.route("/api/fixed-memo")
@login_required
def get_fixed_memo():
    memo = Memo.query.filter_by(user_id=current_user.id, date_str="__fixed__").first()
    return jsonify({"text": memo.text if memo else ""})


@app.route("/api/fixed-memo", methods=["PUT"])
@login_required
def save_fixed_memo():
    data = request.json
    memo = Memo.query.filter_by(user_id=current_user.id, date_str="__fixed__").first()
    if memo:
        memo.text = data.get("text", "")
    else:
        memo = Memo(user_id=current_user.id, date_str="__fixed__", text=data.get("text", ""))
        db.session.add(memo)
    db.session.commit()
    return jsonify({"text": memo.text})


# ── Sticky Note (이번주 할 일) API ────────────────────────

@app.route("/api/sticky")
@login_required
def get_sticky():
    notes = StickyNote.query.filter_by(user_id=current_user.id).order_by(StickyNote.order).all()
    return jsonify([n.to_dict() for n in notes])


@app.route("/api/sticky", methods=["POST"])
@login_required
def add_sticky():
    data = request.json
    note = StickyNote(user_id=current_user.id, text=data["text"])
    db.session.add(note)
    db.session.commit()
    return jsonify(note.to_dict())


@app.route("/api/sticky/<int:nid>", methods=["PUT"])
@login_required
def update_sticky(nid):
    note = StickyNote.query.filter_by(id=nid, user_id=current_user.id).first_or_404()
    data = request.json
    if "text" in data:
        note.text = data["text"]
    if "done" in data:
        note.done = data["done"]
    db.session.commit()
    return jsonify(note.to_dict())


@app.route("/api/sticky/<int:nid>", methods=["DELETE"])
@login_required
def delete_sticky(nid):
    note = StickyNote.query.filter_by(id=nid, user_id=current_user.id).first_or_404()
    db.session.delete(note)
    db.session.commit()
    return jsonify({"ok": True})


# ── Diary Download ────────────────────────────────────────

@app.route("/diary/download/txt", methods=["GET", "POST"])
@login_required
def download_diary_txt():
    if request.method == "POST":
        ids = request.json.get("ids", [])
    else:
        ids = [int(x) for x in request.args.get("ids", "").split(",") if x]
    entries = Diary.query.filter(Diary.id.in_(ids), Diary.user_id == current_user.id).order_by(Diary.date_str.asc()).all()
    lines = []
    for e in entries:
        lines.append(f"{'='*50}")
        lines.append(f"날짜: {e.date_str}")
        if e.mood:
            lines.append(f"기분: {e.mood}")
        lines.append(f"제목: {e.title or '무제'}")
        if e.event:
            lines.append(f"이벤트: {e.event}")
        lines.append(f"{'─'*50}")
        lines.append(e.content or '')
        lines.append('')
    text = '\n'.join(lines)
    resp = make_response(text)
    resp.headers['Content-Type'] = 'text/plain; charset=utf-8'
    resp.headers['Content-Disposition'] = 'attachment; filename=diary.txt'
    return resp


@app.route("/diary/export")
@login_required
def export_diary_page():
    entries = Diary.query.filter_by(user_id=current_user.id).filter(Diary.deleted != True).order_by(Diary.date_str.desc()).all()
    return render_template("diary_print.html", entries=entries, user=current_user, cache_bust=cache_bust())


# ── Memo Folder API ───────────────────────────────────────

@app.route("/api/memo-folders")
@login_required
def get_memo_folders():
    folders = MemoFolder.query.filter_by(user_id=current_user.id).order_by(MemoFolder.order).all()
    return jsonify([f.to_dict() for f in folders])


@app.route("/api/memo-folders", methods=["POST"])
@login_required
def add_memo_folder():
    data = request.json
    folder = MemoFolder(user_id=current_user.id, name=data.get("name", "새 폴더"))
    db.session.add(folder)
    db.session.commit()
    return jsonify(folder.to_dict()), 201


@app.route("/api/memo-folders/<int:fid>", methods=["PUT"])
@login_required
def update_memo_folder(fid):
    folder = MemoFolder.query.filter_by(id=fid, user_id=current_user.id).first_or_404()
    data = request.json
    if "name" in data:
        folder.name = data["name"]
    db.session.commit()
    return jsonify(folder.to_dict())


@app.route("/api/memo-folders/<int:fid>", methods=["DELETE"])
@login_required
def delete_memo_folder(fid):
    folder = MemoFolder.query.filter_by(id=fid, user_id=current_user.id).first_or_404()
    # 폴더 안 메모들은 폴더 없음으로 이동
    FreeMemo.query.filter_by(folder_id=fid, user_id=current_user.id).update({"folder_id": None})
    db.session.delete(folder)
    db.session.commit()
    return jsonify({"ok": True})


# ── Free Memo API ─────────────────────────────────────────

@app.route("/api/free-memos")
@login_required
def get_free_memos():
    folder_id = request.args.get("folder_id", type=int)
    q = FreeMemo.query.filter_by(user_id=current_user.id)
    if folder_id is not None:
        if folder_id == 0:
            q = q.filter(FreeMemo.folder_id.is_(None))
        else:
            q = q.filter_by(folder_id=folder_id)
    memos = q.order_by(FreeMemo.updated_at.desc()).all()
    return jsonify([m.to_dict() for m in memos])


@app.route("/api/free-memos", methods=["POST"])
@login_required
def add_free_memo():
    data = request.json
    memo = FreeMemo(
        user_id=current_user.id,
        folder_id=data.get("folder_id"),
        title=data.get("title", "").strip() or "제목 없음",
        content=data.get("content", ""),
    )
    db.session.add(memo)
    db.session.commit()
    return jsonify(memo.to_dict()), 201


@app.route("/api/free-memos/<int:memo_id>", methods=["PUT"])
@login_required
def update_free_memo(memo_id):
    memo = FreeMemo.query.filter_by(id=memo_id, user_id=current_user.id).first_or_404()
    data = request.json
    if "title" in data:
        memo.title = data["title"]
    if "content" in data:
        memo.content = data["content"]
    if "folder_id" in data:
        memo.folder_id = data["folder_id"]
    memo.updated_at = datetime.now()
    db.session.commit()
    return jsonify(memo.to_dict())


@app.route("/api/free-memos/<int:memo_id>", methods=["DELETE"])
@login_required
def delete_free_memo(memo_id):
    memo = FreeMemo.query.filter_by(id=memo_id, user_id=current_user.id).first_or_404()
    db.session.delete(memo)
    db.session.commit()
    return jsonify({"ok": True})


# ── 백업 API ─────────────────────────────────────────────

@app.route("/api/backup")
@login_required
def backup_data():
    data = {
        "exported_at": datetime.now().isoformat(),
        "user": {"id": current_user.id, "email": current_user.email, "name": current_user.name},
        "todos": [t.to_dict() for t in Todo.query.filter_by(user_id=current_user.id).all()],
        "habits": [h.to_dict() for h in Habit.query.filter_by(user_id=current_user.id).all()],
        "memos": [{"date_str": m.date_str, "text": m.text} for m in Memo.query.filter_by(user_id=current_user.id).all()],
        "diaries": [d.to_dict() for d in Diary.query.filter_by(user_id=current_user.id).all()],
        "buckets": [b.to_dict() for b in BucketItem.query.filter_by(user_id=current_user.id).all()],
        "free_memos": [m.to_dict() for m in FreeMemo.query.filter_by(user_id=current_user.id).all()],
        "memo_folders": [f.to_dict() for f in MemoFolder.query.filter_by(user_id=current_user.id).all()],
        "sticky_notes": [n.to_dict() for n in StickyNote.query.filter_by(user_id=current_user.id).all()],
        "finance_records": [r.to_dict() for r in FinanceRecord.query.filter_by(user_id=current_user.id).all()],
        "fixed_expenses": [f.to_dict() for f in FixedExpense.query.filter_by(user_id=current_user.id).all()],
        "loans": [l.to_dict() for l in Loan.query.filter_by(user_id=current_user.id).all()],
    }
    resp = make_response(json.dumps(data, ensure_ascii=False, indent=2))
    resp.headers['Content-Type'] = 'application/json; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename=todo-matrix-backup-{datetime.now().strftime("%Y%m%d")}.json'
    return resp


# ── Pay Account API ───────────────────────────────────────

@app.route("/api/pay-accounts")
@login_required
def get_pay_accounts():
    items = PayAccount.query.filter_by(user_id=current_user.id).all()
    return jsonify([i.to_dict() for i in items])


@app.route("/api/pay-accounts", methods=["POST"])
@login_required
def add_pay_account():
    name = request.json.get("name", "").strip()
    if not name:
        return jsonify({"error": "이름 필요"}), 400
    item = PayAccount(user_id=current_user.id, name=name)
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@app.route("/api/pay-accounts/<int:pid>", methods=["DELETE"])
@login_required
def delete_pay_account(pid):
    item = PayAccount.query.filter_by(id=pid, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


# ── Finance Balance API ───────────────────────────────────

@app.route("/api/finance/start-balance")
@login_required
def get_start_balance():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    key = f"__fin_balance_{year}_{month}__"
    memo = Memo.query.filter_by(user_id=current_user.id, date_str=key).first()
    return jsonify({"amount": int(memo.text) if memo and memo.text else 0})


@app.route("/api/finance/start-balance", methods=["PUT"])
@login_required
def set_start_balance():
    data = request.json
    year = data.get("year")
    month = data.get("month")
    amount = data.get("amount", 0)
    key = f"__fin_balance_{year}_{month}__"
    memo = Memo.query.filter_by(user_id=current_user.id, date_str=key).first()
    if memo:
        memo.text = str(amount)
    else:
        memo = Memo(user_id=current_user.id, date_str=key, text=str(amount))
        db.session.add(memo)
    db.session.commit()
    return jsonify({"ok": True})


# ── Finance API ──────────────────────────────────────────

@app.route("/api/finance")
@login_required
def get_finance():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    q = FinanceRecord.query.filter_by(user_id=current_user.id)
    if year and month:
        prefix = f"{year}-{str(month).zfill(2)}"
        q = q.filter(FinanceRecord.date_str.like(f"{prefix}%"))
    records = q.order_by(FinanceRecord.date_str.desc(), FinanceRecord.id.desc()).all()
    return jsonify([r.to_dict() for r in records])


@app.route("/api/finance/summary")
@login_required
def get_finance_summary():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    prefix = f"{year}-{str(month).zfill(2)}" if year and month else ""
    q = FinanceRecord.query.filter_by(user_id=current_user.id)
    if prefix:
        q = q.filter(FinanceRecord.date_str.like(f"{prefix}%"))
    records = q.all()
    income = sum(r.amount for r in records if r.record_type == 'income')
    expense = sum(r.amount for r in records if r.record_type == 'expense')
    cats = {}
    for r in records:
        if r.record_type == 'expense':
            cats[r.category] = cats.get(r.category, 0) + r.amount
    return jsonify({"income": income, "expense": expense, "balance": income - expense, "categories": cats})


@app.route("/api/finance", methods=["POST"])
@login_required
def create_finance():
    data = request.json
    record = FinanceRecord(
        user_id=current_user.id, date_str=data["date_str"],
        record_type=data["record_type"], category=data["category"],
        amount=data["amount"], description=data.get("description", ""),
    )
    db.session.add(record)
    db.session.commit()
    return jsonify(record.to_dict()), 201


@app.route("/api/finance/<int:rid>", methods=["PUT"])
@login_required
def update_finance(rid):
    r = FinanceRecord.query.filter_by(id=rid, user_id=current_user.id).first_or_404()
    data = request.json
    for k in ["date_str", "record_type", "category", "amount", "description"]:
        if k in data:
            setattr(r, k, data[k])
    db.session.commit()
    return jsonify(r.to_dict())


@app.route("/api/finance/<int:rid>", methods=["DELETE"])
@login_required
def delete_finance(rid):
    r = FinanceRecord.query.filter_by(id=rid, user_id=current_user.id).first_or_404()
    db.session.delete(r)
    db.session.commit()
    return jsonify({"ok": True})


# ── Fixed Expense API ────────────────────────────────────

@app.route("/api/finance/fixed")
@login_required
def get_fixed():
    items = FixedExpense.query.filter_by(user_id=current_user.id).all()
    return jsonify([i.to_dict() for i in items])


@app.route("/api/finance/fixed", methods=["POST"])
@login_required
def create_fixed():
    data = request.json
    item = FixedExpense(user_id=current_user.id, name=data["name"], amount=data["amount"],
                        category=data.get("category", "기타"), day_of_month=data.get("day_of_month", 1),
                        pay_method=data.get("pay_method", ""), note=data.get("note", ""))
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@app.route("/api/finance/fixed/<int:fid>", methods=["PUT"])
@login_required
def update_fixed(fid):
    item = FixedExpense.query.filter_by(id=fid, user_id=current_user.id).first_or_404()
    data = request.json
    for k in ["name", "amount", "category", "day_of_month", "is_active", "pay_method", "note"]:
        if k in data:
            setattr(item, k, data[k])
    db.session.commit()
    return jsonify(item.to_dict())


@app.route("/api/finance/fixed/<int:fid>", methods=["DELETE"])
@login_required
def delete_fixed(fid):
    item = FixedExpense.query.filter_by(id=fid, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


# ── Loan API ─────────────────────────────────────────────

@app.route("/api/finance/loans")
@login_required
def get_loans():
    items = Loan.query.filter_by(user_id=current_user.id).all()
    return jsonify([i.to_dict() for i in items])


@app.route("/api/finance/loans", methods=["POST"])
@login_required
def create_loan():
    data = request.json
    item = Loan(user_id=current_user.id, name=data["name"],
                bank=data.get("bank", ""), remaining_amount=data.get("remaining_amount", 0),
                interest_rate=data.get("interest_rate", 0), due_date=data.get("due_date", ""),
                repay_type=data.get("repay_type", ""), prepay_fee=data.get("prepay_fee", ""),
                monthly_interest=data.get("monthly_interest", 0), account=data.get("account", ""),
                pay_day=data.get("pay_day", 0))
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@app.route("/api/finance/loans/<int:lid>", methods=["PUT"])
@login_required
def update_loan(lid):
    item = Loan.query.filter_by(id=lid, user_id=current_user.id).first_or_404()
    data = request.json
    for k in ["name", "bank", "remaining_amount", "interest_rate", "due_date", "repay_type", "prepay_fee", "monthly_interest", "account", "pay_day"]:
        if k in data:
            setattr(item, k, data[k])
    db.session.commit()
    return jsonify(item.to_dict())


@app.route("/api/finance/loans/<int:lid>", methods=["DELETE"])
@login_required
def delete_loan(lid):
    item = Loan.query.filter_by(id=lid, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


# ── 헬퍼 ─────────────────────────────────────────────────

def _matches_repeat(todo, date_str):
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return True
    weekdays = json.loads(todo.repeat_weekdays or "[]")
    days = json.loads(todo.repeat_days or "[]")
    if not weekdays and not days:
        return True
    if weekdays and d.weekday() in weekdays:
        return True
    if days and d.day in days:
        return True
    return False


# ── 앱 실행 ──────────────────────────────────────────────

with app.app_context():
    try:
        db.create_all()
        # Loan 테이블에 새 컬럼 추가
        _new_loan_cols = [
            ("bank", "VARCHAR(200) DEFAULT ''"),
            ("due_date", "VARCHAR(10) DEFAULT ''"),
            ("repay_type", "VARCHAR(50) DEFAULT ''"),
            ("prepay_fee", "VARCHAR(300) DEFAULT ''"),
            ("monthly_interest", "INTEGER DEFAULT 0"),
            ("account", "VARCHAR(200) DEFAULT ''"),
            ("pay_day", "INTEGER DEFAULT 0"),
        ]
        for col_name, col_type in _new_loan_cols:
            try:
                db.session.execute(db.text(f"ALTER TABLE loan ADD COLUMN {col_name} {col_type}"))
                db.session.commit()
            except Exception:
                db.session.rollback()
        # FixedExpense 테이블에 새 컬럼 추가
        _new_fixed_cols = [
            ("pay_method", "VARCHAR(200) DEFAULT ''"),
            ("note", "VARCHAR(500) DEFAULT ''"),
        ]
        for col_name, col_type in _new_fixed_cols:
            try:
                db.session.execute(db.text(f"ALTER TABLE fixed_expense ADD COLUMN {col_name} {col_type}"))
                db.session.commit()
            except Exception:
                db.session.rollback()
        print("DB tables created successfully")
    except Exception as e:
        print(f"DB create_all error: {e}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
