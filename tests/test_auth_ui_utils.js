const test = require("node:test");
const assert = require("node:assert/strict");

const { describeAuthServerErrorMessage } = require("../web/auth-ui-utils.js");

test("Unsupported route 오류는 서버 재시작 안내로 바꾼다", () => {
  assert.equal(
    describeAuthServerErrorMessage("Unsupported route."),
    "서버를 다시 시작해 주세요. 현재 실행 중인 서버가 로그인 기능 이전 버전일 수 있습니다."
  );
});

test("Not found 오류도 서버 재시작 안내로 바꾼다", () => {
  assert.equal(
    describeAuthServerErrorMessage("Not found."),
    "서버를 다시 시작해 주세요. 현재 실행 중인 서버가 로그인 기능 이전 버전일 수 있습니다."
  );
});

test("일반 오류는 그대로 유지한다", () => {
  assert.equal(describeAuthServerErrorMessage("아이디 또는 비밀번호가 올바르지 않습니다."), "아이디 또는 비밀번호가 올바르지 않습니다.");
});
