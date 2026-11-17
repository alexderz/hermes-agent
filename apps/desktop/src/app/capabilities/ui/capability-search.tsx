import type { ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { SearchField } from '@/components/ui/search-field'

/** Shared scoped search and actions. Actions get their own row in narrow
 *  containers so a wrapping toolbar cannot consume the input's touch target. */
export function CapabilitySearch({
  actions,
  hints,
  onChange,
  placeholder,
  scope,
  value
}: {
  actions?: ReactNode
  hints?: string[]
  onChange: (value: string) => void
  placeholder: string
  scope: string
  value: string
}) {
  return (
    <div className="@container/capability-search w-full min-w-0">
      <div className="flex min-w-0 flex-col gap-3 @3xl/capability-search:flex-row @3xl/capability-search:items-center">
        <SearchField
          containerClassName="h-10 w-full min-w-0 rounded-2xl bg-(--dt-card) py-0 @3xl/capability-search:flex-1"
          hints={hints}
          leadingContent={
            <Badge size="xs" variant="muted">
              {scope}
            </Badge>
          }
          onChange={onChange}
          placeholder={placeholder}
          value={value}
          variant="box"
        />
        {actions ? (
          <div
            className="flex min-w-0 max-w-full shrink-0 flex-wrap items-center justify-end gap-3"
            data-catalog-actions
          >
            {actions}
          </div>
        ) : null}
      </div>
    </div>
  )
}
