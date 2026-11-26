from fakes import fixture

from monkey_api.domain.logcat_analyzer import LogcatAnalyzer
from monkey_api.domain.monkey_output import MonkeyOutputTracker

PKG = "com.example.app"


def analyze(text: str, package: str = PKG):
    analyzer = LogcatAnalyzer(package)
    found = []
    for line in text.splitlines():
        found += analyzer.feed(line)
    return found + analyzer.flush()


def test_java_crash_detected_even_without_package_on_fatal_line() -> None:
    issues = analyze(fixture("logcat_crash.txt"))
    assert [i.kind for i in issues] == ["crash"]  # other app's crash ignored
    crash = issues[0]
    assert "NullPointerException" in crash.summary
    assert any("MainActivity.kt:42" in line for line in crash.lines)
    assert not any("WifiService" in line for line in crash.lines)  # interleaved line not in block


def test_anr_detected_for_package() -> None:
    issues = analyze(fixture("logcat_anr.txt"))
    assert len(issues) == 1 and issues[0].kind == "anr"
    assert issues[0].summary.startswith("ANR in com.example.app")
    assert any("Input dispatching timed out" in line for line in issues[0].lines)


def test_anr_for_other_package_ignored() -> None:
    assert analyze(fixture("logcat_anr.txt"), package="com.other") == []


def test_native_crash_detected_via_tombstone() -> None:
    issues = analyze(fixture("logcat_native.txt"))
    assert [i.kind for i in issues] == ["native_crash"]
    assert issues[0].summary.startswith("signal 11")


def test_short_block_flushed_at_end_of_run() -> None:
    text = "\n".join(fixture("logcat_crash.txt").splitlines()[:4])  # block cut mid-way
    assert [i.kind for i in analyze(text)] == ["crash"]


def test_monkey_tracker_counts_events_and_completion() -> None:
    tracker = MonkeyOutputTracker()
    for line in fixture("monkey_output.txt").splitlines():
        tracker.feed(line)
    assert tracker.events_sent == 300
    assert tracker.injected == 300
    assert tracker.finished and not tracker.aborted
    assert tracker.reported_crashes == 1


def test_monkey_tracker_aborted() -> None:
    tracker = MonkeyOutputTracker()
    tracker.feed("    // Sending event #100")
    tracker.feed("** Monkey aborted due to error.")
    assert tracker.aborted and tracker.events_sent == 100
