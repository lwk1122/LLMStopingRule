# GitHub 精简发布包

对应论文《Stopping Rules in LLM Code Repair: Editing Failures, Token Savings,
and Missed Repairs》。本包聚焦停止、选版、损失分解和编辑接口，不包含历史草稿和大体积运行日志。

## 运行

使用 Python 3.10 或更新版本，无第三方 Python 依赖：

```sh
python3 reproduce.py
python3 -m unittest discover -s tests -v
```

第一个命令核对分析代码、数据及参考结果的哈希并重算结果；第二个运行行为测试。
不要使用 `python -O`，因为核验使用断言。无需模型调用、联网或 Docker。

## 核心文件

- `analyze.py`：停止时点、最早/最新最高分选版、预算比较、两类损失、未知结果联合界限。
- `reproduce.py`：一键核验，输出 Table 2–5 和 Figure 4 对应数据。
- `editing/`：精确编辑器、匹配回退组件、工具格式和原系统提示。
- `data/versions.csv`：912 个版本的结构化观测；保留失败及不完整评价。
- `reference/`：冻结的原分析结果和哈希，不作为新结果写入位置。
- `tests/`：停止信号、标签泄漏防护、共同未知结果和编辑器原子性的测试。

输出写入 `results/`，该目录已在 `.gitignore` 中排除。
图相关输出是可绘图的数据和决策位置，不是 PDF 图片。

## 更新现有仓库

1. 将本目录中的代码、文档、`data/`、`reference/`、`editing/` 和 `tests/` 合并到目标仓库。
2. 同时保留 `.gitignore` 与 `MANIFEST.json`；不要加入本地生成的 `results/`、`__pycache__/`。
3. 按 README 运行复算和测试后再提交。不要覆盖仓库已有许可证，除非确定需要变更许可。
4. README、许可说明和 Git 设置可按仓库需要更新。若改动分析代码或数据，原 manifest 核验会提示变化。
5. 公开完整复现材料后，在 README 和论文中补上仓库或存档链接。

这个精简包不能替代完整复现包的原始日志核验，也不声称可一键重跑原始模型和仓库测试。
原始完整包保留全部提示、补丁、评价日志和实验环境资料。
本次未上传 GitHub，也未替作者授予新的开源许可证；第三方 Apache-2.0 声明已保留。
