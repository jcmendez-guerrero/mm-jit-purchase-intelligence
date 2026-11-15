// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import esJson from "../../../src/i18n/es-ES.json";
import glossary from "../../../src/i18n/glossary.json";
import { HelpHint } from "../../../src/ui/HelpHint";
import "../../../src/i18n";

// T032 (feature 012, FR-012): help is keyboard-operable, Spanish, from the glossary, and returns focus.

afterEach(cleanup);
const catalogue = esJson as Record<string, string>;

describe("HelpHint", () => {
  it("is a button with an accessible Spanish name and the definition hidden until opened", () => {
    render(<HelpHint concept="safety_stock" />);
    const b = screen.getByRole("button", { name: "Qué significa stock de seguridad" });
    expect(b.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("opens the glossary definition and closes with a second press", () => {
    render(<HelpHint concept="lead_time" />);
    fireEvent.click(screen.getByRole("button", { name: "Qué significa plazo de entrega" }));
    expect(screen.getByRole("note").textContent).toBe(catalogue["glossary.lead_time"]);
    const close = screen.getByRole("button", { name: "Cerrar la explicación de plazo de entrega" });
    expect(close.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(close);
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("closes with Escape and keeps focus on the button", () => {
    render(<HelpHint concept="service_level" />);
    const b = screen.getByRole("button");
    b.focus();
    fireEvent.click(b);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("note")).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole("button"));
  });

  it("every glossary concept has a definition in the catalogue and no note text", () => {
    for (const concept of Object.keys(glossary)) {
      expect(catalogue[`glossary.${concept}`], concept).toBeTruthy();
      expect(catalogue[`glossary.${concept}`], concept).not.toMatch(/nota del proveedor/i);
    }
  });
});
