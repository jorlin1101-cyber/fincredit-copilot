// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { BorrowerDashboardPage } from "../../pages/borrower-dashboard.page";

test.describe("Borrower Dashboard Cards", () => {
  let dashboard: BorrowerDashboardPage;

  test.beforeEach(async ({ page }) => {
    dashboard = new BorrowerDashboardPage(page);
    await dashboard.goto();
  });

  test("should show status card with application number and stage", async ({
    page,
  }) => {
    const appHeading = page.getByRole("heading", { name: /申请编号 #/ });
    const noApp = page.getByText("暂无进行中的住房贷款申请。");
    await expect(appHeading.or(noApp).first()).toBeVisible();
  });

  test("should show stage stepper with stage labels", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /申请编号 #/ })).toBeVisible({
      timeout: 10_000,
    });

    // Stage stepper renders responsive labels (two spans per stage: mobile hidden, desktop visible)
    await expect(page.getByText("咨询").last()).toBeVisible();
    await expect(page.getByText("已结案").last()).toBeVisible();
  });

  test("should display documents card", async () => {
    await expect(
      dashboard.page.getByRole("heading", { name: "申请材料" }),
    ).toBeVisible();
  });

  test("should display conditions card", async ({ page }) => {
    // Either conditions list or "No outstanding conditions" message
    const conditionsHeading = page.getByRole("heading", {
      name: "审批条件",
    });
    await expect(conditionsHeading).toBeVisible();
  });

  test("should display disclosures card", async () => {
    await expect(
      dashboard.page.getByRole("heading", { name: "信息披露" }),
    ).toBeVisible();
  });

  test("should display rate lock or pre-qualification card", async ({
    page,
  }) => {
    const rateLock = page.getByRole("heading", { name: "利率锁定" });
    const prequal = page.getByRole("heading", { name: "预审结果" });
    await expect(rateLock.or(prequal).first()).toBeVisible();
  });

  test("should display application summary with loan details", async ({
    page,
  }) => {
    const summaryHeading = page.getByRole("heading", {
      name: "申请摘要",
    });
    await expect(summaryHeading).toBeVisible();
  });

  test("should show loan amount in summary card", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /申请编号 #/ })).toBeVisible({
      timeout: 10_000,
    });

    // Summary card should display a formatted currency value (may have multiple: property value + loan amount)
    const summaryCard = page
      .getByRole("heading", { name: "申请摘要" })
      .locator("../..");
    await expect(summaryCard.getByText(/¥[\d,]+/).first()).toBeVisible();
  });

  test("should show the localized China demo scene without internal prompts", async ({
    page,
  }) => {
    await expect(page.getByRole("heading", { name: /申请编号 #/ })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/成都市高新区/)).toBeVisible();
    await expect(page.getByText("请补充最新的房屋保险凭证")).toBeVisible();
    await expect(page.getByText("个人住房贷款要素确认书")).toBeVisible();
    await expect(page.getByText("个人金融信息保护告知书")).toBeVisible();
    await expect(page.getByText("个人征信查询与报送授权书")).toBeVisible();
    await expect(page.getByText("金融消费者权益告知书")).toBeVisible();
    await expect(page.getByText(/\[System context\]/)).toHaveCount(0);
    await expect(page.getByText(/Use application_id=/)).toHaveCount(0);
    await expect(page.getByText(/Aspen Ridge|Elm Street/)).toHaveCount(0);
  });

  test("should allow the authenticated content area to scroll", async ({
    page,
  }) => {
    const scrollArea = page.getByTestId("authenticated-content-scroll");
    await expect(scrollArea).toBeVisible();

    await expect
      .poll(() =>
        scrollArea.evaluate(
          (element) => element.scrollHeight > element.clientHeight,
        ),
      )
      .toBe(true);

    await scrollArea.evaluate((element) =>
      element.scrollTo({ top: element.scrollHeight }),
    );
    await expect
      .poll(() => scrollArea.evaluate((element) => element.scrollTop))
      .toBeGreaterThan(0);
  });

  // C-1 + W-1: Replace three-way OR assertion and waitForTimeout with a
  // deterministic Playwright-native assertion that waits for any valid state.
  test("should show document rows or empty message in documents card", async ({
    page,
  }) => {
    const docsHeading = page.getByRole("heading", { name: "申请材料" });
    await expect(docsHeading).toBeVisible();

    // Documents card should show either document rows or an empty/missing message.
    // Use Playwright's built-in retry instead of a fixed timeout.
    const docsCard = docsHeading.locator("../..");
    await expect(
      docsCard
        .getByText(/尚未上传材料|缺失材料/)
        .or(docsCard.locator(".divide-y > div").first()),
    ).toBeVisible({ timeout: 5_000 });
  });
});
