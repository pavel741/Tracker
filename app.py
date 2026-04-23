import os, io, csv, json
from datetime import datetime, date, time

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, Response, send_file
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(32).hex())

db_dir = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(db_dir, "visitation.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"

# ── Models ────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    visits = db.relationship("Visit", backref="user", lazy=True, cascade="all,delete-orphan")
    incidents = db.relationship("Incident", backref="user", lazy=True, cascade="all,delete-orphan")
    schedule_rules = db.relationship("ScheduleRule", backref="user", lazy=True, cascade="all,delete-orphan")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5))
    actual_start_time = db.Column(db.String(5))
    actual_end_time = db.Column(db.String(5))
    type = db.Column(db.String(30), nullable=False)
    punctuality = db.Column(db.String(10), nullable=False)
    person = db.Column(db.String(120))
    witnesses = db.Column(db.String(250))
    location = db.Column(db.String(250))
    activities = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    incidents = db.relationship("Incident", backref="related_visit", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "start_time": self.start_time,
            "end_time": self.end_time or "",
            "actual_start_time": self.actual_start_time or "",
            "actual_end_time": self.actual_end_time or "",
            "type": self.type,
            "punctuality": self.punctuality,
            "person": self.person or "",
            "witnesses": self.witnesses or "",
            "location": self.location or "",
            "activities": self.activities or "",
            "notes": self.notes or "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }


class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    severity = db.Column(db.String(20), nullable=False)
    mood = db.Column(db.String(30))
    tone = db.Column(db.String(30))
    related_visit_id = db.Column(db.Integer, db.ForeignKey("visit.id"), nullable=True)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else "",
            "severity": self.severity,
            "mood": self.mood or "",
            "tone": self.tone or "",
            "related_visit_id": self.related_visit_id,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }


class ScheduleRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rule_type = db.Column(db.String(20), nullable=False)
    config_json = db.Column(db.Text, nullable=False)
    label = db.Column(db.String(120), nullable=False)

    @property
    def config(self):
        return json.loads(self.config_json)

    def to_dict(self):
        return {
            "id": self.id,
            "rule_type": self.rule_type,
            "config": self.config,
            "label": self.label,
        }


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


with app.app_context():
    db.create_all()
    with db.engine.connect() as conn:
        inc_cols = {r[1] for r in conn.execute(db.text("PRAGMA table_info(incident)"))}
        if "mood" not in inc_cols:
            conn.execute(db.text("ALTER TABLE incident ADD COLUMN mood VARCHAR(30)"))
        if "tone" not in inc_cols:
            conn.execute(db.text("ALTER TABLE incident ADD COLUMN tone VARCHAR(30)"))
        visit_cols = {r[1] for r in conn.execute(db.text("PRAGMA table_info(visit)"))}
        if "actual_start_time" not in visit_cols:
            conn.execute(db.text("ALTER TABLE visit ADD COLUMN actual_start_time VARCHAR(5)"))
        if "actual_end_time" not in visit_cols:
            conn.execute(db.text("ALTER TABLE visit ADD COLUMN actual_end_time VARCHAR(5)"))
        if "activities" not in visit_cols:
            conn.execute(db.text("ALTER TABLE visit ADD COLUMN activities TEXT"))
        conn.commit()

# ── Auth Routes ───────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            nxt = request.args.get("next")
            return redirect(nxt or url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if not username or not email or not password:
            flash("All fields are required.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        elif User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already taken.", "danger")
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user, remember=True)
            flash("Account created! Welcome.", "success")
            return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

