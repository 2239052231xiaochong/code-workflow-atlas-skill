# v0.1.0 验证记录

核对日期：2026-11-24。示例全部为人工编写的通用代码，不涉及生产环境、课程资料或真实模型请求。

## 自动测试

| 验证 | 结果 |
| --- | --- |
| Skill Creator 结构校验 | 通过 |
| Python 测试 | 14 项通过 |
| 示例 HTML 浏览器检查 | 28 项通过 |
| 双流程对照浏览器检查 | 30 项通过 |
| 独立前向测试源码 / 行为核对 | 38 项通过 |
| 独立前向测试扩展浏览器检查 | 31 项通过 |

浏览器检查包括鼠标 / 键盘选节点、源码原文一致性、行号、提示词示例、SVG 下载、手机布局、节点文字可读性、无 JavaScript 错误，以及离线页面无网络请求。

Python 测试包含 Git 快照不随工作副本变化、注释边界、错误引用、路径边界、提示词缺参及条件块失败、HTML 数据转义，以及 ZIP 重复打包得到相同字节。

## 独立使用测试

评估代理只获得新 skill、原始 `examples/report_pipeline.py` 和一个输出目录，没有获得预期流图或此前课件项目结论。代理独立完成了 7 节点流程、8 份源码摘录和中文注释，并检查缓存、异常、模板拼接及报告输出的真实行为。

它明确指出：示例中的 `demonstration_model()` 是固定返回的本地替身，没有真实模型调用；输出是 Python 字典，`format` 标签不代表已经写出 JSON 文件或视频。这些区别正确反映在流图中。

详见 [独立前向测试报告](forward-test.md) 与 [38 项行为记录](behavior-results.json)。

## 发现并修复的问题

1. **分支连线文字叠写**：调整为分别定位在各自线段上，重新核对示例标签不相互重叠。
2. **手机无溢出但节点不可读**：增加局部画布滚动与最小图宽；自动测试测量实际渲染字号，不再只检查页面宽度。

上述修复已进入最终 skill 模板。独立报告中的初版与隔离修复描述是前向测试过程记录；发布示例由最终模板重新生成。

## 可复现命令

```bash
python -m unittest discover -s tests -v
python skills/code-workflow-atlas/scripts/build_atlas.py --manifest examples/workflow.json --repo . --output artifacts/workflow.html
python skills/code-workflow-atlas/scripts/build_atlas.py --manifest examples/comparison.json --repo . --output artifacts/comparison.html
node skills/code-workflow-atlas/scripts/smoke_atlas.mjs artifacts/workflow.html artifacts/browser
node skills/code-workflow-atlas/scripts/smoke_atlas.mjs artifacts/comparison.html artifacts/comparison-browser
```

浏览器测试先按 README 安装 Playwright 和 Chromium。Windows 也可通过环境变量指定已有的 Playwright 与 Edge。

代码语义仍需人工或 AI 阅读核对；这些测试不代表任意项目、任意图形或线上性能都已验证。
