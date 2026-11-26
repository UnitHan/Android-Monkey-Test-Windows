"""Write the OpenAPI contract to backend/openapi.json (and frontend type generation input)."""

import json
import tempfile
from pathlib import Path

from monkey_api.core.settings import Settings
from monkey_api.main import create_app

OUT = Path(__file__).resolve().parents[1] / "openapi.json"

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(Settings(data_dir=Path(tmp), adb_path="adb"))
        OUT.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
