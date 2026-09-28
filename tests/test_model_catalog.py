"""모델 동향 전문가(T-007 r2) 대역 테스트 — 실제 네트워크·LLM 없이 코드 경로만 검증한다.

C1 snapshot / C2 change / C3 retry / C4 failure / C7 inject 를 커버한다.
C5·C6(실제 4개 출처·실제 LLM·브라우저)은 manifest.json에서 manual — PL이 별도 확인한다.
"""
import json
import sys
import threading
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cc import expert  # noqa: E402
from src.cc import model_catalog as mc


@pytest.fixture
def mc_env(tmp_path, monkeypatch):
    """DATA_DIR/위키 경로를 임시 폴더로 돌리고, run_headless를 대역으로 바꾼다."""
    data_dir = tmp_path / "data" / "model_updates"
    monkeypatch.setattr(mc, "DATA_DIR", data_dir)
    monkeypatch.setattr(mc, "STATE_PATH", data_dir / "state.json")
    monkeypatch.setattr(mc, "LOCK_PATH", data_dir / ".lock")

    wiki_dir = tmp_path / "docs_experts"
    wiki_dir.mkdir(parents=True)

    def fake_wiki_path(domain):
        return wiki_dir / f"{domain}.md"

    monkeypatch.setattr(expert, "wiki_path", fake_wiki_path)
    return {"wiki_dir": wiki_dir}


def _fake_fetch(ok=True, body="", status=200, final_url="https://example.test/doc", error=None):
    return {"ok": ok, "status": status, "final_url": final_url, "body": body, "error": error}


def _llm_calls(monkeypatch, responses):
    """run_headless를 순서대로 responses를 반환하는 대역으로 바꾸고 호출 기록을 돌려준다."""
    calls = []

    def fake_run_headless(prompt, cwd, allowed_tools, disallowed_tools, timeout=300, **kw):
        calls.append(prompt)
        idx = len(calls) - 1
        return responses[idx] if idx < len(responses) else responses[-1]

    monkeypatch.setattr(mc, "run_headless", fake_run_headless)
    return calls


CLAUDE_MODELS_BODY = """# Claude 모델 개요

## Claude Opus 5.5
현재 최상위 모델.

## Claude Sonnet 5
균형 모델.
"""

RELEASE_BODY_V1 = """# Release notes

### 2026-01-05 최초 출시
Claude Opus 4 출시.
"""

RELEASE_BODY_V2 = RELEASE_BODY_V1 + """
### 2026-09-20 도구 호출 갱신
도구 호출 프로토콜이 바뀌었다. 기존 프롬프트 재평가가 필요할 수 있다.
"""


def _valid_change(name="새 기능", source_url="https://example.test/doc", impact_type="asserted"):
    return [{
        "name": name,
        "announced_date": "2026-09-20",
        "confirmed_date": date.today().isoformat(),
        "diff": f"{name} 관련 변경",
        "impact": "도구 사용 프롬프트를 재평가할 것을 제안",
        "impact_type": impact_type,
        "source_url": source_url,
        "related": [],
    }]


# ── C1: 최초 수집 + 동일 본문 재실행에서 LLM 0회, nav/script 변경은 무시 ──────────────────
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


# ── C2: 새 변경이 출처·사실·적용 제안으로 설명되고, 과거 이력을 새 출시로 과장하지 않음 ──────
class TestChange:
    def test_new_release_section_produces_change_with_source_and_impact(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        _llm_calls(monkeypatch, [json.dumps([])])
        r1 = mc.collect_source("claude-releases")
        assert r1["ok"]

        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V2))
        _llm_calls(monkeypatch, [json.dumps(_valid_change("도구 호출 갱신"))])
        r2 = mc.collect_source("claude-releases")
        assert r2["ok"] and r2["changed"] and r2["changes"] == 1

        state = mc._load_state()
        assert len(state["changes"]) == 1
        c = state["changes"][0]
        assert c["name"] == "도구 호출 갱신"
        assert c["source_url"].startswith("https://")
        assert c["impact_type"] == "asserted"

        wiki = (mc_env["wiki_dir"] / "models.md").read_text(encoding="utf-8")
        assert "도구 호출 갱신" in wiki
        assert "https://example.test/doc" in wiki

    def test_first_run_filters_old_dated_sections_from_llm_input(self):
        old = date.today() - timedelta(days=200)
        recent = date.today() - timedelta(days=5)
        sections = [
            (f"{old.isoformat()} 오래된 기록", f"{old.isoformat()}: 아주 오래전 변경"),
            (f"{recent.isoformat()} 최근 기록", f"{recent.isoformat()}: 최근 변경"),
        ]
        cutoff = date.today() - timedelta(days=90)
        kept = mc._filter_recent(sections, cutoff)
        titles = [t for t, _ in kept]
        assert any("최근 기록" in t for t in titles)
        assert not any("오래된 기록" in t for t in titles)


