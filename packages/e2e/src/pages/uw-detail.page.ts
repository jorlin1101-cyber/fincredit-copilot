// This project was developed with assistance from AI tools.

import type { Locator, Page } from "@playwright/test";

export class UWDetailPage {
    readonly page: Page;

    // Breadcrumb
    readonly queueLink: Locator;
    readonly breadcrumb: Locator;

    // Risk Assessment card
    readonly riskAssessmentHeading: Locator;
    readonly runAssessmentButton: Locator;
    readonly creditMetric: Locator;
    readonly capacityMetric: Locator;
    readonly collateralMetric: Locator;

    // Compliance Checks card
    readonly complianceHeading: Locator;
    readonly runChecksButton: Locator;

    // Conditions card
    readonly conditionsHeading: Locator;
    readonly issueConditionButton: Locator;

    // Recommendation banner
    readonly recommendationBanner: Locator;

    // Decision panel
    readonly decisionHeading: Locator;
    readonly approveRadio: Locator;
    readonly conditionalRadio: Locator;
    readonly suspendRadio: Locator;
    readonly denyRadio: Locator;
    readonly rationaleInput: Locator;
    readonly recordDecisionButton: Locator;

    // Application Summary card
    readonly appSummaryHeading: Locator;

    // Compliance KB card
    readonly complianceKBHeading: Locator;
    readonly kbTopicChips: Locator;

    // Error state
    readonly notFoundMessage: Locator;

    constructor(page: Page) {
        this.page = page;

        this.queueLink = page.getByRole("link", { name: "审批队列" });
        this.breadcrumb = page.getByRole("navigation");

        this.riskAssessmentHeading = page.getByText("补充风险画像").first();
        this.runAssessmentButton = page.getByRole("button", { name: /运行画像|重新运行/ }).first();
        this.creditMetric = page.getByText("征信", { exact: true }).first();
        this.capacityMetric = page.getByText(/偿付能力 DTI/).first();
        this.collateralMetric = page.getByText(/抵押物 LTV/).first();

        this.complianceHeading = page.getByText("合规检查").first();
        this.runChecksButton = page.getByRole("button", { name: /运行检查|重新检查/ }).first();

        this.conditionsHeading = page.getByText(/审批条件/).first();
        this.issueConditionButton = page.getByRole("button", { name: "新增审批条件" });

        this.recommendationBanner = page.getByText(/系统初步提示|辅助建议：|风险画像：/).first();

        this.decisionHeading = page.getByText("人工审批决策");
        this.approveRadio = page.getByLabel("同意", { exact: true });
        this.conditionalRadio = page.getByLabel("有条件同意");
        this.suspendRadio = page.getByLabel("暂缓");
        this.denyRadio = page.getByLabel("拒绝");
        this.rationaleInput = page.getByPlaceholder("请输入可审计的决策理由…");
        this.recordDecisionButton = page.getByRole("button", { name: "生成待确认提案" });

        this.appSummaryHeading = page.getByText("申请摘要");
        this.complianceKBHeading = page.getByText("政策库", { exact: true });
        this.kbTopicChips = page.locator("button").filter({ hasText: /全国个人贷款管理|全国最低首付比例|成都公积金贷款|商转公规则|历史政策冲突|材料与收入一致性/ });

        this.notFoundMessage = page.getByText("未找到该申请");
    }

    async goto(applicationId: number): Promise<void> {
        await this.page.goto(`/underwriter/${applicationId}`);
    }
}
