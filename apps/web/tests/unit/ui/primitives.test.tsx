// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Button } from "../../../src/ui/Button";
import { Card } from "../../../src/ui/Card";
import { EmptyState } from "../../../src/ui/EmptyState";
import { ErrorState } from "../../../src/ui/ErrorState";
import { PageHeader } from "../../../src/ui/PageHeader";
import { ScreenState } from "../../../src/ui/ScreenState";
import { Skeleton } from "../../../src/ui/Skeleton";
import "../../../src/i18n";

/** T005 — behavioural contract of the shared primitives (contracts/ui-contracts.md §5). */

afterEach(cleanup);

describe("Button", () => {
  it("is a button with its label and fires onClick", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Guardar cambios</Button>);
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("keeps its label, is busy and does not fire while loading", () => {
    const onClick = vi.fn();
    render(<Button loading onClick={onClick}>Guardar cambios</Button>);
    const button = screen.getByRole("button", { name: /Guardar cambios/ });
    expect(button.getAttribute("aria-busy")).toBe("true");
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("supports variants and disabled", () => {
    render(<Button variant="secondary" disabled>Quitar filtros</Button>);
    const button = screen.getByRole("button", { name: "Quitar filtros" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.className).toContain("mmi-button--secondary");
  });
});

describe("Card and PageHeader", () => {
  it("renders a titled card region", () => {
    render(<Card title="Condiciones">contenido</Card>);
    expect(screen.getByRole("region", { name: "Condiciones" })).toBeTruthy();
  });

  it("renders exactly one h1 with context line and actions", () => {
    render(<PageHeader title="Panel de control" description="Riesgos y alertas" actions={<Button>Actualizar</Button>} />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1, name: "Panel de control" })).toBeTruthy();
    expect(screen.getByText("Riesgos y alertas")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Actualizar" })).toBeTruthy();
  });
});

describe("states", () => {
  it("Skeleton is hidden from assistive technology", () => {
    const { container } = render(<Skeleton lines={3} />);
    expect(container.firstElementChild?.getAttribute("aria-hidden")).toBe("true");
  });

  it("EmptyState explains and offers an action", () => {
    const onAction = vi.fn();
    render(<EmptyState title="No hay productos." hint="Cambia los filtros." actionLabel="Quitar filtros" onAction={onAction} />);
    fireEvent.click(screen.getByRole("button", { name: "Quitar filtros" }));
    expect(onAction).toHaveBeenCalled();
    expect(screen.getByText("No hay productos.")).toBeTruthy();
  });

  it("ErrorState announces the problem and offers retry", () => {
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("ScreenState renders exactly one of loading / empty / error / no-access, or its children when ready", () => {
    const { rerender } = render(<ScreenState state="loading">listo</ScreenState>);
    expect(screen.getByRole("status").getAttribute("aria-busy")).toBe("true");
    expect(screen.queryByText("listo")).toBeNull();

    rerender(<ScreenState state="empty">listo</ScreenState>);
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.queryByText("listo")).toBeNull();
    expect(screen.getByText("No hay datos que mostrar.")).toBeTruthy();

    rerender(<ScreenState state="error" onRetry={() => undefined}>listo</ScreenState>);
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeTruthy();

    rerender(<ScreenState state="no_access">listo</ScreenState>);
    expect(screen.getByText("Tu rol no permite ver esta sección.")).toBeTruthy();

    rerender(<ScreenState state="ready">listo</ScreenState>);
    expect(screen.getByText("listo")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("ScreenState keeps current content visible while refreshing (stale-while-revalidate)", () => {
    render(<ScreenState state="ready" refreshing>filas actuales</ScreenState>);
    expect(screen.getByText("filas actuales")).toBeTruthy();
    expect(screen.getByRole("status", { name: "Cargando datos" })).toBeTruthy();
  });
});

describe("ScreenState permission refusal", () => {
  it("explains the refusal with a way forward instead of a retry", () => {
    render(<ScreenState state="error" errorHint="No tiene permiso para realizar esta acción." onRetry={() => undefined} />);
    expect(screen.getByRole("alert").textContent).toContain("No tiene permiso para realizar esta acción.");
    expect(screen.getByRole("link", { name: "Ir al panel de control" }).getAttribute("href")).toBe("/panel");
    expect(screen.queryByRole("button", { name: "Reintentar" })).toBeNull();
  });
});
