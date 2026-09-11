"use strict";

/* DOM and formatting. API strings and user input only enter text nodes. */
const $ = id => document.getElementById(id);
const SVG_NS = "http://www.w3.org/2000/svg";
const PAGE_SIZE = 50;
const POLL_INTERVAL = 5000;
const COMPANY_MARKS = {makers: "M", hnl: "H", stock: "S"};
const EVENT_LABELS = {created: "프로젝트 접수", assigned: "담당 역할 자동 배정", advance: "다음 단계로 인계", block: "흐름 차단", resume: "업무 재개", reject: "검수 반려 · 구현으로 복귀"};
const STAGE_ROOMS = {
  intake: {number: "01", place: "접수실", verb: "문제를 일로 바꿉니다", work: "요청 · 목표 · 책임자를 기록", exit: "목표와 담당 팀이 정해지면 설계실로"},
  design: {number: "02", place: "설계실", verb: "해결할 방법을 정합니다", work: "범위 · 규칙 · 완료 조건을 확정", exit: "실행 가능한 계획이 기록되면 제작실로"},
  build: {number: "03", place: "제작실", verb: "결과물을 만듭니다", work: "코드 · 영상 · 문서를 실제로 제작", exit: "산출물과 확인 결과가 있으면 검증실로"},
  verify: {number: "04", place: "검증실", verb: "실제로 되는지 확인합니다", work: "실사용 · 오류 · 완료 조건을 대조", exit: "별도 검수자와 근거가 있으면 완료 보관실로"},
  done: {number: "05", place: "완료 보관실", verb: "승인된 결과를 남깁니다", work: "검증 근거 · 결정 · 전체 이력을 보존", exit: "완료 · 필요하면 새 프로젝트로 다시 시작"},
};
let state = null;
let companyId = "makers";
let teamFilter = null;
let activeView = "organization";
let selectedId = null;
let detailProject = null;
let createCompanyId = null;
let writing = false;
let refreshPromise = null;
let refreshAgain = false;
let highWaterEventId = null;
let detailEvents = new Map();
let eventsCursor = null;
let eventsHasMore = false;
let eventsBusy = false;
let eventsGeneration = 0;
let inspectedProjectId = null;
let replaying = false;
const renderKeys = new Map();
const dialogReturnTargets = new Map();
const mediaMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
let motionPreference = true;
try { motionPreference = localStorage.getItem("company-ops-motion") !== "off"; } catch (_) { /* Storage is optional. */ }

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = String(text);
  return element;
}
function put(id, text) {
  const element = $(id);
  const value = String(text ?? "");
  if (element.textContent !== value) element.textContent = value;
}
function showError(id, message) {
  put(id, message || "");
  $(id).hidden = !message;
}
function sameRender(key, value) {
  const signature = JSON.stringify(value);
  if (renderKeys.get(key) === signature) return true;
  renderKeys.set(key, signature);
  return false;
}
const company = () => state?.companies.find(item => item.id === companyId);
const companyProjects = () => state ? state.projects.filter(item => item.company_id === companyId) : [];
const projectById = id => state?.projects.find(item => item.id === id);
const projectRow = id => [...$("project-list").querySelectorAll("[data-project-id]")].find(item => item.dataset.projectId === id) || null;
const teamName = id => state?.teams.find(item => item.id === id)?.name || id;
const stageName = id => state?.stages.find(item => item.id === id)?.label || id;
const roleName = id => state?.roles.find(item => item.id === id)?.name || id || "완료";
const eventClass = kind => ({block: "blocked", reject: "rejected"}[kind] || kind);
function dateText(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "시각 확인 필요" : date.toLocaleString("ko-KR", {month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit"});
}
function motionEnabled() { return motionPreference && !mediaMotion.matches; }
function updateMotion() {
  const enabled = motionEnabled();
  document.body.dataset.motion = enabled ? "on" : "off";
  $("motion-toggle").setAttribute("aria-pressed", String(enabled));
  $("motion-toggle").setAttribute("aria-label", mediaMotion.matches ? "기기 설정에 따라 화면 움직임 꺼짐" : "화면 움직임 " + (enabled ? "끄기" : "켜기"));
  put("motion-label", enabled ? "움직임 켜짐" : "움직임 꺼짐");
  $("motion-toggle").title = mediaMotion.matches ? "기기의 움직임 줄이기 설정을 따릅니다." : "";
  if (!enabled) clearPulses();
}
function announce(text) { put("announcement", text); }
function apiMessage(data) {
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map(item => {
    const field = Array.isArray(item.loc) ? item.loc.filter(part => part !== "body").join(" · ") : "";
    return (field ? field + ": " : "") + (item.msg || "입력을 확인해 주세요.");
  }).join("\n");
  return "요청을 처리하지 못했습니다. 입력과 서버 상태를 확인해 주세요.";
}
async function api(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const options = {cache: "no-store", signal: controller.signal};
    if (body !== undefined) Object.assign(options, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    const response = await fetch(path, options);
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const err = new Error(apiMessage(data));
      err.status = response.status;
      throw err;
    }
    if (data === null) throw new Error("서버 응답을 읽지 못했습니다.");
    return data;
  } catch (err) {
    if (err.name === "AbortError") throw new Error("서버 응답이 지연되고 있습니다. 마지막 조회 시각을 확인해 주세요.");
    throw err;
  } finally { clearTimeout(timeout); }
}

/* Build stable interactive nodes. Polling updates labels, not focus or user selections. */
function buildCompanyNavigation() {
  if (sameRender("company-catalog", state.companies)) return;
  $("company-nav").replaceChildren(...state.companies.map(item => {
    const button = node("button", "company-core");
    button.type = "button";
    button.id = "company-" + item.id;
    button.dataset.testid = button.id;
    button.dataset.company = item.id;
    const frame = node("span", "core-frame");
    frame.setAttribute("aria-hidden", "true");
    frame.append(node("span", "core-meridian"), node("span", "core-equator"), node("span", "core-letter", COMPANY_MARKS[item.id] || "·"));
    button.append(frame, node("span", "core-label", item.name), node("span", "core-caption", "회사 탐색 ↗"));
    button.addEventListener("click", () => selectCompany(item.id));
    return button;
  }));
}
function renderCompanyNavigation() {
  buildCompanyNavigation();
  const others = state.companies.filter(item => item.id !== companyId);
  for (const item of state.companies) {
    const button = $("company-" + item.id);
    const selected = item.id === companyId;
    button.setAttribute("aria-current", String(selected));
    button.setAttribute("aria-label", item.name + (selected ? " · 현재 선택한 회사" : " · 회사 선택"));
    button.dataset.position = selected ? "center" : others.indexOf(item) === 0 ? "left" : "right";
  }
}
function roleNode(role) {
  const item = node("div", "role-node");
  item.dataset.role = role.id;
  item.title = role.role + " · " + role.status;
  const monogram = node("span", "role-monogram", role.name.slice(0, 1));
  monogram.setAttribute("aria-hidden", "true");
  const status = node("small", "role-load", "배정 0건");
  status.setAttribute("aria-label", role.status);
  item.append(monogram, node("strong", "", role.name), status);
  item.setAttribute("aria-label", role.name + " · " + role.role + " · " + role.status);
  return item;
}
function metric(id, value) {
  const target = $(id);
  const next = String(value);
  if (target.textContent === next) return;
  target.textContent = next;
  if (!motionEnabled()) return;
  target.classList.remove("metric-hit");
  void target.offsetWidth;
  target.classList.add("metric-hit");
}
function renderMetrics() {
  const projects = companyProjects();
  const open = projects.filter(project => project.stage !== "done");
  const assignments = state.assignments.filter(item => item.company_id === companyId && ["active", "blocked"].includes(item.status));
  const activeRoles = new Set(assignments.filter(item => item.status === "active").map(item => item.role_id));
  metric("metric-active", activeRoles.size);
  metric("metric-work", open.length);
  metric("metric-standby", Math.max(0, state.roles.length - activeRoles.size));
  metric("metric-blocked", open.filter(project => project.blocked).length);
  metric("metric-done", projects.filter(project => project.stage === "done").length);
  metric("metric-events", state.events.filter(event => event.company_id === companyId).length);
}
function buildOrganization() {
  if (!sameRender("roles", state.roles)) {
    $("planning-roles").replaceChildren(...state.roles.filter(role => role.group === "planning").map(roleNode));
    $("execution-roles").replaceChildren(...state.roles.filter(role => role.group === "execution").map(roleNode));
  }
  if (sameRender("teams", state.teams)) return;
  $("team-routes").replaceChildren();
  $("team-nodes").replaceChildren(...state.teams.map((team, index) => {
    const card = node("article", "department-card");
    card.dataset.teamId = team.id;
    const button = node("button", "team-node");
    button.type = "button";
    button.id = "team-" + team.id;
    button.dataset.testid = "team-" + team.id;
    button.dataset.teamId = team.id;
    button.title = team.description;
    const heading = node("span", "team-heading");
    heading.append(node("span", "team-index", String(index + 1).padStart(2, "0")), node("span", "team-name", team.name));
    button.append(heading, node("span", "team-description", team.description), node("span", "team-load"), node("span", "team-enter", "내부 보기 →"));
    button.addEventListener("click", () => selectTeam(teamFilter === team.id ? null : team.id, true));
    card.append(button);
    return card;
  }));
  buildProcessFloor();
}
function renderOrganization() {
  buildOrganization();
  const all = companyProjects();
  for (const team of state.teams) {
    const list = all.filter(project => project.team_id === team.id && project.stage !== "done");
    const blocked = list.filter(project => project.blocked).length;
    const selected = teamFilter === team.id;
    const button = $("team-" + team.id);
    const card = button.closest(".department-card");
    button.classList.toggle("active", selected);
    button.classList.toggle("is-blocked", blocked > 0);
    card.classList.toggle("active", selected);
    card.classList.toggle("is-blocked", blocked > 0);
    button.setAttribute("aria-pressed", String(selected));
    const load = "열린 업무 " + list.length + (blocked ? " · 차단 " + blocked : "");
    button.querySelector(".team-load").textContent = load;
    button.setAttribute("aria-label", team.name + " · " + load + " · 프로젝트 필터");
  }
  for (const role of state.roles) {
    const active = state.assignments.filter(item => item.company_id === companyId && item.role_id === role.id && ["active", "blocked"].includes(item.status));
    const target = document.querySelector(`.role-node[data-role="${role.id}"]`);
    if (!target) continue;
    target.classList.toggle("has-work", active.length > 0);
    target.classList.toggle("has-blocked-work", active.some(item => item.status === "blocked"));
    target.querySelector(".role-load").textContent = active.length ? `배정 ${active.length}건` : "대기";
  }
  renderProcessFloor();
}

function buildProcessFloor() {
  if ($("stage-rooms").children.length) return;
  $("stage-rooms").replaceChildren(...state.stages.map(stage => {
    const info = STAGE_ROOMS[stage.id];
    const room = node("article", "stage-room");
    room.dataset.stage = stage.id;
    const head = node("header");
    head.append(node("span", "room-number", info.number), node("strong", "", info.place), node("span", "room-count", "0"));
    room.append(head, node("p", "room-verb", info.verb), node("p", "room-work", info.work));
    const threshold = node("div", "room-threshold");
    threshold.append(node("span", "", "다음 방 조건"), node("small", "", info.exit));
    room.append(threshold);
    return room;
  }));
}

function activeAssignment(project) {
  return state.assignments.find(item => item.project_id === project.id && ["active", "blocked"].includes(item.status));
}

function elapsedText(value) {
  const started = new Date(value).getTime();
  if (!Number.isFinite(started)) return "시작 시각 확인 필요";
  const seconds = Math.max(0, Math.floor((Date.now() - started) / 1000));
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days) return `${days}일 ${hours}시간 경과`;
  if (hours) return `${hours}시간 ${minutes}분 경과`;
  return `${minutes}분 ${String(seconds % 60).padStart(2, "0")}초 경과`;
}

