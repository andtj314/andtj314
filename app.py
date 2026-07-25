
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Callable, Optional

import streamlit as st


# =========================================================
# 기본 설정
# =========================================================
st.set_page_config(
    page_title="서·논술형 자동 채점기",
    page_icon="📝",
    layout="wide",
)

st.title("📝 2회고사 대비 서·논술형 자동 채점기")
st.caption("1~3세트 문항을 의미 중심으로 판정하는 규칙 기반 채점 도구")


# =========================================================
# 문자열 처리
# =========================================================
def normalize(text: str) -> str:
    """띄어쓰기·문장부호 차이를 줄여 의미 패턴을 안정적으로 탐색한다."""
    text = unicodedata.normalize("NFKC", text or "")
    text = text.lower()
    text = re.sub(r"[\"'“”‘’`]", "", text)
    text = re.sub(r"[^0-9a-zA-Z가-힣\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compact(text: str) -> str:
    return re.sub(r"\s+", "", normalize(text))


def contains_any(text: str, patterns: List[str]) -> bool:
    t = compact(text)
    return any(compact(p) in t for p in patterns)


def contains_all_groups(text: str, groups: List[List[str]]) -> bool:
    return all(contains_any(text, group) for group in groups)


def count_group_hits(text: str, groups: List[List[str]]) -> int:
    return sum(1 for group in groups if contains_any(text, group))


def has_negated_phrase(text: str, targets: List[str]) -> bool:
    """
    단순 부정 탐지.
    예: '위험하지 않다', '감정이 없다', '흐르지 않는다'
    """
    t = compact(text)
    for target in targets:
        p = compact(target)
        if p in t:
            return True
    return False


# =========================================================
# 설명 방법 판정
# =========================================================
METHOD_ALIASES = {
    "정의": ["정의"],
    "예시": ["예시", "예"],
    "인과": ["인과", "원인과결과"],
    "분석": ["분석"],
    "비교와 대조": ["비교와대조", "비교대조", "비교", "대조"],
    "분류와 구분": ["분류와구분", "분류구분", "분류", "구분"],
}


def extract_labeled_method(text: str) -> Optional[str]:
    """문장 끝 괄호 표기 등에서 학생이 선택한 설명 방법을 탐지한다."""
    t = compact(text)
    for method, aliases in METHOD_ALIASES.items():
        if any(compact(alias) in t for alias in aliases):
            return method
    return None


def method_features(text: str, method: str) -> Tuple[bool, str]:
    """
    용어가 없어도 설명 방법의 의미가 구현되어 있으면 인정한다.
    특정 방법을 표기한 경우에는 해당 방법의 특성이 실제 답안에 드러나야 한다.
    """
    t = normalize(text)

    if method == "정의":
        ok = (
            contains_any(t, ["이란", "란", "뜻한다", "말한다", "의미한다", "전기이다", "현상이다"])
            and contains_any(t, ["정전기", "사회적 촉진", "사회적 억제", "인공 지능", "인공지능", "예술"])
        )
        return ok, "대상의 뜻이나 개념을 직접 밝혔는지 확인"

    if method == "예시":
        ok = (
            contains_any(t, ["예를 들어", "예로", "등", "커피숍", "도서관", "공부 모임", "피겨 스케이팅"])
            and len(normalize(text)) >= 12
        )
        return ok, "구체적인 사례가 제시되었는지 확인"

    if method == "인과":
        cause_markers = ["때문", "므로", "해서", "따라서", "그 결과", "로 인해", "에서", "점에서"]
        ok = contains_any(t, cause_markers) and (
            contains_any(t, ["효율", "위험하지", "예술로 보기 어렵", "가치", "감동", "집중"])
        )
        return ok, "원인과 결과가 연결되어 있는지 확인"

    if method == "비교와 대조":
        contrast_markers = ["반면", "하지만", "반대로", "와 달리", "보다", "그러나", "공통점", "차이점"]
        # 두 대상 또는 두 상황이 함께 있어야 함
        pair_hits = 0
        pairs = [
            (["쉬운 과제", "큰 노력이 필요 없는 과제"], ["어려운 과제", "도전이 필요한 과제"]),
            (["정전기"], ["실생활 전기", "집에서 사용하는 전기"]),
            (["인간의 예술", "인간 작품"], ["인공 지능 그림", "인공지능 그림", "ai 그림"]),
            (["흐르는 물"], ["고여 있는 물"]),
            (["함께", "다른 사람"], ["혼자"]),
        ]
        for left, right in pairs:
            if contains_any(t, left) and contains_any(t, right):
                pair_hits += 1
        ok = pair_hits >= 1 and contains_any(t, contrast_markers)
        return ok, "두 대상·상황의 차이가 대비되어 있는지 확인"

    if method == "분석":
        ok = (
            contains_any(t, ["요소", "부분", "구성", "경험", "관점", "환경", "감정", "철학", "이야기"])
            and count_group_hits(
                t,
                [
                    ["경험"],
                    ["관점"],
                    ["환경"],
                    ["감정"],
                    ["철학", "이야기"],
                ],
            ) >= 2
        )
        return ok, "대상을 여러 요소나 부분으로 나누어 설명했는지 확인"

    if method == "분류와 구분":
        ok = (
            contains_any(t, ["나뉜다", "구분된다", "분류된다", "종류", "두 가지", "한편"])
            and (
                contains_any(t, ["쉬운 과제", "어려운 과제"])
                or contains_any(t, ["인간의 예술", "인공 지능의 예술", "인공지능의 예술"])
            )
        )
        return ok, "일정한 기준으로 대상을 묶거나 나누었는지 확인"

    return False, "알 수 없는 설명 방법"


def detect_methods_by_meaning(text: str) -> List[str]:
    methods = []
    for method in METHOD_ALIASES:
        ok, _ = method_features(text, method)
        if ok:
            methods.append(method)
    return methods


# =========================================================
# 채점 결과 구조
# =========================================================
@dataclass
class GradeResult:
    passed: bool
    score: int
    max_score: int
    feedback: List[str] = field(default_factory=list)
    matched: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    misconceptions: List[str] = field(default_factory=list)


def result_to_markdown(result: GradeResult):
    if result.passed:
        st.success(f"통과 · {result.score}/{result.max_score}점")
    else:
        st.error(f"보완 필요 · {result.score}/{result.max_score}점")

    if result.matched:
        st.write("**충족 요소:** " + ", ".join(result.matched))
    if result.missing:
        st.write("**누락 요소:** " + ", ".join(result.missing))
    if result.misconceptions:
        st.write("**오개념·방향 오류:** " + ", ".join(result.misconceptions))
    for msg in result.feedback:
        st.info(msg)


# =========================================================
# 세트 1 채점
# =========================================================
def grade_s1_q1(a1: str, a2: str, a3: str) -> GradeResult:
    score = 0
    matched, missing, misconceptions = [], [], []

    ok1 = contains_any(a1, ["쉬운 과제", "비교적 쉬운 과제", "큰 노력이 필요 없는 과제", "큰 노력을 들일 필요가 없는 과제", "쉬운 취미"])
    if ok1:
        score += 1; matched.append("㉠ 쉬운 과제")
    else:
        missing.append("㉠ 쉬운 과제")

    wrong1 = contains_any(a1, ["어려운 과제", "도전이 필요한 과제"])
    if wrong1:
        misconceptions.append("㉠에 어려운 과제의 특성을 씀")

    ok2 = contains_any(a2, ["혼자 집중", "혼자 공부", "차분하게 혼자", "혼자 연습"]) and (
        contains_any(a2, ["익숙해질 때까지", "충분히 연습", "차분하게"]) or contains_any(a2, ["혼자 집중"])
    )
    if ok2:
        score += 1; matched.append("㉡ 혼자 집중·연습")
    else:
        missing.append("㉡ 혼자 집중·연습")

    if contains_any(a2, ["다른 사람과 함께", "친구들과 함께", "모임을 만들어", "커피숍", "도서관"]):
        misconceptions.append("㉡에 사회적 촉진 환경을 씀")

    ok3 = contains_any(a3, ["사회적 억제"])
    if ok3:
        score += 1; matched.append("㉢ 사회적 억제")
    else:
        missing.append("㉢ 사회적 억제")

    if contains_any(a3, ["사회적 촉진"]):
        misconceptions.append("사회적 촉진과 사회적 억제를 바꾸어 씀")

    passed = score == 3 and not misconceptions
    return GradeResult(passed, score, 3, matched=matched, missing=missing, misconceptions=misconceptions)


def grade_s1_q2(s1: str, s2: str) -> GradeResult:
    score = 0
    matched, missing, misconceptions, feedback = [], [], [], []

    combined = f"{s1} {s2}"

    easy_ok = contains_any(combined, ["쉬운 과제", "비교적 쉬운 과제", "큰 노력이 필요 없는 과제", "큰 노력을 들일 필요가 없는 과제"])
    social_ok = contains_any(combined, ["다른 사람과 함께", "친구들과 함께", "공부 모임", "모임을 만들어", "커피숍", "도서관"])
    hard_ok = contains_any(combined, ["어려운 과제", "지나치게 어려운 과제", "도전이 필요한 과제"])
    alone_ok = contains_any(combined, ["혼자 집중", "혼자 공부", "차분하게 혼자", "혼자 연습", "익숙해질 때까지"])

    # 오개념 교차 사용
    if contains_any(s1, ["어려운 과제", "도전이 필요한 과제"]) and contains_any(s1, ["함께", "친구", "모임", "커피숍"]):
        misconceptions.append("어려운 과제에 사회적 촉진 환경을 적용함")
    if contains_any(s2, ["쉬운 과제", "큰 노력이 필요 없는 과제"]) and contains_any(s2, ["혼자 집중", "혼자 공부"]):
        misconceptions.append("쉬운 과제에 사회적 억제 환경을 적용함")

    if easy_ok and social_ok:
        score += 1; matched.append("쉬운 과제→함께하는 환경")
    else:
        missing.append("쉬운 과제와 함께하는 환경의 연결")

    if hard_ok and alone_ok:
        score += 1; matched.append("어려운 과제→혼자 집중")
    else:
        missing.append("어려운 과제와 혼자 집중의 연결")

    m1_label = extract_labeled_method(s1)
    m2_label = extract_labeled_method(s2)
    m1_meaning = detect_methods_by_meaning(s1)
    m2_meaning = detect_methods_by_meaning(s2)

    # 용어가 없어도 의미가 있으면 인정
    chosen1 = m1_label or (m1_meaning[0] if m1_meaning else None)
    chosen2 = m2_label or (m2_meaning[0] if m2_meaning else None)

    method1_ok = bool(chosen1) and method_features(s1, chosen1)[0]
    method2_ok = bool(chosen2) and method_features(s2, chosen2)[0]

    if method1_ok and method2_ok and chosen1 != chosen2:
        score += 1
        matched.append(f"서로 다른 설명 방법({chosen1}, {chosen2})")
    else:
        missing.append("서로 다른 두 설명 방법의 실제 구현")
        if m1_label and not method1_ok:
            misconceptions.append(f"(1)에 {m1_label}을 표기했으나 그 특성이 드러나지 않음")
        if m2_label and not method2_ok:
            misconceptions.append(f"(2)에 {m2_label}을 표기했으나 그 특성이 드러나지 않음")
        if chosen1 and chosen2 and chosen1 == chosen2:
            misconceptions.append("두 문장에 같은 설명 방법을 사용함")

    # 결론 방향
    conclusion_ok = contains_any(combined, ["효율적", "좋다", "도움", "높인다", "적합"])
    if conclusion_ok:
        score += 1; matched.append("학습 전략의 결론 방향")
    else:
        missing.append("어떤 방법이 효율적인지에 대한 결론")

    passed = score == 4 and not misconceptions
    feedback.append("문장 끝의 설명 방법 표기는 권장되지만, 용어가 없어도 설명 방법의 의미가 실제로 구현되면 인정합니다.")
    return GradeResult(passed, score, 4, feedback, matched, missing, misconceptions)


def grade_s1_q3(visual: str, visual_effect: str, audio: str, audio_effect: str) -> GradeResult:
    score = 0
    matched, missing, misconceptions = [], [], []

    visual_ok = contains_any(visual, ["혼자", "한 명", "개인"]) and contains_any(visual, ["공부", "과제", "문제", "책상", "연습"])
    if visual_ok:
        score += 1; matched.append("시각: 혼자 공부")
    else:
        missing.append("시각 요소의 혼자 집중하는 장면")

    if contains_any(visual, ["친구들과", "여럿이", "모임", "함께 공부"]):
        misconceptions.append("어려운 과제 장면에 함께 공부하는 모습을 제시함")

    v_effect_ok = contains_any(visual_effect, ["어려운 과제", "도전이 필요한 과제"]) and contains_any(visual_effect, ["혼자 집중", "차분하게", "익숙해질 때까지", "연습"])
    if v_effect_ok:
        score += 1; matched.append("시각 효과: 어려운 과제와 혼자 집중의 연결")
    else:
        missing.append("시각 효과에서 지문 근거 제시")

    audio_ok = contains_any(audio, ["조용", "소음이 거의", "잔잔", "고요", "무음"])
    if audio_ok:
        score += 1; matched.append("청각: 조용한 분위기")
    else:
        missing.append("청각 요소의 조용한 분위기")

    if contains_any(audio, ["경쾌", "신나는", "큰 소리", "발소리", "책장 넘기는 소리"]):
        misconceptions.append("어려운 과제 장면에 사회적 촉진형 청각 요소를 사용함")

    a_effect_ok = contains_any(audio_effect, ["집중", "차분", "혼자", "어려운 과제"])
    if a_effect_ok:
        score += 1; matched.append("청각 효과: 집중 환경 강조")
    else:
        missing.append("청각 효과에서 집중 환경과의 연결")

    passed = score == 4 and not misconceptions
    return GradeResult(passed, score, 4, matched=matched, missing=missing, misconceptions=misconceptions)


# =========================================================
# 세트 2 채점
# =========================================================
def grade_s2_q1(a1: str, a2: str, a3: str) -> GradeResult:
    score = 0
    matched, missing, misconceptions = [], [], []

    ok1 = contains_all_groups(a1, [["높은 곳", "높이"], ["고여 있는 물", "고인 물", "머물러 있는 물"]])
    if ok1:
        score += 1; matched.append("㉠ 높은 곳에 고여 있는 물")
    else:
        missing.append("㉠ 높은 곳에 고여 있는 물")
    if contains_any(a1, ["흐르는 물", "폭포", "강물"]):
        misconceptions.append("정전기를 흐르는 물로 비유함")

    ok2 = contains_any(a2, ["전하가 이동하지 않", "전하가 머물", "전하가 정지", "이동하지 않고 머물"])
    if ok2:
        score += 1; matched.append("㉡ 전하가 이동하지 않음")
    else:
        missing.append("㉡ 전하가 이동하지 않음")
    if contains_any(a2, ["전하가 이동함", "전하가 흐름", "전류가 흐름"]):
        misconceptions.append("정전기에 실생활 전기의 특성을 씀")

    ok3 = contains_any(a3, ["위험하지 않", "안전"])
    if ok3:
        score += 1; matched.append("㉢ 위험하지 않음")
    else:
        missing.append("㉢ 위험하지 않음")
    if contains_any(a3, ["위험하다", "감전", "큰 피해"]):
        misconceptions.append("정전기가 위험하다고 씀")

    passed = score == 3 and not misconceptions
    return GradeResult(passed, score, 3, matched=matched, missing=missing, misconceptions=misconceptions)


def grade_s2_q2(s1: str, s2: str) -> GradeResult:
    score = 0
    matched, missing, misconceptions, feedback = [], [], [], []
    combined = f"{s1} {s2}"

    state_ok = contains_any(combined, ["고여 있는 물", "고인 물", "전하가 이동하지 않", "전하가 머물", "흐르지 않고 머물"])
    danger_ok = contains_any(combined, ["위험하지 않", "안전"])
    voltage_ok = contains_any(combined, ["전압은 매우 높", "전압이 높"])

    if state_ok:
        score += 1; matched.append("정전기의 정지·고임 특성")
    else:
        missing.append("전하가 이동하지 않고 머무는 특성")

    if danger_ok:
        score += 1; matched.append("위험하지 않다는 결론")
    else:
        missing.append("위험하지 않다는 결론")

    if contains_any(combined, ["전압이 낮", "전하가 이동함", "흐르는 물", "감전된다", "위험하다"]):
        misconceptions.append("정전기에 실생활 전기의 특성 또는 반대 결론을 적용함")

    m1_label = extract_labeled_method(s1)
    m2_label = extract_labeled_method(s2)
    m1_meaning = detect_methods_by_meaning(s1)
    m2_meaning = detect_methods_by_meaning(s2)
    chosen1 = m1_label or (m1_meaning[0] if m1_meaning else None)
    chosen2 = m2_label or (m2_meaning[0] if m2_meaning else None)
    method1_ok = bool(chosen1) and method_features(s1, chosen1)[0]
    method2_ok = bool(chosen2) and method_features(s2, chosen2)[0]

    if method1_ok and method2_ok and chosen1 != chosen2:
        score += 1; matched.append(f"서로 다른 설명 방법({chosen1}, {chosen2})")
    else:
        missing.append("서로 다른 두 설명 방법의 구현")
        if m1_label and not method1_ok:
            misconceptions.append(f"(1)에 {m1_label}을 표기했으나 특성이 없음")
        if m2_label and not method2_ok:
            misconceptions.append(f"(2)에 {m2_label}을 표기했으나 특성이 없음")
        if chosen1 and chosen2 and chosen1 == chosen2:
            misconceptions.append("두 문장에 같은 설명 방법을 사용함")

    # 인과를 선택한 경우 원인→결과 필수
    for i, sentence in enumerate([s1, s2], start=1):
        label = extract_labeled_method(sentence)
        if label == "인과":
            if not (
                contains_any(sentence, ["전하가 이동하지 않", "전하가 머물"])
                and contains_any(sentence, ["위험하지 않", "안전"])
                and contains_any(sentence, ["므로", "때문", "따라서", "해서"])
            ):
                misconceptions.append(f"({i}) 인과를 선택했으나 원인과 결과의 연결이 불충분함")

    # 전압은 필수는 아니지만 제시하면 방향 정확해야 함
    if voltage_ok:
        matched.append("전압이 높다는 특성도 정확히 제시")
    feedback.append("전압이 높다는 내용은 보조 요소이며, 핵심 통과 기준은 '전하가 머무름→위험하지 않음'입니다.")
    passed = score == 3 and not misconceptions
    return GradeResult(passed, score, 3, feedback, matched, missing, misconceptions)


def grade_s2_q3(visual: str, visual_effect: str, audio: str, audio_effect: str) -> GradeResult:
    score = 0
    matched, missing, misconceptions = [], [], []

    visual_ok = contains_any(visual, ["고여", "고인 물", "호수", "댐", "저수지", "그릇에 담긴 물"]) and not contains_any(visual, ["쏟아져", "흐르는", "폭포"])
    if visual_ok:
        score += 1; matched.append("시각: 고여 있는 물")
    else:
        missing.append("시각 요소의 고여 있는 물")
    if contains_any(visual, ["폭포", "흐르는 물", "쏟아지는 물"]):
        misconceptions.append("정전기 장면에 실생활 전기의 흐르는 물을 사용함")

    v_effect_ok = contains_any(visual_effect, ["전하가 이동하지 않", "전하가 머물", "흐르지 않"]) and contains_any(visual_effect, ["정전기", "특성", "보여", "전달", "이해"])
    if v_effect_ok:
        score += 1; matched.append("시각 효과: 전하가 머무는 특성")
    else:
        missing.append("시각 효과에서 전하가 머무는 지문 근거")

    audio_ok = contains_any(audio, ["조용", "고요", "잔잔", "소리가 거의", "무음"])
    if audio_ok:
        score += 1; matched.append("청각: 움직임이 적은 조용한 소리")
    else:
        missing.append("청각 요소의 조용한 분위기")
    if contains_any(audio, ["거세게", "웅장", "콸콸", "큰 물소리", "폭포 소리"]):
        misconceptions.append("정전기 장면에 흐르는 물의 큰 소리를 사용함")

    a_effect_ok = (
        contains_any(audio_effect, ["흐르지 않", "머물", "이동하지 않", "정지"])
        and contains_any(audio_effect, ["위험하지 않", "정전기", "특성", "전달", "강조"])
    )
    if a_effect_ok:
        score += 1; matched.append("청각 효과: 흐르지 않는 정전기 강조")
    else:
        missing.append("청각 효과에서 흐르지 않는 특성과의 연결")

    passed = score == 4 and not misconceptions
    return GradeResult(passed, score, 4, matched=matched, missing=missing, misconceptions=misconceptions)


# =========================================================
# 세트 3 채점
# =========================================================
def grade_s3_q1(a1: str, a2: str, a3: str) -> GradeResult:
    score = 0
    matched, missing, misconceptions = [], [], []

    ok1 = contains_any(a1, ["로봇"]) and contains_any(a1, ["피겨 스케이팅", "피겨스케이팅"]) and contains_any(a1, ["완벽", "실수 없이"])
    if ok1:
        score += 1; matched.append("㉠ 로봇의 완벽한 피겨 스케이팅")
    else:
        missing.append("㉠ 로봇이 실수 없이 완벽하게 하는 피겨 스케이팅")

    reason_ok = count_group_hits(a2, [["감정이 없", "감정을 느끼지 못"], ["철학이 없", "독자적인 철학이 없"], ["이야기가 없"]]) >= 1
    conclusion_ok = contains_any(a2, ["예술로 보기 어렵", "예술이라고 보기 어렵", "예술이 아니다"])
    if reason_ok and conclusion_ok:
        score += 1; matched.append("㉡ 근거+예술로 보기 어렵다는 결론")
    else:
        if not reason_ok:
            missing.append("㉡ 감정·철학·이야기 부재 근거")
        if not conclusion_ok:
            missing.append("㉡ 예술로 보기 어렵다는 결론")
    if contains_any(a2, ["감정이 있다", "철학이 있다", "삶의 경험이 담겨 있다", "예술이다"]):
        misconceptions.append("인공지능 그림에 인간 예술의 특성을 적용함")

    value_hits = count_group_hits(a3, [["미술계에 큰 변화", "기존 미술계 변화"], ["예술의 범주를 확장", "예술 범주 확장"], ["상징적 가치", "상징적인 가치"]])
    if value_hits >= 1:
        score += 1; matched.append("㉢ 미술계 변화·범주 확장·상징적 가치")
    else:
        missing.append("㉢ 기존 미술계 변화 또는 예술 범주 확장의 상징적 가치")
    if contains_any(a3, ["가치가 없다", "전혀 가치 없음", "감동을 준다"]):
        misconceptions.append("인공지능 그림의 가치에 대해 반대 방향으로 씀")

    passed = score == 3 and not misconceptions
    return GradeResult(passed, score, 3, matched=matched, missing=missing, misconceptions=misconceptions)


def grade_s3_q2(s1: str, s2: str) -> GradeResult:
    score = 0
    matched, missing, misconceptions, feedback = [], [], [], []
    combined = f"{s1} {s2}"

    human_ok = contains_any(combined, ["인간의 예술", "인간 작품", "작가의 작품"]) and count_group_hits(
        combined, [["경험"], ["관점"], ["환경"], ["감정"], ["철학"]]
    ) >= 1
    ai_limit_ok = contains_any(combined, ["인공 지능", "인공지능", "ai"]) and count_group_hits(
        combined, [["감정이 없", "감정을 느끼지 못"], ["철학이 없", "독자적인 철학이 없"], ["이야기가 없"]]
    ) >= 1 and contains_any(combined, ["예술로 보기 어렵", "예술이라고 보기 어렵"])

    ai_value_ok = contains_any(combined, ["미술계에 큰 변화", "예술의 범주를 확장", "예술 범주 확장", "상징적 가치", "상징적인 가치"])

    if human_ok and ai_limit_ok:
        score += 1; matched.append("인간 예술과 AI 그림의 차이")
    else:
        missing.append("인간 예술의 근거와 AI 그림의 한계 비교")

    if ai_value_ok:
        score += 1; matched.append("AI 그림의 상징적 가치")
    else:
        missing.append("미술계 변화 또는 예술 범주 확장 가치")

    if contains_any(combined, ["인공 지능은 감정이 있다", "인공지능은 감정이 있다", "ai는 감정이 있다", "삶의 경험이 담겨 있다"]):
        misconceptions.append("AI 그림에 인간 예술의 특성을 적용함")
    if contains_any(combined, ["가치가 전혀 없다", "아무 가치가 없다"]):
        misconceptions.append("AI 그림의 상징적 가치를 부정함")
    if contains_any(combined, ["인공 지능 그림은 예술이다", "인공지능 그림은 예술이다"]) and not contains_any(combined, ["보기 어렵", "그러나"]):
        misconceptions.append("제시문과 반대로 AI 그림을 곧바로 예술로 단정함")

    m1_label = extract_labeled_method(s1)
    m2_label = extract_labeled_method(s2)
    m1_meaning = detect_methods_by_meaning(s1)
    m2_meaning = detect_methods_by_meaning(s2)
    chosen1 = m1_label or (m1_meaning[0] if m1_meaning else None)
    chosen2 = m2_label or (m2_meaning[0] if m2_meaning else None)
    method1_ok = bool(chosen1) and method_features(s1, chosen1)[0]
    method2_ok = bool(chosen2) and method_features(s2, chosen2)[0]

    if method1_ok and method2_ok and chosen1 != chosen2:
        score += 1; matched.append(f"서로 다른 설명 방법({chosen1}, {chosen2})")
    else:
        missing.append("서로 다른 두 설명 방법의 구현")
        if m1_label and not method1_ok:
            misconceptions.append(f"(1)에 {m1_label}을 표기했으나 특성이 없음")
        if m2_label and not method2_ok:
            misconceptions.append(f"(2)에 {m2_label}을 표기했으나 특성이 없음")
        if chosen1 and chosen2 and chosen1 == chosen2:
            misconceptions.append("두 문장에 같은 설명 방법을 사용함")

    # 최종 관점: 예술로 보기 어렵지만 가치는 있음
    direction_ok = contains_any(combined, ["예술로 보기 어렵", "예술이라고 보기 어렵"]) and ai_value_ok
    if direction_ok:
        score += 1; matched.append("결론 방향: 예술성은 제한적이나 상징적 가치는 있음")
    else:
        missing.append("예술로 보기 어렵지만 상징적 가치는 있다는 균형적 결론")

    feedback.append("핵심 결론은 '예술로 보기는 어렵지만 가치가 전혀 없는 것은 아니다'라는 양면적 판단입니다.")
    passed = score == 4 and not misconceptions
    return GradeResult(passed, score, 4, feedback, matched, missing, misconceptions)


def grade_s3_q3(visual: str, visual_effect: str, audio: str, audio_effect: str) -> GradeResult:
    score = 0
    matched, missing, misconceptions = [], [], []

    visual_ok = contains_any(visual, ["작가", "화가", "예술가", "사람"]) and contains_any(
        visual, ["그림을 그리", "작품을 만들", "창작", "감상", "삶의 경험", "기억"]
    )
    if visual_ok:
        score += 1; matched.append("시각: 인간 작가의 창작·경험")
    else:
        missing.append("시각 요소의 인간 작가와 삶·감정이 담긴 창작")
    if contains_any(visual, ["로봇이 그림", "인공지능이 그림", "ai가 그림"]):
        misconceptions.append("인간 예술 장면에 AI·로봇 창작을 제시함")

    v_effect_ok = count_group_hits(
        visual_effect,
        [["경험"], ["관점"], ["환경"], ["감정"], ["철학"], ["감동", "울림"]],
    ) >= 2
    if v_effect_ok:
        score += 1; matched.append("시각 효과: 인간 예술의 내외부 요소")
    else:
        missing.append("시각 효과에서 경험·관점·환경·감정·철학 또는 감동 근거")

    audio_ok = contains_any(audio, ["따뜻", "잔잔", "감성", "서정", "사람의 숨소리", "붓 소리", "대화", "진심"])
    if audio_ok:
        score += 1; matched.append("청각: 인간적이고 따뜻한 분위기")
    else:
        missing.append("청각 요소의 인간적·정서적 분위기")
    if contains_any(audio, ["기계음", "메트로놈", "일정한 박자", "차갑고 정형화"]):
        misconceptions.append("인간 예술 장면에 장면 1의 기계적 소리를 반복함")

    a_effect_ok = contains_any(audio_effect, ["감동", "울림", "감정", "인간", "진정한 예술", "삶의 경험"])
    if a_effect_ok:
        score += 1; matched.append("청각 효과: 인간 예술의 감동 강조")
    else:
        missing.append("청각 효과에서 인간 예술의 감동·정서와 연결")

    passed = score == 4 and not misconceptions
    return GradeResult(passed, score, 4, matched=matched, missing=missing, misconceptions=misconceptions)


# =========================================================
# 모범 답안 자료
# =========================================================
MODEL_ANSWERS = {
    "1세트": {
        "문항 1": [
            "㉠ 비교적 쉬운 취미 생활이나 큰 노력을 들일 필요가 없는 과제",
            "㉡ 충분히 연습하며 익숙해질 때까지 차분하게 혼자 집중함",
            "㉢ 사회적 억제",
        ],
        "문항 2": {
            "예시 + 비교와 대조": [
                "(1) 비교적 쉬운 과제는 커피숍이나 도서관에서 하거나 다른 사람들과 함께 공부하는 것이 효율적이다. (예시)",
                "(2) 반대로 지나치게 어렵거나 도전이 필요한 과제는 혼자 집중하는 것이 좋다. (비교와 대조)",
            ],
            "분류와 구분 + 인과": [
                "(1) 과제는 비교적 쉬운 과제와 지나치게 어렵거나 도전이 필요한 과제로 나눌 수 있다. (분류와 구분)",
                "(2) 어려운 과제는 충분히 연습해 익숙해질 때까지 혼자 집중해야 하므로 차분한 개인 학습 환경이 효율적이다. (인과)",
            ],
        },
        "문항 3": [
            "시각 요소: 조용한 방에서 학생이 혼자 책상에 앉아 어려운 문제를 집중해 푸는 모습을 보여 준다.",
            "시각 효과: 어렵거나 도전이 필요한 과제는 혼자 집중하고 충분히 연습하는 환경이 효율적임을 전달한다.",
            "청각 요소: 주변 소음을 줄이고 잔잔하거나 거의 들리지 않는 배경음을 사용한다.",
            "청각 효과: 차분하게 혼자 집중해야 하는 학습 환경의 특성을 강조한다.",
        ],
    },
    "2세트": {
        "문항 1": [
            "㉠ 높은 곳에 고여 있는 물",
            "㉡ 전하가 이동하지 않고 머물러 있음",
            "㉢ 위험하지 않음",
        ],
        "문항 2": {
            "비교와 대조 + 인과": [
                "(1) 실생활 전기가 흐르는 물과 같다면, 정전기는 높은 곳에 고여 있는 물과 같다. (비교와 대조)",
                "(2) 정전기는 전하가 이동하지 않고 머물러 있으므로 전압은 매우 높아도 위험하지 않다. (인과)",
            ],
            "정의 + 비교와 대조": [
                "(1) 정전기란 전하가 이동하지 않고 머물러 있는 전기 현상을 말한다. (정의)",
                "(2) 실생활 전기가 흐르는 물과 같다면 정전기는 높은 곳에 고여 있는 물과 같아 위험하지 않다. (비교와 대조)",
            ],
        },
        "문항 3": [
            "시각 요소: 높은 곳에 많은 물이 고여 있으나 아래로 흐르지 않는 모습을 보여 준다.",
            "시각 효과: 정전기의 전하가 이동하지 않고 머물러 있는 특성을 시각적으로 나타낸다.",
            "청각 요소: 물 흐르는 소리 없이 고요하고 잔잔한 배경음을 사용한다.",
            "청각 효과: 정전기가 흐르지 않고 머물러 있어 위험하지 않다는 점을 강조한다.",
        ],
    },
    "3세트": {
        "문항 1": [
            "㉠ 로봇이 한 번의 실수 없이 완벽하게 피겨 스케이팅을 하는 경기",
            "㉡ 감정이나 독자적인 철학, 이야기가 없으므로 예술로 보기 어렵다.",
            "㉢ 기존 미술계에 큰 변화를 가져왔으며 예술의 범주를 확장할 수 있다는 점에서 상징적 가치가 있다.",
        ],
        "문항 2": {
            "비교와 대조 + 인과": [
                "(1) 인간의 예술에는 작가의 경험과 관점, 환경이 담겨 있지만 인공 지능의 그림에는 감정과 독자적인 철학이나 이야기가 없어 예술로 보기 어렵다. (비교와 대조)",
                "(2) 그러나 인공 지능 그림은 기존 미술계에 큰 변화를 가져왔고 예술의 범주를 확장할 수 있으므로 상징적 가치를 지닌다. (인과)",
            ],
            "분석 + 인과": [
                "(1) 인간의 작품에는 작가의 감정과 철학, 삶의 경험, 관점, 환경이 종합적으로 담겨 있다. (분석)",
                "(2) 인공 지능 그림은 이러한 요소가 없어 예술로 보기 어렵지만, 미술계에 변화를 주고 예술의 범주를 확장할 수 있으므로 상징적 가치는 있다. (인과)",
            ],
        },
        "문항 3": [
            "시각 요소: 작가가 자신의 경험과 감정을 떠올리며 작품을 만들고, 감상자가 작품 앞에서 깊은 울림을 느끼는 모습을 보여 준다.",
            "시각 효과: 인간의 예술에는 작가의 경험·관점·환경이 담겨 감상자에게 감동을 준다는 점을 전달한다.",
            "청각 요소: 따뜻하고 감정의 흐름이 느껴지는 잔잔한 배경음악을 사용한다.",
            "청각 효과: 인간 예술이 주는 정서와 마음의 울림을 강조한다.",
        ],
    },
}


# =========================================================
# 화면 구성
# =========================================================
with st.sidebar:
    st.header("채점 설정")
    set_name = st.selectbox("세트 선택", ["1세트", "2세트", "3세트"])
    question_name = st.selectbox("문항 선택", ["문항 1", "문항 2", "문항 3"])
    st.divider()
    st.markdown(
        """
        **판정 원칙**
        - 용어가 없어도 방법의 의미가 구현되면 인정
        - 방법을 직접 표기했다면 해당 특성이 실제 문장에 있어야 인정
        - 다른 개념의 특성을 섞으면 오개념 처리
        - 요구된 결론 방향이 분명해야 통과
        """
    )

tab_grade, tab_models, tab_logic = st.tabs(["자동 채점", "모범 답안", "채점 로직 설명"])

with tab_grade:
    st.subheader(f"{set_name} · {question_name}")

    if question_name == "문항 1":
        c1, c2, c3 = st.columns(3)
        with c1:
            a1 = st.text_area("㉠ 답안", height=120)
        with c2:
            a2 = st.text_area("㉡ 답안", height=120)
        with c3:
            a3 = st.text_area("㉢ 답안", height=120)

        if st.button("채점하기", type="primary"):
            if set_name == "1세트":
                result_to_markdown(grade_s1_q1(a1, a2, a3))
            elif set_name == "2세트":
                result_to_markdown(grade_s2_q1(a1, a2, a3))
            else:
                result_to_markdown(grade_s3_q1(a1, a2, a3))

    elif question_name == "문항 2":
        s1 = st.text_area("(1) 문장", height=150)
        s2 = st.text_area("(2) 문장", height=150)

        if st.button("채점하기", type="primary"):
            if set_name == "1세트":
                result_to_markdown(grade_s1_q2(s1, s2))
            elif set_name == "2세트":
                result_to_markdown(grade_s2_q2(s1, s2))
            else:
                result_to_markdown(grade_s3_q2(s1, s2))

    else:
        c1, c2 = st.columns(2)
        with c1:
            visual = st.text_area("시각 요소(Ⓐ)", height=130)
            visual_effect = st.text_area("시각 요소의 효과", height=130)
        with c2:
            audio = st.text_area("청각 요소(Ⓑ)", height=130)
            audio_effect = st.text_area("청각 요소의 효과", height=130)

        if st.button("채점하기", type="primary"):
            if set_name == "1세트":
                result_to_markdown(grade_s1_q3(visual, visual_effect, audio, audio_effect))
            elif set_name == "2세트":
                result_to_markdown(grade_s2_q3(visual, visual_effect, audio, audio_effect))
            else:
                result_to_markdown(grade_s3_q3(visual, visual_effect, audio, audio_effect))

with tab_models:
    st.subheader(f"{set_name} · {question_name} 모범 답안")
    models = MODEL_ANSWERS[set_name][question_name]
    if isinstance(models, dict):
        st.write("선택 가능한 설명 방법 조합별 모범 답안입니다.")
        for label, answers in models.items():
            with st.expander(label, expanded=True):
                for answer in answers:
                    st.markdown(f"- {answer}")
    else:
        for answer in models:
            st.markdown(f"- {answer}")

with tab_logic:
    st.subheader("채점 로직 핵심")
    st.markdown(
        """
        1. **의미 중심 통과**  
           정확한 용어가 없어도 핵심 의미를 나타내는 동의 표현이 있으면 인정합니다.

        2. **설명 방법 검증**  
           학생이 `(인과)`, `(비교와 대조)`처럼 방법을 직접 적었을 때는 단순 표기만으로 인정하지 않습니다.  
           - 인과: 원인과 결과가 모두 있어야 함  
           - 비교와 대조: 두 대상·상황과 차이 관계가 있어야 함  
           - 예시: 구체적 사례가 있어야 함  
           - 정의: 대상의 뜻이나 개념을 밝혀야 함  
           - 분석: 둘 이상의 요소나 부분으로 나누어 설명해야 함  
           - 분류와 구분: 일정한 기준으로 대상을 나누어야 함

        3. **오개념 교차 차단**  
           쉬운 과제에 혼자 집중을 연결하거나, 정전기에 흐르는 물을 연결하거나, AI 그림에 인간의 감정·삶의 경험을 부여하면 오답으로 처리합니다.

        4. **결론 방향 확인**  
           단순 키워드 나열이 아니라 문항이 요구한 결론이 분명해야 합니다.  
           - 1세트: 쉬운 과제는 함께, 어려운 과제는 혼자  
           - 2세트: 전하가 머물기 때문에 위험하지 않음  
           - 3세트: 예술로 보기는 어렵지만 상징적 가치는 있음
        """
    )
    st.warning(
        "이 앱은 규칙 기반 자동 채점기입니다. 표현이 매우 창의적이거나 중의적인 답안은 교사의 최종 확인이 필요합니다."
    )
