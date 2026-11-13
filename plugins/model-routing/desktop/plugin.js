// model-routing usage meter for the Hermes desktop app: a status-bar chip with one reading per
// subscription (weekly used %, dot coloured by pace) and a popover with the detail. Data comes from
// this plugin's backend (/api/plugins/model-routing/state), refreshed every minute; the collector
// reads the providers every 15 minutes, and "Refresh now" reads them on demand (read-only, no tokens).
import {
  Button, Popover, PopoverContent, PopoverTrigger, STATUSBAR_AREAS, StatusDot, Tip, queryClient, useQuery
} from '@hermes/plugin-sdk'
import { useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'model-routing'
const KEY = [ID, 'state']
const SHORT = { claude: 'Claude', codex: 'GPT', supergrok: 'Grok' }

function tone(c) {
  if (!c.fresh) return ['muted', 'no data']
  if (!c.eligible) return ['bad', c.reason || 'not eligible']
  if (c.pace_delta != null && c.pace_delta < 0) return ['warn', 'over pace']
  return ['good', 'under pace']
}

const pct = v => (v == null ? '–' : `${Math.round(v)}%`)
const signed = v => (v == null ? '' : `${v > 0 ? '+' : ''}${Math.round(v)}%`)
const money = v => `$${(v || 0).toFixed(2)}`
const remaining = v => v == null ? null : Math.max(0, Math.min(100, 100 - v))

// A single status-bar row, not another mobile toolbar. Reserve enough of the
// right cluster for the compact meter; the other status items can still clip.
const METER_CSS = `
  [data-usage-compact] { display: none; }
  @media (max-width: 600px) {
    [data-usage-full] { display: none !important; }
    [data-usage-compact] { display: inline-flex; }
    [data-slot="statusbar"] > :last-child:has([data-subscription-meter]) {
      flex-shrink: 0;
      max-width: calc(100% - 2.5rem);
    }
  }
`

function Row({ c }) {
  const [t, word] = tone(c)
  return jsxs('div', {
    style: { display: 'grid', gridTemplateColumns: '1fr auto', gap: '2px 12px', padding: '6px 0',
      borderBottom: '1px solid var(--ui-stroke-secondary)' },
    children: [
      jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }, children: [
        jsx(StatusDot, { tone: t }), `${c.name} ${c.plan || ''}`,
        c.picked ? jsx('span', { style: { fontSize: 10, color: 'var(--ui-accent)' }, children: '· current pick' }) : null
      ] }),
      jsx('div', { style: { fontWeight: 700, fontSize: 15 }, children: `${pct(c.used_percent)}  P: ${signed(c.pace_delta)}` }),
      jsx('div', { style: { color: 'var(--ui-text-tertiary)', fontSize: 11 }, children:
        `${word} · week resets ${c.reset_label || '?'}` +
        (c.short_used_percent != null ? ` · 5-hour ${pct(c.short_used_percent)}` : '') }),
      jsx('div', { style: { color: 'var(--ui-text-tertiary)', fontSize: 11, textAlign: 'right' }, children:
        c.pace_used_percent != null ? `pace ${pct(c.pace_used_percent)}` : '' })
    ]
  })
}

