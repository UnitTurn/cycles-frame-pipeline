# Publishing a release

[简体中文](README.zh-CN.md)

1. Build and test the patched engine. Set the extension manifest version and update the [English](notes.md) and [Chinese](notes.zh-CN.md) release notes.
2. Generate both Windows overlay ZIPs with `tools/package_windows_backend.py`, one for `en` and one for `zh-CN`. Install and test each package with the matching extension ZIP before staging it.
3. Run `python tools/stage_windows_release.py` at the repository root. Run its printed Git push command to stage both tested ZIPs on the temporary `release-input/v<version>` branch.
4. Commit `release/windows-overlay.sha256` with the matching source on `main`. Push `main`, tag the commit `v<version>`, and push that tag. The workflow verifies both Windows overlays, generates both extension packages and one shared source ZIP, and publishes all five assets.
5. After the five assets are available, the temporary input branch may be removed. The source tag retains the build instructions and digests.

To retry a failed publication after correcting its inputs, rerun the workflow for the same tag. A maintainer using Git can also push `main` to `refs/heads/publish/v<version>`. The workflow packages the source at the version tag.
