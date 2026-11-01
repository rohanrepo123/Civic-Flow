"use client";

const baseUrl = "/api/core";

export const isCoreApiConfigured = true;

export interface GeoState {
  state_code: string;
  name: string;
  jurisdiction_type: string;
  primary_portal_name: string;
  primary_portal_url: string;
  verification_status: string;
}

export interface ServiceItem {
  id: string;
  title: string;
  category: string;
  description: string;
  jurisdiction?: string;
  department?: string;
  status: string;
  integration_mode: string;
  application_mode: string;
  aliases: string[];
  official_url?: string;
  workflow_steps?: string[];
  eligibility_criteria?: string[];
  required_documents?: string[];
}

export interface CategoryInfo {
  key: string;
  label: string;
  description: string;
  service_count: number;
}

export interface CustomApplicationInput {
  request_text: string;
  jurisdiction?: string;
  state_code?: string;
  district?: string;
  department_id?: string;
  portal_url?: string;
  additional_context?: Record<string, unknown>;
}

export interface ApplicationDetail {
  id: string;
  service_id: string;
  user_id: string;
  status: string;
  current_step: number;
  progress: number;
  form_data: Record<string, unknown>;
  documents: Array<{ document_id: string; name: string; file_type: string; status: string }>;
  review_state: Record<string, boolean>;
  approval_state: string;
  tracking: { demo_mode: boolean; reference_number?: string; last_checked?: string };
  created_at: string;
  updated_at: string;
  portal_url?: string;
  allowed_domains?: string[];
  custom_request?: string;
  custom_state?: string;
  custom_district?: string;
  application_mode?: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${baseUrl}${path}`;
  const response = await fetch(url, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(`Core API request failed (${response.status}): ${errorText || response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function getChatIdentity() {
  return request<{ scope: string }>("/api/v1/assistant/session");
}

export interface AssistantTurnResult {
  message: string;
  run_id: string;
  mode: string;
  intent: string;
  source_citations: Array<{ title: string; url: string; excerpt?: string }>;
  proposed_next_action?: { action_type: string; parameters: Record<string, unknown> } | null;
  missing_information?: string[];
}

export function sendAssistantMessage(
  message: string,
  conversationId: string,
  history: Array<{ role: "user" | "assistant"; content: string }>,
) {
  return request<AssistantTurnResult>("/api/v1/assistant/messages", {
    method: "POST",
    body: JSON.stringify({ message, conversation_id: conversationId, history }),
  });
}

// --- Geographic Endpoints ---
export function getGeoStates(): Promise<GeoState[]> {
  return request<GeoState[]>("/api/v1/geo/states");
}

export function getGeoDistricts(stateCode: string): Promise<string[]> {
  return request<string[]>(`/api/v1/geo/states/${encodeURIComponent(stateCode)}/districts`);
}

// --- Service Catalog Endpoints ---
export function listCoreServices(params: Record<string, string | undefined> = {}): Promise<ServiceItem[]> {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, value]) => Boolean(value)) as string[][]
  );
  return request<ServiceItem[]>(`/api/v1/services${query.size ? `?${query}` : ""}`);
}

export function getCoreService(serviceId: string): Promise<ServiceItem> {
  return request<ServiceItem>(`/api/v1/services/${encodeURIComponent(serviceId)}`);
}

export function getCoreCategories(): Promise<CategoryInfo[]> {
  return request<CategoryInfo[]>("/api/v1/services/categories");
}

// --- Applications Endpoints ---
export function createCoreApplication(serviceId: string, formData: Record<string, unknown> = {}): Promise<ApplicationDetail> {
  return request<ApplicationDetail>("/api/v1/applications", {
    method: "POST",
    body: JSON.stringify({ service_id: serviceId, form_data: formData }),
  });
}

export function createCoreCustomApplication(input: CustomApplicationInput): Promise<{ application_id: string; status: string; message: string }> {
  return request<{ application_id: string; status: string; message: string }>("/api/v1/applications/custom", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function loadCoreApplication(applicationId: string): Promise<ApplicationDetail> {
  return request<ApplicationDetail>(`/api/v1/applications/${encodeURIComponent(applicationId)}`);
}

export function listCoreApplications(): Promise<Array<{ id: string; service_id: string; status: string; progress: number; created_at: string; updated_at: string }>> {
  return request("/api/v1/applications");
}

export function updateCoreApplication(applicationId: string, patch: Record<string, unknown>): Promise<ApplicationDetail> {
  return request<ApplicationDetail>(`/api/v1/applications/${encodeURIComponent(applicationId)}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function getCoreApplicationPortal(applicationId: string): Promise<{ application_id: string; portal_url: string; allowed_domains: string[] }> {
  return request<{ application_id: string; portal_url: string; allowed_domains: string[] }>(`/api/v1/applications/${encodeURIComponent(applicationId)}/portal`);
}

export function getCoreApplicationActivity(applicationId: string): Promise<Array<{ id: string; label: string; timestamp: string; tone: string }>> {
  return request(`/api/v1/applications/${encodeURIComponent(applicationId)}/activity`);
}

// --- Browser Agent Endpoints ---
export function browserAgentReady(): Promise<{ status: string; mode: string }> {
  return request<{ status: string; mode: string }>("/api/v1/browser/health");
}

export function createBrowserSession(input: { applicationId: string; serviceId: string; portalUrl: string; allowedDomains: string[] }): Promise<{ browser_session_id: string; session_status: string; stream_endpoint?: string; stream_url?: string; stream_token?: string }> {
  return request(`/api/v1/applications/${encodeURIComponent(input.applicationId)}/browser-sessions`, {
    method: "POST",
    body: JSON.stringify({ service_id: input.serviceId, form_data: {} }),
  });
}

export function getBrowserStreamToken(sessionId: string): Promise<{ stream_token: string; stream_endpoint: string }> {
  return request(`/api/v1/browser-sessions/${encodeURIComponent(sessionId)}/stream-token`);
}

export function sendBrowserCommand(sessionId: string, command: { command_type: "navigate" | "inspect" | "fill"; element_id?: string; value?: string; target_url?: string }): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/api/v1/browser-sessions/${encodeURIComponent(sessionId)}/commands`, {
    method: "POST",
    body: JSON.stringify(command),
  });
}

export function setBrowserControl(sessionId: string, action: "pause" | "resume" | "take-control" | "return-control" | "close"): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/api/v1/browser-sessions/${encodeURIComponent(sessionId)}/${action}`, {
    method: "POST",
  });
}
