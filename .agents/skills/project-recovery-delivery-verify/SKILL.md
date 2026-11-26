---
name: project-recovery-delivery-verify
description: use this when changing the recovery outbox, the owner digest scan, close-aware admit, or keyed-queue recovery. Run the TLA+ check and read a failing trace with the statechart skill.
---

# Recovery delivery check

One TLC run checks four safety invariants of `plugins/project_recovery/verify/DeliveryWake.tla`. A pass is the model inside the bounds below, not the whole product.

## Check

Tool: TLC 2.19, TLA+ tools release v1.7.4 (stable). Jar SHA-1 `bee4a54f3ee3d4afc347c3240ec2d9e93b075104`, SHA-256 `936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88`. Java: Temurin 21.0.13.1+2. The jar is not in this repo. v1.8.0 was a prerelease when this pin was taken; do not substitute it. Use one worker.

From the repo root, with that jar on the classpath:

```
java -XX:+UseParallelGC -Xmx512m -cp tla2tools.jar tlc2.TLC -workers 1 -coverage 1 -config plugins/project_recovery/verify/DeliveryWake.cfg plugins/project_recovery/verify/DeliveryWake.tla
```

Invariants, and the harm if one fails:

- `NoLostWake` — a settled wake was carried, and a finished scan does not drop an undelivered wake with no pin and no close or unreachable notice. Harm: the owner never sees the episode and nobody is told.
- `NoFalseAccept` — `accepted` has an admission id, and a live marker with no admission is not `accepted`. Harm: a send that never reached the owner is treated as delivered.
- `OneCarry` — one carry, plus at most one more after the named cache-loss step. Listing a carried episode is not another carry. Restart may submit once more and does not itself carry. Harm: the owner is woken again for an episode it already carried.
- `NoticeIndependence` — a notice-only scan does not submit. Harm: a membership notice wakes the owner.

Read the TLC output with the toolbox skill `statechart`.

## Bounds

These are the model, not product budgets. One owner and one key. Wake ids `w1` and `w2` share one delivery state and one digest. One notice id. At most three scans, one restart, one cache loss, and three submits. Invariants only. `Finished` may stutter between scans, so a deferred wake is not a lost wake. The memory arm of close-aware admit and unflagged submit are outside the model. Crashes are the named steps in the spec (`CrashAfterInsert`, `CrashBeforeAdmit`, `CrashAfterAdmit`), matching the keyed insert, the frame, and the admit write.

Named residuals stay in the model: `Restart` may allow one later submit while a digest is queued; `CacheLoss` may allow one later carry of a fresh episode; `OfferHuman` before `OfferDigest` is admission order, not a lock. A closed or unreachable pre-read still sends. O3 is the in-write `closed-by-user` refusal. `LookupConflict` requires `~same`. `NoticeSubmit` assigns `noticeSubmits`, and the notice-only guard disables it.

## Coverage

| Code | What the spec steps follow |
| --- | --- |
| `plugins/project_recovery/deliver.py` | `scan_owner`, `_apply_observed`, `_stall_notices`, `_settled_notices`, `render_digest` |
| `plugins/project_recovery/outbox.py` | `write_intent`, `remember_message`, `adopt_receipt` |
| `plugins/intercom/route.py` | `_queue_keyed`, `_ride`, `_resume_pinned`, `_take_outcome`, `_lookup_frame` |
| `plugins/intercom/record.py` | `insert_keyed_queue` |
| `plugins/intercom/client.py` | `deliver_sync` when the close flag is on |
| `gateway/session_close_aware.py` | flagged canonical target; the admit gate |
| `persistence/sqlite/authority/_admission_close.py` | user-close refusal inside the admit write |
| `persistence/sqlite/authority/admissions.py` | replay of the same principal, target, request id, and payload before that refusal |
| `persistence/sqlite/authority/_admission_lookup.py` | `found`, `proven_not_found`, `unavailable`, `conflict` |

A change touches this check when it edits those functions or the delivery-state names, the unreceipted-outbox rule, the keyed pin, or the close check inside the admit write.

## Sync

Commit: none

Base: `88815dd97fcc2445c68e068c7e0bec3a3b397dec`

The spec was checked against the uncommitted worktree copies of the files above. There is no commit to name. Advance this line only after a commit exists and this command has been run on that commit.

## When the result changes

Replay the trace against the code, one spec step to one code step. A step the code cannot take means the spec is wrong: fix the spec and run the command again. If the code can take every step, the invariant failure is a bug in the covered code: keep the trace, and do not weaken the invariant or the bound to make it pass.

When a change to the covered code is intended, edit the spec so its steps still match the code, then run the command. Confirm each invariant can still fail: outside this repo, copy the spec, break one guard for that invariant, run the same command, see that invariant fail, and delete the copy. Do not keep a broken spec in the product tree.
