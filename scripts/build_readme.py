#!/usr/bin/env python3
"""Generate README.md and assets/social-preview.png from data/entries.yml."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_entries import CATEGORIES, load_entries, validate

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
PNG = ROOT / "assets" / "social-preview.png"
ANNOUNCEMENT = (
    "https://blog.google/innovation-and-ai/models-and-research/"
    "gemini-models/introducing-gemini-4-carbon/"
)

CATEGORY_COPY = {
    "3d-threejs": (
        "3D & Three.js",
        "Scenes the author describes as 3D or Three.js.",
    ),
    "games": (
        "Games",
        "Playable games. A single animated character stays in 3D or UI/SVG.",
    ),
    "simulations": (
        "Simulations & physics",
        "A running physical system, with the prompt that produced it.",
    ),
    "ui-svg": (
        "UI/SVG",
        "Interfaces, SVG, pixel art, and other 2D or motion-graphics posts.",
    ),
    "agents": (
        "Agents & long code",
        "Long agent runs and multi-step coding, with the prompt the author published.",
    ),
    "failures": (
        "Failures",
        "The published result misses, in the author's words or in the frame they posted. The prompt is still required.",
    ),
}

EMPTY = (
    "Nothing verified for this category yet. A post qualifies when it is public, "
    "the author published the prompt, and the result is on the post. "
    "[Add one](CONTRIBUTING.md)."
)

FONTS = (
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)


def _font(bold: bool, size: int):
    from PIL import ImageFont

    preferred = [path for path in FONTS if ("Bold" in path) == bold]
    for path in preferred + list(FONTS):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    raise SystemExit("No sans font found. Install fonts-noto-core or fonts-dejavu-core.")


def proof_line(entries: list[dict]) -> str:
    authors = {entry["author"]["handle"].lower() for entry in entries}
    for entry in entries:
        for credit in entry.get("credits") or []:
            authors.add(credit["handle"].lower())
    checked = max(entry["verified_on"] for entry in entries)
    return (
        f"{len(entries)} creations · {len(authors)} authors credited · "
        f"every link checked {checked}"
    )


def _people(entries: list[dict]) -> str:
    return proof_line(entries)


def render_card(entries: list[dict]):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1280, 640), "#12151c")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 14, 640), fill="#f0b429")
    draw.text((72, 78), "CURATED PROMPTS", font=_font(True, 22), fill="#f0b429")
    draw.text((72, 124), "Gemini 4 Carbon", font=_font(True, 84), fill="#f7f4ee")
    hook = "Every creation worth seeing, with its exact prompt\nand the original post."
    draw.multiline_text((72, 240), hook, font=_font(False, 32), fill="#d9d3c7", spacing=8)
    draw.text((72, 390), _people(entries), font=_font(True, 28), fill="#f7f4ee")
    draw.text(
        (72, 520),
        "Prompts stay with their authors  ·  CC BY 4.0  ·  Original card, no third-party media",
        font=_font(False, 22),
        fill="#9a9386",
    )
    return image


def _entry_md(entry: dict) -> str:
    author = entry["author"]
    lines = [
        f"<a id=\"{entry['id']}\"></a>",
        f"### {entry['title']}",
        "",
        f"**Author:** [{author['name']}]({author['url']}) (@{author['handle']})",
        f"**Post:** {entry['post']}",
        f"**Date:** {entry['date']}",
        "**Prompt:**",
        "",
        "```text",
        entry["prompt"],
        "```",
        "",
        entry["note"],
        "",
    ]
    if entry.get("arena_label"):
        lines.append(
            f"**Arena label:** the author says this checkpoint was displayed as {entry['arena_label']}."
        )
        lines.append("")
    comparison = entry.get("comparison")
    if comparison:
        same = comparison["url"] == entry["post"]
        if same:
            lines.append(f"**Comparison:** [Opus 5.5 is in this post]({comparison['url']}), with the same prompt.")
        else:
            lines.append(f"**Comparison:** [Opus 5.5, same prompt]({comparison['url']})")
    else:
        lines.append("**Comparison:** No Opus 5.5 output with this prompt is on the post.")
    lines.append("")
    for credit in entry.get("credits") or []:
        lines.append(
            f"**Also credited:** [{credit['name']}]({credit['url']}) (@{credit['handle']}), named by the poster."
        )
        lines.append("")
    for related in entry.get("related") or []:
        lines.append(f"**Also:** [{related['label']}]({related['url']})")
        lines.append("")
    lines.append(f"**Verified:** {entry['verified_on']}")
    lines.append("")
    return "\n".join(lines)


def render_readme(entries: list[dict]) -> str:
    featured = sorted((e for e in entries if e["featured"]), key=lambda e: e["featured"])
    by_cat: dict[str, list[dict]] = {key: [] for key in CATEGORIES}
    for entry in entries:
        by_cat[entry["category"]].append(entry)

    index = "\n".join(
        f"- [{CATEGORY_COPY[key][0]}](#{key}) ({len(by_cat[key])})" for key in CATEGORIES
    )
    rows = [
        "| Creation | Author | Prompt as published | Post |",
        "| --- | --- | --- | --- |",
    ]
    for entry in featured:
        author = entry["author"]
        prompt = entry["prompt"].replace("|", "\\|")
        rows.append(
            f"| [{entry['title']}](#{entry['id']}) | "
            f"[@{author['handle']}]({author['url']}) | `{prompt}` | [post]({entry['post']}) |"
        )
    sections = []
    for key in CATEGORIES:
        title, blurb = CATEGORY_COPY[key]
        body = "\n".join(_entry_md(entry) for entry in by_cat[key]) or EMPTY + "\n"
        sections.append(f"<a id=\"{key}\"></a>\n## {title}\n\n{blurb}\n\n{body}")

    flower = "https://x.com/thtbee_/status/2112935205703147750"
    mario = "https://x.com/LuminaBench/status/2112848294581813473"
    proof = _people(entries)
    return f"""<!-- Generated by scripts/build_readme.py from data/entries.yml. Do not edit by hand. -->

