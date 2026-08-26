// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { LandingPage } from "../../pages/landing.page";

test.describe("Public Chat Panel", () => {
    let landing: LandingPage;

    test.beforeEach(async ({ page }) => {
        landing = new LandingPage(page);
        await landing.goto();
    });

    test("should show chat FAB on landing page", async () => {
        await expect(landing.chatFab).toBeVisible({ timeout: 10_000 });
    });

    test("should open public chat panel when clicking FAB", async () => {
        await expect(landing.chatFab).toBeVisible({ timeout: 10_000 });
        await landing.chatFab.click();
        await expect(landing.chatPanel).toBeVisible();
    });

    test("should show suggestion chips in empty public chat", async () => {
        await expect(landing.chatFab).toBeVisible({ timeout: 10_000 });
        await landing.chatFab.click();
        await expect(landing.chatSuggestions).toBeVisible();
    });

    test("should close public chat panel via close button", async () => {
        await expect(landing.chatFab).toBeVisible({ timeout: 10_000 });
        await landing.chatFab.click();
        await expect(landing.chatPanel).toBeVisible();
        await landing.chatCloseButton.click();
        await expect(landing.chatFab).toBeVisible();
    });

    test("should open guided chat without auto-sending a hero prompt", async ({ page }) => {
        await landing.exploreProductsButton.click();
        await expect(landing.chatPanel).toBeVisible();
        await expect(landing.chatSuggestions).toBeVisible();
        await expect(landing.chatInput).toHaveValue("");
        await expect(
            page.getByText(
                "请介绍 FinCredit Copilot 的端到端授信辅助流程，以及每个 Agent 的职责。",
                { exact: true },
            ),
        ).toHaveCount(0);
    });
});