function renderProcessFloor() {
  const visible = companyProjects().filter(project => !teamFilter || project.team_id === teamFilter);
  if (!visible.some(project => project.id === inspectedProjectId)) inspectedProjectId = visible.find(project => project.stage !== "done")?.id || visible[0]?.id || null;
  for (const room of $("stage-rooms").children) {
    const count = visible.filter(project => project.stage === room.dataset.stage).length;
    room.querySelector(".room-count").textContent = `${count}건`;
    room.classList.toggle("is-occupied", count > 0);
    room.classList.toggle("is-selected", visible.some(project => project.id === inspectedProjectId && project.stage === room.dataset.stage));
  }
  const keep = new Set(visible.map(project => project.id));
  for (const old of [...$("work-stream").children]) if (!keep.has(old.dataset.projectId)) old.remove();
  visible.forEach((project, lane) => {
    let pass = [...$("work-stream").children].find(item => item.dataset.projectId === project.id);
    const stageIndex = Math.max(0, state.stages.findIndex(stage => stage.id === project.stage));
    if (!pass) {
      pass = node("button", "work-pass");
      pass.type = "button";
      pass.dataset.projectId = project.id;
      pass.style.setProperty("--stage", stageIndex);
      const signal = node("span", "pass-signal");
      signal.setAttribute("aria-hidden", "true");
      pass.append(signal, node("span", "pass-place"), node("strong", ""), node("small", ""));
      pass.addEventListener("click", () => {
        inspectedProjectId = project.id;
        renderProcessFloor();
        announce(project.title + "의 현재 작업을 표시합니다.");
      });
      $("work-stream").append(pass);
    }
    const previous = Number(pass.dataset.stageIndex ?? stageIndex);
    pass.dataset.stageIndex = String(stageIndex);
    pass.dataset.blocked = String(project.blocked);
    pass.classList.toggle("is-selected", project.id === inspectedProjectId);
    pass.classList.toggle("is-blocked", project.blocked);
    pass.style.setProperty("--lane", lane % 4);
    pass.querySelector(".pass-place").textContent = STAGE_ROOMS[project.stage].place;
    pass.querySelector("strong").textContent = project.title;
    pass.querySelector("small").textContent = `${roleName(project.current_assignee)} · ${teamName(project.team_id)}`;
    pass.setAttribute("aria-label", `${project.title} · ${STAGE_ROOMS[project.stage].place} · 담당 ${roleName(project.current_assignee)}`);
    if (previous !== stageIndex && motionEnabled() && !replaying) {
      pass.classList.add("is-moving");
      requestAnimationFrame(() => pass.style.setProperty("--stage", stageIndex));
      setTimeout(() => pass.classList.remove("is-moving"), 1100);
    } else if (!replaying) pass.style.setProperty("--stage", stageIndex);
  });
  $("replay-route").disabled = !inspectedProjectId || replaying;
  renderRoomInspector();
}

