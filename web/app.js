const state = {
  authenticated: false,
  authReady: false,
  authUser: "",
  appInitialized: false,
  currentView: "ip-scan",
  currentJobId: null,
  currentFilter: "all",
  rawResults: [],
  currentResults: [],
  selectedResult: null,
  resultSearchQuery: "",
  pollTimer: null,
  siteAccounts: [],
  siteAccountFilter: "all",
  siteAccountSearchQuery: "",
  selectedAccountId: null,
  accountEditorMode: "detail",
  siteAccountsLoaded: false,
  accountCopyStatus: {},
  deviceInventory: [],
  deviceInventoryFilter: "all",
  deviceInventorySearchQuery: "",
  selectedDeviceId: null,
  deviceEditorMode: "detail",
  deviceMetadata: null,
  deviceEvents: [],
  deviceInventoryLoaded: false,
  deviceBusy: false,
};

const DEFAULT_RANGE = {
  startIp: "10.73.78.2",
  endIp: "10.73.78.254",
};

const {
  describeAuthServerErrorMessage,
} = window.AuthUiUtils;

const {
  copyTextToClipboard,
  createCredentialCopyModel,
  getCredentialCopyFeedbackMessage,
  normalizeCredentialValue,
} = window.SiteAccountCopyUtils;

let deviceFeedbackTimerId = null;
const accountCopyStatusTimerIds = new Map();

const VIEW_META = {
  "ip-scan": {
    label: "실시간 범위 스캔",
    contextLabel: "학교 기본 범위",
    contextValue: () => `${DEFAULT_RANGE.startIp} ~ ${DEFAULT_RANGE.endIp}`,
    sidebar: "시작 IP와 끝 IP를 입력해서 범위를 스캔합니다.",
  },
  "site-accounts": {
    label: "사이트 계정 관리",
    contextLabel: "내부 관리",
    contextValue: () => "사이트, 설명, URL, ID, 비밀번호, 비고를 한 화면에서 수정합니다.",
    sidebar: "사이트, 설명, URL, ID, PW, 비고를 같은 화면에서 관리합니다.",
  },
  "coming-soon": {
    label: "추가 모듈 준비",
    contextLabel: "다음 단계",
    contextValue: () => "설정과 보조 기능은 이후 운영 규칙에 맞춰 추가할 수 있습니다.",
    sidebar: "현재는 IP 스캔, 사이트 계정 관리, 기기관리대장이 실제로 동작하는 상태입니다.",
  },
  "device-inventory": {
    label: "기기 자산 관리",
    contextLabel: "자산 현황",
    contextValue: () => "설치장소, 형태, 사양, 상태, 사용자, 제품이미지를 한 화면에서 관리합니다.",
    sidebar: "기기관리대장은 분류 필터, 수정 저장, 이미지 보기, 서식 적용 보고서 다운로드를 제공합니다.",
  },
  settings: {
    label: "설정 준비",
    contextLabel: "다음 단계",
    contextValue: () => "포트, 기본 범위, 권한 정책은 이후 설정 화면으로 분리할 수 있습니다.",
    sidebar: "현재는 IP 스캔과 사이트 계정 관리가 실제로 동작하는 상태입니다.",
  },
};

const elements = {
  loginShell: document.getElementById("loginShell"),
  appShell: document.getElementById("appShell"),
  loginForm: document.getElementById("loginForm"),
  loginIdInput: document.getElementById("loginIdInput"),
  loginPasswordInput: document.getElementById("loginPasswordInput"),
  loginFeedbackText: document.getElementById("loginFeedbackText"),
  loginSubmitButton: document.getElementById("loginSubmitButton"),
  loginFooterText: document.getElementById("loginFooterText"),
  activeModuleLabel: document.getElementById("activeModuleLabel"),
  topbarContextLabel: document.getElementById("topbarContextLabel"),
  topbarContextValue: document.getElementById("topbarContextValue"),
  sidebarFooterText: document.getElementById("sidebarFooterText"),
  localHostMeta: document.getElementById("localHostMeta"),
  sessionUserMeta: document.getElementById("sessionUserMeta"),
  logoutButton: document.getElementById("logoutButton"),
  navItems: Array.from(document.querySelectorAll("[data-view]")),
  viewPanels: Array.from(document.querySelectorAll("[data-view-panel]")),

  scanForm: document.getElementById("scanForm"),
  startIpInput: document.getElementById("startIpInput"),
  endIpInput: document.getElementById("endIpInput"),
  scanStartButton: document.getElementById("scanStartButton"),
  cancelScanButton: document.getElementById("cancelScanButton"),
  defaultRangeButton: document.getElementById("defaultRangeButton"),
  clearButton: document.getElementById("clearButton"),
  copyJsonButton: document.getElementById("copyJsonButton"),
  copySelectedButton: document.getElementById("copySelectedButton"),
  lanUrlBox: document.getElementById("lanUrlBox"),
  jobStatusPill: document.getElementById("jobStatusPill"),
  progressText: document.getElementById("progressText"),
  progressCount: document.getElementById("progressCount"),
  progressFill: document.getElementById("progressFill"),
  totalTargetsValue: document.getElementById("totalTargetsValue"),
  aliveValue: document.getElementById("aliveValue"),
  unresolvedValue: document.getElementById("unresolvedValue"),
  macValue: document.getElementById("macValue"),
  resultsTableBody: document.getElementById("resultsTableBody"),
  detailDeviceName: document.getElementById("detailDeviceName"),
  detailStatus: document.getElementById("detailStatus"),
  detailSummary: document.getElementById("detailSummary"),
  detailIp: document.getElementById("detailIp"),
  detailHostname: document.getElementById("detailHostname"),
  detailHostnameSource: document.getElementById("detailHostnameSource"),
  detailMac: document.getElementById("detailMac"),
  detailLatency: document.getElementById("detailLatency"),
  detailReportedAt: document.getElementById("detailReportedAt"),
  resultSearchInput: document.getElementById("resultSearchInput"),
  resultMetaText: document.getElementById("resultMetaText"),
  filterButtons: Array.from(document.querySelectorAll("[data-filter]")),

  accountStatusPill: document.getElementById("accountStatusPill"),
  refreshAccountsButton: document.getElementById("refreshAccountsButton"),
  siteAccountSearchInput: document.getElementById("siteAccountSearchInput"),
  newAccountButton: document.getElementById("newAccountButton"),
  accountFilterButtons: Array.from(document.querySelectorAll("[data-account-filter]")),
  accountFeedbackText: document.getElementById("accountFeedbackText"),
  accountTotalValue: document.getElementById("accountTotalValue"),
  accountUrlValue: document.getElementById("accountUrlValue"),
  accountMissingDescriptionValue: document.getElementById("accountMissingDescriptionValue"),
  accountMissingPasswordValue: document.getElementById("accountMissingPasswordValue"),
  siteAccountResultMeta: document.getElementById("siteAccountResultMeta"),
  siteAccountsTableBody: document.getElementById("siteAccountsTableBody"),
  accountDetailView: document.getElementById("accountDetailView"),
  accountDetailSiteName: document.getElementById("accountDetailSiteName"),
  accountDetailStatus: document.getElementById("accountDetailStatus"),
  accountDetailSummary: document.getElementById("accountDetailSummary"),
  accountDetailUrl: document.getElementById("accountDetailUrl"),
  accountDetailUsername: document.getElementById("accountDetailUsername"),
  accountDetailPassword: document.getElementById("accountDetailPassword"),
  accountDetailNote: document.getElementById("accountDetailNote"),
  accountDetailCreatedAt: document.getElementById("accountDetailCreatedAt"),
  accountDetailUpdatedAt: document.getElementById("accountDetailUpdatedAt"),
  accountDetailNoteBox: document.getElementById("accountDetailNoteBox"),
  openSiteButton: document.getElementById("openSiteButton"),
  editAccountButton: document.getElementById("editAccountButton"),
  deleteAccountButton: document.getElementById("deleteAccountButton"),
  accountEditorForm: document.getElementById("accountEditorForm"),
  accountEditorTitle: document.getElementById("accountEditorTitle"),
  accountEditorDescription: document.getElementById("accountEditorDescription"),
  accountSiteNameInput: document.getElementById("accountSiteNameInput"),
  accountDescriptionInput: document.getElementById("accountDescriptionInput"),
  accountUrlInput: document.getElementById("accountUrlInput"),
  accountUsernameInput: document.getElementById("accountUsernameInput"),
  accountPasswordInput: document.getElementById("accountPasswordInput"),
  accountPasswordHint: document.getElementById("accountPasswordHint"),
  accountNoteInput: document.getElementById("accountNoteInput"),
  saveAccountButton: document.getElementById("saveAccountButton"),
  cancelAccountEditButton: document.getElementById("cancelAccountEditButton"),

  deviceStatusPill: document.getElementById("deviceStatusPill"),
  refreshDevicesButton: document.getElementById("refreshDevicesButton"),
  deviceSearchInput: document.getElementById("deviceSearchInput"),
  newDeviceButton: document.getElementById("newDeviceButton"),
  deviceImportButton: document.getElementById("deviceImportButton"),
  deviceReportButton: document.getElementById("deviceReportButton"),
  deviceImportInput: document.getElementById("deviceImportInput"),
  deviceFeedbackText: document.getElementById("deviceFeedbackText"),
  deviceFilterButtons: Array.from(document.querySelectorAll("[data-device-filter]")),
  deviceTotalValue: document.getElementById("deviceTotalValue"),
  deviceNormalValue: document.getElementById("deviceNormalValue"),
  deviceRepairValue: document.getElementById("deviceRepairValue"),
  deviceInspectionValue: document.getElementById("deviceInspectionValue"),
  deviceResultMeta: document.getElementById("deviceResultMeta"),
  deviceInventoryTableBody: document.getElementById("deviceInventoryTableBody"),
  deviceDetailView: document.getElementById("deviceDetailView"),
  deviceDetailName: document.getElementById("deviceDetailName"),
  deviceDetailStatus: document.getElementById("deviceDetailStatus"),
  deviceDetailSummary: document.getElementById("deviceDetailSummary"),
  deviceDetailManagementNo: document.getElementById("deviceDetailManagementNo"),
  deviceDetailGroup: document.getElementById("deviceDetailGroup"),
  deviceDetailLocation: document.getElementById("deviceDetailLocation"),
  deviceDetailType: document.getElementById("deviceDetailType"),
  deviceDetailManufacturer: document.getElementById("deviceDetailManufacturer"),
  deviceDetailModelName: document.getElementById("deviceDetailModelName"),
  deviceDetailSerialNumber: document.getElementById("deviceDetailSerialNumber"),
  deviceDetailCpu: document.getElementById("deviceDetailCpu"),
  deviceDetailRam: document.getElementById("deviceDetailRam"),
  deviceDetailAcquiredAt: document.getElementById("deviceDetailAcquiredAt"),
  deviceDetailAge: document.getElementById("deviceDetailAge"),
  deviceDetailStatusText: document.getElementById("deviceDetailStatusText"),
  deviceDetailUser: document.getElementById("deviceDetailUser"),
  deviceDetailNote: document.getElementById("deviceDetailNote"),
  editDeviceButton: document.getElementById("editDeviceButton"),
  deleteDeviceButton: document.getElementById("deleteDeviceButton"),
  deviceEditorForm: document.getElementById("deviceEditorForm"),
  deviceEditorTitle: document.getElementById("deviceEditorTitle"),
  deviceEditorStatus: document.getElementById("deviceEditorStatus"),
  deviceEditorDescription: document.getElementById("deviceEditorDescription"),
  deviceManagementNoInput: document.getElementById("deviceManagementNoInput"),
  deviceGroupInput: document.getElementById("deviceGroupInput"),
  deviceLocationInput: document.getElementById("deviceLocationInput"),
  deviceTypeInput: document.getElementById("deviceTypeInput"),
  deviceManufacturerInput: document.getElementById("deviceManufacturerInput"),
  deviceModelNameInput: document.getElementById("deviceModelNameInput"),
  deviceSerialNumberInput: document.getElementById("deviceSerialNumberInput"),
  deviceCpuInput: document.getElementById("deviceCpuInput"),
  deviceRamInput: document.getElementById("deviceRamInput"),
  deviceAcquiredAtInput: document.getElementById("deviceAcquiredAtInput"),
  deviceStatusInput: document.getElementById("deviceStatusInput"),
  deviceUserInput: document.getElementById("deviceUserInput"),
  deviceImageInput: document.getElementById("deviceImageInput"),
  deviceNoteInput: document.getElementById("deviceNoteInput"),
  saveDeviceButton: document.getElementById("saveDeviceButton"),
  cancelDeviceEditButton: document.getElementById("cancelDeviceEditButton"),
  deviceImageModal: document.getElementById("deviceImageModal"),
  deviceImageModalBackdrop: document.getElementById("deviceImageModalBackdrop"),
  deviceImageModalClose: document.getElementById("deviceImageModalClose"),
  deviceImageModalTitle: document.getElementById("deviceImageModalTitle"),
  deviceImageModalImage: document.getElementById("deviceImageModalImage"),
};

