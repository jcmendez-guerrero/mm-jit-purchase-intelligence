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

describe("permission refusals", () => {
  it("gives any 403 the no-permission sentence, even with a code the screen does not know", () => {
    expect(errorMessage(new ApiError(403, "something_new"), "Ha ocurrido un error")).toBe(catalogue["errors.auth_forbidden_role"]);
  });

  it("keeps the specific sentence of a known 403 code", () => {
    expect(errorMessage(new ApiError(403, "auth_mfa_stale"), "x")).toBe(catalogue["errors.auth_mfa_stale"]);
  });
});

// T026 (feature 012, FR-010): every message says what to do next, in Spanish, without technical terms.
const NEXT_STEP = /\b(int[eé]nt\w+|reint\w+|revis\w+|compruebe\w*|corrij\w+|corríj\w+|indique\w*|elija\w*|espere\w*|vuelva\w*|acote\w*|use\b|usa\b|contact\w+|solicit\w+|cargue\w*|añad\w+|añádal\w+|cree\w*|pida\w*|pídalo|debe\w*|deben|necesita\w*|solo\b|sólo|puede\w*|pueden|se reintentar\w+|automáticamente|actualice\w*|seleccion\w+|escriba|ajuste\w*|asegúrese|confirme\w*|repita\w*|sustituya|cambie\w*|quite\w*|pruebe\w*|calcúl\w+|reduzca|divida|suba\b|abra\b|consulte\w*|relaje|descargue\w*|actualiza\w*|revisa\w*|indica\w*|elige\w*|comprueba\w*|corrige\w*|corrígel\w+|recarga\w*|carga\b|confirma\w*|repite\w*|quita\w*|prueba\w*|descarga\w*|solicita\w*|pide\w*|añade\w*|añádel\w+|reduce\b|divide\b|sube\b|abre\b|consulta\w*|vuelve\w*|puedes|tienes|debes|reasígnal\w+|omítel\w+|resuélvel\w+|completa\b|usa\b|crea\b|cambia\w*|ajusta\w*|espera\w*|asegúrate)/i;

describe("every error message tells the person what to do next", () => {
  // The no-access box (ScreenState) adds its own next step and link, so this one sentence stands alone.
  const OWN_NEXT_STEP = new Set(["errors.auth_forbidden_role"]);
  const messages = Object.entries(catalogue).filter(([k]) => k.startsWith("errors.") && !OWN_NEXT_STEP.has(k));

  it("the next-step detector recognises a next step and a bare statement (self-check)", () => {
    expect(NEXT_STEP.test("El archivo es demasiado grande. Reduce o divide el archivo.")).toBe(true);
    expect(NEXT_STEP.test("El proveedor no existe.")).toBe(false);
  });

  it.each(messages)("%s has a next step and no technical wording", (key, text) => {
    expect(NEXT_STEP.test(text), `${key}: add what the person should do`).toBe(true);
    expect(text.length, key).toBeGreaterThan(20);
    expect(/Traceback|HTTP|\b[45]\d\d\b|undefined|null\b/.test(text), key).toBe(false);
  });
});
