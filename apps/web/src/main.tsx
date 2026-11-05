import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import "./i18n";
import "./index.css";

const container = document.getElementById("root");
if (container) {
  createRoot(container).render(<App />);
}
