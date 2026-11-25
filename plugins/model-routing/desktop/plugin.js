// model-routing usage meter for the Hermes desktop app: a status-bar chip with one reading per
// subscription (weekly remaining %, dot coloured by pace) and a popover with the detail. Data comes from
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
const METER_SHORT = { claude: 'Cl', codex: 'GPT', supergrok: 'Gr' }

function tone(c) {
  if (!c.fresh) return ['muted', 'no data']
  if (!c.eligible) return ['bad', c.reason || 'not eligible']
  if (c.pace_delta != null && c.pace_delta < 0) return ['warn', 'over pace']
  return ['good', 'under pace']
}

const pct = v => (!Number.isFinite(v) ? '–' : v > 0 && v < 1 ? '<1%' : `${Math.round(v)}%`)
const signed = v => (v == null ? '' : `${v > 0 ? '+' : ''}${Math.round(v)}pp`)
const money = v => Number.isFinite(v) ? `$${v.toFixed(2)}` : '–'
const compactMoney = v => money(v).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1')
const remaining = v => Number.isFinite(v) ? Math.max(0, Math.min(100, 100 - v)) : null
const isAgy = c => c.id === 'agy' || c.display_only

function windowWord(windowKind) {
  if (windowKind === 'weekly') return 'weekly'
  if (windowKind === '5h') return '5-hour'
  return windowKind || 'window'
}

function agySummary(c) {
  const summary = c.fresh ? c.summary : null
  return summary && Number.isFinite(summary.remaining_percent) ? summary : null
}

function agyPace(c) {
  const summary = agySummary(c)
  return summary && Number.isFinite(summary.pace_delta) ? summary.pace_delta : null
}

function agyAccess(c) {
  const summary = agySummary(c)
  if (!c.fresh) return 'Antigravity quota unavailable. Other model groups are separate.'
  if (!summary) return 'Antigravity has no weekly group reading. Other model groups are separate.'
  const windowKind = windowWord(summary.window)
  const pace = agyPace(c)
  const paceText = pace == null ? '' : ` Pace headroom ${signed(pace)}.`
  if (summary.remaining_percent === 0) {
    return `Antigravity ${summary.group_name} ${windowKind} allowance is exhausted, 0% remaining.${paceText} Other model groups are separate.`
  }
  return `Antigravity ${summary.group_name} ${windowKind} ${pct(summary.remaining_percent)} remaining.${paceText} Other model groups are separate.`
}

function agyChipText(c, compact) {
  const provider = compact ? 'Ag' : 'AGY'
  const summary = agySummary(c)
  if (!summary) return `${provider} ${pct(null)}`
  const pace = agyPace(c)
  const paceText = !compact && pace != null ? ` P${signed(pace)}` : ''
  return `${provider} ${summary.tag} ${pct(summary.remaining_percent)}${paceText}`
}

// Pace is the meter's contract: the dot follows the Gemini pool's pace when it has one, and
// falls back to remaining-quota thresholds when the reset is too far out to pace.
const AGY_WARN_REMAINING = 20
const AGY_BAD_REMAINING = 10

function agyTone(c) {
  const summary = agySummary(c)
  if (!summary || !Number.isFinite(summary.remaining_percent)) return 'muted'
  if (Number.isFinite(summary.pace_delta)) return summary.pace_delta < 0 ? 'warn' : 'good'
  const left = summary.remaining_percent
  if (left <= AGY_BAD_REMAINING) return 'bad'
  if (left <= AGY_WARN_REMAINING) return 'warn'
  return 'good'
}

// A single status-bar row, not another mobile toolbar. Reserve enough of the
// right cluster for the compact meter; the other status items can still clip.
const METER_CSS = `
  [data-usage-compact] { display: none; }
  [data-usage-full], [data-usage-compact] { max-width: 100%; min-width: 0; }
  [data-slot="statusbar"] > :last-child:has([data-subscription-meter]) {
    flex-shrink: 0;
    min-width: 0;
    max-width: calc(100dvw - 2.5rem);
  }
  @media (max-width: 600px) {
    [data-usage-full] { display: none !important; }
    [data-usage-compact] { display: inline-flex; }
  }
  @media (max-width: 400px) {
    [data-usage-compact] {
      gap: 2px !important;
      font-size: 10px !important;
      letter-spacing: -0.03em;
    }
    [data-usage-compact] > span { gap: 1px !important; }
    [data-usage-compact] span[aria-hidden="true"] {
      width: 4px !important;
      height: 4px !important;
    }
  }
`

