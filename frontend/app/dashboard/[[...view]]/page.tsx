import Dashboard from "@/components/Dashboard";
export default async function Page({
  params,
}: {
  params: Promise<{ view?: string[] }>;
}) {
  const { view } = await params;
  return <Dashboard view={view || []} />;
}
