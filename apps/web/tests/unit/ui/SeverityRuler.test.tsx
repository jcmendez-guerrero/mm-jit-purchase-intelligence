// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SeverityRuler } from "../../../src/ui/SeverityRuler";
import "../../../src/i18n";

/** T079 — stockout-severity ruler (design.md §6). */

afterEach(cleanup);
const counts = { out_of_stock: 4, imminent: 9, below_reorder_point: 21 };

describe("SeverityRuler", () => {
  it("sizes segments in proportion to their counts and omits empty ones", () => {
    const { container } = render(<SeverityRuler counts={{ out_of_stock: 0, imminent: 9, below_reorder_point: 21 }} active={null} onSelect={() => undefined} />);
    const segments = [...container.querySelectorAll<HTMLElement>(".mmi-ruler__segment")];
    expect(segments).toHaveLength(2);
    expect(segments[0]!.style.flexGrow).toBe("9");
    expect(segments[1]!.style.flexGrow).toBe("21");
  });

  it("makes each segment a button named with its count and label, with aria-pressed", () => {
    render(<SeverityRuler counts={counts} active="imminent" onSelect={() => undefined} />);
    expect(screen.getByRole("button", { name: "4: Sin existencias" }).getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByRole("button", { name: "9: Rotura inminente" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "21: Bajo el punto de pedido" })).toBeTruthy();
  });

  it("filters on activation and clears when the same segment is activated again", () => {
    const onSelect = vi.fn();
    const { rerender } = render(<SeverityRuler counts={counts} active={null} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: "4: Sin existencias" }));
    expect(onSelect).toHaveBeenLastCalledWith("out_of_stock");
    rerender(<SeverityRuler counts={counts} active="out_of_stock" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: "4: Sin existencias" }));
    expect(onSelect).toHaveBeenLastCalledWith(null);
  });

  it("never relies on colour alone: icon, count and label are present, plus a text summary", () => {
    const { container } = render(<SeverityRuler counts={counts} active={null} onSelect={() => undefined} />);
    expect(container.querySelectorAll(".mmi-ruler__segment svg").length).toBe(3);
    expect(screen.getAllByText(/Productos con riesgo de rotura de stock: 34/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Sin existencias").length).toBeGreaterThan(0);
  });

  it("shows a calm line when there is no stockout risk", () => {
    render(<SeverityRuler counts={{ out_of_stock: 0, imminent: 0, below_reorder_point: 0 }} active={null} onSelect={() => undefined} />);
    expect(screen.getByText("Sin riesgo de rotura de stock.")).toBeTruthy();
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("shows only the total when the split is not reliable", () => {
    render(<SeverityRuler counts={counts} total={7} splitReliable={false} active={null} onSelect={() => undefined} />);
    expect(screen.getByText("Productos con riesgo de rotura de stock: 7")).toBeTruthy();
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("animates only when asked, so refetches and filters never replay it", () => {
    const { container, rerender } = render(<SeverityRuler counts={counts} active={null} onSelect={() => undefined} animate />);
    expect(container.querySelector(".mmi-ruler--animate")).toBeTruthy();
    rerender(<SeverityRuler counts={counts} active={null} onSelect={() => undefined} />);
    expect(container.querySelector(".mmi-ruler--animate")).toBeNull();
  });
});
