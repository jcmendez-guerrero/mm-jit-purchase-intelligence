// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Link, RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FormField, focusFirstInvalid } from "../../../src/ui/FormField";
import { UnsavedChangesPrompt } from "../../../src/ui/UnsavedChangesPrompt";
import { useUnsavedChanges } from "../../../src/ui/useUnsavedChanges";
import "../../../src/i18n";

/** T053 — FormField wiring, first-invalid focus, and the unsaved-changes guard (FR-016, FR-017). */

afterEach(cleanup);

describe("FormField", () => {
  it("ties label, hint and error to the control and marks it invalid", () => {
    render(<FormField id="f-lead" label="Plazo de entrega (días)" value="x" onChange={() => undefined} hint="En días" error="Introduce un número entero igual o mayor que cero." />);
    const input = screen.getByLabelText("Plazo de entrega (días)");
    expect(input.getAttribute("aria-invalid")).toBe("true");
    const described = (input.getAttribute("aria-describedby") ?? "").split(" ");
    expect(described.map((id) => document.getElementById(id)?.textContent)).toEqual(["En días", "Introduce un número entero igual o mayor que cero."]);
  });

  it("is not invalid and has no error text without an error", () => {
    render(<FormField id="f-a" label="Campo" value="" onChange={() => undefined} />);
    const input = screen.getByLabelText("Campo");
    expect(input.getAttribute("aria-invalid")).toBeNull();
    expect(input.getAttribute("aria-describedby")).toBeNull();
  });

  it("reports changes", () => {
    const onChange = vi.fn();
    render(<FormField id="f-a" label="Campo" value="" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Campo"), { target: { value: "7" } });
    expect(onChange).toHaveBeenCalledWith("7");
  });

  it("focusFirstInvalid moves focus to the first invalid control in the form", () => {
    render(
      <form data-testid="form">
        <FormField id="a" label="A" value="" onChange={() => undefined} />
        <FormField id="b" label="B" value="" onChange={() => undefined} error="mal" />
        <FormField id="c" label="C" value="" onChange={() => undefined} error="mal" />
      </form>,
    );
    expect(focusFirstInvalid(screen.getByTestId("form"))).toBe(true);
    expect(document.activeElement?.id).toBe("b");
    cleanup();
    render(<FormField id="a" label="A" value="" onChange={() => undefined} />);
    expect(focusFirstInvalid(document.body)).toBe(false);
  });
});

describe("unsaved changes", () => {
  const Probe: React.FC<{ dirty: boolean }> = ({ dirty }) => {
    useUnsavedChanges(dirty);
    return null;
  };

  it("registers a beforeunload warning only while the form is dirty", () => {
    const { rerender } = render(<Probe dirty={false} />);
    const clean = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(clean);
    expect(clean.defaultPrevented).toBe(false);
    rerender(<Probe dirty />);
    const dirty = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(dirty);
    expect(dirty.defaultPrevented).toBe(true);
    rerender(<Probe dirty={false} />);
    const after = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(after);
    expect(after.defaultPrevented).toBe(false);
  });

  function setup(dirty: boolean) {
    const router = createMemoryRouter([
      {
        path: "/editar",
        element: (
          <>
            <UnsavedChangesPrompt dirty={dirty} />
            <Link to="/otra">Ir a otra pantalla</Link>
          </>
        ),
      },
      { path: "/otra", element: <p>Otra pantalla</p> },
    ], { initialEntries: ["/editar"] });
    render(<RouterProvider router={router} />);
    return router;
  }

  it("asks before leaving with unsaved changes; keep editing stays", async () => {
    const router = setup(true);
    await act(async () => fireEvent.click(screen.getByRole("link", { name: "Ir a otra pantalla" })));
    expect(await screen.findByText("Tienes cambios sin guardar")).toBeTruthy();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Seguir editando" })));
    expect(router.state.location.pathname).toBe("/editar");
    expect(screen.queryByText("Tienes cambios sin guardar")).toBeNull();
  });

  it("discard changes proceeds with the navigation", async () => {
    const router = setup(true);
    await act(async () => fireEvent.click(screen.getByRole("link", { name: "Ir a otra pantalla" })));
    await act(async () => fireEvent.click(await screen.findByRole("button", { name: "Descartar cambios" })));
    expect(router.state.location.pathname).toBe("/otra");
  });

  it("does not interrupt when nothing changed", async () => {
    const router = setup(false);
    await act(async () => fireEvent.click(screen.getByRole("link", { name: "Ir a otra pantalla" })));
    expect(router.state.location.pathname).toBe("/otra");
    expect(screen.queryByText("Tienes cambios sin guardar")).toBeNull();
  });

  it("renders nothing and does not throw outside a data router", () => {
    expect(() => render(<UnsavedChangesPrompt dirty />)).not.toThrow();
  });
});
