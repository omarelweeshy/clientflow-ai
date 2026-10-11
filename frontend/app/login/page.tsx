"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Workflow, ShieldCheck } from "lucide-react";
import { api, setCsrf } from "@/lib/api";
const publicDemo = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
export default function Login() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <main className="auth-page">
      <div className="auth-story">
        <Link className="brand" href="/intake">
          <Workflow /> ClientFlow <span>AI</span>
        </Link>
        <div>
          <p className="eyebrow">YOUR OPERATIONS, CONNECTED</p>
          <h1>
            Less chasing.
            <br /> More momentum.
          </h1>
          <p>
            Every enquiry, decision and next step.
            <br />
            One clear line from interest to opportunity.
          </p>
        </div>
        <small>INDEPENDENT PRODUCT · BUILT FOR REAL WORK</small>
      </div>
      <div className="auth-form">
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              const data = await api<{ csrf: string }>("/auth/login", "POST", {
                password,
              });
              setCsrf(data.csrf);
              router.replace("/dashboard");
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <ShieldCheck className="auth-icon" />
          <p className="eyebrow">
            {publicDemo ? "EXPLORE THE PRODUCT" : "PRIVATE WORKSPACE"}
          </p>
          <h2>{publicDemo ? "Try the workflow." : "Welcome back."}</h2>
          <p className="muted">
            {publicDemo
              ? "Explore fictional enquiries, approve a response and simulate delivery. No account or real email required."
              : "Sign in to review and control your automations."}
          </p>
          {!publicDemo && (
            <>
              <label htmlFor="password">Administrator password</label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </>
          )}
          {error && (
            <p role="alert" className="alert error">
              {error}
            </p>
          )}
          <button className="button primary full" disabled={busy}>
            {busy ? "Opening…" : publicDemo ? "Explore demo" : "Open workspace"}
            <ArrowRight size={18} />
          </button>
          <Link href="/intake" className="text-link">
            View public enquiry form ↗
          </Link>
        </form>
      </div>
    </main>
  );
}
