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

    test("should require reading confirmation before showing acknowledgment", async ({ page }) => {
        const reviewButton = page.getByRole("button", {
            name: "查看并确认",
        });

        const beforeCount = await reviewButton.count();
        if (beforeCount > 0) {
            await reviewButton.first().click();
            const dialog = page.getByRole("dialog");
            await expect(dialog).toBeVisible();

            const submitButton = dialog.getByRole("button", {
                name: "确认并提交",
            });
            await expect(submitButton).toBeDisabled();

            await dialog.getByRole("checkbox").check();
            await expect(submitButton).toBeEnabled();

            const responsePromise = page.waitForResponse(
                (response) =>
                    response.url().includes("/disclosures/") &&
                    response.url().endsWith("/acknowledge") &&
                    response.request().method() === "POST",
            );
            await submitButton.click();
            expect((await responsePromise).ok()).toBeTruthy();
            await expect(dialog).not.toBeVisible();

            if (beforeCount > 1) {
                await expect(reviewButton).toHaveCount(beforeCount - 1);
            } else {
                await expect(page.getByText("信息披露均已确认")).toBeVisible();
            }
            await expect(page.getByText(/我已阅读并确认《/)).toHaveCount(0);
        }
    });
});
