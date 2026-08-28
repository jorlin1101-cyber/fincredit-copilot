// This project was developed with assistance from AI tools.

import type { Locator, Page } from "@playwright/test";

export class CeoDashboardPage {
    readonly page: Page;

    // Heading
    readonly heading: Locator;
    readonly subtitle: Locator;

    // Pipeline Overview card
    readonly pipelineCard: Locator;
    readonly pullThroughRate: Locator;
    readonly avgDaysToClose: Locator;
    readonly activeApplications: Locator;

    // Denial Analysis card
    readonly denialCard: Locator;
    readonly overallDenialRate: Locator;
    readonly topDenialReasons: Locator;

    // LO Performance card
    readonly loPerformanceCard: Locator;
    readonly loTable: Locator;
    readonly loTableRows: Locator;

    // Model Health card
    readonly modelHealthCard: Locator;
    readonly latencyP50: Locator;
    readonly latencyP95: Locator;
    readonly latencyP99: Locator;
    readonly monitoringUnavailable: Locator;

    // Audit Events card
    readonly auditCard: Locator;
    readonly auditTable: Locator;
    readonly auditTableHeaders: Locator;
    readonly auditTableRows: Locator;
    readonly viewFullAuditTrail: Locator;

    // Footer
    readonly disclaimer: Locator;

    constructor(page: Page) {
        this.page = page;

        this.heading = page.getByRole("heading", { name: "管理驾驶舱" });
        this.subtitle = page.getByText("住房贷款业务运行概览");

        this.pipelineCard = page.getByText("业务申请概览");
        this.pullThroughRate = page.getByText("申请转化率");
        this.avgDaysToClose = page.getByText("平均结案时长");
        this.activeApplications = page.getByText("当前申请数");

        this.denialCard = page.getByText("未通过申请分析");
        this.overallDenialRate = page.getByText("总体未通过率");
        this.topDenialReasons = page.getByText("主要未通过原因");

        this.loPerformanceCard = page.getByText("客户经理业务表现");
        this.loTable = page.locator("table").filter({ has: page.getByText("未通过率") });
        this.loTableRows = this.loTable.locator("tbody tr");

        this.modelHealthCard = page.getByText("AI Model Health");
        this.latencyP50 = page.getByText("P50");
        this.latencyP95 = page.getByText("P95");
        this.latencyP99 = page.getByText("P99");
        this.monitoringUnavailable = page.getByText("Monitoring Unavailable");

        this.auditCard = page.getByText("最近操作记录");
        this.auditTable = page.locator("table").filter({ has: page.getByText("操作类型") });
        this.auditTableHeaders = this.auditTable.locator("thead th");
        this.auditTableRows = this.auditTable.locator("tbody tr");
        this.viewFullAuditTrail = page.getByText("查看全部操作记录");

        this.disclaimer = page.getByText("本平台及其中展示的机构、人员、申请与审批数据均为虚构演示内容");
    }

    async goto(): Promise<void> {
        await this.page.goto("/ceo");
    }
}
