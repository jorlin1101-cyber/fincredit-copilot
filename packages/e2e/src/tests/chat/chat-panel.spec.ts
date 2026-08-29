// This project was developed with assistance from AI tools.

import { test, expect, type Locator, type Page } from "@playwright/test";

// S-01: Extract repeated "ensure chat visible" pattern into a local helper.
async function ensureChatVisible(page: Page): Promise<Locator> {
    const textarea = page.locator('textarea[placeholder="请输入您的问题…"]').first();
    // Wait for the chat sidebar to render (may take a moment after navigation)
    await textarea.waitFor({ state: "visible", timeout: 10_000 }).catch(() => {
        // On mobile viewports the sidebar is hidden behind a FAB
    });
    if (!(await textarea.isVisible())) {
        const fab = page.locator('button[aria-label="打开智能助手"]');
        if (await fab.isVisible()) await fab.click();
    }
    return textarea;
}

test.describe("Chat Panel", () => {
    test.beforeEach(async ({ page }) => {
        await page.goto("/borrower");
        const clearButton = page.locator('button[aria-label="清空聊天记录"]');
        if (await clearButton.isVisible()) {
            await expect(clearButton).toBeEnabled({ timeout: 15_000 });
            await clearButton.click();
        }
    });

    // This test MUST be first -- later tests send messages via WS which leave
    // conversation history that hides the empty state.
    test("should show empty state with suggestion text before messages", async ({ page }) => {
        await expect(page.getByText(/您好，我是小融/)).toBeVisible({ timeout: 15_000 });
    });

    test("should display chat sidebar on authenticated pages", async ({ page }) => {
        const chatSidebar = page.locator('aside[aria-label="智能助手"]');
        // On desktop, sidebar should be visible; on mobile, FAB button instead
        const sidebarVisible = await chatSidebar.isVisible();
        const fabButton = page.locator('button[aria-label="打开智能助手"]');
        const fabVisible = await fabButton.isVisible();

        expect(sidebarVisible || fabVisible).toBeTruthy();
    });

    test("should accept text in chat input", async ({ page }) => {
        const textarea = await ensureChatVisible(page);
        await textarea.fill("我想了解当前住房贷款申请进度");
        await expect(textarea).toHaveValue("我想了解当前住房贷款申请进度");
    });

    test("should display user message after sending", async ({ page }) => {
        const textarea = await ensureChatVisible(page);

        await textarea.fill("请查询我的申请进度");
        await page.locator('button[aria-label="发送消息"]').click();

        // The user message should appear in the chat
        await expect(page.getByText("请查询我的申请进度")).toBeVisible({ timeout: 5_000 });
    });

    test("should populate input via chat-prefill event with autoSend false", async ({ page }) => {
        const textarea = await ensureChatVisible(page);

        // Dispatch chat-prefill event with autoSend: false
        await page.evaluate(() => {
            window.dispatchEvent(
                new CustomEvent("chat-prefill", {
                    detail: {
                        message: "请帮我查看待补充材料",
                        autoSend: false,
                    },
                }),
            );
        });

        await expect(textarea).toHaveValue("请帮我查看待补充材料");
    });

    test("should auto-send message via chat-prefill with autoSend true", async ({ page }) => {
        await ensureChatVisible(page);

        // Dispatch with autoSend: true -- message should appear in chat, not just in input
        await page.evaluate(() => {
            window.dispatchEvent(
                new CustomEvent("chat-prefill", {
                    detail: {
                        message: "请查询审批条件",
                        autoSend: true,
                    },
                }),
            );
        });

        // The message should appear as a user message bubble (auto-sent)
        // Use .first() since desktop sidebar and mobile panel may both render the text
        await expect(page.getByText("请查询审批条件").first()).toBeVisible({ timeout: 5_000 });
    });

    test("should show clear history button after sending a message and clear on click", async ({ page }) => {
        const textarea = await ensureChatVisible(page);
        const clearButton = page.locator('button[aria-label="清空聊天记录"]');

        // Send a message so the trash button appears
        await textarea.fill("这条消息将被清除");
        await page.locator('button[aria-label="发送消息"]').click();
        await expect(page.getByText("这条消息将被清除").first()).toBeVisible({ timeout: 5_000 });

        // Reload to end the active stream without coupling this UI test to model latency.
        // The persisted user message must still be present and can then be cleared.
        await page.reload();
        await expect(page.getByText("这条消息将被清除").first()).toBeVisible({ timeout: 10_000 });
        await expect(clearButton).toBeVisible();
        await expect(clearButton).toBeEnabled({ timeout: 10_000 });
        await clearButton.click();

        // The message should be gone and empty state should return
        await expect(page.getByText("这条消息将被清除")).toHaveCount(0);
        await expect(page.getByText(/您好，我是小融/)).toBeVisible({ timeout: 5_000 });
    });

    // C-1: Replaced vacuous `ws !== null || true` assertion. The test documents intent
    // clearly: we check whether a WebSocket connection was attempted, and skip rather
    // than trivially pass when the backend is unavailable.
    test("should attempt WebSocket connection", async ({ page }) => {
        // Monitor WebSocket connections
        const wsPromise = page.waitForEvent("websocket", { timeout: 10_000 }).catch(() => null);

        // Navigate to trigger WS connection
        await page.goto("/borrower");

        const ws = await wsPromise;
        // C-1 fix: assert the WS was actually attempted rather than always passing.
        // If the backend is not running this test should be fixed up, not vacuously passed.
        test.fixme(
            ws === null,
            "WebSocket connection depends on backend availability -- start the API server before running E2E tests",
        );
        expect(ws).not.toBeNull();
    });

});
