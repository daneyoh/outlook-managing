"""
통합 스모크 — build_data() 와 Api.get_view() 가 예외 없이 dict 를 반환하는지 확인.

왜 필요한가 (회귀 방지):
Phase 2.2 에서 build_dashboard.build_data() 안의 지역변수 `rules`(프로젝트 규칙 dict)가
모듈 `import rules`(분류 규칙 단일 소스)를 섀도잉해, `rules.replied_thread_keys(...)` 가
'dict' object has no attribute ... 로 크래시했다. 순수함수 characterization 테스트는
`rules.*` 를 모듈 스코프에서 직접 호출하므로 이 섀도잉을 통과시켜 버렸다 — build_data 전체
경로를 한 번도 실행하지 않았기 때문이다. 이 테스트가 그 통합 경로를 얇게 실행해 같은 종류의
결함(섀도잉/이름해석 오류)을 잡는다.

build_data / get_view 는 데이터 파일이 없어도 try/except 로 빈 목록을 반환하므로,
픽스처 없이 레포의 실제 02. DB 상태에 대해 그대로 호출해도 안전하다.
"""
import build_dashboard as bd


def test_build_data_returns_dict_without_raising():
    d = bd.build_data()
    assert isinstance(d, dict)
    # build_data 가 내보내는 핵심 리스트 키 (get_view 가 여기에 replies/counts 등을 더한다).
    for key in ("todos", "threads"):
        assert key in d, f"build_data() 결과에 '{key}' 누락"
        assert isinstance(d[key], list)


def test_get_view_returns_counts_without_raising():
    import app
    view = app.Api().get_view()
    assert isinstance(view, dict)
    assert isinstance(view.get("counts"), dict), "get_view()['counts'] 가 dict 여야 함"
    # 홈 화면 카운트 키가 채워지는지 (분류 파이프가 끝까지 도는지) 확인.
    assert "미회신" in view["counts"]