# ── Dashboard ─────────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/dashboard")
@login_required
def api_dashboard():
    year = request.args.get("year", date.today().year, type=int)
    month = request.args.get("month", date.today().month, type=int)

    month_visits = Visit.query.filter(
        Visit.user_id == current_user.id,
        db.extract("year", Visit.date) == year,
        db.extract("month", Visit.date) == month,
    ).all()

    month_incidents = Incident.query.filter(
        Incident.user_id == current_user.id,
        db.extract("year", Incident.date) == year,
        db.extract("month", Incident.date) == month,
    ).all()

    rules = ScheduleRule.query.filter_by(user_id=current_user.id).all()

    recent = (
        Visit.query.filter_by(user_id=current_user.id)
        .order_by(Visit.date.desc(), Visit.start_time.desc())
        .limit(5)
        .all()
    )

    return jsonify({
        "visits": [v.to_dict() for v in month_visits],
        "incidents": [i.to_dict() for i in month_incidents],
        "rules": [r.to_dict() for r in rules],
        "recent": [v.to_dict() for v in recent],
    })

# ── Visit CRUD ────────────────────────────────────────────────────────

@app.route("/log")
@login_required
def log_page():
    return render_template("log.html")


@app.route("/api/visits")
@login_required
def api_visits():
    q = Visit.query.filter_by(user_id=current_user.id).order_by(Visit.date.desc(), Visit.start_time.desc())
    search = request.args.get("search", "").strip().lower()
    vtype = request.args.get("type", "").strip()
    if vtype:
        q = q.filter(Visit.type == vtype)
    visits = q.all()
    if search:
        visits = [
            v for v in visits
            if search in (v.person or "").lower()
            or search in (v.location or "").lower()
            or search in (v.activities or "").lower()
            or search in (v.notes or "").lower()
            or search in v.type.lower()
            or search in v.date.isoformat()
        ]
    return jsonify([v.to_dict() for v in visits])


@app.route("/api/visits", methods=["POST"])
@login_required
def api_create_visit():
    d = request.json
    v = Visit(
        user_id=current_user.id,
        date=date.fromisoformat(d["date"]),
        start_time=d["start_time"],
        end_time=d.get("end_time") or None,
        actual_start_time=d.get("actual_start_time") or None,
        actual_end_time=d.get("actual_end_time") or None,
        type=d["type"],
        punctuality=d["punctuality"],
        person=d.get("person"),
        witnesses=d.get("witnesses"),
        location=d.get("location"),
        activities=d.get("activities"),
        notes=d.get("notes"),
    )
    db.session.add(v)
    db.session.commit()
    return jsonify(v.to_dict()), 201


@app.route("/api/visits/<int:vid>", methods=["PUT"])
@login_required
def api_update_visit(vid):
    v = Visit.query.filter_by(id=vid, user_id=current_user.id).first_or_404()
    d = request.json
    v.date = date.fromisoformat(d["date"])
    v.start_time = d["start_time"]
    v.end_time = d.get("end_time") or None
    v.actual_start_time = d.get("actual_start_time") or None
    v.actual_end_time = d.get("actual_end_time") or None
    v.type = d["type"]
    v.punctuality = d["punctuality"]
    v.person = d.get("person")
    v.witnesses = d.get("witnesses")
    v.location = d.get("location")
    v.activities = d.get("activities")
    v.notes = d.get("notes")
    db.session.commit()
    return jsonify(v.to_dict())


@app.route("/api/visits/<int:vid>", methods=["DELETE"])
@login_required
def api_delete_visit(vid):
    v = Visit.query.filter_by(id=vid, user_id=current_user.id).first_or_404()
    db.session.delete(v)
    db.session.commit()
    return "", 204

# ── Incident CRUD ─────────────────────────────────────────────────────

@app.route("/incidents")
@login_required
def incidents_page():
    return render_template("incidents.html")


@app.route("/api/incidents")
@login_required
def api_incidents():
    items = (
        Incident.query.filter_by(user_id=current_user.id)
        .order_by(Incident.date.desc())
        .all()
    )
    return jsonify([i.to_dict() for i in items])


@app.route("/api/incidents", methods=["POST"])
@login_required
def api_create_incident():
    d = request.json
    items = d if isinstance(d, list) else [d]
    created = []
    for item in items:
        inc = Incident(
            user_id=current_user.id,
            date=datetime.fromisoformat(item["date"]),
            severity=item["severity"],
            mood=item.get("mood") or None,
            tone=item.get("tone") or None,
            related_visit_id=item.get("related_visit_id") or None,
            description=item["description"],
        )
        db.session.add(inc)
        created.append(inc)
    db.session.commit()
    if len(created) == 1:
        return jsonify(created[0].to_dict()), 201
    return jsonify([c.to_dict() for c in created]), 201


