#!/usr/bin/env python3
"""Scaffold a newsletter issue page and register it in the archive index.

From a Markdown draft (recommended) -- metadata can live in front matter:

    python3 new_issue.py --from drafts/fodmaps.md

    ---
    title: What FODMAPs actually are
    tags: ibs-fodmaps, diet-elimination
    excerpt: A plain-language primer on the carbohydrates behind IBS symptoms.
    date: 2026-09-13
    ---

    Body starts here...

Anything omitted is inferred: title from the first `# Heading`, excerpt from
the first paragraph, date from today. Command-line flags override front matter.
Write `excerpt:` explicitly -- see the warning the script prints if you don't.

Or scaffold an empty page and paste the body in by hand:

    python3 new_issue.py --title "What FODMAPs actually are" --tags ibs-fodmaps

Tags must already exist in the `tags` list in issues.json -- that list is the
single source of truth shared with archive.html and index.html, so adding a new
topic means adding it there (and adding a tile to index.html) first.
"""

import argparse
import datetime as dt
import html as html_mod
import json
import re
import sys
import textwrap
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "issues.json"
TEMPLATE = ROOT / "issues" / "_template.html"
ISSUE_DIR = ROOT / "issues"
SITEMAP = ROOT / "sitemap.xml"
BASE_URL = "https://gutadvice.com"

PLACEHOLDER = "        <p>Replace this paragraph with the issue content.</p>"


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


def parse_front_matter(text: str):
    """Minimal `key: value` front matter. Avoids a PyYAML dependency -- every
    field we support is a plain scalar."""
    if not text.lstrip().startswith("---"):
        return {}, text
    text = text.lstrip()
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block, body = text[3:end], text[end + 4:]
    meta = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip().lower()] = value.strip().strip("'\"")
    return meta, body.lstrip("\n")


def md_to_html(md_text: str) -> str:
    try:
        import mistune
    except ImportError:
        print("error: converting Markdown needs mistune -- pip3 install mistune",
              file=sys.stderr)
        raise SystemExit(1)
    # escape=False so raw HTML in the draft passes through untouched.
    render = mistune.create_markdown(escape=False, plugins=["strikethrough", "table", "url"])
    html = render(md_text).strip()
    # The template already renders the title in <header>, so drop a leading H1.
    return re.sub(r"^\s*<h1[^>]*>.*?</h1>\s*", "", html, count=1, flags=re.S).strip()


def first_paragraph_text(rendered: str) -> str:
    m = re.search(r"<p>(.*?)</p>", rendered, re.S)
    if not m:
        return ""
    # Strip tags, then unescape: the excerpt is stored as plain text and gets
    # re-escaped by whoever renders it (the template, or archive.html).
    text = html_mod.unescape(re.sub(r"<[^>]+>", "", m.group(1)))
    text = " ".join(text.split())
    if len(text) <= 200:
        return text
    return text[:200].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


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
    ap.add_argument("--from", dest="source", metavar="FILE.md",
                    help="Markdown draft to convert into the issue body")
    ap.add_argument("--title", help="Issue headline (overrides front matter / first # heading)")
    ap.add_argument("--tags", help="Comma-separated tag slugs (overrides front matter)")
    ap.add_argument("--excerpt", help="One-sentence summary for the archive card and meta description")
    ap.add_argument("--date", help="Publish date, YYYY-MM-DD (default: today)")
    args = ap.parse_args()

    for path in (INDEX, TEMPLATE):
        if not path.exists():
            print(f"error: {path.relative_to(ROOT)} not found", file=sys.stderr)
            return 1

    meta, body_html = {}, None
    if args.source:
        src = Path(args.source)
        if not src.exists():
            print(f"error: {src} not found", file=sys.stderr)
            return 1
        meta, md_body = parse_front_matter(src.read_text())
        if not md_body.strip():
            print(f"error: {src} has no content below the front matter", file=sys.stderr)
            return 1
        md_title = re.search(r"^#\s+(.+)$", md_body, re.M)
        if md_title:
            meta.setdefault("title", md_title.group(1).strip())
        body_html = md_to_html(md_body)

    title = args.title or meta.get("title")
    raw_tags = args.tags or meta.get("tags")
    if not title:
        print("error: no title -- pass --title, or add one to the front matter "
              "or as a `# Heading`", file=sys.stderr)
        return 1
    if not raw_tags:
        print("error: no tags -- pass --tags, or add `tags:` to the front matter", file=sys.stderr)
        return 1

    try:
        date = dt.date.fromisoformat(args.date or meta.get("date") or
                                     dt.date.today().isoformat()).isoformat()
    except ValueError:
        print(f"error: date must be YYYY-MM-DD, got {args.date or meta.get('date')!r}",
              file=sys.stderr)
        return 1

    data = json.loads(INDEX.read_text())
    known = {t["slug"]: t["label"] for t in data["tags"]}

    tags = [t.strip() for t in raw_tags.replace(",", " ").split() if t.strip()]
    unknown = [t for t in tags if t not in known]
    if unknown:
        print(f"error: unknown tag(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"known tags: {', '.join(known)}", file=sys.stderr)
        return 1
    if not tags:
        print("error: at least one tag is required", file=sys.stderr)
        return 1

    slug = f"{date}-{slugify(title)}"
    out = ISSUE_DIR / f"{slug}.html"
    if out.exists():
        print(f"error: {out.relative_to(ROOT)} already exists", file=sys.stderr)
        return 1
    if any(i["slug"] == slug for i in data["issues"]):
        print(f"error: slug {slug!r} is already in issues.json", file=sys.stderr)
        return 1

    excerpt = (args.excerpt or meta.get("excerpt") or "").strip()
    derived_excerpt = False
    if not excerpt and body_html:
        excerpt = first_paragraph_text(body_html)
        derived_excerpt = bool(excerpt)
    if not excerpt:
        excerpt = f"An issue of the Sunday gut digest on {known[tags[0]].lower()}."

    tag_links = "".join(
        f'<a class="issue-tag" href="../archive.html?tag={t}">{esc(known[t])}</a>'
        for t in tags
    )

    html = TEMPLATE.read_text()
    for key, value in {
        "{{TITLE}}": esc(title),
        "{{EXCERPT}}": esc(excerpt),
        "{{SLUG}}": slug,
        "{{DATE}}": date,
        "{{DATE_LONG}}": long_date(date),
        "{{TAG_LINKS}}": tag_links,
    }.items():
        html = html.replace(key, value)

    if body_html:
        html = html.replace(PLACEHOLDER, textwrap.indent(body_html, "        "))

    out.write_text(html)

    data["issues"].append({
        "slug": slug, "title": title, "date": date,
        "tags": tags, "excerpt": excerpt,
    })
    data["issues"].sort(key=lambda i: (i["date"], i["slug"]), reverse=True)
    INDEX.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    n = write_sitemap(data)

    print(f"created  {out.relative_to(ROOT)}")
    print(f"title    {title}")
    print(f"tags     {', '.join(tags)}")
    print(f"excerpt  {excerpt}")
    print(f"indexed  {len(data['issues'])} issue(s) in issues.json")
    print(f"sitemap  {n} URLs")
    if derived_excerpt:
        print("\nwarning: no excerpt given, so it was taken from the first paragraph --"
              "\n         which means that text now appears twice on the page. Set"
              "\n         `excerpt:` in the front matter and re-run to avoid this.")
    if not body_html:
        print(f"\nNext: paste the issue body into the marked block in {out.relative_to(ROOT)}")
    else:
        print(f"\nBody converted from {args.source}. Preview it, then commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
