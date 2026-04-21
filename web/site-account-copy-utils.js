(function initializeSiteAccountCopyUtils(globalScope, factory) {
  const api = factory();

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }

  globalScope.SiteAccountCopyUtils = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function createSiteAccountCopyUtils() {
  const STATUS_TEXT = {
    idle: "클릭해 복사",
    copied: "복사됨",
    failed: "복사 실패",
  };

  function normalizeCredentialValue(value) {
    return String(value ?? "").trim();
  }

  function createCredentialCopyModel(value, status = "idle") {
    const normalizedValue = normalizeCredentialValue(value);
    const hasValue = normalizedValue.length > 0;
    const safeStatus = STATUS_TEXT[status] ? status : "idle";

    return {
      normalizedValue,
      displayValue: hasValue ? normalizedValue : "-",
      hintText: hasValue ? STATUS_TEXT[safeStatus] : "값 없음",
      statusClassName: hasValue ? `is-${safeStatus}` : "is-empty",
      disabled: !hasValue,
      hasValue,
    };
  }

  function getCredentialCopyFeedbackMessage({ siteName, fieldLabel, success, hasValue }) {
    if (!hasValue) {
      return `${siteName} ${fieldLabel}가 없습니다.`;
    }
    return success ? `${siteName} ${fieldLabel}를 복사했습니다.` : `${siteName} ${fieldLabel} 복사에 실패했습니다.`;
  }

  return {
    createCredentialCopyModel,
    getCredentialCopyFeedbackMessage,
    normalizeCredentialValue,
  };
});
