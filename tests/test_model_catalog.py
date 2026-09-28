"""모델 동향 전문가(T-007 r2 → R-010 벤더 분리·모델별 상세) 대역 테스트 — 실제 네트워크·LLM 없이.

snapshot / change / retry / failure / profile / inject / vendor / parse 를 커버한다.
실제 4개 출처·실제 LLM·브라우저는 수동 확인 대상이다.
"""
import json
import sys
import threading
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cc import expert  # noqa: E402
from src.cc import model_catalog as mc  # noqa: E402


@pytest.fixture
def mc_env(tmp_path, monkeypatch):
    """DATA_DIR/위키 경로를 임시 폴더로 돌리고, run_headless를 대역으로 바꾼다."""
    data_dir = tmp_path / "data" / "model_updates"
    monkeypatch.setattr(mc, "DATA_DIR", data_dir)

    wiki_dir = tmp_path / "docs_experts"
    wiki_dir.mkdir(parents=True)

    def fake_wiki_path(domain):
        return wiki_dir / f"{domain}.md"

    monkeypatch.setattr(expert, "wiki_path", fake_wiki_path)
    return {"wiki_dir": wiki_dir, "data_dir": data_dir}


def _fake_fetch(ok=True, body="", status=200, final_url="https://example.test/doc", error=None):
    return {"ok": ok, "status": status, "final_url": final_url, "body": body, "error": error}


PROFILE_OK = json.dumps({
    "overview": "테스트 모델 개요.",
    "spec": {"api_id": "test-model-1", "pricing": "$1/$5", "context": "200K/64K",
             "reasoning": "effort high", "cutoff": None, "availability": None, "retirement": None},
    "usage_tips": ["짧은 작업엔 low effort"],
    "harness_changes": ["config에 effort=low"],
    "gotchas": ["budget_tokens 미지원"],
    "sources": ["https://example.test/doc"],
})


def _llm_calls(monkeypatch, responses, profile=PROFILE_OK):
    """run_headless 대역 — 변경 추출 프롬프트에는 responses를 순서대로, 프로필 프롬프트에는
    profile을 준다. 반환값은 [(kind, prompt)] 기록."""
    calls = []
    change_idx = [0]

    def fake_run_headless(prompt, cwd, allowed_tools, disallowed_tools, timeout=300, **kw):
        if "상세 프로필" in prompt:
            calls.append(("profile", prompt))
            return profile
        calls.append(("change", prompt))
        i = change_idx[0]
        change_idx[0] += 1
        return responses[i] if i < len(responses) else responses[-1]

    monkeypatch.setattr(mc, "run_headless", fake_run_headless)
    return calls


def _n(calls, kind):
    return sum(1 for k, _ in calls if k == kind)


CLAUDE_MODELS_BODY = """# Claude 모델 개요

## Claude Opus 5.5
현재 최상위 모델. 기본 effort medium.

## Claude Sonnet 5
균형 모델.
"""

RELEASE_BODY_V1 = """# Release notes

### 2026-01-05 최초 출시
Claude Opus 4 출시.
"""

RELEASE_BODY_V2 = RELEASE_BODY_V1 + """
### 2026-09-20 도구 호출 갱신
Claude Opus 5.5의 도구 호출 프로토콜이 바뀌었다. 기존 프롬프트 재평가가 필요할 수 있다.
"""


def _valid_change(name="새 기능", model="Claude Opus 5.5", source_url="https://example.test/doc",
                  impact_type="asserted", **extra):
    item = {
        "name": name,
        "model": model,
        "announced_date": "2026-09-20",
        "confirmed_date": date.today().isoformat(),
        "diff": f"{name} 관련 변경",
        "usage_tips": ["도구 결과를 짧게 넣어라"],
        "harness_changes": ["도구 사용 프롬프트를 재평가"],
        "impact_type": impact_type,
        "source_url": source_url,
    }
    item.update(extra)
    return [item]


