/**
 * Hermes Bot Mode — a "one chat per agent" roster for the Hermes desktop.
 *
 * Sessions sidebar "Bots": one row per Hermes profile (a bot = an agent profile) with
 * a customizable avatar (shape + color + eyes, image, or pet). Click opens that
 * bot's chat; right-click → Edit Profile (avatar, title, description).
 * "New Bot" creates a profile — Name / Title / Description with an
 * "Advanced" disclosure for full profile config.
 *
 * Right tile "Routines": scheduled tasks (Hermes cron jobs) scoped to the
 * bot you're currently chatting with — follows the live gateway profile.
 *
 * Bots message each other straight into each bot's ONE canonical "Bot
 * Chat" — @-mentions deliver over gateway RPCs (no CLI relay), and
 * bot-initiated sends use `hermes -p <bot> chat --in ~ -c "Bot Chat"`.
 */

import {
  CHAT_EMPTY_AREA,
  COMPOSER_AREAS,
  host,
  LocalizedTabTitle,
  PALETTE_AREA,
  SIDEBAR_PROFILE_GROUP_HEADER_AREA,
  SIDEBAR_SECTIONS_AREA,
  translateNow
} from '@hermes/plugin-sdk'
import type { ChatEmptyProps, PluginContext, ProfileGroupRoute } from '@hermes/plugin-sdk'

import { startFaceClock, stopFaceClock } from './avatar'
import {
  $botChatFocused,
  $focusedBotOwner,
  $openBotChat,
  $selectedBot,
  $selectedRosterHydrated,
  $selectedRosterKey,
  focusedMentionProfile
} from './bot-state'
import { isCanonicalChatOnScreen, openBotCanonicalChat } from './canonical-chat'
import { BotChatEmpty } from './chat-empty'
import { bindProfileSync, RoutinesPane } from './cron'
import {
  $botMeta,
  $lastRoster,
  botHandle,
  botMentionTag,
  botSelectionKey,
  cachedUnionRoster,
  claimDefaultHandles,
  isActiveRosterBot,
  migrateBotMeta,
  primeRoster,
  resolveRosterMentions
} from './data'
import {
  $groupChats,
  $groupChatWorkspace,
  assignLegacyThreads,
  handleSessionsGatewayTransition,
  hydrateGroupChatTombstones,
  pullGroupChatServerState,
  scheduleGroupChatServerSync,
  setGroupChatSyncDisposed,
  stopGroupChatServerSync,
  sweepGroupChatMembersForRemovedConnection,
  updateGroupChat
} from './group-chat'
import { stickyGroupEngine } from './group-engine'
import { groupWorkspaceOwnerKey } from './group-membership'
import { groupChatMainTabs } from './group-panes'
import { annotateOrphanedGroupChatMembers } from './hygiene'
import { BOTS_LOCALES, botsText } from './i18n'
import { displayName, slugifyProfileName } from './labels'
import { startBotRelay, stopBotRelay } from './relay'
import { $activityToasts } from './roster-actions'
import { botChatOwnsWorkspace, BotsPane, releaseStaleOpenBotChat, selectedRosterBot } from './roster-pane'
import { botRosterMeta, botWorkspaceOwnerKey, setBotsWorkspaceOwner } from './routing'
import { startScreenAutoRaise } from './screen-autoraise'
import { ProfileGroupScreenPortal } from './screen-portal'
import { startHideSweepScheduler } from './session-sweep'
import { $pendingBotOpen, bumpBotOpenGeneration, getBotOpenGeneration, ID, setPluginCtx } from './shared'
import { TeammateWaits } from './teammate-waits'
import type { GroupChat, RosterRow } from './types'
import { loadBotSections } from './user-sections'

// ── plugin ───────────────────────────────────────────────────────────────────

/** One row the composer's `@` popover renders from the roster. */
interface MentionCompletionItem {
  display: string
  insert: string
  meta: string
  /** Handles that resolve to this same bot — the raw profile name and the
   *  roster handle — so the popover can drop the gateway's own row for that
   *  name instead of listing the bot twice (once under its title slug,
   *  once under the raw name). */
  handles?: string[]
}

/** The draft a `composer.middleware` handler rewrites, passes through, or
 *  cancels (this plugin never cancels). */
interface ComposerDraftPayload {
  attachments?: unknown[]
  text: string
}