function Row({ c }) {
  const [t, word] = tone(c)
  return jsxs('div', {
    style: { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: '2px 12px', padding: '6px 0',
      borderBottom: '1px solid var(--ui-stroke-secondary)', minWidth: 0 },
    children: [
      jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, minWidth: 0, overflowWrap: 'anywhere' }, children: [
        jsx(StatusDot, { tone: t }), `${c.name} ${c.plan || ''}`,
        c.picked ? jsx('span', { style: { fontSize: 10, color: 'var(--ui-accent)' }, children: '· current pick' }) : null
      ] }),
      jsx('div', { style: { fontWeight: 700, fontSize: 15 }, children: `${pct(remaining(c.used_percent))}  P: ${signed(c.pace_delta)}` }),
      jsx('div', { style: { color: 'var(--ui-text-tertiary)', fontSize: 11 }, children:
        `${word} · week resets ${c.reset_label || '?'}` +
        (c.short_used_percent != null ? ` · 5-hour ${pct(remaining(c.short_used_percent))}` : '') }),
      jsx('div', { style: { color: 'var(--ui-text-tertiary)', fontSize: 11, textAlign: 'right' }, children:
        c.pace_used_percent != null ? `pace target ${pct(remaining(c.pace_used_percent))}` : '' })
    ]
  })
}

function groupMetric(group) {
  const buckets = group.buckets || []
  return buckets.find(bucket => bucket.window === 'weekly' && Number.isFinite(bucket.remaining_percent))
    || buckets.find(bucket => Number.isFinite(bucket.remaining_percent))
    || null
}

const rate = v => !Number.isFinite(v) ? '–' : v === 0 ? 'free' : String(Number(v.toPrecision(3)))

function Section({ label, children }) {
  return jsxs('div', { style: { marginTop: 6, minWidth: 0 }, children: [
    jsx('div', {
      style: { fontSize: 9.5, fontWeight: 700, letterSpacing: '.07em', textTransform: 'uppercase',
        color: 'var(--ui-text-quaternary)', borderBottom: '1px solid var(--ui-stroke-secondary)',
        paddingBottom: 2, marginBottom: 1 },
      children: label
    }),
    ...children
  ] })
}

function AgyDetails({ c }) {
  const groups = c.fresh ? (c.groups || []) : []
  const summary = agySummary(c)
  return jsxs('div', {
    'data-agy-details': '',
    style: { padding: '5px 0', borderBottom: '1px solid var(--ui-stroke-secondary)', minWidth: 0 },
    children: [
      jsxs('div', { style: { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: '2px 12px', alignItems: 'center' }, children: [
        jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, minWidth: 0 }, children: [
          jsx(StatusDot, { tone: agyTone(c) }), 'Antigravity'
        ] }),
        summary ? jsxs('div', { 'data-agy-summary': '', style: { textAlign: 'right' }, children: [
          jsx('div', { style: { fontWeight: 700, fontSize: 14, fontVariantNumeric: 'tabular-nums' }, children: pct(summary.remaining_percent) }),
          Number.isFinite(summary.pace_delta)
            ? jsx('div', { 'data-agy-pace': '', style: { fontSize: 10, color: 'var(--ui-text-tertiary)', fontVariantNumeric: 'tabular-nums' },
                children: `P: ${signed(summary.pace_delta)}` })
            : null
        ] }) : null
      ] }),
      groups.length ? groups.map(group => {
        const metric = groupMetric(group)
        return jsxs('div', {
          'data-agy-group': group.name,
          style: { minWidth: 0, marginTop: 3, paddingLeft: 6, borderLeft: '2px solid var(--ui-stroke-secondary)' },
          children: [
            jsxs('div', { style: { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: '2px 8px', alignItems: 'baseline' }, children: [
              jsx('div', { style: { fontWeight: 600, minWidth: 0, overflowWrap: 'anywhere' }, children: group.name }),
              metric ? jsx('div', { 'data-agy-metric': metric.id, style: { fontWeight: 700, fontVariantNumeric: 'tabular-nums' }, children: pct(metric.remaining_percent) }) : null
            ] }),
            ...(group.buckets || []).map(bucket => jsx('div', {
              'data-agy-bucket': bucket.id,
              style: { color: 'var(--ui-text-tertiary)', fontSize: 10.5, minWidth: 0, overflowWrap: 'anywhere', fontVariantNumeric: 'tabular-nums' },
              children: `${windowWord(bucket.window)} ${pct(bucket.remaining_percent)} remaining, resets ${bucket.reset_label || '?'}`
            }, bucket.id))
          ]
        }, group.name)
      }) : jsx('div', {
        style: { color: 'var(--ui-text-tertiary)', fontSize: 11 },
        children: c.reason || 'quota unavailable'
      })
    ]
  })
}

