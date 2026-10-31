"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowRight, Building2, FileCheck, FileText, Grid2X2, HandCoins, IdCard, Info, Search, Sparkles, GraduationCap } from "lucide-react"
import { categoryMeta, serviceCatalog, type Service, type ServiceCategory, type ServiceStatus } from "@/src/data/serviceCatalog"
import { useCivicFlow } from "@/lib/civicflow-store"
import { Button, Card, Status } from "@/components/page-primitives"
import { getGeoStates, type GeoState } from "@/lib/civicflow-api"

const icons = { education: GraduationCap, certificates: FileCheck, licenses: IdCard, benefits: HandCoins, registrations: Building2, other: Grid2X2 }
const statusLabels: Record<ServiceStatus, string> = { available: "Listed service", coming_soon: "Not integrated", information_only: "Guided information" }
const categoryColors: Record<ServiceCategory, string> = { education: "education", certificates: "certificates", licenses: "licenses", benefits: "benefits", registrations: "registrations", other: "other" }

function integrationLabel(service: Service) {
  return service.status === "available" && service.officialUrl
    ? "Guided portal"
    : service.status === "coming_soon"
    ? "Not integrated"
    : service.officialUrl
    ? "Guided information"
    : "Needs verification"
}

export function CategoryIcon({ category }: { category: ServiceCategory }) {
  const Icon = icons[category]
  return <Icon size={21} />
}

export function ServiceCard({ service, onStart }: { service: Service; onStart: (serviceId: string) => void }) {
  const Icon = icons[service.category]
  return (
    <Card className="cf-service-card">
      <div className="flex items-start justify-between gap-3">
        <span className={`cf-service-icon ${categoryColors[service.category]}`}>
          <Icon size={21} />
        </span>
        <Status tone={service.status === "available" ? "green" : service.status === "coming_soon" ? "amber" : "blue"}>
          {statusLabels[service.status]}
        </Status>
      </div>
      <h2 className="mt-4 text-[17px] font-bold text-[#10272b]">{service.title}</h2>
      <p className="mt-1 min-h-10 text-[13px] leading-5 text-[#60756f]">{service.description}</p>
      <p className="mt-3 text-xs font-medium text-[#657871]">
        {service.jurisdiction ?? "Jurisdiction not specified"} · {service.department ?? "Department not verified"}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <span className="cf-capability-pill">CivicFlow: {integrationLabel(service)}</span>
        {service.officialUrl && <span className="cf-capability-pill source">Official source listed</span>}
      </div>
      <div className="mt-auto flex flex-wrap gap-2 pt-5">
        <Button href={`/services/${service.id}`} variant="secondary">
          View details <ArrowRight className="ml-1 size-4" />
        </Button>
        {service.status === "available" && (
          <Button onClick={() => onStart(service.id)}>Start guided flow</Button>
        )}
      </div>
    </Card>
  )
}

