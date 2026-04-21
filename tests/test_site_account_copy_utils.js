const test = require("node:test");
const assert = require("node:assert/strict");

const {
  copyTextToClipboard,
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

test("copyTextToClipboard falls back to execCommand when clipboard write fails", async () => {
  let appendedNode = null;
  let removedNode = null;
  const fakeBody = {
    appendChild(node) {
      appendedNode = node;
      node.parentNode = fakeBody;
    },
    removeChild(node) {
      removedNode = node;
      node.parentNode = null;
    },
  };
  const fakeDocument = {
    body: fakeBody,
    createElement() {
      return {
        style: {},
        setAttribute() {},
        focus() {},
        select() {},
        remove() {
          fakeBody.removeChild(this);
        },
      };
    },
    execCommand(command) {
      assert.equal(command, "copy");
      return true;
    },
  };

  const method = await copyTextToClipboard("teacher01", {
    navigator: {
      clipboard: {
        async writeText() {
          throw new Error("clipboard unavailable");
        },
      },
    },
    document: fakeDocument,
  });

  assert.equal(method, "execCommand");
  assert.equal(appendedNode.value, "teacher01");
  assert.equal(removedNode, appendedNode);
});

test("copyTextToClipboard keeps clipboard path when writeText succeeds", async () => {
  let copiedValue = "";

  const method = await copyTextToClipboard("pw-1234", {
    navigator: {
      clipboard: {
        async writeText(value) {
          copiedValue = value;
        },
      },
    },
  });

  assert.equal(method, "clipboard");
  assert.equal(copiedValue, "pw-1234");
});
