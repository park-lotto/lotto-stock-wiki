if (process.env.COMPANY_OPS_E2E !== "1") {
  console.error("E2E 안전 가드 / safety guard: COMPANY_OPS_E2E=1과 명시적인 COMPANY_OPS_URL을 설정하세요; 이 스크립트는 대상 서버에 실제 시험 프로젝트를 생성합니다.");
  process.exit(1);
}

const fs = require("fs");
const path = require("path");
const puppeteer = require(path.resolve(__dirname, "../../../../node_modules/puppeteer"));

const baseUrl = process.env.COMPANY_OPS_URL;
if (!baseUrl) {
  console.error("E2E 안전 가드 / safety guard: COMPANY_OPS_URL은 전용 시험 서버를 명시해야 합니다; 기본 운영 포트 8917에는 이 스크립트를 실행하지 마세요.");
  process.exit(1);
}
const artifacts = path.resolve(__dirname, "../.artifacts");
const browserExecutable = process.env.COMPANY_OPS_BROWSER ||
  "C:/Users/CH/.cache/puppeteer/chrome-headless-shell/win64-148.0.7778.167/chrome-headless-shell-win64/chrome-headless-shell.exe";
fs.mkdirSync(artifacts, {recursive: true});

async function state(page) {
  return page.evaluate(async () => {
    const response = await fetch("/api/state", {cache: "no-store"});
    if (!response.ok) throw new Error(`state ${response.status}`);
    return response.json();
  });
}

async function projectStage(page, title) {
  const data = await state(page);
  const project = data.projects.find(item => item.title === title);
  return project ? {id: project.id, stage: project.stage, version: project.version, blocked: project.blocked} : null;
}

async function activeAssignment(page, title) {
  const data = await state(page);
  const project = data.projects.find(item => item.title === title);
  if (!project) return null;
  return data.assignments.find(item => item.project_id === project.id && item.status === "active") || null;
}

async function expectAssignee(page, title, roleId, stage) {
  await page.waitForFunction(async (expectedTitle, expectedRole, expectedStage) => {
    const response = await fetch("/api/state", {cache: "no-store"});
    const data = await response.json();
    const project = data.projects.find(item => item.title === expectedTitle);
    if (!project || project.current_assignee !== expectedRole || project.stage !== expectedStage) return false;
    return data.assignments.some(item => (
      item.project_id === project.id && item.role_id === expectedRole &&
      item.stage === expectedStage && item.status === "active"
    ));
  }, {timeout: 8000}, title, roleId, stage);
  const assignment = await activeAssignment(page, title);
  if (assignment?.role_id !== roleId || assignment?.stage !== stage) {
    throw new Error(`${stage} 담당자 이동 실패: ${JSON.stringify(assignment)}`);
  }
  await page.waitForFunction((expectedTitle, expectedRole) => {
    const pass = [...document.querySelectorAll('.work-pass')]
      .find(item => item.textContent.includes(expectedTitle));
    const expectedName = expectedRole === 'codex' ? 'Codex' : expectedRole === 'astra' ? 'Astra' : 'Claude';
    return pass?.textContent.includes(expectedName);
  }, {timeout: 8000}, title, roleId);
}

async function waitStage(page, title, stage) {
  await page.waitForFunction(async (expectedTitle, expectedStage) => {
    const response = await fetch("/api/state", {cache: "no-store"});
    const data = await response.json();
    return data.projects.some(item => item.title === expectedTitle && item.stage === expectedStage);
  }, {timeout: 8000}, title, stage);
  if (stage !== "done") {
    await page.waitForSelector("#action-submit:not([disabled])", {timeout: 8000});
  }
}

