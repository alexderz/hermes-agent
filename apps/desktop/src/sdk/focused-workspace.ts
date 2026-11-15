import { computed } from 'nanostores'

import { findGroup } from '@/components/pane-shell/tree/model'
import { $activeTreeGroup, $layoutTree } from '@/components/pane-shell/tree/store'
import { $selectedStoredSessionId } from '@/store/session'
import { $focusedTreePaneId, TILE_PANE_PREFIX } from '@/store/session-focus'
import { $botChatScopes, $sessionTiles, type SessionTileWorkspaceScope } from '@/store/session-states'

/** Actual keyboard-owning pane, unlike focusedTreePaneId which remembers the
 * conversation while the person works in chrome (including auxiliary panes). */
export const $focusedPaneId = computed([$activeTreeGroup, $layoutTree], (groupId, tree) =>
  groupId && tree ? (findGroup(tree, groupId)?.active ?? null) : null
)

/** Read-only projection of existing open metadata, never a session registry.
 * In-place opens record primary ownership before selection, just as tile opens
 * record scope before focus. Chrome retains that working conversation; primary
 * focus alone (including an ordinary session or draft) grants no bot ownership. */
export const $focusedSessionWorkspace = computed(
  [$focusedTreePaneId, $sessionTiles, $selectedStoredSessionId, $botChatScopes],
  (paneId, tiles, selected, primaryScopes): SessionTileWorkspaceScope | null => {
    // Match session-focus's primary fallback, including its null homing edge
    // and auxiliary-pane focus before a content pane has been remembered.
    if (!paneId?.startsWith(TILE_PANE_PREFIX)) {
      return selected ? (primaryScopes[selected] ?? null) : null
    }

    const tile = tiles.find(candidate => candidate.storedSessionId === paneId.slice(TILE_PANE_PREFIX.length))

    return tile
      ? {
          workspaceMode: tile.workspaceMode ?? 'sessions',
          workspaceOwnerKey: tile.workspaceOwnerKey,
          workspaceTabTitle: tile.workspaceTabTitle,
          ownerProfile: tile.ownerProfile,
          ownerRoute: tile.ownerRoute
        }
      : null
  }
)