# Awesome Gemini 4 Carbon

Gemini 4 Carbon creations worth seeing, each with its exact prompt and the original post, plus an Opus 5.5 side-by-side where the author posted one.

![Gemini 4 Carbon curated prompt card: {proof}](assets/social-preview.png)

**{proof}**

That line is generated from [`data/entries.yml`](data/entries.yml): one row per creation, counting the poster and anyone the poster names.

Public creations whose authors attribute them to Gemini 4 Carbon. Each row quotes the prompt only as that author published it, names them, and links the original post. Where someone published an Opus 5.5 output from that same prompt, the row links it.

Google announced Carbon on 2026-10-28 and limited the first rollout to cyber defenders ([Introducing Gemini 4 Carbon]({ANNOUNCEMENT})). Several posts here are from Arena tests before that post. When the author says the checkpoint was still labeled Gemini 4 Argon, the entry says so. A display name is the author's report, not an independent check of the backend.

The text of this list is [CC BY 4.0](LICENSE). Prompts and creations stay with their authors.

## Start here

{chr(10).join(rows)}

## Contents

{index}
- [How to add one](#how-to-add-one)
- [How this list was made](#how-this-list-was-made)
- [License](#license)

{chr(10).join(sections)}
## How to add one

1. Add one public creation to [`data/entries.yml`](data/entries.yml): the author's post, the prompt as they published it, their name, and the date.
2. Run `python3 scripts/build_readme.py` and include the regenerated README and card.
3. Open a pull request. The checks confirm the post, the date, and that the prompt is on the post.

Rules, the entry format, and what to leave out: [CONTRIBUTING.md](CONTRIBUTING.md).

## How this list was made

This list was assembled by an AI agent and is human-curated via pull requests. For this first version, the agent checked each public post — author, date, and the prompt text on the post — on 2026-10-29. A person reviews what lands through a PR.

Posts that show a result and never print the prompt are not listed. [@thtbee_](https://x.com/thtbee_)'s [mechanical flower]({flower}) describes a Three.js scene and says the bee was not in the prompt, but does not quote the prompt. [@LuminaBench](https://x.com/LuminaBench)'s [Super Mario post]({mario}) refers to "the Super Mario prompt" and does not quote it. Descriptions such as "I asked it to build…" were not copied in as if they were the prompt. No prompt in this file was written by the list.

X pages often block anonymous clients. Lychee skips those URLs. [`scripts/check_x_posts.py`](scripts/check_x_posts.py) reads each status from a public post API and checks the handle, the UTC date, and the prompt text. The exception list is in [`.lycheeignore`](.lycheeignore).

## License

The wording of this list is licensed under [CC BY 4.0](LICENSE). Prompts, videos, and code belong to the people who made them. Link them. Do not re-upload their media. This list is not affiliated with Google.
"""


def write_outputs(entries: list[dict]) -> None:
    PNG.parent.mkdir(parents=True, exist_ok=True)
    README.write_text(render_readme(entries), encoding="utf-8")
    render_card(entries).save(PNG, "PNG")


def main() -> None:
    entries = load_entries()
    validate(entries)
    check = "--check" in sys.argv
    if check:
        expected_readme = render_readme(entries)
        actual_readme = README.read_text(encoding="utf-8") if README.exists() else ""
        if actual_readme != expected_readme:
            raise SystemExit("README.md is out of date. Run python3 scripts/build_readme.py")
        if not PNG.is_file():
            raise SystemExit("assets/social-preview.png is missing. Run python3 scripts/build_readme.py")
        print("ok README.md")
        return
    write_outputs(entries)
    print(f"wrote {README.relative_to(ROOT)} and {PNG.relative_to(ROOT)}")
    print(_people(entries))


if __name__ == "__main__":
    main()