function renderRoomInspector() {
  const target = $("room-inspector");
  const project = projectById(inspectedProjectId);
  if (!project || project.company_id !== companyId) {
    target.replaceChildren(node("p", "inspector-empty", "이 회사에 아직 이동 중인 업무가 없습니다.\n프로젝트를 만들면 접수실에서 시작합니다."));
    return;
  }
  const room = STAGE_ROOMS[project.stage];
  const assignment = activeAssignment(project);
  const latest = state.events.find(event => event.project_id === project.id);
  const location = node("div", "inspector-location");
  location.append(node("span", "", `${room.number} · 현재 위치`), node("strong", "", room.place));
  const title = node("h3", "", project.title);
  const owner = node("p", "inspector-owner", `${teamName(project.team_id)} · 책임자 ${project.owner}`);
  const current = node("div", "inspector-section");
  current.append(node("span", "section-kicker", "지금 맡은 사람"), node("strong", "", roleName(project.current_assignee)), node("p", "", assignment?.note || room.work));
  if (assignment?.started_at) {
    const clock = node("time", "elapsed-clock", elapsedText(assignment.started_at));
    clock.dataset.startedAt = assignment.started_at;
    current.append(clock);
  }
  const next = node("div", "inspector-section next-condition");
  next.append(node("span", "section-kicker", "다음 방으로 가려면"), node("p", "", room.exit));
  const recent = node("div", "inspector-section recent-record");
  recent.append(node("span", "section-kicker", "마지막 저장 기록"), node("p", "", latest?.message || "아직 저장된 사건이 없습니다."));
  const open = node("button", "inspector-open", "기록과 다음 행동 열기 ↗");
  open.type = "button";
  open.addEventListener("click", () => openDetail(project.id, {returnTarget: open}));
  target.replaceChildren(location, title, owner, current, next, recent, open);
}