function Panel({ data, ctx }) {
  const [busy, setBusy] = useState(false)
  const o = data.openrouter || {}
  const refresh = async () => {
    setBusy(true)
    try {
      const fresh = await ctx.rest('/refresh', { method: 'POST', timeoutMs: 90000 })
      queryClient.setQueryData(KEY, fresh)
    } catch (e) {
      queryClient.invalidateQueries({ queryKey: KEY })
    } finally {
      setBusy(false)
    }
  }
  const pick = data.pick
  return jsxs('div', { style: { fontSize: 12, padding: 4 }, children: [
    jsx('div', { style: { fontWeight: 600, marginBottom: 4 }, children: 'Weekly usage (% used), most over pace first' }),
    data.warning && data.warning.active
      ? jsx('div', { style: { color: 'var(--ui-text-secondary)', marginBottom: 4 },
          children: `Warning: usage data unavailable for ${data.warning.subscriptions.join(', ')}` })
      : null,
    ...(data.cards || []).map(c => jsx(Row, { c }, c.id)),
    jsxs('div', { style: { display: 'grid', gridTemplateColumns: '1fr auto', padding: '6px 0' }, children: [
      jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }, children: [
        jsx(StatusDot, { tone: 'muted' }), 'OpenRouter (pay per use)'] }),
      jsx('div', { style: { fontWeight: 700, fontSize: 15 }, children: `${money(o.week)} this week` }),
      jsx('div', { style: { color: 'var(--ui-text-tertiary)', fontSize: 11 }, children:
        `${money(o.today)} today · ${money(o.month)} this month · balance ${money(o.balance)}` })
    ] }),
    jsx('div', { style: { color: 'var(--ui-text-tertiary)', fontSize: 11, margin: '4px 0 8px' }, children:
      (data.on_demand && data.on_demand.active ? 'Routing would use on-demand OpenRouter. '
        : pick ? `Routing would pick ${SHORT[pick.subscription] || pick.subscription} (${pick.model}). ` : 'No routing pick. ') +
      'Advisory only for now. P is headroom against the weekly pace line; minus means over pace.' }),
    jsxs('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' }, children: [
      jsx('span', { style: { color: 'var(--ui-text-quaternary)', fontSize: 11 },
        children: data.written_at ? `Read ${new Date(data.written_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}` : 'Not read yet' }),
      jsx(Button, { variant: 'ghost', size: 'sm', disabled: busy, onClick: refresh, children: busy ? 'Reading…' : 'Refresh now' })
    ] })
  ] })
}

function Meter({ ctx }) {
  const [open, setOpen] = useState(false)
  const { data, error } = useQuery({
    queryKey: KEY,
    queryFn: () => ctx.rest('/state'),
    refetchInterval: 60000,
    staleTime: 30000
  })
  if (error && !data) {
    return jsx(Tip, { label: 'Usage meter: the model-routing backend is not reachable. Is the plugin enabled in plugins.enabled?',
      children: jsx('span', { style: { fontSize: 11, color: 'var(--ui-text-quaternary)', padding: '0 6px' }, children: 'usage –' }) })
  }
  if (!data) return null
  const o = data.openrouter || {}
  const chips = (compact) => (data.cards || []).map(c => {
    const [t, word] = tone(c)
    return jsxs('span', { key: c.id, 'aria-label': `${c.name} ${pct(remaining(c.used_percent))} left, ${word}`,
      style: { display: 'inline-flex', alignItems: 'center', gap: 4 }, children: [
        jsx(StatusDot, { tone: t }),
        `${SHORT[c.id] || c.name} ${pct(remaining(c.used_percent))}${compact ? '' : ` left${c.pace_delta != null ? ` P${signed(c.pace_delta)}` : ''}`}`
      ] })
  })
  return jsxs(Popover, { open, onOpenChange: setOpen, children: [
    jsx('style', { children: METER_CSS }),
    jsx(PopoverTrigger, { asChild: true, children: jsx(Button, {
      variant: 'ghost', size: 'micro', 'aria-label': 'Subscription usage',
      'data-subscription-meter': '',
      children: [
        jsxs('span', { key: 'full', 'data-usage-full': '', style: { display: 'inline-flex', gap: 10, fontSize: 11, color: 'var(--ui-text-secondary)' }, children: [...chips(false), jsx('span', { children: `OR ${money(o.today)}` }, 'or')] }),
        jsxs('span', { key: 'compact', 'data-usage-compact': '', style: { alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--ui-text-secondary)' }, children: ['Left', ...chips(true)] })
      ]
    }) }),
    jsx(PopoverContent, { side: 'top', align: 'end', style: { width: 'min(360px, calc(100vw - 16px))' }, children: jsx(Panel, { data, ctx }) })
  ] })
}

export default {
  id: ID,
  name: 'Usage meter',
  register(ctx) {
    ctx.register({ id: 'meter', area: STATUSBAR_AREAS.right, order: 5, render: () => jsx(Meter, { ctx }) })
  }
}
