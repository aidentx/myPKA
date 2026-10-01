#!/usr/bin/env python3
"""checkpoint.py: the deterministic half of a session checkpoint (WS-1005).

Answers, from the files alone, the questions a checkpoint asks:

  1. Which tasks moved this session?  Every task file changed since this
     session STARTED (`.mypka/state/session.json`), falling back
     to the last session log's own name where no session start hook ran,
     in all four states: Tasks/open/, Tasks/in-progress/,
     and the date-nested Tasks/done/YYYY/MM/ and Tasks/cancelled/YYYY/MM/.
     A task closed earlier in the same session lives in done/ by the time
     the checkpoint runs, and until 2026-09-07 it was invisible here (the
     report said `tasks touched : 0` for a session that shipped one;
     reported by Andrew Gillley from a 1.10.2 vault).
  2. Which work in WiP could leave?  Every piece of work in the wip concept (not
     _archive) whose newest file is older than --window days AND which no
     open or in-progress task mentions. Both facts are printed for every
     entry; the flag is only the intersection. The four buckets
     (the wip room's README.md, 2026-09-17) are never candidates themselves; the
     scan steps into them and reports the dated work inside, which inside
     a bucket is a folder OR a single .md file. Workstreams/<Name>/ is
     standing too, because a process has no finish line to leave against,
     so only its dated runs can be flagged; Projects/<name>/ is the unit
     that leaves, with its Project. A bucket's own README.md is never
     reported. Operations/ is reported first: it is the bucket nothing
     closes from the outside, so it is where work goes stale unnoticed.
  3. Is there a session log for today?
  4. How many date mentions still are not linked to their daily note?
     Asked of link-dates-to-daily-notes.py --check, not re-implemented here,
     so GL-1011's scope has one home.

It decides nothing (GL-1005): the operator reads the report and rules.
Exit 0 always, except the asserts, which exit 1 with a FAIL line.

THE COMPLETION RECEIPT, AND WHY --assert-logged CHANGED
-------------------------------------------------------
Until 2026-09-14 --assert-logged asked one question: is there a file in
Session Logs/ whose name starts with today's date. A log written at 09:00
therefore passed the checkpoint of a session that ran at 17:00 and wrote
nothing, and the gate read green for a session that never closed. The check
was bound to the DATE. Sessions are not days.

It is bound to the SESSION now. Closing a session writes a receipt:

  .mypka/state/receipts/<session-id>.json   (schema 1)
    workflow           which workflow this receipt closes (WS-1005)
    session_id         whose session it was
    started, finished  when
    inputs             path -> sha256 of what the work read
    outputs            path -> sha256 of what it wrote, the session log
                       among them
    validator_version  which version of THIS script wrote it
    unresolved         what is knowingly left open

--assert-logged then checks the receipt for THIS session: that it exists,
that it names this script's current validator version, that it names a
session log among its outputs, and that every output it names is still on
disk with the hash it recorded. Yesterday's receipt belongs to yesterday's
session id and cannot answer for this one.

The session id is read, never minted here, in this order: `--session-id`,
then a host variable (`HERMES_SESSION_ID`, then `ICOR_SESSION_ID`), then
`.mypka/state/session.json`, written by the SessionStart hook
(session-start.py). So on a host that exports its own variable this session's
id is picked up on its own and no flag is needed; the window comes from the
id's own timestamp (`started_from_id`) rather than the shared slot. This
paragraph said the opposite until 2026-09-30 — that no environment variable
carried a session id on any host checked — and a caller who believed it would
mint a fresh id and re-point the one shared slot for nothing. Where the host
supplies none and the slot holds a minted `local-...`, a bare call is REFUSED
rather than filing this receipt under another session's id, and the assert
says exactly that instead of guessing.

--assert-logged-today keeps the old behaviour under its true name, for a
runtime with no session start hook. It is WEAKER, by design and by name: it
proves a file exists with today's date on it and nothing else.

WHAT A RECEIPT DOES NOT PROVE
- That the work was any good, or that the log says anything true. It proves
  which bytes were written, by which version, in which session.
- That nothing else changed. Only the paths named in the receipt are
  hashed; a file the checkpoint never listed is invisible to it.
- That the session id is the host's. Where the host sends none, one is
  minted, and the receipt is then bound to a local id rather than a real
  session. session.json records which of the two it was.

WHAT --assert-wikilinks PROVES, AND WHAT IT DOES NOT
- It proves THIS session's declared outputs — the files named in its
  completion receipt's `outputs` — carry no wikilink that resolves in NO
  vault (a target absent from the team root AND, in mode B, from the content
  source). That is the universally-broken class; the gate fails on it alone.
- A link that resolves in the content source but not the team root is a
  cross_tree dependency (mode B) and is allowed, not failed.
- It does NOT prove the whole tree is clean: only the receipt's outputs are
  scanned, never the vault at large.
- It does NOT prove the receipt's `outputs` list is complete: a file the
  session wrote but forgot to declare is invisible to this gate, exactly as
  it is invisible to the hash check.

Usage:
  Scripts/checkpoint.py [<vault-root>] [--window 30] [--json]
                        [--assert-logged] [--assert-logged-today]
                        [--assert-dates-linked] [--assert-wikilinks]
  Scripts/checkpoint.py --write-receipt --output "<session log path>" [...]

REBUILDING A RECEIPT A SESSION LOST (--reconstruct)
---------------------------------------------------
A receipt that was overwritten or deleted cannot be re-created by the strict
writer: `started` falls back to the repair moment for a minted id, `finished`
is always stamped now, and a prior receipt whose `started` disagrees blocks the
write rather than being corrected. That left hand-edited JSON as the only way
back, which is the one thing a receipt must never need.

--reconstruct is that way back, and it is the ONLY caller allowed to write a
window that is not this session's own:

  Scripts/checkpoint.py --write-receipt --reconstruct \
    --session-id <the id the lost receipt used> \
    --started <when that session really began, ISO 8601 UTC> \
    --finished <when it really ended> \
    --output "<each artifact it named>" --unresolved "<each open item>"

It refuses when --started is missing, when `started` is later than `finished`,
or when the receipt on disk turns out to belong to a DIFFERENT session (see
below). The strict path, without the flag, is unchanged and still refuses.

THE DELETE CHECK (--removing <id>, defect 1)
--------------------------------------------
The receipt this task is about was not lost to a bug in the writer: a sibling
session had it REMOVED, deciding from "the id is minted and absent from
session.json". Neither fact is evidence about the receipt. The evidence that
settles it is the one thing the delete decision did not consult — a session log
on disk that only that receipt pins. Run this before removing any receipt:

  Scripts/checkpoint.py --removing <the id you are about to remove>

Exit 1 names the log(s) that would be orphaned; keep the receipt, or rebuild
the ones that really are missing with --reconstruct first. It is scoped to the
receipts named, not the whole vault: a vault-wide "is any log unpinned" gate
would be permanently red, since logs written before receipts were in use look
identical to sessions that never closed.

WHY THE OVERWRITE GUARD NOW ASKS ABOUT THE SESSION LOG, NOT `started`
---------------------------------------------------------------------
Until 2026-09-29 the guard refused a second receipt for one id only when the
prior `started` DIFFERED from the incoming one. But `started` is taken from
session.json whenever the slot id is the caller's — and two sessions that both
pass that one minted `local-...` id read the IDENTICAL value out of that one
file. The values matched, no refusal was raised, and the second write replaced
the first session's receipt in silence: the exact case the guard existed for,
and the one case it could not see.

A receipt's own session log is the field that is NOT derived from the shared
slot, and a log belongs to exactly one session. So the guard now refuses when
the prior receipt names a session log that (a) is not among this call's outputs
and (b) no OTHER receipt claims — the signature of a real session whose log
would be orphaned. The `started` comparison stays as a second signal, for the
slot-re-pointed case, and either one firing is enough.
"""
import argparse, datetime, hashlib, importlib.util, json, os, re, subprocess, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("root", nargs="?", default=None)
ap.add_argument("--window", type=int, default=30, help="days a WiP folder may sit untouched before it is a candidate to leave")
ap.add_argument("--json", action="store_true")
ap.add_argument("--assert-logged", action="store_true", help="exit 1 unless this session has a completion receipt naming a session log that is still on disk unchanged")
ap.add_argument("--assert-logged-today", action="store_true", help="the pre-2026-09-14 check, kept for runtimes with no session start hook: exit 1 unless SOME session log carries today's date. Weaker: a morning log passes an afternoon checkpoint")
ap.add_argument("--write-receipt", action="store_true", help="write this session's completion receipt")
ap.add_argument("--workflow", default="WS-1005", help="which workflow the receipt closes")
ap.add_argument("--session-id", default=None, help="override the session id from .mypka/state/session.json")
ap.add_argument("--input", action="append", default=[], help="a path the work read; repeatable")
ap.add_argument("--output", action="append", default=[], help="a path the work wrote; repeatable. The session log belongs here")
ap.add_argument("--unresolved", action="append", default=[], help="something knowingly left open; repeatable")
ap.add_argument("--reconstruct", action="store_true", help="rebuild the receipt for a session that has ALREADY closed, from --started/--finished. The one caller allowed to replace an existing receipt's window, and only after the evidence test below; the strict path is unchanged while this flag is absent")
ap.add_argument("--started", default=None, help="when a reconstructed session began, ISO 8601 UTC (requires --reconstruct)")
ap.add_argument("--finished", default=None, help="when a reconstructed session ended, ISO 8601 UTC (requires --reconstruct; defaults to now)")
ap.add_argument("--assert-dates-linked", action="store_true", help="exit 1 unless every date mention in scope links to its daily note (GL-1011)")
ap.add_argument("--assert-wikilinks", action="store_true", help="exit 1 unless this session's declared receipt outputs carry no wikilink that resolves in NO vault (dangling); a link that resolves only in the content source (mode B) is cross_tree and allowed")
ap.add_argument("--removing", action="append", default=[], help="the id of a receipt about to be removed; repeatable. Exit 1 when removing it would leave a session log that no other receipt pins — a log no receipt claims is a session whose close was recorded and then lost (defect 1 of task 2026-09-29-receipt-repair-refused-by-own-guard)")
ap.add_argument("--today", default=None, help="override today's date, YYYY-MM-DD (tests)")
a = ap.parse_args()