function renderAssignments() {
  const projects = companyProjects().filter(project => project.stage !== "done" && (!teamFilter || project.team_id === teamFilter));
  const signature = projects.map(project => [project.id, project.version, project.current_assignee, project.blocked]);
  if (sameRender("assignment-lanes", [companyId, teamFilter, signature])) return;
  put("assignment-count", projects.length + "건 작동 중");
  const lanes = state.roles.map(role => {
    const lane = node("article", "assignment-lane");
    lane.dataset.role = role.id;
    const header = node("header");
    const mine = projects.filter(project => project.current_assignee === role.id);
    header.append(node("span", "assignment-orb", role.name.slice(0, 1)), node("strong", "", role.name), node("small", "", mine.length + "건"));
    lane.append(header);
    const body = node("div", "assignment-stack");
    if (!mine.length) body.append(node("p", "assignment-empty", "다음 배정 대기"));
    for (const project of mine) {
      const card = node("button", "work-card" + (project.blocked ? " is-blocked" : " is-live"));
      card.type = "button";
      card.dataset.projectId = project.id;
      card.append(node("span", "work-stage", project.blocked ? "차단" : stageName(project.stage)), node("strong", "", project.title), node("small", "", teamName(project.team_id)));
      card.addEventListener("click", () => openDetail(project.id, {returnTarget: card}));
      body.append(card);
    }
    lane.append(body);
    return lane;
  });
  $("assignment-lanes").replaceChildren(...lanes);
}
function renderBusiness() {
  const selected = company();
  if (sameRender("business", selected)) return;
  $("product-list").replaceChildren(...selected.products.map(product => {
    const item = node("div", "product-item");
    item.append(node("span", "", product.name), node("small", "", product.status));
    return item;
  }));
  $("revenue-list").replaceChildren(...selected.revenue.map(value => node("li", "", value)));
}
function stageSummary(target, list, current) {
  const value = state.stages.map(stage => [stage.id, stage.label, list?.filter(project => project.stage === stage.id).length, current === stage.id]);
  if (sameRender(target, value)) return;
  $(target).replaceChildren(...value.map(([id, label, count, selected]) => {
    const item = node("div", "stage-chip" + (selected ? " current" : count ? " has-projects" : ""));
    item.dataset.stage = id;
    if (selected) item.setAttribute("aria-current", "step");
    item.append(node("span", "", label));
    if (list) item.append(node("span", "", count));
    return item;
  }));
}
function renderProjects() {
  const list = companyProjects().filter(project => !teamFilter || project.team_id === teamFilter);
  put("project-count", list.length + "건");
  put("project-context", teamFilter ? teamName(teamFilter) + "의 저장된 프로젝트" : "선택한 회사의 저장된 프로젝트");
  $("clear-team").hidden = !teamFilter;
  stageSummary("stage-summary", list);
  if (sameRender("project-list", [companyId, teamFilter, selectedId, list])) return;
  const focusedProjectId = document.activeElement?.dataset.projectId;
  if (!list.length) {
    const empty = node("div", "empty-projects");
    empty.dataset.testid = "empty-projects";
    const emblem = node("span", "empty-emblem");
    emblem.setAttribute("aria-hidden", "true");
    emblem.append(node("span", "", "＋"));
    const copy = node("div");
    copy.append(node("h3", "", teamFilter ? "이 팀의 첫 번째 일은 무엇인가요?" : "아직 쓰이지 않은, 회사의 다음 장."), node("p", "", "등록된 프로젝트가 없습니다. 해결할 문제와 원하는 결과를 남겨보세요."));
    const create = node("button", "text-button", "첫 프로젝트 기록하기 ↗");
    create.type = "button";
    create.addEventListener("click", openCreate);
    copy.append(create);
    empty.append(emblem, copy);
    $("project-list").replaceChildren(empty);
  } else {
    $("project-list").replaceChildren(...list.map(project => {
      const lane = node("div", "mission-lane" + (project.blocked ? " blocked" : ""));
      const button = node("button", "project-row" + (project.blocked ? " blocked" : "") + (selectedId === project.id ? " is-selected" : ""));
      button.type = "button";
      button.dataset.projectId = project.id;
      button.dataset.testid = "project-row";
      const marker = node("span", "mission-marker");
      marker.setAttribute("aria-hidden", "true");
      const copy = node("span", "project-copy");
      copy.append(node("strong", "", project.title), node("small", "", teamName(project.team_id) + " · 현재 담당 " + roleName(project.current_assignee) + " · 책임자 " + project.owner));
      button.append(marker, copy, node("span", "stage-label", project.blocked ? "차단 · " + stageName(project.stage) : stageName(project.stage)), node("span", "project-arrow", "↗"));
      button.addEventListener("click", () => openDetail(project.id));
      const progress = node("span", "mission-progress");
      progress.setAttribute("aria-hidden", "true");
      progress.style.setProperty("--progress", ((state.stages.findIndex(stage => stage.id === project.stage) + 1) / state.stages.length * 100) + "%");
      const track = node("span", "mission-track");
      track.setAttribute("aria-label", "프로젝트 단계 · 현재 " + stageName(project.stage));
      const currentIndex = state.stages.findIndex(stage => stage.id === project.stage);
      state.stages.forEach((stage, index) => {
        const stop = node("span", "mission-stop", stage.label);
        stop.dataset.state = index === currentIndex ? "current" : index < currentIndex ? "passed" : "future";
        if (index === currentIndex) stop.setAttribute("aria-current", "step");
        track.append(stop);
      });
      button.append(track);
      lane.append(button, progress);
      return lane;
    }));
  }
  if (focusedProjectId && !$("detail-dialog").open && !$("create-dialog").open) {
    projectRow(focusedProjectId)?.focus({preventScroll: true});
  }
}
function eventNode(event, detailed = false) {
  const item = node("li", "event-item");
  item.dataset.eventId = String(event.id);
  item.dataset.kind = eventClass(event.kind);
  item.append(node("span", "event-kind", EVENT_LABELS[event.kind] || "업무 기록"));
  if (!detailed) {
    const project = projectById(event.project_id);
    if (project) {
      const link = node("button", "event-title", project.title + " ↗");
      link.type = "button";
      link.setAttribute("aria-label", project.title + " 프로젝트 기록 열기");
      link.addEventListener("click", () => openDetail(project.id));
      item.append(link);
    }
  }
  item.append(node("p", "event-message", event.message));
  if (detailed && event.evidence) {
    const evidence = node("div", "event-evidence");
    evidence.append(node("strong", "", "기록된 검증 근거"), node("span", "", event.evidence));
    item.append(evidence);
  }
  if (detailed && event.reviewer) item.append(node("p", "event-reviewer", "검수 담당 기록 · " + event.reviewer));
  const time = node("time", "", dateText(event.created_at));
  time.dateTime = event.created_at;
  item.append(time);
  return item;
}
function emptyEvents(title, message) {
  const item = node("li", "empty-events");
  item.append(node("strong", "", title), node("span", "", message));
  return item;
}
function renderEvents() {
  const events = state.events.filter(event => event.company_id === companyId).slice(0, 6);
  if (sameRender("event-list", [companyId, events])) return;
  $("event-list").replaceChildren(...(events.length ? events.map(event => eventNode(event)) : [emptyEvents("아직 조용한 기록의 자리.", "프로젝트의 시작, 인계와 검증이 이곳에 남습니다.")]));
}
function render() {
  if (!state.companies.some(item => item.id === companyId)) companyId = state.companies[0].id;
  document.body.dataset.company = companyId;
  put("company-name", company().name);
  put("company-subtitle", company().subtitle);
  put("breadcrumb", company().name);
  put("team-breadcrumb", teamFilter ? "/ " + teamName(teamFilter) : "");
  $("team-breadcrumb").hidden = !teamFilter;
  put("open-count", state.projects.filter(project => project.stage !== "done").length);
  $("open-count").title = "전체 회사의 저장된 미완료 프로젝트";
  renderCompanyNavigation();
  renderMetrics();
  renderOrganization();
  renderBusiness();
  renderAssignments();
  renderProjects();
  renderEvents();
  if (!sameRender("integrations", state.integrations)) {
    $("integration-list").replaceChildren(...state.integrations.map(item => node("span", "", item.name + " · " + item.status)));
  }
  $("new-project").disabled = writing;
}
function selectCompany(id) {
  if (!state || companyId === id) return;
  clearPulses();
  companyId = id;
  teamFilter = null;
  inspectedProjectId = null;
  put("route-status", "팀을 선택하면 업무로 이어집니다 ↘");
  $("route-status").dataset.event = "false";
  render();
  announce(company().name + " 선택. 열린 프로젝트 " + companyProjects().filter(project => project.stage !== "done").length + "건.");
}
function selectTeam(id, scroll = false) {
  teamFilter = id;
  inspectedProjectId = null;
  render();
  announce(id ? teamName(id) + "의 프로젝트를 표시합니다." : "회사의 전체 프로젝트를 표시합니다.");
  if (scroll) $("process-floor").scrollIntoView({behavior: motionEnabled() ? "smooth" : "auto", block: "center"});
}
function selectView(view) {
  activeView = view;
  $("organization-view").hidden = view !== "organization";
  $("business-view").hidden = view !== "business";
  $("view-organization").setAttribute("aria-pressed", String(view === "organization"));
  $("view-business").setAttribute("aria-pressed", String(view === "business"));
  put("scene-note", view === "organization" ? "업무 배정 연결 · AI 모델 실행 미연결" : "대표 제공 현황 · 회계 미연결");
  clearPulses();
}

