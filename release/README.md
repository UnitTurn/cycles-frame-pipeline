# Publishing a release · 发布版本

1. Build and test the patched engine, then create the Windows overlay with `tools/package_windows_backend.py`. The extension manifest sets the version. Update both languages in `release/notes.md`.
2. Run `python tools/stage_windows_release.py` at the repository root. Run the printed Git push command to stage the tested ZIP in the temporary `release-input/v<version>` branch.
3. Commit `release/windows-overlay.sha256` with the matching source changes on `main`. Push `main`, tag the commit `v<version>`, and push that tag. The release workflow builds the extension and project source archive, verifies the Windows ZIP against the committed digest and attaches all three to the GitHub Release.
4. Once the three assets are available, the temporary input branch may be removed. The source tag keeps the build instructions and the recorded digest.

To retry a failed publication after correcting the input branch, rerun the workflow for that tag. A maintainer using only Git can push `main` to `refs/heads/publish/v<version>` to request a retry. The workflow packages the immutable version tag.

1. 构建并测试配套引擎，再运行 `tools/package_windows_backend.py` 生成 Windows 引擎包。版本号来自插件清单，发布说明的中英文两版保存在 `release/notes.md`。
2. 在仓库根目录运行 `python tools/stage_windows_release.py`，按输出的 Git 命令将已测试的 ZIP 推送到临时分支 `release-input/v<版本号>`。
3. 将 `release/windows-overlay.sha256` 和对应源码一起提交到 `main`，推送主分支，再给该提交打上 `v<版本号>` 标签并推送。发布工作流会打包插件和项目源码，核验 Windows 包的摘要，再将三项附到 GitHub Release。
4. 确认三项均可下载后即可删除临时分支，版本标签会保留构建说明和摘要。

修正临时分支后，可重新运行对应标签的发布任务。仅使用 Git 的维护者也可以将 `main` 推送到 `refs/heads/publish/v<版本号>` 触发重试。工作流始终从指定的版本标签构建发布包。
