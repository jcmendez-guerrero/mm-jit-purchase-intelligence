// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, RoleMirrorStatus, RolesListing } from "../../src/api/client";
import { RolesScreen } from "../../src/features/admin/RolesScreen";
import "../../src/i18n";

const listing = (approvers = 2): RolesListing => ({
  users: [
    { user_id: "buyer-1", roles: ["buyer", "viewer"], active: true, revision: 1 },
    { user_id: "approver-1", roles: ["approver", "viewer"], active: true, revision: 1 },
  ],
  eligible_approvers_count: approvers,
  valid_roles: ["viewer", "buyer", "approver", "admin"],
});
const mirrorOk: RoleMirrorStatus = { pending: 0, failed: 0, sent: 3, oldest_pending_seconds: 0, items: [] };

beforeEach(() => {
  vi.spyOn(api, "getRoles").mockResolvedValue(listing());
  vi.spyOn(api, "getRoleMirror").mockResolvedValue(mirrorOk);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("RolesScreen (Spanish)", () => {
  it("lists the users and says the mirror is up to date", async () => {
    render(<RolesScreen />);
    expect(await screen.findByText("buyer-1")).toBeTruthy();
    expect(screen.getByText("Usuarios y roles")).toBeTruthy();
    expect(screen.getByText("Aprobadores activos: 2")).toBeTruthy();
    expect(screen.getByText("Todos los cambios de rol se han comunicado al área de compras.")).toBeTruthy();
  });

  it("saves a role change with viewer kept, then reloads", async () => {
    const update = vi.spyOn(api, "updateRoles").mockResolvedValue({});
    render(<RolesScreen />);
    fireEvent.click(await screen.findByLabelText("buyer-1 Aprobador"));
    await waitFor(() => expect(update).toHaveBeenCalledWith("buyer-1", ["approver", "buyer", "viewer"], true));
    await waitFor(() => expect(api.getRoles).toHaveBeenCalledTimes(2));
  });

  it("shows the refusal in Spanish, never the code", async () => {
    vi.spyOn(api, "updateRoles").mockRejectedValue(new ApiError(409, "approval_fewer_than_two_approvers"));
    render(<RolesScreen />);
    fireEvent.click(await screen.findByLabelText("approver-1 Aprobador"));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Se necesitan al menos dos personas con rol de aprobador");
    expect(document.body.textContent).not.toContain("approval_fewer_than_two_approvers");
  });

  it("warns when fewer than two approvers exist", async () => {
    vi.spyOn(api, "getRoles").mockResolvedValue(listing(1));
    render(<RolesScreen />);
    expect((await screen.findByRole("alert")).textContent).toContain("al menos dos aprobadores activos");
  });

  it("surfaces failed mirror changes and offers a retry", async () => {
    vi.spyOn(api, "getRoleMirror").mockResolvedValue({ pending: 0, failed: 2, sent: 0, oldest_pending_seconds: 600, items: [] });
    const retry = vi.spyOn(api, "retryRoleMirror").mockResolvedValue({ requeued: 2 });
    render(<RolesScreen />);
    expect((await screen.findByText("Fallidos: 2")).getAttribute("role")).toBe("alert");
    fireEvent.click(screen.getByRole("button", { name: "Reintentar envío" }));
    await waitFor(() => expect(retry).toHaveBeenCalled());
  });

  it("shows pending changes with their age", async () => {
    vi.spyOn(api, "getRoleMirror").mockResolvedValue({ pending: 1, failed: 0, sent: 0, oldest_pending_seconds: 125, items: [] });
    render(<RolesScreen />);
    expect(await screen.findByText("Pendientes: 1")).toBeTruthy();
    expect(screen.getByText("Cambio pendiente más antiguo: 2 min")).toBeTruthy();
  });
});
