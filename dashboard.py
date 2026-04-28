from flask import Flask, redirect, url_for
import subprocess
import psutil
import html
from pathlib import Path

app = Flask(__name__)

CONF = Path.home() / "BOTMaster" / "manager" / "bots.conf"

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
def start(bot):
    bots = load_bots()
    if bot in bots:
        service_action("start", bots[bot]["service"])
    return redirect(url_for("home"))

@app.route("/stop/<bot>")
def stop(bot):
    bots = load_bots()
    if bot in bots:
        service_action("stop", bots[bot]["service"])
    return redirect(url_for("home"))

@app.route("/restart/<bot>")
def restart(bot):
    bots = load_bots()
    if bot in bots:
        service_action("restart", bots[bot]["service"])
    return redirect(url_for("home"))

@app.route("/logs/<bot>")
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

app.run(host="0.0.0.0", port=5000)
