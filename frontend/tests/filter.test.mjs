import { test } from "node:test";
import assert from "node:assert/strict";
import { filterLeads } from "../lib/filter.ts";
const leads = [
  {
    id: "1",
    name: "Nadia Farouk",
    email: "nadia@example.com",
    company: "Atlas Studio",
    service: "AI automation",
    status: "QUALIFIED",
    category: "high",
    source: "portfolio",
  },
  {
    id: "2",
    name: "James Porter",
    email: "james@example.com",
    company: "",
    service: "Internal tool",
    status: "NEEDS_REVIEW",
    category: "manual review",
    source: "referral",
  },
];
const defaults = {
  search: "",
  status: "all",
  category: "all",
  source: "all",
  failuresOnly: false,
};
test("search tolerates casing and surrounding whitespace", () => {
  assert.deepEqual(
    filterLeads(leads, { ...defaults, search: " ATLAS " }, new Set()).map(
      (x) => x.id,
    ),
    ["1"],
  );
  assert.equal(
    filterLeads(leads, { ...defaults, search: "JAMES@" }, new Set()).length,
    1,
  );
});
test("status, category, source and unresolved failure filters compose", () => {
  assert.deepEqual(
    filterLeads(
      leads,
      {
        ...defaults,
        status: "NEEDS_REVIEW",
        category: "manual review",
        source: "referral",
        failuresOnly: true,
      },
      new Set(["2"]),
    ).map((x) => x.id),
    ["2"],
  );
  assert.equal(
    filterLeads(
      leads,
      { ...defaults, source: "portfolio", failuresOnly: true },
      new Set(["2"]),
    ).length,
    0,
  );
});
test("search text is treated literally and input order is preserved", () => {
  assert.equal(
    filterLeads(leads, { ...defaults, search: "<script>" }, new Set()).length,
    0,
  );
  assert.deepEqual(filterLeads(leads, defaults, new Set()), leads);
});