# ── C3: fetch-only→실행, LLM 실패→재시도, 분할 입력에서 누락/중복 없음 ───────────────────
class TestRetry:
    def test_fetch_only_then_run_applies_pending_diff(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        calls = _llm_calls(monkeypatch, [json.dumps([])])

        r1 = mc.collect_source("claude-releases", fetch_only=True)
        assert r1["ok"] and r1["changed"] and r1["llm_called"] is False and r1.get("pending")
        assert len(calls) == 0  # fetch-only는 LLM을 부르지 않는다

        r2 = mc.collect_source("claude-releases")  # fetch-only 뒤 실제 실행 → 미반영 diff 반영
        assert r2["ok"] and r2["llm_called"] is True
        assert len(calls) == 1

    def test_llm_failure_then_retry_succeeds_without_losing_change(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        _llm_calls(monkeypatch, ["이건 JSON이 아니다"])
        r1 = mc.collect_source("claude-releases")
        assert r1["ok"] is False and r1["error"] == "llm_failed"

        state_after_fail = mc._load_state()
        assert state_after_fail["sources"]["claude-releases"].get("applied_hash") is None

        _llm_calls(monkeypatch, [json.dumps([])])
        r2 = mc.collect_source("claude-releases")  # 같은 본문 재시도 — 미반영 변경을 다시 시도
        assert r2["ok"] is True

        state_after_ok = mc._load_state()
        assert state_after_ok["sources"]["claude-releases"]["applied_hash"] is not None

    def test_same_day_multiple_distinct_changes_kept_without_duplication(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        _llm_calls(monkeypatch, [json.dumps([])])
        mc.collect_source("claude-releases")

        body_v2 = RELEASE_BODY_V1 + "\n### 2026-09-21 변경 A\n첫 번째 변경.\n"
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=body_v2))
        _llm_calls(monkeypatch, [json.dumps(_valid_change("변경 A"))])
        mc.collect_source("claude-releases")

        body_v3 = body_v2 + "\n### 2026-09-22 변경 B\n두 번째 변경.\n"
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=body_v3))
        _llm_calls(monkeypatch, [json.dumps(_valid_change("변경 B"))])
        mc.collect_source("claude-releases")

        # 같은 본문으로 재실행해도(재시도) 중복 삽입되지 않는다
        _llm_calls(monkeypatch, [json.dumps([])])
        mc.collect_source("claude-releases")

        state = mc._load_state()
        names = [c["name"] for c in state["changes"]]
        assert names.count("변경 A") == 1
        assert names.count("변경 B") == 1

    def test_chunking_splits_large_diff_without_missing_or_duplicating(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body="# base\n\n본문"))
        _llm_calls(monkeypatch, [json.dumps([])])
        mc.collect_source("claude-releases")

        section_a = "## 절 A\n" + ("가" * 20000)
        section_b = "## 절 B\n" + ("나" * 20000)
        big_body = f"# base\n\n본문\n\n{section_a}\n\n{section_b}"
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=big_body))
        calls = _llm_calls(monkeypatch, [
            json.dumps(_valid_change("절 A 변경")),
            json.dumps(_valid_change("절 B 변경")),
        ])
        r = mc.collect_source("claude-releases")
        assert r["ok"]
        assert len(calls) == 2  # 24,000자 제한으로 두 번에 나눠 호출
        for prompt in calls:
            assert len(prompt) < 30000  # 프롬프트 골격 포함해도 과도하게 크지 않음

        state = mc._load_state()
        names = {c["name"] for c in state["changes"]}
        assert {"절 A 변경", "절 B 변경"}.issubset(names)


