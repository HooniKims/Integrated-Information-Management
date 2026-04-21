(function initializeAuthUiUtils(globalScope, factory) {
  const api = factory();

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }

  globalScope.AuthUiUtils = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function createAuthUiUtils() {
  const STALE_SERVER_MESSAGE = "서버를 다시 시작해 주세요. 현재 실행 중인 서버가 로그인 기능 이전 버전일 수 있습니다.";

  function describeAuthServerErrorMessage(message) {
    if (message === "Unsupported route." || message === "Not found.") {
      return STALE_SERVER_MESSAGE;
    }
    return message || "로그인 처리 중 오류가 발생했습니다.";
  }

  return {
    describeAuthServerErrorMessage,
    STALE_SERVER_MESSAGE,
  };
});
