import { describe, expect, it } from "vitest";
import esJson from "../../src/i18n/es-ES.json";
import { GROUPS, NAV_ITEMS, groupedItems, itemsFor } from "../../src/app/routes";

// T010 (feature 012, SC-001): the screens offered to each role, pinned in one place.

const catalogue = esJson as Record<string, string>;
const COMMON = ["panel", "calidad", "propuestas", "escenarios", "costes", "proveedores", "importaciones", "configuracion"];

const MATRIX: Array<{ role: string; features: string[]; offered: string[] }> = [
  { role: "viewer", features: [], offered: COMMON },
  { role: "viewer", features: ["localLoad"], offered: COMMON },
  { role: "buyer", features: [], offered: COMMON },
  { role: "buyer", features: ["localLoad"], offered: [...COMMON, "carga-local"] },
  { role: "approver", features: [], offered: COMMON },
  { role: "approver", features: ["localLoad"], offered: COMMON },
  { role: "admin", features: [], offered: [...COMMON, "administracion"] },
  { role: "admin", features: ["localLoad"], offered: [...COMMON, "carga-local", "administracion"] },
];

describe("navigation offered per role", () => {
  it.each(MATRIX)("$role with features [$features] is offered exactly its screens", ({ role, features, offered }) => {
    const ids = itemsFor([role], features).map((i) => i.id);
    expect([...ids].sort()).toEqual([...offered].sort());
    const grouped = groupedItems([role], features).flatMap((g) => g.items.map((i) => i.id));
    expect([...grouped].sort()).toEqual([...offered].sort());
  });

  it("a person with no known role is offered only the screens open to any signed-in role", () => {
    const ids = itemsFor([], []).map((i) => i.id).sort();
    expect(ids).toEqual([...COMMON].sort());
  });

  it("the union of all roles covers every registered screen", () => {
    const all = new Set(MATRIX.flatMap((m) => m.offered));
    expect([...all].sort()).toEqual(NAV_ITEMS.map((i) => i.id).sort());
  });

  it("every screen has a Spanish label and description, and every group a Spanish title", () => {
    for (const i of NAV_ITEMS) {
      expect(catalogue[i.labelKey], i.labelKey).toBeTruthy();
      expect(catalogue[i.descriptionKey], i.descriptionKey).toBeTruthy();
    }
    for (const g of GROUPS) expect(catalogue[g.labelKey], g.labelKey).toBeTruthy();
  });

  it("order is unique inside each group", () => {
    for (const g of GROUPS) {
      const orders = NAV_ITEMS.filter((i) => i.group === g.id).map((i) => i.order);
      expect(new Set(orders).size, g.id).toBe(orders.length);
    }
  });
});
