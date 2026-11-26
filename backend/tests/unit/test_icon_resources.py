import io
import zipfile
from pathlib import Path

import pytest
from fakes import fixture
from PIL import Image

from monkey_api.adapters.adb.aapt_resources import adaptive_layers, icon_path, resource_table
from monkey_api.adapters.adb.apk_icon import ApkIconRenderer
from monkey_api.adapters.adb.package_assets import apk_paths, installation_identity
from monkey_api.core.icon_errors import IconUnavailable


def test_captured_ixio_installation_and_icon_resources() -> None:
    paths = apk_paths(fixture("ixio_pm_path.txt"))
    assert len(paths) == 1 and paths[0].endswith("/base.apk")
    identity = installation_identity(fixture("ixio_version.txt"))
    assert "versionCode=13424" in identity and "lastUpdateTime=2026-11-19" in identity
    assert icon_path(fixture("ixio_badging.txt")) == "res/E4.xml"
    table = resource_table(fixture("ixio_icon_resources.txt"), Path("base.apk"))
    assert table["0x7f060075"][0].value == "#ffffffff"
    assert table["0x7f0f0001"][0].value == "res/as.png"
    assert adaptive_layers(fixture("ixio_icon_xml.txt")) == {
        "background": "@0x7f060075",
        "foreground": "@0x7f0f0001",
    }


def test_invalid_paths_and_missing_install_identity_are_not_cached() -> None:
    for output in ("", "package:../../bad.apk", "package:/data/app/file.txt"):
        with pytest.raises(IconUnavailable):
            apk_paths(output)
    with pytest.raises(IconUnavailable):
        installation_identity("versionCode=1")


def test_adaptive_composition_and_raster_output(tmp_path: Path, monkeypatch) -> None:
    # Pixel fixture is generated; aapt resource/XML fixtures come from the real installed APK.
    image = io.BytesIO()
    Image.new("RGBA", (432, 432), (128, 0, 255, 128)).save(image, format="PNG")
    apk = tmp_path / "base.apk"
    with zipfile.ZipFile(apk, "w") as archive:
        archive.writestr("res/as.png", image.getvalue())
    renderer = ApkIconRenderer("fake-aapt2")
    outputs = {"badging": "ixio_badging.txt", "resources": "ixio_icon_resources.txt", "xmltree": "ixio_icon_xml.txt"}
    monkeypatch.setattr(renderer, "dump", lambda kind, *_: fixture(outputs[kind]))
    with Image.open(io.BytesIO(renderer.render([apk]))) as icon:
        assert icon.size == (128, 128) and icon.format == "PNG"
        assert icon.getpixel((0, 0))[3] == 0
        assert icon.getpixel((64, 64)) == (191, 127, 255, 255)


def test_unsupported_vector_does_not_pick_an_unrelated_png(tmp_path: Path, monkeypatch) -> None:
    renderer = ApkIconRenderer("fake-aapt2")
    outputs = {"badging": fixture("ixio_badging.txt"), "resources": "", "xmltree": "E: vector (line=1)"}
    monkeypatch.setattr(renderer, "dump", lambda kind, *_: outputs[kind])
    with pytest.raises(IconUnavailable):
        renderer.render([tmp_path / "base.apk"])
