import pytest

from monkey_api.domain.app_search import match_rank


@pytest.mark.parametrize(
    ("name", "package", "query"),
    [
        ("blind", "com.teamblind.blind", "블"),
        ("blind", "com.teamblind.blind", "블라"),
        ("blind", "com.teamblind.blind", "블라인드"),
        ("YouTube", "com.google.android.youtube", "유튜브"),
        ("AlphaKey", "com.lguplus.alphakey", "아"),
        ("AlphaKey", "com.lguplus.alphakey", "알파"),
        ("Confluence", "com.atlassian.confluence", "컨"),
        ("Confluence", "com.atlassian.confluence", "컨플루언스"),
        ("OneDrive", "com.microsoft.skydrive", "원"),
        ("OneDrive", "com.microsoft.skydrive", "드라이브"),
        ("Google Cloud", "com.google.cloud", "클라우드"),
        ("Google Play 스토어", "com.android.vending", "플레이"),
        ("카카오톡", "com.kakao.talk", "ㅋㅋ"),
        ("배달의민족", "com.sampleapp", "ㅂㄷ"),
        ("카카오", "com.sample", "kakao"),
        ("Reqable", "com.reqable.android", "REQ"),
        ("갤럭시 웨어러블", "com.samsung.wear", "웨어"),
        ("익시오", "com.lguplus.aicallagent", "ㅇㅅㅇ"),
        ("U+tv모바일", "com.lguplus.remocon", "ㅁㅂㅇ"),
        ("카카오톡", "com.kakao.talk", "ㅋ ㅋ"),
        ("익시오", "com.lguplus.aicallagent", "ᄋᄉᄋ"),
        ("anything", "com.any", "   "),
        ("U+tv모바일", "com.lguplus.remocon", "remocon"),
    ],
)
def test_appkium_search_examples(name, package, query):
    assert match_rank(name, package, query) is not None


@pytest.mark.parametrize(
    ("name", "package", "query"),
    [
        ("U+ 원넘버", "com.lguplus.onenumber", "블"),
        ("U+tv모바일", "com.lguplus.remocon", "블"),
        ("blind", "com.teamblind.blind", "ㅁㅈ"),
        ("카카오톡", "com.kakao.talk", "날씨"),
    ],
)
def test_completed_syllables_do_not_match_unrelated_initials(name, package, query):
    assert match_rank(name, package, query) is None


def test_match_order_prefers_installed_name_then_package_then_initials():
    assert match_rank("모바일매니저", "com.x", "모") < match_rank("U+모바일매니저", "com.y", "모")
    assert match_rank("blind", "com.x", "blind") < match_rank("다른 앱", "com.blind", "blind")
    assert match_rank("카카오톡", "com.x", "ㅋㅋ") == 3
