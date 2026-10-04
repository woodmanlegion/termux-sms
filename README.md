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
| `termux-sms-send` | The message manager's send entrypoint — logs outbound, then sends |
| `termux-sms` | Unified status/handler-management/send CLI |

## Two directories, two purposes

- `~/.config/termux-sms/` — things *you* edit: `config` (your number, MMSC
  settings, ...) and `handlers.d/` (scripts you register).
- `~/.termux-sms/` — things the *package* generates: `state.json` (poll
  high-water marks), `messages.jsonl` (the message log, both directions),
  `media/inbound/` (saved MMS parts).

## The message manager: one poller, one log, pluggable handlers

`_termux_sms_lib.py` is the actual message-manager module — the one
place that knows how to record a message and how to load/save poll
state. Both directions go through it:

- **Inbound**: `termux-sms-poll` is the **only** thing that should ever
  poll this SIM's inbox. It runs under `sv` on an interval, and for every
  genuinely new message, calls `log_message("inbound", ...)` then fans
  out to every executable in `~/.config/termux-sms/handlers.d/` (message
  as JSON on stdin, `sms`/`mms` as `argv[1]`). A handler that exits
  non-zero is logged and skipped — it never blocks another handler or
  blocks state advancement.
- **Outbound**: `termux-sms-send <sms|mms> <to> <body-or-file>` calls the
  real `sms-send`/`mms-http-send`, then calls `log_message("outbound",
  ...)` with the result — success or failure, always logged. `termux-sms
  send`/`termux-sms send-mms` route through this; the raw `sms-send`/
  `mms-send` bins still work completely standalone with no logging, for
  direct scripting use.

Both directions land in the same `~/.termux-sms/messages.jsonl`, each
entry stamped with `direction: inbound|outbound`.

Looking forward: `termux-sms-channel` (the openclaw plugin, still
separate, not yet rewired) should call `send_sms`/`send_mms` from the
shared lib directly instead of invoking the raw CLI tools itself — even
as a pure pass-through, that keeps logging in exactly one place instead
of being duplicated per-consumer.

```bash
termux-sms handlers add ~/my-scripts/notify-slack.sh
termux-sms handlers list
termux-sms handlers remove notify-slack.sh
termux-sms send +15551234567 "hello"       # logged
termux-sms send-mms +15551234567 photo.jpg  # logged
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
