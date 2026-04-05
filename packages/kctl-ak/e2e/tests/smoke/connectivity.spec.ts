import { test, expect } from "../../fixtures/auth";

test.describe("Connectivity", () => {
  test.skip(!process.env.AUTHENTIK_TOKEN, "AUTHENTIK_TOKEN not set");

  test("API endpoint is reachable", async ({ request, apiToken, baseUrl }) => {
    const response = await request.get(`${baseUrl}/api/v3/core/applications/`, {
      headers: { Authorization: `Bearer ${apiToken}` },
    });
    expect([200, 204]).toContain(response.status());
  });
});
