/**
 * In-repo icon set (T011): simple strokes on a 24 px grid, drawn for this project, rendered with currentColor.
 * Each value is the inner SVG markup; the wrapper in Icon.tsx adds size, stroke and accessibility attributes.
 */
export const ICON_PATHS = {
  dashboard: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  quality: '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M9 12l2.2 2.2L15.5 10"/>',
  proposals: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1M9 11h6M9 15h6"/>',
  scenarios: '<path d="M6 4v6a4 4 0 004 4h4a4 4 0 014 4v2"/><circle cx="6" cy="4" r="1.6"/><circle cx="18" cy="20" r="1.6"/><path d="M6 14v6"/>',
  costs: '<path d="M16.5 7.5A5.5 5.5 0 0010 6c-3 0-5 2.5-5 6s2 6 5 6a5.5 5.5 0 006.5-1.5M3.5 10.5h9M3.5 13.5h9"/>',
  suppliers: '<path d="M3 7h11v9H3zM14 10h4l3 3v3h-7z"/><circle cx="7" cy="18" r="1.8"/><circle cx="17" cy="18" r="1.8"/>',
  imports: '<path d="M12 16V4M7.5 8.5L12 4l4.5 4.5M4 15v4h16v-4"/>',
  config: '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
  admin: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c.8-3.6 3.6-5.5 7-5.5s6.2 1.9 7 5.5"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6L7 7M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  warning: '<path d="M12 4l9 16H3z"/><path d="M12 10v4.5M12 17.2v.3"/>',
  error: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.2v.3"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.8v.3"/>',
  user: '<circle cx="12" cy="9" r="3.5"/><path d="M5 20c.8-3.6 3.6-5.5 7-5.5s6.2 1.9 7 5.5"/>',
  logout: '<path d="M10 4H5v16h5M15 8l4 4-4 4M19 12H9"/>',
  download: '<path d="M12 4v12M7.5 11.5L12 16l4.5-4.5M4 19h16"/>',
  filter: '<path d="M4 5h16l-6 7.5V19l-4-2v-4.5z"/>',
  "chevron-down": '<path d="M6 9l6 6 6-6"/>',
  "chevron-up": '<path d="M6 15l6-6 6 6"/>',
  "chevron-left": '<path d="M15 6l-6 6 6 6"/>',
  "chevron-right": '<path d="M9 6l6 6-6 6"/>',
  sort: '<path d="M8 5v14M5 16l3 3 3-3M16 19V5M13 8l3-3 3 3"/>',
  cross: '<path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z"/>',
} as const;

export type IconName = keyof typeof ICON_PATHS;

export const ICON_NAMES = Object.keys(ICON_PATHS) as IconName[];