const DEFAULT_DEVICE_METADATA = {
  asset_groups: [
    { value: "교원용PC", label: "교원용PC" },
    { value: "정보교과실PC", label: "정보교과실PC" },
    { value: "디벗", label: "디벗" },
    { value: "전자칠판", label: "전자칠판" },
    { value: "태블릿(교무실)", label: "태블릿(교무실)" },
    { value: "태블릿(과학실)", label: "태블릿(과학실)" },
    { value: "특별실", label: "특별실" },
    { value: "진로상담실PC", label: "진로상담실PC" },
  ],
  device_types: [
    { value: "노트북", label: "노트북" },
    { value: "데스크톱", label: "데스크톱" },
    { value: "태블릿", label: "태블릿" },
    { value: "전자칠판", label: "전자칠판" },
    { value: "기타", label: "기타" },
  ],
  statuses: [
    { value: "정상 사용", label: "정상 사용" },
    { value: "예비", label: "예비" },
    { value: "점검 필요", label: "점검 필요" },
    { value: "점검중", label: "점검중" },
    { value: "수리중", label: "수리중" },
    { value: "교체 검토", label: "교체 검토" },
  ],
};

const DEVICE_FIELD_HEADERS = [
  "관리번호",
  "분류",
  "설치장소",
  "형태",
  "제조회사",
  "모델명",
  "시리얼넘버",
  "CPU",
  "RAM",
  "구입시기",
  "사용연수",
  "상태",
  "비고",
  "사용자명",
  "제품이미지",
];

const DEVICE_STATUS_FILTER_LABELS = {
  all: "전체 보기",
  "교원용PC": "교원용PC",
  "정보교과실PC": "정보교과실PC",
  "디벗": "디벗",
  "전자칠판": "전자칠판",
  "태블릿(교무실)": "태블릿(교무실)",
  "태블릿(과학실)": "태블릿(과학실)",
  "특별실": "특별실",
  "진로상담실PC": "진로상담실PC",
};

const DEVICE_STATUS_LABELS = {
  "정상 사용": "정상 사용",
  정상: "정상 사용",
  normal: "정상 사용",
  healthy: "정상 사용",
  예비: "예비",
  spare: "예비",
  "점검 필요": "점검 필요",
  점검중: "점검중",
  inspection: "점검중",
  수리중: "수리중",
  repair: "수리중",
  maintenance: "수리중",
  "교체 검토": "교체 검토",
  불용대기: "불용대기",
  폐기: "폐기",
  disposed: "폐기",
};

const DEVICE_STATUS_CLASS_MAP = {
  "정상 사용": "healthy",
  정상: "healthy",
  normal: "healthy",
  healthy: "healthy",
  예비: "neutral",
  spare: "neutral",
  "점검 필요": "warning",
  점검중: "warning",
  inspection: "warning",
  수리중: "danger",
  repair: "danger",
  maintenance: "warning",
  "교체 검토": "warning",
  불용대기: "danger",
  폐기: "danger",
  disposed: "danger",
};

function getDeviceMetadata() {
  return state.deviceMetadata || DEFAULT_DEVICE_METADATA;
}

function resolveOptionList(values, fallback) {
  const source = Array.isArray(values) && values.length ? values : fallback;
  return source.map((item) => {
    if (typeof item === "string") {
      return { value: item, label: item };
    }
    if (item && typeof item === "object") {
      return {
        value: String(item.value ?? item.label ?? ""),
        label: String(item.label ?? item.value ?? ""),
      };
    }
    return { value: "", label: "" };
  }).filter((item) => item.value);
}

