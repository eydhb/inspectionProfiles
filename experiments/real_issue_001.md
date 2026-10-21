# real_issue_001：PyJWT 参数字典被意外修改

**结论：Top-1 文件命中失败；Top-3 文件命中成功。真实修复文件排第 3。**

本次使用未修改的 **CodeLens 离线规则模式基线**，由 LangGraph 调度。没有调用大模型，也没有根据结果调参或改写排名。实验时间：2026-10-21 17:08:03–17:08:04（Asia/Shanghai）。

## 1. 真实问题与选样依据

- Issue：[jpadilla/pyjwt #679](https://github.com/jpadilla/pyjwt/issues/679)，2021-08-10 提出。
- 原标题：PyJWT.decode_complete() method changing provided options object。
- 问题：调用解码 API 后，调用者传入的 `options` 字典被添加了额外字段；预期是解码不改变这个入参对象。
- 修复关联：[PR #743](https://github.com/jpadilla/pyjwt/pull/743) 明确关闭 #679，2022-04-05 合并。选它是因为仓库较小、Issue 与单提交修复关联明确，而且可以用本地数据复现参数变化。选样发生在首次定位运行之前，没有按命中结果更换样本。

原 Issue 包含源码文件名、实现片段以及复制字典的建议。本次只使用标题和预期／实际行为的中文转述，保留公开 API 名称和选项名，删除这些直接定位及修复提示；也没有向 Agent 提供 PR、修复 diff 或后续评论。因此，这是**经过明确编辑的症状输入**，并非完整原文输入。固定输入见 [input.txt](real_issue_001/input.txt)：

> PyJWT.decode_complete() 会修改调用者传入的 options 字典。预期调用 jwt.decode 后，options 保持 {'verify_signature': False, 'verify_aud': False}；实际会额外增加 verify_exp、verify_nbf、verify_iat、verify_iss 等字段。请定位导致调用参数被修改的代码。

实验组织者为确认样本查阅过修复记录；被测规则 Agent 只收到上述文本和修复前源码，不能将本实验称为组织者未知答案的盲测。

## 2. 仓库、版本与实验隔离

| 项目 | 固定值 |
|---|---|
| 测试仓库 | [jpadilla/pyjwt](https://github.com/jpadilla/pyjwt) |
| 修复前 Commit | [`1f1fe15bb41846c602b3e106176b2c692b93a613`](https://github.com/jpadilla/pyjwt/commit/1f1fe15bb41846c602b3e106176b2c692b93a613) |
| 修复 Commit | [`3d4d82248f1120c87f1f4e0e8793eaa1d54843a6`](https://github.com/jpadilla/pyjwt/commit/3d4d82248f1120c87f1f4e0e8793eaa1d54843a6) |
| CodeLens 版本 | [`3eddd1f77132e9a0fad87defb908b4a6e588b96d`](https://github.com/eydhb/issue-500-agent-makefile-src-controller/commit/3eddd1f77132e9a0fad87defb908b4a6e588b96d) |
| 环境 | Windows、Python 3.11.4、LangGraph 1.2.16 |
| 模式与预算 | `offline`；最多 28 次工具调用、10 个文件读取 |
| 实际运行 | 1 次定位；19 次工具调用：1 次列表、8 次搜索、10 次读取 |
| Agent 耗时 | 453 ms，仅此机器上的单次观测 |
| 文件范围 | 完整 Git 树导出 76 个文件；CodeLens 可见 63 个；文件枚举未截断 |

Git 验证了修复提交的唯一父提交就是上述修复前 Commit。导出快照与每个 Git blob 逐字节核对；快照不包含 `.git`，修复后的源码、实验记录和修复 diff 均位于 Agent 仓库根目录之外。运行前后快照保持不变。源文件、输入、结果和快照哈希见 [run_metadata.json](real_issue_001/run_metadata.json) 与 [snapshot_manifest.json](real_issue_001/snapshot_manifest.json)。

准备阶段曾因 Windows 的 Git 换行转换导致快照字节校验失败，**当时尚未调用 Agent**。导出器改为使用 `core.autocrlf=false`，在新目录成功导出后才执行唯一一次定位。这不是一次失败后改题重跑的定位实验。

## 3. Agent 实际候选与依据

以下保持 [agent_result.json](real_issue_001/agent_result.json) 的原始顺序。分值是规则排序值，不是概率。所有 70 条展示证据均已逐行与旧版本核对。

| 排名 | 候选文件 | 分值 | 实际展示证据 | 对原始依据的说明 |
|---:|---|---:|---|---|
| 1 | `jwt/algorithms.py` | 13 | 116–118、123–125、130–132、137–139 | 展示抽象算法方法的 `NotImplementedError`；没有指出字典变更 |
| 2 | `jwt/api_jws.py` | 13 | 47–52、61–63、103–105 | 展示算法注册异常及 headers 校验，未说明目标问题 |
| 3 | **`jwt/api_jwt.py`** | **13** | **47–49、97–99** | 真实修复文件，但展示的是 payload 类型检查和缺少 algorithms 的异常 |
| 4 | `docs/conf.py` | 9 | 82、89、112、119 | 文档构建配置中的 `False`／`Options` |
| 5 | `CHANGELOG.rst` | 8 | 7–68 内的 18 条非连续行 | 旧版发布记录与项目名称等通用匹配 |
| 6 | `docs/api.rst` | 8 | 23–105 内的 18 条非连续行 | 解码 API 和验证选项的文档 |

六个候选的原始 `reason` 都是同一个通用理由：“命中与问题有关的关键词或已读代码中的关联符号；已读取以下片段，需要结合调用路径确认相关性。”

**不能把上表中的人工解释冒充 Agent 的推理。** 原始工具记录显示 Agent 读取了 `jwt/api_jwt.py:9–108`，其中包含实际问题代码；但它最终没有引用关键的 `setdefault` 语句。表中的范围也不意味着每个范围内的行都已展示，完整非连续证据保留在 JSON 中。

## 4. 实际修复文件与行为验证

修复提交仅修改两个文件：

| 文件 | 分类与计分 |
|---|---|
| `jwt/api_jwt.py` | 生产实现，纳入 ground truth |
| `tests/test_api_jwt.py` | 回归测试，单独记录，不计作生产文件命中 |

因此，预先规定的生产文件评分集合为：

```text
G = {jwt/api_jwt.py}
```

修复前的 [`jwt/api_jwt.py:74–95`](https://github.com/jpadilla/pyjwt/blob/1f1fe15bb41846c602b3e106176b2c692b93a613/jwt/api_jwt.py#L74-L95) 直接使用传入字典，再调用 `setdefault` 添加验证选项。修复在方法开始处对字典做浅复制。见 [实际 diff](real_issue_001/fix.patch) 和 [修复提交](https://github.com/jpadilla/pyjwt/commit/3d4d82248f1120c87f1f4e0e8793eaa1d54843a6)。

定位结果保存后，另用 [最小复现脚本](reproduce_pyjwt_679.py) 在两个快照的独立 Python 进程中执行。它使用原 Issue 的 `verify_signature=False`、`verify_aud=False` 情形及本地合成 HS256 数据，不调用网络服务。

| 版本 | 解码是否成功 | 调用者字典是否改变 | “不得修改入参”检查 |
|---|---|---|---|
| 修复前 | 是 | 新增 `verify_exp`、`verify_nbf`、`verify_iat`、`verify_iss` | 失败，退出码 1 |
| 修复后 | 是 | 无新增字段 | 通过，退出码 0 |

完整观测见 [reproduction.json](real_issue_001/reproduction.json)。两个快照内部版本字符串都还是 `2.3.0`，所以实验标识必须使用 Commit，而不能仅依赖包版本号。本次执行的是针对该问题的最小复现，并未运行 PyJWT 的完整测试套件。

## 5. Top-1、Top-3 评分

定义：按原始顺序取前 k 个不同的仓库相对路径，与实际生产修复文件集合求交；交集非空即命中。不按 basename 模糊匹配，也不把测试文件当作生产修复文件。

```text
Top-k hit = 1，若 set(candidates[:k]) ∩ G 非空；否则为 0。
```

| 指标 | 参与评分的候选 | 结果 |
|---|---|---|
| Top-1 | `jwt/algorithms.py` | **失败，0** |
| Top-3 | `jwt/algorithms.py`、`jwt/api_jws.py`、`jwt/api_jwt.py` | **成功，1** |
| 首个相关文件排名 | `jwt/api_jwt.py` | **3** |

机器可读结果见 [metrics.json](real_issue_001/metrics.json)。本次 `n=1`，这些是一个样本的命中指示，**不能推断整体准确率，更不能声称准确率为 100%**。

## 6. 失败原因与可靠性边界

1. **Top-1 失败的直接排序原因：分数封顶与同分排序。** 三个文件的唯一命中行数分别为 8、24、24；评分将命中数封顶为 8，再为 Python 文件加 5，全部变成 13。最终报告按路径字典序打破同分，`algorithms.py` 排到了前面。不是“没搜索到正确文件”，而是已经读取后排序不够准确。
2. **宽泛词产生噪声。** `algorithms.py` 的 8 条匹配全部来自 `False`。8 个搜索词中有 6 个达到每次 40 条的截断上限。原始搜索词是 `PyJWT / decode_complete / options / jwt / decode / verify_signature / False / verify_aud`。事后审计见 [search_audit.json](real_issue_001/search_audit.json)。
3. **文件命中不等于错误行或根因解释成功。** 读取窗口覆盖了关键代码，证据选择却优先挑选 `raise` 等预置语法信号，覆盖了关键词证据。最终显示的 47–49、97–99 行没有指出实际修改点 74–77，也没有指出 90–95 行的入参变更逻辑。
4. **报告模板迁移失败。** 原始总结仍出现“本次 500”，待验证项仍要求接口、令牌状态和 HTTP 500 日志。本 Issue 描述的是参数字典被修改，不能把这些模板文字当成真实故障现象。为保留实验真实性，没有改写原始输出。

以上是依据当前代码和 trace 的事后分析，尚未做消融实验，不能据此承诺某项改动一定提升命中率。后续可以单独建立新实验，比较过滤 `False` 等通用词、提高精确 API 匹配权重、处理同分排名、改进证据选择和模板的问题；本次保持基线不变。

## 7. 如何复核与复跑

在本 CodeLens Git 仓库根目录执行。下面使用已有本机环境；换电脑时先在项目目录安装 `requirements-lock.txt`，并将命令中的解释器替换为自己的虚拟环境 Python。

```powershell
# 获取同一个公开仓库；历史库与 Agent 可见快照分离
git -c http.sslBackend=openssl clone --no-checkout --no-tags https://github.com/jpadilla/pyjwt.git work/benchmarks/real_issue_001_replay/history

# 复跑写入新目录，脚本拒绝覆盖首次实验
.\work\runtime\venv\Scripts\python.exe outputs/issue-locator/experiments/run_real_issue_001.py --history work/benchmarks/real_issue_001_replay/history --workspace work/benchmarks/real_issue_001_replay/snapshots --output-dir work/benchmarks/real_issue_001_replay/results
```

复跑必须使用被固定的 Agent 实现；脚本会检查源码是否与记录的 CodeLens Commit 一致。时间和耗时字段不保证相同，候选顺序与评分才是主要比较对象。首次结果保存在本报告同名目录中。

本次机器上还可以直接复核两个快照的行为：

```powershell
# 预期退出码 1：旧版本违反“不修改入参”的要求
.\work\runtime\venv\Scripts\python.exe -I -B outputs/issue-locator/experiments/reproduce_pyjwt_679.py --snapshot work/benchmarks/real_issue_001/snapshots_exact/before

# 预期退出码 0：修复版本满足要求
.\work\runtime\venv\Scripts\python.exe -I -B outputs/issue-locator/experiments/reproduce_pyjwt_679.py --snapshot work/benchmarks/real_issue_001/snapshots_exact/after
```

快照只保存在本地 `work/` 中，不随实验记录分发；固定 SHA、文件清单、原始输出、diff 和上游 [MIT 许可](real_issue_001/upstream-LICENSE.txt) 随记录保存。修复后的行为验证与候选评分相互独立，不能把人工复现结论追记成 Agent 自主发现的结论。