function PaygSection({ data }) {
  const o = data.openrouter || {}
  const ci = data.cheaperinference || {}
  const models = (ci.status === 'ok' ? (ci.models || []) : [])
    .filter(row => String(row.id).startsWith('deepseek') && !String(row.id).endsWith('-ultrafast'))
    .slice(0, 2)
  const spend = ci.status === 'ok' ? (ci.spend || null) : null
  const shortModel = id => String(id).replace(/^deepseek-v4\.1-flash-/, '').replace(/-/g, ' ')
  return jsx(Section, { label: 'Pay per use', children: [
    jsxs('div', {
      'data-payg-openrouter': '',
      style: { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: '1px 10px', padding: '3px 0',
        borderBottom: '1px dotted var(--ui-stroke-secondary)', minWidth: 0 },
      children: [
        jsx('div', { style: { fontWeight: 600, minWidth: 0 }, children: 'OpenRouter' }),
        jsx('div', { style: { fontWeight: 700, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }, children: `W ${money(o.week)}  D ${money(o.today)}` }),
        jsx('div', { style: { color: 'var(--ui-text-tertiary)', fontSize: 10.5 }, children: 'UTC spend' }),
        jsx('div', { style: { color: 'var(--ui-text-tertiary)', fontSize: 10.5, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }, children: `M ${money(o.month)} · bal ${money(o.balance)}` })
      ]
    }),
    jsxs('div', {
      'data-payg-cheaperinference': '',
      style: { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: '1px 10px', padding: '3px 0',
        borderBottom: '1px dotted var(--ui-stroke-secondary)', minWidth: 0 },
      children: [
        jsx('div', { style: { fontWeight: 600, minWidth: 0 }, children: 'Cheaper Inference' }),
        jsx('div', { style: { fontWeight: 700, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }, children:
          spend ? `W ${money(spend.week)}  D ${money(spend.today)}` : '–' }),
        jsx('div', { style: { color: 'var(--ui-text-tertiary)', fontSize: 10.5 }, children: 'UTC spend' }),
        jsx('div', { style: { color: 'var(--ui-text-tertiary)', fontSize: 10.5, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }, children:
          spend ? `M ${money(spend.month)}${Number.isFinite(spend.balance) ? ` · bal ${money(spend.balance)}` : ''}`
            : (ci.spend_error || ci.error || 'spend unavailable') })
      ]
    }),
    models.length ? jsxs('div', { 'data-ci-rates': '', style: { paddingTop: 2, minWidth: 0 }, children: [
      jsx('div', { style: { fontSize: 10, color: 'var(--ui-text-tertiary)', paddingBottom: 1 }, children: 'deepseek · $/M in/out' }),
      ...models.map(row => jsxs('div', {
        'data-ci-model': row.id,
        style: { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 46px 46px 30px', gap: '0 6px',
          fontSize: 10.5, fontVariantNumeric: 'tabular-nums', padding: '1px 0', minWidth: 0 },
        children: [
          jsx('span', { title: row.id, style: { fontWeight: row.id === ci.active_model ? 700 : 500 }, children: shortModel(row.id) }),
          jsx('span', { style: { textAlign: 'right' }, children: rate(row.input) }),
          jsx('span', { style: { textAlign: 'right' }, children: rate(row.output) }),
          jsx('span', { style: { textAlign: 'right', color: 'var(--ui-text-tertiary)' },
            children: row.discount ? `-${Math.round(row.discount)}%` : '—' })
        ]
      }, row.id)),
      models.some(row => row.id === ci.active_model)
        ? jsx('div', { style: { color: 'var(--ui-text-tertiary)', fontSize: 10, paddingTop: 1 }, children: 'Bold = current model' })
        : null
    ] }) : null
  ] })
}