# ── C4: 네트워크/본문/형식 오류, 동시 실행, 공개 중단 시 기존 위키 보존 ───────────────────
class TestFailure:
    def test_network_error_preserves_prior_changes(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        _llm_calls(monkeypatch, [json.dumps([])])
        mc.collect_source("claude-releases")

        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V2))
        _llm_calls(monkeypatch, [json.dumps(_valid_change("도구 호출 갱신"))])
        mc.collect_source("claude-releases")

        monkeypatch.setattr(
            mc, "_fetch", lambda url: _fake_fetch(ok=False, error="connect timeout"))
        r = mc.collect_source("claude-releases")
        assert r["ok"] is False and r["error"] == "connect timeout"

        wiki_after = (mc_env["wiki_dir"] / "models.md").read_text(encoding="utf-8")
        assert "도구 호출 갱신" in wiki_after
        state = mc._load_state()
        assert state["sources"]["claude-releases"]["last_status"] == "error"

    def test_html_without_main_or_article_is_extract_failure(self, mc_env, monkeypatch):
        no_main_html = "<html><body><div>본문 없음</div></body></html>"
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=no_main_html))
        r = mc.collect_source("codex-changelog")
        assert r["ok"] is False and r["error"] == "extract_failed"

    def test_empty_body_is_failure_not_silent_success(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body="   \n\n  "))
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
            t.join(timeout=10)

        assert not errors
        assert not mc.LOCK_PATH.exists()  # 잠금이 남지 않는다
        state = mc._load_state()  # state.json이 깨지지 않고 파싱된다
        assert "claude-releases" in state["sources"]

    def test_interrupted_wiki_write_preserves_existing_wiki(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V1))
        _llm_calls(monkeypatch, [json.dumps([])])
        mc.collect_source("claude-releases")
        wiki_path = mc_env["wiki_dir"] / "models.md"
        original = wiki_path.read_text(encoding="utf-8")

        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V2))
        _llm_calls(monkeypatch, [json.dumps(_valid_change("중단될 변경"))])

        real_atomic_write = mc._atomic_write

        def crash_on_wiki(path, text):
            if path == wiki_path:
                raise OSError("simulated crash before replace")
            real_atomic_write(path, text)

        monkeypatch.setattr(mc, "_atomic_write", crash_on_wiki)
        with pytest.raises(OSError):
            mc.collect_source("claude-releases")

        assert wiki_path.read_text(encoding="utf-8") == original  # 부분 기록 없이 원본 그대로
        assert not any(wiki_path.parent.glob(".tmp-*"))  # 임시 파일 잔재 없음


# ── C7: harness·llm-apps 수집/자문 입력에 모델동향 요약 주입, 위키 없을 때도 기존 기능 정상 ──
class TestInject:
    def test_no_state_yet_leaves_prompt_unchanged(self, mc_env):
        assert mc.trend_brief() == ""
        assert expert._with_trend_brief("harness", "기존 위키") == "기존 위키"

    def test_state_present_injects_brief_for_other_domains_only(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V2))
        _llm_calls(monkeypatch, [json.dumps(_valid_change("도구 호출 갱신"))])
        mc.collect_source("claude-releases")

        brief = mc.trend_brief()
        assert "확인 시각" in brief
        assert "도구 호출 갱신" in brief

        injected = expert._with_trend_brief("harness", "기존 하네스 위키")
        assert "최신 모델 동향 요약" in injected
        assert "도구 호출 갱신" in injected
        assert "기존 하네스 위키" in injected

        unchanged = expert._with_trend_brief("models", "기존 모델동향 위키")
        assert unchanged == "기존 모델동향 위키"  # 자기 자신에게는 주입하지 않는다

    def test_collect_knowledge_passes_augmented_prompt(self, mc_env, monkeypatch):
        monkeypatch.setattr(mc, "_fetch", lambda url: _fake_fetch(body=RELEASE_BODY_V2))
        _llm_calls(monkeypatch, [json.dumps(_valid_change("도구 호출 갱신"))])
        mc.collect_source("claude-releases")

        monkeypatch.setattr(expert, "read_wiki", lambda domain: "")
        monkeypatch.setattr(expert, "_neutral", lambda: str(mc_env["wiki_dir"]))
        captured = {}

        def fake_run_headless(prompt, cwd, allowed_tools, disallowed_tools, timeout=300, **kw):
            captured["prompt"] = prompt
            return "무시됨"

        monkeypatch.setattr(expert, "run_headless", fake_run_headless)
        expert.collect_knowledge("harness")
        assert "도구 호출 갱신" in captured["prompt"]


# ── LLM 응답 검증 — 구조/필수 필드/출처 링크가 어긋나면 배치 전체를 거부 ─────────────────
class TestParseValidation:
    def test_missing_required_field_rejected(self):
        bad = [{"name": "x", "confirmed_date": "2026-09-28", "diff": "d",
                 "impact": "", "impact_type": "asserted"}]  # source_url 없음
        assert mc._parse_llm_changes(json.dumps(bad)) is None

    def test_non_https_source_rejected(self):
        bad = _valid_change(source_url="http://insecure.test/doc")
        assert mc._parse_llm_changes(json.dumps(bad)) is None

    def test_invalid_impact_type_rejected(self):
        bad = _valid_change(impact_type="maybe")
        assert mc._parse_llm_changes(json.dumps(bad)) is None

    def test_code_fence_wrapped_json_is_accepted(self):
        wrapped = "```json\n" + json.dumps(_valid_change()) + "\n```"
        parsed = mc._parse_llm_changes(wrapped)
        assert parsed is not None and len(parsed) == 1

    def test_non_json_rejected(self):
        assert mc._parse_llm_changes("그냥 문장이다") is None

    def test_empty_array_is_valid_no_change(self):
        assert mc._parse_llm_changes("[]") == []
