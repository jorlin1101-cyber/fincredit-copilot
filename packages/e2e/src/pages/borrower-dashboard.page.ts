// This project was developed with assistance from AI tools.

import type { Locator, Page } from "@playwright/test";

export class BorrowerDashboardPage {
    readonly page: Page;

    // Status card
    readonly statusCard: Locator;
    readonly applicationHeading: Locator;

    // Dashboard cards
    readonly documentsCard: Locator;
    readonly conditionsCard: Locator;
    readonly disclosuresCard: Locator;
    readonly rateLockCard: Locator;
    readonly prequalCard: Locator;
    readonly summaryCard: Locator;

    // Documents
    readonly uploadZone: Locator;
    readonly fileInput: Locator;

    // Disclosures
    readonly acknowledgeButton: Locator;

    constructor(page: Page) {
        this.page = page;

        this.statusCard = page.locator("div").filter({ has: page.getByRole("heading", { name: /申请编号 #/ }) }).first();
        this.applicationHeading = page.getByRole("heading", { name: /申请编号 #/ });

        this.documentsCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "申请材料" }) }).first();
        this.conditionsCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "审批条件" }) }).first();
        this.disclosuresCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "信息披露" }) }).first();
        this.rateLockCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "利率锁定" }) }).first();
        this.prequalCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "预审结果" }) }).first();
        this.summaryCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "申请摘要" }) }).first();

        this.uploadZone = page.getByRole("button", { name: /将材料拖到此处|点击选择文件/ });
        this.fileInput = page.locator('input[type="file"]');

        this.acknowledgeButton = page.getByRole("button", {
            name: "查看并确认",
        });
    }

    async goto(): Promise<void> {
        await this.page.goto("/borrower");
    }
}
