----------------------------- MODULE DeliveryWake -----------------------------
(***************************************************************************)
(* Per-key recovery delivery. One logical owner, one keyed queue, two     *)
(* wake episodes that share one digest, and one notice episode.           *)
(*                                                                         *)
(* w1 and w2 share one delivery state because scan_owner sends one digest *)
(* for one owner (plugins/project_recovery/deliver.py, render_digest).    *)
(*                                                                         *)
(* Atomic steps follow the code:                                           *)
(*   deliver.scan_owner, _apply_observed, _stall_notices                   *)
(*   route._queue_keyed, _ride, _resume_pinned, _take_outcome              *)
(*   record.insert_keyed_queue                                             *)
(*   the admit write's replay, then the user-close check, then insert     *)
(*                                                                         *)
(* Named residuals, and the only steps allowed to add a carry beyond the  *)
(* first: CacheLoss (fresh episode after state/ is deleted) and Restart   *)
(* (one extra submit while a digest is queued; it does not itself carry). *)
(***************************************************************************)

EXTENDS Integers, FiniteSets

VARIABLES
  pc, activity, mode, wake, notice,
  outbox, msg, scanAdm, ownerAdm, rowAdm,
  queue, marker, framed, offered, carried,
  carryN, carryC, fresh, named, closed,
  submits, noticeSubmits, stall, held, human,
  scans, losses, restarts, receipt, pendingCache,
  listed, same

vars == <<pc, activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
          rowAdm, queue, marker, framed, offered, carried, carryN, carryC,
          fresh, named, closed, submits, noticeSubmits, stall, held, human,
          scans, losses, restarts, receipt, pendingCache, listed, same>>

WakeIds == {"w1", "w2"}
MaxScan == 3

Undelivered == mode # "notice" /\ wake = "undelivered"
NoticeOpen == notice \in {"undelivered", "noticed"}
WakeOpen == wake \in {"undelivered", "accepted", "carried"}
NoticeOnlyCond == NoticeOpen /\ ~WakeOpen
ReplayCond == ownerAdm # "none" /\ same

\* A completed idle/closed/unreachable scan must still account for an open wake.
Accounted ==
  \/ mode = "notice"
  \/ wake # "undelivered"
  \/ outbox # "none"
  \/ held
  \/ "o3" \in named
  \/ "o4" \in named
  \/ activity = "running"
  \/ scans = 0
  \/ pendingCache

(***************************************************************************)
(* No lost wake: a settled wake was carried, and a finished scan does not *)
(* drop an undelivered wake without a pin or a close/unreachable notice.  *)
(* Harm: the owner never sees the episode and nobody is told.             *)
(***************************************************************************)
NoLostWake ==
  /\ wake \in {"absent", "undelivered", "accepted", "carried", "settled"}
  /\ (wake = "settled" => carried = "turn")
  /\ (mode = "notice" => wake = "absent")
  /\ (mode = "wake" => notice = "absent")
  /\ (pc = "between" => Accounted)

(***************************************************************************)
(* No false accept: accepted requires an admission id. A live marker with *)
(* no admission is not accepted. Harm: the scanner treats a send that     *)
(* never reached the owner as delivered.                                  *)
(***************************************************************************)
NoFalseAccept ==
  /\ (wake = "accepted" => scanAdm # "none")
  /\ (marker /\ rowAdm = "none" => wake # "accepted")

(***************************************************************************)
(* One carry, except the cache-loss step named by fresh/carryC. A later   *)
(* digest that lists the episode (listed) is not another carry. Restart   *)
(* may submit once more and does not increment a carry by itself.         *)
(* Harm: the owner is woken again for an episode it already carried.      *)
(***************************************************************************)
OneCarry ==
  /\ carryN <= 1
  /\ carryC <= losses

(***************************************************************************)
(* Notice independence: a notice-only scan performs no submit.            *)
(* Harm: a membership notice wakes the owner.                             *)
(***************************************************************************)
NoticeIndependence == noticeSubmits = 0

TypeOK ==
  /\ pc \in {"between", "advance", "settle", "stall", "gate", "write",
             "insert", "frame", "admit", "store", "adopt", "lookup", "crashed"}
  /\ activity \in {"idle", "running", "closed", "unreachable"}
  /\ mode \in {"wake", "notice", "both"}
  /\ wake \in {"absent", "undelivered", "accepted", "carried", "settled"}
  /\ notice \in {"absent", "undelivered", "noticed"}
  /\ outbox \in {"none", "intent", "receipt"}
  /\ msg \in {"none", "m1"}
  /\ scanAdm \in {"none", "a1"}
  /\ ownerAdm \in {"none", "a1"}
  /\ rowAdm \in {"none", "a1"}
  /\ queue \in {"empty", "pending", "refused"}
  /\ marker \in BOOLEAN
  /\ framed \in BOOLEAN
  /\ offered \in {"none", "turn"}
  /\ carried \in {"none", "turn"}
  /\ carryN \in 0..2
  /\ carryC \in 0..2
  /\ fresh \in BOOLEAN
  /\ named \subseteq {"o3", "o4", "o5", "noprog"}
  /\ closed \in BOOLEAN
  /\ submits \in 0..3
  /\ noticeSubmits \in 0..1
  /\ stall \in 0..2
  /\ held \in BOOLEAN
  /\ human \in 0..1
  /\ scans \in 0..MaxScan
  /\ losses \in 0..1
  /\ restarts \in 0..1
  /\ receipt \in {"none", "queued", "unknown", "terminal"}
  /\ pendingCache \in BOOLEAN
  /\ listed \in BOOLEAN
  /\ same \in BOOLEAN

Base ==
  /\ pc = "between"
  /\ activity = "idle"
  /\ outbox = "none"
  /\ msg = "none"
  /\ scanAdm = "none"
  /\ ownerAdm = "none"
  /\ rowAdm = "none"
  /\ queue = "empty"
  /\ marker = FALSE
  /\ framed = FALSE
  /\ offered = "none"
  /\ carried = "none"
  /\ carryN = 0
  /\ carryC = 0
  /\ fresh = FALSE
  /\ named = {}
  /\ closed = FALSE
  /\ submits = 0
  /\ noticeSubmits = 0
  /\ stall = 0
  /\ held = FALSE
  /\ human = 0
  /\ scans = 0
  /\ losses = 0
  /\ restarts = 0
  /\ receipt = "none"
  /\ pendingCache = FALSE
  /\ listed = FALSE
  /\ same = FALSE

Init ==
  /\ Base
  /\ \/ /\ mode = "wake" /\ wake = "undelivered" /\ notice = "absent"
     \/ /\ mode = "notice" /\ wake = "absent" /\ notice = "undelivered"
     \/ /\ mode = "both" /\ wake = "undelivered" /\ notice = "undelivered"

\* Environment, only between scans, plus a close while the scanner is dead.
UserCloses ==
  /\ pc \in {"between", "crashed"}
  /\ ~closed
  /\ closed' = TRUE
  /\ UNCHANGED <<pc, activity, mode, wake, notice, outbox, msg, scanAdm,
       ownerAdm, rowAdm, queue, marker, framed, offered, carried, carryN,
       carryC, fresh, named, submits, noticeSubmits, stall, held, human,
       scans, losses, restarts, receipt, pendingCache, listed, same>>

HumanArrives ==
  /\ pc = "between"
  /\ human = 0
  /\ ~closed
  /\ human' = 1
  /\ UNCHANGED <<pc, activity, mode, wake, notice, outbox, msg, scanAdm,
       ownerAdm, rowAdm, queue, marker, framed, offered, carried, carryN,
       carryC, fresh, named, closed, submits, noticeSubmits, stall, held,
       scans, losses, restarts, receipt, pendingCache, listed, same>>

ReceiptUnknown ==
  /\ pc = "between"
  /\ wake \in {"accepted", "carried"}
  /\ receipt \in {"none", "queued"}
  /\ receipt' = "unknown"
  /\ UNCHANGED <<pc, activity, mode, wake, notice, outbox, msg, scanAdm,
       ownerAdm, rowAdm, queue, marker, framed, offered, carried, carryN,
       carryC, fresh, named, closed, submits, noticeSubmits, stall, held,
       human, scans, losses, restarts, pendingCache, listed, same>>

ReceiptTerminal ==
  /\ pc = "between"
  /\ wake \in {"accepted", "carried"}
  /\ receipt \in {"queued", "unknown"}
  /\ receipt' = "terminal"
  /\ UNCHANGED <<pc, activity, mode, wake, notice, outbox, msg, scanAdm,
       ownerAdm, rowAdm, queue, marker, framed, offered, carried, carryN,
       carryC, fresh, named, closed, submits, noticeSubmits, stall, held,
       human, scans, losses, restarts, pendingCache, listed, same>>

\* Marker from an earlier owner instance is dead. One extra submit may follow.
Restart ==
  /\ pc = "between"
  /\ restarts = 0
  /\ queue = "pending"
  /\ marker
  /\ restarts' = 1
  /\ marker' = FALSE
  /\ UNCHANGED <<pc, activity, mode, wake, notice, outbox, msg, scanAdm,
       ownerAdm, rowAdm, queue, framed, offered, carried, carryN, carryC,
       fresh, named, closed, submits, noticeSubmits, stall, held, human,
       scans, losses, receipt, pendingCache, listed, same>>

\* state/ is deleted. The intercom row remains. The next carry is the exception.
CacheLoss ==
  /\ pc = "between"
  /\ losses = 0
  /\ losses' = 1
  /\ fresh' = TRUE
  /\ pendingCache' = TRUE
  /\ outbox' = "none"
  /\ scanAdm' = "none"
  /\ msg' = "none"
  /\ carried' = "none"
  /\ offered' = "none"
  /\ named' = {}
  /\ held' = FALSE
  /\ stall' = 0
  /\ listed' = FALSE
  /\ wake' = IF mode = "notice" THEN wake ELSE "undelivered"
  /\ notice' = IF mode = "wake" THEN notice ELSE "undelivered"
  /\ UNCHANGED <<pc, activity, mode, ownerAdm, rowAdm, queue, marker, framed,
       carryN, carryC, closed, submits, noticeSubmits, human, scans, restarts,
       receipt, same>>

OfferHuman ==
  /\ pc = "between"
  /\ human = 1
  /\ human' = 0
  /\ UNCHANGED <<pc, activity, mode, wake, notice, outbox, msg, scanAdm,
       ownerAdm, rowAdm, queue, marker, framed, offered, carried, carryN,
       carryC, fresh, named, closed, submits, noticeSubmits, stall, held,
       scans, losses, restarts, receipt, pendingCache, listed, same>>

OfferDigest ==
  /\ pc = "between"
  /\ human = 0
  /\ offered = "none"
  /\ ownerAdm # "none"
  /\ offered' = "turn"
  /\ UNCHANGED <<pc, activity, mode, wake, notice, outbox, msg, scanAdm,
       ownerAdm, rowAdm, queue, marker, framed, carried, carryN, carryC,
       fresh, named, closed, submits, noticeSubmits, stall, held, human,
       scans, losses, restarts, receipt, pendingCache, listed, same>>

ScanStart ==
  /\ pc = "between"
  /\ scans < MaxScan
  /\ \E a \in {"idle", "running", "closed", "unreachable"}:
       /\ activity' = a
       /\ scans' = scans + 1
       /\ pendingCache' = FALSE
       /\ pc' = "advance"
       /\ UNCHANGED <<mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
            rowAdm, queue, marker, framed, offered, carried, carryN, carryC,
            fresh, named, closed, submits, noticeSubmits, stall, held, human,
            losses, restarts, receipt, listed, same>>

CanCarry ==
  mode # "notice" /\ wake = "accepted" /\ offered = "turn" /\ carried = "none"

DoCarry ==
  /\ pc = "advance"
  /\ CanCarry
  /\ wake' = "carried"
  /\ carried' = "turn"
  /\ IF fresh
     THEN /\ carryC' = carryC + 1
          /\ fresh' = FALSE
          /\ UNCHANGED carryN
     ELSE /\ carryN' = carryN + 1
          /\ UNCHANGED <<carryC, fresh>>
  /\ pc' = "settle"
  /\ UNCHANGED <<activity, mode, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, named, closed, submits,
       noticeSubmits, stall, held, human, scans, losses, restarts, receipt,
       pendingCache, listed, same>>

SkipCarry ==
  /\ pc = "advance"
  /\ ~CanCarry
  /\ pc' = "settle"
  /\ listed' = IF mode # "notice" /\ wake = "carried" /\ offered = "turn"
               THEN TRUE ELSE listed
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, same>>

CanSettle ==
  wake = "carried" /\ activity = "idle" /\ receipt = "terminal"
  /\ "noprog" \notin named

DoSettle ==
  /\ pc = "settle"
  /\ CanSettle
  /\ wake' = "settled"
  /\ named' = named \cup {"noprog"}
  /\ pc' = "stall"
  /\ UNCHANGED <<activity, mode, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       closed, submits, noticeSubmits, stall, held, human, scans, losses,
       restarts, receipt, pendingCache, listed, same>>

SkipSettle ==
  /\ pc = "settle"
  /\ ~CanSettle
  /\ pc' = "stall"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed, same>>

UnknownNow == scanAdm # "none" /\ receipt = "unknown" /\ "o5" \notin named
QueuedNow ==
  activity = "idle" /\ receipt = "queued" /\ scanAdm # "none" /\ stall < 2

StallUnknown ==
  /\ pc = "stall"
  /\ UnknownNow
  /\ named' = named \cup {"o5"}
  /\ pc' = "gate"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       closed, submits, noticeSubmits, stall, held, human, scans, losses,
       restarts, receipt, pendingCache, listed, same>>

StallQueued ==
  /\ pc = "stall"
  /\ ~UnknownNow
  /\ QueuedNow
  /\ stall' = stall + 1
  /\ named' = IF stall + 1 >= 2 THEN named \cup {"o5"} ELSE named
  /\ pc' = "gate"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       closed, submits, noticeSubmits, held, human, scans, losses, restarts,
       receipt, pendingCache, listed, same>>

SkipStall ==
  /\ pc = "stall"
  /\ ~UnknownNow
  /\ ~QueuedNow
  /\ pc' = "gate"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed, same>>

AtGate == pc = "gate"
NotRunningDefer == ~(activity = "running" /\ Undelivered)
Sendable == activity \in {"idle", "closed", "unreachable"}

NoticeOnly ==
  /\ AtGate
  /\ NoticeOnlyCond
  /\ notice' = "noticed"
  /\ pc' = "between"
  /\ UNCHANGED <<activity, mode, wake, outbox, msg, scanAdm, ownerAdm, rowAdm,
       queue, marker, framed, offered, carried, carryN, carryC, fresh, named,
       closed, submits, noticeSubmits, stall, held, human, scans, losses,
       restarts, receipt, pendingCache, listed, same>>

\* Enabled only when the notice-only guard is false: NoticeOnlyCond includes ~WakeOpen.
NoticeSubmit ==
  /\ AtGate
  /\ NoticeOnlyCond
  /\ WakeOpen
  /\ noticeSubmits' = 1
  /\ pc' = "between"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, stall, held, human, scans, losses, restarts,
       receipt, pendingCache, listed, same>>

DeferRunning ==
  /\ AtGate
  /\ ~NoticeOnlyCond
  /\ activity = "running"
  /\ Undelivered
  /\ pc' = "between"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed, same>>

HoldSkip ==
  /\ AtGate
  /\ ~NoticeOnlyCond
  /\ Sendable
  /\ held
  /\ Undelivered
  /\ pc' = "between"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed, same>>

BeginSend ==
  /\ AtGate
  /\ ~NoticeOnlyCond
  /\ Sendable
  /\ ~held
  /\ Undelivered
  /\ pc' = "write"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed, same>>

IdleNoSend ==
  /\ AtGate
  /\ ~NoticeOnlyCond
  /\ NotRunningDefer
  /\ ~(Sendable /\ Undelivered)
  /\ pc' = "between"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed, same>>

ReuseIntent ==
  /\ pc = "write"
  /\ outbox = "intent"
  /\ pc' = "insert"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed, same>>

WriteIntent ==
  /\ pc = "write"
  /\ outbox # "intent"
  /\ outbox' = "intent"
  /\ scanAdm' = "none"
  /\ msg' = "none"
  /\ pc' = "insert"
  /\ UNCHANGED <<activity, mode, wake, notice, ownerAdm, rowAdm, queue, marker,
       framed, offered, carried, carryN, carryC, fresh, named, closed, submits,
       noticeSubmits, stall, held, human, scans, losses, restarts, receipt,
       pendingCache, listed, same>>

PinUnsent ==
  /\ pc = "insert"
  /\ queue = "pending"
  /\ rowAdm = "none"
  /\ same' = TRUE
  /\ pc' = "lookup"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed>>

PinRefusal ==
  /\ pc = "insert"
  /\ queue = "refused"
  /\ held' = TRUE
  /\ named' = named \cup {"o3"}
  /\ pc' = "between"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       closed, submits, noticeSubmits, stall, human, scans, losses,
       restarts, receipt, pendingCache, listed, same>>

\* Flagged retry of a live admitted wake: copy the id, do not submit.
RideCopy ==
  /\ pc = "insert"
  /\ queue = "pending"
  /\ rowAdm # "none"
  /\ marker
  /\ pc' = "adopt"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed, same>>

FreshInsert ==
  /\ pc = "insert"
  /\ queue # "refused"
  /\ ~(queue = "pending" /\ rowAdm = "none")
  /\ ~(queue = "pending" /\ rowAdm # "none" /\ marker)
  /\ queue' = "pending"
  /\ marker' = TRUE
  /\ framed' = FALSE
  /\ rowAdm' = "none"
  /\ msg' = "m1"
  /\ same' = FALSE
  /\ pc' = "frame"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, scanAdm, ownerAdm,
       offered, carried, carryN, carryC, fresh, named, closed, submits,
       noticeSubmits, stall, held, human, scans, losses, restarts, receipt,
       pendingCache, listed>>

\* Foreign admission at the frame: same stays false, so lookup can conflict.
DigestMismatch ==
  /\ pc = "frame"
  /\ ~same
  /\ ownerAdm = "none"
  /\ submits < 3
  /\ ownerAdm' = "a1"
  /\ submits' = submits + 1
  /\ pc' = "lookup"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, rowAdm,
       queue, marker, framed, offered, carried, carryN, carryC, fresh, named,
       closed, noticeSubmits, stall, held, human, scans, losses, restarts,
       receipt, pendingCache, listed, same>>

FrameFresh ==
  /\ pc = "frame"
  /\ framed' = TRUE
  /\ pc' = "admit"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, offered, carried, carryN, carryC, fresh, named,
       closed, submits, noticeSubmits, stall, held, human, scans, losses,
       restarts, receipt, pendingCache, listed, same>>

\* Death after the frame is stored and before the admit write.
CrashBeforeAdmit ==
  /\ pc = "admit"
  /\ pc' = "crashed"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed, same>>

CrashAfterInsert ==
  /\ pc = "frame"
  /\ pc' = "crashed"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed, same>>

\* Exact replay of the same request returns the existing admission and is not re-judged.
AdmitReplay ==
  /\ pc = "admit"
  /\ ReplayCond
  /\ same' = TRUE
  /\ pc' = "store"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed>>

AdmitNew ==
  /\ pc = "admit"
  /\ ~ReplayCond
  /\ ~closed
  /\ submits < 3
  /\ ownerAdm' = "a1"
  /\ submits' = submits + 1
  /\ same' = TRUE
  /\ pc' = "store"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, rowAdm,
       queue, marker, framed, offered, carried, carryN, carryC, fresh, named,
       closed, noticeSubmits, stall, held, human, scans, losses, restarts,
       receipt, pendingCache, listed>>

AdmitRefuse ==
  /\ pc = "admit"
  /\ ~ReplayCond
  /\ closed
  /\ ownerAdm = "none"
  /\ queue' = "refused"
  /\ marker' = FALSE
  /\ held' = TRUE
  /\ named' = named \cup {"o3"}
  /\ pc' = "between"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, framed, offered, carried, carryN, carryC, fresh, closed,
       submits, noticeSubmits, stall, human, scans, losses, restarts, receipt,
       pendingCache, listed, same>>

AdmitRefuseNew ==
  /\ pc = "admit"
  /\ ~ReplayCond
  /\ closed
  /\ ownerAdm # "none"
  /\ queue' = "refused"
  /\ marker' = FALSE
  /\ held' = TRUE
  /\ named' = named \cup {"o3"}
  /\ pc' = "between"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, framed, offered, carried, carryN, carryC, fresh, closed,
       submits, noticeSubmits, stall, human, scans, losses, restarts, receipt,
       pendingCache, listed, same>>

StoreRow ==
  /\ pc = "store"
  /\ rowAdm' = ownerAdm
  /\ pc' = "adopt"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       queue, marker, framed, offered, carried, carryN, carryC, fresh, named,
       closed, submits, noticeSubmits, stall, held, human, scans, losses,
       restarts, receipt, pendingCache, listed, same>>

CrashAfterAdmit ==
  /\ pc = "store"
  /\ pc' = "crashed"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed, same>>

Adopt ==
  /\ pc = "adopt"
  /\ rowAdm # "none" \* accepted only with an admission id
  /\ scanAdm' = rowAdm
  /\ outbox' = "receipt"
  /\ wake' = IF mode = "notice" THEN wake ELSE "accepted"
  /\ receipt' = "queued"
  /\ pc' = "between"
  /\ UNCHANGED <<activity, mode, notice, msg, ownerAdm, rowAdm, queue, marker,
       framed, offered, carried, carryN, carryC, fresh, named, closed, submits,
       noticeSubmits, stall, held, human, scans, losses, restarts,
       pendingCache, listed, same>>

Resume ==
  /\ pc = "crashed"
  /\ pc' = "lookup"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed, same>>

\* A second physical RPC of the same pinned frame. The admit write replays it.
DuplicateSubmit ==
  /\ pc = "lookup"
  /\ ownerAdm # "none"
  /\ same
  /\ pc' = "admit"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed, same>>

LookupFound ==
  /\ pc = "lookup"
  /\ ownerAdm # "none"
  /\ same
  /\ pc' = "store"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed, same>>

\* A foreign admission (same is false). A matching pin cannot take this step.
LookupConflict ==
  /\ pc = "lookup"
  /\ ownerAdm # "none"
  /\ ~same
  /\ named' = named \cup {"o4"}
  /\ pc' = "between"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       closed, submits, noticeSubmits, stall, held, human, scans, losses,
       restarts, receipt, pendingCache, listed, same>>

LookupUnavailable ==
  /\ pc = "lookup"
  /\ named' = named \cup {"o4"}
  /\ pc' = "between"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       closed, submits, noticeSubmits, stall, held, human, scans, losses,
       restarts, receipt, pendingCache, listed, same>>

LookupMissing ==
  /\ pc = "lookup"
  /\ ownerAdm = "none"
  /\ framed
  /\ same' = TRUE
  /\ pc' = "admit"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, framed, offered, carried, carryN, carryC, fresh,
       named, closed, submits, noticeSubmits, stall, held, human, scans,
       losses, restarts, receipt, pendingCache, listed>>

LookupUnframed ==
  /\ pc = "lookup"
  /\ ownerAdm = "none"
  /\ ~framed
  /\ framed' = TRUE
  /\ same' = TRUE
  /\ pc' = "admit"
  /\ UNCHANGED <<activity, mode, wake, notice, outbox, msg, scanAdm, ownerAdm,
       rowAdm, queue, marker, offered, carried, carryN, carryC, fresh, named,
       closed, submits, noticeSubmits, stall, held, human, scans, losses,
       restarts, receipt, pendingCache, listed>>

Finished ==
  /\ pc = "between"
  /\ UNCHANGED vars

Next ==
  \/ UserCloses \/ HumanArrives \/ ReceiptUnknown \/ ReceiptTerminal
  \/ Restart \/ CacheLoss \/ OfferHuman \/ OfferDigest
  \/ ScanStart \/ DoCarry \/ SkipCarry \/ DoSettle \/ SkipSettle
  \/ StallUnknown \/ StallQueued \/ SkipStall
  \/ NoticeOnly \/ NoticeSubmit \/ DeferRunning
  \/ HoldSkip \/ BeginSend \/ IdleNoSend
  \/ ReuseIntent \/ WriteIntent
  \/ PinUnsent \/ PinRefusal \/ RideCopy \/ FreshInsert
  \/ DigestMismatch \/ FrameFresh \/ CrashBeforeAdmit \/ CrashAfterInsert
  \/ AdmitReplay \/ AdmitNew \/ AdmitRefuse \/ AdmitRefuseNew
  \/ StoreRow \/ CrashAfterAdmit \/ Adopt
  \/ Resume
  \/ DuplicateSubmit
  \/ LookupFound \/ LookupConflict \/ LookupUnavailable
  \/ LookupMissing \/ LookupUnframed
  \/ Finished

Spec == Init /\ [][Next]_vars

=============================================================================
