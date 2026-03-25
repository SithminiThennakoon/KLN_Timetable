#import "theme.typ": *

#cover(
  "ABC Handover",
  "Submission package record for repository access, deliverables, and included support material.",
  "Project handover record",
)

= Contents

#outline(title: none)

= Project Record

#kv-table((
  ([Project], [Lecture and Practical Timetable Generator]),
  ([Client context], [Faculty of Science timetable generation and distribution workflow]),
  ([Primary repo], [`KLN_Timetable`]),
  ([Active product flow], [Snapshot-first `Setup -> Generate -> Views`]),
  ([Primary documentation source], [Typst project under `docs/typst/`]),
))

= Repository Access

#kv-table((
  ([Git hosting URL], [`https://github.com/SithminiThennakoon/KLN_Timetable.git`]),
  ([Default integration branch], [`dev`]),
  ([Release branch], [`main`]),
  ([Submission branch for this documentation pass], [`documentation-handover`]),
))

= Included Deliverables

The repository submission includes:

- backend source
- frontend source
- deployment assets
- realistic CSV fixture pack
- verifier projects
- Typst source for the final documentation package

The documentation package includes the generated PDFs:

- `User Manual.pdf`
- `Technical Documentation.pdf`
- `ABC Handover.pdf`

= Supplementary Materials

The current submission does not include a separate shared folder, database backup, slide deck, or demo video.

Additional supporting material can be appended to this section later if new assets are produced.

= In-Repo Operational Assets

#kv-table((
  ([Fixture pack], [`backend/testdata/import_fixtures/production_like/`]),
  ([Fixture generator], [`backend/scripts/generate_import_fixture_pack.py`]),
  ([Azure deployment assets], [`deploy/azure/`]),
  ([Verifier projects], [`verifiers/rust_snapshot_verifier/`, `verifiers/elixir_snapshot_verifier/`]),
  ([Root environment example], [`backend/.env.example`]),
))

= Support and Troubleshooting Handover

Reference order for review and maintenance:

1. root `README.md`
2. `Technical Documentation.pdf`
3. deployment assets in `deploy/azure/`
4. fixture pack and import scripts
5. verification contract and verifier directories

Operationally important product behaviors to communicate:

- enrolment import must be materialized before support CSV imports
- support CSVs enrich a snapshot; they do not create the academic structure
- verification status matters after generation
- export behavior differs by audience

= Final Handover Checklist

- [ ] repository access confirmed
- [ ] integration branch and release branch confirmed
- [ ] user manual PDF generated
- [ ] technical documentation PDF generated
- [ ] ABC handover PDF generated
- [ ] repository branch for submission recorded
