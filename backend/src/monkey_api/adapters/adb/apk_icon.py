"""Render raster and raster-layer adaptive icons using SDK aapt2 and Pillow."""

import io
import subprocess
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, UnidentifiedImageError

from monkey_api.adapters.adb.aapt_resources import Resource, adaptive_layers, icon_path, resource_table
from monkey_api.core.icon_errors import IconToolUnavailable, IconUnavailable

SIZE = 128
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class ApkIconRenderer:
    def __init__(self, aapt2: str) -> None:
        self.aapt2 = aapt2

    def dump(self, kind: str, apk: Path, *args: str) -> str:
        try:
            result = subprocess.run(
                [self.aapt2, "dump", kind, *args, str(apk)],
                capture_output=True,
                timeout=30,
                creationflags=_NO_WINDOW,
                check=False,
            )
        except OSError:
            raise IconToolUnavailable("Android SDK Build Tools의 aapt2를 찾을 수 없습니다.") from None
        except subprocess.TimeoutExpired:
            raise IconUnavailable("앱 아이콘 분석 시간이 초과되었습니다.") from None
        if result.returncode:
            raise IconUnavailable("APK 아이콘 리소스를 읽지 못했습니다.")
        return result.stdout.decode("utf-8", errors="replace")

    def render(self, apks: list[Path]) -> bytes:
        try:
            path = icon_path(self.dump("badging", apks[0]))
            if not path:
                raise IconUnavailable("앱 아이콘 리소스가 없습니다.")
            table: dict[str, list[Resource]] = {}
            for apk in apks:
                for key, values in resource_table(self.dump("resources", apk), apk).items():
                    table.setdefault(key, []).extend(values)
            candidates = [r for values in table.values() for r in values if r.value == path]
            root = max(candidates, key=lambda r: r.density) if candidates else Resource(apks[0], path)
            icon = self._image(root, table, set())
            output = io.BytesIO()
            icon.resize((SIZE, SIZE), Image.Resampling.LANCZOS).save(output, format="PNG")
            return output.getvalue()
        except (
            OSError,
            ValueError,
            KeyError,
            zipfile.BadZipFile,
            UnidentifiedImageError,
            Image.DecompressionBombError,
        ):
            raise IconUnavailable("이 앱의 아이콘 형식을 처리하지 못했습니다.") from None

    def _image(self, resource: Resource, table: dict[str, list[Resource]], visited: set[str]) -> Image.Image:
        value = resource.value
        if len(visited) > 12 or value in visited:
            raise IconUnavailable("순환 아이콘 리소스를 처리할 수 없습니다.")
        visited = visited | {value}
        if value.startswith("@"):
            candidates = table.get(value[1:], [])
            if not candidates:
                raise IconUnavailable("아이콘의 분할 APK 리소스가 없습니다.")
            return self._image(max(candidates, key=lambda r: r.density), table, visited)
        if value.startswith("#"):
            color = value[1:]
            rgba = color[2:] + color[:2] if len(color) == 8 else color + "ff"
            return Image.new("RGBA", (192, 192), tuple(bytes.fromhex(rgba)))
        if value.endswith(".xml"):
            return self._adaptive(resource, table, visited)
        with zipfile.ZipFile(resource.apk) as archive:
            if archive.getinfo(value).file_size > 4 * 1024 * 1024:
                raise IconUnavailable("아이콘 리소스가 너무 큽니다.")
            with Image.open(io.BytesIO(archive.read(value))) as image:
                if image.width * image.height > 4_000_000:
                    raise IconUnavailable("아이콘 해상도가 너무 큽니다.")
                return image.convert("RGBA")

    def _adaptive(self, resource: Resource, table: dict[str, list[Resource]], visited: set[str]) -> Image.Image:
        layers = adaptive_layers(self.dump("xmltree", resource.apk, "--file", resource.value))
        if set(layers) != {"background", "foreground"}:
            raise IconUnavailable("지원되지 않는 XML/벡터 아이콘입니다.")
        images = [self._image(Resource(resource.apk, layers[k]), table, visited) for k in ("background", "foreground")]
        background, foreground = [im.resize((192, 192), Image.Resampling.LANCZOS) for im in images]
        icon = Image.alpha_composite(background, foreground).crop((32, 32, 160, 160))
        mask = Image.new("L", (SIZE, SIZE))
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=28, fill=255)
        result = Image.new("RGBA", (SIZE, SIZE))
        result.paste(icon, (0, 0), mask)
        return result