/* First observation only. Initial history, navigation and visibility changes never replay work. */
function clearPulses() {
  document.querySelectorAll(".route-pulse").forEach(element => element.remove());
  document.querySelectorAll(".is-arriving").forEach(element => element.classList.remove("is-arriving"));
}
function observeEvents(nextState) {
  const ids = nextState.events.map(event => Number(event.id)).filter(Number.isFinite);
  const latest = ids.length ? Math.max(...ids) : 0;
  const fresh = highWaterEventId === null ? [] : nextState.events.filter(event => Number(event.id) > highWaterEventId);
  highWaterEventId = Math.max(highWaterEventId ?? 0, latest);
  return fresh;
}
function showNewEvents(events) {
  const visible = events.filter(event => event.company_id === companyId);
  if (!visible.length || document.hidden) return;
  const latest = visible[0];
  put("route-status", "새 기록 · " + (EVENT_LABELS[latest.kind] || "업무 기록") + " · " + dateText(latest.created_at));
  $("route-status").dataset.event = "true";
  if (!motionEnabled() || activeView !== "organization") return;
  for (const event of visible) {
    const project = projectById(event.project_id);
    const pass = project && [...$("work-stream").children].find(item => item.dataset.projectId === project.id);
    if (!pass) continue;
    pass.classList.add("is-arriving");
    setTimeout(() => pass.classList.remove("is-arriving"), 1500);
  }
}

