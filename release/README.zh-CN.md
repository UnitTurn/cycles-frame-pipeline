# 发布版本

[English](README.md)

1. 构建并测试引擎，设置扩展清单版本，分别更新[中文](notes.zh-CN.md)和[英文](notes.md)发布说明。
2. 使用 `tools/package_windows_backend.py` 分别为 `zh-CN` 和 `en` 生成 Windows 引擎 ZIP，将两套引擎与各自语言的插件配套安装并验证。
3. 在仓库根目录运行 `python tools/stage_windows_release.py`，按输出的 Git 命令将两份已验证的包推送到临时分支 `release-input/v<版本号>`。
4. 将 `release/windows-overlay.sha256` 与对应源码一起提交并推送至 `main`。给该提交打上 `v<版本号>` 标签并推送。工作流会核验两份引擎包，生成两个插件包和一个通用源码包，并发布全部五项。
5. 确认资产均可下载后即可删除临时分支，版本标签保留构建说明和摘要。

修正输入后可以重新运行该标签的发布任务，也可以将 `main` 推送到 `refs/heads/publish/v<版本号>` 触发重试。任务从版本标签读取源码。
