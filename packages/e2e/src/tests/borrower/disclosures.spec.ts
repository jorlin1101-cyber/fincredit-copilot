// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { BorrowerDashboardPage } from "../../pages/borrower-dashboard.page";

test.describe("Borrower Disclosures", () => {
    test.describe.configure({ mode: "serial" });
    let dashboard: BorrowerDashboardPage;

    test.beforeEach(async ({ page }) => {
        dashboard = new BorrowerDashboardPage(page);
        await dashboard.goto();
    });

    test("should show disclosures list or all-acknowledged message", async ({ page }) => {
        const disclosuresHeading = page.getByRole("heading", { name: "信息披露" });
        await expect(disclosuresHeading).toBeVisible();

        const allAcknowledged = page.getByText("信息披露均已确认");
        const reviewButton = page.getByRole("button", {
            name: "查看并确认",
        });

        const isAllDone = await allAcknowledged.isVisible();
        const hasPending = (await reviewButton.count()) > 0;

        expect(isAllDone || hasPending).toBeTruthy();
    });

    test("should open disclosure modal on Review & Acknowledge click", async ({ page }) => {
        const reviewButton = page.getByRole("button", {
            name: "查看并确认",
        });
        await expect(reviewButton.first()).toBeVisible({ timeout: 10_000 });

        await reviewButton.first().click();
        await expect(dashboard.disclosureModal).toBeVisible();
    });

    test("should close disclosure modal via close button", async ({ page }) => {
        const reviewButton = page.getByRole("button", {
            name: "查看并确认",
        });
        await expect(reviewButton.first()).toBeVisible({ timeout: 10_000 });

        await reviewButton.first().click();
        await expect(dashboard.disclosureModal).toBeVisible();

        await dashboard.modalCloseButton.click();
        await expect(dashboard.disclosureModal).not.toBeVisible();
    });

    test("should immediately show acknowledgment without sending a chat message", async ({ page }) => {
        const reviewButton = page.getByRole("button", {
            name: "查看并确认",
        });

        const beforeCount = await reviewButton.count();
        if (beforeCount > 0) {
            await reviewButton.first().click();
            await expect(dashboard.disclosureModal).toBeVisible();
            await dashboard.modalAcknowledgeButton.click();
            await expect(dashboard.disclosureModal).not.toBeVisible();
            await expect(reviewButton).toHaveCount(beforeCount - 1);
            await expect(page.getByText(/我已阅读并确认《/)).toHaveCount(0);
        }
    });
});