function populateDeviceSelectOptions() {
  const metadata = getDeviceMetadata();
  const groupOptions = resolveOptionList(metadata.asset_groups, DEFAULT_DEVICE_METADATA.asset_groups);
  const typeOptions = resolveOptionList(metadata.device_types, DEFAULT_DEVICE_METADATA.device_types);
  const statusOptions = resolveOptionList(metadata.statuses, DEFAULT_DEVICE_METADATA.statuses);

  elements.deviceGroupInput.innerHTML = groupOptions
    .map((item) => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`)
    .join("");
  elements.deviceTypeInput.innerHTML = typeOptions
    .map((item) => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`)
    .join("");
  elements.deviceStatusInput.innerHTML = statusOptions
    .map((item) => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`)
    .join("");
}

function normalizeText(value) {
  return String(value ?? "").trim();
}

function normalizeDeviceStatus(value) {
  const text = normalizeText(value);
  if (!text) {
    return "정상 사용";
  }
  const lower = text.toLowerCase();
  const matched = DEVICE_STATUS_LABELS[text] || DEVICE_STATUS_LABELS[lower] || null;
  if (matched) {
    return matched;
  }
  return text;
}

function deviceStatusClass(value) {
  const normalized = normalizeDeviceStatus(value);
  const lower = normalizeText(value).toLowerCase();
  return DEVICE_STATUS_CLASS_MAP[normalized] || DEVICE_STATUS_CLASS_MAP[lower] || "neutral";
}

function deviceStatusLabel(value) {
  return normalizeDeviceStatus(value);
}

function normalizeDeviceRecord(item = {}) {
  const fallbackId = [
    normalizeText(item.management_no ?? item.managementNo ?? item.관리번호),
    normalizeText(item.model_name ?? item.modelName ?? item.모델명),
    normalizeText(item.serial_no ?? item.serial_number ?? item.serialNumber ?? item.시리얼넘버 ?? item.시리얼번호),
  ].filter(Boolean).join("|");
  return {
    id: item.id || item.device_id || item.management_no || fallbackId || crypto.randomUUID(),
    management_no: normalizeText(item.management_no ?? item.managementNo ?? item.관리번호),
    asset_group: normalizeText(item.asset_group ?? item.assetGroup ?? item.분류),
    location: normalizeText(item.location ?? item.install_location ?? item.설치장소 ?? item.설치위치),
    device_type: normalizeText(item.device_type ?? item.deviceType ?? item.형태 ?? item.기기구분),
    manufacturer: normalizeText(item.manufacturer ?? item.제조사),
    model_name: normalizeText(item.model_name ?? item.modelName ?? item.모델명),
    serial_number: normalizeText(item.serial_no ?? item.serial_number ?? item.serialNumber ?? item.시리얼넘버 ?? item.시리얼번호),
    cpu: normalizeText(item.cpu ?? item.CPU),
    ram: normalizeText(item.ram ?? item.RAM),
    acquired_at: normalizeText(item.introduced_date ?? item.acquired_at ?? item.acquiredAt ?? item.구입시기 ?? item.도입일자),
    status: normalizeDeviceStatus(item.status ?? item.device_status ?? item.상태),
    assigned_user: normalizeText(item.user_name ?? item.assigned_user ?? item.assignedUser ?? item.user ?? item.사용자명 ?? item.사용자),
    note: normalizeText(item.notes ?? item.note ?? item.memo ?? item.비고),
    image_url: normalizeText(item.image_url ?? item.imageUrl ?? item.제품이미지 ?? item["이미지 URL"]),
    usage_years: Number.isFinite(Number(item.usage_years)) ? Number(item.usage_years) : null,
    life_cycle_due: typeof item.life_cycle_due === "boolean" ? item.life_cycle_due : false,
    repair_or_inspection_needed: typeof item.repair_or_inspection_needed === "boolean" ? item.repair_or_inspection_needed : false,
  };
}

function normalizeDeviceItems(items) {
  return Array.isArray(items) ? items.map((item) => normalizeDeviceRecord(item)) : [];
}

function normalizeDeviceEvents(events) {
  return Array.isArray(events)
    ? events.map((event) => ({
        id: event.event_id || event.id || crypto.randomUUID(),
        device_id: normalizeText(event.device_id ?? event.deviceId ?? event.관리번호),
        event_type: normalizeText(event.event_type ?? event.eventType ?? "update"),
        event_summary: normalizeText(event.event_summary ?? event.summary ?? event.message ?? ""),
        event_at: normalizeText(event.event_at ?? event.eventAt ?? event.occurred_at ?? event.created_at),
      }))
    : [];
}

function isEmptyValue(value) {
  return normalizeText(value) === "";
}

function isInspectionDue(device) {
  if (!device.last_inspection_at) {
    return true;
  }
  const inspectedAt = new Date(device.last_inspection_at);
  if (Number.isNaN(inspectedAt.getTime())) {
    return true;
  }
  const elapsedMs = Date.now() - inspectedAt.getTime();
  return elapsedMs >= 180 * 24 * 60 * 60 * 1000;
}

function deviceNeedsInspection(device) {
  if (typeof device?.repair_or_inspection_needed === "boolean") {
    return device.repair_or_inspection_needed;
  }
  const status = deviceStatusLabel(device.status);
  return status.includes("점검") || status.includes("수리");
}

function formatDeviceAge(device) {
  if (Number.isFinite(device?.usage_years)) {
    return `${device.usage_years}년`;
  }
  return calculateDeviceAge(device?.acquired_at);
}

function calculateDeviceAge(acquiredAt) {
  if (!acquiredAt) {
    return "-";
  }
  const parsed = new Date(acquiredAt);
  if (Number.isNaN(parsed.getTime())) {
    return "-";
  }

  const now = new Date();
  let months = (now.getFullYear() - parsed.getFullYear()) * 12 + (now.getMonth() - parsed.getMonth());
  if (now.getDate() < parsed.getDate()) {
    months -= 1;
  }
  if (months < 0) {
    return "-";
  }
  if (months < 12) {
    return `${months}개월`;
  }
  const years = Math.floor(months / 12);
  const remainMonths = months % 12;
  return remainMonths ? `${years}년 ${remainMonths}개월` : `${years}년`;
}

function formatDeviceDate(value) {
  const text = normalizeText(value);
  if (!text) {
    return "-";
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    return text;
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) {
    return text;
  }
  return parsed.toLocaleDateString("ko-KR");
}

function formatDeviceMonth(value) {
  const text = normalizeText(value);
  if (!text) {
    return "-";
  }
  const directMatch = text.match(/^(\d{4})[-./](\d{1,2})/);
  if (directMatch) {
    return `${directMatch[1]}-${directMatch[2].padStart(2, "0")}`;
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) {
    return text;
  }
  return `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, "0")}`;
}

function formatDeviceEventTime(value) {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString("ko-KR");
}

function buildCsvValue(value) {
  const text = normalizeText(value);
  if (/[",\n]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}

function toDeviceCsv(items) {
  const rows = [DEVICE_FIELD_HEADERS, ...items.map((item) => [
    item.management_no,
    item.asset_group,
    item.location,
    item.device_type,
    item.manufacturer,
    item.model_name,
    item.serial_number,
    item.cpu,
    item.ram,
    item.acquired_at,
    formatDeviceAge(item),
    item.status,
    item.note,
    item.assigned_user,
    item.image_url,
  ])];
  return rows.map((row) => row.map(buildCsvValue).join(",")).join("\n");
}

function toScanResultsCsv(items) {
  const rows = [[
    "IP",
    "상태",
    "장치명",
    "응답여부",
    "이름 출처",
    "MAC",
    "응답 시간(ms)",
    "메모",
    "마지막 보고",
  ], ...items.map((item) => [
    item.ip,
    statusLabelFromValue(item.status),
    scanResultDisplayName(item),
    item.reachable ? "응답 있음" : "응답 없음",
    item.hostname_source || "",
    item.mac_address || "",
    item.latency_ms != null ? String(item.latency_ms) : "",
    item.note || "",
    formatTime(item.reported_at),
  ])];

  return rows.map((row) => row.map(buildCsvValue).join(",")).join("\n");
}

function downloadTextFile(filename, text, mimeType = "text/plain;charset=utf-8") {
  const blob = new Blob([text], { type: mimeType });
  downloadBlob(filename, blob);
}

function downloadBlob(filename, blob) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setTopbarForView(view) {
  const meta = VIEW_META[view] || VIEW_META["ip-scan"];
  elements.activeModuleLabel.textContent = meta.label;
  elements.topbarContextLabel.textContent = meta.contextLabel;
  elements.topbarContextValue.textContent = meta.contextValue();
  elements.sidebarFooterText.textContent = meta.sidebar;
}

function setLoginFooterYear() {
  elements.loginFooterText.textContent = `${new Date().getFullYear()} DCMS`;
}

function setLoginFeedback(message) {
  elements.loginFeedbackText.textContent = message;
}

function setSessionUserMeta(username = "") {
  elements.sessionUserMeta.textContent = username ? `로그인 계정 ${username}` : "로그인 필요";
}

function showLoginShell(message) {
  state.authenticated = false;
  state.authUser = "";
  elements.appShell.classList.add("is-hidden");
  elements.loginShell.classList.remove("is-hidden");
  elements.logoutButton.disabled = true;
  elements.loginPasswordInput.value = "";
  setSessionUserMeta("");
  if (message) {
    setLoginFeedback(message);
  }
  window.setTimeout(() => {
    elements.loginIdInput.focus();
  }, 0);
}

function initializeAppShell() {
  if (state.appInitialized) {
    return;
  }

  state.appInitialized = true;
  setIdleState();
  applyDefaultRange(false);
  populateDeviceSelectOptions();
  resetDetailPanel();
  resetAccountDetail();
  resetDeviceDetail();
  setTopbarForView("ip-scan");
}

async function showAuthenticatedApp(username) {
  state.authenticated = true;
  state.authReady = true;
  state.authUser = username;
  elements.loginShell.classList.add("is-hidden");
  elements.appShell.classList.remove("is-hidden");
  elements.logoutButton.disabled = false;
  setSessionUserMeta(username);
  initializeAppShell();
  await loadLocalHost();
  switchView(state.currentView || "ip-scan");
}

function handleAuthenticationRequired(message = "세션이 만료되었습니다. 다시 로그인해 주세요.") {
  if (!state.authenticated && state.authReady) {
    showLoginShell(message);
    return;
  }

  state.authReady = true;
  state.currentJobId = null;
  stopPolling();
  showLoginShell(message);
}

async function checkSession() {
  try {
    const session = await fetchJson("/api/session", { headers: {}, ignoreAuthError: true });
    state.authReady = true;
    if (session.authenticated) {
      await showAuthenticatedApp(session.username || "dcms");
      return;
    }
    showLoginShell("아이디와 비밀번호를 입력해 주세요.");
  } catch (error) {
    state.authReady = true;
    showLoginShell(describeAuthServerErrorMessage(error.message || "세션 상태를 확인하지 못했습니다."));
  }
}

function switchView(view) {
  const panelView = elements.viewPanels.some((panel) => panel.dataset.viewPanel === view) ? view : "coming-soon";
  state.currentView = view;
  elements.navItems.forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  elements.viewPanels.forEach((panel) => panel.classList.toggle("active", panel.dataset.viewPanel === panelView));
  setTopbarForView(view);

  if (view === "site-accounts") {
    loadSiteAccounts();
  } else if (view === "device-inventory") {
    loadDeviceInventory();
  }
}

function setIdleState() {
  elements.jobStatusPill.textContent = "대기 중";
  elements.progressText.textContent = "아직 스캔을 시작하지 않았습니다.";
  elements.progressCount.textContent = "0 / 0";
  elements.progressFill.style.width = "0%";
  elements.totalTargetsValue.textContent = "0";
  elements.aliveValue.textContent = "0";
  elements.unresolvedValue.textContent = "0";
  elements.macValue.textContent = "0";
}

function updateSummary(summary = {}) {
  elements.totalTargetsValue.textContent = String(summary.total ?? 0);
  elements.aliveValue.textContent = String(summary.alive ?? 0);
  elements.unresolvedValue.textContent = String(summary.unresolved ?? 0);
  elements.macValue.textContent = String(summary.has_mac ?? 0);
  elements.progressCount.textContent = `${summary.completed ?? 0} / ${summary.total ?? 0}`;
}

function statusLabelFromValue(status) {
  if (status === "healthy") return "응답";
  if (status === "warning") return "응답 / 이름 미해결";
  if (status === "offline") return "미응답";
  if (status === "failed") return "실패";
  return "대기";
}

function statusClassFromValue(status) {
  if (status === "healthy") return "healthy";
  if (status === "warning") return "warning";
  if (status === "offline") return "offline";
  return "neutral";
}

function setJobState(snapshot) {
  const statusMap = {
    queued: "대기열 등록",
    running: "스캔 중",
    cancelling: "중지 요청됨",
    cancelled: "중지됨",
    completed: "완료",
    failed: "실패",
  };

  elements.jobStatusPill.textContent = statusMap[snapshot.status] ?? snapshot.status;
  elements.progressText.textContent = `${snapshot.start_ip} ~ ${snapshot.end_ip} 범위를 스캔 중입니다.`;
  elements.progressFill.style.width = `${snapshot.progress_percent ?? 0}%`;
  updateSummary(snapshot.summary);
}

function formatTime(value) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString("ko-KR");
  } catch {
    return value;
  }
}

function applyFilter(results) {
  let next = [...results];

  if (state.currentFilter === "reachable") {
    next = next.filter((item) => item.reachable);
  } else if (state.currentFilter === "offline") {
    next = next.filter((item) => !item.reachable);
  } else if (state.currentFilter === "unresolved") {
    next = next.filter((item) => item.reachable && !item.hostname);
  } else if (state.currentFilter === "has-mac") {
    next = next.filter((item) => Boolean(item.mac_address));
  }

  const query = state.resultSearchQuery.trim().toLowerCase();
  if (query) {
    next = next.filter((item) => {
      const haystack = [
        item.ip,
        item.hostname,
        item.hostname_source,
        item.mac_address,
        item.note,
        item.status,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }

  next.sort((left, right) => compareIpAddress(left.ip, right.ip));
  return next;
}

function compareIpAddress(leftIp, rightIp) {
  const leftParts = leftIp.split(".").map((value) => Number(value));
  const rightParts = rightIp.split(".").map((value) => Number(value));

  for (let index = 0; index < 4; index += 1) {
    const delta = (leftParts[index] || 0) - (rightParts[index] || 0);
    if (delta !== 0) {
      return delta;
    }
  }
  return 0;
}

function renderResults(results) {
  state.rawResults = Array.isArray(results) ? [...results] : [];
  const filtered = applyFilter(state.rawResults);
  state.currentResults = filtered;
  elements.resultMetaText.textContent = `정렬: IP 오름차순 / 현재 ${filtered.length}건`;

  if (filtered.length === 0) {
    resetDetailPanel();
    elements.resultsTableBody.innerHTML = `
      <tr>
        <td colspan="7" class="empty-cell">조건에 맞는 결과가 없습니다.</td>
      </tr>
    `;
    return;
  }

  elements.resultsTableBody.innerHTML = filtered
    .map(
      (item, index) => `
        <tr data-index="${index}">
          <td><span class="mono">${escapeHtml(item.ip)}</span></td>
          <td><span class="status ${statusClassFromValue(item.status)}">${statusLabelFromValue(item.status)}</span></td>
          <td>
            <div class="primary-cell">
              <strong>${escapeHtml(scanResultDisplayName(item))}</strong>
              <span class="secondary-line">${item.reachable ? "응답 있음" : "응답 없음"}</span>
            </div>
          </td>
          <td>${escapeHtml(item.hostname_source || "-")}</td>
          <td><span class="mono">${escapeHtml(item.mac_address || "-")}</span></td>
          <td>${item.latency_ms != null ? `${escapeHtml(item.latency_ms)} ms` : "-"}</td>
          <td class="wrap-cell">${escapeHtml(item.note || "-")}</td>
        </tr>
      `,
    )
    .join("");

  Array.from(elements.resultsTableBody.querySelectorAll("tr[data-index]")).forEach((row) => {
    row.addEventListener("click", () => {
      const index = Number(row.dataset.index);
      selectResult(filtered[index]);
      Array.from(elements.resultsTableBody.querySelectorAll("tr[data-index]")).forEach((targetRow) => {
        targetRow.classList.toggle("selected", targetRow === row);
      });
    });
  });

  if (filtered.length > 0) {
    selectResult(filtered[0]);
    const firstRow = elements.resultsTableBody.querySelector("tr[data-index]");
    if (firstRow) {
      firstRow.classList.add("selected");
    }
  }
}

function selectResult(result) {
  state.selectedResult = result;
  elements.copySelectedButton.disabled = false;
  elements.detailDeviceName.textContent = scanResultDisplayName(result, " 장치");
  elements.detailStatus.textContent = statusLabelFromValue(result.status);
  elements.detailStatus.className = `status ${statusClassFromValue(result.status)}`;
  elements.detailSummary.textContent = result.note;
  elements.detailIp.textContent = result.ip;
  elements.detailHostname.textContent = result.hostname || "-";
  elements.detailHostnameSource.textContent = result.hostname_source || "-";
  elements.detailMac.textContent = result.mac_address || "-";
  elements.detailLatency.textContent = result.latency_ms != null ? `${result.latency_ms} ms` : "-";
  elements.detailReportedAt.textContent = formatTime(result.reported_at);
}

function scanResultDisplayName(result, suffix = "") {
  if (!result.reachable) {
    return `응답 없음${suffix}`;
  }

  return result.hostname || `이름 미해결${suffix}`;
}

function resetDetailPanel() {
  state.selectedResult = null;
  elements.copySelectedButton.disabled = true;
  elements.detailDeviceName.textContent = "아직 선택된 결과가 없습니다";
  elements.detailStatus.textContent = "대기";
  elements.detailStatus.className = "status neutral";
  elements.detailSummary.textContent = "왼쪽 표에서 결과를 선택하면 상세 정보가 표시됩니다.";
  elements.detailIp.textContent = "-";
  elements.detailHostname.textContent = "-";
  elements.detailHostnameSource.textContent = "-";
  elements.detailMac.textContent = "-";
  elements.detailLatency.textContent = "-";
  elements.detailReportedAt.textContent = "-";
}

async function fetchJson(url, options = {}) {
  const {
    headers: customHeaders = {},
    ignoreAuthError = false,
    ...requestOptions
  } = options;
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...customHeaders,
    },
    ...requestOptions,
  });

  const rawText = await response.text();
  const data = rawText ? JSON.parse(rawText) : {};
  if (!response.ok) {
    if (response.status === 401 && !ignoreAuthError) {
      handleAuthenticationRequired(data.error || "로그인이 필요합니다.");
    }
    throw new Error(data.error || "요청 처리에 실패했습니다.");
  }
  return data;
}

async function loadLocalHost() {
  try {
    const info = await fetchJson("/api/self", { headers: {} });
    const ips = Array.isArray(info.ips) && info.ips.length ? info.ips.join(", ") : "IP 확인 불가";
    elements.localHostMeta.textContent = `${info.hostname} / ${ips}`;
    const lanUrls = Array.isArray(info.suggested_urls) && info.suggested_urls.length
      ? info.suggested_urls.join(" , ")
      : "내부망 URL을 계산하지 못했습니다.";
    elements.lanUrlBox.textContent = `다른 PC 접속 주소: ${lanUrls}`;
    const defaultRange = info.default_range || {};
    if (defaultRange.start_ip && defaultRange.end_ip) {
      DEFAULT_RANGE.startIp = defaultRange.start_ip;
      DEFAULT_RANGE.endIp = defaultRange.end_ip;
      applyDefaultRange(false);
      if (state.currentView === "ip-scan") {
        setTopbarForView("ip-scan");
      }
    }
  } catch (error) {
    elements.localHostMeta.textContent = "서버 호스트 정보 확인 실패";
    elements.lanUrlBox.textContent = "내부망 접속 주소 확인 실패";
  }
}

async function handleLoginSubmit(event) {
  event.preventDefault();
  const username = elements.loginIdInput.value.trim();
  const password = elements.loginPasswordInput.value;

  if (!username || !password) {
    setLoginFeedback("아이디와 비밀번호를 모두 입력해 주세요.");
    return;
  }

  elements.loginSubmitButton.disabled = true;
  setLoginFeedback("로그인 정보를 확인하는 중입니다.");

  try {
    const result = await fetchJson("/api/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
      ignoreAuthError: true,
    });
    elements.loginPasswordInput.value = "";
    await showAuthenticatedApp(result.username || username);
  } catch (error) {
    elements.loginPasswordInput.value = "";
    setLoginFeedback(describeAuthServerErrorMessage(error.message));
    elements.loginPasswordInput.focus();
  } finally {
    elements.loginSubmitButton.disabled = false;
  }
}

async function handleLogout() {
  elements.logoutButton.disabled = true;

  try {
    await fetchJson("/api/logout", {
      method: "POST",
      body: JSON.stringify({}),
      ignoreAuthError: true,
    });
    showLoginShell("로그아웃되었습니다.");
  } catch (error) {
    showLoginShell(error.message || "로그아웃 처리에 실패했습니다.");
  } finally {
    elements.loginIdInput.focus();
  }
}

function stopPolling() {
  if (state.pollTimer) {
    clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }
}

async function pollJob() {
  if (!state.currentJobId) {
    return;
  }

  try {
    const snapshot = await fetchJson(`/api/scan/${state.currentJobId}`, { headers: {} });
    setJobState(snapshot);
    renderResults(snapshot.results || []);
    elements.cancelScanButton.disabled = !["queued", "running", "cancelling"].includes(snapshot.status);
    elements.scanStartButton.disabled = ["queued", "running", "cancelling"].includes(snapshot.status);

    if (snapshot.status === "completed") {
      elements.progressText.textContent = "스캔이 완료되었습니다.";
      stopPolling();
      return;
    }

    if (snapshot.status === "cancelled") {
      elements.progressText.textContent = "스캔이 중지되었습니다.";
      stopPolling();
      return;
    }

    if (snapshot.status === "failed") {
      elements.progressText.textContent = snapshot.error || "스캔이 실패했습니다.";
      stopPolling();
      return;
    }

    state.pollTimer = window.setTimeout(pollJob, 900);
  } catch (error) {
    elements.progressText.textContent = error.message;
    stopPolling();
  }
}

async function startScan(event) {
  event.preventDefault();
  stopPolling();
  state.selectedResult = null;
  elements.copySelectedButton.disabled = true;

  try {
    const payload = {
      start_ip: elements.startIpInput.value.trim(),
      end_ip: elements.endIpInput.value.trim(),
    };

    const snapshot = await fetchJson("/api/scan", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    state.currentJobId = snapshot.job_id;
    setJobState(snapshot);
    renderResults(snapshot.results || []);
    elements.scanStartButton.disabled = true;
    elements.cancelScanButton.disabled = false;
    state.pollTimer = window.setTimeout(pollJob, 500);
  } catch (error) {
    elements.progressText.textContent = error.message;
    elements.jobStatusPill.textContent = "오류";
  }
}

async function cancelScan() {
  if (!state.currentJobId) {
    return;
  }

  try {
    const snapshot = await fetchJson(`/api/scan/${state.currentJobId}/cancel`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    setJobState(snapshot);
    elements.progressText.textContent = "스캔 중지 요청을 보냈습니다.";
  } catch (error) {
    elements.progressText.textContent = error.message;
  }
}

function clearResults() {
  stopPolling();
  state.currentJobId = null;
  state.rawResults = [];
  state.currentResults = [];
  state.resultSearchQuery = "";
  setIdleState();
  elements.cancelScanButton.disabled = true;
  elements.scanStartButton.disabled = false;
  elements.resultSearchInput.value = "";
  applyDefaultRange(false);
  resetDetailPanel();
  elements.resultsTableBody.innerHTML = `
    <tr>
      <td colspan="7" class="empty-cell">스캔을 시작하면 결과가 여기에 표시됩니다.</td>
    </tr>
  `;
  elements.resultMetaText.textContent = "정렬: IP 오름차순";
}

async function copyAllResults() {
  if (!state.currentResults.length) {
    elements.progressText.textContent = "다운로드할 스캔 결과가 없습니다.";
    return;
  }

  try {
    const csvText = toScanResultsCsv(state.currentResults);
    const filename = `ip_scan_results_${new Date().toISOString().slice(0, 10)}.csv`;
    downloadTextFile(filename, `\uFEFF${csvText}`, "text/csv;charset=utf-8");
    elements.progressText.textContent = "현재 필터 기준 결과를 CSV로 다운로드했습니다.";
  } catch {
    elements.progressText.textContent = "CSV 다운로드에 실패했습니다.";
  }
}

async function copySelectedResult() {
  if (!state.selectedResult) {
    return;
  }
  try {
    await copyTextToClipboard(JSON.stringify(state.selectedResult, null, 2));
    elements.progressText.textContent = "선택한 결과를 클립보드에 복사했습니다.";
  } catch {
    elements.progressText.textContent = "선택 결과 복사에 실패했습니다.";
  }
}

function activateFilter(button) {
  elements.filterButtons.forEach((target) => target.classList.toggle("active", target === button));
  state.currentFilter = button.dataset.filter;
  renderResults(state.rawResults);
}

function applyDefaultRange(updateMessage = true) {
  elements.startIpInput.value = DEFAULT_RANGE.startIp;
  elements.endIpInput.value = DEFAULT_RANGE.endIp;
  if (updateMessage) {
    elements.progressText.textContent = `학교 기본 범위 ${DEFAULT_RANGE.startIp} ~ ${DEFAULT_RANGE.endIp} 를 적용했습니다.`;
  }
}

function handleResultSearch() {
  state.resultSearchQuery = elements.resultSearchInput.value || "";
  renderResults(state.rawResults);
}

function setAccountFeedback(message) {
  elements.accountFeedbackText.textContent = message;
}

function getAccountCredentialKey(accountId, field) {
  return `${accountId}:${field}`;
}

function getAccountCredentialLabel(field) {
  return field === "password" ? "PW" : "ID";
}

function getAccountCredentialStatus(accountId, field) {
  if (!accountId) {
    return "idle";
  }
  return state.accountCopyStatus[getAccountCredentialKey(accountId, field)] || "idle";
}

function clearAccountCredentialTimer(key) {
  const timerId = accountCopyStatusTimerIds.get(key);
  if (!timerId) {
    return;
  }
  window.clearTimeout(timerId);
  accountCopyStatusTimerIds.delete(key);
}

function bindAccountCredentialButtons() {
  Array.from(document.querySelectorAll(".credential-copy-button")).forEach((button) => {
    if (button.disabled || button.dataset.copyBound === "true") {
      return;
    }

    button.dataset.copyBound = "true";
    button.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      await copySiteAccountCredential(button.dataset.copyAccountId, button.dataset.copyField);
    });
  });
}

function renderAccountCredentialButton(account, field, variant = "table") {
  const label = getAccountCredentialLabel(field);
  const accountId = account?.id || "";
  const siteName = account?.site_name || "선택된 계정";
  const model = createCredentialCopyModel(account?.[field], getAccountCredentialStatus(accountId, field));
  const buttonClassName = [
    "credential-copy-button",
    `credential-copy-button--${variant}`,
    model.statusClassName,
  ].join(" ");

  return `
    <button
      class="${buttonClassName}"
      type="button"
      data-copy-account-id="${escapeHtml(accountId)}"
      data-copy-field="${escapeHtml(field)}"
      aria-label="${escapeHtml(`${siteName} ${label} 복사`)}"
      ${model.disabled ? "disabled" : ""}
    >
      <span class="credential-copy-value">${escapeHtml(model.displayValue)}</span>
      <span class="credential-copy-hint">${escapeHtml(model.hintText)}</span>
    </button>
  `;
}

function setAccountCredentialStatus(accountId, field, status) {
  if (!accountId) {
    return;
  }

  const key = getAccountCredentialKey(accountId, field);
  clearAccountCredentialTimer(key);

  if (status === "idle") {
    delete state.accountCopyStatus[key];
  } else {
    state.accountCopyStatus[key] = status;
    const timerId = window.setTimeout(() => {
      delete state.accountCopyStatus[key];
      accountCopyStatusTimerIds.delete(key);
      renderSiteAccounts();
    }, 1600);
    accountCopyStatusTimerIds.set(key, timerId);
  }

  renderSiteAccounts();
}

async function copySiteAccountCredential(accountId, field) {
  const account = state.siteAccounts.find((item) => item.id === accountId);
  if (!account) {
    return;
  }

  const fieldLabel = getAccountCredentialLabel(field);
  const normalizedValue = normalizeCredentialValue(account[field]);
  const hasValue = normalizedValue.length > 0;

  if (!hasValue) {
    setAccountFeedback(
      getCredentialCopyFeedbackMessage({
        siteName: account.site_name,
        fieldLabel,
        success: false,
        hasValue: false,
      })
    );
    return;
  }

  try {
    await copyTextToClipboard(normalizedValue);
    setAccountFeedback(
      getCredentialCopyFeedbackMessage({
        siteName: account.site_name,
        fieldLabel,
        success: true,
        hasValue: true,
      })
    );
    setAccountCredentialStatus(accountId, field, "copied");
  } catch {
    setAccountFeedback(
      getCredentialCopyFeedbackMessage({
        siteName: account.site_name,
        fieldLabel,
        success: false,
        hasValue: true,
      })
    );
    setAccountCredentialStatus(accountId, field, "failed");
  }
}

function setAccountSummary(summary = {}) {
  elements.accountTotalValue.textContent = String(summary.total ?? 0);
  elements.accountUrlValue.textContent = String(summary.with_url ?? 0);
  elements.accountMissingDescriptionValue.textContent = String(summary.missing_description ?? 0);
  elements.accountMissingPasswordValue.textContent = String(summary.missing_password ?? 0);
  elements.accountStatusPill.textContent = `총 ${summary.total ?? 0}건`;
}

function applySiteAccountFilter(accounts) {
  let next = [...accounts];

  if (state.siteAccountFilter === "with-url") {
    next = next.filter((item) => Boolean(item.url));
  } else if (state.siteAccountFilter === "with-note") {
    next = next.filter((item) => Boolean(item.note));
  } else if (state.siteAccountFilter === "missing-description") {
    next = next.filter((item) => !item.description);
  } else if (state.siteAccountFilter === "missing-password") {
    next = next.filter((item) => !item.password);
  }

  const query = state.siteAccountSearchQuery.trim().toLowerCase();
  if (query) {
    next = next.filter((item) => {
      const haystack = [
        item.site_name,
        item.description,
        item.url,
        item.username,
        item.note,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }

  next.sort((left, right) => left.site_name.localeCompare(right.site_name, "ko-KR", { sensitivity: "base" }));
  return next;
}

function getSelectedAccount() {
  return state.siteAccounts.find((item) => item.id === state.selectedAccountId) || null;
}

function resetAccountDetail() {
  elements.accountDetailSiteName.textContent = "아직 선택된 항목이 없습니다";
  elements.accountDetailStatus.textContent = "대기";
  elements.accountDetailStatus.className = "status neutral";
  elements.accountDetailSummary.textContent = "왼쪽 표에서 사이트 계정을 선택하면 상세 정보가 표시됩니다.";
  elements.accountDetailUrl.textContent = "-";
  elements.accountDetailUsername.innerHTML = renderAccountCredentialButton(null, "username", "detail");
  elements.accountDetailPassword.innerHTML = renderAccountCredentialButton(null, "password", "detail");
  elements.accountDetailNote.textContent = "-";
  elements.accountDetailCreatedAt.textContent = "-";
  elements.accountDetailUpdatedAt.textContent = "-";
  elements.accountDetailNoteBox.textContent = "사이트 계정 정보는 내부 관리용으로 바로 수정할 수 있습니다.";
  elements.openSiteButton.disabled = true;
  elements.editAccountButton.disabled = true;
  elements.deleteAccountButton.disabled = true;
  bindAccountCredentialButtons();
}

function renderSelectedAccount() {
  if (state.accountEditorMode !== "detail") {
    elements.accountDetailView.classList.add("is-hidden");
    elements.accountEditorForm.classList.remove("is-hidden");
    return;
  }

  elements.accountDetailView.classList.remove("is-hidden");
  elements.accountEditorForm.classList.add("is-hidden");

  const account = getSelectedAccount();
  if (!account) {
    resetAccountDetail();
    return;
  }

  const hasUsername = Boolean(normalizeCredentialValue(account.username));
  const hasPassword = Boolean(normalizeCredentialValue(account.password));

  elements.accountDetailSiteName.textContent = account.site_name;
  elements.accountDetailStatus.textContent = hasPassword ? "저장됨" : "비밀번호 없음";
  elements.accountDetailStatus.className = `status ${hasPassword ? "healthy" : "warning"}`;
  elements.accountDetailSummary.textContent = account.description || "설명이 아직 없습니다.";
  elements.accountDetailUrl.textContent = account.url || "-";
  elements.accountDetailUsername.innerHTML = renderAccountCredentialButton(account, "username", "detail");
  elements.accountDetailPassword.innerHTML = renderAccountCredentialButton(account, "password", "detail");
  elements.accountDetailNote.textContent = account.note || "-";
  elements.accountDetailCreatedAt.textContent = formatTime(account.created_at);
  elements.accountDetailUpdatedAt.textContent = formatTime(account.updated_at);
  elements.accountDetailNoteBox.textContent = hasUsername && hasPassword
    ? "저장된 ID와 비밀번호를 클릭하면 바로 복사할 수 있습니다."
    : hasUsername
      ? "저장된 ID는 클릭하면 복사됩니다. 비밀번호는 아직 등록되지 않았습니다."
      : hasPassword
        ? "저장된 비밀번호는 클릭하면 복사됩니다. ID는 아직 등록되지 않았습니다."
        : "ID와 비밀번호가 아직 등록되지 않았습니다. 수정 버튼으로 바로 입력할 수 있습니다.";
  elements.openSiteButton.disabled = !account.url;
  elements.editAccountButton.disabled = false;
  elements.deleteAccountButton.disabled = false;
  bindAccountCredentialButtons();
}

function renderSiteAccounts() {
  const filtered = applySiteAccountFilter(state.siteAccounts);
  elements.siteAccountResultMeta.textContent = `정렬: 사이트명 오름차순 / 현재 ${filtered.length}건`;

  const selectedInFiltered = filtered.find((item) => item.id === state.selectedAccountId);
  if (!selectedInFiltered) {
    state.selectedAccountId = filtered[0]?.id || null;
  }

  if (filtered.length === 0) {
    elements.siteAccountsTableBody.innerHTML = `
      <tr>
        <td colspan="6" class="empty-cell">조건에 맞는 사이트 계정이 없습니다.</td>
      </tr>
    `;
    renderSelectedAccount();
    return;
  }

  elements.siteAccountsTableBody.innerHTML = filtered
    .map((item) => {
      const updatedText = item.updated_at ? `수정 ${escapeHtml(formatTime(item.updated_at))}` : "수정 기록 없음";
      const urlCell = item.url
        ? `<a class="url-icon-link" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" aria-label="${escapeHtml(item.site_name)} 열기">↗</a>`
        : `<span class="muted-inline">-</span>`;

      return `
        <tr data-account-id="${item.id}" class="${item.id === state.selectedAccountId ? "selected" : ""}">
          <td>
            <div class="primary-cell">
              <strong>${escapeHtml(item.site_name)}</strong>
              <span class="secondary-line">${updatedText}</span>
            </div>
          </td>
          <td class="wrap-cell">${escapeHtml(item.description || "-")}</td>
          <td>${urlCell}</td>
          <td>${renderAccountCredentialButton(item, "username")}</td>
          <td>${renderAccountCredentialButton(item, "password")}</td>
          <td class="wrap-cell site-account-note-cell">${escapeHtml(item.note || "-")}</td>
        </tr>
      `;
    })
    .join("");

  Array.from(elements.siteAccountsTableBody.querySelectorAll("tr[data-account-id]")).forEach((row) => {
    row.addEventListener("click", () => {
      state.selectedAccountId = row.dataset.accountId;
      state.accountEditorMode = "detail";
      renderSiteAccounts();
      renderSelectedAccount();
    });
  });

  Array.from(elements.siteAccountsTableBody.querySelectorAll(".url-icon-link")).forEach((link) => {
    link.addEventListener("click", (event) => {
      event.stopPropagation();
    });
  });

  renderSelectedAccount();
}