# ── snapshot: 최초 수집 + 동일 본문 재실행에서 LLM 0회, nav/script 변경은 무시 ──────────────────
class TestSnapshot:
    def test_first_collect_then_same_body_no_llm_call(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=CLAUDE_MODELS_BODY))
        calls = _llm_calls(monkeypatch, [json.dumps([])])

        r1 = mc.collect_source("claude-models")
        assert r1["ok"] and r1["changed"]
        first_calls = len(calls)
        assert first_calls >= 1  # 첫 수집은 기준선 정리를 위해 LLM을 부른다

        r2 = mc.collect_source("claude-models")
        assert r2["ok"] and r2["changed"] is False and r2["llm_called"] is False
        assert len(calls) == first_calls  # 동일 본문 재실행은 LLM을 추가로 부르지 않는다

    def test_html_nav_script_change_is_not_body_change(self, mc_env, monkeypatch):
        html_v1 = (
            "<html><head><script>var x=1;</script></head><body>"
            "<nav>홈 | 소개</nav>"
            "<main><h1>Changelog</h1><p>2026-09-01: 첫 기록</p></main>"
            "</body></html>"
        )
        html_v2 = (
            "<html><head><script>var x=2;</script></head><body>"
            "<nav>홈 | 소개 | 새 메뉴</nav>"
            "<main><h1>Changelog</h1><p>2026-09-01: 첫 기록</p></main>"
            "</body></html>"
        )
        calls = _llm_calls(monkeypatch, [json.dumps([])])
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=html_v1))
        r1 = mc.collect_source("codex-changelog")
        assert r1["ok"]
        n_after_first = len(calls)

        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=html_v2))
        r2 = mc.collect_source("codex-changelog")
        assert r2["ok"] and r2["changed"] is False
        assert len(calls) == n_after_first  # nav/script만 바뀐 건 본문 변경이 아니다


# ── change: 새 변경이 모델 절 아래 출처·팁·하네스와 함께 실리고, 과거 이력을 과장하지 않음 ──
class TestChange:
    def test_new_release_section_produces_model_entry_with_source(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        _llm_calls(monkeypatch, [json.dumps([])])
        r1 = mc.collect_source("claude-releases")
        assert r1["ok"]

        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V2))
        calls = _llm_calls(monkeypatch, [json.dumps(_valid_change("도구 호출 갱신"))])
        r2 = mc.collect_source("claude-releases")
        assert r2["ok"] and r2["changed"] and r2["changes"] == 1
        assert r2["models"] == ["Claude Opus 5.5"]
        assert _n(calls, "profile") == 1  # 바뀐 모델 하나 → 프로필 1회

        state = mc._load_state("claude")
        assert len(state["changes"]) == 1
        c = state["changes"][0]
        assert c["model"] == "Claude Opus 5.5" and c["source_url"].startswith("https://")
        assert c["impact_type"] == "asserted" and c["usage_tips"]

        wiki = (mc_env["wiki_dir"] / "models-claude.md").read_text(encoding="utf-8")
        assert "## Claude Opus 5.5" in wiki
        assert "도구 호출 갱신" in wiki and "https://example.test/doc" in wiki
        assert "### 잘 쓰는 법" in wiki and "### 하네스 조정" in wiki
        assert "### 변화 이력" in wiki
        assert "팁: 도구 결과를 짧게" in wiki

    def test_first_run_filters_old_dated_sections_including_english_dates(self):
        old = date.today() - timedelta(days=200)
        recent = date.today() - timedelta(days=5)
        sections = [
            (f"{old.isoformat()} 오래된 기록", f"{old.isoformat()}: 아주 오래전 변경"),
            ("하위 절(날짜 없음)", "직전 날짜를 물려받아 오래된 것으로 취급"),
            (recent.strftime("%B %d, %Y"), "최근 변경(영문 월 이름 날짜)"),
            ("최근 하위 절", "직전 최근 날짜를 물려받는다"),
        ]
        cutoff = date.today() - timedelta(days=90)
        kept = [t for t, _ in mc._filter_recent(sections, cutoff)]
        assert kept == [recent.strftime("%B %d, %Y"), "최근 하위 절"]

    def test_platform_only_items_are_not_stored(self, mc_env, monkeypatch):
        """LLM이 규칙을 어기고 model을 비우면 배치 전체를 거부한다(플랫폼·API 차단 방어)."""
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        _llm_calls(monkeypatch, [json.dumps(_valid_change("Files API", model=""))])
        r = mc.collect_source("claude-releases")
        assert r["ok"] is False and r["error"] == "llm_failed"
        assert mc._load_state("claude")["changes"] == []


