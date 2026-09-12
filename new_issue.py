#!/usr/bin/env python3
"""Scaffold a newsletter issue page and register it in the archive index.

    python3 new_issue.py --title "What FODMAPs actually are" \
                         --tags ibs-fodmaps,diet-elimination \
                         --excerpt "A short primer on the carbohydrates behind IBS symptoms."

Creates issues/<date>-<slug>.html from issues/_template.html, adds the entry to
issues.json (newest first), and regenerates sitemap.xml. Then paste the issue
body into the marked block in the new file.

Tags must already exist in the `tags` list in issues.json -- that list is the
single source of truth shared with archive.html and index.html, so adding a new
topic means adding it there (and adding a tile to index.html) first.
"""

import argparse
import datetime as dt
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "issues.json"
TEMPLATE = ROOT / "issues" / "_template.html"
ISSUE_DIR = ROOT / "issues"
SITEMAP = ROOT / "sitemap.xml"
BASE_URL = "https://gutadvice.com"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def long_date(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def write_sitemap(data: dict) -> int:
    """Static issue pages are the SEO surface; archive.html is JS-rendered, so
    the sitemap is what guarantees every issue is discoverable."""
    urls = [f"{BASE_URL}/", f"{BASE_URL}/archive.html"]
    urls += [f"{BASE_URL}/issues/{i['slug']}.html" for i in data["issues"]]
    body = "\n".join(f"  <url><loc>{esc(u)}</loc></url>" for u in urls)
    SITEMAP.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n"
    )
    return len(urls)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--title", required=True, help="Issue headline")
    ap.add_argument("--tags", required=True,
                    help="Comma-separated tag slugs (must exist in issues.json)")
    ap.add_argument("--excerpt", default="",
                    help="One-sentence summary for the archive card and meta description")
    ap.add_argument("--date", default=dt.date.today().isoformat(),
                    help="Publish date, YYYY-MM-DD (default: today)")
    args = ap.parse_args()

    for path in (INDEX, TEMPLATE):
        if not path.exists():
            print(f"error: {path.relative_to(ROOT)} not found", file=sys.stderr)
            return 1

    try:
        date = dt.date.fromisoformat(args.date).isoformat()
    except ValueError:
        print(f"error: --date must be YYYY-MM-DD, got {args.date!r}", file=sys.stderr)
        return 1

    data = json.loads(INDEX.read_text())
    known = {t["slug"]: t["label"] for t in data["tags"]}

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    unknown = [t for t in tags if t not in known]
    if unknown:
        print(f"error: unknown tag(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"known tags: {', '.join(known)}", file=sys.stderr)
        return 1
    if not tags:
        print("error: at least one tag is required", file=sys.stderr)
        return 1

    slug = f"{date}-{slugify(args.title)}"
    out = ISSUE_DIR / f"{slug}.html"
    if out.exists():
        print(f"error: {out.relative_to(ROOT)} already exists", file=sys.stderr)
        return 1
    if any(i["slug"] == slug for i in data["issues"]):
        print(f"error: slug {slug!r} is already in issues.json", file=sys.stderr)
        return 1

    excerpt = args.excerpt.strip() or f"An issue of the Sunday gut digest on {known[tags[0]].lower()}."
    tag_links = "".join(
        f'<a class="issue-tag" href="../archive.html?tag={t}">{esc(known[t])}</a>'
        for t in tags
    )

    html = TEMPLATE.read_text()
    for key, value in {
        "{{TITLE}}": esc(args.title),
        "{{EXCERPT}}": esc(excerpt),
        "{{SLUG}}": slug,
        "{{DATE}}": date,
        "{{DATE_LONG}}": long_date(date),
        "{{TAG_LINKS}}": tag_links,
    }.items():
        html = html.replace(key, value)
    out.write_text(html)

    data["issues"].append({
        "slug": slug, "title": args.title, "date": date,
        "tags": tags, "excerpt": excerpt,
    })
    data["issues"].sort(key=lambda i: (i["date"], i["slug"]), reverse=True)
    INDEX.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    n = write_sitemap(data)

    print(f"created  {out.relative_to(ROOT)}")
    print(f"indexed  {len(data['issues'])} issue(s) in issues.json")
    print(f"sitemap  {n} URLs")
    print(f"\nNext: paste the issue body into the marked block in {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
