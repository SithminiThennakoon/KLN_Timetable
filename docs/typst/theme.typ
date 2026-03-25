#set page(
  paper: "a4",
  margin: (x: 1.7cm, y: 1.7cm),
  numbering: "1",
  number-align: center + bottom,
)

#set text(
  font: ("Libertinus Serif", "Georgia"),
  size: 10.5pt,
  lang: "en",
)

#set heading(numbering: "1.1")
#set par(justify: true, leading: 0.72em)

#show heading.where(level: 1): it => block(
  above: 1.2em,
  below: 0.65em,
  text(18pt, weight: "bold", fill: rgb("#132238"))[#{it.body}],
)

#show heading.where(level: 2): it => block(
  above: 1em,
  below: 0.5em,
  text(13.5pt, weight: "bold", fill: rgb("#1c3554"))[#{it.body}],
)

#show heading.where(level: 3): it => block(
  above: 0.8em,
  below: 0.35em,
  text(11.5pt, weight: "semibold", fill: rgb("#27496b"))[#{it.body}],
)

#let brand = "Lecture and Practical Timetable Generator"
#let group-id = "PM03"

#let cover(title, subtitle, audience, version: "March 2026") = [
  #align(center)[
    #v(2.4cm)
    #text(24pt, weight: "bold", fill: rgb("#0f172a"))[#brand]
    #v(0.45cm)
    #text(17pt, weight: "semibold", fill: rgb("#1d4ed8"))[#title]
    #v(0.35cm)
    #text(11pt, fill: rgb("#475569"))[#subtitle]
    #v(0.85cm)
    #box(
      inset: 12pt,
      radius: 10pt,
      fill: rgb("#eef4ff"),
      stroke: rgb("#bfd2ff"),
    )[
      *Group:* #group-id \
      *Audience:* #audience \
      *Version:* #version
    ]
  ]
  #pagebreak()
]

#let info-box(title, body) = box(
  inset: 12pt,
  radius: 8pt,
  fill: rgb("#f8fafc"),
  stroke: rgb("#d7e2f0"),
)[
  *#title* \
  #body
]

#let small-note(body) = text(size: 9pt, fill: rgb("#5b6b7f"))[#body]

#let kv-table(rows) = table(
  columns: (32%, 68%),
  align: (left, left),
  inset: 7pt,
  stroke: rgb("#d8e0ea"),
  fill: (x, y) => if y == 0 { rgb("#eff4fa") } else { white },
  table.header[*Item*][*Details*],
  ..rows.flatten()
)

#let simple-flow(items) = block(
  inset: 0pt,
)[
  #for item in items [
    #box(
      inset: 10pt,
      radius: 8pt,
      fill: rgb("#f8fbff"),
      stroke: rgb("#ccd9eb"),
      width: 100%,
    )[
      *#item.at(0)* \
      #item.at(1)
    ]
    #align(center)[#text(fill: rgb("#94a3b8"))[↓]]
  ]
]