async function replayRoute() {
  const project = projectById(inspectedProjectId);
  const pass = project && [...$("work-stream").children].find(item => item.dataset.projectId === project.id);
  if (!project || !pass || replaying) return;
  replaying = true;
  $("replay-route").disabled = true;
  const destination = Math.max(0, state.stages.findIndex(stage => stage.id === project.stage));
  pass.classList.add("is-replaying");
  pass.style.setProperty("--stage", 0);
  put("route-status", `이동 기록 재생 · ${STAGE_ROOMS.intake.place}`);
  await new Promise(resolve => setTimeout(resolve, motionEnabled() ? 450 : 0));
  for (let index = 1; index <= destination; index += 1) {
    const stage = state.stages[index];
    pass.style.setProperty("--stage", index);
    put("route-status", `저장된 인계 ${index}회 · ${STAGE_ROOMS[stage.id].place}로 이동`);
    await new Promise(resolve => setTimeout(resolve, motionEnabled() ? 900 : 0));
  }
  pass.classList.remove("is-replaying");
  replaying = false;
  $("replay-route").disabled = false;
  put("route-status", `${project.title} · 현재 ${STAGE_ROOMS[project.stage].place}`);
  announce(project.title + "의 저장된 이동 경로 재생이 끝났습니다.");
}

/* One serialized drain prevents old responses from overwriting newer data.
   A write requests a forced trailing read even when a poll is already in flight. */
function refresh({force = false} = {}) {
  if (refreshPromise) {
    if (force) refreshAgain = true;
    return refreshPromise;
  }
  refreshPromise = (async () => {
    let succeeded = false;
    do {
      refreshAgain = false;
      try {
        const nextState = await api("/api/state");
        for (const field of ["companies", "teams", "roles", "projects", "events", "assignments", "stages", "integrations"]) {
          if (!Array.isArray(nextState[field])) throw new Error("회사 상태 응답의 형식이 올바르지 않습니다.");
        }
        if (!nextState.companies.length) throw new Error("회사 정보를 찾지 못했습니다.");
        const fresh = observeEvents(nextState);
        state = nextState;
        render();
        $("sync-status").dataset.state = "connected";
        put("sync-label", "로컬 저장 연결");
        const now = new Date();
        put("last-sync", now.toLocaleTimeString("ko-KR", {hour12: false}));
        $("last-sync").dateTime = now.toISOString();
        showError("global-error", "");
        if ($("detail-dialog").open && selectedId) {
          const current = projectById(selectedId);
          if (current && detailProject && current.version !== detailProject.version) {
            put("detail-update", "이 프로젝트에 새 기록이 있습니다. 작성 내용은 유지됩니다. 저장 시 최신 상태와 충돌하면 다시 확인하도록 안내합니다.");
            $("detail-update").hidden = false;
          }
          const newDetailEvents = state.events.filter(event => event.project_id === selectedId && !detailEvents.has(event.id));
          if (newDetailEvents.length) {
            newDetailEvents.forEach(event => detailEvents.set(event.id, event));
            renderDetailEvents();
          }
        }
        showNewEvents(fresh);
        succeeded = true;
      } catch (err) {
        $("sync-status").dataset.state = "error";
        put("sync-label", "저장 연결 확인 필요");
        showError("global-error", "최신 상태를 가져오지 못했습니다. 마지막으로 확인한 기록을 표시합니다. " + err.message);
        succeeded = false;
      }
    } while (refreshAgain);
    return succeeded;
  })().finally(() => { refreshPromise = null; });
  return refreshPromise;
}

