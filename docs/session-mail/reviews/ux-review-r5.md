# UX review, round 5 (full re-review on the intercom base): session-mail (DER-701)

Reviewer: UX reviewer (designer role, review loop only). Date: 2026-11-09.

Under review: `docs/session-mail/ux.md` and `stories/sm-01…sm-22` at commit `9cba7fa6fd`. The
working tree has no changes to them.

Requirements:
- Alex's request, including the settled sections "Scope addition", "Delivery modes" and "Build on
  intercom";
- the brief (round 6, Refine pass `a945a2ddda`), on the recommended answers to SM-Q7…SM-Q11, SM-Q15
  and SM-Q16;
- `hld.md` (`923a6ff272`);
- the stated taste;
- the templates;
- open items from rounds 1–4.

## What holds

- **Template shape.** The UX doc has every required and optional section. All 22 stories have As
  a / I want / So that / Done when / Out of scope.
- **The interrupt sentence is Alex's, word for word** (`ux.md:192`, sm-17). It sits right after a
  plain statement of what interrupt does ("stops the current turn and runs your message now"), so
  the intent ("only interrupt on intention, default to steer or queue") reads clearly. The
  parameter table and J1 make `steer` the default. No gate or approval is added to interrupt, and
  `ux.md:424` says so.
- **The receipt names the applied mode**, as `requested` / `applied` / `applied_detail`
  (`ux.md:204`). Each `message` sentence and CLI line names the applied mode in words, and adds
  "asked: <requested>" when it is weaker (`ux.md:206-213`, `:360`, `log` and `status`). The
  fallback chain (J9, sm-17, sm-18) matches the "Delivery modes" section: interrupt > steer > queue,
  and an idle target starts a turn in any mode.
- **All hosts are covered:**
  - dashboard and desktop (J4–J7, sm-09);
  - classic CLI and Ink TUI (J10, "Terminal sessions", sm-19);
  - Telegram (J11, the gateway section, sm-20);
  - many sessions in one process (sm-22).
- **The failures each have their own wording and exit code:** no seam, a host that refuses, no
  dashboard, no endpoint, no gateway, not reachable, delivery unknown, lost after handover, a reply
  that is not delivered, and a message to your own session.
- **Nothing forbidden is added.** Intercom's four caps are removed (sm-07). There are still no
  holds, retries or pending states.
- **Earlier rounds:**
  - **R4-1 is fixed.** The first sentence is `Message another Hermes session; never send an empty
    message.`, exactly 60 characters. `_short_desc` returns it whole, because it checks
    `len(text) <= 60` (`tools/tool_search_catalog.py:220`).
  - **R4-2 is fixed.** Footer line 1 now says to call `tool_describe` and then `tool_call`.
  - **R4-3 is fixed:** sm-16 is now checkable from the footer alone; sm-05's wording is fixed;
    F11 has the hand-on clause; and 4090 now appears only as the wake-path race.
  - Every round-1 to round-3 fix carries over in the new frame: the closing line, the relabel rule
    for the 📡 emoji, footer line 2 always writing the block, the stopped-turn rule, the
    script-sender line 2, the "delivery unknown" split and the transcript check.
- **"For the architect" items 1–6** are clearly flagged as changes to the new HLD:
  - header order and the D3 anchor (HLD D2/D3 still use `📡 hermes@"…" (…, not Alex) says:`);
  - "message" instead of "mail";
  - the script header form;
  - `log` versus `list`;
  - the first sentence instead of intercom's opening;
  - the `user_name` setting.

  None of them adds a cap, hold, retry or gate.

## Findings

### R5-1. On a classic CLI or gateway target, `status` "not found" can invite a duplicate (blocking)

- **Where:** `ux.md:389` (the "not found" advice), `ux.md:223` (the delivery-unknown receipt),
  architect item 7 (`ux.md:482`); sm-12, sm-15.
- **Requirement broken:** the R2-1 fix exists so that a sender facing "delivery unknown" can decide
  whether to send again without causing a duplicate. Failures must be covered: delivery unknown,
  and a session held by a command-line process.
- **What happens:**
  - Architect item 7 itself notes that classic CLI and gateway queues write no row until the message
    runs.
  - A message handed to a busy terminal or Telegram turn can sit in that queue for many minutes
    while the receipt is lost: the socket answer never came back, so the result is "delivery
    unknown".
  - For all that time, `status` prints "not found (yet)". After a minute the advice says "sending
    again will not duplicate it", which is false here. The target then runs the message twice.
  - Item 7 says "the advice in `status` still holds". It does not hold on these two hosts.
