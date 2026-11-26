import importlib.util
import json
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("release_builder", Path(__file__).parents[1] / "build_installer.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def test_release_version_uses_last_build_without_changing_development_version(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(builder, "DIST", tmp_path / "dist")
    (tmp_path / "frontend").mkdir()
    package = tmp_path / "frontend/package.json"
    package.write_text('{"version":"4.0.6"}')
    (tmp_path / "dist/installers/4.0.7").mkdir(parents=True)
    (tmp_path / "dist/release-work/4.0.8").mkdir(parents=True)
    assert builder.next_version() == ("4.0.8", "4.0.9")
    assert json.loads(package.read_text())["version"] == "4.0.6"


def test_snapshot_excludes_live_build_outputs_and_keeps_fonts_and_sources(tmp_path, monkeypatch):
    root = tmp_path / "source"
    monkeypatch.setattr(builder, "ROOT", root)
    paths = [*builder.VERSION_FILES, "scripts/release_worker.py", "backend/scripts/export_openapi.py",
             "frontend/public/fonts/font.otf", "frontend/src/App.tsx", "frontend/index.html",
             "frontend/tsconfig.json", "frontend/vite.config.ts", "frontend/src-tauri/src/lib.rs",
             "frontend/src-tauri/target/debug/app.dll", "frontend/src-tauri/runtime/deployment.vault.json", ".env"]
    for relative in paths:
        file = root / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('{"version":"4.0.6"}' if relative == "frontend/package.json" else "fixture")
    before = {p: (root / p).read_bytes() for p in paths}
    stage = tmp_path / "snapshot"
    builder.copy_source(stage, "4.0.9")
    assert all((root / p).read_bytes() == content for p, content in before.items())
    assert json.loads((stage / "frontend/package.json").read_text())["version"] == "4.0.9"
    assert (stage / "frontend/public/fonts/font.otf").is_file()
    assert (stage / "frontend/src-tauri/src/lib.rs").is_file()
    assert not (stage / "frontend/src-tauri/target").exists()
    assert not (stage / "frontend/src-tauri/runtime").exists()
    assert not (stage / ".env").exists()
