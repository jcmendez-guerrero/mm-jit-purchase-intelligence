import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, errorMessage } from "../../src/api/client";
import esJson from "../../src/i18n/es-ES.json";

const catalogue = esJson as Record<string, string>;

function respond(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })));
}

afterEach(() => vi.unstubAllGlobals());

describe("API refusals reach the user as Spanish text", () => {
  it("translates a stable code", async () => {
    respond(403, { detail: "auth_forbidden_role" });
    const err = await api.getRoles().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(403);
    expect(errorMessage(err, "fallback")).toBe(catalogue["errors.auth_forbidden_role"]);
  });

  it("uses the generic message for an unknown code, never the raw code", () => {
    expect(errorMessage(new ApiError(400, "something_new"), "Ha ocurrido un error")).toBe("Ha ocurrido un error");
  });

  it("never shows free text or technical errors from the network", async () => {
    respond(500, { detail: "Traceback (most recent call last): secret" });
    const err = await api.getRoles().catch((e) => e);
    expect(err.code).toBe("unknown");
    expect(errorMessage(err, "Ha ocurrido un error")).toBe("Ha ocurrido un error");
    expect(errorMessage(new TypeError("Failed to fetch"), "Ha ocurrido un error")).toBe("Ha ocurrido un error");
  });

  it("maps validation lists to one stable code", async () => {
    respond(422, { detail: [{ loc: ["body"], msg: "field required" }] });
    const err = await api.getRoles().catch((e) => e);
    expect(err.code).toBe("request_invalid");
    expect(errorMessage(err, "x")).toBe(catalogue["errors.request_invalid"]);
  });

  it("every message is Spanish, not a code", () => {
    for (const [key, value] of Object.entries(catalogue)) {
      if (!key.startsWith("errors.")) continue;
      expect(value).not.toBe(key.replace("errors.", ""));
      expect(value).toMatch(/^[A-ZÁÉÍÓÚÑ¿¡]/);
    }
  });
});
