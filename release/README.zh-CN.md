# 发布版本

[English](README.md)

1. 设置扩展清单版本，更新[英文](notes.md)和[中文](notes.zh-CN.md)发行说明，以及对应版本的下载链接。
2. 在仓库根目录打包扩展和通用 Windows 引擎，传入已测试的定制程序及匹配的官方 Blender 安装。

   ```powershell
   python tools/package.py
   python tools/package_windows_backend.py .\backend\blender.exe "$env:ProgramFiles\Blender Foundation\Blender 5.2"
   ```

3. 验证打包后的引擎安装器和两种语言的扩展。运行 `python tools/stage_windows_release.py` 并执行其输出的 Git 推送命令，将引擎包暂存在 `release-input/v<版本>` 分支，摘要写入 `release/windows-overlay.sha256`。
4. 将校验摘要、代码和文档一起提交到 `main` 并推送，等待 **Check extension** 通过。给已验证提交打 `v<版本>` 标签并推送标签。
5. **Publish release** 核对暂存的引擎包，从标签构建两个扩展和一份源码包，发布四个资产。GitHub 确认四个文件已上传，且线上引擎摘要与标签记录一致后，工作流会删除本次实际使用的临时分支版本。

上传失败时临时分支会保留。可重跑相同标签的工作流，或把源码提交推送到 `refs/heads/publish/v<版本>`。重试会继续完成已有草稿，或在确认版本已经发布后重试清理分支。