function Panel({ data, ctx }) {
  const [busy, setBusy] = useState(false)
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
  const blank = (data.cards || []).filter(c => !isAgy(c) && !Number.isFinite(remaining(c.used_percent)))
  return jsxs('div', {
    'data-subscription-panel': '',
    style: { fontSize: 12, padding: 4, minWidth: 0, maxWidth: '100%', maxHeight: 'min(78dvh, calc(100dvh - 40px))', overflow: 'auto', overflowWrap: 'anywhere' },
    children: [
    jsx('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8, fontWeight: 600 }, children: [
      jsx('span', { children: 'Usage' }),
      jsx('span', { style: { color: 'var(--ui-text-quaternary)', fontSize: 10, fontWeight: 400 },
        children: data.written_at ? `read ${new Date(data.written_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}` : 'not read yet' })
    ] }),
    jsx(Section, { label: 'Subscriptions', children: [
      ...(data.cards || []).filter(c => !isAgy(c)).map(c => jsx(Row, { c }, c.id)),
      (data.cards || []).some(isAgy) ? jsx(AgyDetails, { c: (data.cards || []).find(isAgy) }, 'agy') : null,
      blank.length ? jsx('div', { style: { color: 'var(--ui-text-quaternary)', fontSize: 10, paddingTop: 2 },
        children: `No reading: ${blank.map(c => c.name).join(', ')}` }) : null
    ] }),
    jsx(PaygSection, { data }),
    jsx('div', { style: { color: 'var(--ui-text-quaternary)', fontSize: 10, margin: '6px 0 6px' }, children:
      (data.on_demand && data.on_demand.active ? 'Routing: on-demand OpenRouter. '
        : pick ? `Routing: ${SHORT[pick.subscription] || pick.subscription}${pick.model ? ` (${pick.model})` : ''}. ` : 'No routing pick. ') +
      'Quota percentages are remaining; P is pace headroom in percentage points.' }),
    jsxs('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' }, children: [
      jsx('span', { style: { color: 'var(--ui-text-quaternary)', fontSize: 10 },
        children: 'Antigravity groups are separate; Gemini pace uses its own week.' }),
      jsx(Button, { variant: 'ghost', size: 'sm', disabled: busy, onClick: refresh, children: busy ? 'Reading…' : 'Refresh' })
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
  const ci = data.cheaperinference || {}
  const ciSpend = ci.status === 'ok' ? (ci.spend || null) : null
  const chips = (compact) => (data.cards || []).flatMap(c => {
    if (isAgy(c)) {
      if (!agySummary(c)) return []
      const label = agyAccess(c)
      return [jsxs('span', {
        key: c.id, 'data-agy-chip': '', 'aria-label': label, title: label,
        style: { display: 'inline-flex', alignItems: 'center', gap: 4 },
        children: [jsx(StatusDot, { tone: agyTone(c) }), agyChipText(c, compact)]
      })]
    }
    const left = remaining(c.used_percent)
    if (!Number.isFinite(left)) return []
    const [t, word] = tone(c)
    return [jsxs('span', { key: c.id, 'aria-label': `${c.name} ${pct(left)} remaining, ${word}`,
      style: { display: 'inline-flex', alignItems: 'center', gap: 4 }, children: [
        jsx(StatusDot, { tone: t }),
        `${METER_SHORT[c.id] || c.name} ${pct(left)}${!compact && c.pace_delta != null ? ` P${signed(c.pace_delta)}` : ''}`
      ] })]
  })
  const ciDetail = ciSpend
    ? `Cheaper Inference spending: this week (UTC) ${money(ciSpend.week)}, today (UTC) ${money(ciSpend.today)}` +
      `, this month (UTC) ${money(ciSpend.month)}`
    : 'Cheaper Inference spend unavailable'
  const ciChip = ciSpend
    ? jsx('span', { 'data-ci-chip': '', 'aria-label': ciDetail, title: ciDetail,
        style: { display: 'inline-flex', alignItems: 'center', gap: 4 }, children: [
          jsx(StatusDot, { tone: 'muted' }), `CI W${compactMoney(ciSpend.week)} D${compactMoney(ciSpend.today)}`
        ] }, 'ci')
    : null
  const costDetail = `OpenRouter spending: this week (UTC) ${money(o.week)}, today (UTC) ${money(o.today)}`
  const cost = jsx('span', { 'aria-label': costDetail, title: costDetail, children: `OR W${compactMoney(o.week)} D${compactMoney(o.today)}` }, 'or')
  return jsxs(Popover, { open, onOpenChange: setOpen, children: [
    jsx('style', { children: METER_CSS }),
    jsx(PopoverTrigger, { asChild: true, children: jsx(Button, {
      variant: 'ghost', size: 'micro', 'aria-label': 'Subscription usage',
      'data-subscription-meter': '',
      children: [
        jsxs('span', { key: 'full', 'data-usage-full': '', style: { display: 'inline-flex', flexWrap: 'nowrap', whiteSpace: 'nowrap', gap: 10, fontSize: 11, color: 'var(--ui-text-secondary)' }, children: [...chips(false), ciChip, cost] }),
        jsxs('span', { key: 'compact', 'data-usage-compact': '', style: { alignItems: 'center', flexWrap: 'nowrap', whiteSpace: 'nowrap', gap: 6, fontSize: 11, color: 'var(--ui-text-secondary)' }, children: [...chips(true), ciChip, cost] })
      ]
    }) }),
    jsx(PopoverContent, {
      side: 'top', align: 'end', collisionPadding: 8,
      style: { width: 'min(360px, calc(100dvw - 16px))', maxWidth: 'calc(100dvw - 16px)' },
      children: jsx(Panel, { data, ctx })
    })
  ] })
}

export default {
  id: ID,
  name: 'Usage meter',
  register(ctx) {
    ctx.register({ id: 'meter', area: STATUSBAR_AREAS.right, order: 5, render: () => jsx(Meter, { ctx }) })
  }
}