async function main() {
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: browserExecutable,
    args: ["--disable-gpu", "--no-sandbox"],
  });
  const errors = [];
  let ignoreExpectedHttpError = false;
  const page = await browser.newPage();
  page.on("console", message => {
    if (message.type() === "error") {
      if (ignoreExpectedHttpError && message.text().startsWith("Failed to load resource:")) return;
      errors.push(`console: ${message.text()}`);
    }
  });
  page.on("pageerror", error => errors.push(`page: ${error.message}`));

  try {
    await page.setViewport({width: 1440, height: 1000, deviceScaleFactor: 1});
    await page.goto(baseUrl, {waitUntil: "domcontentloaded", timeout: 15000});
    await page.waitForSelector("#company-makers:not([disabled])", {timeout: 8000});
    const atlasLightStyle = await page.$eval(".atlas-light", element => {
      const style = getComputedStyle(element);
      return {zIndex: style.zIndex, maskImage: style.maskImage || style.webkitMaskImage};
    });
    if (atlasLightStyle.zIndex !== "-1" || atlasLightStyle.maskImage === "none") {
      throw new Error(`아틀라스 광원 스타일 무효: ${JSON.stringify(atlasLightStyle)}`);
    }
    const coreCount = await page.$$eval(".company-core", nodes => nodes.length);
    if (coreCount !== 3) throw new Error(`회사 코어 ${coreCount}개`);
    await page.screenshot({path: path.join(artifacts, "company-atlas-empty.png"), fullPage: true});

    const title = `브라우저 검증 ${Date.now()}`;
    await page.click("#new-project");
    await page.waitForSelector("#create-dialog[open]");
    await page.type("#project-title", title);
    await page.select("#project-team", "improve");
    await page.click("#project-description");
    await page.type("#project-description", "회사 지도에서 저장과 검증 흐름을 실제 확인합니다.");
    await page.click("#create-submit");
    await page.waitForSelector("#detail-dialog[open]");
    await waitStage(page, title, "intake");
    await expectAssignee(page, title, "claude", "intake");
    const liveMetrics = await page.evaluate(() => ({
      active: document.querySelector('#metric-active')?.textContent,
      work: document.querySelector('#metric-work')?.textContent,
      standby: document.querySelector('#metric-standby')?.textContent,
    }));
    if (liveMetrics.active !== "1" || liveMetrics.work !== "1" || liveMetrics.standby !== "3") {
      throw new Error(`관제 지표 갱신 실패: ${JSON.stringify(liveMetrics)}`);
    }
    const created = await projectStage(page, title);
    if (!created?.id) throw new Error("생성한 프로젝트를 API에서 찾지 못함");
    await page.keyboard.press("Escape");
    await new Promise(resolve => setTimeout(resolve, 250));
    const returnedFocus = await page.evaluate(() => ({
      id: document.activeElement?.id || "",
      projectId: document.activeElement?.dataset?.projectId || "",
    }));
    if (returnedFocus.projectId !== created.id && returnedFocus.id !== "new-project") {
      throw new Error(`자동 상세 닫기 포커스 복귀 실패: ${JSON.stringify(returnedFocus)}`);
    }
    await page.click(`.project-row[data-project-id="${created.id}"]`);
    await page.waitForSelector("#detail-dialog[open]");

    for (const [expected, assignee] of [["design", "claude"], ["build", "codex"], ["verify", "astra"]]) {
      await page.select("#project-action", "advance");
      await page.click("#action-submit");
      await waitStage(page, title, expected);
      await expectAssignee(page, title, assignee, expected);
    }

    await page.select("#project-action", "advance");
    const nativeBlocked = await page.$eval("#action-form", form => !form.reportValidity());
    if (!nativeBlocked) throw new Error("근거 없는 완료 폼이 허용됨");
    await page.type("#action-evidence", "실제 브라우저 생성·단계 이동·새로고침을 확인한 캡처");
    await page.type("#action-reviewer", "대표");
    ignoreExpectedHttpError = true;
    await page.click("#action-submit");
    await page.waitForFunction(() => !document.querySelector("#action-error").hidden, {timeout: 5000});
    ignoreExpectedHttpError = false;
    const sameReviewerError = await page.$eval("#action-error", node => node.textContent);
    if (!sameReviewerError.includes("달라야")) throw new Error(`동일 검수자 오류 미표시: ${sameReviewerError}`);
    await page.$eval("#action-reviewer", input => { input.value = ""; });
    await page.type("#action-reviewer", "독립 검증자");
    await page.click("#action-submit");
    await waitStage(page, title, "done");
    await page.waitForFunction(expectedTitle => (
      document.querySelector('#metric-active')?.textContent === '0' &&
      document.querySelector('#metric-work')?.textContent === '0' &&
      document.querySelector('#metric-done')?.textContent === '1' &&
      [...document.querySelectorAll('.work-pass')].some(item => item.textContent.includes(expectedTitle) && item.dataset.stageIndex === '4')
    ), {timeout: 8000}, title);
    await page.screenshot({path: path.join(artifacts, "company-atlas-verified.png"), fullPage: true});

    await page.reload({waitUntil: "domcontentloaded", timeout: 15000});
    await page.waitForSelector("#company-makers:not([disabled])");
    const persisted = await projectStage(page, title);
    if (persisted?.stage !== "done" || persisted.id !== created.id) throw new Error("새로고침 뒤 프로젝트 보존 실패");

    await page.click("#company-hnl");
    const leaked = await page.$$eval("[data-testid='project-row']", (rows, value) => rows.some(row => row.textContent.includes(value)), title);
    if (leaked) throw new Error("다른 회사 화면에 프로젝트 혼입");
    await page.click("#company-makers");

    await page.setViewport({width: 390, height: 844, deviceScaleFactor: 1});
    await page.reload({waitUntil: "domcontentloaded", timeout: 15000});
    await page.waitForSelector("#company-makers:not([disabled])");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (overflow > 1) throw new Error(`모바일 가로 넘침 ${overflow}px`);
    await page.screenshot({path: path.join(artifacts, "company-atlas-mobile.png"), fullPage: true});

    if (errors.length) throw new Error(errors.join("\n"));
    const final = await projectStage(page, title);
    const finalAssignment = await activeAssignment(page, title);
    if (finalAssignment !== null) throw new Error(`완료 뒤 활성 배정 잔존: ${JSON.stringify(finalAssignment)}`);
    process.stdout.write(JSON.stringify({ok: true, title, project_id: final.id, stage: final.stage, assignment_flow: ["claude", "codex", "astra"], screenshots: 3, mobile_overflow: overflow}) + "\n");
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(error.stack || error);
  process.exit(1);
});
