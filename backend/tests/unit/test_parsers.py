from fakes import fixture

from monkey_api.adapters.adb import parsers


def test_parse_devices_states_connection_and_model() -> None:
    devices = parsers.parse_devices(fixture("devices_l.txt"))
    by_serial = {d.serial: d for d in devices}
    assert set(by_serial) == {"R3CN30ABCDE", "192.168.0.23:5555", "emulator-5554", "ZY22XYZ"}
    assert by_serial["R3CN30ABCDE"].model == "SM G991N"
    assert by_serial["R3CN30ABCDE"].connection == "usb"
    assert by_serial["192.168.0.23:5555"].connection == "wifi"
    assert by_serial["emulator-5554"].state == "offline"
    assert by_serial["ZY22XYZ"].state == "unauthorized"


def test_parse_packages_sorted_unique_valid_only() -> None:
    out = "package:com.b.app\npackage:com.a.app\npackage:com.a.app\npackage:not valid\ngarbage\n"
    assert parsers.parse_packages(out) == ["com.a.app", "com.b.app"]


def test_meminfo_modern_total_pss() -> None:
    assert parsers.parse_meminfo_total_pss_mb(fixture("meminfo_android14.txt")) == 180.0


def test_meminfo_legacy_table_total() -> None:
    assert parsers.parse_meminfo_total_pss_mb(fixture("meminfo_legacy.txt")) == 50.0


def test_meminfo_no_process() -> None:
    assert parsers.parse_meminfo_total_pss_mb("No process found for: com.example.app") is None


def test_ps_pid_matches_main_process_not_service() -> None:
    assert parsers.parse_ps_pid(fixture("ps.txt"), "com.example.app") == 11509
    assert parsers.parse_ps_pid(fixture("ps.txt"), "com.missing") is None


def test_pidof() -> None:
    assert parsers.parse_pidof("11509 11600\n") == 11509
    assert parsers.parse_pidof("") is None


def test_top_cpu_uses_header_column() -> None:
    assert parsers.parse_top_cpu(fixture("top.txt"), 11509) == 25.0
    assert parsers.parse_top_cpu(fixture("top.txt"), 1) is None


def test_top_cpu_plain_header() -> None:
    out = "  PID USER PR NI VIRT RES SHR S %CPU %MEM TIME+ ARGS\n 99 u0 10 -10 1G 1M 1M S 7.5 1.0 0:01 x\n"
    assert parsers.parse_top_cpu(out, 99) == 7.5


def test_package_version() -> None:
    assert parsers.parse_package_version(fixture("dumpsys_package.txt")) == ("4.2.1", "4021")
    assert parsers.parse_package_version("Unable to find package: x") == (None, None)


def test_foreground_package() -> None:
    assert parsers.parse_foreground_package(fixture("activity_activities.txt")) == "com.example.app"
    assert parsers.parse_foreground_package("nothing here") is None


def test_setting_flag() -> None:
    assert parsers.parse_setting_flag("1\n") is True
    assert parsers.parse_setting_flag("0") is False
    assert parsers.parse_setting_flag("null") is None
