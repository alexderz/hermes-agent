import { useState } from 'react'

import { ClarifyShell } from '@/components/assistant-ui/clarify/core/shell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useI18n } from '@/i18n'
import { $gateway } from '@/store/gateway'
import { reconnectAction } from '@/store/gateway-reconnect'
import { notify, notifyError } from '@/store/notifications'
import { clearSecretRequest, readSecretDraft, type SecretRequest, writeSecretDraft } from '@/store/prompts'
import { respondToServerRequest } from '@/store/server-requests'

/** The draft never enters the transcript or a persistent store. */
export function SecretCard({ request }: { request: SecretRequest }) {
  const { t } = useI18n()
  const [value, setValue] = useState(() => readSecretDraft(request))
  const [submitting, setSubmitting] = useState(false)
  const destination = request.destination
  const owner = destination?.group ? `${destination.owner}:${destination.group}` : (destination?.owner ?? '')

  function send(answer: string) {
    if (submitting) {
      return
    }

    if (!$gateway.get()) {
      notifyError(new Error(t.prompts.gatewayDisconnected), t.prompts.secretSendFailed, { action: reconnectAction() })

      return
    }

    setSubmitting(true)

    try {
      const sent = respondToServerRequest(request.requestId, { value: answer })
      setValue('')
      clearSecretRequest(request.sessionId, request.requestId, request)

      if (!sent) {
        notify({ kind: 'info', message: t.prompts.secretNoLongerOpen })
      }
    } catch (error) {
      notifyError(error, t.prompts.secretSendFailed)
      setSubmitting(false)
    }
  }

  return (
    <form
      className="min-w-0"
      data-slot="secret-inline"
      onSubmit={event => {
        event.preventDefault()
        send(value)
      }}
    >
      <ClarifyShell className="grid min-w-0 gap-3">
        <div>
          <div className="font-medium break-all">{request.envVar || t.prompts.secretTitle}</div>
          <div className="text-(--ui-text-secondary)">{request.prompt || t.prompts.secretDesc}</div>
        </div>
        {destination && (
          <section aria-label={t.prompts.secretSavedTo} className="grid min-w-0 gap-1 text-xs">
            <span className="text-(--ui-text-secondary)">{t.prompts.secretSavedTo}</span>
            <code className="font-mono break-all whitespace-pre-wrap">{destination.path}</code>
            <span className="text-(--ui-text-secondary)">{t.prompts.secretFileFacts(destination.mode, owner)}</span>
          </section>
        )}
        <Input
          aria-label={request.envVar || t.prompts.secretPlaceholder}
          autoComplete="off"
          disabled={submitting}
          onChange={event => {
            setValue(event.target.value)
            writeSecretDraft(request, event.target.value)
          }}
          placeholder={request.envVar || t.prompts.secretPlaceholder}
          type="password"
          value={value}
        />
      </ClarifyShell>
      <div className="mt-2 flex justify-end gap-2">
        <Button disabled={submitting} onClick={() => send('')} type="button" variant="ghost">
          {t.common.cancel}
        </Button>
        <Button disabled={submitting || !value} type="submit">
          {t.common.save}
        </Button>
      </div>
    </form>
  )
}
