"use client";
import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { DEMO_STORAGE_KEY } from "@/lib/demo-api";

export default function DemoBanner() {
  const [confirmReset, setConfirmReset] = useState(false);
  const banner = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!banner.current) return;
    const observer = new ResizeObserver(([entry]) =>
      document.documentElement.style.setProperty(
        "--demo-banner-height",
        `${entry.target.getBoundingClientRect().height}px`,
      ),
    );
    observer.observe(banner.current);
    return () => observer.disconnect();
  }, []);
  if (process.env.NEXT_PUBLIC_DEMO_MODE !== "true") return null;
  return (
    <aside
      ref={banner}
      className="demo-banner"
      aria-label="Public demo information"
    >
      <div>
        <strong>Interactive portfolio demo</strong>
        <span>
          Fictional data. Changes stay in this browser. AI, email and n8n
          activity are simulated.
        </span>
      </div>
      <div className="demo-banner-actions">
        <Link
          href="https://github.com/omarelweeshy/clientflow-ai"
          target="_blank"
          rel="noreferrer"
        >
          Source & architecture ↗
        </Link>
        {confirmReset ? (
          <>
            <button
              onClick={() => {
                localStorage.removeItem(DEMO_STORAGE_KEY);
                window.location.assign(
                  new URL("/dashboard", window.location.origin).href,
                );
              }}
            >
              Confirm reset
            </button>
            <button onClick={() => setConfirmReset(false)}>Cancel</button>
          </>
        ) : (
          <button onClick={() => setConfirmReset(true)}>Reset demo</button>
        )}
      </div>
    </aside>
  );
}
