"use client"

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { serviceCatalog, type Service } from "@/src/data/serviceCatalog"
import { appendSessionMessages } from "@/lib/chat-sessions"
import { createCoreApplication } from "@/lib/civicflow-api"

export type ApplicationStatus = "draft" | "prepared" | "validation_complete" | "waiting_for_approval" | "approved_for_submission" | "submission_in_progress" | "submitted" | "failed" | "uncertain"
export type DocumentStatus = "pending" | "verified"
export type ReviewState = Record<string, boolean>

export type DocumentItem = { id: string; name: string; type: string; status: DocumentStatus }
export type ActivityEvent = { id: string; label: string; timestamp: string; tone?: "blue" | "green" | "amber" }
export type Tracking = { referenceNumber?: string; submittedAt?: string; officialStatus?: string; demoMode: boolean }
export type ChatMessage = { role: "user" | "assistant"; text: string }
export type ChatSession = {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: string
  updatedAt: string
}

export interface Application {
  id: string
  serviceId: string
  userId: string
  status: ApplicationStatus
  currentStep: number
  progress: number
  formData: { applicantName: string; fatherName: string; income: string; dob: string; category: string }
  documents: DocumentItem[]
  reviewState: ReviewState
  approvalState: "not_started" | "approved" | "declined"
  tracking: Tracking
  createdAt: string
  updatedAt: string
  activity: ActivityEvent[]
  selectedScholarship?: string | null
  applicationMode?: "catalog" | "custom"
  customRequest?: string
  customState?: string
  customDistrict?: string
  customDepartment?: string
}

type StoreState = {
  user: { id: string; name: string; email: string; phone: string; location: string }
  applications: Record<string, Application>
  documents: DocumentItem[]
  selectedApplicationId: string | null
  chat: ChatMessage[]
  conversationId: string
  chatSessions: Record<string, ChatSession>
  aiPaused: boolean
  userControl: boolean
}

type CivicFlowContext = {
  state: StoreState
  chatReady: boolean
  createApplication: (serviceId: string, options?: { scholarshipId?: string }) => Promise<Application | null>
  createCustomApplication: (request: string, jurisdiction: string, district?: string, department?: string) => Application
  getApplication: (applicationId: string) => Application | null
  updateApplication: (applicationId: string, patch: Partial<Application>) => void
  deleteApplication: (applicationId: string) => void
  appendChat: (conversationId: string, messages: ChatMessage[]) => void
  startNewChat: () => void
  openChat: (conversationId: string) => void
  deleteChat: (conversationId: string) => void
  update: (patch: Partial<StoreState>) => void
}

const defaultForm = { applicantName: "Aarav Patil", fatherName: "Rajesh Patil", income: "₹2,00,000", dob: "12/03/2004", category: "OBC" }
const welcomeMessage: ChatMessage = { role: "assistant", text: "Hello Aarav. I can help you discover services, check eligibility, and complete applications." }
const initialConversationId = "conversation-welcome"
const chatStorageKey = "civicflow-chat:local"
const initialChatSession: ChatSession = {
  id: initialConversationId,
  title: "New chat",
  messages: [welcomeMessage],
  createdAt: "2026-01-01T00:00:00.000Z",
  updatedAt: "2026-01-01T00:00:00.000Z",
}
const initialState: StoreState = {
  user: { id: "user-aarav-patil", name: "Aarav Patil", email: "aarav@example.com", phone: "+91 98765 43210", location: "Pune, Maharashtra" },
  applications: {}, documents: [], selectedApplicationId: null,
  chat: initialChatSession.messages,
  conversationId: initialConversationId,
  chatSessions: { [initialConversationId]: initialChatSession },
  aiPaused: false, userControl: false,
}

