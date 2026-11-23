# Publishing a release

[简体中文](README.zh-CN.md)

1. Set the extension manifest version. Update the [English](notes.md) and [Chinese](notes.zh-CN.md) notes and their versioned download links.
2. From the repository root, package the extensions and the single Windows engine. Supply the tested patched executable and the matching official Blender installation.

   ```powershell
   python tools/package.py
   python tools/package_windows_backend.py .\backend\blender.exe "$env:ProgramFiles\Blender Foundation\Blender 5.2"
   ```

3. Test the packaged engine installer and both extension editions. Run `python tools/stage_windows_release.py` and execute its printed Git push command. This stages the tested engine ZIP on `release-input/v<version>` and writes its digest to `release/windows-overlay.sha256`.
4. Commit the digest, code and documentation together. Push `main` and wait for **Check extension**. Tag the tested commit `v<version>` and push that tag.
5. **Publish release** verifies the staged ZIP, builds two extensions and the source ZIP at the tag, then publishes the four assets. After GitHub reports all four uploaded and the published engine digest matches the tag, it deletes the exact temporary branch revision it used.

A failed upload leaves the staging branch available. Rerun the workflow for that tag, or push the source commit to `refs/heads/publish/v<version>`. A retry can complete an existing draft or verify an already published release before retrying branch cleanup.
