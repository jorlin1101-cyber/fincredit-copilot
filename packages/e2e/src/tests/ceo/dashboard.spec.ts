// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { CeoDashboardPage } from "../../pages/ceo-dashboard.page";

let dashboard: CeoDashboardPage;

test.beforeEach(async ({ page }) => {
    dashboard = new CeoDashboardPage(page);
    await dashboard.goto();
    await expect(dashboard.heading).toBeVisible();
});

test.describe("CEO Executive Dashboard", () => {
    test("should display dashboard heading and subtitle", async () => {
        await expect(dashboard.heading).toHaveText("管理驾驶舱");
        await expect(dashboard.subtitle).toBeVisible();
    });

    test("should display all dashboard cards", async () => {
        await expect(dashboard.pipelineCard).toBeVisible();
        await expect(dashboard.denialCard).toBeVisible();
        await expect(dashboard.loPerformanceCard).toBeVisible();
        await expect(dashboard.auditCard).toBeVisible();
    });

    test("should display pipeline card with stage bars and stats", async () => {
        await expect(dashboard.pullThroughRate).toBeVisible();
        await expect(dashboard.avgDaysToClose).toBeVisible();
        await expect(dashboard.activeApplications).toBeVisible();
    });

    test("should display denial analysis card with bar chart and reasons", async () => {
        await expect(dashboard.overallDenialRate).toBeVisible();
        await expect(dashboard.topDenialReasons).toBeVisible();
    });

    test("should display LO performance card with table columns", async () => {
        const headers = dashboard.loTable.locator("thead th");
        await expect(headers.nth(0)).toHaveText("客户经理");
        await expect(headers.nth(1)).toHaveText("在办申请");
        await expect(headers.nth(2)).toHaveText("已结案");
        await expect(headers.nth(3)).toHaveText("未通过率");
    });

    test("should display at least one loan officer row", async () => {
        await expect(dashboard.loTableRows.first()).toBeVisible();
    });

    test("should display audit events card with table columns", async () => {
        await expect(dashboard.auditTableHeaders.nth(0)).toHaveText("时间");
        await expect(dashboard.auditTableHeaders.nth(1)).toHaveText("操作类型");
        await expect(dashboard.auditTableHeaders.nth(2)).toHaveText("操作角色");
        await expect(dashboard.auditTableHeaders.nth(3)).toHaveText("说明");
    });

    test("should display view full audit trail link", async () => {
        await expect(dashboard.viewFullAuditTrail).toBeVisible();
    });

    test("should display regulatory disclaimer footer", async () => {
        await expect(dashboard.disclaimer).toBeVisible();
    });
});
