import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { atom } from 'nanostores'
import { afterEach, expect, it } from 'vitest'

import { ChatRuntimeBoundary } from '@/app/chat'
import { PRIMARY_SESSION_VIEW, SessionViewProvider } from '@/app/chat/session-view'
import { stubThreadEnvironment, stubThreadViewportSize } from '@/components/assistant-ui/test-utils'
import { Thread } from '@/components/assistant-ui/thread'
import { I18nProvider } from '@/i18n'
import { type ChatMessage } from '@/lib/chat-messages'
import { $activeGatewayProfile } from '@/store/profile'
import { clearAllPrompts, clearSecretRequest, readSecretDraft, sessionSecretRequest, setSecretRequest, writeSecretDraft } from '@/store/prompts'
import { $activeSessionId, $connection } from '@/store/session'

stubThreadEnvironment()
stubThreadViewportSize()
afterEach(() => {cleanup(); clearAllPrompts(); $activeSessionId.set(null); $connection.set(null)})
const req = {sessionId:'s1', requestId:'srq-test',envVar:'TEST_KEY',prompt:'Dummy',profile:'default'}
function mount(messages: ChatMessage[]) {
  $activeGatewayProfile.set('default')
  $activeSessionId.set('s1')
  setSecretRequest(req)
  const $messages = atom(messages)
  const view = {...PRIMARY_SESSION_VIEW,$messages,$runtimeId:atom<string|null>('s1'),$storedId:atom<string|null>(null)}
  const v=render(<I18nProvider configClient={null}><SessionViewProvider value={view}>
    <ChatRuntimeBoundary busy onCancel={()=>{}} onEdit={async()=>{}} onReload={async()=>{}} onThreadMessagesChange={()=>{}} suppressMessages={false}>
      <Thread/>
    </ChatRuntimeBoundary>
  </SessionViewProvider></I18nProvider>)
  return {...v,$messages}
}
it.each([
 {connectionId:'conn-a',profile:'other'},
 {connectionId:'conn-b',profile:'default'}
])('does not erase an independent live draft on another scope: %j', otherScope=>{
 const a={...req,connectionId:'conn-a'}
 const b={...req,...otherScope,requestId:'srq-other'}
 setSecretRequest(a)
 writeSecretDraft(a,'dummy-a')
 setSecretRequest(b)
 expect(readSecretDraft(b)).toBe('')
 expect(readSecretDraft(a)).toBe('dummy-a')
 expect(sessionSecretRequest('s1', a).get()?.requestId).toBe(a.requestId)
 expect(sessionSecretRequest('s1', b).get()?.requestId).toBe(b.requestId)
 writeSecretDraft(b, 'dummy-b')
 clearSecretRequest('s1', a.requestId, a)
 expect(sessionSecretRequest('s1', a).get()).toBeNull()
 expect(sessionSecretRequest('s1', b).get()?.requestId).toBe(b.requestId)
 expect(readSecretDraft(b)).toBe('dummy-b')
})
it.each(['profile', 'connection'])('renders independent colliding session requests when switching %s', async dimension => {
 const a = {...req, connectionId: 'conn-a', requestId: 'a', envVar: 'KEY_A'}
 const b = {...req, connectionId: dimension === 'connection' ? 'conn-b' : 'conn-a', profile: dimension === 'profile' ? 'other' : 'default', requestId: 'b', envVar: 'KEY_B'}
 const messages: ChatMessage[] = [{id:'m1',role:'assistant',pending:true,parts:[{type:'tool-call',toolCallId:'skill-1',toolName:'skill_view',args:{},argsText:'{}'}]}]
 const $messages = atom(messages)
 const view = {...PRIMARY_SESSION_VIEW,$messages,$runtimeId:atom<string|null>('s1'),$storedId:atom<string|null>(null)}
 $activeSessionId.set('s1')
 $activeGatewayProfile.set('default')
 $connection.set({connectionId:'conn-a',mode:'ssh'} as never)
 setSecretRequest(a)
 setSecretRequest(b)
 render(<I18nProvider configClient={null}><SessionViewProvider value={view}><ChatRuntimeBoundary busy onCancel={()=>{}} onEdit={async()=>{}} onReload={async()=>{}} onThreadMessagesChange={()=>{}} suppressMessages={false}><Thread/></ChatRuntimeBoundary></SessionViewProvider></I18nProvider>)
 fireEvent.change(await screen.findByLabelText('KEY_A'), {target:{value:'dummy-a'}})
 act(() => { $activeGatewayProfile.set(b.profile); $connection.set({connectionId:b.connectionId,mode:'ssh'} as never) })
 fireEvent.change(await screen.findByLabelText('KEY_B'), {target:{value:'dummy-b'}})
 act(() => { $activeGatewayProfile.set(a.profile); $connection.set({connectionId:a.connectionId,mode:'ssh'} as never) })
 expect((await screen.findByLabelText('KEY_A') as HTMLInputElement).value).toBe('dummy-a')
 act(() => clearSecretRequest('s1', a.requestId, a))
 act(() => { $activeGatewayProfile.set(b.profile); $connection.set({connectionId:b.connectionId,mode:'ssh'} as never) })
 expect((await screen.findByLabelText('KEY_B') as HTMLInputElement).value).toBe('dummy-b')
})
it('keeps the same anchored secret input when a parallel tool adds a later assistant row', async()=>{
 const initial: ChatMessage[]=[{id:'m1',role:'assistant',pending:true,parts:[{type:'tool-call',toolCallId:'skill-1',toolName:'skill_view',args:{name:'dummy'},argsText:'{}'}]}]
 const {$messages}=mount(initial)
 const input=await screen.findByLabelText('TEST_KEY') as HTMLInputElement
 fireEvent.change(input,{target:{value:'dummy-unsubmitted'}})
 input.focus()
 const beforeAnchor = input.closest('[data-message-id]')?.getAttribute('data-message-id')
 expect(document.activeElement === input).toBe(true)
 act(()=> $messages.set([...initial,{id:'m2',role:'assistant',pending:true,parts:[{type:'text',text:'Parallel tool progress'}]}]))
 await waitFor(() => expect(screen.getByText('Parallel tool progress')).toBeTruthy())
 const next=screen.getByLabelText('TEST_KEY') as HTMLInputElement
 const afterAnchor = next.closest('[data-message-id]')?.getAttribute('data-message-id')
 expect(next.value).toBe('dummy-unsubmitted')
 expect(readSecretDraft(req)).toBe('dummy-unsubmitted')
 expect(afterAnchor).toBe(beforeAnchor)
 expect(document.activeElement === next).toBe(true)
})
it('does not move the pending secret beneath a queued future-turn user prompt', async()=>{
 const initial: ChatMessage[]=[{id:'m1',role:'assistant',pending:true,parts:[{type:'tool-call',toolCallId:'skill-1',toolName:'skill_view',args:{name:'dummy'},argsText:'{}'}]}]
 const {$messages}=mount(initial)
 const input=await screen.findByLabelText('TEST_KEY') as HTMLInputElement
 fireEvent.change(input,{target:{value:'dummy-unsubmitted'}})
 const beforeAnchor=input.closest('[data-message-id]')?.getAttribute('data-message-id')
 act(()=> $messages.set([...initial,{id:'user-queued-next',role:'user',parts:[{type:'text',text:'Future queued prompt'}]}]))
 await waitFor(() => expect(screen.getByText('Future queued prompt')).toBeTruthy())
 const afterAnchor=screen.getByLabelText('TEST_KEY').closest('[data-message-id]')?.getAttribute('data-message-id')
 expect(afterAnchor).toBe(beforeAnchor)
})
it('keeps the same anchored secret input when pending replay arrives without a provider clarify row', async()=>{
 mount([{id:'m1',role:'assistant',pending:true,parts:[{type:'tool-call',toolCallId:'skill-1',toolName:'skill_view',args:{},argsText:'{}'}]}])
 const input=await screen.findByLabelText('TEST_KEY') as HTMLInputElement
 fireEvent.change(input,{target:{value:'dummy-unsubmitted'}})
 input.focus()
 act(()=>setSecretRequest({...req}))
 const next=await screen.findByLabelText('TEST_KEY') as HTMLInputElement
 expect(next.value).toBe('dummy-unsubmitted')
 expect(next).toBe(input)
 expect(document.activeElement).toBe(input)
})
