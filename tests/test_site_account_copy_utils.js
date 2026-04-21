const test = require("node:test");
const assert = require("node:assert/strict");

const {
  createCredentialCopyModel,
  getCredentialCopyFeedbackMessage,
} = require("../web/site-account-copy-utils.js");

test("저장된 계정 값은 기본 복사 대기 상태를 만든다", () => {
  const model = createCredentialCopyModel(" teacher01 ");

  assert.deepEqual(model, {
    normalizedValue: "teacher01",
    displayValue: "teacher01",
    hintText: "클릭해 복사",
    statusClassName: "is-idle",
    disabled: false,
    hasValue: true,
  });
});

test("복사 완료 상태는 복사됨 문구를 돌려준다", () => {
  const model = createCredentialCopyModel("pw-1234", "copied");

  assert.equal(model.hintText, "복사됨");
  assert.equal(model.statusClassName, "is-copied");
});

test("빈 값은 복사 비활성 상태를 만든다", () => {
  const model = createCredentialCopyModel("   ");

  assert.deepEqual(model, {
    normalizedValue: "",
    displayValue: "-",
    hintText: "값 없음",
    statusClassName: "is-empty",
    disabled: true,
    hasValue: false,
  });
});

test("복사 성공 피드백 문구를 만든다", () => {
  const message = getCredentialCopyFeedbackMessage({
    siteName: "나이스",
    fieldLabel: "ID",
    success: true,
    hasValue: true,
  });

  assert.equal(message, "나이스 ID를 복사했습니다.");
});
