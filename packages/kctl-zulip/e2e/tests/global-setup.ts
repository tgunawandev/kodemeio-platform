import { test } from "../fixtures/zulip-test";

test("verify environment", async ({ zulipURL }) => {
  test.skip(!zulipURL, "ZULIP_URL not set");
  console.log(`Zulip URL: ${zulipURL}`);
});
