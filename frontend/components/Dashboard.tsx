"use client";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { filterLeads } from "@/lib/filter";
import {
  Activity,
  ArrowDownLeft,
  ArrowRight,
  ArrowUpRight,
  Bell,
  CalendarDays,
  Check,
  CheckCheck,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  Clock3,
  ExternalLink,
  Filter,
  GitBranch,
  LayoutDashboard,
  LogOut,
  Menu,
  MoreHorizontal,
  Play,
  RefreshCw,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Users,
  Workflow,
  X,
  AlertTriangle,
  Pause,
} from "lucide-react";
import { api, setCsrf } from "@/lib/api";
import type {
  Lead,
  Detail,
  Message,
  Overview,
  Run,
  Settings,
  Rules,
} from "@/lib/types";

const nav = [
  { path: "", name: "Overview", icon: LayoutDashboard },
  { path: "pipeline", name: "Lead pipeline", icon: Users },
  { path: "approvals", name: "Approval queue", icon: ClipboardCheck },
  { path: "runs", name: "Automation runs", icon: GitBranch },
  { path: "settings", name: "Settings", icon: Settings2 },
];
const statuses = [
  "NEW",
  "PROCESSING",
  "NEEDS_REVIEW",
  "QUALIFIED",
  "NURTURE",
  "DISQUALIFIED",
  "CONTACTED",
  "BOOKED",
  "WON",
  "LOST",
];
function human(value: string) {
  return value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^\w/, (x) => x.toUpperCase());
}
function date(value: string) {
  return new Date(
    value.endsWith("Z") || /[+-]\d\d:\d\d$/.test(value) ? value : value + "Z",
  ).toLocaleDateString("en", { month: "short", day: "numeric" });
}
function time(value: string) {
  return new Date(
    value.endsWith("Z") || /[+-]\d\d:\d\d$/.test(value) ? value : value + "Z",
  ).toLocaleTimeString("en", { hour: "2-digit", minute: "2-digit" });
}
function Badge({ value }: { value: string }) {
  const tone = [
    "high",
    "QUALIFIED",
    "success",
    "synced",
    "approved",
    "sent",
    "WON",
  ].includes(value)
    ? "green"
    : ["failed", "DISQUALIFIED", "unknown"].includes(value)
      ? "red"
      : [
            "manual review",
            "NEEDS_REVIEW",
            "pending",
            "pending_approval",
          ].includes(value)
        ? "amber"
        : "neutral";
  return (
    <span className={`badge ${tone}`}>
      <i />
      {human(value)}
    </span>
  );
}
function Empty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty">
      <CheckCheck size={30} />
      <h3>{title}</h3>
      <p>{detail}</p>
    </div>
  );
}

