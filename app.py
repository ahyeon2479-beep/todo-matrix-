import os
import json
from datetime import datetime, date

from flask import Flask, render_template, redirect, url_for, request, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

from models_db import db, User, Todo, Memo, Habit, HabitCheck
from holidays_kr import HOLIDAYS_KR

from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///todos.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

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
        return render_template("index.html", user=current_user)
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
    db.create_all()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
