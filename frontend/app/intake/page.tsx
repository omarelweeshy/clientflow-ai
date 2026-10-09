"use client";
import { useRef, useState, useEffect } from "react";
import Link from "next/link";
import { ArrowRight, Check, Workflow, LockKeyhole } from "lucide-react";
import { api } from "@/lib/api";
const defaultServices = [
  "AI automation",
  "Workflow integration",
  "Dashboard development",
  "Document intelligence",
  "Custom internal tool",
  "Other",
];
export default function Intake() {
  const [services, setServices] = useState(defaultServices);
  useEffect(() => {
    api<{services: string[]}>("/public/config").then(data => setServices(data.services)).catch(() => {});
  }, []);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [receipt, setReceipt] = useState("");
  const submission = useRef<{
    key: string;
    correlation: string;
    payload: string;
  } | null>(null);
  return (
    <main className="intake-page">
      <header className="public-header">
        <Link className="brand dark" href="/intake">
          <Workflow /> ClientFlow <span>AI</span>
        </Link>
        <Link href="/login">
          Workspace <ArrowRight size={16} />
        </Link>
      </header>
      <div className="intake-grid">
        <section className="intake-story">
          <p className="eyebrow">LET’S MAKE WORK FLOW</p>
          <h1>
            A good project
            <br />{" "}
            starts with a<br />{" "}
            <em>clear conversation.</em>
          </h1>
          <p>
            Tell us what you want to build or improve. We’ll review your needs
            and get back to you with a thoughtful next step.
          </p>
          <div className="intake-steps">
            <div>
              <span>01</span>
              <p>
                <b>Share the context</b>
                <small>Your goals, constraints and the work ahead.</small>
              </p>
            </div>
            <div>
              <span>02</span>
              <p>
                <b>We connect the dots</b>
                <small>A structured review, with a human in control.</small>
              </p>
            </div>
            <div>
              <span>03</span>
              <p>
                <b>Decide the next step</b>
                <small>Clarify scope or book a discovery conversation.</small>
              </p>
            </div>
          </div>
          <p className="privacy">
            <LockKeyhole size={16} /> Used only to respond to your project
            enquiry.
          </p>
        </section>
        <section className="intake-card">
          {receipt ? (
            <div className="success-state">
              <span className="success-icon">
                <Check size={32} />
              </span>
              <p className="eyebrow">ENQUIRY RECEIVED</p>
              <h2>It’s in good hands.</h2>
              <p>
                Your enquiry has been saved. We’ll review the details before
                responding.
              </p>
              <small>Reference: {receipt}</small>
              <button
                className="button"
                onClick={() => {
                  setReceipt("");
                  submission.current = null;
                }}
              >
                Start another enquiry
              </button>
            </div>
          ) : (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const data = new FormData(e.currentTarget);
                const payload = {
                  name: data.get("name"),
                  email: data.get("email"),
                  company: data.get("company"),
                  website: data.get("website"),
                  service: data.get("service"),
                  enquiry: data.get("enquiry"),
                  budget: data.get("budget"),
                  deadline: data.get("deadline"),
                  contact_method: data.get("contact_method"),
                  phone: data.get("phone"),
                  consent: data.get("consent") === "on",
                  honeypot: data.get("honeypot"),
                };
                const encoded = JSON.stringify(payload);
                if (
                  !submission.current ||
                  submission.current.payload !== encoded
                )
                  submission.current = {
                    key: crypto.randomUUID(),
                    correlation: crypto.randomUUID(),
                    payload: encoded,
                  };
                setBusy(true);
                setError("");
                try {
                  const result = await api<{ correlation_id: string }>(
                    "/public/intake",
                    "POST",
                    payload,
                    {
                      "Idempotency-Key": submission.current.key,
                      "X-Correlation-ID": submission.current.correlation,
                    },
                  );
                  setReceipt(result.correlation_id);
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              <div className="section-heading">
                <div>
                  <h2>Tell us about your project</h2>
                  <p className="muted">
                    A few details now. A better conversation next.
                  </p>
                </div>
                <span className="badge neutral">~3 MIN</span>
              </div>
              <div className="form-grid">
                <label>
                  Full name <span>*</span>
                  <input
                    name="name"
                    autoComplete="name"
                    placeholder="Your name"
                    minLength={2}
                    maxLength={120}
                    required
                  />
                </label>
                <label>
                  Email <span>*</span>
                  <input
                    name="email"
                    type="email"
                    autoComplete="email"
                    placeholder="you@company.com"
                    required
                  />
                </label>
                <label>
                  Company
                  <input
                    name="company"
                    autoComplete="organization"
                    placeholder="Company or organization"
                    maxLength={160}
                  />
                </label>
                <label>
                  Website
                  <input
                    name="website"
                    type="url"
                    placeholder="https://"
                    maxLength={500}
                  />
                </label>
                <label className="span-2">
                  What can we help with? <span>*</span>
                  <select name="service" required>
                    <option value="">Select a service</option>
                    {services.map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                </label>
                <label className="span-2">
                  Describe your project <span>*</span>
                  <textarea
                    name="enquiry"
                    rows={5}
                    placeholder="What would you like to achieve? What is happening today, and what should change?"
                    minLength={20}
                    maxLength={5000}
                    required
                  />
                </label>
                <label>
                  Budget range
                  <select name="budget">
                    <option value="unspecified">Not sure yet</option>
                    <option value="under-500">Under $500</option>
                    <option value="500-2000">$500 – $2,000</option>
                    <option value="2000-5000">$2,000 – $5,000</option>
                    <option value="5000-plus">$5,000+</option>
                  </select>
                </label>
                <label>
                  Desired deadline
                  <input name="deadline" type="date" />
                </label>
                <label>
                  Preferred contact
                  <select name="contact_method">
                    <option value="email">Email</option>
                    <option value="phone">Phone</option>
                  </select>
                </label>
                <label>
                  Phone
                  <input
                    name="phone"
                    type="tel"
                    autoComplete="tel"
                    maxLength={40}
                    placeholder="If you prefer a call"
                  />
                </label>
              </div>
              <div className="honeypot" aria-hidden="true">
                <label>
                  Leave empty
                  <input name="honeypot" tabIndex={-1} autoComplete="off" />
                </label>
              </div>
              <label className="check-label">
                <input name="consent" type="checkbox" required />{" "}
                <span>
                  I agree to be contacted about this enquiry. I can opt out of
                  follow-ups at any time.
                </span>
              </label>
              {error && (
                <p className="alert error" role="alert">
                  {error}
                </p>
              )}
              <button className="button primary full" disabled={busy}>
                {busy ? "Saving your enquiry…" : "Send project enquiry"}
                <ArrowRight size={18} />
              </button>
              <p className="form-note">
                Your enquiry stays in a controlled workflow. Follow-ups can be
                stopped at any time.
              </p>
            </form>
          )}
        </section>
      </div>
      <footer className="public-footer">
        ClientFlow AI · Independent portfolio & internal-operations product
      </footer>
    </main>
  );
}
