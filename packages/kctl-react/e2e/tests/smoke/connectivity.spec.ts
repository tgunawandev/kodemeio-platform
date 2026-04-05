import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";

test.describe("kctl-react CLI", () => {
  test.skip(!process.env.REACT_MONOREPO_PATH, "REACT_MONOREPO_PATH not set");

  test("can list apps in monorepo", async () => {
    const output = execFileSync("kctl-react", ["apps", "list"], {
      cwd: process.env.REACT_MONOREPO_PATH,
      encoding: "utf-8",
    });
    expect(output).toContain("sfa");
  });
});
