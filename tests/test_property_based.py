"""tests.test_property_based — Hypothesis 驱动的属性测试。

覆盖:
- patient_id.encode/decode: 确定性 / 可逆 / 注入性 / 拒绝空
- scoring_card.dimensions: 所有评分函数返回值 ∈ [0, 100]

不构造 examples, 直接 st.builds / st.lists 让 Hypothesis 随机生成 100+ 用例,
捕获 example-based tests 漏的边界。
"""

from __future__ import annotations

import os
import string

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

# 确保 master key 已配置 (conftest.py 通常已设, 这里再确认一次)
os.environ.setdefault("LAB_DEID_KEY", "")
os.environ.setdefault("WORK_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lab_analysis import patient_id  # noqa: E402
from lab_analysis.scoring_card import dimensions  # noqa: E402

# ---------------------------------------------------------------------------
# patient_id.encode / decode — 确定性加密 + 可逆
# ---------------------------------------------------------------------------
# 任意字符串 (但跳过空 + 控制字符避免 _is_valid_id_card 误伤)
NON_EMPTY_TEXT = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Pc"),
        max_codepoint=0x7E,
    ),
    min_size=1,
    max_size=64,
)


class TestPatientIdDeterministic:
    """encode 必须 deterministic — 同一输入多次调用产出同一 deid。"""

    @given(s=NON_EMPTY_TEXT)
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_encode_is_deterministic(self, s):
        a = patient_id.encode(s)
        b = patient_id.encode(s)
        assert a == b, f"encode 不稳定: {s!r} → {a!r} vs {b!r}"


class TestPatientIdReversible:
    """decode(encode(x)) 必须 == x。"""

    @given(s=NON_EMPTY_TEXT)
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_decode_encode_roundtrip(self, s):
        deid = patient_id.encode(s)
        recovered = patient_id.decode(deid)
        assert recovered == s, f"可逆失败: {s!r} → {deid!r} → {recovered!r}"


class TestPatientIdInjective:
    """不同 input 应产出不同 deid (确定性加密天然成立, 但要确认)。"""

    @given(s1=NON_EMPTY_TEXT, s2=NON_EMPTY_TEXT)
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_different_inputs_yield_different_deids(self, s1, s2):
        assume(s1 != s2)
        d1 = patient_id.encode(s1)
        d2 = patient_id.encode(s2)
        assert d1 != d2, f"碰撞: {s1!r} 和 {s2!r} 都映射到 {d1!r}"


class TestPatientIdEmptyRejected:
    """encode/decode 必须拒绝空字符串。"""

    @given(s=st.just(""))
    def test_encode_rejects_empty(self, s):
        with pytest.raises(ValueError):
            patient_id.encode(s)

    @given(s=st.just(""))
    def test_decode_rejects_empty(self, s):
        with pytest.raises(ValueError):
            patient_id.decode(s)


class TestPatientIdDeidFormat:
    """deid 形如 URL-safe base64, 长度合理 (12 nonce + 加密/认证 tag)。"""

    @given(s=NON_EMPTY_TEXT)
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_deid_contains_only_url_safe_chars(self, s):
        deid = patient_id.encode(s)
        # base64 url-safe: A-Z a-z 0-9 - _
        allowed = set(string.ascii_letters + string.digits + "-_")
        assert set(deid) <= allowed, f"非法字符: {set(deid) - allowed} in {deid!r}"

    @given(s=NON_EMPTY_TEXT)
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_deid_nonempty_and_bounded_length(self, s):
        deid = patient_id.encode(s)
        # 12 nonce + N + 16-byte GCM tag; base64 url-safe 后约 36-200 字符
        # 输入越短 deid 也越短 (但不会比 36 短, 因为有 nonce+tag 的固定开销)
        assert 36 <= len(deid) <= 200, f"异常长度 {len(deid)}: {deid!r}"


# ---------------------------------------------------------------------------
# scoring_card.dimensions — 所有评分函数 clamp 到 [0, 100]
# ---------------------------------------------------------------------------
# 构造一个 generic 的 results dict, 让 Hypothesis 填充关键字段
_INFLAM_LABELS = st.lists(
    elements=st.sampled_from(["急性期", "缓解期", "过渡期", "未知"]),
    min_size=0,
    max_size=20,
)
_TRENDS = st.sampled_from(["上升", "下降", "平稳", None])
_R2 = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


@st.composite
def _inflammation_results(draw):
    n_labels = draw(st.integers(min_value=0, max_value=10))
    labels = draw(_INFLAM_LABELS)
    return {
        "inflammation_classification": {"labels": labels[:n_labels]},
        "linear_regression": {
            "hs-CRP": {
                "trend": draw(_TRENDS),
                "r2": draw(_R2),
            }
        },
    }


