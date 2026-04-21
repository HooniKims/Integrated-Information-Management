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

  async function copyTextToClipboard(text, env = globalThis) {
    const clipboard = env?.navigator?.clipboard;
    let clipboardError = null;

    if (clipboard?.writeText) {
      try {
        await clipboard.writeText(text);
        return "clipboard";
      } catch (error) {
        clipboardError = error;
      }
    }

    const documentRef = env?.document;
    const body = documentRef?.body;
    const canUseExecCommand =
      documentRef &&
      typeof documentRef.createElement === "function" &&
      typeof documentRef.execCommand === "function" &&
      body &&
      typeof body.appendChild === "function";

    if (!canUseExecCommand) {
      throw clipboardError || new Error("copy failed");
    }

    const textArea = documentRef.createElement("textarea");
    textArea.value = text;
    if (typeof textArea.setAttribute === "function") {
      textArea.setAttribute("readonly", "");
    }
    if (!textArea.style) {
      textArea.style = {};
    }
    textArea.style.position = "fixed";
    textArea.style.opacity = "0";
    textArea.style.pointerEvents = "none";

    body.appendChild(textArea);
    if (typeof textArea.focus === "function") {
      textArea.focus();
    }
    if (typeof textArea.select === "function") {
      textArea.select();
    }
    if (typeof textArea.setSelectionRange === "function") {
      textArea.setSelectionRange(0, textArea.value.length);
    }

    const copied = documentRef.execCommand("copy");

    if (typeof textArea.remove === "function") {
      textArea.remove();
    } else if (textArea.parentNode && typeof textArea.parentNode.removeChild === "function") {
      textArea.parentNode.removeChild(textArea);
    }

    if (!copied) {
      throw clipboardError || new Error("copy failed");
    }

    return "execCommand";
  }

  return {
    copyTextToClipboard,
    createCredentialCopyModel,
    getCredentialCopyFeedbackMessage,
    normalizeCredentialValue,
  };
});