function activateAccountFilter(button) {
  elements.accountFilterButtons.forEach((target) => target.classList.toggle("active", target === button));
  state.siteAccountFilter = button.dataset.accountFilter;
  renderSiteAccounts();
}

async function fetchSiteAccounts(options = {}) {
  const response = await fetchJson("/api/site-accounts", { headers: {} });
  state.siteAccounts = response.items || [];
  state.siteAccountsLoaded = true;
  setAccountSummary(response.summary || {});

  if (options.selectedAccountId) {
    state.selectedAccountId = options.selectedAccountId;
  } else if (!state.selectedAccountId && state.siteAccounts.length > 0) {
    state.selectedAccountId = state.siteAccounts[0].id;
  } else if (state.selectedAccountId && !state.siteAccounts.some((item) => item.id === state.selectedAccountId)) {
    state.selectedAccountId = state.siteAccounts[0]?.id || null;
  }

  renderSiteAccounts();
}

async function loadSiteAccounts() {
  try {
    setAccountFeedback("사이트 계정 목록을 불러오는 중입니다.");
    await fetchSiteAccounts();
    setAccountFeedback("사이트 계정 목록을 최신 상태로 불러왔습니다.");
  } catch (error) {
    setAccountFeedback(error.message);
    elements.accountStatusPill.textContent = "오류";
  }
}

