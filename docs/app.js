const DATA_URL = "data/latest.json";

const elements = {
  statusBadge: document.querySelector("#statusBadge"),
  updatedAt: document.querySelector("#updatedAt"),
  newCount: document.querySelector("#newCount"),
  failureCount: document.querySelector("#failureCount"),
  runMode: document.querySelector("#runMode"),
  cards: document.querySelector("#cards"),
  emptyState: document.querySelector("#emptyState"),
  errorState: document.querySelector("#errorState"),
  failures: document.querySelector("#failures"),
  failureList: document.querySelector("#failureList"),
  searchInput: document.querySelector("#searchInput"),
  refreshButton: document.querySelector("#refreshButton"),
};

let snapshot = null;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function formatDateTime(value) {
  if (!value) return "실행 시각 확인 불가";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    dateStyle: "long",
    timeStyle: "short",
  }).format(date);
}

function statusLabel(status) {
  return {
    success: "정상 완료",
    partial: "일부 확인 필요",
    no_new: "신규 없음",
  }[status] || "상태 확인 필요";
}

function createLink(label, href, primary = false) {
  const link = el("a", `button-link${primary ? " primary" : ""}`, label);
  link.href = href;
  link.target = "_blank";
  link.rel = "noreferrer";
  return link;
}

function createCard(item) {
  const article = el("article", "site-card");
  article.dataset.search = [
    item.site_name,
    item.domain,
    item.agency,
    ...(item.technologies || []),
    ...(item.targets || []),
  ].join(" ").toLocaleLowerCase("ko-KR");

  const header = el("div", "card-header");
  const headingGroup = el("div");
  const titleRow = el("div", "card-title-row");
  titleRow.append(el("h3", "", item.site_name), el("span", "date-chip", item.registered_date));
  const meta = [item.domain, item.agency].filter(Boolean).join(" · ");
  headingGroup.append(titleRow, el("p", "site-meta", meta || "메타 정보 확인 불가"));

  const actions = el("div", "card-actions");
  actions.append(
    createLink("GDWEB 상세", item.detail_url),
    createLink("실사이트", item.live_url, true),
  );
  header.append(headingGroup, actions);
  article.append(header);

  const tags = [...(item.technologies || []), ...(item.concepts || [])].slice(0, 8);
  if (tags.length) {
    const list = el("ul", "tag-list");
    tags.forEach((tag) => list.append(el("li", "tag", tag)));
    article.append(list);
  }

  const analysis = el("ol", "analysis-list");
  (item.lines || []).forEach((line) => {
    analysis.append(el("li", "", line.replace(/^\d+\)\s*/, "")));
  });
  article.append(analysis);
  return article;
}

function render() {
  if (!snapshot) return;
  const query = elements.searchInput.value.trim().toLocaleLowerCase("ko-KR");
  elements.cards.replaceChildren();
  const filtered = (snapshot.items || []).filter((item) => {
    if (!query) return true;
    return [
      item.site_name,
      item.domain,
      item.agency,
      ...(item.technologies || []),
      ...(item.targets || []),
    ].join(" ").toLocaleLowerCase("ko-KR").includes(query);
  });
  filtered.forEach((item) => elements.cards.append(createCard(item)));

  elements.emptyState.hidden = snapshot.items.length > 0 || query.length > 0;
  if (query && filtered.length === 0) {
    const noResult = el("div", "empty-state");
    noResult.append(
      el("div", "empty-icon", "0"),
      el("h3", "", "검색 결과 없음"),
      el("p", "", "다른 사이트명이나 기술 키워드로 검색해 주세요."),
    );
    elements.cards.append(noResult);
  }
}

function renderSnapshot(data) {
  snapshot = data;
  elements.errorState.hidden = true;
  elements.statusBadge.textContent = statusLabel(data.status);
  elements.statusBadge.className = `status-badge ${data.status === "partial" ? "partial" : ""}`;
  elements.updatedAt.textContent = `최근 실행 ${formatDateTime(data.generated_at)}`;
  elements.newCount.textContent = String(data.new_count ?? 0);
  elements.failureCount.textContent = String(data.failure_count ?? 0);
  elements.runMode.textContent = data.mode === "live" ? "Notion 실등록" : "드라이런";

  elements.failureList.replaceChildren();
  const failures = data.failures || [];
  elements.failures.hidden = failures.length === 0;
  failures.forEach((failure) => {
    elements.failureList.append(el("article", "failure-card", failure.text));
  });
  render();
}

async function loadData() {
  elements.refreshButton.disabled = true;
  try {
    const response = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderSnapshot(await response.json());
  } catch (error) {
    console.error(error);
    elements.errorState.hidden = false;
    elements.emptyState.hidden = true;
    elements.statusBadge.textContent = "연결 실패";
    elements.statusBadge.className = "status-badge partial";
  } finally {
    elements.refreshButton.disabled = false;
  }
}

elements.searchInput.addEventListener("input", render);
elements.refreshButton.addEventListener("click", loadData);
loadData();

