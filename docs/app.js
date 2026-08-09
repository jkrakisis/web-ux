const DATA_URL = "data/latest.json";

const elements = {
  statusBadge: document.querySelector("#statusBadge"),
  updatedAt: document.querySelector("#updatedAt"),
  totalCount: document.querySelector("#totalCount"),
  newCountNote: document.querySelector("#newCountNote"),
  failureCount: document.querySelector("#failureCount"),
  runMode: document.querySelector("#runMode"),
  cards: document.querySelector("#cards"),
  emptyState: document.querySelector("#emptyState"),
  errorState: document.querySelector("#errorState"),
  failures: document.querySelector("#failures"),
  failureList: document.querySelector("#failureList"),
  searchInput: document.querySelector("#searchInput"),
  dateFilter: document.querySelector("#dateFilter"),
  refreshButton: document.querySelector("#refreshButton"),
};

let snapshot = null;

function allItems() {
  if (!snapshot) return [];
  const items = [...(snapshot.items || []), ...(snapshot.preview_items || [])];
  const unique = new Map();
  items.forEach((item) => {
    const key = item.str_no || `${item.domain || ""}:${item.registered_date || ""}`;
    unique.set(key, { ...(unique.get(key) || {}), ...item });
  });
  return [...unique.values()].sort((a, b) => {
    const byDate = String(b.registered_date || "").localeCompare(String(a.registered_date || ""));
    if (byDate) return byDate;
    return Number(b.str_no || 0) - Number(a.str_no || 0);
  });
}

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

function parseTechActions(line) {
  const content = String(line || "").replace(/^6\)\s*/, "");
  const legacy = content.match(
    /^키워드\+A\/B\/C\/D\s*:\s*(.*?)\s*\/\s*A\)(.*?)\s+B\)(.*?)\s+C\)(.*?)\s+D\)(.*)$/s,
  );
  if (legacy) {
    return {
      technology: legacy[1].trim(),
      A: legacy[2].trim(),
      B: legacy[3].trim(),
      C: legacy[4].trim(),
      D: legacy[5].trim(),
    };
  }

  const parts = content.split(/\s+\+\s+(?=[A-D]\))/);

  if (parts.length < 2) return null;

  const sections = {
    technology: parts.shift().replace(/^기술\/플러그인 키워드\s*:\s*/, "").trim(),
  };

  parts.forEach((part) => {
    const match = part.match(/^([A-D])\)\s*(.*)$/s);
    if (match) sections[match[1]] = match[2].trim();
  });

  return sections.A || sections.B || sections.C || sections.D ? sections : null;
}

function createInsightBlock(label, value, className = "") {
  const block = el("div", `insight-block${className ? ` ${className}` : ""}`);
  block.append(el("dt", "insight-label", label), el("dd", "insight-value", value || "확인 불가"));
  return block;
}

function createTechActions(line) {
  const sections = parseTechActions(line);
  if (!sections) return null;

  const breakdown = el("dl", "insight-breakdown");
  const technology = el("div", "insight-block technology-block");
  technology.append(el("dt", "insight-label", "기술 · 플러그인"));

  const keywords = sections.technology
    .split(/\s*,\s*|\s*·\s*/)
    .map((keyword) => keyword.trim())
    .filter(Boolean);

  if (keywords.length > 1) {
    const keywordList = el("dd", "tech-keyword-list");
    keywords.forEach((keyword) => keywordList.append(el("span", "tech-keyword", keyword)));
    technology.append(keywordList);
  } else {
    technology.append(el("dd", "insight-value", sections.technology || "확인 불가"));
  }

  breakdown.append(
    technology,
    createInsightBlock("A · IA 퀵액션", sections.A),
    createInsightBlock("B · 핵심 KPI", sections.B),
    createInsightBlock("C · 공공기관 Do / Don’t", sections.C, "public-guideline-block"),
    createInsightBlock("D · 오늘의 한 줄", sections.D, "one-line-block"),
  );
  return breakdown;
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
  const identity = el("div", "card-identity");
  const headingGroup = el("div", "card-heading");
  const titleRow = el("div", "card-title-row");
  titleRow.append(el("h3", "", item.site_name), el("span", "date-chip", item.registered_date));
  const meta = [item.domain, item.agency].filter(Boolean).join(" · ");
  headingGroup.append(titleRow, el("p", "site-meta", meta || "메타 정보 확인 불가"));

  if (item.thumbnail_url && item.thumbnail_status === "success") {
    const thumbnail = el("div", "card-thumbnail");
    const image = el("img");
    image.alt = "";
    image.loading = "lazy";
    image.decoding = "async";
    image.width = 192;
    image.height = 128;
    image.addEventListener("error", () => thumbnail.remove(), { once: true });
    const thumbnailVersion = item.thumbnail_attempted_at
      ? `?v=${encodeURIComponent(item.thumbnail_attempted_at)}`
      : "";
    image.src = `${item.thumbnail_url}${thumbnailVersion}`;
    thumbnail.append(image);
    identity.append(thumbnail);
  }
  identity.append(headingGroup);

  const actions = el("div", "card-actions");
  actions.append(
    createLink("GDWEB 상세", item.detail_url),
    createLink("실사이트", item.live_url, true),
  );
  header.append(identity, actions);
  article.append(header);

  const tags = [...(item.technologies || []), ...(item.concepts || [])].slice(0, 8);
  if (tags.length) {
    const list = el("ul", "tag-list");
    tags.forEach((tag) => list.append(el("li", "tag", tag)));
    article.append(list);
  }

  const analysis = el("ol", "analysis-list");
  (item.lines || []).forEach((line, index) => {
    const listItem = el("li");
    const techActions = index === 5 ? createTechActions(line) : null;
    if (techActions) {
      listItem.classList.add("analysis-breakdown-item");
      listItem.append(techActions);
    } else {
      listItem.textContent = line.replace(/^\d+\)\s*/, "");
    }
    analysis.append(listItem);
  });
  article.append(analysis);
  return article;
}

function render() {
  if (!snapshot) return;
  const query = elements.searchInput.value.trim().toLocaleLowerCase("ko-KR");
  const selectedDate = elements.dateFilter.value;
  elements.cards.replaceChildren();
  const items = allItems();
  const filtered = items.filter((item) => {
    if (selectedDate && item.registered_date !== selectedDate) return false;
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

  elements.emptyState.hidden = items.length > 0 || query.length > 0;
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
  const items = allItems();
  elements.totalCount.textContent = String(data.total_count ?? items.length);
  elements.newCountNote.textContent = `이번 실행 신규 ${data.new_count ?? 0}건`;
  elements.failureCount.textContent = String(data.failure_count ?? 0);
  elements.runMode.textContent = data.mode === "live" ? "Notion 실등록" : "드라이런";

  elements.failureList.replaceChildren();
  const failures = data.failures || [];
  elements.failures.hidden = failures.length === 0;
  failures.forEach((failure) => {
    elements.failureList.append(el("article", "failure-card", failure.text));
  });

  const previousDate = elements.dateFilter.value;
  const dates = [...new Set(items.map((item) => item.registered_date).filter(Boolean))].sort().reverse();
  elements.dateFilter.replaceChildren(new Option("전체 날짜", ""));
  dates.forEach((date) => elements.dateFilter.append(new Option(date, date)));
  elements.dateFilter.value = dates.includes(previousDate) ? previousDate : (dates[0] || "");
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
elements.dateFilter.addEventListener("change", render);
elements.refreshButton.addEventListener("click", loadData);
loadData();