function showAccountEditor(mode, account = null) {
  state.accountEditorMode = mode;
  elements.accountDetailView.classList.add("is-hidden");
  elements.accountEditorForm.classList.remove("is-hidden");

  const isEdit = mode === "edit" && account;
  elements.accountEditorTitle.textContent = isEdit ? "사이트 계정 수정" : "새 항목 추가";
  elements.accountEditorDescription.textContent = isEdit
    ? `${account.site_name} 항목을 수정합니다.`
    : "학교 내부에서 관리할 사이트 계정 정보를 입력하십시오.";
  elements.saveAccountButton.textContent = isEdit ? "수정 저장" : "새 항목 저장";
  elements.accountPasswordHint.textContent = isEdit
    ? "기존 비밀번호를 유지하려면 비워 두십시오."
    : "필요하면 바로 입력하고, 나중에 채워도 됩니다.";

  elements.accountSiteNameInput.value = account?.site_name || "";
  elements.accountDescriptionInput.value = account?.description || "";
  elements.accountUrlInput.value = account?.url || "";
  elements.accountUsernameInput.value = account?.username || "";
  elements.accountPasswordInput.value = "";
  elements.accountNoteInput.value = account?.note || "";
}

function hideAccountEditor() {
  state.accountEditorMode = "detail";
  renderSelectedAccount();
}