@app.route("/api/incidents/<int:iid>", methods=["PUT"])
@login_required
def api_update_incident(iid):
    inc = Incident.query.filter_by(id=iid, user_id=current_user.id).first_or_404()
    d = request.json
    inc.date = datetime.fromisoformat(d["date"])
    inc.severity = d["severity"]
    inc.mood = d.get("mood") or None
    inc.tone = d.get("tone") or None
    inc.related_visit_id = d.get("related_visit_id") or None
    inc.description = d["description"]
    db.session.commit()
    return jsonify(inc.to_dict())


@app.route("/api/incidents/<int:iid>", methods=["DELETE"])
@login_required
def api_delete_incident(iid):
    inc = Incident.query.filter_by(id=iid, user_id=current_user.id).first_or_404()
    db.session.delete(inc)
    db.session.commit()
    return "", 204

# ── Schedule CRUD ─────────────────────────────────────────────────────

@app.route("/schedule")
@login_required
def schedule_page():
    return render_template("schedule.html")


@app.route("/api/schedule")
@login_required
def api_schedule():
    rules = ScheduleRule.query.filter_by(user_id=current_user.id).all()
    return jsonify([r.to_dict() for r in rules])


@app.route("/api/schedule", methods=["POST"])
@login_required
def api_create_rule():
    d = request.json
    rule = ScheduleRule(
        user_id=current_user.id,
        rule_type=d["rule_type"],
        config_json=json.dumps(d["config"]),
        label=d["label"],
    )
    db.session.add(rule)
    db.session.commit()
    return jsonify(rule.to_dict()), 201


@app.route("/api/schedule/<int:rid>", methods=["PUT"])
@login_required
def api_update_rule(rid):
    rule = ScheduleRule.query.filter_by(id=rid, user_id=current_user.id).first_or_404()
    d = request.json
    rule.rule_type = d["rule_type"]
    rule.config_json = json.dumps(d["config"])
    rule.label = d["label"]
    db.session.commit()
    return jsonify(rule.to_dict())


@app.route("/api/schedule/<int:rid>", methods=["DELETE"])
@login_required
def api_delete_rule(rid):
    rule = ScheduleRule.query.filter_by(id=rid, user_id=current_user.id).first_or_404()
    db.session.delete(rule)
    db.session.commit()
    return "", 204

# ── Export ────────────────────────────────────────────────────────────

@app.route("/export")
@login_required
def export_page():
    return render_template("export.html")


@app.route("/api/export/csv")
@login_required
def api_export_csv():
    frm = request.args.get("from", "1900-01-01")
    to = request.args.get("to", "2999-12-31")
    dtype = request.args.get("type", "all")
    frm_d = date.fromisoformat(frm)
    to_d = date.fromisoformat(to)

    buf = io.StringIO()
    writer = csv.writer(buf)

    if dtype in ("visits", "all"):
        vlist = (
            Visit.query.filter(
                Visit.user_id == current_user.id,
                Visit.date >= frm_d,
                Visit.date <= to_d,
            )
            .order_by(Visit.date)
            .all()
        )
        writer.writerow(["VISITATION LOG"])
        writer.writerow(["Date", "Scheduled Start", "Scheduled End", "Actual Start", "Actual End", "Type", "Punctuality", "Person", "People Present", "Location", "Activities", "Notes"])
        for v in vlist:
            writer.writerow([v.date.isoformat(), v.start_time, v.end_time or "", v.actual_start_time or "", v.actual_end_time or "", v.type, v.punctuality, v.person or "", v.witnesses or "", v.location or "", v.activities or "", v.notes or ""])
        writer.writerow([])

    if dtype in ("incidents", "all"):
        ilist = (
            Incident.query.filter(
                Incident.user_id == current_user.id,
                Incident.date >= datetime.combine(frm_d, time.min),
                Incident.date <= datetime.combine(to_d, time.max),
            )
            .order_by(Incident.date)
            .all()
        )
        writer.writerow(["INCIDENT LOG"])
        writer.writerow(["Date", "Severity", "Mood", "Tone", "Description", "Related Visit Date"])
        for inc in ilist:
            rel = Visit.query.get(inc.related_visit_id) if inc.related_visit_id else None
            writer.writerow([inc.date.strftime("%Y-%m-%d %H:%M"), inc.severity, inc.mood or "", inc.tone or "", inc.description, rel.date.isoformat() if rel else ""])

    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=visitation-records.csv"},
    )


