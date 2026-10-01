---
type: workstream
id: WS-1005
title: Checkpoint (end a session on purpose)
created: 2026-09-06
owner: aiden
skill_name: checkpoint
skill_summary: 'Ends a session on purpose: reads the checkpoint report, closes or carries every task the session touched, rules on each WiP folder with the user, links the dates the session wrote, writes the session log and asserts it exists before the session is allowed to be over.'
skill_triggers:
  - 'checkpoint'
  - 'close the session'
  - 'wrap up'
  - 'we are done for today'
  - 'end the session'
  - 'let us stop here'
skill_prerun: 'python3 "06 AI Team/AI Team Knowledge/Scripts/checkpoint.py" --json'
uses: ["[[SOP-1008-track-work-across-sessions]]", "[[SOP-1006-start-work-and-archive-a-wip-folder]]", "[[SOP-1009-write-a-session-log-and-agent-journal]]", "[[WS-1002-weekly-review]]", "[[GL-1005-code-vs-instructions]]", "[[GL-1011-date-mentions-link-to-daily-notes]]"]
---
# WS-1005 Checkpoint

A session ends when you close the terminal, and nothing fires on its own.
The checkpoint is the forcing function: **you** type `/checkpoint`, and the
team answers five questions before the session is allowed to be over. Run it
whenever you stop for the day, and whenever a piece of work is done.

1. [SCRIPT] `Scripts/checkpoint.py` prints the facts: the last session
   log, which tasks changed since it, and every piece of work in the WiP room
   with its age and whether any open task still names it. Read it; do not
   re-derive it. The buckets themselves never leave, only the dated work
   inside them, and `Operations/` is read first because it is the bucket
   nothing closes from the outside.
2. [JUDGEMENT] **Tasks.** For each task the report lists as touched: if
   its work shipped, move it to `Tasks/done/YYYY/MM/` with a one-line
   outcome ([[SOP-1008-track-work-across-sessions|SOP-1008]]); if it is
   still open, leave it and write the unfinished part into the session
   log's Open threads. Unfinished work that has no task yet gets one now
   (`Scripts/new-task.py`). Propose cancelling what is dead; the user rules.
3. [JUDGEMENT] **WiP.** For each folder the report flags `LEAVE?`, propose
   archiving it ([[SOP-1006-start-work-and-archive-a-wip-folder|SOP-1006]]
   step 4). Archive only what the user confirms; a folder they name as
   ongoing stays, and the reason goes in the log.
4. [SCRIPT] **Date links.** Get the path of the content source's
   `link-dates-to-daily-notes` tool with
   `python3 "06 AI Team/AI Team Knowledge/Scripts/resolve.py" --tool link-dates-to-daily-notes`
   ([[GL-1013-sources-and-the-resolver|GL-1013]]), then run that path
   with `--fix`. It turns every date this session wrote into a note body into
   `[[YYYY-MM-DD]]` and creates the daily notes behind them
   ([[GL-1011-date-mentions-link-to-daily-notes|GL-1011]]). It runs before
   the log is written, so the log's own dates are linked too. Additive and
   idempotent; nothing to rule on.
5. [SCRIPT] **Session log.** `Scripts/new-session-log.py --agent aiden
   --slug <what-happened>`, then fill it per
   [[SOP-1009-write-a-session-log-and-agent-journal|SOP-1009]]: what
   happened, decisions, open threads. Agents that learned something
   durable append to their own `Journal/`.
6. [SCRIPT] **The receipt.** `Scripts/checkpoint.py --write-receipt
   --output "<the session log you just wrote>"` records what this session
   closed: the workflow, the session id, the outputs and their hashes, and
   anything knowingly left open (`--unresolved "..."`, repeatable).

   A receipt for an id that already exists is refused when the receipt on
   disk is a DIFFERENT session's — the evidence is the session log that
   receipt names, not the two sessions' `started` values, which are
   identical whenever both hold one minted id. Re-writing your own receipt
   (same log, after adding an output) still succeeds.

   **Rebuilding a receipt a session lost.** If a receipt was overwritten or
   deleted, rebuild it with the script, never by hand:
   `--write-receipt --reconstruct --session-id <the id the lost receipt
   used> --started <when that session really began> --finished <when it
   really ended>` plus the same `--output`/`--unresolved` lists. It refuses
   a missing `--started`, a `started` later than `finished`, and a prior
   receipt that turns out to belong to a different session. No hand-edited
   JSON.

   **Before removing a receipt, ask what it pins:** `--removing <id>` exits
   1 when a session log on disk is named only by that receipt. A minted id,
   or an id absent from `session.json`, is NOT evidence that a receipt is a
   phantom — on 2026-09-29 exactly that reasoning deleted a real session's
   receipt. A `local-...` receipt whose outputs are a session log and a
   journal entry belongs to a real session.
7. [SCRIPT] `Scripts/checkpoint.py --assert-logged --assert-dates-linked
   --assert-wikilinks` must exit 0. `--assert-logged` reads the receipt for
   THIS session, so a log written this morning can no longer close a session
   that ran this afternoon and wrote nothing. A checkpoint that ends without
   its own log is not a checkpoint, and neither is one that leaves a date
   pointing at nothing, nor one whose own files carry a link to a note that
   exists in neither vault.

   **The wikilink gate is scoped to this session's receipt `outputs`, never
   the whole tree.** The team tree's standing links to content-side records
   (`[[GL-1007-capture-and-where-things-go]]`, `[[WS-1001-daily-processing-run]]`)
   resolve in the content vault — they are the mode-B cross-tree dependency,
   not this session's debt — so a whole-tree verdict would fail every session
   for a dependency it did not create. `--assert-wikilinks` therefore runs the
   guard over the files the receipt declares, with the content root as a
   second root, and fails only on a link that resolves in NEITHER vault. GL-1005:
   a gate that cannot tell mine from pre-existing is a gate sessions learn to
   ignore. It is fail-closed: a guard it cannot run, or a receipt it cannot
   read, is a FAIL, never a pass.

   **Minted session id.** When the host sent no session id, the start
   ritual minted one (`local-...`) into `.mypka/state/session.json`, one
   file every session in the vault shares. It prints it as `YOUR SESSION
   ID is ...`. Pass that id on BOTH calls above: `--session-id <id>`.
   `checkpoint.py` refuses a bare call on a minted id, because a second
   session's start would have re-pointed the file and the bare call would
   close the wrong session's receipt. Why:
   [[2026-09-28-session-json-single-slot-concurrent-sessions]].

   **A host that sends its own id needs no flag at all.** Both scripts read
   a host variable first — `HERMES_SESSION_ID`, then `ICOR_SESSION_ID` —
   before the slot, so on such a host the id is picked up on its own, the
   receipt's window is derived from the id's own timestamp, and
   `--session-id` is belt-and-braces rather than the mechanism. A host id
   is unique per session, and the bare refusal above applies only where
   nothing exports one and the slot holds a mint.

   On a runtime with no session start hook there is no session id, and the
   assert says so and names the lever. Use `--assert-logged-today` there,
   knowing it is weaker: it proves a file exists with today's date on it
   and nothing else.

**What it does not do.** It does not process the Inbox or the Scratchpad
(that is [[WS-1001-daily-processing-run|WS-1001]], on your word), and it
does not look back over the week ([[WS-1002-weekly-review|WS-1002]] does,
with the same script at a 30-day window). It does not touch your task
tools outside this vault.

**Why a command and not a habit.** `CLAUDE.md` used to carry a three-line
"session close ritual" that fired when the model decided a session was
ending. Sessions do not announce their ending, so it rarely fired. A command
you type fires every time.
