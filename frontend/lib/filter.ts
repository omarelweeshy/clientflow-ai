import type { Lead } from "./types";
export function filterLeads(
  leads: Lead[],
  filters: {
    search: string;
    status: string;
    category: string;
    source: string;
    failuresOnly: boolean;
  },
  failedIds: Set<string>,
): Lead[] {
  const search = filters.search.trim().toLocaleLowerCase();
  return leads.filter(
    (lead) =>
      `${lead.name} ${lead.email} ${lead.company} ${lead.service}`
        .toLocaleLowerCase()
        .includes(search) &&
      (filters.status === "all" || lead.status === filters.status) &&
      (filters.category === "all" || lead.category === filters.category) &&
      (filters.source === "all" || lead.source === filters.source) &&
      (!filters.failuresOnly || failedIds.has(lead.id)),
  );
}