# resolve.py sits beside this script and is loaded by path, like noteio.py.
# It is the one code that finds the team root and turns a concept into a
# place (GL-1013 sections 6 and 9).
_rs_path = Path(__file__).resolve().parent / "resolve.py"
if not _rs_path.is_file():
    raise SystemExit("FAIL resolve.py is missing from %s. Scripts/ is half "
                     "upgraded; restore resolve.py beside this script and run "
                     "this again." % _rs_path.parent)
_rs = importlib.util.spec_from_file_location("mypka_resolve", _rs_path)
resolver = importlib.util.module_from_spec(_rs)
_rs.loader.exec_module(resolver)


def _team_root(explicit=None):
    """GL-1013 section 6: explicit, then CLAUDE_PROJECT_DIR when it holds the
    marker, then the walk up from this file."""
    try:
        return resolver.find_team_root(explicit=explicit, start=__file__).path
    except resolver.ResolveError as e:
        raise SystemExit("FAIL %s" % e)


ROOT = _team_root(a.root)
# The binding: which source serves wip, and the source a content tool reads.
# A root with no binding (no sources.yaml, no ICOR marker) still has team
# memory to check; it simply has no WiP to scan and no dates to count.
try:
    BIND = resolver.load(ROOT)
except resolver.ResolveError:
    BIND = None
TASKS = resolver.team_path("tasks", root=ROOT)
LOGS = resolver.team_path("session_logs", root=ROOT)
WIP = None
if BIND is not None:
    try:
        WIP = resolver.resolve_path("wip", bindings=BIND)
    except resolver.ResolveError:
        WIP = None   # no source serves wip: deliverables sit with their tasks (k4v)
# Team state, ruling j5d: .mypka/state/, no longer .icor-for-life/scripts/.
MACHINE = resolver.team_path("team_state", root=ROOT)
RECEIPTS = MACHINE / "receipts"
# The one place a session log is recognised inside a receipt's outputs. The
# assert below requires one; the overwrite guard uses it as the receipt's
# identity anchor, because a session log is the single field of a receipt that
# is NOT derived from the shared session.json slot.
LOGS_PREFIX = LOGS.relative_to(ROOT).as_posix() + "/"
# The buckets of the wip room's README.md. Never candidates themselves; the scan
# steps into them and reports the dated work inside. `Reports/` is not
# shipped and is listed anyway, because a member who opens one must not
# have it flagged as a stale folder on the first checkpoint after.
STANDING = ("Workstreams", "Projects", "AI Team", "Operations", "Reports")
# The two buckets that hold a NAMED folder per process or per Project
# rather than dated work directly. The other buckets hold the dated work
# itself, as a file or as a folder.
NAMED = ("Workstreams", "Projects")
# Report order, not filesystem order. `Operations/` is read first because
# it is the bucket nothing closes from the outside: a Project takes its
# folder with it and a Workstream run is finished by the next run, so
# Operations is where work goes stale unnoticed (Tom, 2026-09-17).
BUCKET_ORDER = ("Operations", "Reports", "Workstreams", "AI Team", "Projects")
today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
now = datetime.datetime.combine(today, datetime.time(23, 59))

def mtime(p: Path) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(p.stat().st_mtime)


def mtime_aware(p: Path) -> datetime.datetime:
    """The same instant, carrying the machine's own offset.

    `fromtimestamp()` with no argument returns LOCAL WALL TIME with no
    tzinfo on it, and `.astimezone()` on a naive value attaches the local
    zone rather than converting, which is exactly what is wanted here: the
    number is already local. Only the cutoff comparison needs this; `now`
    and every age in days below stay naive and stay comparable to mtime().
    """
    return datetime.datetime.fromtimestamp(p.stat().st_mtime).astimezone()

def newest_under(folder: Path):
    best = None
    for dp, _, fs in os.walk(folder):
        for f in fs:
            t = mtime(Path(dp) / f)
            if best is None or t > best:
                best = t
    return best