export function ServiceDirectory() {
  const router = useRouter()
  const { createApplication } = useCivicFlow()

  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("all")
  const [status, setStatus] = useState("all")
  const [stateFilter, setStateFilter] = useState("all")
  const [department, setDepartment] = useState("all")
  const [integration, setIntegration] = useState("all")
  const [sort, setSort] = useState("relevance")
  const [filtersReady, setFiltersReady] = useState(false)
  const [jurisdictions, setJurisdictions] = useState<GeoState[]>([])
  const [displayLimit, setDisplayLimit] = useState(30)

  useEffect(() => {
    const p = new URLSearchParams(window.location.search)
    setQuery(p.get("query") ?? p.get("q") ?? "")
    setCategory(p.get("category") ?? "all")
    setStateFilter(p.get("state")?.toLowerCase() ?? "all")
    setDepartment(p.get("department") ?? "all")
    setSort(p.get("sort") === "name" ? "name" : "relevance")
    setFiltersReady(true)

    // Load pan-India states/UTs from Core API or static inventory
    getGeoStates()
      .then((data) => setJurisdictions(data))
      .catch(() => {
        fetch("/inventory/state_ut_portals.json")
          .then((res) => res.json())
          .then((data) => setJurisdictions(data))
          .catch(() => setJurisdictions([]))
      })
  }, [])

  useEffect(() => {
    if (!filtersReady) return
    const p = new URLSearchParams()
    if (query) p.set("query", query)
    if (category !== "all") p.set("category", category)
    if (stateFilter !== "all") p.set("state", stateFilter)
    if (department !== "all") p.set("department", department)
    if (sort !== "relevance") p.set("sort", sort)
    const suffix = p.toString()
    window.history.replaceState(null, "", suffix ? `/services?${suffix}` : "/services")
    setDisplayLimit(30)
  }, [filtersReady, query, category, stateFilter, department, sort])

  const departments = useMemo(
    () =>
      Array.from(
        new Set(
          serviceCatalog
            .filter(
              (s) =>
                stateFilter === "all" ||
                s.jurisdiction?.toLowerCase().includes(stateFilter) ||
                s.jurisdiction?.toLowerCase().includes("national") ||
                s.jurisdiction?.toLowerCase().includes("india")
            )
            .map((s) => s.department)
            .filter((x): x is string => Boolean(x))
        )
      ).sort(),
    [stateFilter]
  )

  const results = serviceCatalog
    .filter((service) => {
      const text = [
        service.title,
        service.description,
        service.department,
        service.jurisdiction,
        ...(service.aliases ?? []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()

      const mode = integrationLabel(service).toLowerCase()
      const matchesQuery = query ? text.includes(query.toLowerCase()) : true
      const matchesCategory = category === "all" || service.category === category
      const matchesStatus = status === "all" || service.status === status
      const matchesState =
        stateFilter === "all" ||
        service.jurisdiction?.toLowerCase().includes(stateFilter) ||
        (stateFilter === "central" && service.jurisdiction?.toLowerCase().includes("national"))

      const matchesDept = department === "all" || service.department === department
      const matchesIntegration = integration === "all" || mode === integration

      return matchesQuery && matchesCategory && matchesStatus && matchesState && matchesDept && matchesIntegration
    })
    .sort((a, b) => (sort === "name" ? a.title.localeCompare(b.title) : 0))

  const start = (id: string) => {
    const application = createApplication(id)
    if (application) {
      router.push(`/applications/${application.id}/workspace`)
    }
  }

  const clear = () => {
    setQuery("")
    setCategory("all")
    setStatus("all")
    setStateFilter("all")
    setDepartment("all")
    setIntegration("all")
    setSort("relevance")
    router.push("/services")
  }

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-[#eadfcf] bg-[#fff8eb] px-4 py-3 text-xs leading-5 text-[#72521e]">
        Explore Services is seeded from CivicFlow’s India inventory: covering Central Government portals and all {jurisdictions.length || 36} States and Union Territories. Candidate rows remain unverified until an exact official service route is confirmed.
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
        {Object.entries(categoryMeta).map(([key, meta]) => (
          <button
            key={key}
            onClick={() => setCategory(category === key ? "all" : key)}
            className={`cf-category-chip ${category === key ? "selected" : ""}`}
          >
            <span className={`cf-service-icon ${categoryColors[key as ServiceCategory]}`}>
              <CategoryIcon category={key as ServiceCategory} />
            </span>
            <span>{meta.label}</span>
          </button>
        ))}
      </div>

      <div className="cf-directory-layout">
        <Card className="cf-filter-panel">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold">Filters</h2>
            <button onClick={clear} className="text-xs font-semibold text-[#08785e]">
              Clear all
            </button>
          </div>

          <label className="cf-filter-field">
            <span>Search within results</span>
            <span className="cf-filter-input">
              <Search size={16} />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Service, keyword, department"
              />
            </span>
          </label>

          <label className="cf-filter-field">
            <span>State / Jurisdiction</span>
            <select
              value={stateFilter}
              onChange={(e) => {
                setStateFilter(e.target.value)
                setDepartment("all")
              }}
            >
              <option value="all">All India (National & States)</option>
              <option value="national">Central / National Portals</option>
              {jurisdictions.map((st) => (
                <option key={st.state_code} value={st.name.toLowerCase()}>
                  {st.name} ({st.jurisdiction_type})
                </option>
              ))}
            </select>
          </label>

          <label className="cf-filter-field">
            <span>Department</span>
            <select value={department} onChange={(e) => setDepartment(e.target.value)}>
              <option value="all">All departments</option>
              {departments.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
          </label>

          <label className="cf-filter-field">
            <span>Category</span>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="all">All categories</option>
              {Object.entries(categoryMeta).map(([key, meta]) => (
                <option key={key} value={key}>
                  {meta.label}
                </option>
              ))}
            </select>
          </label>

          <label className="cf-filter-field">
            <span>Official listing</span>
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="all">All listing states</option>
              <option value="available">Listed service</option>
              <option value="information_only">Guided information</option>
              <option value="coming_soon">Not integrated</option>
            </select>
          </label>

          <label className="cf-filter-field">
            <span>CivicFlow capability</span>
            <select value={integration} onChange={(e) => setIntegration(e.target.value)}>
              <option value="all">All capabilities</option>
              <option value="guided portal">Guided portal</option>
              <option value="guided information">Guided information</option>
              <option value="not integrated">Not integrated</option>
              <option value="needs verification">Needs verification</option>
            </select>
          </label>
        </Card>

        <div className="min-w-0">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-[.12em] text-[#08785e]">Service directory</p>
              <h2 className="mt-1 text-xl font-bold text-[#10272b]">
                {category === "all" ? "Explore Government Services" : categoryMeta[category as ServiceCategory].label}
              </h2>
              <p className="mt-1 text-sm text-[#60756f]">
                {results.length} matching {results.length === 1 ? "service" : "services"} across India
              </p>
            </div>
            <label className="cf-sort">
              <span>Sort</span>
              <select value={sort} onChange={(e) => setSort(e.target.value)}>
                <option value="relevance">Most relevant</option>
                <option value="name">Name</option>
              </select>
            </label>
          </div>

          {results.length ? (
            <>
              <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                {results.slice(0, displayLimit).map((service) => (
                  <ServiceCard key={service.id} service={service} onStart={start} />
                ))}
              </div>
              {results.length > displayLimit && (
                <div className="mt-8 flex flex-col items-center justify-center gap-2">
                  <p className="text-xs text-[#60756f]">
                    Showing <strong>{Math.min(displayLimit, results.length)}</strong> of <strong>{results.length}</strong> services across India
                  </p>
                  <Button variant="secondary" onClick={() => setDisplayLimit((prev) => prev + 30)}>
                    Show more services
                  </Button>
                </div>
              )}
            </>
          ) : (
            <Card className="text-center py-10">
              <Info className="mx-auto text-[#08785e] size-8" />
              <h3 className="mt-3 font-bold text-lg text-[#10272b]">No matching services found</h3>
              <p className="mt-1 text-sm text-[#60756f]">
                Try adjusting your filters or searching with alternative keywords.
              </p>
              <Button href="/services/custom" className="mt-4">
                Request a custom service <ArrowRight className="ml-2 size-4" />
              </Button>
            </Card>
          )}
        </div>
      </div>

      <div className="cf-custom-banner">
        <span className="cf-custom-mark">
          <Sparkles size={20} />
        </span>
        <div>
          <strong>Can’t find your service in the catalog?</strong>
          <p>Describe your requirement in natural language and CivicFlow will locate the authoritative state/central portal.</p>
        </div>
        <Button href="/services/custom" variant="secondary">
          Describe a service <ArrowRight className="ml-2 size-4" />
        </Button>
      </div>
    </div>
  )
}
