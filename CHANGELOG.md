# Changelog

All notable changes to this repository are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- `make check` recomputes the README table from the unit suite and tracked
  artifacts, and fails if those numbers drift. Historical generation counts,
  costs, and review scores are withdrawn from the README; see `FAILURE_MODES.md`.
- Version banners read `APP_VERSION` in `config.py`. The disclaimer states that
  the tool cannot prevent fabricated data or plagiarism.
- The upload-path unit test removes the placeholder it used to leave under
  `data/templates/`.
- Governance baseline: LICENSE, security policy, code of conduct, contributor and
  support guides, issue and pull-request templates, CODEOWNERS, dependabot, and
  `.editorconfig` added. No research content changed.
