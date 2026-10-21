# inspectionProfiles

**CodeLens 真实 GitHub Bug 定位基准实验记录与复现工具。**

本项目将“Agent 能运行”进一步落实为可检查的实验：固定真实 Issue、修复前代码和 Agent 版本，保存候选文件及源码证据，再用真实修复提交评价 Top-1、Top-3 文件命中情况。

这是从 [CodeLens 项目](https://github.com/eydhb/issue-500-agent-makefile-src-controller) 拆出的独立实验仓库。它包含本次新增的实验记录、原始 JSON、修复 diff、来源信息和复现脚本；CodeLens 主程序作为固定版本的外部依赖使用，不重复放入本仓库。

## 先看实验结果

完整记录：[experiments/real_issue_001.md](experiments/real_issue_001.md)。

| 项目 | 结果 |
|---|---|
| 真实 Issue | [PyJWT #679](https://github.com/jpadilla/pyjwt/issues/679) |
| 问题 | 解码 API 意外修改调用者传入的 options 字典 |
| 运行模式 | CodeLens 离线规则模式，LangGraph 编排，无大模型 API 调用 |
| Top-1 文件命中 | **失败** |
| Top-3 文件命中 | **成功** |
| 实际生产修复文件 | jwt/api_jwt.py，候选中排名第 3 |
| 工具记录 | 19 次调用，6 个最终候选，70 条展示证据 |
| 最小行为复现 | 修复前字典新增 4 个字段；修复后保持不变 |

前三名候选依次是：

1. jwt/algorithms.py
2. jwt/api_jws.py
3. **jwt/api_jwt.py**

前三个文件规则分值相同，最终按路径排序；第一名的匹配来自宽泛的 False 关键词。Agent 虽然读取了真正有问题的方法，却没有展示关键的字典修改语句，还套用了与本问题无关的 HTTP 500 文案。这些不足全部保留在原始输出中，便于后续做对照实验。

**文件命中不等于定位到错误行，也不等于解释了根因。一个样本的结果不能代表整体准确率。**

## Benchmark 如何计分

Ground truth 取真实修复提交修改的生产代码文件；测试文件另列。本次生产文件集合只有 jwt/api_jwt.py。

保持 Agent 原始候选顺序，对相同仓库相对路径去重，然后按精确路径判断：

```text
Top-k hit = 前 k 个候选与真实生产修复文件集合的交集是否非空
```

这是一种 any-hit 指标。对于涉及多个生产文件的修复，命中一个文件不意味着找全了所有修复文件。本实验没有把分值解释为概率，也没有把测试文件或同名文件当成生产文件命中。

## 仓库结构

```text
inspectionProfiles/
├── README.md
├── verify_record.py                  # 无第三方依赖的记录与评分核验
└── experiments/
    ├── real_issue_001.md              # 首次实验完整记录
    ├── run_real_issue_001.py          # 指定外部 CodeLens 路径的复跑入口
    ├── reproduce_pyjwt_679.py         # 验证字典是否被意外修改
    └── real_issue_001/
        ├── case.json                 # 样本、固定版本、输入处理和评分规则
        ├── input.txt                 # 实际传给 Agent 的症状描述
        ├── agent_result.json         # 原始候选、真实行号和完整工具记录
        ├── metrics.json              # Top-1、Top-3 与 ground truth
        ├── run_metadata.json         # 时间、环境、预算及 SHA-256
        ├── snapshot_manifest.json    # 修复前 76 个文件的内容摘要
        ├── visible_files.json        # Agent 能检索的 63 个文件
        ├── search_audit.json         # 事后搜索与排序审计
        ├── reproduction.json         # 修复前后的行为观测
        ├── provenance.json           # Issue → PR → Commit 来源关系
        ├── fix.patch                 # 真实修复 diff
        └── upstream-LICENSE.txt      # 所引用 PyJWT 代码的 MIT 许可
```

首次实验记录及证据保持原样。独立仓库只调整了运行脚本的项目路径接入方式，增加 --codelens 参数，并新增本 README、忽略规则和核验脚本。原实验报告中的机器目录与命令是历史记录；从这个独立仓库复跑时，请使用下面的步骤。

## 固定版本与隔离方式

| 对象 | Commit |
|---|---|
| CodeLens 实现 | [3eddd1f77132e9a0fad87defb908b4a6e588b96d](https://github.com/eydhb/issue-500-agent-makefile-src-controller/commit/3eddd1f77132e9a0fad87defb908b4a6e588b96d) |
| PyJWT 修复前 | [1f1fe15bb41846c602b3e106176b2c692b93a613](https://github.com/jpadilla/pyjwt/commit/1f1fe15bb41846c602b3e106176b2c692b93a613) |
| PyJWT 修复 | [3d4d82248f1120c87f1f4e0e8793eaa1d54843a6](https://github.com/jpadilla/pyjwt/commit/3d4d82248f1120c87f1f4e0e8793eaa1d54843a6) |
| 修复 PR | [jpadilla/pyjwt #743](https://github.com/jpadilla/pyjwt/pull/743) |

运行脚本核验 CodeLens 源码与固定提交一致，导出修复前 Git 树，并逐文件校验字节内容。Agent 只能读取该快照，不能读取历史库、修复后的树、实验报告或修复 diff。保存原始输出后才计算指标。已有结果和快照目录不能被复跑静默覆盖。

原 Issue 已直接给出了源文件名。本实验输入明确删除了该文件名、源码片段及修复建议，只保留症状、API 名称和选项；它不是完整原文输入。实验组织者知道修复答案，被测规则 Agent 没有接收答案。

## 快速检查：不安装 CodeLens 也能核验记录

需要 Python 3.11+ 和 Git。以下命令以 Windows PowerShell 为例，从本仓库根目录运行：

```powershell
git clone https://github.com/eydhb/inspectionProfiles.git
cd inspectionProfiles
python verify_record.py
```

这个命令会验证输入、case、原始结果与快照清单的 SHA-256，重新计算排名及 Top-1/Top-3，核对工具调用数量和保存的行为复现记录。

默认只验证已保存文件的内部一致性，不重新运行 Agent，也不声称已经拿到源码核对行号。取得旧版本快照后，可增加 --snapshot 参数逐行检查源码证据。

## 完整复跑

### 1. 获取两个外部仓库

```powershell
git clone https://github.com/eydhb/issue-500-agent-makefile-src-controller.git deps/codelens
git -C deps/codelens checkout --detach 3eddd1f77132e9a0fad87defb908b4a6e588b96d
git clone --no-checkout --no-tags https://github.com/jpadilla/pyjwt.git deps/pyjwt
```

只对新克隆到 deps 的 CodeLens 副本切换版本。PyJWT 历史仓库不检出工作树，分析脚本另外导出指定 Commit。下载仓库和首次安装依赖需要网络，规则模式的定位过程不调用模型 API。

### 2. 安装固定环境

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r deps/codelens/outputs/issue-locator/requirements-lock.txt
```

首次记录使用 Python 3.11.4、LangGraph 1.2.16。其他兼容 Python 环境下的耗时可能不同，依赖以固定 CodeLens 提交内的锁定清单为准。在 Linux/macOS 上将解释器路径改为 .venv/bin/python；本次实际执行环境为 Windows。

### 3. 执行定位并保存新的结果

```powershell
.\.venv\Scripts\python.exe experiments/run_real_issue_001.py --codelens deps/codelens --history deps/pyjwt --workspace work/replay/snapshots --output-dir work/replay/results

.\.venv\Scripts\python.exe verify_record.py --record work/replay/results --snapshot work/replay/snapshots/before
```

脚本不修改 Agent 的搜索词生成、权重或工具预算。这里生成的是独立复跑结果，不覆盖 experiments/real_issue_001 内的首次记录。再次运行时换用 work/replay-002 等全新目录。

### 4. 验证 Bug 在修复前后消失

上一步已生成 before 快照。先导出对应 after 快照：

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from experiments.run_real_issue_001 import export_snapshot; export_snapshot(Path('deps/pyjwt'), '3d4d82248f1120c87f1f4e0e8793eaa1d54843a6', Path('work/replay/snapshots/after'))"

.\.venv\Scripts\python.exe -I -B experiments/reproduce_pyjwt_679.py --snapshot work/replay/snapshots/before
# 预期退出码 1：解码成功，但调用者字典被修改

.\.venv\Scripts\python.exe -I -B experiments/reproduce_pyjwt_679.py --snapshot work/replay/snapshots/after
# 预期退出码 0：解码成功，调用者字典保持不变
```

脚本仅使用本地合成 HS256 数据；不会访问真实账号、真实令牌或服务。使用 -B 避免在快照内生成字节码缓存。

## 已知限制与下一步

- 只有一个历史问题，不能估计整体准确率；应继续增加预先确定的独立样本。
- 当前是规则模式基线，未测量真实大模型的定位效果。
- 正确文件进入 Top-3，但关键错误语句没有进入展示证据，根因解释仍然不足。
- 同分排序和 False 等通用词会产生噪声；后续优化应保留本次基线，单独记录新实验与配置。
- 原始报告出现不适用的 HTTP 500 模板，保留它是为了准确记录现有系统的不足。
- 最小复现不等于 PyJWT 完整测试套件通过；独立仓库中的核验也不代表新的模型评测。

建议新增实验时沿用 Issue、固定快照、原始输入、完整结果、真实修复集合、评分和失败分析这些记录项。未经说明，不要在看到结果后换题、重排候选或覆盖失败记录。

## 来源与文件管理

PyJWT 修复片段遵循随附的 [MIT 许可](experiments/real_issue_001/upstream-LICENSE.txt)。本仓库保留来源链接，不将上游代码或人工行为验证结论归为 Agent 自主发现。

本地虚拟环境、下载仓库、运行缓存和复跑产物位于 .venv、deps、work，已由 .gitignore 排除；仓库不包含模型 API 密钥或本机运行环境。
