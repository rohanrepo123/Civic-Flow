"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { Bell, Bot, BriefcaseBusiness, CheckCircle2, ChevronDown, FileText, Grid2X2, Landmark, LayoutDashboard, Menu, Search, Settings, UserRound, X, FilePlus2, Heart, BadgeCheck, IdCard } from "lucide-react"
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react"
import { CivicFlowProvider, useCivicFlow } from "@/lib/civicflow-store"

const nav = [
  ["Dashboard", "/dashboard", LayoutDashboard], ["New Application", "/applications/new", FilePlus2],
  ["Explore Services", "/services", BriefcaseBusiness], ["My Applications", "/applications", FileText],
  ["Documents", "/documents", IdCard], ["Approvals", "/approvals", CheckCircle2],
  ["AI Assistant", "/assistant", Bot], ["Notifications", "/notifications", Bell], ["Settings", "/settings", Settings],
] as const
const newLinks = [
  ["Education & Scholarships", "education", "GraduationCap"], ["Certificates", "certificates", "BadgeCheck"],
  ["Licenses & Permits", "licenses", "IdCard"], ["Benefits & Subsidies", "benefits", "Heart"],
  ["Government Registrations", "registrations", "Landmark"], ["Other Services", "other", "Grid2X2"],
] as const
const exploreLinks = [["All Services", ""], ["By Category", "view=category"], ["By Department", "view=department"], ["By State", "view=state"], ["Popular Services", "sort=popular"], ["Recently Added", "sort=recent"]] as const

function ShellInner({ children }: { children: ReactNode }) {
  const pathname = usePathname(); const router = useRouter(); const { state } = useCivicFlow()
  const [drawer, setDrawer] = useState(false); const [open, setOpen] = useState<"new" | "explore" | "profile" | null>(null); const [query, setQuery] = useState("")
  const menus = useRef<HTMLDivElement>(null); const initials = state.user.name.split(" ").map((part) => part[0]).slice(0, 2).join("").toUpperCase()
  useEffect(() => { const outside = (event: MouseEvent) => { if (!menus.current?.contains(event.target as Node)) setOpen(null) }; const key = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpen(null); setDrawer(false) } }; document.addEventListener("mousedown", outside); document.addEventListener("keydown", key); return () => { document.removeEventListener("mousedown", outside); document.removeEventListener("keydown", key) } }, [])
  useEffect(() => { setOpen(null); setDrawer(false) }, [pathname])
  function search(event: FormEvent<HTMLFormElement>) { event.preventDefault(); router.push(query.trim() ? `/services?query=${encodeURIComponent(query.trim())}` : "/services") }
  const toggle = (name: "new" | "explore" | "profile") => setOpen((current) => current === name ? null : name)
  const newMenu = <div className="cf-menu-panel cf-category-menu">{newLinks.map(([label, category], index) => { const Icons = [Landmark, BadgeCheck, IdCard, Heart, Landmark, Grid2X2]; const Icon = Icons[index]; return <Link key={category} href={category === "other" ? "/services/custom" : `/services?category=${category}`} className="cf-menu-link"><span className="cf-menu-icon"><Icon size={17}/></span>{label}</Link> })}</div>
  const exploreMenu = <div className="cf-menu-panel">{exploreLinks.map(([label, query]) => <Link key={label} href={query ? `/services?${query}` : "/services"} className="cf-menu-link"><span className="cf-menu-icon"><Grid2X2 size={17}/></span>{label}</Link>)}</div>
  return <div className="cf-app-shell">
    {drawer && <button aria-label="Close navigation" className="fixed inset-0 z-30 bg-[#10272b]/55 lg:hidden" onClick={() => setDrawer(false)}/>}
    <aside className={`cf-sidebar ${drawer ? "cf-sidebar-open" : ""}`}>
      <div className="cf-brand-row"><Link href="/dashboard" aria-label="CivicFlow dashboard"><img src="/civicflow-logo.svg" alt="CivicFlow" className="cf-logo"/></Link><button className="cf-mobile-close lg:hidden" onClick={() => setDrawer(false)} aria-label="Close navigation"><X size={20}/></button></div>
      <nav aria-label="Main navigation" className="cf-nav">{nav.map(([label, href, Icon]) => { const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`)); return <Link key={href} href={href} aria-current={active ? "page" : undefined} className={`cf-nav-link ${active ? "active" : ""}`}><Icon size={19}/><span>{label}</span>{label === "Notifications" && <i className="cf-nav-dot"/>}</Link> })}</nav>
      <div className="cf-sidebar-foot"><span className="cf-trust-mark"><CheckCircle2 size={17}/></span><span><strong>Your data stays yours</strong><small>Citizen-controlled assistance</small></span></div>
    </aside>
    <div className="cf-main-column">
      <header className="cf-topbar">
        <button className="cf-mobile-toggle lg:hidden" onClick={() => setDrawer(true)} aria-label="Open navigation"><Menu size={21}/></button>
        <form onSubmit={search} className="cf-global-search"><Search size={18}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search services, applications…" aria-label="Search services and applications"/></form>
        <div className="cf-top-actions" ref={menus}>
          <div className="cf-menu-wrap"><button aria-label="New Application menu" className={`cf-top-action ${open === "new" ? "selected" : ""}`} onClick={() => toggle("new")} aria-expanded={open === "new"}><FilePlus2 size={17}/><span>New Application</span><ChevronDown size={15}/></button>{open === "new" && newMenu}</div>
          <div className="cf-menu-wrap cf-explore-wrap"><button aria-label="Explore Services menu" className={`cf-top-action ${open === "explore" ? "selected" : ""}`} onClick={() => toggle("explore")} aria-expanded={open === "explore"}><Grid2X2 size={17}/><span>Explore Services</span><ChevronDown size={15}/></button>{open === "explore" && exploreMenu}</div>
          <Link href="/notifications" className="cf-icon-button" aria-label="Notifications"><Bell size={19}/><i/></Link>
          <div className="cf-menu-wrap"><button aria-label="Profile menu" className="cf-profile-button" onClick={() => toggle("profile")} aria-expanded={open === "profile"}><span className="cf-avatar">{initials}</span><span className="cf-profile-copy"><strong>{state.user.name}</strong><small>Citizen</small></span><ChevronDown size={15}/></button>{open === "profile" && <div className="cf-menu-panel cf-profile-menu"><Link className="cf-menu-link" href="/profile"><UserRound size={17}/>Profile &amp; account</Link><Link className="cf-menu-link" href="/settings"><Settings size={17}/>Settings</Link></div>}</div>
        </div>
      </header>
      <main className="cf-content">{children}</main>
      <footer className="cf-footer">CivicFlow · Citizen-controlled public service assistance</footer>
    </div>
  </div>
}

export default function AppShell({ children }: { children: ReactNode }) { return <CivicFlowProvider><ShellInner>{children}</ShellInner></CivicFlowProvider> }
