import { test, expect } from "../../fixtures/auth";

test.describe("Connectivity", () => {
  test.skip(!process.env.DOKPLOY_TOKEN, "DOKPLOY_TOKEN not set");

  test("API endpoint is reachable", async ({ request, apiToken, baseUrl }) => {
    const response = await request.get(`${baseUrl}/api/health`, {
      headers: { Authorization: `Bearer ${apiToken}` },
    });
    expect([200, 204]).toContain(response.status());
  });
});
