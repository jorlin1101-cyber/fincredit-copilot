// This project was developed with assistance from AI tools.

import type { Locator, Page } from "@playwright/test";

export class LOPipelinePage {
    readonly page: Page;

    // Heading
    readonly heading: Locator;

    // Metric cards
    readonly activeLoansCard: Locator;
    readonly inUnderwritingCard: Locator;
    readonly criticalUrgencyCard: Locator;
    readonly avgDaysCard: Locator;

    // Filters
    readonly searchInput: Locator;
    readonly stageFilter: Locator;
    readonly urgencyFilter: Locator;
    readonly stalledCheckbox: Locator;
    readonly columnHeaders: Locator;

    // Pipeline table
    readonly tableRows: Locator;
    readonly emptyState: Locator;

    constructor(page: Page) {
        this.page = page;

        this.heading = page.getByRole("heading", { name: "客户经理业务看板" });

        this.activeLoansCard = page.locator("div").filter({ has: page.getByText("在途申请") }).first();
        this.inUnderwritingCard = page.locator("div").filter({ has: page.getByText("授信审批中") }).first();
        this.criticalUrgencyCard = page.locator("div").filter({ has: page.getByText("紧急事项") }).first();
        this.avgDaysCard = page.locator("div").filter({ has: page.getByText("平均阶段时长") }).first();

        this.searchInput = page.getByPlaceholder("按借款人姓名或申请编号搜索…");
        // Identify each select by its unique first/default option text
        this.stageFilter = page.locator("select").filter({ has: page.locator("option", { hasText: "全部阶段" }) });
        this.urgencyFilter = page.locator("select").filter({ has: page.locator("option", { hasText: "全部优先级" }) });
        this.stalledCheckbox = page.getByLabel("仅看停滞申请");
        this.columnHeaders = page.locator("thead th");

        this.tableRows = page.locator("tbody tr");
        this.emptyState = page.getByText("没有符合当前筛选条件的申请。");
    }

    async goto(): Promise<void> {
        await this.page.goto("/loan-officer");
    }
}