async function saveAccount(event) {
  event.preventDefault();
  const account = getSelectedAccount();
  const payload = {
    site_name: elements.accountSiteNameInput.value.trim(),
    description: elements.accountDescriptionInput.value.trim(),
    url: elements.accountUrlInput.value.trim(),
    username: elements.accountUsernameInput.value.trim(),
    note: elements.accountNoteInput.value.trim(),
  };

  const passwordValue = elements.accountPasswordInput.value.trim();
  const isEdit = state.accountEditorMode === "edit" && account;
  if (!isEdit || passwordValue) {
    payload.password = passwordValue;
  }

  try {
    const response = await fetchJson(isEdit ? `/api/site-accounts/${account.id}` : "/api/site-accounts", {
      method: isEdit ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    });
    await fetchSiteAccounts({ selectedAccountId: response.id });
    state.accountEditorMode = "detail";
    renderSelectedAccount();
    setAccountFeedback(isEdit ? "사이트 계정 정보를 수정했습니다." : "새 사이트 계정을 저장했습니다.");
  } catch (error) {
    setAccountFeedback(error.message);
  }
}

async function deleteSelectedAccount() {
  const account = getSelectedAccount();
  if (!account) {
    return;
  }
  const confirmed = window.confirm(`'${account.site_name}' 항목을 삭제하시겠습니까?`);
  if (!confirmed) {
    return;
  }

  try {
    await fetchJson(`/api/site-accounts/${account.id}`, { method: "DELETE" });
    state.selectedAccountId = null;
    await fetchSiteAccounts();
    setAccountFeedback("선택한 사이트 계정을 삭제했습니다.");
  } catch (error) {
    setAccountFeedback(error.message);
  }
}

function openSelectedSite() {
  const account = getSelectedAccount();
  if (!account || !account.url) {
    return;
  }
  window.open(account.url, "_blank", "noopener,noreferrer");
}

function handleSiteAccountSearch() {
  state.siteAccountSearchQuery = elements.siteAccountSearchInput.value || "";
  renderSiteAccounts();
}

function hideDeviceFeedback() {
  if (deviceFeedbackTimerId) {
    window.clearTimeout(deviceFeedbackTimerId);
    deviceFeedbackTimerId = null;
  }
  elements.deviceFeedbackText.textContent = "";
  elements.deviceFeedbackText.classList.add("is-hidden");
}

function setDeviceFeedback(message, options = {}) {
  const { visible = false, autoHideMs = 0 } = options;
  if (deviceFeedbackTimerId) {
    window.clearTimeout(deviceFeedbackTimerId);
    deviceFeedbackTimerId = null;
  }
  elements.deviceFeedbackText.textContent = message;
  if (!visible) {
    elements.deviceFeedbackText.classList.add("is-hidden");
    return;
  }
  elements.deviceFeedbackText.classList.remove("is-hidden");
  if (autoHideMs > 0) {
    deviceFeedbackTimerId = window.setTimeout(() => {
      hideDeviceFeedback();
    }, autoHideMs);
  }
}

function setDeviceSummary(summary = {}) {
  const total = summary.total ?? state.deviceInventory.length;
  const normal = summary.normal_use ?? state.deviceInventory.filter((item) => deviceStatusLabel(item.status) === "정상 사용").length;
  const repair = summary.life_cycle_due ?? state.deviceInventory.filter((item) => item.life_cycle_due).length;
  const inspection = summary.repair_or_inspection_needed ?? state.deviceInventory.filter((item) => deviceNeedsInspection(item)).length;

  elements.deviceTotalValue.textContent = String(total ?? 0);
  elements.deviceNormalValue.textContent = String(normal ?? 0);
  elements.deviceRepairValue.textContent = String(repair ?? 0);
  elements.deviceInspectionValue.textContent = String(inspection ?? 0);
  elements.deviceStatusPill.textContent = `총 ${total ?? 0}건`;
}

