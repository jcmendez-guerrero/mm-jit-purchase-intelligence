// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { CommandPalette } from "../../src/app/CommandPalette";
import { itemsFor } from "../../src/app/routes";
import "../../src/i18n";

/** T018 — quick-jump: opens by shortcut and button, combobox/listbox, accent-insensitive, role-filtered, screens only. */

afterEach(cleanup);

const Where: React.FC = () => <output data-testid="where">{useLocation().pathname}</output>;

function setup(roles: string[] = ["viewer", "buyer"]) {
  return render(
    <MemoryRouter initialEntries={["/panel"]}>
      <CommandPalette items={itemsFor(roles)} />
      <Where />
    </MemoryRouter>,
  );
}

const open = () => fireEvent.click(screen.getByRole("button", { name: "Ir a una pantalla" }));

describe("CommandPalette", () => {
  it("opens from the visible button", () => {
    setup();
    open();
    expect(screen.getByRole("combobox")).toBeTruthy();
    expect(screen.getByRole("listbox")).toBeTruthy();
  });

  it("opens with Ctrl+K and Cmd+K", () => {
    setup();
    fireEvent.keyDown(document, { key: "k", ctrlKey: true });
    expect(screen.getByRole("combobox")).toBeTruthy();
    cleanup();
    setup();
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    expect(screen.getByRole("combobox")).toBeTruthy();
  });

  it("filters screens ignoring case and accents", () => {
    setup();
    open();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "CONFIGURACION" } });
    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options.some((t) => t?.includes("Configuración"))).toBe(true);
    expect(options.some((t) => t?.includes("Escenarios"))).toBe(false);
  });

  it("ranks an exact name before a name that merely contains the text", () => {
    setup();
    open();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "proveedores" } });
    const options = screen.getAllByRole("option").map((o) => o.textContent ?? "");
    expect(options[0]).toContain("Proveedores");
    expect(options[0]).not.toContain("Costes");
    expect(options.some((t) => t.includes("Costes y proveedores"))).toBe(true);
  });

  it("offers only screens the role may use", () => {
    setup(["viewer"]);
    open();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "admin" } });
    expect(screen.queryAllByRole("option")).toHaveLength(0);
    expect(screen.getByText("No hay pantallas que coincidan.")).toBeTruthy();
  });

  it("navigates to the chosen screen with Enter and closes", () => {
    setup();
    open();
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "costes" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.getByTestId("where").textContent).toBe("/costes");
    expect(screen.queryByRole("combobox")).toBeNull();
  });

  it("moves the active option with the arrow keys and navigates on click", () => {
    setup();
    open();
    const input = screen.getByRole("combobox");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    const active = input.getAttribute("aria-activedescendant");
    expect(active).toBeTruthy();
    expect(document.getElementById(active ?? "")?.getAttribute("aria-selected")).toBe("true");
    fireEvent.click(screen.getByRole("option", { name: /Propuestas de compra/ }));
    expect(screen.getByTestId("where").textContent).toBe("/propuestas");
  });

  it("closes with Escape and returns focus to the button", () => {
    setup();
    const button = screen.getByRole("button", { name: "Ir a una pantalla" });
    button.focus();
    open();
    fireEvent.keyDown(screen.getByRole("combobox"), { key: "Escape" });
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(document.activeElement).toBe(button);
  });
});
