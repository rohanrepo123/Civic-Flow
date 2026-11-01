import type { ChatMessage, ChatSession } from "./civicflow-store"

type ChatState = {
  conversationId: string
  chat: ChatMessage[]
  chatSessions: Record<string, ChatSession>
}

export function appendSessionMessages<T extends ChatState>(state: T, conversationId: string, messages: ChatMessage[]): T {
  const session = state.chatSessions[conversationId]
  if (!session) return state
  const combined = [...session.messages, ...messages]
  const title = combined.find((message) => message.role === "user")?.text.trim() || "New chat"
  return {
    ...state,
    chat: state.conversationId === conversationId ? combined : state.chat,
    chatSessions: { ...state.chatSessions, [conversationId]: {
      ...session, title: title.length > 34 ? `${title.slice(0, 34)}…` : title,
      messages: combined, updatedAt: new Date().toISOString(),
    } },
  }
}
