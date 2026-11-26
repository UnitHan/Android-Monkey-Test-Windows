import json

import pytest
from fakes import fixture

from monkey_api.adapters.adb.app_labels import parse_icon


def test_real_device_icon_checks_package_protocol_and_size():
    raw = fixture("youtube_icon.json")
    assert len(parse_icon(raw, "com.google.android.youtube")) == 3632
    with pytest.raises(ValueError):
        parse_icon(raw, "com.wrong.app")
    body = json.loads(raw)
    for png in ("broken", "x" * 350_001, "bm90IGEgcG5n"):
        body["png"] = png
        with pytest.raises(ValueError):
            parse_icon(json.dumps(body), body["package"])
