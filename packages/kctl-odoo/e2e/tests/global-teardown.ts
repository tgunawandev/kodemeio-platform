/**
 * Global teardown: cleanup after all tests.
 */

import { test as teardown } from "@playwright/test";

teardown("cleanup", async ({}) => {
  // Nothing to clean up currently.
  // Future: logout, delete test records, etc.
});
