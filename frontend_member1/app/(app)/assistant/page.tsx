"use client"

import { FormEvent, useState } from "react"
import { Bot, Info, Send, Sparkles, ArrowRight } from "lucide-react"
import { useCivicFlow } from "@/lib/civicflow-store"
import { sendAssistantMessage } from "@/lib/civicflow-api"
import { Button, Card, PageHeader, Status } from "@/components/page-primitives"

export default function AssistantPage() {
  const { state, update } = useCivicFlow()
  const [text, setText] = useState("")
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState("")

  async function send(event: FormEvent) {
    event.preventDefault()
    const question = text.trim()
    if (!question || sending) return
    setSending(true)
    setSendError("")
    update({ chat: [...state.chat, { role: "user", text: question }] })
    setText("")
    try {
      const history = state.chat.slice(-20).map(({ role, text }) => ({ role, content: text }))
      const result = await sendAssistantMessage(question, state.conversationId, history)
      update({ chat: [...state.chat, { role: "user", text: question }, { role: "assistant", text: result.message }] })
    } catch (error) {
      const message = error instanceof Error ? error.message : "CivicFlow could not reach the assistant service."
      setSendError(message)
      update({ chat: [...state.chat, { role: "user", text: question }, { role: "assistant", text: "I couldn’t reach the assistant service just now. Please try again in a moment." }] })
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      <PageHeader
        title="CivicFlow Assistant"
        description="Guidance for finding public services, understanding eligibility, and navigating government portals."
        action={<Status tone="blue">Manual Guidance Mode</Status>}
      />

      <div className="mb-5 flex items-start gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
        <Info className="size-5 shrink-0 text-emerald-700" />
        <div>
          <strong className="font-semibold">CivicFlow assistant:</strong> Ask questions about public-service forms, schemes, eligibility, or casual topics. Passwords, OTPs, and CAPTCHA values must be entered directly on the service portal.
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <Card className="flex min-h-[540px] flex-col">
          <div className="flex items-center gap-3 border-b border-[#e9e1d5] pb-4">
            <div className="grid size-10 place-items-center rounded-full bg-[#08785e] text-white">
              <Bot className="size-5" />
            </div>
            <div>
              <p className="font-bold text-[#10272b]">CivicFlow Public Service Guide</p>
              <p className="text-xs text-[#60756f]">Public-service guidance · Nemotron via Ollama</p>
            </div>
          </div>

          <div className="flex flex-1 flex-col gap-4 overflow-auto py-5" aria-live="polite">
            {state.chat.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={`max-w-[85%] whitespace-pre-line rounded-2xl px-4 py-3 text-sm ${
                  message.role === "user"
                    ? "ml-auto bg-[#08785e] text-white"
                    : "bg-[#f7f5ee] text-[#10272b] border border-[#e9e1d5]"
                }`}
              >
                {message.text}
              </div>
            ))}
          </div>

          {sendError && <p role="alert" className="pt-2 text-xs text-red-700">{sendError}</p>}
          <form onSubmit={send} className="flex gap-2 border-t border-[#e9e1d5] pt-4">
            <label className="sr-only" htmlFor="assistant-message">
              Message
            </label>
            <input
              id="assistant-message"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Ask about a form, scheme, application, or just say hello..."
              className="min-w-0 flex-1 rounded-xl border border-[#d9cfc0] bg-white px-4 py-3 text-sm outline-none focus:border-[#08785e] focus:ring-2 focus:ring-[#e3f2e8]"
            />
            <button
              aria-label="Send message"
              disabled={sending}
              className="grid size-11 place-items-center rounded-xl bg-[#08785e] text-white hover:bg-[#065f4a] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#08785e] disabled:opacity-60"
            >
              <Send className="size-4" />
            </button>
          </form>
        </Card>

        <div className="space-y-4">
          <Card>
            <div className="flex items-center gap-2 font-bold text-[#10272b]">
              <Sparkles className="size-4 text-[#08785e]" /> Common Inquiries
            </div>
            <div className="mt-4 flex flex-col gap-2">
              {[
                "Income Certificate",
                "Caste Certificate in Bihar",
                "Driving Licence Renewal",
                "Post-Matric Scholarship",
                "Aadhaar Address Update",
              ].map((item) => (
                <Button key={item} variant="secondary" onClick={() => setText(item)}>
                  {item}
                </Button>
              ))}
            </div>
          </Card>

          <Card>
            <h3 className="font-bold text-sm text-[#10272b]">Need a Custom Service?</h3>
            <p className="mt-1 text-xs text-[#60756f]">
              If a service is not in our direct catalog, tell us the requirement and state to create a custom application.
            </p>
            <div className="mt-3">
              <Button href="/services/custom" variant="secondary" className="w-full justify-center">
                Custom Service Request <ArrowRight className="ml-1 size-3.5" />
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </>
  )
}