- **Fix:**
  - Make the advice depend on the host, which the record already stores (`host`). For a classic
    CLI or gateway host, `status` can also read the target's live state, read only. Intercom `list`
    already shows busy or idle, and the lease registry has it too. For example:
    - `not found in the target's transcript (yet); the target is still busy in its terminal, so a
      queued message may not have run. Run status again after its current turn ends.`
    - Use the existing wording once the target is idle, or once its host is gone.
  - Correct architect item 7 so it asks the HLD for this. Add a Done-when to sm-12 and sm-15.
  - This is a read, not a timer or a hold.

### R5-2. The `ask` footer drops `[SILENT]`, but every footer must carry it (blocking)

- **Where:** the `ask` row in the footer variants (`ux.md:293`, "line 5, `[SILENT]`, is dropped");
  sm-07 (now "every `send` footer variant"); sm-21.
- **Requirement broken:** the stated taste: the no-empty-replies rule **and [SILENT]** must be in
  the tool description and in **every delivered message's footer**. Decision 6 says the same.
- **What happens:**
  - The designer's reason is sound: a `[SILENT]` final answer would leave the asker waiting until
    the timeout, up to 600 seconds.
  - But dropping the token from the footer breaks the stated rule. It also leaves the target
    without a way to say "nothing to add" quickly.
- **Fix:** keep `[SILENT]` in the `ask` footer, in a form that does not leave the asker waiting.
  For example: "If you have nothing to add, reply once with message="[SILENT]"; the asker gets
  that at once instead of waiting." Then:
  - sm-21 needs one Done-when: a `reply` whose message is `[SILENT]` returns to the asker as
    "nothing to add".
  - sm-07 can go back to "every footer variant".

  If the designer thinks the rule should not apply to `ask`, that changes a stated requirement,
  so it is a question for the operator, not a design choice.

### R5-3. sm-01 forbids `held`, which the receipt keeps (minor)

- **Where:** sm-01 ("No receipt says "pending", "held" or "will retry"") compared with
  `ux.md:204` and `:225` and HLD D4. Intercom's `receipt` field is kept for compatibility, and
  `held` in it means queued.
- **Fix:** "No receipt `message` sentence says pending or will retry. The compatibility `receipt`
  field may be `held`, meaning queued."

### R5-4. Interrupt receipt and header wording for a hard interrupt (minor)

- **Where:** `ux.md:208` and J8 step 2.
- **What happens:** the `interrupted` sentence says the message "runs now". With
  `applied_detail = hard-interrupt`, the turn is stopped and the message runs **next**, as J8 and
  sm-18 say themselves.
- **Fix:** give the sentence a hard-interrupt variant: "… stopped the running turn of "…"; the
  message runs as its next turn."

### R5-5. Classic CLI: a turn that starts while the person is typing is not checked (minor)

- **Where:** `ux.md:330` ("`started` (idle at the prompt)"), `ux.md:332` ("half-typed input stays
  in the prompt"); sm-19; "Still to check".
- **Requirement:** a message must not cost Alex his draft, on every host.
- **What happens:** at an idle classic-CLI prompt, the input loop is reading the person's typing.
  The design says the turn starts "as if typed", and that the half-typed text stays. Nothing shows
  how a turn starts from `_pending_input` while the prompt is being read. "Still to check" lists
  the CLI's notices but not this case.
- **Fix:** add "an idle classic CLI with half-typed input: the message starts its turn and the
  draft survives" to "Still to check", and to sm-19 as a Trial-backed Done-when.

### R5-6. Gateway injection switched off is not covered (minor)

- **Where:** F3 and F4, and the gateway section. Compare HLD B4(a): mail steers or interrupts a
  gateway turn only with `allow_gateway_injection: true`.
- **What happens:** the design does not say what a sender sees when that setting is off. That
  could happen in an upstream install, or before house-infra applies the setting. Hermes's own
  default then queues internal events, so the receipt may say `queued` when `interrupt` was asked,
  or the host refuses.
- **Fix:** name the outcome (for example "applied `queue` (asked: interrupt; gateway injection
  is off)", or a refusal with exit 4). Add it to "For the architect" if the HLD has to choose.

### R5-7. Smaller points (minor)

- **The `30–42 characters` claim** (`ux.md:259`, `:443`). An `ask` sent with interrupt reads
  `📡 Not Alex · interrupt · waiting for your reply`, which is about 48 characters. Either widen the
  range, or note that this one case wraps after "interrupt ·".
- **The admonition on the CLI.** Cron scripts are often written by sessions that read
  `hermes intercom send --help`, not the tool description. Putting Alex's interrupt sentence in
  the `--delivery` help text costs nothing and keeps one rule everywhere. This is optional; the
  requirement names only the tool description.

Verdict: changes needed
Reviewed: bbbde6a97e2bbda97458a4408408623a9a0224356b1186968c0312d6e2914113