# --- 1. the last session log, and today's ---------------------------------
# A session log is named for the moment it covers (GL-1004:
# YYYY-MM-DD-HH-MM_agent_slug.md), and that is the timestamp this scan needs.
# Filesystem mtime is a different fact: a sync tool, a restore from Time
# Machine, a checkout, or the member simply reopening the log to read it all
# move mtime forward. Comparing against mtime therefore put the cutoff in the
# future and the report said `tasks touched : 0` on a session that had
# shipped six of them (Brian Carroll, T16-12). The name is read first and
# mtime is the fallback, for a log a member renamed or wrote by hand.
LOG_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{2})-(\d{2})_")


def log_time(p: Path) -> datetime.datetime:
    m = LOG_NAME.match(p.name)
    if m:
        try:
            return datetime.datetime.fromisoformat(
                "%sT%s:%s" % (m.group(1), m.group(2), m.group(3)))
        except ValueError:
            pass
    return mtime(p)


logs = sorted(LOGS.glob("*/*/*.md")) if LOGS.exists() else []
last_log = max(logs, key=log_time) if logs else None
last_log_time = log_time(last_log) if last_log else datetime.datetime.min
todays = [p for p in logs if p.name.startswith(today.isoformat())]

# --- 1b. the cutoff: when THIS session started ----------------------------
# The log's own name is the right cutoff for a report written after the log,
# and the wrong one for the report a checkpoint writes BEFORE it (WS-1005
# runs the report first, then writes the log). Read in that order the log
# name is still the PREVIOUS session's, so work shipped earlier today was
# listed twice: once in the report that preceded the log and again in the
# next session's. Worse in the other direction: once the log exists, a task
# closed earlier in the same session but before the log's own minute sits
# BEHIND the cutoff and disappears from the session that shipped it.
#
# A session knows when it started. session-start.py writes it to
# .mypka/state/session.json as `started`, UTC, with a trailing Z,
# and the receipt half of this script already reads that file. The log name
# stays as the fallback, for a runtime with no session start hook.
#
# Two traps, both of which this handles rather than documents:
#   - `fromisoformat` did not accept a trailing `Z` until Python 3.11, and
#     3.9 is what ships on this machine. The Z is converted, not parsed.
#   - `started` is UTC-aware and mtime() is naive local. Comparing the two
#     raises TypeError on some paths and silently compares wall clocks on
#     none of them, so the comparison is made in aware time on both sides
#     (mtime_aware) and every OTHER use of mtime() is left alone.
# Reported by Brian Carroll (B2-2).
def _parse_started(raw):
    s = str(raw or "").strip()
    if not s:
        return None
    if s[-1] in "Zz":
        s = s[:-1] + "+00:00"
    try:
        d = datetime.datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo is not None else d.replace(tzinfo=datetime.timezone.utc)


def _slot():
    """The single shared .mypka/state/session.json, or {}."""
    sf = MACHINE / "session.json"
    try:
        d = json.loads(sf.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (ValueError, OSError):
        return {}


def _named_id():
    """The session id THIS caller named, from the flag or a host variable.

    `HERMES_SESSION_ID` is included because it is the name a live host actually
    exports; reading only `ICOR_SESSION_ID` meant a Hermes session that passed
    no flag looked like one that had named nothing, so `_slot_is_mine()` said
    the slot was ours and the report borrowed another session's window
    (measured 2026-09-30). Order matches session-start.py: the host's own
    variable first, then a deliberately-set neutral one.
    """
    for var in ("HERMES_SESSION_ID", "ICOR_SESSION_ID"):
        if os.environ.get(var):
            return os.environ[var]
    return None


def _slot_is_mine():
    """session.json holds ONE session, whichever minted it last. It is this
    caller's only when the caller did not name a different id: an override
    (--session-id / a host variable) that names another session is, by
    definition, not the one in the slot, so its `started` is not ours to
    borrow (task 2026-09-28-session-json-single-slot-concurrent-sessions)."""
    named = a.session_id or _named_id()
    return not named or named == _slot().get("session_id")


def session_started():
    if not _slot_is_mine():
        return None
    return _parse_started(_slot().get("started"))


# A HOST-SUPPLIED id carries the session's start inside itself, and that is the
# honest answer whenever the slot is not ours. `20260929_012047_539173` is local
# time, the same rule the session-lifecycle skill prescribes for recomputing a
# mis-filed `started`. Without this a session that named its own id got
# `started` = now on its receipt (a zero-width window that hides every task the
# session touched) and `cutoff_source` = the last session log's name, so the
# report was computed over a window that was never its own. A minted `local-...`
# id holds no timestamp and keeps the fallbacks below. Reported while closing a
# session whose receipt recorded `started` == `finished`.
_ID_STAMP = re.compile(r"^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})(?:_|$)")


def started_from_id(sid):
    """This session's start, derived from its own id, or None when the id
    carries no timestamp (a minted `local-...`)."""
    m = _ID_STAMP.match(str(sid or ""))
    if not m:
        return None
    try:
        naive = datetime.datetime(*(int(x) for x in m.groups()))
    except ValueError:
        return None
    return naive.astimezone().astimezone(datetime.timezone.utc)


_started = session_started()
_id_started = None if _started is not None else started_from_id(
    a.session_id or _named_id())
cutoff = _started if _started is not None else (
    _id_started if _id_started is not None else (
        last_log_time.astimezone() if last_log else
        datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)))
cutoff_source = "session.json started" if _started is not None else (
    "derived from the session id" if _id_started is not None else (
        "last session log name" if last_log else "no cutoff (nothing to compare against)"))

# --- 2. tasks touched since the last log ----------------------------------
# open/ and in-progress/ are flat; done/ and cancelled/ nest by YYYY/MM/
# (hard rule 6), so those two are walked recursively. Only open and
# in-progress tasks can still reference a WiP folder, so only their text
# feeds the WiP check below.
STATES = ("open", "in-progress", "done", "cancelled")
touched = []
task_texts = []
touched_by_state = {s: 0 for s in STATES}
for state in STATES:
    d = TASKS / state
    if not d.exists():
        continue
    live = state in ("open", "in-progress")
    for f in sorted(d.glob("*.md") if live else d.rglob("*.md")):
        if live:
            task_texts.append(f.read_text(errors="ignore"))
        if mtime_aware(f) > cutoff:
            touched.append({"state": state, "file": f.name,
                            "path": f.relative_to(TASKS).as_posix(),
                            # WHEN, not just WHETHER. The window is time-based and
                            # carries no author, so a task a SIBLING session edited
                            # lands in this session's list and reads as work to close
                            # here — which is what happened to the 23:58 session on
                            # 2026-09-29, whose report named a task the other session had
                            # touched at 00:09:55. With the instant on the entry, the
                            # judgement step can see an edit that is not its own without
                            # stat'ing the file from outside the report. The rule the fix
                            # serves is the one the session-lifecycle skill states: read
                            # the mtime against your own timeline before ruling on an item.
                            "touched": mtime_aware(f).isoformat()})
            touched_by_state[state] += 1
all_task_text = "\n".join(task_texts)

# --- 3. WiP folders: age and task references -------------------------------
wip = []


def wip_row(entry: Path, label: str, standing: bool):
    # newest_under() walks a folder; a single dated FILE is its own newest.
    newest = (mtime(entry) if entry.is_file()
              else (newest_under(entry) or mtime(entry)))
    age = (now - newest).days
    # A task may name the bucket path, the file or folder name, or the
    # name without its extension. All three are the same piece of work.
    referenced = (label in all_task_text or entry.name in all_task_text
                  or (entry.is_file() and entry.stem in all_task_text))
    return {
        "folder": label,
        "days_untouched": max(0, age),
        "referenced_by_open_task": referenced,
        "standing": standing,
        "candidate_to_leave": (not standing) and age > a.window and not referenced,
    }


