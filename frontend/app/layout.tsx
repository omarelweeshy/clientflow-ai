import type { Metadata } from "next";
import "./globals.css";
import DemoBanner from "@/components/DemoBanner";
export const metadata: Metadata = {
  title: "ClientFlow AI | Operations",
  description:
    "From first enquiry to the next opportunity. A human-controlled automation workspace.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        className={
          process.env.NEXT_PUBLIC_DEMO_MODE === "true"
            ? "demo-active"
            : undefined
        }
      >
        <DemoBanner />
        {children}
      </body>
    </html>
  );
}
