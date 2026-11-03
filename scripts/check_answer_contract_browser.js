async (page) => {
  // All AI calls in this QA session are intercepted; fixtures are labelled offline replay.
  const fixtures = __ANSWER_CONTRACT_FIXTURES__; // Embedded by build_answer_contract_browser.py.
  let current = fixtures.incomplete;
  let intercepted = 0;
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/api/ai/ask", async route => {
    intercepted++;
    const request = route.request().postDataJSON();
    if (request.expected_analysis_id !== current.answer.analysis_id) throw Error("QA fixture analysis mismatch");
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(current.answer) });
  });
  await page.route("**/api/analyse", route => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(current.result) }));
  async function show(fixture) {
    current = fixture;
    await page.reload();
    await page.getByRole("button", { name: "AI 分析台", exact: true }).click();
    await page.locator("textarea").first().fill(fixture.question);
    await page.getByRole("button", { name: "分析问题", exact: true }).click();
    await page.locator(".answer").waitFor();
  }
  await show(fixtures.incomplete);
  const panel = page.locator(".answer");
  if (!(await panel.innerText()).includes("模型解释不完整") || !(await panel.innerText()).includes("覆盖4/6")) throw Error("Missing incomplete-answer warning");
  if (await panel.locator("tbody tr").count() !== 6 || await panel.getByRole("cell", { name: "模型漏项", exact: true }).count() !== 2) throw Error("Missing full six-row evidence table");
  await panel.screenshot({ path: "output/playwright/answer-contract-incomplete.png" });
  await show(fixtures.ratio);
  const ratioMore = page.locator(".answer").getByText(/展开补充分析/);
  if (await ratioMore.count()) await ratioMore.click();
  const ratioText = await page.locator(".answer").innerText();
  if (!ratioText.includes("比例") || ratioText.includes("份额 / %")) throw Error("Ratio/percent labels are inconsistent");
  if (!ratioText.includes("已按证据目录规范引用字段")) throw Error("Field normalization is hidden");
  await page.locator(".answer").screenshot({ path: "output/playwright/answer-contract-ratio.png" });
  await show(fixtures.scope);
  const scopeText = await page.locator(".answer").innerText();
  if (!scopeText.includes("未调用模型") || !scopeText.includes("当前范围说明")) throw Error("Scope rule is disguised as model output");
  await show(fixtures.verbose);
  const more = page.locator(".answer").getByText(/展开补充分析/);
  if (!await more.count()) throw Error("Verbose answer has no disclosure");
  const before = await page.locator(".answer").innerText();
  await more.click();
  const after = await page.locator(".answer").innerText();
  if (after.length <= before.length) throw Error("Supplementary claims are not accessible");
  await show(fixtures.wording);
  const wording = await page.locator(".answer").innerText();
  if (!wording.includes("检测到可能的百分比与百分点混用") || wording.includes("所谓增长九百九十九个百分点")) throw Error("Suspicious wording is not guarded");
  await page.locator(".answer").getByText("边界说明含疑似单位混用，查看待复核原文", {exact:true}).click();
  if (!(await page.locator(".answer").innerText()).includes("所谓增长九百九十九个百分点")) throw Error("Original wording lost");
  await page.setViewportSize({ width: 390, height: 844 });
  await show(fixtures.incomplete);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  if (overflow) throw Error("Mobile page has horizontal overflow");
  await page.screenshot({ path: "output/playwright/answer-contract-mobile.png", fullPage: true });
  if (errors.length) throw Error(JSON.stringify(errors));
  return { incompleteCoverage: "4/6 clearly labelled, all 6 evidence rows visible", ratioUnits: "PASS", scopeRuleDisclosure: "PASS", conciseDisclosure: "PASS", wordingGuard: "PASS", mobile: "PASS", interceptedAiRequests: intercepted, realModelRequests: 0, uncaughtErrors: errors };
}
