// HTML 한 장을 암호 걸린 HTML 한 장으로 바꾼다 — 브라우저에서 암호를 넣으면 그 자리에서 풀린다.
//
//   node scripts/encrypt_html.mjs <원본.html> <결과.html> <암호>
//
// 왜 이런 방식인가: 보고서를 공개 저장소에 올려도 내용은 안 보이게 하려는 것이다. 그래서
// 암호는 파일 어디에도 담기지 않고(해시조차 안 남긴다), 본문은 AES-256-GCM으로 통째로 잠근다.
// 암호에서 열쇠를 만들 때 PBKDF2를 100만 번 돌린다 — 사람은 1~2초 기다리면 되지만,
// 자동으로 수억 개를 대입하는 쪽에는 그 1~2초가 그대로 곱해진다.
// GCM은 무결성까지 확인해서, 암호가 틀리면 '깨진 내용'이 아니라 실패로 떨어진다.
//
// 한계도 분명히 적어둔다: 이 방식의 안전은 전적으로 암호의 길이·무작위성에 달렸다.
// 짧은 숫자 암호는 공개된 곳에 두면 시간이 걸릴 뿐 언젠가 뚫린다.

import { readFileSync, writeFileSync } from "node:fs";
import { pbkdf2Sync, randomBytes, createCipheriv } from "node:crypto";

const [src, dst, password] = process.argv.slice(2);
if (!src || !dst || !password) {
  console.error("사용법: node scripts/encrypt_html.mjs <원본.html> <결과.html> <암호>");
  process.exit(1);
}

const ITER = 1_000_000; // 브라우저 해독 1~2초 ↔ 대입 공격 비용 100만 배
const plain = readFileSync(src);
const salt = randomBytes(16);
const iv = randomBytes(12);
const key = pbkdf2Sync(password, salt, ITER, 32, "sha256");
const cipher = createCipheriv("aes-256-gcm", key, iv);
const body = Buffer.concat([cipher.update(plain), cipher.final()]);
const packed = Buffer.concat([body, cipher.getAuthTag()]).toString("base64"); // GCM 태그를 뒤에 붙인다(웹 표준과 같은 순서)

const title = (plain.toString("utf8").match(/<title>([^<]*)<\/title>/) || [, "암호 걸린 문서"])[1];

const out = `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} (암호 필요)</title></head>
<body style="margin:0;background:#f5f6f8;font-family:-apple-system,'Segoe UI','맑은 고딕',sans-serif;color:#20242b">
<div style="max-width:420px;margin:14vh auto;background:#fff;border:1px solid #e4e6ea;border-radius:12px;padding:26px 24px">
  <div style="font-size:17px;font-weight:700">${title}</div>
  <div style="font-size:12.5px;color:#8b8f96;margin:8px 0 18px">암호를 넣으면 이 화면에서 바로 열립니다. 암호는 이 파일에 들어 있지 않아, 틀리면 내용을 복구할 방법이 없습니다.</div>
  <form id="f" style="display:flex;gap:8px">
    <input id="pw" type="password" autofocus placeholder="암호" style="flex:1;min-width:0;padding:9px 11px;font-size:14px;border:1px solid #e4e6ea;border-radius:8px">
    <button style="padding:9px 16px;font-size:14px;border:none;background:#1a8a5a;color:#fff;border-radius:8px;cursor:pointer">열기</button>
  </form>
  <div id="msg" style="font-size:12.5px;color:#8b8f96;margin-top:12px;min-height:18px"></div>
</div>
<script>
const SALT = "${salt.toString("base64")}", IV = "${iv.toString("base64")}", DATA = "${packed}", ITER = ${ITER};
const b64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
const msg = document.getElementById('msg');

document.getElementById('f').addEventListener('submit', async e => {
  e.preventDefault();
  const pw = document.getElementById('pw').value;
  if (!pw) return;
  // 열쇠 만들기가 1~2초 걸린다(일부러 느리게 잡은 값이다) — 멈춘 게 아니라는 걸 알려준다
  msg.textContent = '여는 중… (1~2초)';
  await new Promise(r => setTimeout(r, 30));
  try {
    const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(pw), 'PBKDF2', false, ['deriveKey']);
    const key = await crypto.subtle.deriveKey(
      { name: 'PBKDF2', salt: b64(SALT), iterations: ITER, hash: 'SHA-256' },
      base, { name: 'AES-GCM', length: 256 }, false, ['decrypt']);
    const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: b64(IV) }, key, b64(DATA));
    const html = new TextDecoder().decode(plain);
    document.open(); document.write(html); document.close();
  } catch (err) {
    // GCM이 무결성까지 보므로, 여기로 떨어지는 건 사실상 암호가 틀린 경우다
    msg.textContent = '암호가 맞지 않습니다.';
  }
});
</script>
</body></html>`;

writeFileSync(dst, out);
const kb = n => (n / 1024).toFixed(0) + "KB";
console.log(`${dst} · 원본 ${kb(plain.length)} → 암호본 ${kb(Buffer.byteLength(out))} · PBKDF2 ${ITER.toLocaleString()}회 · AES-256-GCM`);
