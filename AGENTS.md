# AGENTS.md — hard rules for this repo

1. **This repo has no openclaw dependency, ever.** Not in `bin/`, not in
   `install.sh`, not in a config default. If a change needs `~/.openclaw/...`
   to exist, it belongs in `termux-sms-channel` (the openclaw plugin that
   depends on this package), not here.
2. **`termux-sms-poll` is the only poller.** Never add a second polling
   loop anywhere in this repo or suggest one in docs — new consumers are
   handlers in `handlers.d/`, not new pollers. This is the whole point of
   consolidating four repos into one.
3. **A handler that fails must never block another handler or block
   state advancement.** Log it (stderr) and move on. Verified by a real
   test in this repo's history — don't regress it.
4. **One shared config file** (`~/.config/termux-sms/config`), not one
   per command. If a new command needs a new field, add it there and
   document it in both `config.example` and the README's config table.
5. **Receiving never requires `FROM_NUMBER`.** Only sending does. Don't
   add a check that blocks `sms-receive`/`mms-receive`/the poller on
   config completeness.
6. **Root is required for MMS and the rate-limit bypass, not for SMS
   send/receive.** Keep that distinction accurate in any new code or docs
   — don't add a blanket "requires root" anywhere.
7. **Prefer `svbase-health`'s safe-write primitives when present**
   (`svbase_write_run_script`, `svbase_register`) over a raw `cat > run`.
   Fall back to a plain write with a visible warning if `svbase-health`
   isn't installed — never fail silently either way.
