import { test } from "node:test";
import assert from "node:assert/strict";
import { createDemoState, handleDemoRequest } from "../lib/demo-api.ts";

const request = (state, path, method = "GET", body, extra) =>
  handleDemoRequest(state, path, method, body, extra);
const intake = {
  name: "Fictional Reviewer",
  email: "reviewer@example.com",
  company: "Demo Studio",
  service: "AI automation",
  enquiry:
    "We need an enquiry workflow with a clear approval step and audit trail.",
  budget: "2000-5000",
  consent: true,
  deadline: "2027-01-20",
};

test("demo sessions start with independent fictional records", () => {
  const a = createDemoState(),
    b = createDemoState();
  a.details[0].lead.name = "Changed";
  assert.notEqual(a.details[0].lead.name, b.details[0].lead.name);
  assert.ok(b.details.every((x) => x.lead.email.endsWith("@example.com")));
});
test("intake has stable receipts and rejects changed idempotency payloads", () => {
  const s = createDemoState(),
    headers = { "Idempotency-Key": "reviewer-intake-key" };
  const first = request(s, "/public/intake", "POST", intake, headers);
  assert.deepEqual(
    request(s, "/public/intake", "POST", intake, headers),
    first,
  );
  assert.equal(
    s.details.filter((x) => x.lead.email === intake.email).length,
    1,
  );
  assert.throws(
    () =>
      request(
        s,
        "/public/intake",
        "POST",
        {
          ...intake,
          enquiry: "A different request with enough detail to be valid.",
        },
        headers,
      ),
    /different details/,
  );
});
test("editing resets approval; delivery is idempotent; replies cancel follow-ups", () => {
  const s = createDemoState(),
    d = s.details[0],
    m = d.messages[0],
    path = `/admin/messages/${m.id}`;
  assert.throws(() => request(s, `${path}/send`, "POST"), /approve/);
  request(s, `${path}/approve`, "POST");
  request(s, path, "PATCH", {
    subject: "Edited subject",
    content: "Edited fictional response.",
  });
  assert.equal(m.approval, "pending");
  assert.equal(m.revisions.length, 1);
  request(s, `${path}/approve`, "POST");
  request(s, `${path}/send`, "POST");
  request(s, `${path}/send`, "POST");
  assert.equal(s.deliveries.filter((x) => x === m.id).length, 1);
  assert.equal(d.followups.length, 2);
  request(s, `/admin/leads/${d.lead.id}`, "PATCH", { replied: true });
  assert.ok(d.followups.every((x) => x.state === "cancelled"));
});
test("follow-up checks create one draft; final step waits for first delivery", () => {
  const s = createDemoState(),
    d = s.details.find((x) => x.lead.name === "Maya Chen");
  d.followups.forEach((x) => (x.scheduled_at = "2020-01-01T00:00:00Z"));
  request(s, "/admin/followups/tick", "POST");
  request(s, "/admin/followups/tick", "POST");
  assert.equal(d.messages.filter((x) => x.kind === "followup_1").length, 1);
  assert.equal(d.messages.filter((x) => x.kind === "followup_2").length, 0);
  const message = d.messages.find((x) => x.kind === "followup_1");
  request(s, `/admin/messages/${message.id}/approve`, "POST");
  request(s, `/admin/messages/${message.id}/send`, "POST");
  request(s, "/admin/followups/tick", "POST");
  assert.equal(d.messages.filter((x) => x.kind === "followup_2").length, 1);
});
test("failure retry records recovery and stop conditions block delivery", () => {
  const s = createDemoState(),
    failed = s.runs.find(
      (x) => x.status === "failed" && x.workflow === "email",
    );
  const d = s.details.find((x) => x.lead.id === failed.lead_id);
  request(s, `/admin/leads/${d.lead.id}`, "PATCH", { opted_out: true });
  assert.throws(
    () => request(s, `/admin/runs/${failed.id}/retry`, "POST"),
    /blocked/,
  );
  assert.equal(failed.retry_state, "available");
  request(s, `/admin/leads/${d.lead.id}`, "PATCH", { opted_out: false });
  request(s, `/admin/runs/${failed.id}/retry`, "POST");
  assert.equal(failed.retry_state, "resolved");
});
test("simulation fails closed for unimplemented and automation routes", () => {
  assert.throws(
    () => request(createDemoState(), "/automation/email", "POST"),
    /unavailable/,
  );
});