/* Dialog lifecycle keeps focus return and the reviewed project version explicit. */
function showDialog(id, initialFocus, returnTarget = null) {
  dialogReturnTargets.set(id, {element: returnTarget || document.activeElement, projectId: selectedId});
  $(id).showModal();
  $(initialFocus)?.focus({preventScroll: true});
}
function restoreDialogFocus(id) {
  const target = dialogReturnTargets.get(id);
  dialogReturnTargets.delete(id);
  let element = target?.element;
  const canRestore = candidate => candidate?.isConnected && !candidate.disabled && candidate !== document.body && candidate !== document.documentElement;
  if (!canRestore(element) && target?.projectId) {
    element = projectRow(target.projectId);
  }
  (canRestore(element) ? element : $("new-project")).focus({preventScroll: true});
}
function openCreate() {
  if (!state || writing) return;
  createCompanyId = companyId;
  $("create-form").reset();
  $("project-team").replaceChildren(...state.teams.map(team => {
    const option = node("option", "", team.name);
    option.value = team.id;
    return option;
  }));
  if (teamFilter) $("project-team").value = teamFilter;
  put("create-company", company().name + " · 새로운 프로젝트");
  showError("create-error", "");
  showDialog("create-dialog", "project-title");
}
function availableActions(project) {
  if (project.stage === "done") return [];
  if (project.blocked) return [["resume", "작업 재개"]];
  const actions = [["advance", project.stage === "verify" ? "검증 근거를 남기고 완료" : "다음 단계로 인계"], ["block", "작업 차단 · 보류"]];
  if (project.stage === "verify") actions.push(["reject", "검수 반려 · 구현으로 돌리기"]);
  return actions;
}
function configureAction() {
  const action = $("project-action").value;
  const verification = action === "advance" && detailProject?.stage === "verify";
  $("verification-fields").hidden = !verification;
  $("action-evidence").required = verification;
  $("action-reviewer").required = verification;
  $("action-note").required = ["block", "resume", "reject"].includes(action);
}
function renderDetail(project, {preserveInputs = false} = {}) {
  const scroll = $("detail-dialog").scrollTop;
  const oldAction = $("project-action").value;
  detailProject = {...project};
  if (!preserveInputs) $("action-form").reset();
  put("detail-title", project.title);
  const name = state.companies.find(item => item.id === project.company_id)?.name || "";
  put("detail-meta", name + " · " + teamName(project.team_id) + " · 책임자 " + project.owner);
  put("detail-description", project.description || "목표와 완료 조건이 아직 기록되지 않았습니다.");
  stageSummary("detail-stages", null, project.stage);
  put("detail-status", project.blocked ? "흐름 차단 · " + stageName(project.stage) + " 단계에 멈춰 있습니다. 재개 이유를 기록해 연결하세요." : project.stage === "done" ? "완료 기록 · 제출된 검증 근거는 아래 이력에서 확인할 수 있습니다." : "현재 " + stageName(project.stage) + " 단계 · 다음 행동을 기록하세요.");
  $("detail-status").dataset.blocked = String(project.blocked);
  const actions = availableActions(project);
  $("project-action").replaceChildren(...actions.map(([value, label]) => {
    const option = node("option", "", label);
    option.value = value;
    return option;
  }));
  if (preserveInputs && actions.some(([value]) => value === oldAction)) $("project-action").value = oldAction;
  $("action-form").hidden = !actions.length;
  $("action-submit").disabled = writing || !actions.length;
  $("detail-update").hidden = true;
  configureAction();
  if (preserveInputs) $("detail-dialog").scrollTop = scroll;
}
function openDetail(id, {returnTarget = null} = {}) {
  const project = projectById(id);
  if (!project || writing) return;
  selectedId = id;
  renderDetail(project);
  showError("action-error", "");
  detailEvents = new Map();
  eventsCursor = null;
  eventsHasMore = false;
  eventsBusy = false;
  eventsGeneration += 1;
  renderKeys.delete("detail-event-list");
  $("detail-event-list").replaceChildren(emptyEvents("기록을 불러오고 있습니다.", "프로젝트의 전체 이력을 확인합니다."));
  $("more-events").hidden = true;
  showError("detail-events-error", "");
  if (!$("detail-dialog").open) showDialog("detail-dialog", "project-action", returnTarget);
  $("detail-dialog").scrollTop = 0;
  renderProjects();
  loadDetailEvents();
}
function renderDetailEvents() {
  const list = [...detailEvents.values()].sort((left, right) => right.id - left.id);
  if (!sameRender("detail-event-list", [selectedId, list])) {
    const scroll = $("detail-dialog").scrollTop;
    $("detail-event-list").replaceChildren(...(list.length ? list.map(event => eventNode(event, true)) : [emptyEvents("저장된 사건이 없습니다.", "프로젝트의 변경이 이곳에 기록됩니다.")]));
    $("detail-dialog").scrollTop = scroll;
  }
  $("more-events").hidden = !eventsHasMore;
  $("more-events").disabled = eventsBusy;
  put("more-events", eventsBusy ? "이전 기록 조회 중…" : "이전 기록 더 보기");
}
async function loadDetailEvents() {
  if (!selectedId || eventsBusy) return;
  eventsBusy = true;
  const id = selectedId;
  const generation = eventsGeneration;
  const cursor = eventsCursor;
  $("more-events").disabled = true;
  put("more-events", "기록 조회 중…");
  showError("detail-events-error", "");
  try {
    const url = "/api/projects/" + encodeURIComponent(id) + "/events?limit=" + PAGE_SIZE + (cursor ? "&before_id=" + cursor : "");
    const page = await api(url);
    if (generation !== eventsGeneration || id !== selectedId || !$("detail-dialog").open) return;
    if (!Array.isArray(page)) throw new Error("프로젝트 기록 응답을 읽지 못했습니다.");
    page.forEach(event => detailEvents.set(event.id, event));
    eventsHasMore = page.length === PAGE_SIZE;
    if (page.length) eventsCursor = Math.min(...page.map(event => event.id));
    renderDetailEvents();
  } catch (err) {
    if (generation !== eventsGeneration || id !== selectedId) return;
    showError("detail-events-error", err.message + " 아래 버튼으로 다시 조회할 수 있습니다.");
    $("more-events").hidden = false;
    put("more-events", "기록 다시 조회");
  } finally {
    if (generation === eventsGeneration && id === selectedId) {
      eventsBusy = false;
      $("more-events").disabled = false;
      if ($("detail-events-error").hidden) {
        $("more-events").hidden = !eventsHasMore;
        put("more-events", "이전 기록 더 보기");
      }
    }
  }
}
function setWriting(value) {
  writing = value;
  $("create-submit").disabled = value;
  $("action-submit").disabled = value || !detailProject || !availableActions(detailProject).length;
  $("new-project").disabled = value || !state;
  document.querySelectorAll("[data-close]").forEach(button => { button.disabled = value; });
  $("create-form").setAttribute("aria-busy", String(value));
  $("action-form").setAttribute("aria-busy", String(value));
}