function serviceFor(serviceId: string): Service | undefined { return serviceCatalog.find((service) => service.id === serviceId) }
function now() { return new Date().toISOString() }
function createId() { return `app-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}` }
function createConversationId() { return `conversation-${crypto.randomUUID()}` }
function initialDocuments(service: Service): DocumentItem[] { return (service.documents ?? []).map((name, index) => ({ id: `${service.id}-doc-${index}`, name, type: "PDF / JPG", status: "pending" })) }
function chatTitle(messages: ChatMessage[]): string {
  const firstUserMessage = messages.find((message) => message.role === "user")?.text.trim()
  if (!firstUserMessage) return "New chat"
  return firstUserMessage.length > 34 ? `${firstUserMessage.slice(0, 34)}…` : firstUserMessage
}
function makeChatSession(id: string, messages: ChatMessage[], timestamp = now()): ChatSession {
  return { id, title: chatTitle(messages), messages, createdAt: timestamp, updatedAt: timestamp }
}

function sanitizePersistedState(value: unknown): StoreState {
  if (!value || typeof value !== "object") return initialState
  const candidate = value as Partial<StoreState>
  const legacyChat = Array.isArray(candidate.chat) ? candidate.chat : []
  const savedSessions = candidate.chatSessions && typeof candidate.chatSessions === "object"
    ? candidate.chatSessions as Record<string, ChatSession>
    : {}
  const chatSessions = Object.fromEntries(
    Object.entries(savedSessions).filter(([, session]) => session && typeof session === "object" && Array.isArray(session.messages))
  ) as Record<string, ChatSession>
  const fallbackId = typeof candidate.conversationId === "string" && candidate.conversationId
    ? candidate.conversationId
    : createConversationId()
  if (!Object.keys(chatSessions).length) {
    const messages = legacyChat.length ? legacyChat : initialState.chat
    chatSessions[fallbackId] = makeChatSession(fallbackId, messages)
  }
  const conversationId = chatSessions[fallbackId] ? fallbackId : Object.keys(chatSessions)[0]
  return {
    ...initialState,
    ...candidate,
    conversationId,
    chatSessions,
    applications: candidate.applications && typeof candidate.applications === "object" ? candidate.applications as Record<string, Application> : {},
    chat: chatSessions[conversationId].messages,
  }
}

const StoreContext = createContext<CivicFlowContext | null>(null)

