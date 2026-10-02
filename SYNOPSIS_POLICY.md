# Synopsis requirements

User-approved project requirement: when a comic has no usable official or other sourced synopsis, generate a short, spoiler-free teaser from verified content in that exact issue or edition.

## Source order

1. Preserve a usable existing synopsis.
2. Prefer an issue-specific publisher synopsis, then a reliable catalog or other issue-specific source. Check that it describes the correct edition. Review sourced text for spoilers too.
3. User correction: research the story on the internet (publisher, databases, wikis, Reddit and other sources). Do not infer or reconstruct a story from archive pages. A local model may use cover/credits text for identification and queries, and rewrite internet evidence into a teaser.
4. If evidence is insufficient, leave the synopsis blank and queue it for review. Do not fabricate a premise.

## Style

- English; normally one paragraph of about 60–100 words, shorter when the available premise is simple.
- Match the user's Chaotica example: introduce the protagonist, setting, motivation, opening problem, and stakes; leave the resolution open.
- Use information established in the opening setup. Reading later pages may help verify facts, but does not make later events safe to disclose.
- Do not disclose twists, hidden identities, betrayals, surprise appearances, deaths, victories, defeats, solutions, endings, or cliffhanger revelations.
- Avoid naming a later destination, encounter, or mission unless it is clearly established in the opening setup or promotional premise.
- Do not tease a spoiler indirectly with phrases such as 'but their trusted ally has a secret'.
- No invented events, unsupported character motivations, review scores, praise, or claims about quality.
- Do not expand a short blurb by adding speculative plot details.

## Recording and review

- Store the teaser in ComicInfo.xml's Summary field.
- Record internet source URLs, exact supporting quotations, model and generation date in provenance. Never claim an editorial synopsis is official publisher text.
- Keep the distinction between sourced and generated descriptions in provenance; do not present generated text as a publisher blurb.
- Check the draft against the opening premise and perform a separate spoiler review before accepting it.
- Preserve an existing nonempty synopsis by default; changing it requires a deliberate reviewed update.
- Apply the same rule when rescanning newly added comics. Record unresolved cases instead of forcing a summary.

This is the agreed requirement for the future automatic enrichment worker. The present pilot uses assistant research and reading; it does not yet run an unattended synopsis generator.
