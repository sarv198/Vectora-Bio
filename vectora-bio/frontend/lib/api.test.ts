import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, buildQuery, parseApiError } from "@/lib/api";
import { formatSigned, optionalNumber } from "@/lib/format";

describe("parseApiError", () => {
  it("reads the backend error envelope", () => {
    const error = parseApiError(503, {
      error: "data_not_loaded",
      message: "Required data has not been loaded: compound_profiles.",
      details: { missing_datasets: ["compound_profiles"], hint: "Run the import." },
    });
    expect(error.code).toBe("data_not_loaded");
    expect(error.missingDatasets).toEqual(["compound_profiles"]);
    expect(error.hint).toBe("Run the import.");
  });

  it("flattens FastAPI validation errors", () => {
    const error = parseApiError(422, {
      detail: [{ loc: ["body", "compound_id"], msg: "String should have at least 1 character" }],
    });
    expect(error.code).toBe("validation_error");
    expect(error.message).toBe("compound_id: String should have at least 1 character");
  });

  it("falls back for unknown bodies", () => {
    expect(parseApiError(500, null).message).toContain("500");
  });
});

describe("buildQuery", () => {
  it("drops empty values", () => {
    expect(buildQuery({ search: "abc", cell_line: "", timepoint: null, limit: 25 })).toBe("?search=abc&limit=25");
    expect(buildQuery({})).toBe("");
  });
});

describe("api client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("throws ApiError with the parsed body on non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ error: "not_found", message: "nope", details: {} }), { status: 404 })),
    );
    await expect(api.getCompound("X")).rejects.toMatchObject({ status: 404, code: "not_found" });
  });

  it("reports network failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );
    const error = await api.health().catch((err: unknown) => err);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("network_error");
  });

  it("posts JSON bodies", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ predictions: [] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.similarCompounds({ compound_id: "C1", top_k: 5 });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/api\/similarity\/compounds$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ compound_id: "C1", top_k: 5 });
  });
});

describe("format helpers", () => {
  it("formats and parses", () => {
    expect(formatSigned(0.5)).toBe("+0.500");
    expect(formatSigned(-0.25, 2)).toBe("-0.25");
    expect(optionalNumber(" 48 ")).toBe(48);
    expect(optionalNumber("")).toBeNull();
    expect(optionalNumber("abc")).toBeNull();
  });
});