def wip_child(parent: Path):
    """The entries inside a bucket that are work, in name order.

    A bucket carries one README.md that explains it. That file is not
    work and must never be reported, or every checkpoint would offer to
    archive the documentation of the room it is reporting on.
    """
    for child in sorted(parent.iterdir()):
        if child.name.startswith(".") or child.name.startswith("_"):
            continue
        if child.is_file() and child.name.lower() == "readme.md":
            continue
        if child.is_dir() or child.suffix.lower() == ".md":
            yield child


if WIP is not None and WIP.exists():
    roots = [e for e in WIP.iterdir()
             if not e.name.startswith("_") and not e.name.startswith(".")]
    # Buckets first, in the order of BUCKET_ORDER; then anything else at
    # the root, which in a vault older than 1.30.0 is undated-bucket work
    # from before the buckets existed and is reported exactly as before.
    def root_key(e: Path):
        if e.is_dir() and e.name in STANDING:
            return (0, BUCKET_ORDER.index(e.name) if e.name in BUCKET_ORDER
                    else len(BUCKET_ORDER), e.name)
        return (1, 0, e.name)

    for entry in sorted(roots, key=root_key):
        if entry.is_dir() and entry.name in STANDING:
            wip.append(wip_row(entry, entry.name, standing=True))
            for child in wip_child(entry):
                label = f"{entry.name}/{child.name}"
                # Workstreams/<Name>/ is itself standing (a process); its
                # dated runs sit one level further down. Projects/<name>/
                # is the unit that leaves, with its Project. Every other
                # bucket holds the dated work itself.
                if entry.name == "Workstreams" and child.is_dir():
                    wip.append(wip_row(child, label, standing=True))
                    for run in wip_child(child):
                        wip.append(wip_row(run, f"{label}/{run.name}", standing=False))
                else:
                    wip.append(wip_row(child, label, standing=False))
            continue
        if not entry.is_dir():
            continue
        wip.append(wip_row(entry, entry.name, standing=False))

# --- 3b. session logs no receipt pins, SPLIT BY THE MECHANISM'S ARRIVAL -----
# A log with no receipt looks the same whether a session failed to close or
# closed before receipts existed, and only the DATE separates them: the
# earliest receipt this vault holds is the first moment a session here COULD
# have written one, so every unpinned log older than that is a pre-mechanism
# record and every one younger is a genuine gap. Reported as two numbers, never
# one: the raw count is dominated by history and reads as debt that does not
# exist (25 against 0, measured 2026-09-30), while the raw count alone is what
# made the two newest orphans look like the same problem.
#
# Both sides are DERIVED — the log's moment from its own name (GL-1004's
# YYYY-MM-DD-HH-MM, the same source `log_time` trusts above), the line from the
# receipts on disk — so the split cannot drift and needs no per-file exception
# list. The comparison is at MINUTE precision, not day: a receipt written
# 2026-09-27T00:49:22Z is 2026-09-26 19:49 LOCAL, and the one log that sits
# between that instant and the next receipt (2026-09-26-21-12, itself 21:12
# local) is a real gap a date-level line would miss. The name is local time, so
# the line is converted to local before comparing.
_LOG_NAME_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")


def receipt_path(sid):
    """Where a receipt for `sid` lives. Defined here, above the report, because
    the overlap block needs it while the report is being built."""
    return RECEIPTS / (re.sub(r"[^A-Za-z0-9._-]", "_", sid) + ".json")


