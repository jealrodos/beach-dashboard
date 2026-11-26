# Atria interface identity

BeachWatch uses a Solarized dark interface. Its product wordmark reads
**beachwatch**, with heavier “beach” and lighter “watch”, in warm cream
`#eee8d5`. The right header signature combines the quiet “part of” label, bold
Othala rune and spaced lowercase Atria wordmark. `HOME_URL` configures its link.

The rune uses SVG viewBox `0 0 32 44`, a 3.2-unit teal stroke, round caps and
joins. Its header box is 20 × 24px, retaining intrinsic proportions. The Atria
wordmark is self-hosted Josefin Sans Regular 400: 18px desktop, 16px at ≤600px,
with `.3em` tracking. The label is 9px, weight 500, with `.12em` tracking
(`.08em` on mobile). Signature gaps are 7px desktop and 5px mobile.

Product names use Segoe UI / Inter / system-ui, weights 650 and 350, line-height
1.2 and tracking `-.04em`. Sizes are 24px desktop, 20px at ≤600px and 18px at
≤380px. Headers align the product left and signature right; card radius is 12px.
The Updated timestamp sits below the table at the bottom right in normal flow.

| Role | Hex |
| --- | --- |
| Canvas / card / inset | `#00242d` / `#052d37` / `#0a3640` |
| Resource / hover | `#08313b` / `#0b3943` |
| Text / muted / names and emphasis | `#93a1a1` / `#839496` / `#eee8d5` |
| Border / soft border | `#486b72` / `#244751` |
| Rune and interaction accent | `#2aa198` |
| Blue / green / ochre | `#268bd2` / `#859900` / `#b58900` |
| Orange / red / magenta / violet | `#cb4b16` / `#dc322f` / `#d33682` / `#6c71c4` |
| Success background / text | `#1a3024` / `#b5bd68` |
| Warning background / text | `#352f1c` / `#dec477` |
| Danger background / text | `#351b23` / `#f09b90` |
| Information background / text | `#123747` / `#9bc6db` |
| Violet background / text | `#292c42` / `#bdbee7` |
| Magenta background / text | `#382638` / `#e0a8c9` |

Shared files are in [`static/atria`](../static/atria): the CSS tokens, rune SVG,
Josefin Sans WOFF2 and its SIL Open Font License. Keep the license with the font.
The application serves its own assets and does not depend on another app's
availability. Runtime location choices and home URLs remain deployment settings.