/* Writes are manual records; a 409 rebases only after an explicit failed attempt.
   Note, evidence and reviewer inputs survive that rebase and all background polls. */
$("create-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (writing || !event.target.reportValidity()) return;
  setWriting(true);
  showError("create-error", "");
  let saved = null;
  try {
    const body = Object.fromEntries(new FormData(event.target));
    body.company_id = createCompanyId;
    saved = await api("/api/projects", body);
    $("create-dialog").close();
    const refreshed = await refresh({force: true});
    announce("프로젝트를 저장했습니다.");
    if (!refreshed) showError("global-error", "프로젝트는 저장됐지만 최신 목록을 가져오지 못했습니다. 다시 조회해 주세요. 중복으로 만들지 않아도 됩니다.");
  } catch (err) {
    showError("create-error", err.message);
  } finally { setWriting(false); }
  if (saved && projectById(saved.id)) openDetail(saved.id, {returnTarget: projectRow(saved.id) || $("new-project")});
});
$("action-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (writing || !detailProject || !event.target.reportValidity()) return;
  const id = selectedId;
  const scroll = $("detail-dialog").scrollTop;
  setWriting(true);
  showError("action-error", "");
  try {
    const body = Object.fromEntries(new FormData(event.target));
    body.version = detailProject.version;
    const updated = await api("/api/projects/" + encodeURIComponent(id) + "/actions", body);
    const refreshed = await refresh({force: true});
    renderDetail(refreshed ? projectById(id) || updated : updated);
    $("detail-dialog").scrollTop = scroll;
    announce("프로젝트 변경을 기록했습니다.");
    if (!refreshed) {
      put("detail-update", "변경은 저장됐습니다. 최신 이력 조회가 지연되어 마지막 저장 결과를 표시합니다.");
      $("detail-update").hidden = false;
    }
  } catch (err) {
    if (err.status === 409) {
      const refreshed = await refresh({force: true});
      if (refreshed && projectById(id)) {
        renderDetail(projectById(id), {preserveInputs: true});
        const message = "최신 상태를 다시 불러왔습니다. 입력한 기록·근거·검수자는 유지했습니다. 현재 단계와 다음 행동을 확인한 뒤 다시 저장해 주세요.";
        showError("action-error", message);
        put("detail-update", message);
        $("detail-update").hidden = false;
      } else {
        showError("action-error", "기록 충돌이 발생했고 최신 상태 조회에도 실패했습니다. 입력은 유지됩니다. 다시 조회한 뒤 저장해 주세요.");
      }
    } else showError("action-error", err.message + " 입력 내용은 유지됩니다.");
    $("detail-dialog").scrollTop = scroll;
  } finally { setWriting(false); }
});

$("new-project").addEventListener("click", openCreate);
$("project-action").addEventListener("change", configureAction);
$("clear-team").addEventListener("click", () => selectTeam(null));
$("more-events").addEventListener("click", loadDetailEvents);
$("view-organization").addEventListener("click", () => selectView("organization"));
$("view-business").addEventListener("click", () => selectView("business"));
$("replay-route").addEventListener("click", replayRoute);
$("all-companies").addEventListener("click", () => {
  if (state) selectTeam(null);
  selectView("organization");
  $("company-nav").scrollIntoView({behavior: motionEnabled() ? "smooth" : "auto", block: "center"});
  if (state) $("company-" + companyId).focus({preventScroll: true});
});
$("refresh-now").addEventListener("click", async () => {
  $("refresh-now").disabled = true;
  try { await refresh({force: true}); } finally { $("refresh-now").disabled = false; }
});
$("motion-toggle").addEventListener("click", () => {
  motionPreference = !motionPreference;
  try { localStorage.setItem("company-ops-motion", motionPreference ? "on" : "off"); } catch (_) { /* Keep the in-memory choice. */ }
  updateMotion();
});
mediaMotion.addEventListener("change", updateMotion);
document.querySelectorAll("[data-close]").forEach(button => {
  button.addEventListener("click", () => { if (!writing) $(button.dataset.close).close(); });
});
for (const id of ["create-dialog", "detail-dialog"]) {
  $(id).addEventListener("cancel", event => { if (writing) event.preventDefault(); });
  $(id).addEventListener("close", () => {
    if (id === "detail-dialog") {
      selectedId = null;
      detailProject = null;
      eventsGeneration += 1;
      eventsBusy = false;
      if (state) renderProjects();
    }
    restoreDialogFocus(id);
  });
}
document.addEventListener("visibilitychange", () => {
  if (document.hidden) clearPulses();
  else if (!writing) refresh();
});
updateMotion();
refresh();
setInterval(() => { if (!writing && !document.hidden) refresh(); }, POLL_INTERVAL);
setInterval(() => {
  if (document.hidden) return;
  document.querySelectorAll(".elapsed-clock[data-started-at]").forEach(clock => {
    clock.textContent = elapsedText(clock.dataset.startedAt);
  });
}, 1000);
