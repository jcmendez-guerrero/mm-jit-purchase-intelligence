import { createRoot } from "react-dom/client";
import es from "./i18n/es-ES.json";

// Placeholder shell; the real SPA (routing, i18next, screens) is built in task T113 onward.
createRoot(document.getElementById("root")!).render(
  <main>
    <h1>{es["app.title"]}</h1>
    <p>{es["app.placeholder"]}</p>
  </main>,
);
