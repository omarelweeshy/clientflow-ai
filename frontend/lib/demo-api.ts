/** Browser-only portfolio simulation. Never connects to an API or sends email. */
import type { Detail, Lead, Message, Rules, Run } from "./types";

export const DEMO_STORAGE_KEY = "clientflow-public-demo-v1";
export interface DemoState {
  version: 1;
  details: Detail[];
  runs: Run[];
  rules: Rules;
  keys: Record<string, { payload: string; correlation: string }>;
  deliveries: string[];
}
const services = [
  "AI automation",
  "Workflow integration",
  "Dashboard development",
  "Document intelligence",
  "Custom internal tool",
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
const stamp = () => new Date().toISOString();
const uid = () => crypto.randomUUID();
const afterDays = (days: number) =>
  new Date(Date.now() + days * 86400000).toISOString();
const copy = <T>(value: T): T => structuredClone(value);

function event(
  detail: Detail,
  kind: string,
  data: Record<string, unknown> = {},
) {
  detail.events.push({
    id: uid(),
    kind,
    actor: "demo simulation",
    created_at: stamp(),
    detail: { simulated: true, ...data },
  });
}
function run(
  state: DemoState,
  detail: Detail,
  workflow: string,
  failed = false,
) {
  state.runs.unshift({
    id: uid(),
    lead_id: detail.lead.id,
    workflow,
    correlation_id: detail.lead.correlation_id,
    status: failed ? "failed" : "success",
    attempts:
      state.runs.filter(
        (x) => x.lead_id === detail.lead.id && x.workflow === workflow,
      ).length + 1,
    error: failed
      ? "Simulated provider failure. Retry to demonstrate recovery."
      : null,
    retry_state: failed ? "available" : "none",
    started_at: stamp(),
    completed_at: stamp(),
  });
}
function stopped(lead: Lead) {
  return (
    lead.replied ||
    lead.opted_out ||
    lead.paused ||
    ["BOOKED", "WON", "LOST"].includes(lead.status)
  );
}
function cancel(detail: Detail) {
  if (!stopped(detail.lead)) return;
  for (const step of detail.followups) {
    if (!["sent", "cancelled"].includes(step.state)) {
      step.state = "cancelled";
      step.stop_reason = "Reply, booking, opt-out, pause or closed opportunity";
      event(detail, "followup_cancelled", { position: step.position });
    }
  }
}
function draft(detail: Detail, kind = "initial") {
  if (detail.messages.some((x) => x.kind === kind)) return;
  detail.messages.push({
    id: uid(),
    lead_id: detail.lead.id,
    kind,
    subject: `${kind === "initial" ? "Your" : "Following up on your"} ${detail.lead.service.toLowerCase()} enquiry`,
    content: `Hi ${detail.lead.name.split(" ")[0]},\n\nThank you for sharing your project. You mentioned: ${detail.lead.enquiry}\n\n${detail.lead.missing.length ? "Could you clarify your " + detail.lead.missing.join(", ") + "?" : "A short discovery conversation would help us confirm scope and the next step."}\n\nThis is a simulated portfolio response. No email will be sent.\n\nOmar`,
    approval: "pending",
    state: "draft",
    error: null,
    provider: "browser simulation",
    prompt_version: "demo-template-v1",
    revisions: [],
  });
  event(detail, "draft_created", { kind });
}
function qualify(state: DemoState, detail: Detail) {
  const lead = detail.lead,
    rules = state.rules;
  lead.missing = [
    !lead.company && "business context",
    lead.budget === "unspecified" && "budget",
    !lead.deadline && "deadline",
  ].filter(Boolean) as string[];
  lead.urgency = /urgent|asap/i.test(lead.enquiry) ? "urgent" : "normal";
  const budget =
    {
      unspecified: 0,
      "under-500": 0.15,
      "500-2000": 0.6,
      "2000-5000": 0.9,
      "5000-plus": 1,
    }[lead.budget] ?? 0;
  const values = [
    budget,
    rules.supported_services.includes(lead.service) ? 1 : 0,
    lead.missing.length ? 0.5 : 1,
    lead.deadline ? 1 : 0,
    lead.company ? 1 : 0,
    1,
  ];
  const weights = [
    rules.budget_weight,
    rules.service_weight,
    rules.completeness_weight,
    rules.timeline_weight,
    rules.business_weight,
    rules.geography_weight,
  ];
  const names = [
    "Budget fit",
    "Requested service",
    "Completeness",
    "Timeline",
    "Business context",
    "Geographic availability",
  ];
  const total = weights.reduce((a, b) => a + b, 0) || 1;
  lead.scoring = weights.map((weight, i) => ({
    rule: names[i],
    weight,
    points: Math.round(((weight * values[i]) / total) * 100),
    reason: "Illustrative browser demo rule",
  }));
  lead.score = Math.min(
    100,
    lead.scoring.reduce((sum, x) => sum + x.points, 0),
  );
  if (lead.budget === "under-500")
    lead.score = Math.min(lead.score, rules.low_budget_cap);
  if (/buy followers|crypto giveaway|guaranteed profit/i.test(lead.enquiry))
    lead.score = Math.max(0, lead.score - rules.spam_penalty);
  lead.review_reasons = [...lead.missing.map((x) => `Missing ${x}`)];
  if (lead.urgency === "urgent" && rules.review_urgent)
    lead.review_reasons.push("Urgent request requires human review");
  if (lead.probable_duplicate)
    lead.review_reasons.push(
      "Possible previous enquiry; review before responding",
    );
  lead.category = lead.review_reasons.length
    ? "manual review"
    : lead.score >= rules.high_threshold
      ? "high"
      : lead.score >= rules.medium_threshold
        ? "medium"
        : "low";
  lead.status =
    lead.category === "manual review"
      ? "NEEDS_REVIEW"
      : lead.category === "high"
        ? "QUALIFIED"
        : lead.category === "medium"
          ? "NURTURE"
          : "DISQUALIFIED";
  lead.requirements = {
    summary: lead.enquiry,
    deliverables: [lead.service],
    suggestions: [
      "Confirm project scope before committing to delivery. This suggestion is simulated.",
    ],
  };
  detail.crm = {
    state: "synced",
    attempts: (detail.crm?.attempts || 0) + 1,
    error: null,
  };
  event(detail, "qualification_calculated", { score: lead.score });
  run(state, detail, "intake");
  run(state, detail, "crm_sync");
  draft(detail);
}
function newDetail(input: Record<string, unknown>): Detail {
  const str = (key: string) =>
    typeof input[key] === "string" ? (input[key] as string).trim() : "";
  const lead: Lead = {
    id: uid(),
    name: str("name"),
    email: str("email").toLowerCase(),
    phone: str("phone"),
    company: str("company"),
    website: str("website"),
    source: "portfolio demo",
    service: str("service"),
    enquiry: str("enquiry"),
    budget: str("budget") || "unspecified",
    deadline: str("deadline"),
    contact_method: str("contact_method") || "email",
    status: "NEW",
    score: 0,
    category: "manual review",
    urgency: "normal",
    consent: input.consent === true,
    opted_out: false,
    replied: false,
    paused: false,
    owner: "Demo operator",
    created_at: stamp(),
    correlation_id: uid(),
    missing: [],
    review_reasons: [],
    requirements: {},
    scoring: [],
    probable_duplicate: null,
  };
  const detail: Detail = {
    lead,
    events: [],
    messages: [],
    followups: [],
    crm: null,
  };
  event(detail, "intake_received");
  return detail;
}
function send(state: DemoState, detail: Detail, message: Message) {
  if (state.deliveries.includes(message.id))
    return { ok: true, simulated: true };
  if (stopped(detail.lead) || !detail.lead.consent)
    throw new Error(
      "Delivery is blocked by this lead's stop conditions or consent.",
    );
  if (
    message.approval !== "approved" ||
    !["draft", "failed"].includes(message.state)
  )
    throw new Error("Save and approve this draft before simulated delivery.");
  if (
    message.kind === "followup_2" &&
    !detail.messages.some((x) => x.kind === "followup_1" && x.state === "sent")
  )
    throw new Error("Deliver the first follow-up before the final follow-up.");
  message.state = "sent";
  message.error = null;
  state.deliveries.push(message.id);
  detail.lead.status = "CONTACTED";
  event(detail, "email_sent", {
    message_id: message.id,
    external_email_sent: false,
  });
  run(state, detail, "email");
  if (message.kind === "initial" && !detail.followups.length) {
    detail.followups = state.rules.followup_days.map((days, i) => ({
      id: uid(),
      position: i + 1,
      scheduled_at: afterDays(days),
      state: "scheduled",
      stop_reason: null,
    }));
    event(detail, "followups_scheduled");
  } else {
    const step = detail.followups.find(
      (x) => `followup_${x.position}` === message.kind,
    );
    if (step) step.state = "sent";
  }
  return { ok: true, simulated: true };
}

export function createDemoState(): DemoState {
  const state: DemoState = {
    version: 1,
    details: [],
    runs: [],
    keys: {},
    deliveries: [],
    rules: {
      budget_weight: 30,
      service_weight: 25,
      completeness_weight: 20,
      timeline_weight: 10,
      business_weight: 10,
      geography_weight: 5,
      spam_penalty: 80,
      low_budget_cap: 39,
      high_threshold: 70,
      medium_threshold: 40,
      supported_services: [...services],
      allowed_countries: [],
      probable_duplicates: true,
      review_urgent: true,
      booking_url: "https://cal.com/",
      followup_days: [3, 7],
      safe_automation: false,
      notifications_enabled: false,
    },
  };
  const fixtures = [
    [
      "Nadia Farouk",
      "Atlas Studio",
      "AI automation",
      "2000-5000",
      "We need to automate enquiry triage and connect our forms to the studio CRM, with human approval and a clear audit trail.",
      "qualified",
    ],
    [
      "James Porter",
      "",
      "Custom internal tool",
      "unspecified",
      "I want an internal tool for organizing project requests. I am still exploring the scope and would appreciate guidance.",
      "incomplete",
    ],
    [
      "Maya Chen",
      "Fieldwork",
      "Workflow integration",
      "5000-plus",
      "Connect our support intake to our CRM and prepare a response for review. Our team processes fifty enquiries each week.",
      "contacted",
    ],
    [
      "Alex Example",
      "Promo Example",
      "Other",
      "under-500",
      "Buy followers and get guaranteed profit. Click here to win a crypto giveaway with our promotional offer.",
      "spam",
    ],
    [
      "Sara Ibrahim",
      "Northline",
      "Document intelligence",
      "2000-5000",
      "Urgent: our team needs to search and summarize internal documents asap. We need citations and approval controls.",
      "urgent",
    ],
    [
      "Leo Martin",
      "Cedar Partners",
      "Document intelligence",
      "5000-plus",
      "We need a document search pilot for internal procedures with access controls and a clear citation trail.",
      "ai_failure",
    ],
    [
      "Amira Hassan",
      "Common Ground",
      "Workflow integration",
      "2000-5000",
      "Sync validated website enquiries to our CRM, de-duplicate contacts and prepare personalized replies for approval.",
      "crm_failure",
    ],
    [
      "Daniel Reed",
      "Paperplane",
      "AI automation",
      "2000-5000",
      "Our agency wants an enquiry qualification pipeline with structured extraction and a review queue before email.",
      "email_failure",
    ],
    [
      "Lina Mansour",
      "Studio Nine",
      "Custom internal tool",
      "5000-plus",
      "Build a small project operations tool for our consulting team. We need an overview and a complete enquiry timeline.",
      "replied",
    ],
    [
      "Oliver Brooks",
      "Evergreen",
      "Dashboard development",
      "2000-5000",
      "We need a control dashboard for incoming service requests, workflow failures, approvals and team follow-ups.",
      "booked",
    ],
  ];
  for (const [name, company, service, budget, enquiry, scenario] of fixtures) {
    const detail = newDetail({
      name,
      company,
      service,
      budget,
      enquiry,
      email: `demo.${scenario}@example.com`,
      consent: true,
      deadline: scenario === "incomplete" ? "" : afterDays(45).slice(0, 10),
    });
    state.details.push(detail);
    qualify(state, detail);
    if (scenario === "ai_failure") {
      detail.lead.status = "NEEDS_REVIEW";
      detail.messages = [];
      run(state, detail, "intake", true);
      event(detail, "ai_failed", { simulated: true });
    }
    if (scenario === "crm_failure") {
      detail.crm = {
        state: "failed",
        attempts: 1,
        error: "Simulated CRM outage",
      };
      run(state, detail, "crm_sync", true);
    }
    if (scenario === "email_failure") {
      detail.messages[0].approval = "approved";
      detail.messages[0].state = "failed";
      detail.messages[0].error =
        "Simulated email failure; retry from Automation runs.";
      run(state, detail, "email", true);
    }
    if (["contacted", "replied", "booked"].includes(scenario)) {
      detail.messages[0].approval = "approved";
      send(state, detail, detail.messages[0]);
      if (scenario === "contacted")
        detail.followups[0].scheduled_at = afterDays(-1);
      if (scenario === "replied") detail.lead.replied = true;
      if (scenario === "booked") detail.lead.status = "BOOKED";
      cancel(detail);
    }
  }
  return state;
}

/** Pure simulation entry point so workflow invariants can be tested without a browser. */
export function handleDemoRequest(
  state: DemoState,
  path: string,
  method = "GET",
  body?: unknown,
  extra: Record<string, string> = {},
): unknown {
  const data = (
    body && typeof body === "object" && !Array.isArray(body) ? body : {}
  ) as Record<string, unknown>;
  const allLeads = () => state.details.map((x) => x.lead);
  if (path === "/auth/session" || path === "/auth/login")
    return { csrf: "public-demo-no-server-session", actor: "demo visitor" };
  if (path === "/auth/logout") return { ok: true };
  if (path === "/public/config")
    return { services: [...state.rules.supported_services, "Other"] };
  if (path === "/public/intake" && method === "POST") {
    const incoming = newDetail(data);
    const lead = incoming.lead;
    if (state.details.length >= 100)
      throw new Error("Demo limit reached. Reset the demo to start again.");
    if (
      lead.name.length < 2 ||
      lead.name.length > 120 ||
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(lead.email) ||
      lead.email.length > 254 ||
      lead.enquiry.length < 20 ||
      lead.enquiry.length > 5000 ||
      !lead.consent ||
      data.honeypot
    )
      throw new Error(
        "Use valid fictional details, a project description and consent.",
      );
    if (![...state.rules.supported_services, "Other"].includes(lead.service))
      throw new Error("Choose a configured service.");
    if (
      ![
        "unspecified",
        "under-500",
        "500-2000",
        "2000-5000",
        "5000-plus",
      ].includes(lead.budget)
    )
      throw new Error("Choose a valid budget.");
    if (lead.contact_method === "phone" && !lead.phone)
      throw new Error("Phone is required for phone contact.");
    if (lead.website) {
      const url = new URL(lead.website);
      if (
        !["http:", "https:"].includes(url.protocol) ||
        url.username ||
        url.password
      )
        throw new Error("Use an HTTP or HTTPS website without credentials.");
    }
    if (
      lead.deadline &&
      (!/^\d{4}-\d{2}-\d{2}$/.test(lead.deadline) ||
        Number.isNaN(Date.parse(lead.deadline)))
    )
      throw new Error("Choose a valid deadline.");
    const key = extra["Idempotency-Key"] || "";
    if (key.length < 8 || key.length > 100)
      throw new Error("A valid submission key is required.");
    const payload = JSON.stringify([
      lead.name,
      lead.email,
      lead.phone,
      lead.company,
      lead.website,
      lead.service,
      lead.enquiry,
      lead.budget,
      lead.deadline,
      lead.contact_method,
    ]);
    if (Object.hasOwn(state.keys, key)) {
      if (state.keys[key].payload !== payload)
        throw new Error(
          "This submission key already belongs to different details.",
        );
      return {
        received: true,
        correlation_id: state.keys[key].correlation,
        simulated: true,
      };
    }
    const exact = state.details.find(
      (x) =>
        x.lead.email === lead.email &&
        x.lead.enquiry === lead.enquiry &&
        x.lead.service === lead.service,
    );
    const correlation = uid();
    state.keys[key] = { payload, correlation };
    if (!exact) {
      lead.correlation_id = correlation;
      if (state.rules.probable_duplicates)
        lead.probable_duplicate =
          state.details.find((x) => x.lead.email === lead.email)?.lead.id ||
          null;
      qualify(state, incoming);
      state.details.unshift(incoming);
    }
    return { received: true, correlation_id: correlation, simulated: true };
  }
  if (path === "/admin/leads" && method === "GET") return allLeads();
  if (path === "/admin/runs" && method === "GET") return state.runs;
  if (path === "/admin/messages" && method === "GET")
    return state.details.flatMap((x) =>
      x.messages
        .filter(
          (m) =>
            !["sent", "unknown"].includes(m.state) && m.approval !== "rejected",
        )
        .map((m) => ({ ...m, lead: x.lead })),
    );
  if (path === "/admin/overview") {
    const leads = allLeads();
    return {
      total: leads.length,
      new: leads.filter((x) => x.status === "NEW").length,
      qualified: leads.filter((x) => x.category === "high").length,
      review: leads.filter((x) => x.category === "manual review").length,
      bookings: leads.filter((x) => x.status === "BOOKED").length,
      conversion: Math.round(
        (leads.filter((x) => x.status === "WON").length / leads.length) * 100,
      ),
      failed_runs: state.runs.filter(
        (x) => x.status === "failed" && x.retry_state !== "resolved",
      ).length,
      average_processing_seconds: 0,
      estimated_ai_cost: 0,
      approval_pending: state.details
        .flatMap((x) => x.messages)
        .filter((x) => x.approval === "pending" && x.state === "draft").length,
    };
  }
  if (path === "/admin/settings") {
    if (method === "PUT") {
      for (const key of [
        "budget_weight",
        "service_weight",
        "completeness_weight",
        "timeline_weight",
        "business_weight",
        "geography_weight",
        "spam_penalty",
        "low_budget_cap",
        "high_threshold",
        "medium_threshold",
      ] as const) {
        const max = key.endsWith("weight") ? 50 : 100;
        if (
          !Number.isInteger(data[key]) ||
          Number(data[key]) < 0 ||
          Number(data[key]) > max
        )
          throw new Error("Rule values are outside their allowed range.");
      }
      if (Number(data.high_threshold) <= Number(data.medium_threshold))
        throw new Error("High threshold must exceed medium threshold.");
      if (
        !Array.isArray(data.supported_services) ||
        !data.supported_services.length ||
        data.supported_services.length > 20 ||
        data.supported_services.some(
          (x) => typeof x !== "string" || !x.trim() || x.length > 80,
        )
      )
        throw new Error("Provide between 1 and 20 valid services.");
      if (
        !Array.isArray(data.followup_days) ||
        data.followup_days.length !== 2 ||
        !data.followup_days.every(Number.isInteger) ||
        data.followup_days[0] < 1 ||
        data.followup_days[1] <= data.followup_days[0] ||
        data.followup_days[1] > 90
      )
        throw new Error("Follow-up days must increase between 1 and 90.");
      if (
        data.booking_url &&
        (typeof data.booking_url !== "string" ||
          !data.booking_url.startsWith("https://"))
      )
        throw new Error("Booking URL must use HTTPS.");
      state.rules = { ...state.rules, ...copy(data) } as Rules;
      // Public demos never enable unattended actions or external notifications.
      state.rules.safe_automation = false;
      state.rules.notifications_enabled = false;
    }
    return {
      rules: state.rules,
      demo_defaults: true,
      providers: {
        llm: "browser simulation",
        crm: "browser-only sample records",
        email: "simulated; never sent",
        slack_configured: false,
        orchestration: "simulated; n8n runs in the Docker edition",
      },
    };
  }
  if (path === "/admin/followups/tick" && method === "POST") {
    for (const detail of state.details) {
      cancel(detail);
      for (const step of detail.followups) {
        if (
          step.state !== "scheduled" ||
          Date.parse(step.scheduled_at) > Date.now() ||
          stopped(detail.lead)
        )
          continue;
        if (
          step.position === 2 &&
          !detail.messages.some(
            (x) => x.kind === "followup_1" && x.state === "sent",
          )
        )
          continue;
        draft(detail, `followup_${step.position}`);
        step.state = "pending_approval";
      }
    }
    return { ok: true, simulated: true };
  }
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "admin" && parts[1] === "leads") {
    const detail = state.details.find((x) => x.lead.id === parts[2]);
    if (!detail)
      throw new Error(
        "Lead not found. Reset the demo if its saved data is outdated.",
      );
    if (method === "GET") return detail;
    if (method === "PATCH") {
      if (typeof data.status === "string") {
        if (!statuses.includes(data.status))
          throw new Error("Invalid lead status.");
        detail.lead.status = data.status;
      }
      if (typeof data.owner === "string")
        detail.lead.owner = data.owner.slice(0, 100);
      for (const flag of ["replied", "paused", "opted_out"] as const)
        if (typeof data[flag] === "boolean") detail.lead[flag] = data[flag];
      event(detail, "lead_updated");
      cancel(detail);
      return detail;
    }
    if (parts[3] === "retry" && method === "POST") {
      if (!detail.messages.length) qualify(state, detail);
      event(detail, "processing_checked");
      return { ok: true };
    }
  }
  if (parts[0] === "admin" && parts[1] === "messages") {
    const detail = state.details.find((x) =>
      x.messages.some((m) => m.id === parts[2]),
    );
    const message = detail?.messages.find((x) => x.id === parts[2]);
    if (!detail || !message) throw new Error("Message not found.");
    if (parts[3] === "send" && method === "POST")
      return send(state, detail, message);
    if (["sent", "unknown", "sending"].includes(message.state))
      throw new Error("Delivered or uncertain drafts cannot be changed.");
    if (method === "PATCH") {
      if (
        typeof data.subject !== "string" ||
        !data.subject.trim() ||
        data.subject.length > 300 ||
        typeof data.content !== "string" ||
        !data.content.trim() ||
        data.content.length > 10000
      )
        throw new Error("Provide a subject and response within their limits.");
      message.revisions.push({
        subject: message.subject,
        content: message.content,
        at: stamp(),
      });
      message.subject = data.subject;
      message.content = data.content;
      message.approval = "pending";
      event(detail, "draft_edited");
    } else if (parts[3] === "approve" && method === "POST") {
      if (stopped(detail.lead))
        throw new Error("This lead's sequence is stopped.");
      message.approval = "approved";
      event(detail, "draft_approved");
    } else if (parts[3] === "reject" && method === "POST") {
      message.approval = "rejected";
      event(detail, "draft_rejected");
    } else throw new Error("That action is unavailable in the public demo.");
    return message;
  }
  if (
    parts[0] === "admin" &&
    parts[1] === "runs" &&
    parts[3] === "retry" &&
    method === "POST"
  ) {
    const old = state.runs.find((x) => x.id === parts[2]);
    const detail = state.details.find((x) => x.lead.id === old?.lead_id);
    if (!old || !detail || old.status !== "failed")
      throw new Error("No recoverable run found.");
    if (old.retry_state === "resolved") return { ok: true };
    if (old.workflow === "email") {
      const message = detail.messages.find((x) => x.state === "failed");
      if (message) send(state, detail, message);
    } else if (old.workflow === "intake") qualify(state, detail);
    else {
      detail.crm = {
        state: "synced",
        attempts: (detail.crm?.attempts || 0) + 1,
        error: null,
      };
      run(state, detail, old.workflow);
    }
    old.retry_state = "resolved";
    event(detail, "failure_resolved", { workflow: old.workflow });
    return { ok: true, simulated: true };
  }
  throw new Error(
    "This operation is unavailable in the browser demo. Run the Docker edition for the real backend and n8n.",
  );
}

export async function demoApi<T>(
  path: string,
  method = "GET",
  body?: unknown,
  extra?: Record<string, string>,
): Promise<T> {
  let state: DemoState;
  try {
    const saved = localStorage.getItem(DEMO_STORAGE_KEY);
    state = saved ? JSON.parse(saved) : createDemoState();
    if (
      state.version !== 1 ||
      !Array.isArray(state.details) ||
      !Array.isArray(state.runs)
    )
      throw new Error("Invalid demo data");
  } catch {
    state = createDemoState();
  }
  // Failed operations do not partially persist changes.
  const result = handleDemoRequest(state, path, method, body, extra);
  try {
    localStorage.setItem(DEMO_STORAGE_KEY, JSON.stringify(state));
  } catch {
    throw new Error(
      "Browser storage is unavailable or full. Allow site storage, or reset the demo.",
    );
  }
  return copy(result) as T;
}
