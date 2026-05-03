from flask import Flask, redirect, url_for, request, session
import subprocess
import os
import hmac
import base64
import hashlib
from functools import wraps
import psutil
import html
from pathlib import Path

app = Flask(__name__)
app.secret_key = os.environ.get("BOTCONTROL_SECRET_KEY")

CONF = Path.home() / "BOTMaster" / "manager" / "bots.conf"

def verify_password_hash(password, stored_hash):
    try:
        algo, iterations, salt_b64, digest_b64 = stored_hash.split("$", 3)

        if algo != "pbkdf2_sha256":
            return False

        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt,
            int(iterations)
        )

        return hmac.compare_digest(actual, expected)
    except Exception:
        return False

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("botcontrol_logged_in"):
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper

@app.route("/login", methods=["GET", "POST"])
def login():
    if not app.secret_key:
        return "BOTCONTROL_SECRET_KEY fehlt", 500

    expected_user = os.environ.get("BOTCONTROL_USER", "sven")
    expected_hash = os.environ.get("BOTCONTROL_PASSWORD_HASH", "")

    error = ""

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if username == expected_user and verify_password_hash(password, expected_hash):
            session["botcontrol_logged_in"] = True
            return redirect(url_for("home"))

        error = "Login fehlgeschlagen"

    return f'''
    <!doctype html>
    <html>
    <head>
        <title>BOTControl Login</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                margin: 0;
                min-height: 100vh;
                display: grid;
                place-items: center;
                font-family: Arial, sans-serif;
                background: linear-gradient(180deg, #020617 0%, #0f172a 100%);
                color: white;
            }}
            .box {{
                width: min(420px, calc(100vw - 32px));
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 24px;
                padding: 28px;
                box-shadow: 0 18px 40px rgba(0,0,0,.35);
            }}
            h1 {{
                margin: 0 0 20px;
                font-size: 30px;
            }}
            label {{
                display: block;
                margin-top: 14px;
                color: #cbd5e1;
                font-weight: 700;
            }}
            input {{
                width: 100%;
                margin-top: 7px;
                padding: 13px;
                border-radius: 12px;
                border: 1px solid #475569;
                background: #020617;
                color: white;
                font-size: 16px;
            }}
            button {{
                width: 100%;
                margin-top: 22px;
                padding: 14px;
                border: 0;
                border-radius: 13px;
                background: #2563eb;
                color: white;
                font-size: 16px;
                font-weight: 900;
                cursor: pointer;
            }}
            .error {{
                margin-top: 14px;
                color: #f87171;
                font-weight: 800;
            }}
            .hint {{
                margin-top: 16px;
                color: #64748b;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <form class="box" method="post">
            <h1>BOTControl Login 🔐</h1>

            <label>Benutzer</label>
            <input name="username" autocomplete="username" autofocus>

            <label>Passwort</label>
            <input name="password" type="password" autocomplete="current-password">

            <button type="submit">Einloggen</button>

            <div class="error">{html.escape(error)}</div>
            <div class="hint">BOTMaster Control ist geschützt.</div>
        </form>
    </body>
    </html>
    '''

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def run_cmd(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def load_bots():
    bots = {}

    if not CONF.exists():
        return bots

    for line in CONF.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        parts = [p.strip() for p in line.split(":")]

        if len(parts) != 3:
            continue

        key, label, service = parts

        if not key or not label or not service:
            continue

        bots[key] = {
            "label": label,
            "service": service
        }

    return bots

def service_exists(service):
    result = run_cmd(["systemctl", "--user", "status", service])
    text = (result.stdout + result.stderr).lower()

    if "could not be found" in text or "not found" in text:
        return False

    return True

def service_status(service):
    if not service_exists(service):
        return "not-found"

    result = run_cmd(["systemctl", "--user", "is-active", service])
    status = result.stdout.strip()

    if not status:
        return "unknown"

    return status

def service_uptime(service):
    result = run_cmd([
        "systemctl", "--user", "show", service,
        "--property=ActiveEnterTimestamp",
        "--value"
    ])
    value = result.stdout.strip()
    return value if value else "—"

def service_action(action, service):
    if service_exists(service):
        subprocess.run(["systemctl", "--user", action, service])

def status_style(status):
    if status == "active":
        return "🟢", "#22c55e", "ONLINE"
    if status == "inactive":
        return "🔴", "#ef4444", "OFFLINE"
    if status == "failed":
        return "🟣", "#a855f7", "FAILED"
    if status == "not-found":
        return "🟡", "#eab308", "SERVICE FEHLT"
    return "⚪", "#94a3b8", status.upper()

@app.route("/")
@login_required
def home():
    bots = load_bots()

    cpu = psutil.cpu_percent(interval=0.3)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent

    cards = ""

    for key, data in bots.items():
        label = html.escape(data["label"])
        service = html.escape(data["service"])
        raw_service = data["service"]

        status = service_status(raw_service)
        icon, color, label_status = status_style(status)
        uptime = html.escape(service_uptime(raw_service)) if status == "active" else "—"

        cards += f"""
        <div class="card">
            <h2>{icon} {label}</h2>

            <div class="meta">
                <div>Service</div>
                <code>{service}</code>
            </div>

            <div class="meta">
                <div>Status</div>
                <strong style="color:{color};">{label_status}</strong>
            </div>

            <div class="meta">
                <div>Aktiv seit</div>
                <span>{uptime}</span>
            </div>

            <div class="buttons">
                <a href="/start/{html.escape(key)}">START</a>
                <a class="danger" href="/stop/{html.escape(key)}">STOP</a>
                <a href="/restart/{html.escape(key)}">RESTART</a>
                <a class="log" href="/logs/{html.escape(key)}">LOGS</a>
            </div>
        </div>
        """

    if not cards:
        cards = """
        <div class="card">
            <h2>⚠️ Keine Bots gefunden</h2>
            <p>Prüfe ~/BOTMaster/manager/bots.conf</p>
        </div>
        """

    return f"""
    <!doctype html>
    <html>
    <head>
        <title>BOTMaster V4</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta http-equiv="refresh" content="10">
        <style>
            * {{
                box-sizing: border-box;
            }}
            body {{
                margin: 0;
                font-family: Arial, sans-serif;
                background: linear-gradient(180deg, #020617 0%, #0f172a 100%);
                color: white;
            }}
            header {{
                padding: 32px 18px 24px;
                background: #020617;
                text-align: center;
                border-bottom: 1px solid #334155;
            }}
            h1 {{
                margin: 0;
                font-size: 34px;
                line-height: 1.1;
            }}
            .stats {{
                margin-top: 14px;
                font-size: 17px;
                color: #cbd5e1;
            }}
            .grid {{
                display: grid;
                gap: 18px;
                padding: 18px;
                max-width: 900px;
                margin: 0 auto;
            }}
            .card {{
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 24px;
                padding: 22px;
                box-shadow: 0 18px 40px rgba(0,0,0,.35);
            }}
            h2 {{
                margin: 0 0 18px;
                font-size: 28px;
            }}
            .meta {{
                margin: 12px 0;
                display: grid;
                grid-template-columns: 110px 1fr;
                gap: 10px;
                align-items: center;
                color: #cbd5e1;
            }}
            code {{
                color: #93c5fd;
                word-break: break-all;
            }}
            .buttons {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 18px;
            }}
            a {{
                display: inline-block;
                padding: 13px 16px;
                background: #2563eb;
                color: white;
                text-decoration: none;
                border-radius: 13px;
                font-weight: 800;
                letter-spacing: .3px;
            }}
            a.danger {{
                background: #dc2626;
            }}
            a.log {{
                background: #16a34a;
            }}
            .footer {{
                text-align: center;
                padding: 22px;
                color: #64748b;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <header>
            <h1>BOTMaster HQ V4 😎</h1>
            <div class="stats">
                CPU: {cpu}% | RAM: {ram}% | DISK: {disk}%
            </div>
            <div style="margin-top:14px;">
                <a style="background:#334155;padding:9px 13px;border-radius:10px;font-size:13px;" href="/logout">Logout</a>
            </div>
        </header>

        <main class="grid">
            {cards}
        </main>

        <div class="footer">
            Auto-Refresh alle 10 Sekunden
        </div>
    </body>
    </html>
    """

@app.route("/start/<bot>")
@login_required
def start(bot):
    bots = load_bots()
    if bot in bots:
        service_action("start", bots[bot]["service"])
    return redirect(url_for("home"))

@app.route("/stop/<bot>")
@login_required
def stop(bot):
    bots = load_bots()
    if bot in bots:
        service_action("stop", bots[bot]["service"])
    return redirect(url_for("home"))

@app.route("/restart/<bot>")
@login_required
def restart(bot):
    bots = load_bots()
    if bot in bots:
        service_action("restart", bots[bot]["service"])
    return redirect(url_for("home"))

@app.route("/logs/<bot>")
@login_required
def logs(bot):
    bots = load_bots()

    if bot not in bots:
        return "Bot nicht gefunden"

    service = bots[bot]["service"]

    if not service_exists(service):
        return f"""
        <body style="background:#020617;color:white;font-family:Arial;padding:20px;">
            <h2>🟡 Service fehlt</h2>
            <p>{html.escape(service)} existiert noch nicht.</p>
            <p><a style="color:white;" href="/">Zurück</a></p>
        </body>
        """

    result = run_cmd([
        "journalctl", "--user", "-u", service,
        "-n", "100", "--no-pager"
    ])

    output = html.escape(result.stdout if result.stdout else "Keine Logs vorhanden.")

    return f"""
    <!doctype html>
    <html>
    <head>
        <title>Logs</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta http-equiv="refresh" content="5">
    </head>
    <body style="background:#020617;color:#22c55e;font-family:monospace;padding:16px;">
        <h2>Logs: {html.escape(service)}</h2>
        <p><a style="color:white;" href="/">⬅ Zurück</a></p>
        <pre style="white-space:pre-wrap;">{output}</pre>
    </body>
    </html>
    """

app.run(host="127.0.0.1", port=5000)
