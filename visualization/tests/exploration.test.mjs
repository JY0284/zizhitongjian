import test from "node:test";
import assert from "node:assert/strict";
import {
  timelineGroups,
  timelineBuckets,
  clampYearWindow,
  networkSubset,
  eventsInYears,
  readFilterDraft,
  roleSearchNames,
} from "../src/utils/exploration.ts";
const event = (id, year, values = {}) => ({
  id,
  timeNumeric: year,
  name: id,
  description: "",
  participants: [],
  location: null,
  ...values,
});
test("timeline sorts known dates and keeps undated records separate", () => {
  const events = [
    event("late", -300),
    event("unknown", null),
    event("early", -400),
  ];
  const result = timelineGroups(events, "");
  assert.deepEqual(
    result.years.map(([year]) => year),
    [-400, -300],
  );
  assert.deepEqual(
    result.undated.map((item) => item.id),
    ["unknown"],
  );
  assert.equal(events[0].id, "late");
});
test("event search includes places, participants and exact aliases, with trimmed queries", () => {
  const events = [
    event("变法", -350, { participants: ["卫鞅"], location: "秦国" }),
    event("other", null),
  ];
  assert.equal(timelineGroups(events, " 秦国 ").matches.length, 1);
  assert.equal(
    timelineGroups(events, "商鞅", [roleSearchNames("公孙鞅", ["商君"])])
      .matches[0].id,
    "变法",
  );
  assert.equal(timelineGroups(events, "不存在").matches.length, 0);
});
const nodes = Array.from({ length: 60 }, (_, i) => ({
  id: String(i),
  appearances: i,
  power: i % 2 ? "秦" : "赵",
}));
const links = [
  { source: "59", target: "0" },
  { source: "59", target: "58" },
  { source: "0", target: "1" },
];
test("core network caps nodes, preserves source arrays and removes dangling edges", () => {
  const original = structuredClone({ nodes, links });
  const core = networkSubset(nodes, links, "core", null, "all");
  assert.equal(core.nodes.length, 50);
  assert.equal(core.nodes[0].id, "59");
  assert.deepEqual(core.links, [links[1]]);
  assert.deepEqual({ nodes, links }, original);
});
test("person focus includes direct neighbors across powers, but not second-degree nodes", () => {
  const local = networkSubset(nodes, links, "person", "59", "秦");
  assert.deepEqual(
    new Set(local.nodes.map((node) => node.id)),
    new Set(["59", "58", "0"]),
  );
  assert.equal(local.links.length, 2);
  const filtered = networkSubset(nodes, links, "all", null, "秦");
  assert.equal(filtered.nodes.length, 30);
  assert.equal(filtered.links.length, 0);
});
test("filter drafts preserve BCE dates and open-ended bounds until explicitly applied", () => {
  assert.deepEqual(readFilterDraft(["1", "5"], [" -403 ", "-300"], 294), {
    juans: [1, 5],
    years: [-403, -300],
  });
  assert.deepEqual(readFilterDraft(["1", "5"], ["", ""], 294), {
    juans: [1, 5],
    years: [null, null],
  });
  assert.deepEqual(readFilterDraft(["1", "5"], ["", "-300"], 294).years, [
    null,
    -300,
  ]);
});
test("invalid and reversed ranges return actionable errors instead of silently changing input", () => {
  for (const [juans, years] of [
    [
      ["", "5"],
      ["", ""],
    ],
    [
      ["0", "5"],
      ["", ""],
    ],
    [
      ["1", "295"],
      ["", ""],
    ],
    [
      ["5", "1"],
      ["", ""],
    ],
    [
      ["1", "5"],
      ["-300", "-400"],
    ],
    [
      ["1", "5"],
      ["NaN", ""],
    ],
    [
      ["1", "5"],
      ["9999999999999999999", ""],
    ],
    [
      ["1", "5"],
      ["1.5", ""],
    ],
  ]) {
    assert.equal(typeof readFilterDraft(juans, years, 294).error, "string");
  }
});

test("year filters exclude undated events and respect inclusive single-year bounds", () => {
  const records = [event("a", -403), event("b", -300), event("unknown", null)];
  assert.equal(eventsInYears(records, [null, null]), records);
  assert.deepEqual(
    eventsInYears(records, [-403, -403]).map((item) => item.id),
    ["a"],
  );
  assert.deepEqual(
    eventsInYears(records, [null, -350]).map((item) => item.id),
    ["a"],
  );
  assert.deepEqual(
    eventsInYears(records, [-350, null]).map((item) => item.id),
    ["b"],
  );
});

test("overview buckets conserve events across adjacent BCE boundaries and zoom levels", () => {
  const years = timelineGroups(
    Array.from({ length: 80 }, (_, i) =>
      event(String(i), -440 + Math.floor(i / 2)),
    ),
    "",
  ).years;
  for (const capacity of [1, 8, 40, 100]) {
    const buckets = timelineBuckets(years, -440, -400, capacity);
    assert.equal(
      buckets.reduce((sum, bucket) => sum + bucket.count, 0),
      80,
    );
    assert.equal(new Set(buckets.flatMap((bucket) => bucket.years)).size, 40);
    assert.ok(buckets.length <= capacity);
  }
  assert.equal(timelineBuckets(years, -420, -419, 40)[0].count, 2);
  assert.deepEqual(timelineBuckets(years, -399, -390, 40), []);
});

test("overview zoom and pan stay within the complete range, including a single year", () => {
  assert.deepEqual(clampYearWindow(-500, 20, -403, -249), [-403, -383]);
  assert.deepEqual(clampYearWindow(-250, 20, -403, -249), [-269, -249]);
  assert.deepEqual(clampYearWindow(-350, 999, -403, -249), [-403, -249]);
  assert.deepEqual(clampYearWindow(-300, 0.2, -300, -299), [-300, -299]);
});

test("network density excludes faint nodes and dangling edges without hiding focused neighbors", () => {
  const sparse = networkSubset(nodes, links, "all", null, "all", 58);
  assert.ok(sparse.nodes.every((node) => node.appearances >= 58));
  assert.equal(sparse.links.length, 1);
  const focused = networkSubset(nodes, links, "person", "59", "all", 58);
  assert.equal(focused.nodes.length, 3);
  assert.equal(focused.links.length, 2);
});
