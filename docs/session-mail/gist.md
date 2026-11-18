# Session mail: message gists (G18)

Status: plan r1, 2026-11-18. Ticket: DER-701 (session mail).

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
