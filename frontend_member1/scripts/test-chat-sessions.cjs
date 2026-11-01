const assert = require('node:assert/strict')
const fs = require('node:fs')
const ts = require('typescript')
const path = require('node:path')
const source = fs.readFileSync(path.join(__dirname, '../lib/chat-sessions.ts'), 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
const exported = {}
new Function('exports', compiled)(exported)
const append = exported.appendSessionMessages
const session = (id) => ({ id, title: 'New chat', messages: [], createdAt: '', updatedAt: '' })
let state = { conversationId: 'a', chat: [], chatSessions: { a: session('a'), b: session('b') } }
state = append(state, 'a', [{ role: 'user', text: 'MahaDBT eligibility' }])
state = { ...state, conversationId: 'b', chat: [] }
state = append(state, 'a', [{ role: 'assistant', text: 'Response belonging to A' }])
assert.equal(state.chat.length, 0)
assert.equal(state.chatSessions.a.messages.length, 2)
delete state.chatSessions.a
assert.equal(append(state, 'a', [{ role: 'assistant', text: 'Late reply' }]), state)
assert.equal(state.chatSessions.a, undefined)
console.log('PASS: switching and deleting chats isolates late responses')
