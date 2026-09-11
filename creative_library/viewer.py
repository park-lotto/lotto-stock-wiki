"""Build and open a self-contained local browser for the shared file catalog."""
import argparse
import base64
from io import BytesIO
import json
import logging
from pathlib import Path
import tempfile
import webbrowser

from .catalog import Catalog
from .schema import AccessContext, LibraryConfig

SAMPLE = "일상을 바꾸는 발견\n놀라운 생활 아이디어\n숏템메이커 0123456789 ABC!?"


def font_preview(path):
    try:
        from fontTools import subset
        from fontTools.ttLib import TTFont
        logging.getLogger("fontTools.subset").setLevel(logging.ERROR)
        with TTFont(path) as font:
            options = subset.Options()
            worker = subset.Subsetter(options=options)
            worker.populate(text=SAMPLE)
            worker.subset(font)
            font.flavor = None
            buffer = BytesIO()
            font.save(buffer)
        return "data:font/otf;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return None


def build_viewer(repo, destination=None):
    repo = Path(repo).resolve(strict=True)
    # File-based company catalog only. No implicit customer DB or admin context.
    catalog = Catalog.load(LibraryConfig(repo=repo), AccessContext())
    payload = catalog.to_dict()
    for item in payload["items"]:
        item["local_media"] = []
        for artifact in item["artifacts"]:
            uri = artifact["uri"]
            if not artifact["exists"] or not uri.startswith("repo:"):
                continue
            path = (repo / uri.removeprefix("repo:")).resolve()
            if not path.is_relative_to(repo) or not path.is_file():
                continue
            if item["domain"] == "font":
                item["font_preview"] = font_preview(path)
            else:
                item["local_media"].append({"url": path.as_uri(), "suffix": path.suffix.lower()})
    template = Path(__file__).with_name("viewer.html").read_text(encoding="utf-8")
    encoded = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    html = template.replace("/*CATALOG_DATA*/null", encoded)
    output = Path(destination) if destination else Path(tempfile.mkdtemp(prefix="creative-library-viewer-")) / "index.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(html)
    return output.resolve()


def main():
    parser = argparse.ArgumentParser(description="크리에이티브 라이브러리 화면 열기")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    output = build_viewer(args.repo, args.output)
    if not args.no_open:
        webbrowser.open(output.as_uri())
    print(json.dumps({"viewer": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