# ── retry: fetch-only→실행, LLM 실패→재시도, 분할 입력에서 누락/중복 없음 ───────────────────
class TestRetry:
    def test_fetch_only_then_run_applies_pending_diff(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        calls = _llm_calls(monkeypatch, [json.dumps([])])

        r1 = mc.collect_source("claude-releases", fetch_only=True)
        assert r1["ok"] and r1["changed"] and r1["llm_called"] is False and r1.get("pending")
        assert len(calls) == 0  # fetch-only는 LLM을 부르지 않는다

        r2 = mc.collect_source("claude-releases")  # fetch-only 뒤 실제 실행 → 미반영 diff 반영
        assert r2["ok"] and r2["llm_called"] is True
        assert _n(calls, "change") == 1

    def test_llm_failure_then_retry_succeeds_without_losing_change(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        _llm_calls(monkeypatch, ["이건 JSON이 아니다"])
        r1 = mc.collect_source("claude-releases")
        assert r1["ok"] is False and r1["error"] == "llm_failed"
        assert mc._load_state("claude")["sources"]["claude-releases"].get("applied_hash") is None

        _llm_calls(monkeypatch, [json.dumps([])])
        r2 = mc.collect_source("claude-releases")  # 같은 본문 재시도 — 미반영 변경을 다시 시도
        assert r2["ok"] is True
        applied = mc._load_state("claude")["sources"]["claude-releases"]["applied_hash"]
        assert applied is not None

    def test_profile_failure_keeps_entries_and_retries_later(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        _llm_calls(monkeypatch, [json.dumps(_valid_change("첫 변경"))], profile="프로필 아님")
        r1 = mc.collect_source("claude-releases")
        assert r1["ok"] and r1["profiles_failed"] == ["Claude Opus 5.5"]
        state = mc._load_state("claude")
        assert len(state["changes"]) == 1 and "Claude Opus 5.5" not in state["profiles"]
        wiki = (mc_env["wiki_dir"] / "models-claude.md").read_text(encoding="utf-8")
        assert "상세 프로필 미생성" in wiki and "첫 변경" in wiki

        calls = _llm_calls(monkeypatch, [json.dumps([])])
        r2 = mc.refresh_profiles("claude")  # 수집 없이 어긋난 프로필만 재시도
        assert r2["ok"] and r2["updated"] == 1 and _n(calls, "profile") == 1
        assert "Claude Opus 5.5" in mc._load_state("claude")["profiles"]

    def test_same_day_multiple_changes_kept_per_model_without_duplication(self, mc_env,
                                                                          monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        _llm_calls(monkeypatch, [json.dumps([])])
        mc.collect_source("claude-releases")

        two = _valid_change("변경 A") + _valid_change("변경 B", model="Claude Sonnet 5")
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V2))
        calls = _llm_calls(monkeypatch, [json.dumps(two)])
        r = mc.collect_source("claude-releases")
        assert r["ok"] and r["changes"] == 2
        assert r["models"] == ["Claude Opus 5.5", "Claude Sonnet 5"]
        assert _n(calls, "profile") == 2

        state = mc._load_state("claude")
        assert {c["name"] for c in state["changes"]} == {"변경 A", "변경 B"}
        assert mc._models_in(state) == ["Claude Sonnet 5", "Claude Opus 5.5"]  # 최근 삽입 순

        # 같은 본문 재실행 → 배치 id로 중복 삽입 없음
        r_again = mc.collect_source("claude-releases")
        assert r_again["changed"] is False
        assert len(mc._load_state("claude")["changes"]) == 2

    def test_chunking_splits_large_diff_without_missing_or_duplicating(self, mc_env, monkeypatch):
        big_sections = "\n\n".join(
            f"## 절 {i}\n" + ("x" * 9000) for i in range(6)
        )  # 6절 × 9KB → 24,000자 청크 3개
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body="# 본문\n\n" + big_sections))
        responses = [json.dumps(_valid_change(f"청크 변경 {i}", model=f"모델 {i}"))
                     for i in range(3)]
        calls = _llm_calls(monkeypatch, responses)
        r = mc.collect_source("claude-models")
        assert r["ok"] and r["changes"] == 3
        assert _n(calls, "change") == 3
        assert all(len(p) < mc.CHUNK_LIMIT + 3000 for k, p in calls if k == "change")

    def test_per_model_rollup_keeps_recent_and_summarizes_rest(self, mc_env):
        state = mc._load_state("claude")
        for i in range(mc.RECENT_PER_MODEL + 3):
            state["changes"].insert(0, {
                "id": f"id{i}", "name": f"변경 {i}", "model": "Claude Opus 5.5", "diff": "d",
                "confirmed_date": "2026-09-28", "source_url": "https://example.test/doc",
                "impact_type": "none", "usage_tips": [], "harness_changes": [],
            })
        mc._rollup(state)
        assert len(state["changes"]) == mc.RECENT_PER_MODEL
        assert len(state["history"]["Claude Opus 5.5"]) == 3


