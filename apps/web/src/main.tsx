import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import { App } from "./app/App";
import "./i18n";
import "./index.css";
import { startThemeSync } from "./ui/theme";

// A data router, so forms can ask before an in-app navigation discards unsaved edits (FR-017).
const router = createBrowserRouter([{ path: "*", element: <App /> }], { future: { v7_relativeSplatPath: true } });

startThemeSync();

const container = document.getElementById("root");
if (container) {
  createRoot(container).render(<RouterProvider router={router} future={{ v7_startTransition: true }} />);
}
