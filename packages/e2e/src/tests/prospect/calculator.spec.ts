// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { LandingPage } from "../../pages/landing.page";

test.describe("中国商业住房贷款购房预算测算", () => {
  let landing: LandingPage;

  test.beforeEach(async ({ page }) => {
    landing = new LandingPage(page);
    await landing.goto();
  });

  test("should accept income, debts, and down payment inputs", async () => {
    await expect(landing.calculatorForm).toBeVisible();
    await expect(landing.incomeInput).toBeVisible();
    await expect(landing.debtsInput).toBeVisible();
    await expect(landing.downPaymentInput).toBeVisible();
  });

  test("should display estimated home budget after submission", async ({
    page,
  }) => {
    await landing.incomeInput.fill("20000");
    await landing.debtsInput.fill("2000");
    await landing.downPaymentInput.fill("300000");
    await landing.calculateButton.click();

    // Wait for a renminbi result to appear.
    await expect(landing.estimatedBudget).toHaveText(/[¥￥][\d,]+/, {
      timeout: 10_000,
    });
  });

  test("should display estimated monthly payment after submission", async ({
    page,
  }) => {
    await landing.incomeInput.fill("20000");
    await landing.debtsInput.fill("2000");
    await landing.downPaymentInput.fill("300000");
    await landing.calculateButton.click();

    await expect(landing.estimatedPayment).toHaveText(/[¥￥][\d,]+/, {
      timeout: 10_000,
    });
  });

  test("should show DTI warning for high-debt scenario", async ({ page }) => {
    await landing.incomeInput.fill("20000");
    await landing.debtsInput.fill("12000");
    await landing.downPaymentInput.fill("300000");
    await landing.calculateButton.click();

    // High DTI should show the blocking warning with amber styling
    await expect(page.getByText("当前偿债空间不足")).toBeVisible({
      timeout: 10_000,
    });
  });

  test("should open chat when clicking Ask our assistant button", async () => {
    await expect(landing.askAssistantButton).toBeVisible();
    await landing.askAssistantButton.click();

    // Public chat panel should open
    await expect(landing.chatPanel).toBeVisible();
  });
});
