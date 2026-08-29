// This project was developed with assistance from AI tools.

import type { Locator, Page } from "@playwright/test";

export class LODetailPage {
    readonly page: Page;

    // Header
    readonly breadcrumb: Locator;
    readonly requestDocsButton: Locator;
    readonly submitToUWButton: Locator;

    // Tabs
    readonly profileTab: Locator;
    readonly financialTab: Locator;
    readonly documentsTab: Locator;
    readonly conditionsTab: Locator;

    // Profile tab
    readonly borrowerInfoCard: Locator;
    readonly propertyInfoCard: Locator;
    readonly loanDetailsCard: Locator;

    // Documents tab
    readonly docCompletenessCard: Locator;

    // Conditions tab
    readonly conditionsEmptyState: Locator;

    // Documents tab upload
    readonly docUploadZone: Locator;
    readonly docFileInput: Locator;

    // Breadcrumb link
    readonly pipelineLink: Locator;

    // Error state
    readonly notFoundMessage: Locator;

    constructor(page: Page) {
        this.page = page;

        this.breadcrumb = page.getByRole("navigation").filter({ hasText: "客户经理看板" });
        this.pipelineLink = page.getByRole("link", { name: "客户经理看板" });
        this.requestDocsButton = page.getByRole("button", { name: "请求补充材料" });
        this.submitToUWButton = page.getByRole("button", { name: "提交授信审批" });

        this.profileTab = page.getByRole("button", { name: "客户资料" });
        this.financialTab = page.getByRole("button", { name: "财务情况" });
        this.documentsTab = page.getByRole("button", { name: "申请材料", exact: true });
        this.conditionsTab = page.getByRole("button", { name: "审批条件" });

        this.borrowerInfoCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "借款人信息" }) }).first();
        this.propertyInfoCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "房产信息" }) }).first();
        this.loanDetailsCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "贷款信息" }) }).first();

        this.docCompletenessCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "材料完整性" }) }).first();

        this.conditionsEmptyState = page.getByText("当前没有待处理的审批条件。");

        this.docUploadZone = page.getByText(/将材料拖到此处|点击选择文件/);
        this.docFileInput = page.locator('input[type="file"]');

        this.notFoundMessage = page.getByText("未找到该申请");
    }

    async goto(applicationId: number): Promise<void> {
        await this.page.goto(`/loan-officer/${applicationId}`);
    }
}
