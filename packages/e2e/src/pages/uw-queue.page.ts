// This project was developed with assistance from AI tools.

import type { Locator, Page } from "@playwright/test";

export class UWQueuePage {
    readonly page: Page;

    // Heading
    readonly heading: Locator;

    // Metric cards
    readonly pendingReviewCard: Locator;
    readonly inProgressCard: Locator;
    readonly decidedTodayCard: Locator;
    readonly avgReviewTimeCard: Locator;

    // Filters
    readonly searchInput: Locator;
    readonly urgencyFilter: Locator;

    // Queue table
    readonly columnHeaders: Locator;
    readonly tableRows: Locator;
    readonly emptyState: Locator;
    readonly showingCount: Locator;

    constructor(page: Page) {
        this.page = page;

        this.heading = page.getByRole("heading", { name: "授信审批工作台" });

        this.pendingReviewCard = page.getByText("待审批", { exact: true });
        this.inProgressCard = page.getByText("处理中", { exact: true });
        this.decidedTodayCard = page.getByText("今日已决策", { exact: true });
        this.avgReviewTimeCard = page.getByText("平均审批时长", { exact: true });

        this.searchInput = page.getByPlaceholder("按借款人姓名或申请编号搜索…");
        this.urgencyFilter = page.locator("select").filter({ has: page.locator("option", { hasText: "全部优先级" }) });

        this.columnHeaders = page.locator("thead th");
        this.tableRows = page.locator("tbody tr");
        this.emptyState = page.getByText("暂无待审批申请。");
        this.showingCount = page.getByText(/当前显示 \d+ \/ \d+ 笔待审批申请/);
    }

    async goto(): Promise<void> {
        await this.page.goto("/underwriter");
    }
}
