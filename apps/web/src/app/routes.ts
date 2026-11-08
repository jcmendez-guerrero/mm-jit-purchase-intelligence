import type { IconName } from "../ui/icons/paths";

/**
 * Route table and navigation registry (contracts/ui-contracts.md §1, data-model.md).
 * Single source for the navigation rail, the quick-jump palette and the route table.
 * `roles` only decides what is offered; the backend remains the authority on permissions.
 */

export type GroupId = "seguimiento" | "compras" | "configuracion" | "administracion";

export interface NavItem {
  id: string;
  path: string;
  labelKey: string;
  descriptionKey: string;
  group: GroupId;
  icon: IconName;
  /** Empty means any signed-in role. */
  roles: string[];
  order: number;
}

export interface NavGroup {
  id: GroupId;
  labelKey: string;
}

export const GROUPS: NavGroup[] = [
  { id: "seguimiento", labelKey: "nav.group.seguimiento" },
  { id: "compras", labelKey: "nav.group.compras" },
  { id: "configuracion", labelKey: "nav.group.configuracion" },
  { id: "administracion", labelKey: "nav.group.administracion" },
];

export const DEFAULT_PATH = "/panel";

export const NAV_ITEMS: NavItem[] = [
  { id: "panel", path: "/panel", labelKey: "nav.dashboard", descriptionKey: "nav.desc.dashboard", group: "seguimiento", icon: "dashboard", roles: [], order: 1 },
  { id: "calidad", path: "/calidad", labelKey: "nav.quality", descriptionKey: "nav.desc.quality", group: "seguimiento", icon: "quality", roles: [], order: 2 },
  { id: "propuestas", path: "/propuestas", labelKey: "nav.proposals", descriptionKey: "nav.desc.proposals", group: "compras", icon: "proposals", roles: [], order: 1 },
  { id: "escenarios", path: "/escenarios", labelKey: "nav.scenarios", descriptionKey: "nav.desc.scenarios", group: "compras", icon: "scenarios", roles: [], order: 2 },
  { id: "costes", path: "/costes", labelKey: "nav.costs", descriptionKey: "nav.desc.costs", group: "compras", icon: "costs", roles: [], order: 3 },
  { id: "proveedores", path: "/proveedores", labelKey: "nav.suppliers", descriptionKey: "nav.desc.suppliers", group: "configuracion", icon: "suppliers", roles: [], order: 1 },
  { id: "importaciones", path: "/importaciones", labelKey: "nav.imports", descriptionKey: "nav.desc.imports", group: "configuracion", icon: "imports", roles: [], order: 2 },
  { id: "configuracion", path: "/configuracion", labelKey: "nav.config", descriptionKey: "nav.desc.config", group: "configuracion", icon: "config", roles: [], order: 3 },
  { id: "administracion", path: "/administracion", labelKey: "nav.admin", descriptionKey: "nav.desc.admin", group: "administracion", icon: "admin", roles: ["admin"], order: 1 },
];

export function canSee(item: NavItem, roles: readonly string[]): boolean {
  return item.roles.length === 0 || item.roles.some((r) => roles.includes(r));
}

export function itemsFor(roles: readonly string[]): NavItem[] {
  return NAV_ITEMS.filter((i) => canSee(i, roles));
}

export function groupedItems(roles: readonly string[]): Array<NavGroup & { items: NavItem[] }> {
  const visible = itemsFor(roles);
  return GROUPS.map((g) => ({ ...g, items: visible.filter((i) => i.group === g.id).sort((a, b) => a.order - b.order) })).filter((g) => g.items.length > 0);
}

export function findItem(pathname: string): NavItem | undefined {
  return NAV_ITEMS.find((i) => i.path === pathname);
}

/** Lower-case and strip accents so "configuracion" finds "Configuración". */
export function normalizeText(text: string): string {
  return text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().trim();
}
