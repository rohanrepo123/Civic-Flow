import { useEffect, useState } from 'react'
import { ArrowDown, ArrowUpRight, Check, ChevronRight, CircleHelp, ClipboardList, FileText, Globe2, Landmark, LoaderCircle, LogOut, MessageSquareText, Plus, ShieldCheck, Upload, UserRound, X } from 'lucide-react'

type Task = { task_id: string; status: string; user_request: string; summary?: string; state?: Record<string, any> }
type EventItem = { event_id: string; sequence: number; type: string; timestamp: string; payload: Record<string, any> }
const API = import.meta.env.VITE_API_URL || ''
const CONVERSATION_INTENTS = new Set(['casual_conversation', 'out_of_scope'])

function taskIntent(task: Task): string | undefined {
  return task.state?.intent?.intent
}

function isConversationTask(task: Task): boolean {
  return CONVERSATION_INTENTS.has(taskIntent(task) || '')
}

function TaskRow({ task, selected, onSelect, conversation = false }: { task: Task; selected: boolean; onSelect: () => void; conversation?: boolean }) {
  return <button className={`task-row ${selected ? 'selected' : ''}`} onClick={onSelect}><div className="task-symbol">{conversation ? <MessageSquareText size={17}/> : <ClipboardList size={17}/>}</div><div className="task-copy"><b>{task.user_request}</b><span>{task.summary || (conversation ? 'Continue this conversation with CivicFlow.' : 'CivicFlow is preparing your next steps.')}</span></div><Status status={task.status}/><ChevronRight size={16}/></button>
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('civicflow_token') || '')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [registering, setRegistering] = useState(false)
  const [error, setError] = useState('')
  const [tasks, setTasks] = useState<Task[]>([])
  const [active, setActive] = useState<Task | null>(null)
  const [events, setEvents] = useState<EventItem[]>([])
  const [request, setRequest] = useState('')
  const [answerValues, setAnswerValues] = useState<Record<string, string>>({})
  const [clarificationService, setClarificationService] = useState('')
  const [clarificationJurisdiction, setClarificationJurisdiction] = useState('')
  const [busy, setBusy] = useState(false)
  const [documents, setDocuments] = useState<any[]>([])
  const [documentType, setDocumentType] = useState('')
  const [requireApproval, setRequireApproval] = useState(false)
  const [profile, setProfile] = useState<Record<string, any>>({})
  const [profileText, setProfileText] = useState('{}')

  async function api(path: string, options: RequestInit = {}) {
    const response = await fetch(`${API}/api/v1${path}`, { ...options, headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } })
    if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || `Request failed (${response.status})`)
    return response.status === 204 ? null : response.json()
  }

  async function refresh() {
    if (!token) return
    try {
      const [taskRows, docRows, profileRow] = await Promise.all([api('/tasks'), api('/documents'), api('/profile')])
      setTasks(taskRows); setDocuments(docRows); setProfile(profileRow.data || {})
      if (document.activeElement?.id !== 'profile-data') setProfileText(JSON.stringify(profileRow.data || {}, null, 2))
      if (active) {
        const latest = taskRows.find((row: Task) => row.task_id === active.task_id)
        if (latest) { setActive(latest); setEvents(await api(`/tasks/${active.task_id}/events`)) }
      }
    } catch (e) { setError((e as Error).message) }
  }

  useEffect(() => { refresh() }, [token, active?.task_id])
  useEffect(() => { if (!token) return; const timer = setInterval(refresh, 2200); return () => clearInterval(timer) }, [token, active?.task_id])

  const applicationTasks = tasks.filter(task => Boolean(taskIntent(task)) && !isConversationTask(task))
  const conversationTasks = tasks.filter(isConversationTask)

  async function signIn(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const response = await fetch(`${API}/api/v1/auth/${registering ? 'register' : 'login'}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) })
      const contentType = response.headers.get('content-type') || ''
      const body = contentType.includes('application/json') ? await response.json() : null
      if (!response.ok) throw new Error(body?.detail || `Request failed (${response.status})`)
      if (!body?.access_token) throw new Error('The backend returned no access token')
      localStorage.setItem('civicflow_token', body.access_token); setToken(body.access_token)
    }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  async function startTask(event: React.FormEvent) {
    event.preventDefault(); if (!request.trim()) return; setBusy(true); setError('')
    try { const task = await api('/tasks', { method: 'POST', body: JSON.stringify({ user_request: request, require_approval: requireApproval }) }); setRequest(''); setActive(task); await refresh() }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  async function upload(file?: File) {
    if (!file) return
    const form = new FormData(); form.append('file', file); if (documentType) form.append('document_type', documentType)
    try { await api('/documents', { method: 'POST', body: form }); await refresh() } catch (e) { setError((e as Error).message) }
  }

  async function saveProfile() {
    try { const data = JSON.parse(profileText); const response = await api('/profile', { method: 'PUT', body: JSON.stringify(data) }); setProfile(response.data); setError('Profile saved') } catch (e) { setError((e as Error).message) }
  }

  async function resumeTask(value?: Record<string, any>) {
    try { await api(`/tasks/${active?.task_id}/resume`, { method: 'POST', body: JSON.stringify({ value: value || answerValues }) }); setAnswerValues({}); await refresh() } catch (e) { setError((e as Error).message) }
  }

  async function decideApproval(approved: boolean) {
    const approvalId = active?.state?.pending_prompt?.approval_id
    if (!approvalId) return
    try { await api(`/approvals/${approvalId}/decision`, { method: 'POST', body: JSON.stringify({ approved }) }); await resumeTask({}) }
    catch (e) { setError((e as Error).message) }
  }

  if (!token) return <main className="auth-screen"><section className="auth-card"><div className="brand"><span className="brand-icon"><Landmark size={19}/></span><span>CivicFlow</span></div><p className="eyebrow">PUBLIC SERVICES, MADE CLEARER</p><h1>{registering ? 'Create your account' : 'Welcome back'}</h1><p className="muted">Your private workspace for understanding and preparing applications.</p><form onSubmit={signIn} className="auth-form"><label>Email address<input type="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com"/></label><label>Password<input type="password" required minLength={10} value={password} onChange={e => setPassword(e.target.value)} placeholder="At least 10 characters"/></label>{error && <div className="error">{error}</div>}<button className="primary" disabled={busy}>{busy ? 'Please wait…' : registering ? 'Create account' : 'Sign in'}<ArrowUpRight size={16}/></button></form><button className="link-button" onClick={() => setRegistering(!registering)}>{registering ? 'Already have an account? Sign in' : 'New to CivicFlow? Create an account'}</button><div className="secure-note"><ShieldCheck size={15}/> Your profile and documents stay private to your account.</div></section></main>

  return <div className="app-shell">
    <aside className="sidebar"><div className="brand"><span className="brand-icon"><Landmark size={19}/></span><span>CivicFlow</span></div><div className="workspace-label">WORKSPACE</div><button className="nav-item active"><ClipboardList size={17}/> My applications</button><button className="nav-item" onClick={() => document.getElementById('profile')?.scrollIntoView({ behavior: 'smooth' })}><UserRound size={17}/> My profile</button><button className="nav-item" onClick={() => document.getElementById('documents')?.scrollIntoView({ behavior: 'smooth' })}><FileText size={17}/> Documents <span className="count">{documents.length}</span></button><div className="sidebar-bottom"><div className="help-card"><CircleHelp size={17}/><span>Need a hand?<small>Learn how CivicFlow works</small></span><ChevronRight size={15}/></div><button className="user-row" onClick={() => { localStorage.removeItem('civicflow_token'); setToken(''); setActive(null) }}><div className="avatar">{email.slice(0,1).toUpperCase() || 'C'}</div><span>{email || 'Your account'}<small>Sign out</small></span><LogOut size={15}/></button></div></aside>
    <main className="main-content"><header className="topbar"><div><div className="breadcrumb">Workspace <ChevronRight size={13}/> Applications</div><h1>My applications</h1></div><div className="top-actions"><span className="privacy"><ShieldCheck size={14}/> Private workspace</span><button className="avatar small">{email.slice(0,1).toUpperCase() || 'C'}</button></div></header>
      <div className="content-grid"><section className="left-column"><div className="welcome"><div><p className="eyebrow">YOUR NEXT STEP, MADE SIMPLE</p><h2>What would you like help with?</h2><p>Tell us what you need. We’ll help you understand the requirements and prepare.</p></div><div className="welcome-art"><div className="art-sun"/><div className="art-building"><span/><span/><span/><b/></div><div className="art-ground"/></div></div>
        <form className="request-card" onSubmit={startTask}><label htmlFor="request">Message CivicFlow</label><textarea id="request" value={request} onChange={e => setRequest(e.target.value)} placeholder="Ask about a form, scheme, application—or just say hello…"/><div className="request-footer"><span><ShieldCheck size={14}/> Your information stays private</span><label className="approval-option"><input type="checkbox" checked={requireApproval} onChange={e => setRequireApproval(e.target.checked)}/> Pause for your approval</label><button className="primary" disabled={busy || !request.trim()}>{busy ? <LoaderCircle size={16} className="spin"/> : <>Start chat <ArrowUpRight size={16}/></>}</button></div></form>
        {active && <section className="panel chat-panel"><div className="panel-title"><div className="panel-icon"><MessageSquareText size={17}/></div><div><h3>Conversation</h3><p>Chat with CivicFlow about this request</p></div></div><div className="chat-thread"><div className="chat-message user-message"><div className="chat-avatar user-chat-avatar">You</div><div><span className="chat-role">You</span><p>{active.user_request}</p></div></div><div className="chat-message assistant-message"><div className="chat-avatar assistant-chat-avatar">C</div><div><span className="chat-role">CivicFlow</span><p>{active.state?.pending_prompt?.question || active.state?.pending_prompt?.message || active.summary || (active.status === 'running' ? 'I’m reviewing your request and preparing the next step…' : 'I’m ready to help with your public-service request.')}</p>{active.status === 'completed' && <small className="chat-meta">No application was submitted automatically.</small>}</div></div></div></section>}
        <div className="section-heading"><div><h3>Recent applications</h3><p>Track the progress of your applications</p></div><span className="subtle-count">{applicationTasks.length} total</span></div>
        <div className="task-list">{applicationTasks.length === 0 ? <div className="empty"><div className="empty-icon"><ClipboardList size={20}/></div><b>Your applications will appear here</b><span>Start by describing the public service you need help with.</span></div> : applicationTasks.map(task => <TaskRow key={task.task_id} task={task} selected={active?.task_id === task.task_id} onSelect={() => setActive(task)} />)}</div>
        {conversationTasks.length > 0 && <><div className="section-heading conversation-heading"><div><h3>Recent conversations</h3><p>Continue your casual chats with CivicFlow</p></div><span className="subtle-count">{conversationTasks.length} total</span></div><div className="task-list">{conversationTasks.map(task => <TaskRow key={task.task_id} task={task} selected={active?.task_id === task.task_id} onSelect={() => setActive(task)} conversation />)}</div></>}
        <section className="panel" id="profile"><div className="panel-title"><div className="panel-icon"><UserRound size={17}/></div><div><h3>Your profile</h3><p>Reusable details for your applications</p></div></div><div className="profile-edit"><textarea id="profile-data" value={profileText} onChange={e => setProfileText(e.target.value)} aria-label="Profile JSON"/><button className="secondary" onClick={saveProfile}>Save profile</button></div></section>
        <section className="panel" id="documents"><div className="panel-title"><div className="panel-icon"><FileText size={17}/></div><div><h3>Your documents</h3><p>Private files you may use when preparing applications</p></div><label className="secondary upload-button"><Upload size={14}/> Add document<input type="file" accept="application/pdf,image/jpeg,image/png" onChange={e => upload(e.target.files?.[0])}/></label></div><div className="doc-type-entry"><label htmlFor="doc-type">Document type (optional)</label><input id="doc-type" value={documentType} onChange={e => setDocumentType(e.target.value)} placeholder="e.g. Aadhaar card, marksheet"/></div>{documents.length ? <div className="document-list">{documents.map(doc => <div className="document-row" key={doc.document_id}><FileText size={16}/><span>{doc.filename}<small>{doc.document_type || doc.status}</small></span><Check size={15}/></div>)}</div> : <p className="empty-inline">No documents uploaded yet. PDF, PNG, or JPEG up to 15 MB.</p>}</section>
      </section>
      <aside className="right-column">{active ? <><section className="panel progress-panel"><div className="panel-title"><div className="panel-icon"><Globe2 size={17}/></div><div><h3>Application workspace</h3><p>Live progress and browser view</p></div></div><div className="active-status"><Status status={active.status}/><span>Updated just now</span></div>{active.summary && <div className="summary-box">{active.summary}</div>}{active.state?.browser_session_id && <><BrowserViewer taskId={active.task_id} token={token} onInput={async (value) => { try { await api(`/tasks/${active.task_id}/browser/input`, { method: 'POST', body: JSON.stringify(value) }) } catch (e) { setError((e as Error).message) } }}/><div className="browser-controls"><button className="secondary" onClick={() => api(`/tasks/${active.task_id}/browser/control`, { method: 'POST', body: JSON.stringify({ control_mode: 'user' }) })}>Take control</button><button className="secondary" onClick={() => api(`/tasks/${active.task_id}/browser/control`, { method: 'POST', body: JSON.stringify({ control_mode: 'agent' }) })}>Return control</button></div></>}</section>
        <section className="panel activity-panel"><div className="panel-title"><div className="panel-icon"><MessageSquareText size={17}/></div><div><h3>Activity</h3><p>What CivicFlow has done so far</p></div></div><div className="timeline">{events.length ? events.map((event, i) => <div className="timeline-item" key={event.event_id}><div className={`timeline-dot ${i === events.length - 1 ? 'current' : ''}`}>{i === events.length - 1 ? <LoaderCircle size={12}/> : <Check size={12}/>}</div><div><b>{event.type.replaceAll('.', ' ').replace(/\b\w/g, x => x.toUpperCase())}</b><small>{new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</small></div></div>) : <p className="empty-inline">Progress updates will appear here.</p>}</div>{active.state?.requirements?.sources?.length > 0 && <div className="sources"><h4>Official sources</h4>{active.state?.requirements?.sources?.map((source: any) => <a key={source.source_id} href={source.url} target="_blank" rel="noreferrer">{source.title}<ArrowUpRight size={12}/></a>)}</div>}</section>
        {['waiting_for_user','waiting_for_approval','paused'].includes(active.status) && <section className="panel resume-panel"><div className="panel-title"><div className="panel-icon"><MessageSquareText size={17}/></div><div><h3>{active.status === 'waiting_for_approval' ? 'Review and approve' : 'Your input is needed'}</h3><p>{active.state?.pending_prompt?.message || active.state?.pending_prompt?.question || 'Review the request and share the details below.'}</p></div></div>{active.state?.pending_prompt?.type === 'service.clarification_required' ? <>{active.state.pending_prompt.candidates.length ? <div className="candidate-list">{active.state.pending_prompt.candidates.map((candidate: any) => <button key={candidate.service_id} className="candidate" onClick={() => resumeTask({ service_id: candidate.service_id })}><b>{candidate.name}</b><small>{candidate.jurisdiction} · {candidate.department || candidate.category}</small></button>)}</div> : <><label className="answer-field">Service or portal<input value={clarificationService} onChange={e => setClarificationService(e.target.value)} placeholder="e.g. domicile certificate" /></label><label className="answer-field">Jurisdiction<input value={clarificationJurisdiction} onChange={e => setClarificationJurisdiction(e.target.value)} placeholder="e.g. Maharashtra" /></label><button className="primary full" onClick={() => resumeTask({ service_name: clarificationService, jurisdiction: clarificationJurisdiction })}>Continue clarification <ArrowUpRight size={16}/></button></>}</> : active.state?.pending_prompt?.type === 'approval.required' ? <div className="approval-actions"><button className="secondary" onClick={() => decideApproval(false)}>Decline</button><button className="primary" onClick={() => decideApproval(true)}>Approve and continue</button></div> : <>{(active.state?.pending_prompt?.items || []).filter((item: string) => !item.startsWith('document:')).map((item: string) => <label className="answer-field" key={item}>{item.replaceAll('_',' ')}<input value={answerValues[item] || ''} onChange={e => setAnswerValues({ ...answerValues, [item]: e.target.value })} /></label>)}{(active.state?.pending_prompt?.items || []).some((item: string) => item.startsWith('document:')) && <p className="empty-inline">Upload the requested document above, label its type, then continue.</p>}<button className="primary full" onClick={() => resumeTask()}>Continue task <ArrowUpRight size={16}/></button></>}</section>}
      </> : <><section className="tip-card"><div className="tip-icon"><ShieldCheck size={18}/></div><p className="eyebrow">A HELPFUL GUIDE</p><h3>You stay in control</h3><p>CivicFlow helps you understand and prepare. You review every important step, and final submission stays with you.</p><div className="tip-footer"><span>Built for clarity</span><ArrowDown size={15}/></div></section><section className="panel checklist"><div className="panel-title"><div className="panel-icon"><ClipboardList size={17}/></div><div><h3>How it works</h3><p>A clear path, at your pace</p></div></div>{[['01','Tell us what you need'],['02','Review official requirements'],['03','Prepare information and documents'],['04','You review before any action']].map(([n,label]) => <div className="check-row" key={n}><span>{n}</span><b>{label}</b></div>)}</section><div className="support-note"><ShieldCheck size={15}/> No application is submitted without your review.</div></>}</aside></div>
      {error && <button className="toast" onClick={() => setError('')}><X size={15}/>{error}</button>}
    </main>
  </div>
}

function Status({ status }: { status: string }) {
  const labels: Record<string, string> = { created: 'New', running: 'In progress', waiting_for_user: 'Needs your input', waiting_for_approval: 'Your review', paused: 'Paused', completed: 'Ready to review', failed: 'Stopped safely', cancelled: 'Cancelled' }
  return <span className={`status status-${status}`}><i/>{labels[status] || status.replaceAll('_', ' ')}</span>
}

function BrowserViewer({ taskId, token, onInput }: { taskId: string; token: string; onInput: (event: Record<string, any>) => void }) {
  const [image, setImage] = useState('')
  useEffect(() => {
    let objectUrl = ''
    let active = true
    const load = async () => {
      try {
        const response = await fetch(`${API}/api/v1/tasks/${taskId}/browser/screenshot`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' })
        if (!response.ok) return
        const next = URL.createObjectURL(await response.blob())
        if (active) { if (objectUrl) URL.revokeObjectURL(objectUrl); objectUrl = next; setImage(next) } else URL.revokeObjectURL(next)
      } catch { /* refresh again when the browser worker is available */ }
    }
    void load(); const timer = setInterval(load, 1500)
    return () => { active = false; clearInterval(timer); if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [taskId, token])
  return <div className="browser-frame" tabIndex={0} onClick={e => { const rect = e.currentTarget.getBoundingClientRect(); onInput({ event_id: crypto.randomUUID(), type: 'pointer_click', x_normalized: (e.clientX - rect.left) / rect.width, y_normalized: (e.clientY - rect.top) / rect.height }) }} onKeyDown={e => { if (e.key.length === 1 || ['Enter','Tab','Backspace'].includes(e.key)) { e.preventDefault(); onInput({ event_id: crypto.randomUUID(), type: 'key_press', key: e.key }) } }}>{image ? <img src={image} alt="Live service page"/> : <div className="empty-inline browser-empty">Browser screenshot will appear when a verified portal is available.</div>}<div className="browser-label"><span className="live-dot"/> Browser session · click and use keys</div></div>
}

export default App