function applyDeviceFilter(devices) {
  let next = [...devices];

  if (state.deviceInventoryFilter !== "all") {
    next = next.filter((item) => item.asset_group === state.deviceInventoryFilter);
  }

  const query = state.deviceInventorySearchQuery.trim().toLowerCase();
  if (query) {
    next = next.filter((item) => {
      const haystack = [
        item.management_no,
        item.asset_group,
        item.location,
        item.device_type,
        item.manufacturer,
        item.model_name,
        item.serial_number,
        item.cpu,
        item.ram,
        item.assigned_user,
        item.status,
        item.acquired_at,
        item.note,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }

  next.sort((left, right) => {
    const leftKey = left.management_no || left.model_name || left.id;
    const rightKey = right.management_no || right.model_name || right.id;
    return leftKey.localeCompare(rightKey, "ko-KR", { sensitivity: "base", numeric: true });
  });
  return next;
}

function getSelectedDevice() {
  return state.deviceInventory.find((item) => item.id === state.selectedDeviceId) || null;
}

function resetDeviceDetail() {
  elements.deviceDetailName.textContent = "아직 선택된 항목이 없습니다";
  elements.deviceDetailStatus.textContent = "대기";
  elements.deviceDetailStatus.className = "status neutral";
  elements.deviceDetailSummary.textContent = "표에서 기기를 선택하면 아래에서 내용을 확인하고 바로 수정할 수 있습니다.";
  elements.deviceDetailManagementNo.textContent = "-";
  elements.deviceDetailGroup.textContent = "-";
  elements.deviceDetailLocation.textContent = "-";
  elements.deviceDetailType.textContent = "-";
  elements.deviceDetailManufacturer.textContent = "-";
  elements.deviceDetailModelName.textContent = "-";
  elements.deviceDetailSerialNumber.textContent = "-";
  elements.deviceDetailCpu.textContent = "-";
  elements.deviceDetailRam.textContent = "-";
  elements.deviceDetailAcquiredAt.textContent = "-";
  elements.deviceDetailAge.textContent = "-";
  elements.deviceDetailStatusText.textContent = "-";
  elements.deviceDetailUser.textContent = "-";
  elements.deviceDetailNote.textContent = "-";
  elements.editDeviceButton.disabled = true;
  elements.deleteDeviceButton.disabled = true;
  closeDeviceImageModal();
}

function openDeviceImageModal(device) {
  if (!device?.image_url) {
    setDeviceFeedback("등록된 제품이미지가 없습니다.");
    return;
  }
  elements.deviceImageModalTitle.textContent = `${device.management_no || "기기"} 제품이미지`;
  elements.deviceImageModalImage.src = device.image_url;
  elements.deviceImageModalImage.alt = `${device.management_no || device.model_name || "기기"} 제품이미지`;
  elements.deviceImageModal.classList.remove("is-hidden");
  elements.deviceImageModal.setAttribute("aria-hidden", "false");
}

function closeDeviceImageModal() {
  elements.deviceImageModal.classList.add("is-hidden");
  elements.deviceImageModal.setAttribute("aria-hidden", "true");
  elements.deviceImageModalImage.removeAttribute("src");
  elements.deviceImageModalImage.alt = "제품이미지 미리보기";
}

function renderSelectedDevice() {
  if (state.deviceEditorMode !== "detail") {
    elements.deviceDetailView.classList.add("is-hidden");
    elements.deviceEditorForm.classList.remove("is-hidden");
    return;
  }

  elements.deviceDetailView.classList.remove("is-hidden");
  elements.deviceEditorForm.classList.add("is-hidden");

  const device = getSelectedDevice();
  if (!device) {
    resetDeviceDetail();
    return;
  }

  const status = deviceStatusLabel(device.status);
  elements.deviceDetailName.textContent = device.management_no || device.model_name || "선택된 기기";
  elements.deviceDetailStatus.textContent = status;
  elements.deviceDetailStatus.className = `status ${deviceStatusClass(device.status)}`;
  elements.deviceDetailSummary.textContent = [
    device.asset_group,
    device.location,
    device.device_type,
    [device.manufacturer, device.model_name].filter(Boolean).join(" "),
  ].filter(Boolean).join(" / ") || "상세 요약 정보가 없습니다.";
  elements.deviceDetailManagementNo.textContent = device.management_no || "-";
  elements.deviceDetailGroup.textContent = device.asset_group || "-";
  elements.deviceDetailLocation.textContent = device.location || "-";
  elements.deviceDetailType.textContent = device.device_type || "-";
  elements.deviceDetailManufacturer.textContent = device.manufacturer || "-";
  elements.deviceDetailModelName.textContent = device.model_name || "-";
  elements.deviceDetailSerialNumber.textContent = device.serial_number || "-";
  elements.deviceDetailCpu.textContent = device.cpu || "-";
  elements.deviceDetailRam.textContent = device.ram || "-";
  elements.deviceDetailAcquiredAt.textContent = formatDeviceDate(device.acquired_at);
  elements.deviceDetailAge.textContent = formatDeviceAge(device);
  elements.deviceDetailStatusText.textContent = status;
  elements.deviceDetailUser.textContent = device.assigned_user || "-";
  elements.deviceDetailNote.textContent = device.note || "-";
  elements.editDeviceButton.disabled = false;
  elements.deleteDeviceButton.disabled = false;
}

function renderDeviceInventory() {
  const filtered = applyDeviceFilter(state.deviceInventory);
  elements.deviceResultMeta.textContent = `정렬: 관리번호 기준 / 현재 ${filtered.length}건`;

  const selectedInFiltered = filtered.find((item) => item.id === state.selectedDeviceId);
  if (!selectedInFiltered) {
    state.selectedDeviceId = filtered[0]?.id || null;
  }

  if (!filtered.length) {
    elements.deviceInventoryTableBody.innerHTML = `
      <tr>
        <td colspan="14" class="empty-cell">조건에 맞는 기기가 없습니다.</td>
      </tr>
    `;
    renderSelectedDevice();
    return;
  }

  elements.deviceInventoryTableBody.innerHTML = filtered
    .map((item, index) => {
      const status = deviceStatusLabel(item.status);
      const statusClassName = deviceStatusClass(item.status);
      const imageButton = item.image_url
        ? `<button class="table-image-button" type="button" data-device-image="${escapeHtml(item.id)}">사진 보기</button>`
        : '<span class="muted-inline">없음</span>';
      return `
        <tr data-device-id="${escapeHtml(item.id)}" class="${item.id === state.selectedDeviceId ? "selected" : ""}">
          <td class="device-sequence-cell">${index + 1}</td>
          <td class="wrap-cell">${escapeHtml(item.location || "-")}</td>
          <td class="wrap-cell">${escapeHtml(item.device_type || "-")}</td>
          <td class="wrap-cell">${escapeHtml(item.manufacturer || "-")}</td>
          <td class="wrap-cell">${escapeHtml(item.model_name || "-")}</td>
          <td class="mono wrap-cell">${escapeHtml(item.serial_number || "-")}</td>
          <td class="wrap-cell device-cpu-cell">${escapeHtml(item.cpu || "-")}</td>
          <td class="wrap-cell device-ram-cell">${escapeHtml(item.ram || "-")}</td>
          <td>${escapeHtml(formatDeviceMonth(item.acquired_at))}</td>
          <td>${escapeHtml(formatDeviceAge(item))}</td>
          <td><span class="status ${statusClassName}">${escapeHtml(status)}</span></td>
          <td class="wrap-cell">${escapeHtml(item.note || "-")}</td>
          <td class="wrap-cell">${escapeHtml(item.assigned_user || "-")}</td>
          <td>${imageButton}</td>
        </tr>
      `;
    })
    .join("");

  Array.from(elements.deviceInventoryTableBody.querySelectorAll("tr[data-device-id]")).forEach((row) => {
    row.addEventListener("click", () => {
      state.selectedDeviceId = row.dataset.deviceId;
      state.deviceEditorMode = "detail";
      renderDeviceInventory();
      renderSelectedDevice();
    });
  });

  Array.from(elements.deviceInventoryTableBody.querySelectorAll("[data-device-image]")).forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const device = state.deviceInventory.find((item) => item.id === button.dataset.deviceImage);
      if (device) {
        openDeviceImageModal(device);
      }
    });
  });

  renderSelectedDevice();
}

function activateDeviceFilter(button) {
  elements.deviceFilterButtons.forEach((target) => target.classList.toggle("active", target === button));
  state.deviceInventoryFilter = button.dataset.deviceFilter;
  renderDeviceInventory();
}

function handleDeviceSearch() {
  state.deviceInventorySearchQuery = elements.deviceSearchInput.value || "";
  renderDeviceInventory();
}

function showDeviceEditor(mode, device = null) {
  state.deviceEditorMode = mode;
  elements.deviceDetailView.classList.add("is-hidden");
  elements.deviceEditorForm.classList.remove("is-hidden");

  const isEdit = mode === "edit" && device;
  elements.deviceEditorTitle.textContent = isEdit ? "기기 정보 수정" : "새 장비 추가";
  elements.deviceEditorDescription.textContent = isEdit
    ? `${device.management_no || device.model_name || "선택한 기기"} 항목을 수정합니다.`
    : "학교 내부에서 관리할 기기 정보를 입력하십시오.";
  elements.saveDeviceButton.textContent = isEdit ? "수정 저장" : "새 장비 저장";
  elements.deviceEditorStatus.textContent = isEdit ? "수정 중" : "편집 중";
  elements.deviceManagementNoInput.value = device?.management_no || "";
  elements.deviceGroupInput.value = device?.asset_group || getDeviceMetadata().asset_groups?.[0]?.value || "";
  elements.deviceLocationInput.value = device?.location || "";
  elements.deviceTypeInput.value = device?.device_type || getDeviceMetadata().device_types?.[0]?.value || "";
  elements.deviceManufacturerInput.value = device?.manufacturer || "";
  elements.deviceModelNameInput.value = device?.model_name || "";
  elements.deviceSerialNumberInput.value = device?.serial_number || "";
  elements.deviceCpuInput.value = device?.cpu || "";
  elements.deviceRamInput.value = device?.ram || "";
  elements.deviceAcquiredAtInput.value = device?.acquired_at || "";
  elements.deviceStatusInput.value = device?.status || getDeviceMetadata().statuses?.[0]?.value || "";
  elements.deviceUserInput.value = device?.assigned_user || "";
  elements.deviceImageInput.value = device?.image_url || "";
  elements.deviceNoteInput.value = device?.note || "";
}

