/* Sets data-theme before first paint so the page never flashes the wrong appearance (FR-024).
   Same-origin script, allowed by the content security policy without 'unsafe-inline'.
   The key and values are the contract in specs/003-modern-frontend-ui/contracts/ui-contracts.md §3. */
(function () {
  try {
    var saved = window.localStorage.getItem("mmi.ui.appearance");
    var dark = saved === "dark" || (saved !== "light" && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  } catch {
    document.documentElement.setAttribute("data-theme", "light");
  }
})();
