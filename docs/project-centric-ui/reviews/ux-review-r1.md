I found 10 issues, so the verdict is **changes needed**. The journeys are complete and the work stays inside slice 1: no deferred item came back, the `/new` guard stays on Hermes Mobile only, and there is no installable web app and no "Make main chat" button. Most findings are places where the UX disagrees with the HLD, or where a promise has no data source in the HLD's shape.

1. **The Projects entry is in the wrong place.** `ux.md:36`, `ux.md:121` and `stories/pcu-01-project-list.md:13` put **Projects** "directly above Sessions".
   - **Breaks:** the HLD (`hld.md:100`, `tab.position: "after:sessions"`) puts it after Sessions. The brief (`brief.md:176`) says "next to Sessions".
   - **Fix:** say "directly after Sessions", or "next to Sessions" and leave the exact slot to the architect.

2. **The UX assumes a core page, but the HLD chose a plugin.** `ux.md:17` assumes the brief's Q3 answer (core page). `ux.md:207` says a plugin tab would sit "further down the navigation… and its address changes".
   - **Breaks:** the HLD (`hld.md:96`, `:138-155`) chooses a bundled plugin at `after:sessions` and shows that the nav slot is the same.
   - **Fix:** note the HLD's decision at line 17. Rewrite open question 3 to say what Alex would actually see: nothing different in the nav slot. Any remaining difference, such as the address, goes to Spec.

3. **"New chat here" contradicts how the HLD builds it.** `stories/pcu-04-new-chat-here.md:15` says starting a chat here does not change "the dashboard's saved default folder for other new chats".
   - **Breaks:** the HLD (`hld.md:105-109`, `:200`) builds "New chat here" by setting exactly that saved value in `localStorage` and then opening `/chat`. As designed, the next fresh chat from Chat would also start in the project folder.
   - **Fix:** either drop the line and state the side effect, or keep it as a requirement and raise it with the architect. Keeping it effectively requires the `/chat?cwd=` deep link from the HLD's Open list.

4. **The project-page address and Back behaviour may not work as a plugin.** `ux.md:139` and `stories/pcu-03-project-page.md:13` use `/projects/<id>`. `pcu-03:21`, `pcu-07:17-18` and `ux.md:146` rely on Back and bookmarks restoring that page.
   - **Breaks:** consistency with the HLD. A plugin tab registers one exact path (`web/src/App.tsx:348-356`, `path: m.tab.path`), so a sub-path may not route.
   - **Fix:** state the requirement without a URL ("the project page has its own address, so Back, scroll position and bookmarks return to it") and leave the URL to Spec. Or ask the architect to confirm a sub-route.

5. **The Live badge has no data source in the HLD's shape.** The UX requires a **Live** badge on cards and on the Main chat card: `ux.md:46`, `:129`, `:141`, `stories/pcu-01-project-list.md:16`, `pcu-03:19`, `pcu-06:14`.
   - **Breaks:** the HLD (`hld.md:99`, `:122-123`) says the page reads only the tree. The tree nodes carry no running state (`tui_gateway/project_tree.py:355-367`). Running state is `is_active` on the sessions API (`web/src/lib/api.ts:2126`).
   - **Fix:** raise it with the architect. Either the HLD adds a read of the sessions list for Live (and message count, if the tree lacks it), or slice 1 drops Live and these lines change.

6. **The family rule conflicts with the folder path.** `stories/pcu-10-family-unaffected.md:16` says "No new screen text uses an id, a file path or an error code".
   - **Breaks:** this contradicts `ux.md:140` and `pcu-03:15`, which show the primary folder path on the project page. As written, the rule cannot pass.
   - **Fix:** limit the rule to empty, missing and error messages (which is what `ux.md:197` says), or drop the folder line.

7. **The project page has no loading, error or "not found" state.** F6 (`ux.md:87-90`) and `pcu-01:18-20` cover only the Projects list.
   - **Breaks:** the check that empty, error and loading states are covered.
   - **Fix:** add these to F6 and `pcu-03`:
     - project page loading;
     - project page load failure with **Retry**;
     - a bookmarked or stale link to a project that no longer exists or is archived (a plain sentence plus a link back to Projects).

8. **The Home page shows a folder message that makes no sense for Home.** Home opens "the same project page" (`ux.md:134-136`). Under F3 (`ux.md:77`) and `pcu-04:16`, its **New chat here** would be disabled with "Add a folder to this project…", pointing to Hermes Mobile.
   - **Breaks:** Home is not a project and cannot get a folder (`brief.md:53`). The message is wrong, and it is the kind of confusing wording the family taste rules out.
   - **Fix:** say what Home's page shows instead: either no **New chat here**, or a plain line that new chats without a folder start from Chat. Add it to `pcu-01` or `pcu-04`.

9. **Chats from another profile have no failure path.** `ux.md:144` and `pcu-03:22` label chats from another profile, but don't say what happens when you open one.
   - **Breaks:** the HLD's Open item (`hld.md:242-243`) says chats open in the current profile, and a non-default profile needs the profile scope switched first. As written, a tap may resume the wrong chat or an empty one. This is the same class of failure as "owner chat deleted".
   - **Fix:** add a journey and a checkable "Done when": opening a chat from another profile lands in that chat. That covers both the Main chat card and the rows. Name the HLD Open item as the dependency.

10. **The "two taps" claim is wrong on the phone.** `stories/pcu-02-open-main-chat.md:14` says "at most two clicks or taps… from any dashboard page", and `ux.md:40` and `:56` say the same for the phone.
    - **Breaks:** "Done when" lines must be checkable. On a phone, Projects sits in the narrow-screen drawer (`ux.md:150`), so it takes three taps: drawer, Projects, Open main chat.
    - **Fix:** say two clicks on a laptop and three taps on a phone. Or say the phone path is a bookmark to the Projects list plus one tap, which matches F5.

Everything else checked meets the requirements:
- **Other failure journeys:** no main chat (F1), missing main chat (F2; the tree does leave out archived chats, `methods_projects.py:349`), no chats (F3), older server (F4) and the current phone app (F5) are covered.
- **Partial profile failure:** the tree endpoint does return a list of errors per profile (`profiles.py`, `errors`), so `pcu-01:20` is supported.
- **Taste:** status colour is always paired with a word, and the dashboard's existing components and the embedded terminal chat are kept.
- **Template shape:** `ux.md` and the stories follow `ux.md` and `user-story.md`.

Verdict: changes needed

Reviewed: `git status --short docs/project-centric-ui` is clean (ux.md and stories/ unmodified at HEAD ec984b370b); `sha256sum ux.md` = `61b644a742a20cc74e323db34d76849411f64dfa94c35844a1418a06f952c2fc`