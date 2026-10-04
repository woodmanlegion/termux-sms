# termux-sms

A standalone SMS/MMS send-and-receive package for Android/Termux. Not an
openclaw skill or plugin — no openclaw dependency anywhere in this repo.
Anything can use it: an openclaw channel, a cron job, pi-agent, a plain
shell script, you by hand.

## Why this exists

Consolidated from four previously-separate repos (`skill-sms-send`,
`skill-mms-send`, `skill-mms-receive`, `sms-limit-apply`) plus a new
`sms-receive` that never existed before — inbound SMS used to only be
polled inline inside the `termux-sms-channel` openclaw plugin itself,
never a first-class capability. Being four tiny repos was a sign of how
it was developed (one capability, one repo, each time), not a sign that
they're actually independent — they all share one SIM, one phone number,
and one config.

## What's in it

| Command | Does |
|---|---|
| `sms-send <phone> <msg>` | Send SMS, with rate-limit-bypass preflight |
| `sms-receive` | Query inbound SMS, `--since`/`--oldest-first` for polling |
| `mms-receive` | Query inbound MMS via the telephony content provider (needs root) |
| `mms-send` / `mms-http-send` | Send MMS via headless MMSC POST |
| `mms-send-auto` / `mms-send-smart` | Higher-level MMS send wrappers |
| `mms-fetch` / `mms-check` / `mms-calibrate` | MMS send support tooling |
| `termux-sms-poll` | One poll pass — checks both SMS and MMS, advances state, fans out to handlers |
| `termux-sms` | Unified status/handler-management CLI |

## The poller: one reader, pluggable handlers

`termux-sms-poll` is the **only** thing that should ever poll this SIM's
inbox. It runs under `sv` (installed by `install.sh`) on an interval,
advances one shared high-water-mark state file
(`~/.config/termux-sms/state.json`), and for every genuinely new message:

1. Appends it to `~/.config/termux-sms/inbox.jsonl` (a plain append-only log).
2. Runs every executable in `~/.config/termux-sms/handlers.d/` once, with
   the message as JSON on stdin and `sms` or `mms` as `argv[1]`.

This is the extension point for "multiple things want to react to the
same inbound message" (an openclaw channel, a contact-specific
auto-responder, whatever else) — they each become one handler script,
not a second independent poller. A handler that exits non-zero is logged
and skipped; it never blocks the other handlers or blocks state
advancement.

```bash
termux-sms handlers add ~/my-scripts/notify-slack.sh
termux-sms handlers list
termux-sms handlers remove notify-slack.sh
```

## Install

```bash
bash install.sh
cp config.example ~/.config/termux-sms/config
# edit ~/.config/termux-sms/config, set FROM_NUMBER
```

Receiving works with zero config (no `FROM_NUMBER` needed to read inbound
messages). Sending needs `FROM_NUMBER` set.

If [`svbase-health`](https://github.com/woodmanlegion/svbase-health) is
already installed on the device, `install.sh` registers the poller
through it (safe run-script writes, flap detection, `svbase-doctor
status`). If not, it falls back to a plain `sv` service definition with a
warning — still works, just without that protection.

## Config

One file, `~/.config/termux-sms/config`, all fields documented in
`config.example`. `FROM_NUMBER` is shared between `sms-send` and
`mms-http-send` since they're the same SIM.

## Standalone use cases

Nothing here requires a gateway, an agent, or any particular framework —
just Termux, root (for MMS and the rate-limit bypass; SMS send/receive
alone doesn't need it), and a SIM. Use the individual bins directly for
scripting, or `termux-sms-poll` + handlers.d for anything that needs to
react to inbound messages continuously.