# ── failure: 네트워크/본문/형식 오류, 동시 실행, 공개 중단 시 기존 위키 보존 ──────────────────
class TestFailure:
    def test_network_error_preserves_prior_changes(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        _llm_calls(monkeypatch, [json.dumps(_valid_change("살아남을 변경"))])
        assert mc.collect_source("claude-releases")["ok"]
        wiki_before = (mc_env["wiki_dir"] / "models-claude.md").read_text(encoding="utf-8")
        assert "살아남을 변경" in wiki_before

        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(ok=False, error="timeout"))
        r = mc.collect_source("claude-releases")
        assert r["ok"] is False
        state = mc._load_state("claude")
        assert state["sources"]["claude-releases"]["last_status"] == "error"
        assert len(state["changes"]) == 1
        wiki_after = (mc_env["wiki_dir"] / "models-claude.md").read_text(encoding="utf-8")
        assert "살아남을 변경" in wiki_after and "마지막 오류: timeout" in wiki_after

    def test_html_without_main_or_article_is_extract_failure(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch",
                            lambda url: _fake_fetch(body="<html><body><p>x</p></body></html>"))
        _llm_calls(monkeypatch, [json.dumps([])])
        r = mc.collect_source("codex-changelog")
        assert r["ok"] is False and r["error"] == "extract_failed"

    def test_empty_body_is_failure_not_silent_success(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body="   \n  "))
        _llm_calls(monkeypatch, [json.dumps([])])
        r = mc.collect_source("claude-models")
        assert r["ok"] is False and r["error"] == "empty_body"

    def test_concurrent_collect_keeps_state_consistent(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        _llm_calls(monkeypatch, [json.dumps([])])
        errors = []

        def worker():
            try:
                mc.collect_source("claude-releases")
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        state = json.loads(mc.state_path("claude").read_text(encoding="utf-8"))
        assert state["sources"]["claude-releases"]["applied_hash"]
        assert not (mc_env["data_dir"] / mc.LOCK_NAME).exists()

    def test_interrupted_wiki_write_preserves_existing_wiki(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        _llm_calls(monkeypatch, [json.dumps(_valid_change("원래 내용"))])
        assert mc.collect_source("claude-releases")["ok"]
        wiki = mc_env["wiki_dir"] / "models-claude.md"
        before = wiki.read_text(encoding="utf-8")

        real_replace = mc.os.replace

        def boom(src, dst):
            if str(dst).endswith("models-claude.md"):
                raise OSError("disk full")
            return real_replace(src, dst)

        monkeypatch.setattr(mc.os, "replace", boom)
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V2))
        _llm_calls(monkeypatch, [json.dumps(_valid_change("새 내용"))])
        with pytest.raises(OSError):
            mc.collect_source("claude-releases")
        assert wiki.read_text(encoding="utf-8") == before
        assert not list(mc_env["wiki_dir"].glob(".tmp-*"))


