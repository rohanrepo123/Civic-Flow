"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { ArrowRight, FileText, LoaderCircle } from "lucide-react"
import { useCivicFlow } from "@/lib/civicflow-store"
import { serviceCatalog } from "@/src/data/serviceCatalog"
import { BrowserViewer } from "@/components/browser-viewer"
import { Button, Card, PageHeader, Status } from "@/components/page-primitives"
import { loadCoreApplication, type ApplicationDetail } from "@/lib/civicflow-api"

export default function WorkspacePage() {
  const params = useParams<{ id: string }>()
  const { getApplication, updateApplication } = useCivicFlow()
  const localApp = getApplication(params.id)

  const [remoteApp, setRemoteApp] = useState<ApplicationDetail | null>(null)
  const [loading, setLoading] = useState(!localApp)

  useEffect(() => {
    if (!localApp && params.id) {
      setLoading(true)
      loadCoreApplication(params.id)
        .then((data) => setRemoteApp(data))
        .catch(() => setRemoteApp(null))
        .finally(() => setLoading(false))
    }
  }, [params.id, localApp])

  if (loading) {
    return (
      <Card className="flex items-center justify-center py-16">
        <LoaderCircle className="size-6 animate-spin text-[#08785e]" />
        <span className="ml-3 text-sm text-[#60756f]">Loading application workspace...</span>
      </Card>
    )
  }

  const app = localApp || remoteApp

  if (!app) {
    return (
      <Card>
        <p className="font-bold text-[#10272b]">Application not found</p>
        <p className="mt-2 text-sm text-[#60756f]">
          Application ID <strong>{params.id}</strong> was not found in your session or backend records.
        </p>
        <div className="mt-4">
          <Button href="/applications">Back to applications</Button>
        </div>
      </Card>
    )
  }

  const serviceId = (app as any).serviceId || (app as any).service_id
  const service = serviceCatalog.find((item) => item.id === serviceId)

  const title =
    service?.title ??
    (app as any).customRequest ??
    (app as any).custom_request ??
    "Public Service Application"

  const portalUrl = [
    (app as any).portal_url,
    service?.officialUrl,
  ].find((candidate): candidate is string =>
    typeof candidate === "string" && candidate.toLowerCase().startsWith("https://"),
  )

  const openForm = () => {
    if (localApp) {
      updateApplication(localApp.id, {
        currentStep: Math.max(localApp.currentStep, 1),
        progress: Math.max(localApp.progress, 25),
      })
    }
  }

  const isCustom = (app as any).applicationMode === "custom" || (app as any).application_mode === "custom"
  const customState = (app as any).customState || (app as any).custom_state
  const customDistrict = (app as any).customDistrict || (app as any).custom_district

  return (
    <>
      <PageHeader
        eyebrow={isCustom ? "Custom Application Workspace" : "Application Workspace"}
        title={title}
        description={
          isCustom
            ? `${customState ?? "Jurisdiction Registered"}${customDistrict ? ` · ${customDistrict}` : ""} · ${portalUrl ? "State portal identified; confirm this service there" : "No portal configured for this jurisdiction"}`
            : `${service?.department ?? "Government Service"} · ${service?.jurisdiction ?? "India"}`
        }
        action={
          <Status tone={app.status === "submitted" ? "green" : "amber"}>
            {app.status.replaceAll("_", " ")}
          </Status>
        }
      />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#e9e1d5] bg-[#fffefb] px-4 py-3 text-sm">
        <span className="text-[#60756f]">
          Application ID: <strong className="text-[#10272b]">{app.id}</strong>
        </span>
        <div className="flex items-center gap-3">
          {portalUrl && (
            <span className="text-xs text-[#08785e] font-medium bg-[#e3f2e8] px-2.5 py-1 rounded-md truncate max-w-xs">
              Portal: {portalUrl}
            </span>
          )}
          <Link
            href={service ? `/services/${service.id}` : "/services"}
            className="font-semibold text-[#08785e] hover:underline"
          >
            {service ? "View service details" : "Explore catalog"}
          </Link>
        </div>
      </div>

      <BrowserViewer
        applicationId={app.id}
        serviceId={serviceId}
        portalUrl={portalUrl}
        activities={(app as any).activity || []}
      />

      <Card className="mt-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <FileText className="size-6 text-[#08785e]" />
          <div>
            <p className="font-semibold text-[#10272b]">Application Details & Review</p>
            <p className="mt-1 text-xs text-[#60756f]">
              Review your details and prepare for official submission.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button href={`/applications/${app.id}/form`} onClick={openForm}>
            Edit details <ArrowRight className="ml-2 size-4" />
          </Button>
          <Button href={`/applications/${app.id}/review`} variant="secondary">
            Review & Approve
          </Button>
        </div>
      </Card>
    </>
  )
}
