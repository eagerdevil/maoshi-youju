async (page) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const button = page.getByRole("button", { name: "开始分析", exact: true });
  await button.waitFor({ state: "visible" });
  await button.evaluate((el) => {
    // Reproduce the DOM mutation seen with translation extensions.
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) if (walker.currentNode.textContent.trim()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const translated = document.createElement("font");
      translated.textContent = node.textContent;
      node.parentNode.replaceChild(translated, node);
    }
  });
  async function analyse(name) {
    const response = page.waitForResponse((r) => r.url().endsWith("/api/analyse") && r.request().method() === "POST");
    await button.click();
    const result = await response;
    await page.waitForTimeout(250);
    if (result.status() !== 200 || await page.locator("main").count() !== 1 || await page.locator(".display-recovery").count()) {
      throw Error("Display regression: " + name + " " + JSON.stringify(errors));
    }
  }
  await analyse("translated-button");
  await page.getByRole("button", { name: "AI 分析台", exact: true }).click();
  await analyse("AI-tab");
  await page.getByRole("button", { name: "多国表现比较", exact: true }).click();
  await analyse("comparison");
  await page.getByRole("button", { name: "双边贸易分析", exact: true }).click();
  await analyse("bilateral");
  await page.getByRole("button", { name: "目标市场竞争", exact: true }).click();
  await page.getByRole("button", { name: "分析总览", exact: true }).click();
  await analyse("competition");
  if (errors.length) throw Error(JSON.stringify(errors));

  await page.evaluate(() => {
    window.__qaCanvasOriginal = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function () { throw Error("QA simulated canvas failure"); };
  });
  await analyse("canvas-failure-isolated");
  if (!await page.locator(".chart-recovery").count()) throw Error("Chart recovery panel missing");
  await page.screenshot({ path: "output/playwright/blankfix-chart-recovery.png" });
  await page.evaluate(() => { HTMLCanvasElement.prototype.getContext = window.__qaCanvasOriginal; });
  while (await page.getByRole("button", { name: "重试图表", exact: true }).count()) {
    await page.getByRole("button", { name: "重试图表", exact: true }).first().click();
    await page.waitForTimeout(100);
  }
  await page.screenshot({ path: "output/playwright/blankfix-after.png" });
  return { translatedButton: "PASS", modes: 3, AI: "PASS", chartFailureRecovery: "PASS", uncaughtErrors: errors };
}
