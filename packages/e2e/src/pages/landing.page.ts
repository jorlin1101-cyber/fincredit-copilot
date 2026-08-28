// This project was developed with assistance from AI tools.

import type { Locator, Page } from "@playwright/test";
import { COMPANY_NAME } from "../helpers/env";

export class LandingPage {
  readonly page: Page;
  readonly heroHeading: Locator;
  readonly getPreQualifiedLink: Locator;
  readonly exploreProductsButton: Locator;
  readonly brandingText: Locator;

  // Affordability calculator
  readonly calculatorForm: Locator;
  readonly incomeInput: Locator;
  readonly debtsInput: Locator;
  readonly downPaymentInput: Locator;
  readonly interestRateInput: Locator;
  readonly calculateButton: Locator;
  readonly estimatedBudget: Locator;
  readonly estimatedPayment: Locator;
  readonly calculatorError: Locator;
  readonly dtiWarning: Locator;
  readonly askAssistantButton: Locator;

  // Public chat
  readonly chatFab: Locator;
  readonly chatPanel: Locator;
  readonly chatCloseButton: Locator;
  readonly chatInput: Locator;
  readonly chatSuggestions: Locator;

  constructor(page: Page) {
    this.page = page;
    this.heroHeading = page.getByRole("heading", { level: 1 });
    this.getPreQualifiedLink = page.getByRole("link", {
      name: "登录服务平台",
    });
    this.exploreProductsButton = page.getByRole("button", {
      name: "咨询智能助手",
    });
    this.brandingText = page.getByText(COMPANY_NAME).first();

    this.calculatorForm = page.getByRole("form", { name: "购房预算测算表单" });
    this.incomeInput = page.locator("#gross_monthly_income");
    this.debtsInput = page.locator("#monthly_debts");
    this.downPaymentInput = page.locator("#down_payment");
    this.interestRateInput = page.locator("#interest_rate");
    this.calculateButton = page.getByRole("button", { name: "开始测算" });
    this.estimatedBudget = page.getByTestId("estimated-home-budget");
    this.estimatedPayment = page.getByTestId("estimated-monthly-payment");
    this.calculatorError = page
      .getByRole("alert")
      .filter({ hasText: "暂时无法完成测算" });
    this.dtiWarning = page.getByRole("alert").first();
    this.askAssistantButton = page.getByRole("button", {
      name: /咨询小融/,
    });

    this.chatFab = page.locator('button[aria-label="打开智能助手"]');
    this.chatPanel = page.locator('aside[aria-label="智能助手"]');
    this.chatCloseButton = page.locator('button[aria-label="关闭智能助手"]');
    this.chatInput = page.locator(
      'input[type="text"][placeholder="请输入您的问题…"]',
    );
    this.chatSuggestions = page.getByRole("button", {
      name: /住房贷款一般需要经过哪些流程/,
    });
  }

  async goto(): Promise<void> {
    await this.page.goto("/");
  }
}
