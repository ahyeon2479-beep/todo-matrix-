import os
import json
import time
from datetime import datetime, date

from flask import Flask, render_template, redirect, url_for, request, jsonify, session, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

from models_db import db, User, Todo, Memo, Habit, HabitCheck, BucketItem, Diary, FreeMemo, StickyNote
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
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True, "connect_args": {}}

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

@app.route("/diary/download/txt", methods=["POST"])
@login_required
def download_diary_txt():
    ids = request.json.get("ids", [])
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


# ── Free Memo API ─────────────────────────────────────────

@app.route("/api/free-memos")
@login_required
def get_free_memos():
    memos = FreeMemo.query.filter_by(user_id=current_user.id).order_by(FreeMemo.updated_at.desc()).all()
    return jsonify([m.to_dict() for m in memos])


@app.route("/api/free-memos", methods=["POST"])
@login_required
def add_free_memo():
    data = request.json
    memo = FreeMemo(
        user_id=current_user.id,
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
        # 기존 diary 테이블에 event 컬럼이 없으면 추가
        try:
            from sqlalchemy import inspect
            insp = inspect(db.engine)
            cols = [c['name'] for c in insp.get_columns('diary')]
            if 'event' not in cols:
                db.session.execute(db.text("ALTER TABLE diary ADD COLUMN event TEXT DEFAULT ''"))
                db.session.commit()
            if 'deleted' not in cols:
                try:
                    db.session.execute(db.text("ALTER TABLE diary ADD COLUMN deleted BOOLEAN DEFAULT false"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                try:
                    db.session.execute(db.text("ALTER TABLE diary ADD COLUMN deleted_at TIMESTAMP"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
        except Exception:
            db.session.rollback()
        # unique constraint 제거 (같은 날짜에 여러 일기 허용)
        try:
            db.session.execute(db.text("ALTER TABLE diary DROP CONSTRAINT IF EXISTS diary_user_id_date_str_key"))
            db.session.commit()
        except Exception:
            db.session.rollback()
        print("DB tables created successfully")
    except Exception as e:
        print(f"DB create_all error: {e}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
