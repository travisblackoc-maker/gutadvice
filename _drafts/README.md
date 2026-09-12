# Drafts

Markdown sources for newsletter issues, before they are converted into pages.

The leading underscore matters: GitHub Pages runs Jekyll on this repo, and
Jekyll excludes underscore-prefixed paths from the published site. A plain
`drafts/` directory would be served publicly at gutadvice.com/drafts/.

Convert a draft into a published issue with:

    python3 new_issue.py --from _drafts/your-draft.md

That writes issues/<date>-<slug>.html, adds the entry to issues.json, and
regenerates sitemap.xml. Drafts stay here afterwards as the editable source.
