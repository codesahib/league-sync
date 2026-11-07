import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

test.beforeEach(() => {
  const root = resolve("..");
  const python = resolve(
    root,
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
  execFileSync(python, ["-m", "backend.seed"], {
    cwd: root,
    env: { ...process.env, LEAGUE_DB: resolve(root, "data/ui-test.sqlite3") },
  });
});

test("baseline CSV handoff exposes a stale transfer", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Two systems. One reliable roster." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Save transfer" }).click();
  await expect(page.getByRole("status")).toContainText("Transfer saved");
  const csv = await (await request.get("/api/baseline/export")).text();
  await page.getByLabel("Upload roster CSV").setInputFiles({
    name: "roster.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  await expect(page.getByRole("status")).toContainText("CSV imported");
  await expect(page.getByText("duplicate · stale_fields")).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "../evidence/baseline.png", fullPage: true });
  expect(errors).toEqual([]);
});

test("reliable transfer, failure retry, replay and conflict review", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByRole("button", { name: "02 Reliable sync" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Reliable synchronization enabled",
  );
  await page.getByRole("button", { name: "Fail next delivery" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Temporary failure armed",
  );
  await page.getByRole("button", { name: "Save transfer" }).click();
  await expect(page.getByRole("status")).toContainText("Transfer saved");
  await page.getByRole("button", { name: "Process queue" }).click();
  await expect(page.getByRole("status")).toContainText("Due jobs processed");
  await expect(
    page.getByRole("cell", { name: "failed", exact: true }),
  ).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "../evidence/failed-delivery.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Retry queued");
  await page.getByRole("button", { name: "Process queue" }).click();
  await expect(page.getByRole("status")).toContainText("Due jobs processed");
  await page.getByRole("button", { name: "Replay", exact: true }).click();
  await expect(page.getByRole("status")).toContainText(
    "Same event queued again",
  );
  await page.getByRole("button", { name: "Process queue" }).click();
  await expect(page.getByRole("status")).toContainText("Due jobs processed");
  let data = await (await request.get("/api/state")).json();
  expect(data.reconciliation.mismatch_count).toBe(0);
  expect(data.league_players).toHaveLength(20);
  expect(data.sync.events[0].attempts).toBe(3);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "../evidence/improved.png", fullPage: true });
  await page.getByRole("button", { name: "Simulate conflicting name" }).click();
  await expect(page.getByRole("status")).toContainText(
    "League name edited locally",
  );
  await page.getByRole("button", { name: "Save transfer" }).click();
  await expect(page.getByRole("status")).toContainText("Transfer saved");
  await page.getByRole("button", { name: "Process queue" }).click();
  await expect(page.getByRole("status")).toContainText("Due jobs processed");
  await page.getByText("Review conflict & approve authority").click();
  await page
    .getByLabel("Reason for approving Club fields")
    .fill(
      "Reviewed synthetic Club registration and approved source authority.",
    );
  await page.getByRole("button", { name: "Approve Club fields" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Club authority approved",
  );
  await page.getByRole("button", { name: "Process queue" }).click();
  await expect(page.getByRole("status")).toContainText("Due jobs processed");
  data = await (await request.get("/api/state")).json();
  expect(data.reconciliation.mismatch_count).toBe(0);
  expect(
    data.sync.audit.some(
      (a: { action: string }) => a.action === "authority_approved",
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "../evidence/mobile.png", fullPage: true });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
