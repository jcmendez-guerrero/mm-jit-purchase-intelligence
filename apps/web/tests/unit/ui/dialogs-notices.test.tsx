// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "../../../src/ui/ConfirmDialog";
import { NoticeProvider, useNotices } from "../../../src/ui/NoticeProvider";
import "../../../src/i18n";

/** T054 — confirmation dialog and notices (FR-018, FR-019). */

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const base = { title: "Aprobar la propuesta", objectLabel: "Semana 2026-W45 · 1.234,50 €", effect: "La propuesta pasará a estar aprobada. No se enviará ningún pedido.", confirmLabel: "Aprobar propuesta" };

describe("ConfirmDialog", () => {
  it("names the object and the effect", () => {
    render(<ConfirmDialog open {...base} onConfirm={() => undefined} onCancel={() => undefined} />);
    expect(screen.getByRole("dialog", { name: "Aprobar la propuesta" })).toBeTruthy();
    expect(screen.getByText("Semana 2026-W45 · 1.234,50 €")).toBeTruthy();
    expect(screen.getByText(/No se enviará ningún pedido/)).toBeTruthy();
  });

  it("focuses the confirm button for a default action and the cancel button for a danger action", () => {
    const { rerender } = render(<ConfirmDialog open {...base} onConfirm={() => undefined} onCancel={() => undefined} />);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Aprobar propuesta" }));
    rerender(<ConfirmDialog open {...base} tone="danger" onConfirm={() => undefined} onCancel={() => undefined} />);
    cleanup();
    render(<ConfirmDialog open {...base} tone="danger" onConfirm={() => undefined} onCancel={() => undefined} />);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Cancelar" }));
  });

  it("confirms and cancels, and Escape cancels", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<ConfirmDialog open {...base} onConfirm={onConfirm} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole("button", { name: "Aprobar propuesta" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onCancel).toHaveBeenCalledTimes(2);
  });

  it("returns focus to the control that opened it", () => {
    const Host: React.FC = () => {
      const [open, setOpen] = React.useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)}>Abrir</button>
          <ConfirmDialog open={open} {...base} onConfirm={() => setOpen(false)} onCancel={() => setOpen(false)} />
        </>
      );
    };
    render(<Host />);
    const opener = screen.getByRole("button", { name: "Abrir" });
    opener.focus();
    fireEvent.click(opener);
    expect(screen.getByRole("dialog")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it("renders nothing when closed", () => {
    render(<ConfirmDialog open={false} {...base} onConfirm={() => undefined} onCancel={() => undefined} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("notices", () => {
  const Trigger: React.FC<{ text?: string }> = ({ text = "Condiciones guardadas" }) => {
    const { notify } = useNotices();
    return <button onClick={() => notify("success", text)}>Guardar</button>;
  };
  const setup = () =>
    render(
      <NoticeProvider>
        <Trigger />
      </NoticeProvider>,
    );

  beforeEach(() => vi.useFakeTimers());

  it("has a polite live region before anything is announced", () => {
    setup();
    const region = screen.getByRole("region", { name: "Avisos" });
    expect(region.getAttribute("aria-live")).toBe("polite");
  });

  it("shows a notice without taking focus, and keeps it at least six seconds", () => {
    setup();
    const button = screen.getByRole("button", { name: "Guardar" });
    button.focus();
    fireEvent.click(button);
    expect(screen.getByText("Condiciones guardadas")).toBeTruthy();
    expect(document.activeElement).toBe(button);
    act(() => vi.advanceTimersByTime(5900));
    expect(screen.queryByText("Condiciones guardadas")).toBeTruthy();
    act(() => vi.advanceTimersByTime(200));
    expect(screen.queryByText("Condiciones guardadas")).toBeNull();
  });

  it("pauses while hovered or focused", () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    const notice = screen.getByText("Condiciones guardadas").closest(".mmi-notice") as HTMLElement;
    fireEvent.mouseEnter(notice);
    act(() => vi.advanceTimersByTime(20000));
    expect(screen.queryByText("Condiciones guardadas")).toBeTruthy();
    fireEvent.mouseLeave(notice);
    act(() => vi.advanceTimersByTime(6100));
    expect(screen.queryByText("Condiciones guardadas")).toBeNull();
  });

  it("is dismissible by keyboard: the button and Escape", () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    fireEvent.click(screen.getByRole("button", { name: "Cerrar aviso" }));
    expect(screen.queryByText("Condiciones guardadas")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    const notice = screen.getByText("Condiciones guardadas").closest(".mmi-notice") as HTMLElement;
    fireEvent.keyDown(notice, { key: "Escape" });
    expect(screen.queryByText("Condiciones guardadas")).toBeNull();
  });

  it("stacks several notices", () => {
    render(
      <NoticeProvider>
        <Trigger text="Uno" />
        <Trigger text="Dos" />
      </NoticeProvider>,
    );
    for (const b of screen.getAllByRole("button", { name: "Guardar" })) fireEvent.click(b);
    expect(screen.getByText("Uno")).toBeTruthy();
    expect(screen.getByText("Dos")).toBeTruthy();
  });

  it("does nothing, and does not throw, without a provider", () => {
    render(<Trigger />);
    expect(() => fireEvent.click(screen.getByRole("button", { name: "Guardar" }))).not.toThrow();
  });
});