function syncFocusedBotWorkspaceRoute() {
  const scope = host.state.focusedSessionWorkspace?.get?.()

  if (scope?.workspaceMode === 'bots' && scope.workspaceOwnerKey) {
    host.setWorkspaceScope?.(
      'bots',
      scope.workspaceOwnerKey,
      scope.ownerRoute ? { kind: 'route', route: scope.ownerRoute } : null
    )

    return
  }

  const claim = $openBotChat.get()
  const owner = claim && selectedRosterBot($lastRoster.get(), claim.key)

  if (owner) {
    setBotsWorkspaceOwner(botWorkspaceOwnerKey(owner), owner)
  }
}

export default {
  id: ID,
  name: translateNow('common.bots'),
  description:
    'Bot Mode — a one-chat-per-agent roster with avatars, routines, group chats, and bot-to-bot messaging. Ships with the app; disable here if unwanted.',
  register(ctx: PluginContext) {
    setPluginCtx(ctx)
    // The user's own roster sections. Read once at register; every mutation
    // writes through.
    loadBotSections()
    const disposeLocales = ctx.i18n.register(BOTS_LOCALES)
    setGroupChatSyncDisposed(false)
    startFaceClock()
    // The cross-connection relay rides every gateway socket this Desktop
    // holds: roster sync + envelope drain/deliver/reply loops.
    startBotRelay()
    // Opt-in per bot: raise a bot's Screen tab on its first live screen tool call.
    const stopScreenAutoRaise = startScreenAutoRaise()

    // Disabling the plugin (or a hot reload) must actually stop the clock —
    // before this, the rAF loop + 1Hz document scan ran until app restart.
    if (typeof ctx.onDispose === 'function') {
      ctx.onDispose(disposeLocales)
      ctx.onDispose(stopFaceClock)
      ctx.onDispose(stopBotRelay)
      ctx.onDispose(stopScreenAutoRaise)
    }

    // @-mention autocomplete: typing "@rese…" in ANY composer offers the
    // roster's handles (issue #88060). Reads the roster straight from the
    // query cache — useRoster keeps it ≤5s stale and the popover must answer
    // synchronously per keystroke. Multi-source rosters contribute their
    // precomputed @name-device handles via botHandle. The active profile is
    // excluded (a bot doesn't @ itself); 'default' surfaces as @hermes.
    ctx.register({
      id: 'mention-completions',
      area: COMPOSER_AREAS.atCompletions,
      data: {
        provide: (query: string): MentionCompletionItem[] => {
          const roster = cachedUnionRoster()
          const profiles = Array.isArray(roster?.profiles) ? roster.profiles : []

          if (!profiles.length) {
            return []
          }

          const active = focusedMentionProfile()
          const q = (query || '').toLowerCase()
          const items: MentionCompletionItem[] = []

          const live = {
            name: active,
            connectionId: String(host.state.connectionId?.get?.() || host.activeConnectionId?.() || 'local')
          }

          const offered = profiles.filter(profile => profile?.name && !isActiveRosterBot(profile, live))
          // Two rows tagging alike (two remote defaults both titled "CoS Bot")
          // cannot share a bare tag — it would resolve to neither. Pin the
          // ambiguous ones to their connection (#103731).
          const tagCounts = new Map<string, number>()

          for (const profile of offered) {
            const tag = botMentionTag(profile).toLowerCase()
            tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1)
          }

          for (const profile of offered) {
            const handle = botHandle(profile.name, profile)
            const display = displayName(profile, botRosterMeta(profile, $botMeta.get()))
            // Renamed bots complete on their friendly name — the tag is the
            // renamed slug when one exists, the profile handle otherwise.
            const tag = botMentionTag(profile)

            if (
              q &&
              !tag.toLowerCase().startsWith(q) &&
              !handle.toLowerCase().startsWith(q) &&
              !display.toLowerCase().startsWith(q)
            ) {
              continue
            }

            const qualified = (tagCounts.get(tag.toLowerCase()) || 0) > 1 && profile.connectionId
            const insert = qualified ? `@${tag}@${profile.connectionId}` : `@${tag}`
            const source = profile.connectionLabel ? ` · ${profile.connectionLabel}` : ''
            items.push({
              insert,
              display: insert,
              meta: `Bot · ${display}${source}`,
              // The live gateway's own `@` rows list this backend's profiles
              // by raw name; claim ours so the popover drops that twin row.
              // Remote rows are NOT ours to claim — the local gateway's
              // same-named row resolves locally, not to the remote bot.
              ...(profile.remoteSource ? {} : { handles: [`@${profile.name}`] })
            })
          }

          return items.slice(0, 8)
        }
      }
    })

    // Hydrate persisted avatars/titles. Migration writes v2 only after a
    // provable sole-local topology and deliberately leaves v1 untouched for
    // one-version rollback.
    void migrateBotMeta(ctx.storage).catch(() => undefined)

    // The last selected bot, source-qualified. Restoring it is PRESENTATION
    // ONLY: it paints the roster highlight, and never activates a gateway,
    // opens a chat, or creates a session. The hydrated flag must flip on
    // every settle path — the roster holds a loading state until it does,
    // and a storage quirk must not strand it there.
    try {
      // TODO(bot-mode-types): PluginStorage.get(key, fallback) requires the fallback; every
      // Bot Mode read omits it (works at runtime, undefined fallback) — same at the two reads below.
      // @ts-expect-error typed as written rather than changing the call.
      Promise.resolve(ctx.storage?.get?.('selected-roster-bot-v1'))
        .then(value => {
          if (typeof value === 'string' && value.trim()) {
            $selectedRosterKey.set(value.trim())
          }
        })
        .catch(() => undefined)
        .finally(() => $selectedRosterHydrated.set(true))
    } catch {
      /* no storage — this window starts with no restored selection */
      $selectedRosterHydrated.set(true)
    }

    // Bot Mode sessions are always hidden now — the old "hide Bot Chats"
    // pref is gone (its stored key is simply ignored). The reconciliation
    // sweep below hides any rows born visible under the old pref.

    // Hydrate the activity-toast pref (default OFF).
    try {
      // @ts-expect-error TODO(bot-mode-types): PluginStorage.get requires a fallback argument.
      Promise.resolve(ctx.storage?.get?.('activity-toasts'))
        .then(value => {
          if (typeof value === 'boolean') {
            $activityToasts.set(value)
          }
        })
        .catch(() => undefined)
    } catch {
      /* no storage — default (silent) stays */
    }

    // Hydrate persisted group-chat room logs (epoch/running are runtime-only
    // and always reset — a loop can't survive a window reload anyway).
    // Disband memory must be in place before the first gateway pull merges
    // a mirror that may still project a disbanded room (#105275) — the pull
    // below awaits this, otherwise the first pull resurrects the room until
    // the next one re-tombstones it.
    let tombstonesHydrated: Promise<void> = Promise.resolve()

    try {
      // @ts-expect-error TODO(bot-mode-types): PluginStorage.get requires a fallback argument.
      tombstonesHydrated = Promise.resolve(ctx.storage?.get?.('group-chat-tombstones'))
        .then(value => hydrateGroupChatTombstones(value))
        .catch(() => undefined)
    } catch {
      /* no storage — no remembered disbands this window */
    }

    try {
      // @ts-expect-error TODO(bot-mode-types): PluginStorage.get requires a fallback argument.
      Promise.resolve(ctx.storage?.get?.('group-chats'))
        .then(async value => {
          if (value && typeof value === 'object' && !Array.isArray(value)) {
            const rooms: Record<string, GroupChat> = {}

            for (const [name, room] of Object.entries(value)) {
              if (room && Array.isArray(room.log)) {
                rooms[name] = {
                  // Pre-thread entries get synthetic thread ids on hydrate so
                  // every UI/engine path can assume entry.thread exists.
                  log: assignLegacyThreads(room.log),
                  watermarks: room.watermarks && typeof room.watermarks === 'object' ? room.watermarks : {},
                  sessions: room.sessions && typeof room.sessions === 'object' ? room.sessions : {},
                  sessionOwners: room.sessionOwners && typeof room.sessionOwners === 'object' ? room.sessionOwners : {},
                  stranded: room.stranded && typeof room.stranded === 'object' ? room.stranded : {},
                  // #93129: rehydrate sticky stop holds with the same shape
                  // guard as the other maps — a held bot stays held across
                  // window restarts until explicitly released.
                  holds: room.holds && typeof room.holds === 'object' ? room.holds : {},
                  externalCursors:
                    room.externalCursors && typeof room.externalCursors === 'object' ? room.externalCursors : {},
                  members: Array.isArray(room.members) ? room.members : [],
                  roomId: typeof room.roomId === 'string' && room.roomId ? room.roomId : null,
                  ...stickyGroupEngine(room),
                  image: typeof room.image === 'string' && room.image ? room.image : null,
                  rosterOrder: Number.isFinite(room.rosterOrder) ? room.rosterOrder : undefined,
                  pinned: Boolean(room.pinned),
                  sectionId: room.sectionId ?? null,
                  syncRevision: Math.max(0, Number(room.syncRevision || 0)),
                  epoch: 0,
                  running: false
                }
              }
            }

            $groupChats.set({
              ...rooms,
              ...$groupChats.get()
            })

            // #93492: annotate rows orphaned before this build (their
            // connection was deleted while an older Desktop ran, so no
            // 'removed' push ever swept them). Registry read is
            // feature-detected; when unavailable only the unresolvable-route
            // shape (lost connectionId) is annotated.
            try {
              const registry =
                typeof window !== 'undefined'
                  ? await Promise.resolve(window.hermesDesktop?.connections?.list?.()).catch(() => null)
                  : null

              const liveIds = Array.isArray(registry?.connections)
                ? new Set(registry.connections.map(connection => String(connection?.id || '').trim()).filter(Boolean))
                : null

              const annotated = annotateOrphanedGroupChatMembers($groupChats.get(), liveIds)

              if (annotated.changed) {
                // Per-room updateGroupChat keeps the durable record's full
                // shape (sessionOwners, holds) in storage; sync:false —
                // the scheduleGroupChatServerSync below publishes once.
                for (const [roomName, room] of Object.entries(annotated.rooms)) {
                  if (room !== $groupChats.get()[roomName]) {
                    updateGroupChat(roomName, () => room, {
                      sync: false
                    })
                  }
                }
              }
            } catch {
              /* registry unavailable — the lost-connectionId shape is still safe to render */
            }
          }

          // Receive before publish. A fresh Desktop with no local room cache
          // must hydrate the gateway projection instead of merely avoiding an
          // empty overwrite and then rendering an empty conversation.
          await tombstonesHydrated
          await pullGroupChatServerState().catch(() => false)
          scheduleGroupChatServerSync($groupChats.get())
        })
        .catch(() => undefined)
    } catch {
      /* no storage — rooms start empty */
    }

    // Routines follow the chat you're in: track the focused chat's owner
    // profile (falls back to the live gateway profile on older desktops —
    // see $focusedBotProfile). Keying this off the socket's home alone left
    // the unread-suppression and Routines scope on the wrong bot whenever a
    // focused tab showed another profile's chat.
    // Capture the unbinds: without them a disable → re-enable cycle stacks a
    // duplicate listener per cycle (same survives-disable class as the face
    // clock before its onDispose hook — these kept firing until app restart).
    const unbindProfileListener = bindProfileSync($focusedBotOwner)
    const unbindGatewayListener = host.state.gateway.listen(handleSessionsGatewayTransition)

    // The composer's @ picker reads the roster cache synchronously; fill it on
    // the first gateway open so cross-connection bots complete before the Bots
    // pane has ever mounted (#94018). The pane owns the refresh once open.
    const primeOnGatewayOpen = (state: unknown) => {
      if (String(state) === 'open') {
        void primeRoster()
      }
    }

    primeOnGatewayOpen(host.state.gateway.get())
    const unbindRosterPrime = host.state.gateway.listen(primeOnGatewayOpen)

    // #93492 root fix: the registry pushes a lifecycle event when a
    // connection is removed. The gateway store already disposes the dead
    // sockets; the persisted group-chat rosters referencing that connection
    // were never touched, which is what left panes throwing "Bot X has no
    // connection owner" forever. Annotate (never silently delete) those
    // member rows the moment the connection goes away. Feature-detected:
    // older Electron mains don't emit it, and bare vm test harnesses have
    // no window global.
    let unbindConnectionsChanged: null | (() => void) = null

    try {
      if (typeof window !== 'undefined') {
        unbindConnectionsChanged =
          window.hermesDesktop?.connections?.onChanged?.(payload => {
            if (payload?.reason === 'removed') {
              sweepGroupChatMembersForRemovedConnection(payload.connectionId)
            }
          }) || null
      }
    } catch {
      /* registry lifecycle push unavailable — hydrate-time annotate still covers it */
    }

    if (typeof ctx.onDispose === 'function') {
      ctx.onDispose(() => {
        stopGroupChatServerSync()

        if (typeof unbindProfileListener === 'function') {
          unbindProfileListener()
        }

        if (typeof unbindGatewayListener === 'function') {
          unbindGatewayListener()
        }

        if (typeof unbindRosterPrime === 'function') {
          unbindRosterPrime()
        }

        if (typeof unbindConnectionsChanged === 'function') {
          unbindConnectionsChanged()
        }
      })
    }

    // Reconciliation sweep: hide every Bot Mode session we know about, on
    // load and again on each reconnect (a swap can land on a gateway whose
    // rows were created before the always-hidden policy). Deferred a tick so
    // the meta/room storage hydrates above have landed; idempotent after that.
    // (Feature-guarded: bare vm test harnesses have no setTimeout global.)
    startHideSweepScheduler(ctx)
    // Sessions sidebar: each gateway/profile group gets the profile's Screen portal
    // above its sessions, so the bot's computer is reachable from either mode.
    // Above a Bot Chat's composer: that bot's unsettled teammate deliveries (renders nothing
    // in any other chat, or when none are pending).
    ctx.register({ id: 'teammate-waits', area: COMPOSER_AREAS.top, render: () => <TeammateWaits /> })
    ctx.register({
      id: 'screen-portal',
      area: SIDEBAR_PROFILE_GROUP_HEADER_AREA,
      data: { render: (route: ProfileGroupRoute) => <ProfileGroupScreenPortal route={route} /> }
    })
    ctx.register({
      id: 'roster',
      area: SIDEBAR_SECTIONS_AREA,
      render: () => <BotsPane embedded />
    })

    // Routines — its OWN tiling pane splitting the workspace's right edge
    // (NOT the collapsible right sidebar; placement 'right' is that sidebar's
    // role and hides the pane until "Show Right Sidebar").
    //
    // Registered only while an actual bot-owned chat is the working surface.
    // The shared navigation roster never owns this lifecycle; group rooms do
    // not acquire bot-scoped tools. Older SDKs keep their established fallback.
    const registerRoutinesPane = (restoreDismissed: boolean) => {
      const dispose = ctx.register({
        id: 'routines',
        area: 'panes',
        // The app's noun for these, so the tab agrees with the pane header and
        // with the core Scheduled jobs surface. `translateNow`, not `useI18n`:
        // a pane title is read at registration, outside React.
        title: translateNow('cron.title'),
        data: {
          tabTitle: () => <LocalizedTabTitle select={t => t.cron.title} />,
          tabTitleText: () => translateNow('cron.title'),
          placement: 'main',
          closeBehavior: 'dismiss',
          collapsible: true,
          // Repair persisted layouts that stranded Cronjobs in the Bots tab strip.
          dock: {
            pane: 'workspace',
            pos: 'right',
            enforce: true
          },
          // A bot's schedule is glanceable, not something you sit in — it
          // arrives as the right edge's vertical tab and takes no width off the
          // chat until the user opens it.
          defaultCollapsed: true,
          width: '250px'
        },
        render: () => <RoutinesPane />
      })

      // The pane's ✕ remembers a Close across launches, and nothing else ever
      // shows this pane again — it only comes back by being registered here.
      // Entering Bot Mode is the user asking for their bot's chrome, so a
      // remembered Close is dropped and the pane returns the way it first
      // arrived: as the collapsed right-edge tab (#102224). Only on ENTRY:
      // the pane also re-registers whenever a bot chat regains the workspace
      // inside one Bots session (a group room and back), and a ✕ from that
      // same session must survive those.
      if (restoreDismissed && typeof host.undismissPane === 'function') {
        host.undismissPane(`${ID}:routines`)
      }

      return dispose
    }

    if (typeof host.paneVisibility === 'function') {
      let unregisterRoutines: null | (() => void) = null
      let botVisit = false
      // Ordinary selection can precede its async focus edge. Until a new
      // content focus or bot-open intent, the old tile must not reclaim routing.
      let yielded = false
      let disposed = false
      let syncTimer: ReturnType<typeof setTimeout> | undefined

      const syncRoutinesPane = () => {
        if (disposed) {
          return
        }

        releaseStaleOpenBotChat(host.state.focusedStoredSessionId?.get?.())
        const owns = !yielded && botChatOwnsWorkspace()
        $botChatFocused.set(owns)
        const pane = host.state.focusedPaneId?.get?.()

        const group = [...groupChatMainTabs.keys()].find(
          name => pane === `plugin-workspace:${ID}:group:${slugifyProfileName(name)}`
        )

        if (group && !yielded) {
          $groupChatWorkspace.set(group)
          setBotsWorkspaceOwner(groupWorkspaceOwnerKey(group), null, botsText().group.startInComposer())
        } else if (owns) {
          $groupChatWorkspace.set(null)

          if (!$pendingBotOpen.get()) {
            syncFocusedBotWorkspaceRoute()
          }

          if (!unregisterRoutines) {
            unregisterRoutines = registerRoutinesPane(!botVisit)
          }

          botVisit = true
        } else if (
          !pane?.startsWith('plugin-workspace:') &&
          !$pendingBotOpen.get() &&
          (!$groupChatWorkspace.get() || pane === 'workspace' || pane?.startsWith('session-tile:'))
        ) {
          // A real ordinary chat/draft takes routing back; a pending roster tap
          // still owns its async intent until explicit selection supersedes it.
          botVisit = false
          host.setWorkspaceScope?.('sessions')
        }

        if (!owns && unregisterRoutines) {
          unregisterRoutines()
          unregisterRoutines = null
        }
      }

      // Focus notifications arrive inside tree mutations. Never re-enter the
      // layout by registering a pane until that mutation has settled.
      const scheduleRoutinesSync = () => {
        if (!disposed && syncTimer === undefined) {
          syncTimer = setTimeout(() => {
            syncTimer = undefined
            syncRoutinesPane()
          }, 0)
        }
      }

      const stopGroupSync = $groupChatWorkspace.listen(scheduleRoutinesSync)
      const focusStore = host.state.focusedStoredSessionId || host.state.activeSessionId

      const stopFocusSync = focusStore?.listen?.(() => {
        yielded = false

        // A tab click is also explicit selection. Bot opens publish their
        // primary/tile scope before focusing, so focus-before-claim stays current.
        // Feature-detect: legacy shells cannot prove that distinction.
        if (
          $pendingBotOpen.get() &&
          host.state.focusedSessionWorkspace &&
          host.state.focusedSessionWorkspace.get()?.workspaceMode !== 'bots'
        ) {
          host.setWorkspaceScope?.('sessions')
        }

        scheduleRoutinesSync()
      })

      const stopTileSync = host.state.focusedSessionWorkspace?.listen?.(scheduleRoutinesSync)

      const stopPaneSync = host.state.focusedPaneId?.listen?.(pane => {
        if (pane === 'workspace' || pane?.startsWith('session-tile:') || pane?.startsWith('plugin-workspace:')) {
          yielded = false
        }

        scheduleRoutinesSync()
      })

      const stopClaimSync = $openBotChat.listen(scheduleRoutinesSync)
      const stopPendingSync = $pendingBotOpen.listen(scheduleRoutinesSync)

      // This is an intent boundary, NOT an ownership predicate. Core yields
      // synchronously on ordinary selection, even reselecting the same chat.
      // Hiding the mobile navigation does not change workspace routing.
      const stopScopeSync = host.state.workspaceMode?.listen?.(mode => {
        yielded = mode === 'sessions'

        if (yielded) {
          bumpBotOpenGeneration()
          $openBotChat.set(null)
          $groupChatWorkspace.set(null)
          botVisit = false
          scheduleRoutinesSync()
        }
      })

      // Proactive reclaim refresh: when the gateway reaps the runtime behind
      // the OPEN bot chat (idle TTL, LRU cap, WS-orphan reap — the mass-reap
      // shape hits every background bot at once), re-resume the canonical
      // chat immediately instead of letting the user's next send eat the
      // stale-id error + recovery retry. Matched on the STORED id (the
      // claim's ids are stored ids; the payload carries both). Best-effort:
      // a failed re-resume (backend still down) leaves the lazy recovery on
      // next send as the backstop. Feature-detected — older shells have no
      // host.onEvent.
      //
      // This is a BACKGROUND wake: it refreshes in place (refreshInPlace
      // through openBotCanonicalChat) and never navigates, so a user
      // reading the Kanban board — or any other route — keeps their view
      // (issue 121874).
      const stopReclaimSync =
        typeof host.onEvent === 'function'
          ? host.onEvent('session.reclaimed', event => {
              const payload = (event?.payload || {}) as { stored_session_id?: string }
              const stored = String(payload.stored_session_id || '')
              const claim = $openBotChat.get()

              if (!stored || !claim) {
                return
              }

              const owned = [claim.openedSessionId, claim.openedRegistryId].filter(Boolean)

              if (!owned.includes(stored)) {
                return
              }

              // A claim without a registry id is the legacy newChat draft
              // fallback: re-resolving the canonical chat here would replace
              // a draft the user is typing into. Its tile recovers on the next
              // send like any tab.
              if (!claim.openedRegistryId) {
                return
              }

              const bot = selectedRosterBot($lastRoster.get(), $selectedRosterKey.get())

              if (!bot) {
                return
              }

              const generation = getBotOpenGeneration()
              void openBotCanonicalChat(bot, { background: true })
                .then(opened => {
                  // A user action while the re-resume ran owns the center now.
                  if (!opened || generation !== getBotOpenGeneration()) {
                    return
                  }

                  $openBotChat.set({
                    key: claim.key,
                    openedRegistryId: opened.registryId,
                    openedSessionId: opened.openedId
                  })
                })
                .catch(() => {
                  /* backend still down — next send recovers via the ladder */
                })
            })
          : null

      // A persisted bot tile can already own focus at registration.
      scheduleRoutinesSync()

      if (typeof ctx.onDispose === 'function') {
        // The registration disposer is already tracked by ctx.register; only
        // the listeners need explicit teardown or they survive plugin disable.
        ctx.onDispose(() => {
          disposed = true
          clearTimeout(syncTimer)
          stopScopeSync?.()
          stopTileSync?.()
          stopPaneSync?.()
          stopClaimSync()
          stopPendingSync()
          stopGroupSync()
          stopFocusSync?.()
          stopReclaimSync?.()
          bumpBotOpenGeneration()
          $openBotChat.set(null)
          $botChatFocused.set(false)
          host.setWorkspaceScope?.('sessions')
        })
      }
    } else {
      registerRoutinesPane(true)
    }

    // A bot's chat before it has spoken: core's splash is Hermes' wordmark and
    // stands down for any session that exists, so the bot titles its own.
    ctx.register({
      id: 'chat-empty',
      area: CHAT_EMPTY_AREA,
      data: {
        render: ({ sessionId }: ChatEmptyProps) => <BotChatEmpty sessionId={sessionId} />
      }
    })

    ctx.register({
      id: 'new-agent',
      area: PALETTE_AREA,
      data: {
        id: `${ID}.new-agent`,
        label: 'New bot…',
        keywords: ['bot', 'agent', 'profile', 'teammate', 'create'],
        run: () => {
          host.notify({
            kind: 'info',
            message: ctx.i18n.t('bot.createFirstHint')
          })
        }
      }
    })

    // @-mention middleware: "@<bot> do the thing" in any chat gets an
    // IDENTIFICATION note — who the user is referring to, resolved against
    // the LIVE roster ("user@example.com" or an unknown @ passes through
    // untouched). The middleware never delivers anything itself: the agent
    // owns messaging via its message_agent tool (Bot Chats), so there is
    // exactly one send path and user text is never forwarded verbatim by
    // the renderer. The composer's @-autocomplete remains the picking aid.
    ctx.register({
      id: 'mention-middleware',
      area: COMPOSER_AREAS.middleware,
      data: {
        handler: async (draft: ComposerDraftPayload): Promise<ComposerDraftPayload> => {
          const text = draft.text || ''

          // /new inside a bot's canonical forever-chat would fork the
          // relationship into a scratch session — the one thing Bots mode
          // promises never happens. Reroute to /compact (same felt effect:
          // fresh working context, SAME conversation) and say so. Only
          // guards the canonical chat: Sessions-mode scratchpads on the
          // same profile keep full /new freedom.
          const slashNew = /^\/(new|reset)\s*$/.exec(text.trim())

          if (slashNew) {
            const activeBot = $selectedBot.get()
            // Canonical identity is the profile's "Bot Chat" registry row —
            // read it from the roster cache (canonical_session, resolved
            // server-side by name), matching either the durable row id or
            // the compression-lineage tip currently on screen.
            const roster = $lastRoster.get()
            const row = Array.isArray(roster) ? roster.find(bot => botSelectionKey(bot) === activeBot) : null

            // The STORED id, which is the id space canonical_session is keyed
            // in. `host.state.activeSessionId` is the runtime id and could
            // never match, so the guard read `host.activeSessionId` — no such
            // property — and silently resolved to null on every turn: /new
            // reset the forever-chat instead of compacting it.
            if (activeBot && isCanonicalChatOnScreen(row, host.state.focusedStoredSessionId.get())) {
              host.notify({
                kind: 'info',
                title: 'This chat never resets',
                message:
                  'Bot chats are one continuous conversation — compacting instead. ' +
                  'For a throwaway session with this bot, use Sessions mode.'
              })

              return {
                ...draft,
                text: '/compact'
              }
            }
          }

          if (!/(^|\s)@[a-z0-9][a-z0-9_-]*/i.test(text)) {
            return draft
          }

          const live = {
            name: focusedMentionProfile(),
            connectionId: String(host.state.connectionId?.get?.() || host.activeConnectionId?.() || 'local')
          }

          let cached = cachedUnionRoster()

          if (!Array.isArray(cached?.profiles)) {
            // Cold cache (the Bots pane never ran this launch): fill it the way
            // the pane does. The profiles.list fallback below only knows the
            // ACTIVE gateway and drops every cross-connection target (#94018).
            await primeRoster()
            cached = cachedUnionRoster()
          }

          const roster = Array.isArray(cached?.profiles) ? cached.profiles : null
          let mentionedBots = roster ? resolveRosterMentions(text, roster, live) : []

          if (!roster) {
            try {
              const res = await host.request<{ profiles?: RosterRow[] }>('profiles.list', {
                include_sessions: false
              })

              // Same resolver as the cached path — renamed bots (display_name
              // / ui_meta title) stay taggable when the roster cache is cold.
              // The same handle claim the pane applies: a real 'hermes'
              // profile keeps @hermes, so the default must not answer it too.
              mentionedBots = resolveRosterMentions(text, claimDefaultHandles(res?.profiles ?? []), live).map(bot => ({
                ...bot,
                remoteSource: false
              }))
            } catch {
              return draft
            }
          }

          if (!mentionedBots.length) {
            return draft
          }

          // Identification only. Each line names the agent the user's tag
          // resolves to (friendly title + device for cross-connection rows),
          // so the agent knows exactly who "@research-buddy" is. Cross-
          // connection targets carry the '@connection' suffix message_agent
          // resolves against the Desktop-synced relay roster.
          const lines = mentionedBots.map(bot => {
            const handle = botHandle(bot.name, bot)

            const title = String(
              botRosterMeta(bot, $botMeta.get())?.title || bot.ui_meta?.['hermes-bots']?.title || bot.title || ''
            ).trim()

            // message_agent only resolves canonical identities: the relay
            // matches a roster row's handle/profile (± @connection-id), the
            // local path a bare profile name or 'hermes'. botHandle() prefers
            // the row's source-qualified UI alias ('default-vera'), which
            // neither resolver accepts — annotate the canonical form instead.
            // The default's canonical form is 'hermes' only while no real
            // 'hermes' profile holds it; then it is 'default' itself.
            const target =
              bot.remoteSource && bot.connectionId
                ? `${bot.name}@${bot.connectionId}`
                : botHandle(bot.name, { hermesHandleTaken: bot.hermesHandleTaken })

            // Local rows get the same annotation whenever their UI alias
            // ('default-this-device') differs from the resolvable handle —
            // otherwise the agent has only the alias to go on and the local
            // path rejects it the same way (#97678).
            const where = bot.remoteSource
              ? ` — on ${bot.connectionLabel || bot.connectionId} (message_agent target: "${target}")`
              : handle !== target
                ? ` (message_agent target: "${target}")`
                : ''

            return `@${handle} = agent profile "${bot.name}"${title ? ` ("${title}")` : ''}${where}`
          })

          const note =
            '\n\n[@mentions resolved from the Bot Mode roster — the user is referring to: ' +
            lines.join('; ') +
            '. If they want one of these agents contacted, compose your own message and send it with your message_agent tool (agents on other connected machines are reachable too — the Desktop relays it); never forward the user\u2019s text verbatim. If this session has no message_agent tool, agent messaging is unavailable here — say so.]'

          return {
            ...draft,
            text: text + note
          }
        }
      }
    })
  }
}
