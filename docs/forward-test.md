# 独立前向测试报告

测试请求：把 examples/report_pipeline.py 整理成简洁、可点击的中文 HTML 流图，展开查看代码注释和提示词来源，并说明分支与实际行为。

## 交付物

- workflow.html：离线、可点击的最终流程图；7 个节点、7 条边、8 份源码摘录。
- workflow.json：语义清单，可作为生成器输入；它没有依赖其他会话或项目案例。
- browser-final/overview-desktop.png：最终桌面总览。
- browser-final/overview-mobile.png：最终窄屏总览。
- browser-final/prompt-templates.png：真实模板与来源视图。
- browser-final/workflow-atlas.svg：最终本地 SVG 导出。
- behavior-results.json：38 项源码与本地运行检查。
- browser-final/smoke-results.json：最终浏览器基础检查，28 项通过。
- browser-final/extended-results.json：31 项额外交互与可读性检查。
- verify_behavior.py、verify_browser.mjs：本次隔离验证脚本。
- adjust_output.py：记录本次只对生成 HTML 做的显示修复；未修改技能或示例源码。

## 核对基线与语义

源文件没有 Git 元数据，故标为工作副本（2026-11-24）。原始文件 SHA-256：

`625aa07f665f8bbd463383974fb85ac69bcabf34113bca4ca2272c1a513f90d1`

已逐一核对源摘录、SHA-256 和原始行号；中文说明与原始源码分开显示。关键语义：

1. 入口为外部调用的 run(topic, material, cache)，文件本身没有 CLI 或顶层启动代码。
2. 材料 strip() 后为空会立即抛出 Material is empty，不查缓存、不生成、不写缓存。
3. 缓存键为 (topic, cleaned)。命中后直接返回 reused=True，跳过提示词、替身、解析和校验；命中值本身没有校验。
4. 未命中时从模块常量取模板，依次执行两次 str.replace；不是另一模型生成提示词，也不是 Mustache 框架。展示真实模板和示意参数，未伪造精确组装视图。
5. demonstration_model() 是不使用参数内容的确定性替身，返回固定 JSON 字符串，没有真实模型请求。
6. json.loads 之后校验 summary 是否为非空字符串；当前固定正常返回不会触发失败分支。仅在隔离测试的函数全局变量中注入异常回复，验证缺字段、非字符串、空白和无效 JSON；没有修改原代码。
7. 校验通过后将 summary 写入 cache，再返回 reused=False 的报告。
8. make_report() 只返回 Python 字典；format='json-report' 是标签，没有写 JSON 文件、TTS、渲染或导出。

## 验证

- 原始未修显示的产物：技能自带 smoke 27 项通过，截图保留在 browser/。
- 最终产物：基础 smoke 28 项 + 扩展浏览器检查 31 项 + 源码/运行检查 38 项全部通过。
- 扩展验证覆盖真实鼠标逐节点选择、Enter/Space、所有提示词来源摘录的注释/原始源码切换、真实 SYSTEM/USER 常量、参数和返回示例标签、打印按钮、SVG、分支标签包围盒与窄屏选择。
- 最终分支标签包围盒互不重叠；390px 窄屏文档不溢出，流程图在本地画布内滚动，标题渲染字号约 21.85px，可选择右侧分支。
- 无 JavaScript 错误；最终扩展检查主动阻断非 file: 请求且记录为 0 次。没有发布、访问凭据或执行网络请求。

## 原始技能问题与本产物修复

### 问题 1：分支标签碰撞

原始 assets/atlas.html 使用 Math.min(ax,bx)+8 作为边标签 x 坐标；同一节点向垂直和右侧分支时，标签共用位置。此例的“键存在/键不存在”和到报告的两条入边标签发生叠写。

原始证据：browser/desktop.png。

本产物修复：仅在 workflow.html 中，将水平边标签放在各自线段中心；垂直边标签放在自身线右侧。清单也缩短了底部标签，完整条件仍在节点说明中。最终用 SVG getBBox 核对 7 个标签，没有互相重叠。

### 问题 2：窄屏无溢出却不可读

原始 SVG 使用 width:100% 将整个 1000 单位宽图缩进 390px；节点字号随之降至约 8–9px。原来的“文档无溢出”检查会通过，因此不能代表可读。

原始证据：browser/mobile.png。

本产物修复：仅在 workflow.html 的窄屏规则中保留 950px 图宽和本地横纵向滚动，并给出滚动提示。最终标题实测约 21.85px，文档宽度不溢出，能够滚到并点击右侧分支。

本报告区分原始发现与本产物修复；父任务后来调整规范技能资产不属于本测试对源目录的修改。本测试未修改技能包或应用源目录。