function hideDeviceEditor() {
  state.deviceEditorMode = "detail";
  renderSelectedDevice();
}

function buildDevicePayload() {
  return {
    management_no: elements.deviceManagementNoInput.value.trim(),
    asset_group: elements.deviceGroupInput.value.trim(),
    location: elements.deviceLocationInput.value.trim(),
    device_type: elements.deviceTypeInput.value.trim(),
    manufacturer: elements.deviceManufacturerInput.value.trim(),
    model_name: elements.deviceModelNameInput.value.trim(),
    serial_no: elements.deviceSerialNumberInput.value.trim(),
    cpu: elements.deviceCpuInput.value.trim(),
    ram: elements.deviceRamInput.value.trim(),
    introduced_date: elements.deviceAcquiredAtInput.value,
    status: elements.deviceStatusInput.value.trim(),
    user_name: elements.deviceUserInput.value.trim(),
    image_url: elements.deviceImageInput.value.trim(),
    notes: elements.deviceNoteInput.value.trim(),
  };
}

async function fetchDeviceInventory() {
  const response = await fetchJson("/api/device-inventory", { headers: {} });
  const metadata = response.metadata || response.meta || {};
  state.deviceMetadata = {
    asset_groups: resolveOptionList(metadata.asset_groups || metadata.assetGroups, DEFAULT_DEVICE_METADATA.asset_groups),
    device_types: resolveOptionList(metadata.device_types || metadata.deviceTypes, DEFAULT_DEVICE_METADATA.device_types),
    statuses: resolveOptionList(metadata.statuses, DEFAULT_DEVICE_METADATA.statuses),
  };
  populateDeviceSelectOptions();
  state.deviceInventory = normalizeDeviceItems(response.items || response.devices || []);
  state.deviceInventoryLoaded = true;
  setDeviceSummary(response.summary || {});
  if (!state.selectedDeviceId && state.deviceInventory.length) {
    state.selectedDeviceId = state.deviceInventory[0].id;
  }
  if (state.selectedDeviceId && !state.deviceInventory.some((item) => item.id === state.selectedDeviceId)) {
    state.selectedDeviceId = state.deviceInventory[0]?.id || null;
  }
}

async function loadDeviceInventory(options = {}) {
  const { showRefreshFeedback = false } = options;
  try {
    if (showRefreshFeedback) {
      setDeviceFeedback("기기관리대장 목록을 새로고침하는 중입니다.", { visible: true });
    } else {
      hideDeviceFeedback();
    }
    await fetchDeviceInventory();
    renderDeviceInventory();
    if (showRefreshFeedback) {
      setDeviceFeedback("기기관리대장 목록을 최신 상태로 불러왔습니다.", {
        visible: true,
        autoHideMs: 2600,
      });
    } else {
      hideDeviceFeedback();
    }
    elements.deviceStatusPill.textContent = `총 ${state.deviceInventory.length}건`;
  } catch (error) {
    setDeviceFeedback(error.message, { visible: true });
    state.deviceInventory = [];
    state.deviceInventoryLoaded = false;
    state.selectedDeviceId = null;
    renderDeviceInventory();
    setDeviceSummary({ total: 0, normal_use: 0, life_cycle_due: 0, repair_or_inspection_needed: 0 });
    elements.deviceStatusPill.textContent = "오류";
  }
}

async function saveDevice(event) {
  event.preventDefault();
  const currentDevice = getSelectedDevice();
  const payload = buildDevicePayload();
  const isEdit = state.deviceEditorMode === "edit" && currentDevice;

  try {
    const response = await fetchJson(isEdit ? `/api/device-inventory/${currentDevice.id}` : "/api/device-inventory", {
      method: isEdit ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    });
    state.deviceEditorMode = "detail";
    await loadDeviceInventory();
    state.selectedDeviceId = response.id || currentDevice?.id || state.selectedDeviceId;
    renderDeviceInventory();
    hideDeviceFeedback();
  } catch (error) {
    setDeviceFeedback(error.message, { visible: true });
  }
}

async function deleteSelectedDevice() {
  const device = getSelectedDevice();
  if (!device) {
    return;
  }

  const confirmed = window.confirm(`'${device.management_no || device.model_name || "선택한 기기"}' 항목을 삭제하시겠습니까?`);
  if (!confirmed) {
    return;
  }

  try {
    await fetchJson(`/api/device-inventory/${device.id}`, { method: "DELETE" });
    state.selectedDeviceId = null;
    state.deviceEditorMode = "detail";
    await loadDeviceInventory();
    hideDeviceFeedback();
  } catch (error) {
    setDeviceFeedback(error.message, { visible: true });
  }
}

async function openDeviceCsvImport() {
  elements.deviceImportInput.click();
}

async function importDeviceCsv(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) {
    return;
  }

  const csvText = await file.text();
  if (!csvText.trim()) {
    setDeviceFeedback("빈 CSV 파일은 가져올 수 없습니다.", { visible: true });
    event.target.value = "";
    return;
  }

  try {
    hideDeviceFeedback();
    const result = await fetchJson("/api/device-inventory/import-csv", {
      method: "POST",
      body: JSON.stringify({
        csv_text: csvText,
        file_name: file.name,
      }),
    });
    await loadDeviceInventory();
    hideDeviceFeedback();
  } catch (error) {
    setDeviceFeedback(error.message, { visible: true });
  } finally {
    event.target.value = "";
  }
}

async function downloadDeviceReport() {
  const fallbackName = `기기관리대장_보고서_${new Date().toISOString().slice(0, 10)}.xlsx`;
  try {
    const response = await fetch("/api/device-inventory/report-xlsx", { headers: {} });
    if (response.status === 401) {
      const payload = await response.json();
      handleAuthenticationRequired(payload.error || "로그인이 필요합니다.");
      throw new Error(payload.error || "로그인이 필요합니다.");
    }
    if (!response.ok) {
      throw new Error("보고서 다운로드 요청에 실패했습니다.");
    }
    const disposition = response.headers.get("content-disposition") || "";
    const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/)?.[1];
    const fileName = encodedName ? decodeURIComponent(encodedName) : fallbackName;
    const blob = await response.blob();
    downloadBlob(fileName, blob);
    hideDeviceFeedback();
  } catch (error) {
    setDeviceFeedback(error.message, { visible: true });
  }
}

async function handleRefreshDevices() {
  await loadDeviceInventory({ showRefreshFeedback: true });
}

elements.loginForm.addEventListener("submit", handleLoginSubmit);
elements.logoutButton.addEventListener("click", handleLogout);
elements.navItems.forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

elements.scanForm.addEventListener("submit", startScan);
elements.cancelScanButton.addEventListener("click", cancelScan);
elements.defaultRangeButton.addEventListener("click", () => applyDefaultRange());
elements.clearButton.addEventListener("click", clearResults);
elements.copyJsonButton.addEventListener("click", copyAllResults);
elements.copySelectedButton.addEventListener("click", copySelectedResult);
elements.resultSearchInput.addEventListener("input", handleResultSearch);
elements.filterButtons.forEach((button) => {
  button.addEventListener("click", () => activateFilter(button));
});

elements.refreshAccountsButton.addEventListener("click", loadSiteAccounts);
elements.newAccountButton.addEventListener("click", () => showAccountEditor("create"));
elements.siteAccountSearchInput.addEventListener("input", handleSiteAccountSearch);
elements.accountFilterButtons.forEach((button) => {
  button.addEventListener("click", () => activateAccountFilter(button));
});
elements.openSiteButton.addEventListener("click", openSelectedSite);
elements.editAccountButton.addEventListener("click", () => {
  const account = getSelectedAccount();
  if (account) {
    showAccountEditor("edit", account);
  }
});
elements.deleteAccountButton.addEventListener("click", deleteSelectedAccount);
elements.accountEditorForm.addEventListener("submit", saveAccount);
elements.cancelAccountEditButton.addEventListener("click", hideAccountEditor);

elements.refreshDevicesButton.addEventListener("click", handleRefreshDevices);
elements.newDeviceButton.addEventListener("click", () => showDeviceEditor("create"));
elements.deviceSearchInput.addEventListener("input", handleDeviceSearch);
elements.deviceFilterButtons.forEach((button) => {
  button.addEventListener("click", () => activateDeviceFilter(button));
});
elements.editDeviceButton.addEventListener("click", () => {
  const device = getSelectedDevice();
  if (device) {
    showDeviceEditor("edit", device);
  }
});
elements.deleteDeviceButton.addEventListener("click", deleteSelectedDevice);
elements.deviceEditorForm.addEventListener("submit", saveDevice);
elements.cancelDeviceEditButton.addEventListener("click", hideDeviceEditor);
elements.deviceImportButton.addEventListener("click", openDeviceCsvImport);
elements.deviceImportInput.addEventListener("change", importDeviceCsv);
elements.deviceReportButton.addEventListener("click", downloadDeviceReport);
elements.deviceImageModalBackdrop.addEventListener("click", closeDeviceImageModal);
elements.deviceImageModalClose.addEventListener("click", closeDeviceImageModal);
elements.deviceImageModal.addEventListener("click", (event) => {
  if (event.target === elements.deviceImageModal) {
    closeDeviceImageModal();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !elements.deviceImageModal.classList.contains("is-hidden")) {
    closeDeviceImageModal();
  }
});

setLoginFooterYear();
setSessionUserMeta("");
checkSession();
