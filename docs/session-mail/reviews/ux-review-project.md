# UX review, delta: project addressing (DER-701)

Reviewer: UX reviewer (designer role, review loop only). Date: 2026-11-11.

Under review: `git diff 9b2b36e4b2 HEAD -- docs/session-mail/ux.md docs/session-mail/stories
docs/session-mail/mockups`, with HEAD at `3a1ed9c4e3`. The working tree has no changes to these
files.

Requirements:
- `prompts/project-addressing-spec.md` (Alex: "detect if our project plugin is there and not
  offer that if it's not; we can't rely on naming");
- the LLD at `01e29d8df8` (B3 rule 3 and "Project addressing is available", B9 exit table, G-4);
- the stated taste: the description short and unambiguous, refusals clear.

**How I checked:** I read every changed line. I searched `ux.md`, the stories, the README and
mockup A's text for title-convention, "Model Master", `@model-testing`, `@budgeting` and `@project`
uses. I compared both description variants and the refusal texts with the spec and LLD B3.

## What holds

- **No title-convention or "Model Master" reliance remains.**
  - Every `<name> — Orchestrator` mention is now a statement that there is no such fallback
    (§ "Project addressing", sm-02).
  - SM-Q10 is withdrawn in the decision list and in "Open questions".
  - "Model Master" appears nowhere in `ux.md`, the stories or mockup A.
  - The journeys address by id or exact title: J1 finds Budgeting with `list` (`query`) and sends
    to `local-1b9e04d7`; J8 reuses that id; J3's cron job uses the exact title.
  - The relay-skill line no longer offers `@project`.
  - In mockup A, `@budgeting` appears only in the new refusal state.
- **Both description variants are right.**
  - The default (feature absent, the launch state) is labelled as such. Its `to` sentence is "a
    session id (…), an exact title, or Home", with no `@` anywhere in the description.
  - The present variant differs only in that sentence, adding `@<project-slug> (that project's
    owner session)`.
  - The variant is built at register, so a change needs the gateway restart. sm-02 checks that
    the description *and schema* never mention `@` when the feature is absent.
  - The catalog sentence and Alex's interrupt sentence are untouched.
- **Detection matches the spec and LLD B3:** `settings.project_plugin` enabled, plus the
  `owner_session_id` column, checked at register and on each call. A missing file or a read error
  means "not available".
- **The `project-addressing-unavailable` refusal** is the spec's sentence word for word, in F1b, the
  receipts and sm-02. Exit 3. It also tells the model what to do next ("Use list … and address the
  session by id").
- **`list` keeps `project`** for discovery, from project folders and the working directory, in both
  states.
- **Nothing reopened.** No cap, hold or gate is added, and nothing else in the accepted design
  changes.

## Findings (minor, not blocking)

### PA-1. The `no-owner-set` wording differs between `ux.md` and the LLD

- **Where:**
  - `ux.md` F1b, § "Receipts" and the README: `Nothing was sent: project "<slug>" has no owner
    session set. Use list (filter by project) and address the session by id.`
  - LLD B3 rule 3: `Project @<slug> has no owner session set. Address a session by id (from
    list).`
- **What happens:** the builder's framing tests (LLD G-4) check the text, so the two documents
  must agree. The `ux.md` version is the clearer one: it says nothing was sent, and it repeats the
  same next step as `project-addressing-unavailable`.
- **Fix:** have the LLD quote `ux.md`'s sentence (add it to "For the architect").

### PA-2. An unknown project slug, when the feature is present, is not worded

- **Where:** LLD B3 rule 3: with the feature present, an `@<slug>` with no matching (unarchived)
  project is `refused` / `unknown`, listing "up to 5 project slugs as candidates". `ux.md` F1 now
  describes only an unknown *title* (closest titles), and sm-03 says "listing the closest titles".
- **Fix:** add one clause to F1 and sm-03: "with the project feature present, an unknown
  `@<slug>` lists the closest project slugs instead".

### PA-3. Small wording points

- **The `project-addressing-unavailable` text has no "Nothing was sent" prefix.** Every other
  `refused` row starts "Nothing was sent". This one is the spec's exact sentence, so keep it, and
  say in the receipts row that nothing was sent.
- **"Use list (filter by project)" doesn't name the parameter.** The tool's parameter is `query`,
  which filters on title or project. If the manager allows a change to the spec's text, "Use list
  with query=<project>" would be more direct for a model. Otherwise leave it.
- **Mockups B and C** still show `@budgeting`-style sends and `reply expected`. The README says
  only layout A is updated, which is fine while A is the recommendation.

Verdict: meets requirements
Reviewed: a928fb8688857ee4041db8df502fd2de72f06f97f4a45704dd2410d53326da2a
