"""
_termux_sms_lib — shared state/message-log functions for termux-sms.

This is the actual "message-manager" function: one place that knows how
to record a message (either direction) and how to load/save poll state.
termux-sms-poll uses it for inbound; the send entrypoints use it for
outbound. termux-sms-channel (the openclaw plugin, not yet rewired)
should eventually call into send_sms/send_mms here directly instead of
invoking sms-send/mms-http-send itself and duplicating the logging --
even as a pure pass-through, that keeps logging in exactly one place.

Not a CLI -- imported only. No openclaw dependency, same as the rest of
this package.
"""

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime, timezone

BIN_DIR    = Path(__file__).resolve().parent
CONFIG_DIR = Path(os.path.expanduser("~/.config/termux-sms"))   # user-edited: config, handlers.d
DATA_DIR   = Path(os.path.expanduser("~/.termux-sms"))          # package-generated: state, messages, media

CONFIG_FILE   = CONFIG_DIR / "config"
HANDLERS_DIR  = CONFIG_DIR / "handlers.d"
STATE_FILE    = DATA_DIR / "state.json"
MESSAGES_FILE = DATA_DIR / "messages.jsonl"


def _now():
    return datetime.now(timezone.utc).isoformat()


# ── Config ──────────────────────────────────────────────────────────────────

def load_config():
    cfg = {}
    try:
        for line in CONFIG_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            cfg[k.strip().lower()] = v.strip()
    except FileNotFoundError:
        pass
    return cfg


# ── State (poll high-water marks) ────────────────────────────────────────────

def load_state():
    """None means no state file yet -- caller must call init_fresh_state()
    rather than assume {-1, 0}. See termux-sms-poll's own history: a fresh
    install defaulting to 'the beginning of time' replayed years of real
    device history and, for MMS specifically, never finished in time to
    even save state, looping the same slow replay forever."""
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return None


def save_state(state):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


def init_fresh_state(run_json_fn):
    latest_sms = run_json_fn([str(BIN_DIR / "sms-receive"), "--limit", "1", "--json"])
    latest_mms = run_json_fn([str(BIN_DIR / "mms-receive"), "--limit", "1", "--no-save", "--json"])
    sms_hw = max((m["id"] for m in latest_sms), default=-1)
    mms_hw = max((m["id"] for m in latest_mms), default=0)
    return {"smsHighWater": sms_hw, "mmsHighWater": mms_hw}


# ── The message manager itself: one log, both directions ───────────────────

def log_message(direction, kind, record):
    """direction: 'inbound' | 'outbound'. kind: 'sms' | 'mms'.
    record: whatever fields are relevant (id/sender/body for inbound,
    to/body/status for outbound) -- this just stamps direction/kind/time
    and appends, it doesn't validate the shape beyond that."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"direction": direction, "kind": kind, "loggedAt": _now(), **record}
    with open(MESSAGES_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def send_sms(to, body, tag=None):
    """The message-manager's send entrypoint for SMS. Logs outbound
    before returning, success or failure, so sent messages are never
    silently un-recorded the way they were before this existed.

    tag: optional free-form string (e.g. "slash") a caller can attach
    to correlate this send with something it knows and the message
    manager doesn't -- omitted from the record entirely when absent,
    rather than logging a null field on every ordinary send."""
    try:
        result = subprocess.run(
            [str(BIN_DIR / "sms-send"), to, body, "--json"],
            capture_output=True, text=True, timeout=35,
        )
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except Exception as e:
        payload = {"status": "error", "error": str(e)}

    ok = payload.get("status") == "sent"
    record = {"to": to, "body": body,
              "status": "sent" if ok else "error",
              "error": payload.get("error")}
    if tag:
        record["tag"] = tag
    log_message("outbound", "sms", record)
    return ok, payload


def send_mms(to, file_path, tag=None):
    """The message-manager's send entrypoint for MMS. Same logging
    guarantee as send_sms, same optional tag."""
    try:
        result = subprocess.run(
            [str(BIN_DIR / "mms-send"), to, file_path, "--json"],
            capture_output=True, text=True, timeout=120,
        )
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except Exception as e:
        payload = {"status": "error", "error": str(e)}

    ok = payload.get("status") == "sent"
    record = {"to": to, "file": file_path,
              "status": "sent" if ok else "error",
              "error": payload.get("error")}
    if tag:
        record["tag"] = tag
    log_message("outbound", "mms", record)
    return ok, payload
