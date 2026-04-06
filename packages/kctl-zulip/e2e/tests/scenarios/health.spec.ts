import { test, expect } from "../../fixtures/zulip-test";

test.describe("Zulip Health", () => {
  test("server settings endpoint returns 200", async ({
    request,
    zulipURL,
  }) => {
    test.skip(!zulipURL, "ZULIP_URL not set");

    const response = await request.get(`${zulipURL}/api/v1/server_settings`);
    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty("zulip_version");
    expect(body.result).toBe("success");
  });
});