# ── vendor: 탭은 벤더별 둘, 각자 자기 출처만 수집하고 자기 위키를 갖는다 ──────────────────────
class TestVendor:
    def test_experts_are_exactly_the_vendor_tabs(self):
        assert list(expert.EXPERTS) == ["models-claude", "models-codex"]
        for domain, meta in expert.EXPERTS.items():
            assert meta["vendor"] == mc.MODEL_DOMAINS[domain]
        for vendor, meta in mc.VENDORS.items():
            assert all(mc.SOURCES[k]["vendor"] == vendor for k in meta["sources"])

    def test_vendor_collect_only_touches_its_own_state_and_wiki(self, mc_env, monkeypatch):
        codex_html = "<main><h1>Codex</h1><p>GPT-6 Sol</p></main>"
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(
            body=codex_html if "chatgpt" in url else CLAUDE_MODELS_BODY))
        _llm_calls(monkeypatch, [json.dumps(_valid_change("Sol 변경", model="GPT-6 Sol"))])
        r = mc.collect_vendor("codex")
        assert r["ok"] and set(r["sources"]) >= {"codex-models", "codex-changelog"}
        assert (mc_env["wiki_dir"] / "models-codex.md").exists()
        assert not (mc_env["wiki_dir"] / "models-claude.md").exists()
        assert mc.state_path("codex").exists() and not mc.state_path("claude").exists()
        codex_wiki = (mc_env["wiki_dir"] / "models-codex.md").read_text(encoding="utf-8")
        assert "## GPT-6 Sol" in codex_wiki

    def test_collect_knowledge_routes_domain_to_vendor(self, mc_env, monkeypatch):
        seen = []
        monkeypatch.setattr(expert, "collect_vendor", lambda v: seen.append(v) or {"ok": True})
        assert expert.collect_knowledge("models-codex")["ok"] and seen == ["codex"]
        assert expert.collect_knowledge("harness") == {"ok": False, "error": "unknown expert"}


# ── inject: 담당 전문가 자문 입력에 벤더별 동향 요약이 들어가고, 상태 없으면 빈 문자열 ────────────
class TestInject:
    def test_no_state_yet_gives_empty_brief(self, mc_env):
        assert mc.trend_brief() == ""

    def test_state_present_gives_per_vendor_brief(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        _llm_calls(monkeypatch, [json.dumps(_valid_change("도구 호출 갱신"))])
        assert mc.collect_source("claude-releases")["ok"]
        brief = mc.trend_brief()
        assert brief.startswith("Claude 모델 동향 (확인 ")
        assert "Claude Opus 5.5 / 도구 호출 갱신" in brief
        assert "Codex" not in brief  # 상태 없는 벤더는 빠진다


# ── parse: LLM 응답 검증 ─────────────────────────────────────────────────────────────
class TestParseValidation:
    def test_missing_required_field_rejected(self):
        bad = _valid_change()
        del bad[0]["model"]
        assert mc._parse_llm_changes(json.dumps(bad)) is None

    def test_non_https_source_rejected(self):
        assert mc._parse_llm_changes(json.dumps(_valid_change(source_url="http://x"))) is None

    def test_invalid_impact_type_rejected(self):
        assert mc._parse_llm_changes(json.dumps(_valid_change(impact_type="maybe"))) is None

    def test_non_list_tips_rejected(self):
        assert mc._parse_llm_changes(json.dumps(_valid_change(usage_tips="문자열"))) is None

    def test_code_fence_wrapped_json_is_accepted(self):
        out = mc._parse_llm_changes("```json\n" + json.dumps(_valid_change()) + "\n```")
        assert out and out[0]["model"] == "Claude Opus 5.5"

    def test_empty_array_is_valid_no_change(self):
        assert mc._parse_llm_changes("[]") == []

    def test_profile_requires_overview_and_list_fields(self):
        assert mc._parse_profile(PROFILE_OK)["spec"]["api_id"] == "test-model-1"
        assert mc._parse_profile(json.dumps({"overview": "", "spec": {}})) is None
        assert mc._parse_profile(json.dumps({"overview": "x", "usage_tips": "no"})) is None
        prof = mc._parse_profile(json.dumps({"overview": "x", "sources": ["http://bad", "https://ok"]}))
        assert prof["sources"] == ["https://ok"] and prof["spec"]["pricing"] is None
