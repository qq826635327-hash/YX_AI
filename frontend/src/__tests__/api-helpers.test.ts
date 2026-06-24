import { ApiError, unwrap, unwrapPaginated, unwrapFull } from "@/api/client";

describe("ApiError", () => {
  it("stores status and message", () => {
    const err = new ApiError("Not found", 404);
    expect(err.message).toBe("Not found");
    expect(err.status).toBe(404);
    expect(err.name).toBe("ApiError");
    expect(err.body).toBeUndefined();
  });

  it("stores body when provided", () => {
    const body = { error: "NOT_FOUND", message: "Resource not found" };
    const err = new ApiError("Not found", 404, body);
    expect(err.body).toEqual(body);
    expect(err.body?.error).toBe("NOT_FOUND");
  });

  it("is an instance of Error", () => {
    const err = new ApiError("test", 500);
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ApiError);
  });
});

describe("unwrap", () => {
  it("extracts data from a successful response", async () => {
    const mockResponse = new Response(
      JSON.stringify({ data: { id: "1", name: "test" }, message: "ok" }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
    const result = await unwrap<{ id: string; name: string }>(
      Promise.resolve(mockResponse)
    );
    expect(result).toEqual({ id: "1", name: "test" });
  });

  it("extracts null data", async () => {
    const mockResponse = new Response(
      JSON.stringify({ data: null }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
    const result = await unwrap(Promise.resolve(mockResponse));
    expect(result).toBeNull();
  });

  it("extracts array data", async () => {
    const mockResponse = new Response(
      JSON.stringify({ data: [1, 2, 3] }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
    const result = await unwrap<number[]>(Promise.resolve(mockResponse));
    expect(result).toEqual([1, 2, 3]);
  });
});

describe("unwrapPaginated", () => {
  it("extracts paginated data", async () => {
    const paginatedData = {
      items: [{ id: "1" }, { id: "2" }],
      total: 10,
      page: 1,
      page_size: 2,
    };
    const mockResponse = new Response(
      JSON.stringify({ data: paginatedData }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
    const result = await unwrapPaginated<{ id: string }>(
      Promise.resolve(mockResponse)
    );
    expect(result.items).toHaveLength(2);
    expect(result.total).toBe(10);
    expect(result.page).toBe(1);
    expect(result.page_size).toBe(2);
  });

  it("handles empty items list", async () => {
    const mockResponse = new Response(
      JSON.stringify({ data: { items: [], total: 0, page: 1, page_size: 10 } }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
    const result = await unwrapPaginated(Promise.resolve(mockResponse));
    expect(result.items).toEqual([]);
    expect(result.total).toBe(0);
  });
});

describe("unwrapFull", () => {
  it("returns the full response including message", async () => {
    const mockResponse = new Response(
      JSON.stringify({ data: { id: "1" }, message: "success" }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
    const result = await unwrapFull<{ id: string }>(
      Promise.resolve(mockResponse)
    );
    expect(result.data).toEqual({ id: "1" });
    expect(result.message).toBe("success");
  });

  it("handles response without message", async () => {
    const mockResponse = new Response(
      JSON.stringify({ data: "hello" }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
    const result = await unwrapFull<string>(Promise.resolve(mockResponse));
    expect(result.data).toBe("hello");
    expect(result.message).toBeUndefined();
  });
});