@app.route("/api/export/data")
@login_required
def api_export_data():
    """JSON endpoint used by client-side PDF generation."""
    frm = request.args.get("from", "1900-01-01")
    to = request.args.get("to", "2999-12-31")
    frm_d = date.fromisoformat(frm)
    to_d = date.fromisoformat(to)

    vlist = (
        Visit.query.filter(
            Visit.user_id == current_user.id,
            Visit.date >= frm_d,
            Visit.date <= to_d,
        )
        .order_by(Visit.date)
        .all()
    )
    ilist = (
        Incident.query.filter(
            Incident.user_id == current_user.id,
            Incident.date >= datetime.combine(frm_d, time.min),
            Incident.date <= datetime.combine(to_d, time.max),
        )
        .order_by(Incident.date)
        .all()
    )

    return jsonify({
        "visits": [v.to_dict() for v in vlist],
        "incidents": [i.to_dict() for i in ilist],
        "range": {"from": frm, "to": to},
    })


@app.route("/api/backup")
@login_required
def api_backup():
    vlist = Visit.query.filter_by(user_id=current_user.id).all()
    ilist = Incident.query.filter_by(user_id=current_user.id).all()
    rlist = ScheduleRule.query.filter_by(user_id=current_user.id).all()
    data = {
        "visits": [v.to_dict() for v in vlist],
        "incidents": [i.to_dict() for i in ilist],
        "schedule_rules": [r.to_dict() for r in rlist],
        "exported_at": datetime.utcnow().isoformat(),
    }
    buf = io.BytesIO(json.dumps(data, indent=2).encode())
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/json",
        as_attachment=True,
        download_name=f"visitation-backup-{date.today().isoformat()}.json",
    )


@app.route("/api/restore", methods=["POST"])
@login_required
def api_restore():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file provided"}), 400
    try:
        data = json.load(f)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    Visit.query.filter_by(user_id=current_user.id).delete()
    Incident.query.filter_by(user_id=current_user.id).delete()
    ScheduleRule.query.filter_by(user_id=current_user.id).delete()

    for vd in data.get("visits", []):
        v = Visit(
            user_id=current_user.id,
            date=date.fromisoformat(vd["date"]),
            start_time=vd["start_time"],
            end_time=vd.get("end_time") or None,
            actual_start_time=vd.get("actual_start_time") or None,
            actual_end_time=vd.get("actual_end_time") or None,
            type=vd["type"],
            punctuality=vd["punctuality"],
            person=vd.get("person"),
            witnesses=vd.get("witnesses"),
            location=vd.get("location"),
            activities=vd.get("activities"),
            notes=vd.get("notes"),
        )
        db.session.add(v)

    for ind in data.get("incidents", []):
        inc = Incident(
            user_id=current_user.id,
            date=datetime.fromisoformat(ind["date"]),
            severity=ind["severity"],
            mood=ind.get("mood") or None,
            tone=ind.get("tone") or None,
            description=ind["description"],
        )
        db.session.add(inc)

    for rd in data.get("schedule_rules", []):
        rule = ScheduleRule(
            user_id=current_user.id,
            rule_type=rd["rule_type"],
            config_json=json.dumps(rd["config"]),
            label=rd["label"],
        )
        db.session.add(rule)

    db.session.commit()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)
