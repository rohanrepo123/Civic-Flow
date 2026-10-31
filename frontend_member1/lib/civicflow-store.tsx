"use client"

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { serviceCatalog, type Service } from "@/src/data/serviceCatalog"

export type ApplicationStatus = "draft" | "prepared" | "validation_complete" | "waiting_for_approval" | "approved_for_submission" | "submission_in_progress" | "submitted" | "failed" | "uncertain"
export type DocumentStatus = "pending" | "verified"
export type ReviewState = Record<string, boolean>

export type DocumentItem = { id: string; name: string; type: string; status: DocumentStatus }
export type ActivityEvent = { id: string; label: string; timestamp: string; tone?: "blue" | "green" | "amber" }
export type Tracking = { referenceNumber?: string; submittedAt?: string; officialStatus?: string; demoMode: boolean }

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
  chat: { role: "user" | "assistant"; text: string }[]
  conversationId: string
  aiPaused: boolean
  userControl: boolean
}

type CivicFlowContext = {
  state: StoreState
  createApplication: (serviceId: string, options?: { scholarshipId?: string }) => Application | null
  createCustomApplication: (request: string, jurisdiction: string, district?: string, department?: string) => Application
  getApplication: (applicationId: string) => Application | null
  updateApplication: (applicationId: string, patch: Partial<Application>) => void
  deleteApplication: (applicationId: string) => void
  update: (patch: Partial<StoreState>) => void
}

const defaultForm = { applicantName: "Aarav Patil", fatherName: "Rajesh Patil", income: "₹2,00,000", dob: "12/03/2004", category: "OBC" }
const initialState: StoreState = {
  user: { id: "user-aarav-patil", name: "Aarav Patil", email: "aarav@example.com", phone: "+91 98765 43210", location: "Pune, Maharashtra" },
  applications: {}, documents: [], selectedApplicationId: null,
  chat: [{ role: "assistant", text: "Hello Aarav. I can help you discover services, check eligibility, and complete applications." }],
  conversationId: "assistant",
  aiPaused: false, userControl: false,
}

function serviceFor(serviceId: string): Service | undefined { return serviceCatalog.find((service) => service.id === serviceId) }
function now() { return new Date().toISOString() }
function createId() { return `app-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}` }
function createConversationId() { return `conversation-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}` }
function initialDocuments(service: Service): DocumentItem[] { return (service.documents ?? []).map((name, index) => ({ id: `${service.id}-doc-${index}`, name, type: "PDF / JPG", status: "pending" })) }

function sanitizePersistedState(value: unknown): StoreState {
  if (!value || typeof value !== "object") return initialState
  const candidate = value as Partial<StoreState>
  return {
    ...initialState,
    ...candidate,
    conversationId: typeof candidate.conversationId === "string" && candidate.conversationId ? candidate.conversationId : createConversationId(),
    applications: candidate.applications && typeof candidate.applications === "object" ? candidate.applications as Record<string, Application> : {},
    chat: Array.isArray(candidate.chat) ? candidate.chat : initialState.chat,
  }
}

const StoreContext = createContext<CivicFlowContext | null>(null)

export function CivicFlowProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<StoreState>(initialState)
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("civicflow-demo")
      if (saved) setState(sanitizePersistedState(JSON.parse(saved)))
    } catch {
      window.localStorage.removeItem("civicflow-demo")
    } finally {
      setState((current) => current.conversationId === "assistant" ? { ...current, conversationId: createConversationId() } : current)
      setHydrated(true)
    }
  }, [])

  useEffect(() => {
    if (!hydrated) return
    try { window.localStorage.setItem("civicflow-demo", JSON.stringify(state)) } catch { /* Storage can be unavailable in private browsing. */ }
  }, [state, hydrated])

  const value = useMemo<CivicFlowContext>(() => ({
    state,
    createApplication: (serviceId, options) => {
      const service = serviceFor(serviceId)
      if (!service) return null
      const timestamp = now()
      const id = createId()
      const application: Application = {
        id, serviceId, userId: state.user.id, status: "draft", currentStep: 0, progress: 0,
        formData: { ...defaultForm }, documents: initialDocuments(service),
        reviewState: Object.fromEntries(["personal", "education", "financial", "documents"].map((key) => [key, false])),
        approvalState: "not_started", tracking: { demoMode: true }, createdAt: timestamp, updatedAt: timestamp,
        selectedScholarship: options?.scholarshipId ?? null,
        activity: [{ id: `${id}-created`, label: service.status === "available" ? "Application draft created" : "CivicFlow workspace created; official application route needs verification", timestamp, tone: service.status === "available" ? "blue" : "amber" }],
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
    update: (patch) => setState((current) => ({ ...current, ...patch })),
  }), [state, hydrated])

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>
}
export function useCivicFlow() { const value = useContext(StoreContext); if (!value) throw new Error("useCivicFlow must be used inside CivicFlowProvider"); return value }
