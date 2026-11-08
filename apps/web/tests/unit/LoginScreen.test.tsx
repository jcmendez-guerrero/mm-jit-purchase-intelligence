// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../src/api/client";
import { LoginScreen } from "../../src/app/LoginScreen";
import "../../src/i18n";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("LoginScreen (Spanish)", () => {
  it("offers a role chooser locally and signs in with the chosen role", async () => {
    vi.spyOn(api, "getAuthConfig").mockResolvedValue({ mode: "dev" });
    const onDevLogin = vi.fn().mockResolvedValue(undefined);
    render(<LoginScreen sessionExpired={false} onDevLogin={onDevLogin} />);
    expect(await screen.findByRole("heading", { name: "Inicia sesión" })).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Entrar como Aprobador" }));
    await waitFor(() => expect(onDevLogin).toHaveBeenCalledWith("approver"));
    expect(screen.queryByText("Iniciar sesión con Microsoft")).toBeNull();
  });

  it("offers Microsoft sign-in in Azure and no role chooser", async () => {
    vi.spyOn(api, "getAuthConfig").mockResolvedValue({ mode: "entra" });
    render(<LoginScreen sessionExpired={false} onDevLogin={vi.fn()} />);
    const link = await screen.findByRole("link", { name: "Iniciar sesión con Microsoft" });
    expect(link.getAttribute("href")).toBe("/api/auth/login");
    expect(screen.queryByText(/Entrar como/)).toBeNull();
  });

  it("says so when sign-in is not configured, and when the session expired", async () => {
    vi.spyOn(api, "getAuthConfig").mockResolvedValue({ mode: "none" });
    render(<LoginScreen sessionExpired onDevLogin={vi.fn()} />);
    expect(await screen.findByText(/no está configurado/)).toBeTruthy();
    expect(screen.getByText("La sesión ha caducado.")).toBeTruthy();
  });
});
