**Who wrote it** — People Ops commissioned it and a contractor built it; nobody on this team has read the source, and it runs as a subprocess of our host inside our trust boundary, not at arm's length.

**What it can reach** — Its own HRIS store today (grade band, accrued leave), but it inherits our process environment, so it can also read every variable we hold, `OPENAI_API_KEY` included, and open any outbound connection our machine can.

**What it logs** — Unknown, and that is the finding: we never see its stdout beyond the JSON-RPC frames, so employee ids we send may be written to a file or shipped off-box without appearing anywhere we look.

**What a stolen token could do** — Read grade band and leave balance for any id it can guess — a salary-adjacent field across the whole company, since ids are sequential (HR-1001, HR-1002, …) and there is no per-caller scoping beyond the two `HRIS_SCOPES` values.

**Ship or don't** — Ship for leave balance only, with `HRIS_SCOPES=hris:leave`, a scrubbed environment rather than our own, and its stdout captured; do not enable `hris:grade` until we have seen the source and know what it logs.
