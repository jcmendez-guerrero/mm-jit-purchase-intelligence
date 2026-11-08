import { describe, expect, it } from "vitest";
import esJson from "../../src/i18n/es-ES.json";
import { GROUPS, NAV_ITEMS, groupedItems, itemsFor, normalizeText } from "../../src/app/routes";
import { ICON_NAMES } from "../../src/ui/icons/paths";

/** T017 — route/navigation registry (contracts/ui-contracts.md §1, data-model.md "Navigation item"). */

const catalogue = esJson as Record<string, string>;
const KNOWN_ROLES = ["viewer", "buyer", "approver", "admin"];

describe("navigation registry", () => {
  it("has unique ids and paths, and paths equal ids with a leading slash", () => {
    expect(new Set(NAV_ITEMS.map((i) => i.id)).size).toBe(NAV_ITEMS.length);
    expect(new Set(NAV_ITEMS.map((i) => i.path)).size).toBe(NAV_ITEMS.length);
    for (const i of NAV_ITEMS) expect(i.path).toBe(`/${i.id}`);
  });

  it("lists the nine screens of the contract", () => {
    expect(NAV_ITEMS.map((i) => i.id).sort()).toEqual(
      ["administracion", "calidad", "configuracion", "costes", "escenarios", "importaciones", "panel", "propuestas", "proveedores"].sort(),
    );
  });

  it("resolves every label, description and group label key in es-ES.json", () => {
    for (const i of NAV_ITEMS) {
      expect(catalogue[i.labelKey], i.labelKey).toBeTruthy();
      expect(catalogue[i.descriptionKey], i.descriptionKey).toBeTruthy();
    }
    for (const g of GROUPS) expect(catalogue[g.labelKey], g.labelKey).toBeTruthy();
  });

  it("uses only icons that exist", () => {
    for (const i of NAV_ITEMS) expect(ICON_NAMES, i.id).toContain(i.icon);
  });

  it("has every group non-empty, in the documented order", () => {
    expect(GROUPS.map((g) => g.id)).toEqual(["seguimiento", "compras", "configuracion", "administracion"]);
    for (const g of GROUPS) expect(NAV_ITEMS.some((i) => i.group === g.id), g.id).toBe(true);
  });

  it("references only known roles, and administration requires admin", () => {
    for (const i of NAV_ITEMS) for (const r of i.roles) expect(KNOWN_ROLES).toContain(r);
    expect(NAV_ITEMS.find((i) => i.id === "administracion")?.roles).toEqual(["admin"]);
  });

  it("offers only permitted sections per role", () => {
    expect(itemsFor(["viewer"]).map((i) => i.id)).not.toContain("administracion");
    expect(itemsFor(["viewer", "buyer"]).map((i) => i.id)).not.toContain("administracion");
    expect(itemsFor(["viewer", "admin"]).map((i) => i.id)).toContain("administracion");
    expect(itemsFor([]).length).toBeGreaterThan(0);
  });

  it("groups visible items in order and omits empty groups", () => {
    const viewer = groupedItems(["viewer"]);
    expect(viewer.map((g) => g.id)).toEqual(["seguimiento", "compras", "configuracion"]);
    expect(groupedItems(["admin"]).map((g) => g.id)).toContain("administracion");
    for (const g of viewer) expect(g.items.length).toBeGreaterThan(0);
  });

  it("normalises text for accent- and case-insensitive search", () => {
    expect(normalizeText("Configuración")).toBe("configuracion");
    expect(normalizeText("PANEL")).toBe("panel");
  });
});