@st.composite
def _lab_abnormality_results(draw):
    n_abnormal = draw(st.integers(min_value=0, max_value=10))
    z_metrics = draw(
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=5, alphabet=string.ascii_letters),
                st.integers(min_value=0, max_value=5),
            ),
            min_size=0,
            max_size=5,
        )
    )
    abnormal = {f"m{i}": 1.0 for i in range(n_abnormal)}
    zscores = {
        name: {"outliers_severe": {"count": cnt}} for name, cnt in z_metrics
    }
    return abnormal, zscores


@st.composite
def _alerts(draw):
    n = draw(st.integers(min_value=0, max_value=10))
    levels = ["CRITICAL", "WARNING", "INFO"]
    return [
        {"level": draw(st.sampled_from(levels)), "msg": "x"} for _ in range(n)
    ]


class TestScoreInflammation:
    @given(results=_inflammation_results())
    @settings(max_examples=50, deadline=None)
    def test_score_in_range(self, results):
        s = dimensions.score_inflammation(results)
        assert 0.0 <= s <= 100.0, f"out of range: {s}"


class TestScoreLabAbnormality:
    @given(data=_lab_abnormality_results(), alerts=_alerts())
    @settings(max_examples=50, deadline=None)
    def test_score_in_range(self, data, alerts):
        abnormal, zscores = data
        results = {"abnormal_summary": abnormal, "zscore_outliers": zscores}
        s = dimensions.score_lab_abnormality(results, alerts)
        assert 0.0 <= s <= 100.0, f"out of range: {s}"


@st.composite
def _lit_papers(draw):
    tiers = ["S", "A", "B", "C", None]
    n = draw(st.integers(min_value=0, max_value=15))
    return [
        {
            "grade": {
                "tier": draw(st.sampled_from(tiers)),
                "score": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
            }
        }
        for _ in range(n)
    ]


class TestScoreLiteratureSupport:
    @given(papers=_lit_papers())
    @settings(max_examples=50, deadline=None)
    def test_score_in_range(self, papers):
        lit = {"filtered_papers": papers}
        s = dimensions.score_literature_support(lit)
        assert 0.0 <= s <= 100.0, f"out of range: {s}"

    @given(_=st.just(None))
    def test_empty_papers_returns_zero(self, _):
        # 空 papers → 0 (基线)
        assert dimensions.score_literature_support({"filtered_papers": []}) == 0.0


@st.composite
def _mri_checks(draw):
    statuses = ["success", "consistent", "fail", "conflict", "pending", None]
    n = draw(st.integers(min_value=0, max_value=20))
    return [{"status": draw(st.sampled_from(statuses))} for _ in range(n)]


class TestScoreImagingConsistency:
    @given(checks=_mri_checks())
    @settings(max_examples=50, deadline=None)
    def test_score_in_range(self, checks):
        s = dimensions.score_imaging_consistency({"results": checks})
        assert 0.0 <= s <= 100.0, f"out of range: {s}"

    @given(_=st.just(None))
    def test_no_imaging_returns_neutral(self, _):
        # 无影像 → 中值 50.0
        assert dimensions.score_imaging_consistency({}) == 50.0
        assert dimensions.score_imaging_consistency({"results": []}) == 50.0


@st.composite
def _cv_data(draw):
    risks = ["高", "中", "低", None]
    n = draw(st.integers(min_value=0, max_value=10))
    return {
        f"metric_{i}": {"risk_level": draw(st.sampled_from(risks))}
        for i in range(n)
    }


class TestScoreVariabilityRisk:
    @given(cv_data=_cv_data())
    @settings(max_examples=50, deadline=None)
    def test_score_in_range(self, cv_data):
        s = dimensions.score_variability_risk({"cv_stability": cv_data})
        assert 0.0 <= s <= 100.0, f"out of range: {s}"

    @given(_=st.just(None))
    def test_no_cv_returns_neutral(self, _):
        assert dimensions.score_variability_risk({"cv_stability": {}}) == 50.0
        assert dimensions.score_variability_risk({}) == 50.0


# ---------------------------------------------------------------------------
# 一致性: 输入不变, 输出不变 (idempotence)
# ---------------------------------------------------------------------------
class TestDimensionsIdempotent:
    @given(results=_inflammation_results())
    @settings(max_examples=20, deadline=None)
    def test_inflammation_idempotent(self, results):
        s1 = dimensions.score_inflammation(results)
        s2 = dimensions.score_inflammation(results)
        assert s1 == s2, f"非幂等: {s1} vs {s2}"