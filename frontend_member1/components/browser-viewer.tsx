"use client"

import { useEffect, useRef, useState } from "react"
import {
  Circle,
  Expand,
  ExternalLink,
  FileCheck2,
  LoaderCircle,
  Pause,
  Play,
  ShieldCheck,
  UserRound,
  Send,
  Link2,
  MonitorPlay,
  Globe,
} from "lucide-react"
import { Button, Card, Status } from "@/components/page-primitives"
import { useCivicFlow, type ActivityEvent } from "@/lib/civicflow-store"
import {
  browserAgentReady,
  createBrowserSession,
  sendBrowserCommand,
  setBrowserControl,
} from "@/lib/civicflow-api"

export function BrowserViewer({
  applicationId,
  serviceId,
  portalUrl,
  activities = [],
}: {
  applicationId: string
  serviceId: string
  portalUrl?: string
  activities?: ActivityEvent[]
}) {
  const { state, update } = useCivicFlow()
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>()
  const [streamEndpoint, setStreamEndpoint] = useState<string>()
  const [frame, setFrame] = useState<string>()
  const [fields, setFields] = useState<Array<{ label: string; type: string; required: boolean }>>([])
  const [instruction, setInstruction] = useState("")
  const [value, setValue] = useState("")
  const [message, setMessage] = useState("")
  const [taken, setTaken] = useState(false)
  const [viewMode, setViewMode] = useState<"stream" | "interactive">("stream")
  const connectingRef = useRef(false)
  const paused = state.aiPaused

  const connect = async () => {
    if (connectingRef.current) return
    if (!portalUrl) {
      setMessage("This service does not have an approved portal URL yet.")
      return
    }
    connectingRef.current = true
    try {
      setLoading(true)
      const host = new URL(portalUrl).hostname
      const session = await createBrowserSession({ applicationId, serviceId, portalUrl, allowedDomains: [host] })
      setSessionId(session.browser_session_id)
      if (!session.stream_url) throw new Error("Core API did not return the live browser stream address. Restart the local services and try again.")
      setStreamEndpoint(session.stream_url)
      const connected = await browserAgentReady()
      setMessage(
        connected.mode === "playwright"
          ? "Live portal opened in a Chromium window on this computer. Inspect it here, or take manual control to use the Chromium window directly."
          : "Simulated browser session connected. This view does not open a live government portal."
      )
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not connect to Browser Agent")
    } finally {
      connectingRef.current = false
      setLoading(false)
    }
  }

  // Auto-connect on mount if portalUrl is available
  useEffect(() => {
    if (portalUrl && !sessionId && !loading) {
      connect()
    }
  }, [portalUrl])

  useEffect(() => {
    if (!streamEndpoint) return
    let disposed = false
    const socket = new WebSocket(streamEndpoint)
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (payload.event_type === "frame") {
          setFrame(`data:${payload.mime_type};base64,${payload.data}`)
        } else if (payload.event_type === "stream_unavailable") {
          setMessage(payload.message)
          setSessionId(undefined)
          setStreamEndpoint(undefined)
          setFrame(undefined)
        }
      } catch {}
    }
    socket.onerror = () => setMessage("Live browser preview disconnected.")
    socket.onclose = () => {
      if (!disposed) {
        setSessionId(undefined)
        setStreamEndpoint(undefined)
        setFrame(undefined)
        setMessage("Browser preview disconnected. Connect a new live session to continue.")
      }
    }
    return () => {
      disposed = true
      socket.close()
    }
  }, [streamEndpoint])

  const refresh = () => sessionId ? void inspect() : setMessage("Connect the browser before refreshing its view.")

  const inspect = async () => {
    if (!sessionId) return
    try {
      setLoading(true)
      const response = await sendBrowserCommand(sessionId, { command_type: "inspect" })
      const snap = response.snapshot as
        | { interactive_elements?: Array<{ label?: string; name?: string; aria_label?: string; element_type?: string; required?: boolean }> }
        | undefined
      setFields(
        (snap?.interactive_elements ?? []).map((f) => ({
          label: f.label || f.aria_label || f.name || "Unlabelled control",
          type: f.element_type || "unknown",
          required: Boolean(f.required),
        }))
      )
      setMessage("Page inspected. Select or enter a field name and provide its value.")
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Page inspection failed")
    } finally {
      setLoading(false)
    }
  }

  const fill = async () => {
    if (!sessionId || !instruction.trim() || !value) {
      setMessage("Connect a browser session and provide a field plus value.")
      return
    }
    try {
      setLoading(true)
      const result = await sendBrowserCommand(sessionId, { command_type: "fill", element_id: instruction.trim(), value })
      const nested = result.result as { success?: boolean; message?: string } | undefined
      setMessage(nested?.message ?? (result.status === "completed" ? "The browser worker accepted the fill request." : "The field needs clarification."))
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Field fill failed")
    } finally {
      setLoading(false)
    }
  }

  const handoff = async () => {
    if (!sessionId) return
    try {
      await setBrowserControl(sessionId, taken ? "return-control" : "take-control")
      setTaken(!taken)
      update({ userControl: !taken })
      setMessage(taken ? "Control returned to CivicFlow Browser Agent." : "Manual control is active. Use the visible CivicFlow Chromium window to interact with the portal.")
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Control change failed")
    }
  }

  const togglePause = async () => {
    if (!sessionId) {
      setMessage("Connect a browser session before pausing browser assistance.")
      return
    }
    try {
      await setBrowserControl(sessionId, paused ? "resume" : "pause")
      update({ aiPaused: !paused })
      setMessage(paused ? "Browser assistance resumed." : "Browser assistance paused.")
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not change browser assistance state.")
    }
  }

  const stopSession = async () => {
    if (!sessionId) return
    try {
      await setBrowserControl(sessionId, "close")
      setSessionId(undefined)
      setStreamEndpoint(undefined)
      setFrame(undefined)
      setMessage("Browser session closed.")
    } catch {
      setMessage("Failed to close session.")
    }
  }

  const shown = activities.length
    ? activities
    : [{ id: "demo", label: "Browser Agent session initialised", timestamp: "Active workspace", tone: "green" as const }]

  return (
    <div className="cf-browser-layout">
      {/* Left: Journey Steps */}
      <Card className="cf-browser-context">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-[#10272b]">Application steps</h2>
          <Status tone={sessionId ? "green" : "amber"}>{sessionId ? "Connected" : "Starting"}</Status>
        </div>
        <p className="mt-1 text-xs text-[#60756f]">{applicationId}</p>
        <div className="mt-5 flex flex-col gap-4">
          {["Prepare details", "Open official portal", "Review application", "Track progress"].map((step, index) => (
            <div className="flex items-center gap-3 text-sm" key={step}>
              {index <= 1 ? (
                <FileCheck2 size={19} className="text-[#08785e]" />
              ) : (
                <Circle size={18} className="text-slate-300" />
              )}
              <span className={index <= 1 ? "font-semibold text-[#08785e]" : "text-slate-600"}>{step}</span>
            </div>
          ))}
        </div>
        <div
          className={`mt-6 rounded-xl p-3 text-xs leading-5 ${
            sessionId
              ? "bg-[#e6f4ea] text-[#137333] border border-[#ceead6]"
              : "bg-[#fff6e7] text-[#72521e] border border-[#eadfcf]"
          }`}
        >
          {sessionId
            ? "✓ Browser session active. Check the mode label before using this simulated or Playwright session."
            : "Connecting to the configured portal session..."}
        </div>
      </Card>

      {/* Center: Live Viewport */}
      <Card className="cf-browser-viewport">
        {/* Navigation / Control Bar */}
        <div className="flex flex-wrap items-center gap-2 rounded-xl bg-[#f7f4ec] p-2">
          <Button variant="ghost" className="px-2 py-1" onClick={refresh} aria-label="Refresh browser">
            <LoaderCircle className={loading ? "size-4 animate-spin text-[#08785e]" : "size-4"} />
          </Button>

          {/* URL / Status Pill */}
          <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-[#e9e1d5] bg-white px-3 py-1.5 text-xs text-[#60756f]">
            <ShieldCheck size={14} className="shrink-0 text-[#08785e]" />
            <span className="truncate font-medium text-[#183b34]">
              {portalUrl ?? "No approved portal URL"}
            </span>
          </div>

          {/* View Mode Toggle */}
          <div className="flex items-center gap-1 rounded-lg bg-[#e8e2d4] p-1 text-xs">
            <button
              type="button"
              onClick={() => setViewMode("stream")}
              className={`flex items-center gap-1 rounded-md px-2.5 py-1 font-semibold transition-colors ${
                viewMode === "stream"
                  ? "bg-white text-[#08785e] shadow-xs"
                  : "text-[#60756f] hover:text-[#10272b]"
              }`}
            >
              <MonitorPlay size={13} />
              Stream
            </button>
            <button
              type="button"
              onClick={() => setViewMode("interactive")}
              className={`flex items-center gap-1 rounded-md px-2.5 py-1 font-semibold transition-colors ${
                viewMode === "interactive"
                  ? "bg-white text-[#08785e] shadow-xs"
                  : "text-[#60756f] hover:text-[#10272b]"
              }`}
            >
              <Globe size={13} />
                Official site
            </button>
          </div>

          {portalUrl && (
            <a
              href={portalUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center rounded-lg border border-[#e9e1d5] bg-white p-2 text-[#60756f] hover:text-[#08785e]"
              title="Open portal in new tab"
            >
              <ExternalLink size={14} />
            </a>
          )}
        </div>

        {/* View Content */}
        {viewMode === "interactive" && portalUrl ? (
          <div className="mt-3 flex min-h-64 flex-col items-center justify-center gap-4 rounded-xl border border-[#e9e1d5] bg-white p-6 text-center">
            <Globe className="size-8 text-[#08785e]" />
            <p className="max-w-lg text-sm leading-6 text-[#60756f]">Open the official portal in a separate tab. This tab is separate from the controlled Chromium session; use the live browser view and its manual-control button to work in the CivicFlow session.</p>
            <a href={portalUrl} target="_blank" rel="noreferrer" className="rounded-lg bg-[#08785e] px-4 py-2.5 text-sm font-semibold text-white">Open official portal</a>
          </div>
        ) : frame ? (
          <div className="mt-3 overflow-hidden rounded-xl border border-[#e9e1d5] bg-white shadow-xs">
            <img
              src={frame}
              alt="Live Browser Agent portal view"
              className="block h-auto max-h-[680px] w-full object-contain"
            />
          </div>
        ) : (
          <div className="cf-browser-placeholder py-12">
            <span className="grid size-14 place-items-center rounded-2xl bg-[#e3f2e8] text-[#08785e]">
              <LoaderCircle size={28} className="animate-spin text-[#08785e]" />
            </span>
            <Status tone={sessionId ? "green" : "amber"}>
              {sessionId ? "Browser Stream Connecting" : "Connecting Browser Session"}
            </Status>
            <h2 className="mt-2 text-base font-bold text-[#10272b]">
              Connecting to configured portal
            </h2>
            <p className="max-w-md text-xs leading-5 text-[#60756f]">
              {portalUrl
                ? `Opening a live Chromium session to ${portalUrl}. A visible browser window will open on this computer.`
                : "No portal URL assigned to this service."}
            </p>
            {!sessionId && (
              <Button
                variant="secondary"
                onClick={connect}
                disabled={!portalUrl || loading}
                className="mt-3"
              >
                <Link2 size={16} className="mr-2" />
                Connect Browser Agent
              </Button>
            )}
          </div>
        )}

        {/* Command & Form Filling Controls */}
        {sessionId && (
          <div className="mt-3 grid gap-3 rounded-xl border border-[#e9e1d5] bg-[#faf8f2] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={inspect} disabled={loading || taken}>
                  Inspect page elements
                </Button>
                <Button variant="secondary" onClick={handoff}>
                  {taken ? "Return control to AI" : "Take manual control"}
                </Button>
              </div>
              <span className="text-xs font-medium text-[#60756f]">
                {taken ? "⚠️ Citizen takeover active" : "🤖 Browser Agent guard active"}
              </span>
            </div>

            {fields.length > 0 && (
              <div className="grid max-h-48 gap-2 overflow-y-auto rounded-xl bg-white p-3 border border-[#e2d8c9]">
                <strong className="text-xs font-bold text-[#10272b]">
                  Detected form fields ({fields.length}):
                </strong>
                <div className="flex flex-wrap gap-1.5">
                  {fields.map((field, index) => (
                    <button
                      key={`${field.label}-${index}`}
                      type="button"
                      onClick={() => setInstruction(field.label)}
                      className="rounded-md border border-[#e2d8c9] bg-[#f8fafc] px-2 py-1 text-left text-xs hover:border-[#08785e] hover:bg-[#eef8f3]"
                    >
                      <span className="font-semibold text-[#183b34]">{field.label}</span>
                      <span className="text-[10px] text-[#808d87]"> · {field.type}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="grid gap-2 sm:grid-cols-2">
              <label className="text-xs font-semibold text-[#60756f]">
                Field description or target
                <input
                  value={instruction}
                  onChange={(e) => setInstruction(e.target.value)}
                  placeholder="e.g. Applicant full name"
                  className="mt-1 w-full rounded-lg border border-[#d9cfc0] bg-white px-3 py-2 text-sm text-[#10272b] outline-hidden focus:border-[#08785e]"
                />
              </label>
              <label className="text-xs font-semibold text-[#60756f]">
                Citizen value to populate
                <input
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  placeholder="Enter a non-sensitive value"
                  className="mt-1 w-full rounded-lg border border-[#d9cfc0] bg-white px-3 py-2 text-sm text-[#10272b] outline-hidden focus:border-[#08785e]"
                />
              </label>
            </div>

            <Button onClick={fill} disabled={loading || taken || !instruction || !value}>
              Fill field <Send size={15} className="ml-2" />
            </Button>
          </div>
        )}

        {message && (
          <p role="status" className="mt-2 text-xs font-medium text-[#08785e]">
            {message}
          </p>
        )}
      </Card>

      {/* Right: AI Companion & Control */}
      <Card className="cf-browser-ai">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-bold text-[#10272b]">AI Companion</h2>
            <p className="mt-1 text-xs text-[#60756f]">Advisory assistance</p>
          </div>
          <Status tone={paused ? "amber" : "blue"}>{paused ? "Paused" : "Active"}</Status>
        </div>

        <div className="mt-5 flex flex-col gap-4">
          {shown.slice(-4).map((event) => (
            <div key={event.id} className="flex gap-2.5 text-sm">
              <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-[#e5f2e8] text-xs font-bold text-[#08785e]">
                i
              </span>
              <div>
                <p className="font-medium text-[#183632]">{event.label}</p>
                <p className="mt-1 text-xs text-[#87938e]">{event.timestamp}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 flex flex-col gap-2">
          <Button variant="secondary" onClick={togglePause} disabled={!sessionId}>
            {paused ? <Play size={15} className="mr-2" /> : <Pause size={15} className="mr-2" />}
            {paused ? "Resume browser assistance" : "Pause browser assistance"}
          </Button>
          <Button variant="secondary" onClick={handoff} disabled={!sessionId}>
            <UserRound size={15} className="mr-2" />
            {state.userControl ? "Return control" : "Take manual control"}
          </Button>
          <Button variant="secondary" onClick={stopSession} disabled={!sessionId}>
            Stop session
          </Button>
        </div>

        <p className="mt-3 text-[11px] leading-4 text-[#85938e]">
          {sessionId
            ? "Browser session connected. Check its mode before entering any information."
            : "AI Companion ready to assist during form filling."}
        </p>
      </Card>
    </div>
  )
}
