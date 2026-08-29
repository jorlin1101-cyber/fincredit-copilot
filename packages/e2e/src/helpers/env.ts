// This project was developed with assistance from AI tools.

/**
 * E2E environment configuration and auth mode detection.
 */

export const BASE_URL = process.env.MORTGAGE_E2E_BASE_URL || process.env.BASE_URL || "http://localhost:5173";
export const API_URL = process.env.API_URL || "http://localhost:8000";
export const KEYCLOAK_URL = process.env.KEYCLOAK_URL || "http://localhost:8080";
export const IS_DEV_AUTH = process.env.E2E_DEV_AUTH === "true";
export const COMPANY_NAME = process.env.COMPANY_NAME || "融安住房金融（虚构演示机构）";

export const DEV_PASSWORD = process.env.E2E_DEV_PASSWORD || "demo1234";
export const KEYCLOAK_PASSWORD = process.env.E2E_KEYCLOAK_PASSWORD || "demo";

export function getPassword(): string {
  return IS_DEV_AUTH ? DEV_PASSWORD : KEYCLOAK_PASSWORD;
}

export const PERSONAS = {
  borrower: {
    title: "借款人",
    testId: "persona-borrower",
    email: "li.xiaoyu@example.com",
    homeRoute: "/borrower",
  },
  loan_officer: {
    title: "客户经理",
    testId: "persona-loan_officer",
    email: "wang.chen@example.com",
    homeRoute: "/loan-officer",
  },
  underwriter: {
    title: "审批人员",
    testId: "persona-underwriter",
    email: "chen.jing@example.com",
    homeRoute: "/underwriter",
  },
  ceo: {
    title: "管理驾驶舱",
    testId: "persona-ceo",
    email: "zhou.mingyuan@example.com",
    homeRoute: "/ceo",
  },
} as const;

export type PersonaKey = keyof typeof PERSONAS;
