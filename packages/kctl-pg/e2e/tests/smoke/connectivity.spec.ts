import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";

test.describe("kctl-pg CLI", () => {
  test.skip(!process.env.KCTL_PG_PROFILE, "KCTL_PG_PROFILE not set");

  test("health check succeeds", async () => {
    const profile = process.env.KCTL_PG_PROFILE!;
    const output = execFileSync(
      "kctl-pg",
      ["--profile", profile, "health", "check"],
      {
        encoding: "utf-8",
      },
    );
    expect(output).toBeTruthy();
  });
});