def receipt_log_owners():
    """{session-log path: [the receipt that names it]} over every receipt.

    A session log belongs to exactly one session, so this index is how the
    script answers the two questions the receipt guard and the deletion check
    both rest on: is this log already claimed, and which logs no receipt claims
    at all (a session's record is missing, or a receipt was removed).

    Receipts that name no log are simply absent from the index; the assert
    refuses such a receipt, so it anchors nothing either way.
    """
    owners = {}
    for rp in sorted(RECEIPTS.glob("*.json")) if RECEIPTS.exists() else []:
        try:
            rec = json.loads(rp.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        for rel in (rec.get("outputs") or {}):
            if str(rel).startswith(LOGS_PREFIX):
                owners.setdefault(rel, []).append(rp)
    return owners


receipt_starts = []
for _rp in sorted(RECEIPTS.glob("*.json")) if RECEIPTS.exists() else []:
    try:
        _rec = json.loads(_rp.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        continue
    _s = _parse_started(_rec.get("started"))
    if _s is not None:
        receipt_starts.append(_s)
# Local NAIVE, to compare like with like against `log_time`'s naive local.
mechanism_at = (min(receipt_starts).astimezone().replace(tzinfo=None)
                if receipt_starts else None)

owners_all = receipt_log_owners()

# --- 3c. WHO ELSE WAS LIVE, derived from the receipts already on disk ---------
# A session's window is `started .. finished`, so overlap is a set operation
# over receipts already written — no new state, and no dependence on the host's
# session store (the vault is runtime-independent by contract). This is the
# DETECTION half of the coordination question: it turns "each session discovers
# a sibling by accident and describes it in prose" into a list the session names
# from, which is why it is derived here rather than left to memory.
#
# TWO LIMITS, and the report says both out loud rather than implying more:
#   - A sibling still RUNNING has no receipt yet, so it cannot appear here.
#     Close-time detection therefore catches the dominant case on this vault
#     (one long session with short ones nested inside it) and misses a sibling
#     that is live at the moment this receipt is written.
#   - `finished` of a receipt written late includes the checkpoint itself, so
#     the window is slightly generous. Reported as a list of ids, not as a
#     precise interval, which is all a session needs to name them.
def _overlaps(mine_id):
    me = None
    rp = receipt_path(mine_id) if mine_id else None
    if rp is not None and rp.is_file():
        try:
            me = json.loads(rp.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            me = None
    # Before its receipt exists (the report usually runs FIRST), fall back to
    # this session's own derived window so the list is still available.
    a_start = (_parse_started(me.get("started")) if me else None) or \
        started_from_id(mine_id) or _started
    a_fin = (_parse_started(me.get("finished")) if me else None) or \
        datetime.datetime.now(datetime.timezone.utc)
    if a_start is None or a_fin is None:
        return None
    out = []
    for op in sorted(RECEIPTS.glob("*.json")) if RECEIPTS.exists() else []:
        try:
            od = json.loads(op.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if str(od.get("session_id")) == str(mine_id):
            continue
        s, f = _parse_started(od.get("started")), _parse_started(od.get("finished"))
        if s is None or f is None or s == f:
            continue                      # a zero-width window proves no overlap
        if a_start < f and s < a_fin:
            out.append({"session_id": str(od.get("session_id")),
                        "started": od.get("started"), "finished": od.get("finished"),
                        "log": next((str(o) for o in (od.get("outputs") or {})
                                     if str(o).startswith(LOGS_PREFIX)), None)})
    return out


_overlap_id = a.session_id or _named_id()
if _overlap_id is None:
    # No id named: the slot is the only candidate, and session_id() would
    # refuse a foreign one, so there is nothing honest to compare against.
    try:
        _overlap_id = str(_slot().get("session_id") or "") or None
    except Exception:
        _overlap_id = None
# `a.session_id`/`_named_id()` come from argparse/env, so this is safe to run
# in the same pass as `unpinned` above.
overlaps = _overlaps(_overlap_id)

unpinned = {
    "mechanism_date": mechanism_at.isoformat() if mechanism_at else None,
    "pre_mechanism": [],   # closed before a receipt could record it: expected
    "unexplained": [],     # at or after the line, and still unpinned: a gap
    "undated": [],         # name carries no timestamp: neither side, said so
}
if mechanism_at is not None and LOGS.exists():
    for f in sorted(LOGS.glob("*/*/*.md")):
        rel = f.relative_to(ROOT).as_posix()
        if rel in owners_all:
            continue
        when = log_time(f)
        # A name that carries no parseable timestamp falls back to mtime in
        # `log_time`; say so rather than silently taking an mtime for a name.
        if not LOG_NAME.match(f.name):
            unpinned["undated"].append(rel)
            continue
        (unpinned["pre_mechanism"] if when < mechanism_at
         else unpinned["unexplained"]).append(rel)

# --- 4. date mentions not yet linked to their daily note (GL-1011) --------
# Asked of the script that owns the rule. A count it could not read is
# reported as None, never as 0: a check that reads a source must say when
# it read none.
dates_unlinked = None
# The linker is the content source's own tool, and it reads the content
# source's root (GL-1013 resolve_tool).
linker, LIFE = None, None
if BIND is not None:
    try:
        linker = resolver.resolve_tool("link-dates-to-daily-notes", bindings=BIND)
        LIFE = resolver.tool_source(BIND).root
    except resolver.ResolveError:
        linker = None
if linker is not None and linker.is_file():
    r = subprocess.run([sys.executable, str(linker), str(LIFE), "--check", "--json"],
                       capture_output=True, text=True)
    try:
        # The first JSON object on stdout, not the whole stream. Belt and
        # braces with the linker's own fix: a caller that demands a pure
        # stdout is a caller that reports None the day anything adds a line.
        dates_unlinked = json.JSONDecoder().raw_decode(
            r.stdout[r.stdout.find("{"):])[0]["mentions"]
    except (ValueError, KeyError):
        dates_unlinked = None

report = {
    "today": today.isoformat(),
    "last_session_log": str(last_log.relative_to(ROOT)) if last_log else None,
    "session_log_today": bool(todays),
    # The key keeps its 1.14.0 name so an existing reader does not break,
    # but the cutoff is the session's start when there is one; `cutoff` and
    # `cutoff_source` say which of the two answered.
    "tasks_touched_since_last_log": touched,
    "tasks_touched_by_state": touched_by_state,
    "cutoff": cutoff.isoformat() if last_log or _started else None,
    "cutoff_source": cutoff_source,
    "wip": wip,
    "window_days": a.window,
    "date_mentions_unlinked": dates_unlinked,
    "unpinned_logs": unpinned,
    # Who else was live across THIS session's window, derived from receipts.
    # A list (or None when no id could be established), never a count of
    # "concurrent sessions": a sibling still running has no receipt yet.
    "overlapped_sessions": overlaps,
}

if a.json:
    print(json.dumps(report, indent=2))
else:
    print(f"checkpoint {today.isoformat()}  (window {a.window} days)")
    print(f"  last session log : {report['last_session_log'] or 'none yet'}")
    print(f"  log for today    : {'yes' if report['session_log_today'] else 'NO'}")
    print(f"  date links       : {'unknown (link-dates-to-daily-notes.py did not answer)' if dates_unlinked is None else str(dates_unlinked) + ' mention(s) unlinked'}")
    # Two numbers, never one: the raw count is dominated by logs that predate
    # the receipt mechanism and reads as debt that does not exist.
    _un = unpinned
    if _un["mechanism_date"] is None:
        print("  session logs     : receipts exist but none records a start, so "
              "the pre-mechanism line cannot be drawn (nothing to compare)")
    else:
        print(f"  session logs     : {len(_un['unexplained'])} unpinned at/after "
              f"{_un['mechanism_date']} local (a gap: a session that could have "
              f"checkpointed and did not); {len(_un['pre_mechanism'])} unpinned "
              f"before it (pre-receipt-era, expected)"
              + (f"; {len(_un['undated'])} undated (name carries no timestamp)"
                 if _un["undated"] else ""))
        for rel in _un["unexplained"]:
            print(f"    - NO RECEIPT, and newer than the mechanism: {rel}")
    # Who else was live, so the session NAMES them in its log instead of
    # guessing which sibling it noticed. Derived, not remembered.
    if overlaps is None:
        print("  overlapped       : unknown (no session id to compare against)")
    elif not overlaps:
        print("  overlapped       : none on record")
    else:
        print(f"  overlapped       : {len(overlaps)} other session(s) were live "
              f"across this window — name them in the session log:")
        for o in overlaps:
            print(f"    - {o['session_id']}  ({o['started']} .. {o['finished']})"
                  + (f"  wrote {o['log']}" if o["log"] else ""))
        print("    A sibling still RUNNING has no receipt yet and cannot appear "
              "here; this list is receipts, not a live roster.")
    print(f"  cutoff           : {report['cutoff'] or 'none'} ({cutoff_source})")
    print(f"  tasks touched    : {len(touched)}"
          + (" (" + ", ".join(f"{s} {n}" for s, n in touched_by_state.items() if n) + ")" if touched else ""))
    for t in touched:
        # The instant, so the operator can tell this session's edit from a
        # sibling's without leaving the report (the window has no author).
        print(f"    - [{t['state']}] {t['path']}"
              + (f"  touched {t['touched']}" if t.get("touched") else ""))
    cands = [w for w in wip if w["candidate_to_leave"]]
    print(f"  wip folders      : {len(wip)}, candidates to leave: {len(cands)}")
    for w in wip:
        flag = "LEAVE?" if w["candidate_to_leave"] else ("stand " if w.get("standing") else "keep  ")
        ref = "task" if w["referenced_by_open_task"] else "none"
        print(f"    {flag}  {w['days_untouched']:>4}d  ref:{ref:<4}  {w['folder']}")

# --- 5. the completion receipt (schema 1) ---------------------------------
# Bumped by hand whenever the receipt's meaning changes. A receipt written by
# a different version is refused rather than half-trusted: the fields would
# still parse, and that is exactly what makes a silent version drift
# dangerous.
RECEIPT_SCHEMA = 1
VALIDATOR_VERSION = "checkpoint.py/2026-09-16"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def session_id():
    """This session's id, and where it came from. Never invented here: a
    receipt bound to an id this script made up would bind to nothing."""
    if a.session_id:
        return a.session_id, "--session-id"
    env = _named_id()
    if env:
        return env, ("HERMES_SESSION_ID" if os.environ.get("HERMES_SESSION_ID")
                     == env else "ICOR_SESSION_ID")
    sf = MACHINE / "session.json"
    if sf.is_file():
        try:
            data = json.loads(sf.read_text(encoding="utf-8"))
            if data.get("schema") == 1 and data.get("session_id"):
                # THE SAME-SLOT GAP (task 2026-09-28-session-json-single-slot-
                # concurrent-sessions). One file is shared by every session in
                # this vault, and a caller that names NO id of its own cannot
                # tell "the slot is MY session" from "the slot is a sibling's".
                # Two shapes, and they need different answers:
                #
                # 1. A MINTED slot. The host sent no id at all, so the session
                #    that wrote it had none either; the id is a guess about
                #    THIS caller and must never be used. Refuse.
                # 2. A HOST-written slot (hook payload) with the caller naming
                #    nothing. Here the slot is the ONLY id source — the design
                #    for a host that writes the slot but exports no variable —
                #    so using it is correct, and refusing it broke the
                #    legitimate path (measured 2026-09-30: `checkpoint/
                #    receipt-*-control` and `session-start/names-the-last-
                #    receipt` all failed when this refused every unnamed
                #    caller). The residual risk is a SIBLING reading it, which
                #    is inherent to a host-only slot; the RECEIPT guard is what
                #    makes that non-destructive, because it refuses the
                #    overwrite and names the log that would be orphaned.
                #
                # CHANGE 1 IS WHAT REMOVES THE AMBIGUITY, not this check: once
                # the host's own variable is read, a Hermes session always has
                # an id of its own and never needs the slot. This branch is the
                # fallback for a host that provides no variable.
                if str(data.get("id_source") or "").startswith("minted here"):
                    print("FAIL: session.json holds an id this machine MINTED "
                          f"({data['session_id']}) because the host sent none, and "
                          "that one file is shared by every session in this vault, "
                          "so a bare checkpoint could close another session's "
                          "receipt. Pass this session's own id, the one the start "
                          "ritual printed as `session id: ...`: "
                          f"--session-id {data['session_id']}  (or set "
                          "HERMES_SESSION_ID).", file=sys.stderr)
                    sys.exit(1)
                return str(data["session_id"]), "session.json"
        except (ValueError, OSError):
            pass
    return None, None


def hashes(paths):
    out = {}
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = ROOT / raw
        rel = p.relative_to(ROOT).as_posix() if str(p).startswith(str(ROOT)) else str(p)
        out[rel] = sha256_of(p) if p.is_file() else None
    return out


def receipt_writes_a_log(rec):
    """True when this receipt names a session log among its outputs.

    A real session's receipt always does; the assert refuses one that does not.
    That makes it the honest identity anchor for the overwrite guard.
    """
    return any(str(p).startswith(LOGS_PREFIX) for p in (rec.get("outputs") or {}))


def prior_window_is_this_sessions(prior, incoming_outputs):
    """The evidence test for replacing an existing receipt's window.

    Two sessions that both pass the slot's own minted `local-...` id read the
    IDENTICAL `started` out of that one shared file, so the old test (values
    DISAGREE -> refuse) is blind exactly where the loss happens: the second
    write matched, no refusal was raised, and the first session's receipt was
    replaced silently.

    `started` is therefore not usable as evidence. What is: the prior receipt's
    own session log. Each session writes its own log, and a log belongs to
    exactly one session, so the honest question is whether this call names the
    log the prior receipt already claimed.

    True  -> the receipt on disk is a re-write of the SAME session (same log,
              legitimately refreshed after adding an output), or it names no log
              at all and so anchors nothing.
    False -> the prior receipt names a DIFFERENT session's log: it is a real
              session's record and this call has no business replacing it.
    """
    prior_logs = {p for p in (prior.get("outputs") or {}).keys()
                  if str(p).startswith(LOGS_PREFIX)}
    incoming_logs = {p for p in (incoming_outputs or {}).keys()
                     if str(p).startswith(LOGS_PREFIX)}
    if not prior_logs:
        return True, "the prior receipt names no session log, so it anchors nothing"
    overlap = prior_logs & incoming_logs
    if overlap:
        return True, ("the prior receipt names this same session log (%s)"
                      % ", ".join(sorted(overlap)))
    return False, ("the prior receipt names %s, and no other receipt claims it: "
                   "it is a real session's only record"
                   % ", ".join(sorted(prior_logs)))


if a.write_receipt:
    sid, how = session_id()
    if not sid:
        print("FAIL: no session id, so a receipt would be bound to nothing. "
              "The SessionStart hook writes .mypka/state/session.json; "
              "on a runtime without hooks, pass --session-id or set "
              "HERMES_SESSION_ID / ICOR_SESSION_ID.",
              file=sys.stderr)
        sys.exit(1)
    # --started / --finished are the reconstruction levers and they are only
    # meaningful together with --reconstruct. Refused here rather than ignored,
    # because a silently-ignored --finished is a reconstruction that records
    # the repair moment as the session's close and looks like it worked.
    if (a.started or a.finished) and not a.reconstruct:
        print("FAIL: --started/--finished only apply to --reconstruct, which is "
              "the one path allowed to write a window that is not this session's "
              "own. Add --reconstruct, or drop the flags.", file=sys.stderr)
        sys.exit(1)
    reconstruct_started = None
    if a.reconstruct:
        if not a.started:
            print("FAIL: --reconstruct needs --started, the instant the session "
                  "this receipt closes actually began (ISO 8601, UTC). Writing the "
                  "repair moment as a start is the zero-width window the assert "
                  "then cannot catch.", file=sys.stderr)
            sys.exit(1)
        reconstruct_started = _parse_started(a.started)
        if reconstruct_started is None:
            print(f"FAIL: --started {a.started!r} is not an ISO 8601 instant.",
                  file=sys.stderr)
            sys.exit(1)
    missing = [p for p, h in hashes(a.output).items() if h is None]
    if missing:
        print("FAIL: the receipt names output(s) that are not on disk: "
              + ", ".join(missing), file=sys.stderr)
        sys.exit(1)
    # A receipt records a hash and later asserts the file still matches it, so
    # an output the machine layer rewrites every session is a receipt that is
    # guaranteed to rot. Codex's first pilot session listed session.json and
    # quality.json, and from session 2 onward that receipt could never verify
    # again (pilot B finding F8). This is one line instead of a lesson.
    MACHINE_REL = MACHINE.relative_to(ROOT).as_posix() + "/"
    # Two machine layers since the split (j5d): the team's own state, and the
    # content source's (quality.json, snapshot.json). Both rewrite themselves.
    prefixes = [MACHINE_REL]
    if BIND is not None:
        try:
            _ls = resolver.resolve_path("life_state", bindings=BIND)
            _ls_s = str(_ls)
            prefixes.append((_ls.relative_to(ROOT).as_posix() if _ls_s.startswith(str(ROOT) + os.sep)
                             else _ls_s) + "/")
        except resolver.ResolveError:
            pass
    self_writing = [p for p in hashes(a.output)
                    if any(p.startswith(x) for x in prefixes)]
    if self_writing:
        print("FAIL: the receipt names output(s) the machine layer rewrites on "
              "its own: " + ", ".join(self_writing) + ". Those files change every "
              "session, so a receipt naming them can never verify again. Name "
              "the work: the session log, a note, a deliverable.", file=sys.stderr)
        sys.exit(1)
    # `started` comes from session.json only when the slot is this session's.
    # Otherwise the best honest answer is the start this SAME id names (a host id
    # always carries one), then the start an earlier receipt for this SAME id
    # already recorded, else now. Never another session's start.
    started = _slot().get("started") if _slot_is_mine() else None
    if started is None:
        _derived = started_from_id(sid)
        if _derived is not None:
            started = _derived.isoformat().replace("+00:00", "Z")
    rp = receipt_path(sid)
    prior = None
    if rp.is_file():
        try:
            prior = json.loads(rp.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            prior = None
    if prior and prior.get("started"):
        # TWO SIGNALS, BOTH REFUSE (task 2026-09-29-receipt-repair-refused-by-
        # own-guard, defect 0). The old guard compared `started` against the
        # incoming value — and `started` is what EVERY session holding one
        # minted id reads out of the one shared session.json, so the case it was
        # built for (two sessions, same id, BOTH reading the same slot value) is
        # the one case it can never see. The second write matched, no refusal
        # was raised, and the first session's receipt was replaced in silence.
        #
        # So the comparison stays — it is still the honest signal that the slot
        # was RE-POINTED between the two writes, i.e. a different session took
        # it — and a second, independent signal is added: the prior receipt's
        # own session log, the one field of a receipt that is NOT derived from
        # the shared slot. A log belongs to exactly one session, so a prior
        # receipt whose log no other receipt claims is a real session's only
        # record, and a call naming a different log has no business replacing
        # it. Either signal firing is enough.
        ok, why = prior_window_is_this_sessions(prior, hashes(a.output))
        # A receipt written before the id-derivation fix recorded `started` =
        # the checkpoint moment, so its own `started` equals its `finished` — a
        # zero-width window carrying no session-start information at all. That
        # is a known-bogus legacy value, not evidence of another session.
        legacy_now = (prior["started"] == prior.get("finished"))
        start_conflict = bool(started) and prior["started"] != started and not legacy_now
        if a.reconstruct:
            # The one path allowed to replace a window. It still refuses when
            # the log anchor says the receipt belongs to somebody else: the
            # strict rule stays strict and the flag reaches only the repair it
            # was added for.
            if not ok:
                print(f"FAIL: {rp.relative_to(ROOT)} already records a session "
                      f"that started {prior['started']}, and {why}. "
                      f"--reconstruct replaces a receipt only when the evidence "
                      f"says it is that same session's; this one belongs to "
                      f"somebody else, so rebuilding it here would destroy their "
                      f"record.", file=sys.stderr)
                sys.exit(1)
            print("NOTE: --reconstruct replacing the window of the existing "
                  f"receipt {rp.relative_to(ROOT)} ({why}).", file=sys.stderr)
        elif not ok:
            print(f"FAIL: {rp.relative_to(ROOT)} already records a session that "
                  f"started {prior['started']}, and {why}. Overwriting would "
                  f"destroy that session's only receipt. Pass --session-id with "
                  f"this session's own id; to rebuild a receipt for a session "
                  f"that already closed, pass --reconstruct with --started and "
                  f"--finished.", file=sys.stderr)
            sys.exit(1)
        elif start_conflict:
            print(f"FAIL: {rp.relative_to(ROOT)} already records a session "
                  f"that started {prior['started']}; this call is for a "
                  f"session that started {started}. Two different sessions "
                  f"resolved the same id, and overwriting would destroy the "
                  f"first one's receipt. Pass --session-id with this "
                  f"session's own id.", file=sys.stderr)
            sys.exit(1)
        elif legacy_now and started and prior["started"] != started:
            print("NOTE: the prior receipt's `started` equals its `finished` "
                  f"({prior['started']}), the pre-derivation fallback; "
                  "replacing it with this session's own start.", file=sys.stderr)
        started = started or prior["started"]
    now_utc = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    finished_stamp = now_utc
    if a.finished:
        finished_stamp = _parse_started(a.finished)
        if finished_stamp is None:
            print(f"FAIL: --finished {a.finished!r} is not an ISO 8601 instant.",
                  file=sys.stderr)
            sys.exit(1)
    if reconstruct_started is not None:
        started = reconstruct_started.isoformat().replace("+00:00", "Z")
    # The backwards-window refusal is scoped to the RECONSTRUCTION path, where
    # both values are typed by the operator and a reversed pair is a typo worth
    # refusing. It must NOT run on the ordinary path: there `started` is derived,
    # never typed, so a reversed pair means a stale slot or a moved clock — and
    # refusing would block a session from closing over a fact it did not choose.
    # It would also make the write time-of-day dependent, which is the defect the
    # red-test fixture already documents: a fixture whose `started` is "today
    # 09:00Z" is in the FUTURE for any run before 09:00 UTC, and a guard that
    # refuses it reports the hour the suite ran rather than the code.
    if a.reconstruct:
        _s, _f = _parse_started(started), finished_stamp
        if _s is not None and _f is not None and _s > _f:
            print(f"FAIL: `started` ({started}) is later than `finished` "
                  f"({finished_stamp.isoformat().replace('+00:00', 'Z')}). A "
                  f"window that runs backwards is not a session; check the two "
                  f"values.", file=sys.stderr)
            sys.exit(1)
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "workflow": a.workflow,
        "session_id": sid,
        "session_id_source": how,
        "started": started or now_utc.isoformat().replace("+00:00", "Z"),
        "finished": finished_stamp.isoformat().replace("+00:00", "Z"),
        "inputs": hashes(a.input),
        "outputs": hashes(a.output),
        "validator_version": VALIDATOR_VERSION,
        "unresolved": list(a.unresolved),
    }
    receipt_path(sid).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"OK receipt written: {receipt_path(sid).relative_to(ROOT)} "
          f"({len(receipt['outputs'])} output(s), {len(receipt['unresolved'])} unresolved)")

if a.removing:
    # THE DELETION CHECK (task 2026-09-29-receipt-repair-refused-by-own-guard,
    # defect 1). The 15:46 session removed a receipt because the id was minted
    # and absent from session.json — neither fact is evidence about the file.
    # The evidence that settles it is the one thing the delete decision did not
    # consult: a session log on disk that only THIS receipt pins.
    #
    # Scoped to the receipt(s) about to go, deliberately. A vault-wide "is any
    # log unpinned" gate would be permanently red in a lived-in vault, because
    # logs written before receipts were in use look identical to sessions that
    # never closed — and a guard that is always red is a guard nobody reads.
    owners = receipt_log_owners()
    would_orphan = []
    for raw in a.removing:
        rp = RECEIPTS / (re.sub(r"[^A-Za-z0-9._-]", "_", raw) + ".json")
        if not rp.is_file():
            print(f"FAIL: no receipt at {rp.relative_to(ROOT)} to check.", file=sys.stderr)
            sys.exit(1)
        try:
            rec = json.loads(rp.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            print(f"FAIL: {rp.relative_to(ROOT)} is unreadable ({exc}); do not "
                  f"remove a receipt you cannot read.", file=sys.stderr)
            sys.exit(1)
        for rel in (rec.get("outputs") or {}):
            if not str(rel).startswith(LOGS_PREFIX):
                continue
            holders = [p for p in owners.get(rel, []) if p != rp]
            if not holders:
                would_orphan.append((rp.relative_to(ROOT).as_posix(), rel))
    if would_orphan:
        print("FAIL: removing %s would leave %d session log(s) pinned by no "
              "receipt. A log belongs to exactly one session, and a receipt is "
              "its only record that the session closed — a minted id or an id "
              "absent from session.json is NOT evidence the receipt is a "
              "phantom. Rebuild or keep it; if a receipt really is duplicated, "
              "remove the duplicate, never the log's only claim."
              % (", ".join(sorted({r for r, _ in would_orphan})), len(would_orphan)),
              file=sys.stderr)
        for r, rel in would_orphan:
            print("  - %s is named only by %s" % (rel, r), file=sys.stderr)
        sys.exit(1)
    print("OK removing %s orphans nothing: every session log it names is also "
          "pinned by another receipt (or it names none)."
          % ", ".join(sorted(a.removing)))

if a.assert_logged:
    sid, how = session_id()
    if not sid:
        print("FAIL: no session id to check a receipt against. The SessionStart "
              "hook writes .mypka/state/session.json; on a runtime "
              "without hooks use --assert-logged-today (weaker: it only proves "
              "some log carries today's date) or pass --session-id.",
              file=sys.stderr)
        sys.exit(1)
    rp = receipt_path(sid)
    if not rp.is_file():
        print(f"FAIL: session {sid} has no completion receipt at "
              f"{rp.relative_to(ROOT)}; finish WS-1005 and run "
              f"checkpoint.py --write-receipt --output '<the session log>'",
              file=sys.stderr)
        sys.exit(1)
    try:
        rec = json.loads(rp.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        print(f"FAIL: the receipt for session {sid} is unreadable ({exc})", file=sys.stderr)
        sys.exit(1)
    problems = []
    if rec.get("schema") != RECEIPT_SCHEMA:
        problems.append(f"it is schema {rec.get('schema')!r}, this script writes {RECEIPT_SCHEMA}")
    if rec.get("validator_version") != VALIDATOR_VERSION:
        problems.append(f"it was written by {rec.get('validator_version')!r}, "
                        f"this script is {VALIDATOR_VERSION!r}")
    if rec.get("workflow") != a.workflow:
        problems.append(f"it closes {rec.get('workflow')!r}, not {a.workflow!r}")
    # The receipt must belong to THIS session, not merely carry its id: when
    # the slot is ours, its start must be the start the receipt recorded.
    slot_started = _slot().get("started")
    if _slot_is_mine() and slot_started and rec.get("started") \
            and rec["started"] != slot_started:
        problems.append(f"it records a session that started {rec['started']}, but "
                        f"this session started {slot_started}: the receipt is "
                        f"another session's")
    outputs = rec.get("outputs") or {}
    if not any(p.startswith(LOGS_PREFIX) for p in outputs):
        problems.append("it names no session log among its outputs")
    for rel, recorded in sorted(outputs.items()):
        f = ROOT / rel
        if not f.is_file():
            problems.append(f"the output {rel} it names is gone")
        elif recorded and sha256_of(f) != recorded:
            problems.append(f"the output {rel} changed after the receipt was written")
    if problems:
        print(f"FAIL: the completion receipt for session {sid} does not close this "
              f"checkpoint: " + "; ".join(problems), file=sys.stderr)
        sys.exit(1)
    if rec.get("unresolved"):
        print(f"NOTE: the receipt records {len(rec['unresolved'])} unresolved item(s): "
              + "; ".join(str(u) for u in rec["unresolved"]))
    print(f"OK receipt {rp.relative_to(ROOT)} closes {rec.get('workflow')} for session {sid}")

if a.assert_logged_today and not todays:
    print(f"FAIL: no session log for {today.isoformat()} under {LOGS.relative_to(ROOT)}; run new-session-log.py before ending the session", file=sys.stderr)
    sys.exit(1)
if a.assert_dates_linked and dates_unlinked != 0:
    print(f"FAIL: {'could not read' if dates_unlinked is None else dates_unlinked} date mention(s) not linked to their daily note (GL-1011); run link-dates-to-daily-notes.py --fix", file=sys.stderr)
    sys.exit(1)
if a.assert_wikilinks:
    # THE WIKILINK GATE (2026-09-30). Scoped to THIS session's declared
    # outputs, and to the genuinely-broken class: a link that resolves in
    # NEITHER vault. The obvious gate (scan everything, or --since) is wrong
    # twice over — an edited SOP/guideline carries pre-existing content-side
    # links that dangle in the team vault, and --since picks up a SIBLING
    # session's files too. The receipt's `outputs` are the precise scope: the
    # files THIS session declared it wrote.
    sid, how = session_id()
    if not sid:
        print("FAIL: --assert-wikilinks needs a session id to find the receipt "
              "whose outputs are in scope. The SessionStart hook writes "
              ".mypka/state/session.json; pass --session-id or set "
              "HERMES_SESSION_ID.", file=sys.stderr)
        sys.exit(1)
    rp = receipt_path(sid)
    if not rp.is_file():
        print(f"FAIL: --assert-wikilinks: session {sid} has no completion "
              f"receipt at {rp.relative_to(ROOT)}; write the receipt before "
              f"asserting its outputs carry no broken links.", file=sys.stderr)
        sys.exit(1)
    cw = Path(__file__).resolve().parent / "check-wikilinks.py"
    if not cw.is_file():
        print(f"FAIL: --assert-wikilinks: check-wikilinks.py is missing from "
              f"{cw.parent}, so the guard could not run. A verification step "
              f"that passes when it could not run is the failure it exists to "
              f"prevent.", file=sys.stderr)
        sys.exit(1)
    try:
        rec = json.loads(rp.read_text(encoding="utf-8"))
        outputs = list((rec.get("outputs") or {}).keys())
    except (ValueError, OSError) as exc:
        print(f"FAIL: --assert-wikilinks: the receipt for session {sid} is "
              f"unreadable ({exc}).", file=sys.stderr)
        sys.exit(1)
    if not outputs:
        print("FAIL: --assert-wikilinks: the receipt names no outputs, so "
              "there is nothing to scan; the gate cannot pass on an empty "
              "scope.", file=sys.stderr)
        sys.exit(1)
    # The content root, for the cross-tree split. Only in mode B with a source
    # that carries the marker; in mode A (or with no source bound) a
    # content-side link is genuinely dangling and must be caught.
    also = []
    if BIND is not None and getattr(BIND, "mode", None) == "B":
        try:
            src = resolver.tool_source(BIND)
            if src is not None:
                also = ["--also-root", str(src.root)]
        except resolver.ResolveError:
            also = []
    cmd = [sys.executable, str(cw), str(ROOT)] + outputs + also + ["--json"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        guard = json.JSONDecoder().raw_decode(
            r.stdout[r.stdout.find("{"):])[0]
    except (ValueError, IndexError) as exc:
        print(f"FAIL: --assert-wikilinks: check-wikilinks.py's report could "
              f"not be parsed ({exc}); the gate cannot pass on an unreadable "
              f"report.", file=sys.stderr)
        sys.exit(1)
    dangling = guard.get("dangling") or []
    if dangling:
        for item in dangling:
            print(f"FAIL: --assert-wikilinks: {item['file']}:{item['line']} "
                  f"-> [[{item['target']}]] resolves in no vault", file=sys.stderr)
        sys.exit(1)
    print("OK --assert-wikilinks: this session's declared outputs carry no "
          "link that resolves in no vault")
sys.exit(0)
