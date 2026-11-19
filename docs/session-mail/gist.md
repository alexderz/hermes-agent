# Session mail: message gists (G18)

Status: plan r2, 2026-11-18. All ten findings of the architect review (`reviews/gist-architect-r1.md`) are accepted; where it differs from the text below, the review wins. Ticket: DER-701 (session mail).

## Why

The owner's chat shows session-mail traffic as folded rows: "Message from <sender> ▸ show message" and "Replied to <sender> ▸ show reply". In a busy session the screen fills with these rows and the owner cannot tell what any of them were about without opening each one. The owner asked for a one- or two-sentence, user-facing gist on each row: very high level, light, no details.

Owner's words (2026-11-18): "have the agent when it ... sends a message ... get like a user facing quick one or two sentence summary of like what the message was ... very high level very light weight no details just have an idea". On the recommendation (sender-written gist, first-sentence fallback, no summarizer model): "Love it, go".

## Settled (out of scope for reviewers)

- The sender writes the gist. No extra model call, no summarizer model.
- A message without a gist still gets one: the first sentence of its body.
- The gist is optional. Nothing is refused for lacking one (no new gates).
- Gateway only, published plugin API only; the Webapp change is a small fork patch to the folded rows.
- All settled session-mail rules stay: no caps, holds or retries on delivery; no empty replies; `[SILENT]` sends nothing.

## Design

### G18a: the plugin (hermes-intercom)

1. **Send tool:** a new optional string field `gist`. The description reads: "One plain sentence for the owner, not for the recipient: what this message is about. No ids, paths or jargon. Example: 'Third review round passed; the harness is ready to merge.'" The CLI gets `--gist`.
2. **Reply block:** the reply instructions in the frame say: start the block with one line `Gist: <one plain sentence for the owner>`, then the answer. The plugin removes that line from the delivered body and uses it as the reply's gist.
3. **Fallback when no gist was given** (old senders, scripts, remote agents): the first sentence of the body, from the first line that is not empty and not a frame or echo line: up to the first `.`, `!` or `?` followed by a space or the end, else the whole line.
4. **Clean-up:**
   - collapse whitespace to single spaces;
   - drop control, format, bidi and zero-width characters;
   - relabel control-frame openers the way bodies already are;
   - strip one pair of surrounding quotes the sender added;
   - cut at 160 characters on a word boundary with `…`.
   An empty result means there is no gist.
5. **Where it goes:** on the notice line, after the colon, in curly quotes:
   `Message from 📡 <sender> (@<profile>): “<gist>”`
   The frame header (`📡 Not <owner> · …`) stays on the next line, unchanged. The quotes mark the text as the sender's words. The notice line already names the sender before the gist.
6. **Peers:**
   - Inbound posts from a remote agent may carry an optional `gist` field; otherwise the fallback applies.
   - Outbound posts carry `gist` in the JSON when the sender gave one.
   - `docs/peer-instructions.md` documents it.
7. **Records:** the `gist` is stored on the message row, so `intercom log` and `status` can show it.

### G18b: the Webapp (fork patch, `apps/desktop`)

1. **Inbound row** (`user-message.tsx`, the folded agent message): when the text after `AGENT_MESSAGE_RE`'s colon starts with a quoted gist on its first line (`“…”`), the row shows:
   - `🤖 <sender>` on the first line;
   - the gist below it, two lines at most, followed by `▸`.
   Tapping the gist opens the full message (replaces "show message"). Without a gist, the row stays as it is today.
2. **Reply row** (`assistant-message.tsx`, `InterAgentCollapsedNotice`), with the gist taken in this order:
   - the `Gist:` line inside the reply's `[REPLY <id>]` block;
   - else the first sentence inside the block;
   - else the first sentence of the reply.
   A reply that is only `[SILENT]`, or a block holding only `[SILENT]`, shows "No reply". The row reads `→ Replied` plus the gist, tap to open.
3. **Style:** the existing faded notice style. The gist is slightly brighter than the label. No new colours.
4. **Tests:** vitest for the gist extraction (quoted gist, none, an old-format frame, the `Gist:` line, first-sentence fallback, `[SILENT]`, clamp) and the rendered rows.

### Items

- **G18a:** plugin gist field, reply `Gist:` line, fallback, notice-line gist, peer field, docs, tests. Builder: Grok.
- **G18b:** Webapp rows. Builder: Grok. Blocked by G18a's notice-line format; it can build in parallel against this spec.
- **G18c:** E2E, an owner and two sessions on a trial home. A send with a gist, a send without one and a reply with a `Gist:` line all show the right notice text; a vitest render of real frames from that run.

### Risks

- **Sender text before the frame header.** The gist sits on the notice line, ahead of the `Not <owner>` header. Mitigations: the notice line names the sender first; the gist is quoted, cleaned, single-line and capped; frame openers are relabelled. Reviewers should check that no gist can forge a header, close a frame, or read as the owner's words.
- **Vague gists.** The tool text pushes for plain words; nothing more.
- **Old messages** keep today's rows; nothing is migrated.

## r2: changes from the architect review (all accepted)

1. **Clean-up, exactly, in this order:**
   - (a) `sanitize_title` (removes line breaks, Cf characters, `📡`, `[` and `]`);
   - (b) every curly or guillemet quote becomes `"`;
   - (c) strip one surrounding pair;
   - (d) clip at 160 characters with `_short_desc`'s logic;
   - (e) empty means no gist.

   The relabel step is dropped.
2. **`split_gist`** takes a leading `Gist:` line off the chosen reply text, block or whole answer, **before** `is_silent`; a body left empty is silent. The gist travels with the delivered reply.
3. **The `Gist:` instruction goes in all four reply-instruction sites:** the requested/waiting block, the optional bullet, the peer bullets and the held-notes line. `ask` answers carry no gist.
4. **Call sites:**
   - `build`, `_notice`, `route.send`, `_framed` and `frame_stored` (stored gist only for the newest keyed version) carry the gist;
   - the keyed wake and the deadline wake pass none and use the fallback;
   - held notes and `to: all` turn context are unchanged.
5. **No peer gist field.** Peers rely on the fallback; `peers.send` accepts and stores the gist but posts nothing extra.
6. **The fallback is computed in `frame.build`** from the echo-stripped body: the first line that is not a frame or notice line, with Markdown markers removed, cut at the first sentence by the existing `_SENTENCE_END_RE`/`_short_desc`, then cleaned as in 1.
7. **Webapp inbound:** a gist is recognised only when line 1 of the body is `“…”` and line 2 starts `📡 Not `. It is parsed in a pure helper, `thread/agent-gist.ts`, and "show message" opens the body without the gist line.
8. **Webapp reply row:**
   - the block is found by the inbound row's message id;
   - text parts are joined with newlines;
   - the "last text part" is the final rung;
   - "No reply" is shown for silence;
   - the gist is computed in a string selector that returns `''` while running;
   - after a `no reply needed` frame, today's row is unchanged.
9. **Schema:** `gist` is added for send and ask (the prompt prefix changes once, at the deploy restart), plus `--gist` on the CLI send. Reboot notices are unchanged.
10. **The gist is stored on the row** (NULL for a fallback), with no `log`/`status` display.

Items: as in the review's "Proposed items" (G18a plugin, G18b Webapp, G18c E2E with a frame fixture that `agent-gist.test.ts` parses).