export function CivicFlowProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<StoreState>(initialState)
  const [hydrated, setHydrated] = useState(false)
  const [storageKey, setStorageKey] = useState("")

  useEffect(() => {
    let restored = { ...initialState, chatSessions: {} } as StoreState
    try {
      const saved = window.localStorage.getItem(chatStorageKey)
      if (saved) restored = sanitizePersistedState(JSON.parse(saved))
    } catch { /* A corrupt record must not stop a new conversation. */ }
    const id = createConversationId()
    const session = makeChatSession(id, [welcomeMessage])
    const hydratedState = { ...restored, conversationId: id, chat: session.messages,
      chatSessions: { ...restored.chatSessions, [id]: session } }
    setStorageKey(chatStorageKey)
    setState(hydratedState)
    setHydrated(true)
  }, [])

  useEffect(() => {
    if (!hydrated) return
    try { window.localStorage.setItem(storageKey, JSON.stringify(state)) } catch { /* Storage can be unavailable in private browsing. */ }
  }, [state, hydrated, storageKey])

  const value = useMemo<CivicFlowContext>(() => ({
    state,
    chatReady: hydrated,
    createApplication: async (serviceId, options) => {
      const service = serviceFor(serviceId)
      if (!service) return null
      const remote = await createCoreApplication(serviceId, { ...defaultForm })
      const timestamp = now()
      const id = remote.id
      const application: Application = {
        id, serviceId, userId: remote.user_id, status: remote.status as ApplicationStatus, currentStep: remote.current_step, progress: remote.progress,
        formData: { ...defaultForm }, documents: remote.documents.map((item) => ({ id: item.document_id, name: item.name, type: item.file_type, status: item.status === "verified" ? "verified" : "pending" })),
        reviewState: remote.review_state,
        approvalState: "not_started", tracking: { demoMode: remote.tracking.demo_mode }, createdAt: remote.created_at, updatedAt: remote.updated_at,
        selectedScholarship: options?.scholarshipId ?? null,
        activity: [{ id: `${id}-created`, label: "Application draft created", timestamp: remote.created_at, tone: "blue" }],
      }
      setState((current) => ({ ...current, applications: { ...current.applications, [id]: application }, selectedApplicationId: id }))
      return application
    },
    createCustomApplication: (request, jurisdiction, district, department) => {
      const timestamp = now()
      const id = createId()
      const application: Application = {
        id, serviceId: "custom-request", userId: state.user.id, status: "draft", currentStep: 0, progress: 0,
        formData: { applicantName: "", fatherName: "", income: "", dob: "", category: "" }, documents: [],
        reviewState: { service: false, details: false, documents: false }, approvalState: "not_started",
        tracking: { demoMode: true }, createdAt: timestamp, updatedAt: timestamp,
        applicationMode: "custom", customRequest: request.trim(), customState: jurisdiction.trim(), customDistrict: district?.trim(), customDepartment: department?.trim(),
        activity: [{ id: `${id}-created`, label: "Custom service request created — source verification needed", timestamp, tone: "amber" }],
      }
      setState((current) => ({ ...current, applications: { ...current.applications, [id]: application }, selectedApplicationId: id }))
      return application
    },
    getApplication: (applicationId) => state.applications[applicationId] ?? null,
    updateApplication: (applicationId, patch) => setState((current) => {
      const existing = current.applications[applicationId]
      if (!existing) return current
      const updated = { ...existing, ...patch, updatedAt: now() }
      return { ...current, applications: { ...current.applications, [applicationId]: updated }, selectedApplicationId: applicationId }
    }),
    deleteApplication: (applicationId) => setState((current) => { const { [applicationId]: _, ...rest } = current.applications; return { ...current, applications: rest, selectedApplicationId: current.selectedApplicationId === applicationId ? null : current.selectedApplicationId } }),
    appendChat: (conversationId, messages) => setState((current) => appendSessionMessages(current, conversationId, messages)),
    startNewChat: () => setState((current) => {
      const id = createConversationId()
      const session = makeChatSession(id, [welcomeMessage])
      return { ...current, conversationId: id, chat: session.messages, chatSessions: { ...current.chatSessions, [id]: session } }
    }),
    openChat: (conversationId) => setState((current) => {
      const session = current.chatSessions[conversationId]
      return session ? { ...current, conversationId, chat: session.messages } : current
    }),
    deleteChat: (conversationId) => setState((current) => {
      const sessions = { ...current.chatSessions }
      delete sessions[conversationId]
      const remaining = Object.keys(sessions)
      if (!remaining.length) {
        const id = createConversationId()
        sessions[id] = makeChatSession(id, [welcomeMessage])
        return { ...current, conversationId: id, chat: sessions[id].messages, chatSessions: sessions }
      }
      if (conversationId !== current.conversationId) return { ...current, chatSessions: sessions }
      const nextId = remaining[0]
      return { ...current, conversationId: nextId, chat: sessions[nextId].messages, chatSessions: sessions }
    }),
    update: (patch) => setState((current) => {
      if (!patch.chat) return { ...current, ...patch }
      const timestamp = now()
      const session = current.chatSessions[current.conversationId] ?? makeChatSession(current.conversationId, [])
      const chatSessions = { ...current.chatSessions, [current.conversationId]: { ...session, title: chatTitle(patch.chat), messages: patch.chat, updatedAt: timestamp } }
      return { ...current, ...patch, chatSessions }
    }),
  }), [state, hydrated])

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>
}
export function useCivicFlow() { const value = useContext(StoreContext); if (!value) throw new Error("useCivicFlow must be used inside CivicFlowProvider"); return value }