export default function Dashboard({ view }: { view: string[] }) {
  const section = view[0] || "",
    leadId = view[0] === "leads" ? view[1] : undefined;
  const router = useRouter();
  const [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [mobile, setMobile] = useState(false);
  const [leads, setLeads] = useState<Lead[]>([]),
    [overview, setOverview] = useState<Overview | null>(null),
    [runs, setRuns] = useState<Run[]>([]),
    [drafts, setDrafts] = useState<Message[]>([]),
    [detail, setDetail] = useState<Detail | null>(null),
    [settings, setSettings] = useState<Settings | null>(null);
  const [search, setSearch] = useState(""),
    [status, setStatus] = useState("all"),
    [category, setCategory] = useState("all"),
    [source, setSource] = useState("all"),
    [failuresOnly, setFailuresOnly] = useState(false);
  const load = useCallback(async () => {
    try {
      const [ls, ov, rs, ds] = await Promise.all([
        api<Lead[]>("/admin/leads"),
        api<Overview>("/admin/overview"),
        api<Run[]>("/admin/runs"),
        api<Message[]>("/admin/messages"),
      ]);
      setLeads(ls);
      setOverview(ov);
      setRuns(rs);
      setDrafts(ds);
      if (leadId) setDetail(await api<Detail>(`/admin/leads/${leadId}`));
      if (section === "settings")
        setSettings(await api<Settings>("/admin/settings"));
    } catch (e) {
      setError((e as Error).message);
      if ((e as Error).message.startsWith("Session expired"))
        router.replace("/login");
    } finally {
      setLoading(false);
    }
  }, [leadId, section, router]);
  useEffect(() => {
    api<{ csrf: string }>("/auth/session")
      .then(async (data) => {
        setCsrf(data.csrf);
        await load();
      })
      .catch(() => router.replace("/login"));
  }, [load, router]);
  async function action(
    path: string,
    method = "POST",
    body?: unknown,
    success = "Change saved.",
  ) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(path, method, body);
      await load();
      setNotice(success);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const failedLeadIds = new Set(
    runs
      .filter((x) => x.status === "failed" && x.retry_state !== "resolved")
      .map((x) => x.lead_id),
  );
  const filtered = filterLeads(
    leads,
    { search, status, category, source, failuresOnly },
    failedLeadIds,
  );
  const title = leadId
    ? "Lead workspace"
    : nav.find((x) => x.path === section)?.name || "Overview";
  return (
    <div className="workspace">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <Link href="/dashboard" className="brand">
          <Workflow size={26} /> ClientFlow <span>AI</span>
        </Link>
        <div className="workspace-label">
          <span className="workspace-avatar">O</span>
          <div>
            Omar’s workspace<small>Freelance operations</small>
          </div>
          <MoreHorizontal size={16} />
        </div>
        <p className="nav-caption">WORKSPACE</p>
        <nav>
          {nav.map((item) => (
            <Link
              key={item.path}
              href={`/dashboard${item.path ? "/" + item.path : ""}`}
              onClick={() => setMobile(false)}
              className={
                section === item.path || (leadId && item.path === "pipeline")
                  ? "active"
                  : ""
              }
            >
              <item.icon size={18} />
              {item.name}
              {item.path === "approvals" && !!drafts.length && (
                <span className="nav-count">{drafts.length}</span>
              )}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="control-note">
            <ShieldCheck size={19} />
            <b>Human in control</b>
            <p>Review. Approve. Then deliver.</p>
            <span>
              <i /> Approval-first workspace
            </span>
          </div>
          <Link href="/intake" target="_blank">
            <ExternalLink size={17} />
            Public enquiry form
          </Link>
          <button
            onClick={() =>
              void action("/auth/logout", "POST").then(() =>
                router.replace("/login"),
              )
            }
          >
            <LogOut size={17} />
            Sign out
          </button>
          <div className="profile">
            <span>OE</span>
            <div>
              Omar<small>Administrator</small>
            </div>
            <span className="online-dot" />
          </div>
        </div>
      </aside>
      {mobile && (
        <button
          className="scrim"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <div className="main-area">
        <header className="topbar">
          <div>
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobile(true)}
            >
              <Menu />
            </button>
            <span className="breadcrumb">
              Workspace <ChevronRight size={14} />
            </span>
            <b>{title}</b>
          </div>
          <div>
            <span className="live-pill">
              <i />{" "}
              {overview
                ? "API connected"
                : loading
                  ? "Connecting"
                  : "API unavailable"}
            </span>
            <button
              className="icon-button"
              aria-label="Open failures"
              onClick={() => router.push("/dashboard/runs")}
            >
              <Bell size={19} />
              {!!overview?.failed_runs && <i className="notification-dot" />}
            </button>
            <span className="top-avatar">OE</span>
          </div>
        </header>
        <main id="main">
          <div className="page-heading">
            <div>
              <p className="eyebrow">
                {leadId
                  ? "FROM ENQUIRY TO OPPORTUNITY"
                  : section === ""
                    ? "YOUR OPERATIONS AT A GLANCE"
                    : "AUTOMATION, WITH OVERSIGHT"}
              </p>
              <h1>
                {leadId
                  ? detail?.lead.name || "Lead workspace"
                  : section === ""
                    ? "Keep good work moving."
                    : title}
              </h1>
              <p className="muted">
                {leadId
                  ? `${detail?.lead.company || "Independent prospect"} · ${detail?.lead.service || "Loading project"}`
                  : section === ""
                    ? "A clear view of your enquiries, decisions and next steps."
                    : section === "pipeline"
                      ? "Every conversation has a place. Find the next one to move forward."
                      : section === "approvals"
                        ? "Review the context. Make it personal. Give the green light."
                        : section === "runs"
                          ? "Follow each run, inspect failures and recover safely."
                          : "Set the rules. Keep business decisions transparent."}
              </p>
            </div>
            <div className="heading-actions">
              <button
                className="button"
                disabled={busy || loading}
                onClick={() => {
                  setError("");
                  void load();
                }}
              >
                <RefreshCw size={16} />
                Refresh
              </button>
              <Link className="button primary" href="/intake" target="_blank">
                Open intake <ArrowUpRight size={16} />
              </Link>
            </div>
          </div>
          {error && (
            <div className="alert error" role="alert">
              <AlertTriangle size={18} />
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="alert success" role="status">
              <Check size={18} />
              {notice}
              <button
                aria-label="Dismiss notification"
                onClick={() => setNotice("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {loading ? (
            <div className="loading">
              <span />
              Connecting to your workspace…
            </div>
          ) : (
            <>
              {section === "" && overview && (
                <>
                  <div className="metrics">
                    {[
                      {
                        label: "Total enquiries",
                        value: overview.total,
                        sub: `${overview.new} awaiting processing`,
                        icon: ArrowDownLeft,
                        tone: "blue",
                      },
                      {
                        label: "Qualified leads",
                        value: overview.qualified,
                        sub: "Ready for a meaningful next step",
                        icon: Sparkles,
                        tone: "green",
                      },
                      {
                        label: "Needs your review",
                        value: overview.review,
                        sub: `${overview.approval_pending} drafts waiting for approval`,
                        icon: ClipboardCheck,
                        tone: "amber",
                      },
                      {
                        label: "Discovery bookings",
                        value: overview.bookings,
                        sub: `${overview.conversion}% won conversion`,
                        icon: CalendarDays,
                        tone: "purple",
                      },
                    ].map((x) => (
                      <section className="metric-card" key={x.label}>
                        <div>
                          <span>{x.label}</span>
                          <x.icon className={x.tone} size={20} />
                        </div>
                        <b>{x.value.toString().padStart(2, "0")}</b>
                        <small>{x.sub}</small>
                      </section>
                    ))}
                  </div>
                  <section className="flow-strip">
                    <div className="flow-title">
                      <Workflow size={20} />
                      <div>
                        <b>Your enquiry engine</b>
                        <small>
                          One connected workflow. Every step traceable.
                        </small>
                      </div>
                    </div>
                    <div className="flow-steps">
                      {[
                        "Capture",
                        "Extract",
                        "Qualify",
                        "Approve",
                        "Deliver",
                        "Follow up",
                      ].map((x, i) => (
                        <div key={x}>
                          <span className={i === 3 ? "approval-step" : ""}>
                            {i === 3 ? (
                              <ShieldCheck size={14} />
                            ) : (
                              <Check size={14} />
                            )}
                          </span>
                          {x}
                          {i < 5 && <ChevronRight size={13} />}
                        </div>
                      ))}
                    </div>
                    <Link
                      href="/dashboard/runs"
                      aria-label="Inspect workflow runs"
                    >
                      <ArrowUpRight size={20} />
                    </Link>
                  </section>
                  <div className="overview-grid">
                    <section className="panel">
                      <div className="section-heading">
                        <div>
                          <p className="eyebrow">PIPELINE</p>
                          <h2>Recent enquiries</h2>
                        </div>
                        <Link className="text-link" href="/dashboard/pipeline">
                          View all <ArrowRight size={15} />
                        </Link>
                      </div>
                      <LeadTable
                        leads={leads.slice(0, 5)}
                        failedIds={failedLeadIds}
                      />
                    </section>
                    <section className="panel attention-panel">
                      <div className="section-heading">
                        <div>
                          <p className="eyebrow">NEXT BEST ACTION</p>
                          <h2>A little attention.</h2>
                        </div>
                        <span className="soft-icon">
                          <Activity size={20} />
                        </span>
                      </div>
                      <Link
                        href="/dashboard/approvals"
                        className="attention-item"
                      >
                        <span className="attention-icon amber">
                          <ClipboardCheck size={19} />
                        </span>
                        <div>
                          <b>{overview.approval_pending} responses to review</b>
                          <small>Your voice. Your final decision.</small>
                        </div>
                        <ChevronRight size={17} />
                      </Link>
                      <Link href="/dashboard/runs" className="attention-item">
                        <span className="attention-icon red">
                          <AlertTriangle size={19} />
                        </span>
                        <div>
                          <b>{overview.failed_runs} runs need recovery</b>
                          <small>Original enquiries are safely stored.</small>
                        </div>
                        <ChevronRight size={17} />
                      </Link>
                      <div className="mini-pipeline">
                        <span>OPPORTUNITY MIX</span>
                        {[
                          [
                            "Qualified",
                            leads.filter((x) => x.category === "high").length,
                            "green",
                          ],
                          ["In review", overview.review, "amber"],
                          [
                            "Other stages",
                            leads.filter(
                              (x) =>
                                x.category !== "high" &&
                                x.status !== "NEEDS_REVIEW",
                            ).length,
                            "blue",
                          ],
                        ].map(([label, value, color]) => (
                          <div key={String(label)}>
                            <label>
                              {label}
                              <b>{value}</b>
                            </label>
                            <div className="bar-track">
                              <i
                                className={String(color)}
                                style={{
                                  width: `${(Number(value) / Math.max(1, leads.length)) * 100}%`,
                                }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="runtime">
                        <span>
                          <i />
                          Average run{" "}
                          <b>{overview.average_processing_seconds}s</b>
                        </span>
                        <span>
                          AI cost{" "}
                          <b>
                            {overview.estimated_ai_cost === null
                              ? "Unavailable"
                              : `$${overview.estimated_ai_cost.toFixed(2)}`}
                          </b>
                        </span>
                      </div>
                    </section>
                  </div>
                  <section className="panel activity-panel">
                    <div className="section-heading">
                      <div>
                        <p className="eyebrow">TRACEABLE BY DESIGN</p>
                        <h2>Latest automation activity</h2>
                      </div>
                      <Link href="/dashboard/runs" className="text-link">
                        All runs <ArrowRight size={15} />
                      </Link>
                    </div>
                    <div className="run-summary">
                      {runs.slice(0, 4).map((run) => (
                        <Link
                          href={`/dashboard/leads/${run.lead_id}`}
                          key={run.id}
                        >
                          <span
                            className={`activity-symbol ${run.status === "failed" ? "red" : "green"}`}
                          >
                            {run.status === "failed" ? (
                              <AlertTriangle size={17} />
                            ) : (
                              <Check size={17} />
                            )}
                          </span>
                          <div>
                            <b>{human(run.workflow)}</b>
                            <small>
                              {run.status === "failed"
                                ? run.error
                                : "Business state recorded successfully"}
                            </small>
                          </div>
                          <Badge value={run.status} />
                          <small>{time(run.started_at)}</small>
                        </Link>
                      ))}
                    </div>
                  </section>
                </>
              )}
              {section === "pipeline" && (
                <section className="panel">
                  <div className="filterbar">
                    <div className="search">
                      <Search size={17} />
                      <input
                        aria-label="Search leads"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search name, company, service…"
                      />
                    </div>
                    <Filter size={17} />
                    <select
                      aria-label="Pipeline status"
                      value={status}
                      onChange={(e) => setStatus(e.target.value)}
                    >
                      <option value="all">All statuses</option>
                      {statuses.map((x) => (
                        <option key={x} value={x}>
                          {human(x)}
                        </option>
                      ))}
                    </select>
                    <select
                      aria-label="Qualification category"
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                    >
                      <option value="all">All scores</option>
                      {["high", "medium", "low", "manual review"].map((x) => (
                        <option key={x}>{x}</option>
                      ))}
                    </select>
                    <select
                      aria-label="Source filter"
                      value={source}
                      onChange={(e) => setSource(e.target.value)}
                    >
                      <option value="all">All sources</option>
                      {[...new Set(leads.map((x) => x.source))].map((x) => (
                        <option key={x}>{x}</option>
                      ))}
                    </select>
                    <label className="check-label compact">
                      <input
                        type="checkbox"
                        checked={failuresOnly}
                        onChange={(e) => setFailuresOnly(e.target.checked)}
                      />
                      Failures
                    </label>
                  </div>
                  <div className="table-caption">
                    {filtered.length} opportunities · Click an enquiry to
                    inspect its complete timeline
                  </div>
                  <LeadTable leads={filtered} failedIds={failedLeadIds} />
                </section>
              )}
              {leadId && detail && (
                <LeadWorkspace detail={detail} busy={busy} action={action} />
              )}
              {section === "approvals" && (
                <>
                  <div className="approval-banner">
                    <ShieldCheck size={23} />
                    <div>
                      <b>A thoughtful response is worth the pause.</b>
                      <p>
                        Editing resets approval. Sending checks approval and
                        consent again.
                      </p>
                    </div>
                    <span className="badge green">{drafts.length} pending</span>
                  </div>
                  {drafts.length ? (
                    <div className="approval-grid">
                      {drafts.map((msg) => (
                        <section className="panel" key={msg.id}>
                          <div className="section-heading">
                            <div>
                              <h2>{msg.lead?.name}</h2>
                              <p className="muted">
                                {msg.lead?.company} · {msg.lead?.service}
                              </p>
                            </div>
                            <Badge value={msg.lead?.category || "pending"} />
                          </div>
                          <p className="draft-context">{msg.lead?.enquiry}</p>
                          <MessageEditor
                            key={`${msg.id}-${msg.revisions.length}-${msg.approval}-${msg.state}`}
                            message={msg}
                            busy={busy}
                            action={action}
                          />
                          <Link
                            className="text-link"
                            href={`/dashboard/leads/${msg.lead_id}`}
                          >
                            View lead & timeline <ArrowRight size={15} />
                          </Link>
                        </section>
                      ))}
                    </div>
                  ) : (
                    <section className="panel">
                      <Empty
                        title="Your queue is clear."
                        detail="New response drafts will appear here after an enquiry is processed."
                      />
                    </section>
                  )}
                </>
              )}
              {section === "runs" && (
                <section className="panel">
                  <div className="section-heading">
                    <div>
                      <h2>Automation ledger</h2>
                      <p className="muted">
                        Safe errors, persistent attempts and explicit recovery.
                      </p>
                    </div>
                    <label className="check-label compact">
                      <input
                        type="checkbox"
                        checked={failuresOnly}
                        onChange={(e) => setFailuresOnly(e.target.checked)}
                      />
                      Only unresolved failures
                    </label>
                  </div>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Workflow / correlation</th>
                          <th>Started</th>
                          <th>Attempt</th>
                          <th>Status</th>
                          <th>Recovery</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {runs
                          .filter(
                            (x) =>
                              !failuresOnly ||
                              (x.status === "failed" &&
                                x.retry_state !== "resolved"),
                          )
                          .map((run) => (
                            <tr key={run.id}>
                              <td>
                                <Link href={`/dashboard/leads/${run.lead_id}`}>
                                  <b>{human(run.workflow)}</b>
                                </Link>
                                <small className="mono">
                                  {run.correlation_id.slice(0, 18)}…
                                </small>
                                {run.error && (
                                  <p className="run-error">{run.error}</p>
                                )}
                              </td>
                              <td>
                                {date(run.started_at)}
                                <small>{time(run.started_at)}</small>
                              </td>
                              <td>{run.attempts}</td>
                              <td>
                                <Badge value={run.status} />
                              </td>
                              <td>{human(run.retry_state)}</td>
                              <td>
                                {run.status === "failed" &&
                                  run.retry_state !== "resolved" && (
                                    <button
                                      disabled={busy}
                                      className="button small"
                                      onClick={() =>
                                        void action(
                                          `/admin/runs/${run.id}/retry`,
                                          "POST",
                                          undefined,
                                          "Retry completed. Inspect the new run for the result.",
                                        )
                                      }
                                    >
                                      <RefreshCw size={14} />
                                      Retry
                                    </button>
                                  )}
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                  {!runs.length && (
                    <Empty
                      title="No runs yet"
                      detail="Submit an enquiry to start the first traceable automation."
                    />
                  )}
                </section>
              )}
              {section === "settings" && settings && (
                <SettingsEditor
                  settings={settings}
                  busy={busy}
                  action={action}
                />
              )}
            </>
          )}
          <footer className="workspace-footer">
            <span>
              <Workflow size={14} /> ClientFlow AI
            </span>
            <span>Independent product · Every action has a trail.</span>
            <Link href="/intake">
              <CircleHelp size={14} />
              Public intake
            </Link>
          </footer>
        </main>
      </div>
    </div>
  );
}

function LeadTable({
  leads,
  failedIds,
}: {
  leads: Lead[];
  failedIds: Set<string>;
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Prospect</th>
            <th>Project</th>
            <th>Score</th>
            <th>Stage</th>
            <th>Received</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {leads.map((lead, i) => (
            <tr key={lead.id}>
              <td>
                <Link href={`/dashboard/leads/${lead.id}`} className="prospect">
                  <span className={`avatar avatar-${i % 4}`}>
                    {lead.name
                      .split(" ")
                      .map((x) => x[0])
                      .slice(0, 2)
                      .join("")}
                  </span>
                  <span>
                    <b>{lead.name}</b>
                    <small>{lead.company || lead.email}</small>
                  </span>
                </Link>
              </td>
              <td>
                <b className="service-name">{lead.service}</b>
                <small>
                  {lead.source}
                  {failedIds.has(lead.id) && (
                    <span className="failure-label"> · Recovery needed</span>
                  )}
                </small>
              </td>
              <td>
                <span
                  className={`score-number ${lead.score >= 70 ? "green" : lead.score < 40 ? "muted" : "amber"}`}
                >
                  {lead.score}
                  <small>/100</small>
                </span>
              </td>
              <td>
                <Badge value={lead.status} />
              </td>
              <td className="date-cell">{date(lead.created_at)}</td>
              <td>
                <Link
                  className="icon-button"
                  aria-label={`Open ${lead.name}`}
                  href={`/dashboard/leads/${lead.id}`}
                >
                  <ArrowUpRight size={17} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!leads.length && (
        <Empty
          title="No enquiries here yet."
          detail="Share the public intake form or adjust your filters."
        />
      )}
    </div>
  );
}

type Action = (
  path: string,
  method?: string,
  body?: unknown,
  success?: string,
) => Promise<void>;
function LeadWorkspace({
  detail,
  busy,
  action,
}: {
  detail: Detail;
  busy: boolean;
  action: Action;
}) {
  const lead = detail.lead;
  const [pendingFlags, setPendingFlags] = useState<Record<string, boolean>>({});
  return (
    <>
      <div className="lead-topline">
        <Link href="/dashboard/pipeline" className="text-link">
          ← Back to pipeline
        </Link>
        <Badge value={lead.status} />
        <Badge value={lead.category} />
        <span className="mono">{lead.correlation_id}</span>
      </div>
      <div className="detail-grid">
        <div className="detail-primary">
          <section className="panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">ORIGINAL ENQUIRY</p>
                <h2>The project, in their words.</h2>
              </div>
              <span className="soft-icon">
                <ArrowDownLeft size={20} />
              </span>
            </div>
            <p className="original-enquiry">{lead.enquiry}</p>
            <div className="lead-facts">
              <div>
                <small>Email</small>
                <b>{lead.email}</b>
              </div>
              <div>
                <small>Budget</small>
                <b>{lead.budget}</b>
              </div>
              <div>
                <small>Deadline</small>
                <b>{lead.deadline || "Not supplied"}</b>
              </div>
              <div>
                <small>Owner</small>
                <b>{lead.owner}</b>
              </div>
            </div>
            {lead.probable_duplicate && (
              <p className="alert warning">
                Probable duplicate.{" "}
                <Link href={`/dashboard/leads/${lead.probable_duplicate}`}>
                  Inspect previous enquiry ↗
                </Link>
              </p>
            )}
          </section>
          <section className="panel timeline-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">THE COMPLETE PICTURE</p>
                <h2>Automation timeline</h2>
              </div>
              <span className="badge neutral">
                {detail.events.length} events
              </span>
            </div>
            <div className="timeline">
              {detail.events.map((event, i) => (
                <div className="timeline-item" key={event.id}>
                  <div
                    className={`timeline-dot ${event.kind.includes("failed") ? "failed" : event.kind.includes("approved") ? "approval" : ""}`}
                  >
                    {event.kind.includes("failed") ? (
                      <AlertTriangle size={14} />
                    ) : event.kind.includes("approved") ? (
                      <ShieldCheck size={14} />
                    ) : (
                      <Check size={14} />
                    )}
                  </div>
                  <div>
                    <div className="timeline-title">
                      <b>{human(event.kind)}</b>
                      <time>
                        {date(event.created_at)} · {time(event.created_at)}
                      </time>
                    </div>
                    <p>
                      {Object.entries(event.detail)
                        .map(
                          ([k, v]) =>
                            `${human(k)}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`,
                        )
                        .join(" · ") ||
                        "Action recorded in the business ledger."}
                    </p>
                    <span className="timeline-actor">
                      {event.actor}{" "}
                      <span>· STEP {String(i + 1).padStart(2, "0")}</span>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </section>
          <section className="panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">OUTBOUND, ON YOUR TERMS</p>
                <h2>Response workspace</h2>
              </div>
              <Send size={20} />
            </div>
            {detail.messages.length ? (
              detail.messages.map((msg) => (
                <MessageEditor
                  key={`${msg.id}-${msg.revisions.length}-${msg.approval}-${msg.state}`}
                  message={msg}
                  busy={busy}
                  action={action}
                />
              ))
            ) : (
              <Empty
                title="No draft yet"
                detail="Retry extraction after resolving its failure. The original enquiry is preserved."
              />
            )}
          </section>
        </div>
        <div className="detail-secondary">
          <section className="panel qualification">
            <p className="eyebrow">DETERMINISTIC QUALIFICATION</p>
            <div className="score-display">
              <b>
                {lead.score}
                <span>/100</span>
              </b>
              <Badge value={lead.category} />
            </div>
            <p className="muted">Business rules decide. AI provides context.</p>
            {lead.scoring.map((rule) => (
              <div className="rule-result" key={rule.rule}>
                <div>
                  <b>{rule.rule}</b>
                  <span>
                    {rule.points}/{rule.weight}
                  </span>
                </div>
                <div className="bar-track">
                  <i
                    style={{
                      width: `${(Math.max(0, rule.points) / Math.max(1, rule.weight)) * 100}%`,
                    }}
                  />
                </div>
                <small>{rule.reason}</small>
              </div>
            ))}
            {lead.review_reasons.map((x) => (
              <p className="review-reason" key={x}>
                <AlertTriangle size={14} />
                {x}
              </p>
            ))}
            <div className="next-action">
              <Sparkles size={17} />
              <div>
                <b>Recommended next step</b>
                <p>
                  {lead.status === "DISQUALIFIED"
                    ? "Inspect the spam indicators before contacting."
                    : lead.missing.length
                      ? "Ask for the missing details."
                      : "Review the draft and confirm the next step."}
                </p>
              </div>
            </div>
          </section>
          <section className="panel">
            <p className="eyebrow">EXTRACTED CONTEXT</p>
            <h2>Facts & open questions</h2>
            <p className="extracted-summary">
              {lead.requirements.summary || "Extraction pending or failed."}
            </p>
            <h3>Stated deliverables</h3>
            {lead.requirements.deliverables?.map((x) => (
              <p className="fact-line" key={x}>
                <Check size={14} />
                {x}
              </p>
            ))}
            <h3>Missing information</h3>
            {lead.missing.length ? (
              lead.missing.map((x) => (
                <p className="fact-line amber" key={x}>
                  <CircleHelp size={14} />
                  {x}
                </p>
              ))
            ) : (
              <p className="muted">No required details missing.</p>
            )}
            <h3>Generated suggestions</h3>
            {lead.requirements.suggestions?.map((x) => (
              <p className="muted" key={x}>
                {x}
              </p>
            ))}
          </section>
          <section className="panel">
            <div className="section-heading">
              <h2>CRM & follow-up</h2>
              <Clock3 size={19} />
            </div>
            <div className="crm-state">
              <span>Internal opportunity</span>
              <Badge value={detail.crm?.state || "pending"} />
            </div>
            {detail.crm?.error && (
              <p className="alert error">{detail.crm.error}</p>
            )}
            {detail.followups.length ? (
              detail.followups.map((f) => (
                <div className="followup-row" key={f.id}>
                  <span className="followup-number">0{f.position}</span>
                  <div>
                    <b>
                      {f.position === 1 ? "First follow-up" : "Final follow-up"}
                    </b>
                    <small>
                      {date(f.scheduled_at)} · {f.stop_reason || human(f.state)}
                    </small>
                  </div>
                </div>
              ))
            ) : (
              <p className="muted">
                The sequence is scheduled after the initial response is sent.
              </p>
            )}
            <button
              className="button small"
              disabled={busy}
              onClick={() =>
                void action(
                  "/admin/followups/tick",
                  "POST",
                  undefined,
                  "Due follow-ups checked. New drafts require approval.",
                )
              }
            >
              <Play size={14} />
              Check due follow-ups
            </button>
          </section>
          <section className="panel lead-controls">
            <h2>Lead controls</h2>
            <label>
              Pipeline status
              <select
                value={lead.status}
                disabled={busy}
                onChange={(e) =>
                  void action(`/admin/leads/${lead.id}`, "PATCH", {
                    status: e.target.value,
                  })
                }
              >
                {statuses.map((x) => (
                  <option key={x} value={x}>
                    {human(x)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Assigned owner
              <input
                defaultValue={lead.owner}
                onBlur={(e) => {
                  if (e.target.value !== lead.owner)
                    void action(`/admin/leads/${lead.id}`, "PATCH", {
                      owner: e.target.value,
                    });
                }}
              />
            </label>
            {[
              { key: "replied", label: "Reply received", value: lead.replied },
              { key: "paused", label: "Pause follow-ups", value: lead.paused },
              { key: "opted_out", label: "Opted out", value: lead.opted_out },
            ].map((x) => (
              <label className="check-label" key={x.key}>
                <input
                  type="checkbox"
                  checked={pendingFlags[x.key] ?? x.value}
                  disabled={busy}
                  onChange={(e) => {
                    const desired = e.target.checked;
                    setPendingFlags({ ...pendingFlags, [x.key]: desired });
                    void action(`/admin/leads/${lead.id}`, "PATCH", {
                      [x.key]: desired,
                    }).finally(() =>
                      setPendingFlags((previous) => {
                        const next = { ...previous };
                        delete next[x.key];
                        return next;
                      }),
                    );
                  }}
                />
                {x.label}
              </label>
            ))}
            <button
              className="button full"
              disabled={busy}
              onClick={() =>
                void action(
                  `/admin/leads/${lead.id}/retry`,
                  "POST",
                  undefined,
                  "Processing checked. Inspect the latest timeline event.",
                )
              }
            >
              <RefreshCw size={15} />
              Retry processing
            </button>
            <p className="muted small-text">
              <Pause size={13} /> Replies, bookings, opt-outs and closed
              opportunities stop the sequence.
            </p>
          </section>
        </div>
      </div>
    </>
  );
}

function MessageEditor({
  message,
  busy,
  action,
}: {
  message: Message;
  busy: boolean;
  action: Action;
}) {
  const [content, setContent] = useState(message.content),
    [subject, setSubject] = useState(message.subject),
    [revisions, setRevisions] = useState(false);
  const dirty = content !== message.content || subject !== message.subject;
  const locked = ["sent", "unknown", "sending"].includes(message.state);
  return (
    <div className="message-editor">
      <div className="message-meta">
        <b>{human(message.kind)} response</b>
        <Badge
          value={message.state === "draft" ? message.approval : message.state}
        />
      </div>
      <label>
        Subject
        <input
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          disabled={locked}
        />
      </label>
      <label>
        Response draft
        <textarea
          rows={9}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          disabled={locked}
        />
      </label>
      {message.error && (
        <p role="alert" className="alert error">
          {message.error}
        </p>
      )}
      <div className="message-actions">
        {!locked && (
          <>
            <button
              className="button"
              disabled={busy || !dirty}
              onClick={() =>
                void action(
                  `/admin/messages/${message.id}`,
                  "PATCH",
                  { subject, content },
                  "Draft saved. Approval reset for the edited version.",
                )
              }
            >
              Save edit
            </button>
            <button
              className="button"
              disabled={busy || dirty}
              onClick={() =>
                void action(`/admin/messages/${message.id}/reject`)
              }
            >
              Reject
            </button>
            {message.approval !== "approved" ? (
              <button
                className="button primary"
                disabled={busy || dirty}
                onClick={() =>
                  void action(
                    `/admin/messages/${message.id}/approve`,
                    "POST",
                    undefined,
                    "Response approved. It is eligible for delivery.",
                  )
                }
              >
                <Check size={16} />
                Approve
              </button>
            ) : (
              <button
                className="button primary"
                disabled={busy || dirty}
                onClick={() =>
                  void action(
                    `/admin/messages/${message.id}/send`,
                    "POST",
                    undefined,
                    "Delivery attempted. Check the recorded state and timeline.",
                  )
                }
              >
                <Send size={16} />
                Send approved
              </button>
            )}
          </>
        )}
      </div>
      <p className="draft-provenance">
        {message.provider} · {message.prompt_version} ·{" "}
        {message.revisions.length} saved revisions{" "}
        <button className="text-link" onClick={() => setRevisions(!revisions)}>
          {revisions ? "Hide history" : "Revision history"}
        </button>
      </p>
      {revisions && (
        <div className="revision-list">
          {message.revisions.length ? (
            message.revisions.map((r, i) => (
              <details key={i}>
                <summary>
                  Revision {i + 1} · {date(r.at)}
                </summary>
                <pre>
                  {r.subject}
                  {"\n\n"}
                  {r.content}
                </pre>
              </details>
            ))
          ) : (
            <p className="muted">No edits yet.</p>
          )}
        </div>
      )}
    </div>
  );
}

function SettingsEditor({
  settings,
  busy,
  action,
}: {
  settings: Settings;
  busy: boolean;
  action: Action;
}) {
  const [rules, setRules] = useState<Rules>(settings.rules);
  const numeric: { key: keyof Rules; label: string }[] = [
    { key: "budget_weight", label: "Budget fit" },
    { key: "service_weight", label: "Requested service" },
    { key: "completeness_weight", label: "Completeness" },
    { key: "timeline_weight", label: "Timeline" },
    { key: "business_weight", label: "Business context" },
    { key: "geography_weight", label: "Geographic availability" },
    { key: "spam_penalty", label: "Spam penalty" },
    { key: "low_budget_cap", label: "Low-budget score cap" },
    { key: "high_threshold", label: "High score threshold" },
    { key: "medium_threshold", label: "Medium score threshold" },
  ];
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void action(
          "/admin/settings",
          "PUT",
          rules,
          "Business rules saved. They apply to newly processed leads.",
        );
      }}
    >
      <div className="settings-grid">
        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">DEMONSTRATION DEFAULTS</p>
              <h2>Qualification rules</h2>
            </div>
            <Settings2 size={20} />
          </div>
          <p className="muted">
            Positive weights are normalized to 100. Spam subtracts points.
            Review conditions override the category.
          </p>
          <div className="form-grid">
            {numeric.map((x) => (
              <label key={x.key}>
                {x.label}
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={rules[x.key] as number}
                  onChange={(e) =>
                    setRules({ ...rules, [x.key]: Number(e.target.value) })
                  }
                />
              </label>
            ))}
          </div>
          <label>
            Supported services (comma separated)
            <textarea
              rows={3}
              value={rules.supported_services.join(", ")}
              onChange={(e) =>
                setRules({
                  ...rules,
                  supported_services: e.target.value
                    .split(",")
                    .map((x) => x.trim()),
                })
              }
            />
          </label>
          <label>
            Available countries (empty means worldwide)
            <input
              value={rules.allowed_countries.join(", ")}
              onChange={(e) =>
                setRules({
                  ...rules,
                  allowed_countries: e.target.value
                    .split(",")
                    .map((x) => x.trim())
                    .filter(Boolean),
                })
              }
            />
          </label>
          <label className="check-label">
            <input
              type="checkbox"
              checked={rules.review_urgent}
              onChange={(e) =>
                setRules({ ...rules, review_urgent: e.target.checked })
              }
            />
            Require manual review for urgent requests
          </label>
          <label className="check-label">
            <input
              type="checkbox"
              checked={rules.probable_duplicates}
              onChange={(e) =>
                setRules({ ...rules, probable_duplicates: e.target.checked })
              }
            />
            Check probable duplicates by email, phone and business website
          </label>
        </section>
        <div>
          <section className="panel">
            <p className="eyebrow">NEXT STEPS</p>
            <h2>Booking & follow-ups</h2>
            <label>
              Booking URL
              <input
                type="url"
                value={rules.booking_url}
                onChange={(e) =>
                  setRules({ ...rules, booking_url: e.target.value })
                }
              />
            </label>
            <div className="form-grid">
              {rules.followup_days.map((n, i) => (
                <label key={i}>
                  {i === 0 ? "First" : "Final"} follow-up (days)
                  <input
                    type="number"
                    min={1}
                    max={90}
                    value={n}
                    onChange={(e) =>
                      setRules({
                        ...rules,
                        followup_days: rules.followup_days.map((x, j) =>
                          i === j ? Number(e.target.value) : x,
                        ),
                      })
                    }
                  />
                </label>
              ))}
            </div>
            <label className="check-label">
              <input
                type="checkbox"
                checked={rules.notifications_enabled}
                onChange={(e) =>
                  setRules({
                    ...rules,
                    notifications_enabled: e.target.checked,
                  })
                }
              />
              Enable configured Slack notifications
            </label>
            <div className="automation-setting">
              <ShieldCheck size={21} />
              <div>
                <b>Safe initial-response automation</b>
                <p>
                  When enabled, complete high-category leads may receive the
                  initial response without manual approval. Follow-ups still
                  require approval.
                </p>
                <label className="check-label">
                  <input
                    type="checkbox"
                    checked={rules.safe_automation}
                    onChange={(e) =>
                      setRules({ ...rules, safe_automation: e.target.checked })
                    }
                  />
                  Enable automatic initial responses
                </label>
              </div>
            </div>
          </section>
          <section className="panel provider-panel">
            <p className="eyebrow">ENVIRONMENT CONFIGURATION</p>
            <h2>Connected adapters</h2>
            {Object.entries(settings.providers).map(([key, value]) => (
              <div className="provider-row" key={key}>
                <span>{human(key)}</span>
                <b>
                  {typeof value === "boolean"
                    ? value
                      ? "Configured"
                      : "Not configured"
                    : value}
                </b>
              </div>
            ))}
            <p className="muted small-text">
              Credentials stay in server environment variables. Provider names
              show configuration, not live health.
            </p>
          </section>
        </div>
      </div>
      <div className="settings-save">
        <p className="muted">
          Rule changes affect future processing. Existing scores retain their
          original breakdown.
        </p>
        <button className="button primary" disabled={busy}>
          <Check size={17} />
          Save settings
        </button>
      </div>
    </form>
  );
}
