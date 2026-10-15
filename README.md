# CapabilityForge 矿工 GitHub 投稿项目

这是一个可以**整体复制为独立 GitHub 仓库**的课程与训练数据生成项目，适配当前 `CURRICULUM_METHOD` 和 `coordinated-a-v1` 投稿流程。

矿工提交公开仓库地址、40 位固定 commit、源码/依赖摘要和课程方法。验证者下载固定版本，在离线沙箱运行生成器，再用可信程序生成训练材料并训练、评估模型。这个仓库提供完整的生成和投稿准备流程；最终模型训练由现有验证者 Compute 执行。

生成器仅需 **Python 3.11 标准库**，不需要 pip 安装、GPU、钱包、Redis 或网络。可选的本地训练数据导出工具需要已安装、与验证者匹配的公共 `capabilityforge` 包，且不需要 training extra。

## 文件说明

| 文件 | 用途 |
| --- | --- |
| `generator.py` | 沙箱入口，接受 `--request`、`--output` |
| `curriculum.py` | 数学及语文、英语、物理、化学、生物的确定性抽样和课程排序 |
| `dependencies.json` | 标准库离线环境声明，供依赖摘要计算 |
| `METHOD.md` | 方法原理、能力范围、统一模型训练流程和开发边界 |
| `examples/*.request.json` | 五个公开开发请求，覆盖三阶段、中英文、图像与四种教学行为 |
| `examples/sources.json` | 当前公开开发预置的来源记录，仅供示例导出 |
| `tools/make_requests.py` | 从真实公开任务政策创建全量本地预览请求 |
| `tools/export_training_data.py` | 用官方可信渲染器导出完整训练材料与 messages |
| `tools/prepare_submission.py` | 从独立仓库 commit 生成 methods.json、源码清单和可审核快照 |
| `LICENSE` | 本模板新增代码的 MIT 许可；来源数据许可单独记录 |

## 1. 复制成独立项目

在 CapabilityForge 主项目根目录，由你选择一个新的独立目录：

```bash
cp -R miner-submission /path/to/my-miner-method
cd /path/to/my-miner-method
```

以下命令均在这个新项目根目录执行。不要直接把 CapabilityForge 主仓库的 URL 当作本项目 URL：验证者会下载整个 GitHub commit，不会只提取 `miner-submission/` 子目录。清单工具会检查 Git 仓库根目录，避免误用父仓库 commit。

## 2. 生成结构化训练题目

以下为人工开发操作示例，本次交付没有执行这些命令：

```bash
python generator.py \
  --request examples/math-foundation.request.json \
  --output var/math-foundation
```

产物为 `var/math-foundation/problem_specs.jsonl`。每行只包含可信 schema 接受的题目参数，恰好满足请求的 `sample_budget`。生成器不输出自由文本答案、训练权重或评分。

其他示例分别为 `math-transfer-image.request.json`、`math-growth.request.json`、`math-clarification.request.json`、`physics-growth.request.json`。更改输入 seed 会改变抽样；同一输入会复现相同输出。已有输出文件不会被覆盖，需要复用请求时选择新的输出目录。

## 3. 导出可阅读、可用于训练实验的数据

在已经安装匹配版本公共 `capabilityforge` 的 Python 3.11 环境中，按需执行：

```bash
python tools/export_training_data.py examples/*.request.json \
  --sources examples/sources.json \
  --output var/training-preview
```

此操作只读取本地输入，调用可信题目求解和材料渲染器，不加载模型或执行训练。产物包括：

| 路径 | 内容 |
| --- | --- |
| `specs/<unit_id>/problem_specs.jsonl` | 各学习单元的结构化题目 |
| `learning_materials.jsonl` | 题目、正确答案、教学步骤、messages、来源/许可、课程顺序、图片工件 |
| `messages.jsonl` | 每条记录的 id、messages 与 images，供对话训练适配器读取 |
| `images/*.png` | 由可信渲染器生成的真实图表，路径相对于输出目录 |
| `curriculum_manifest.json` | 单元、样本数量、生成 seed、请求摘要、材料摘要和开发标识 |

保留整个输出目录，图片文件和消息一起使用。`messages.jsonl` 是本地开发导出格式；现有 Compute 正式训练直接使用 `learning_materials.jsonl` 及其图片工件，不需要矿工另传这份本地导出。

## 4. 使用实际任务生成完整课程

将任务公布的**完整 TaskPolicy 对象**保存到 `var/task-policy.json`。它应包含 `task_id`、`program` 和 `allowed_dependencies`；不要保存 API 外层的列表或 `{policy: ...}` 包装。此文件只含公开任务，不含隐藏评测、钱包或私钥。

`var/` 被忽略；先自行创建该目录并存放政策。不要把示例来源清单当成实际任务许可。以下工具从任务的 `program.sources` 复制已有批准来源，不会替任务批准新来源：

```bash
python tools/make_requests.py \
  --policy var/task-policy.json \
  --seed 20261015 \
  --output var/requests

python tools/export_training_data.py var/requests/*.json \
  --policy var/task-policy.json \
  --output var/task-training-preview
```

预览 seed 仅用于本地开发，由工具派生各单元 seed；它不替换正式任务冻结后由协议产生的 seed。使用 `--policy` 导出时，除这个本地 seed 外，学习单元必须保持与公开任务相同。若只声明部分来源，请在请求生成工具和下文清单工具中用重复的 `--source-id SOURCE_ID` 选择相同来源；导出工具按这些请求里的来源生成材料。

## 5. 固定源码并准备 GitHub 提交清单

完成自己的课程策略修改后，将新项目初始化为独立仓库，并提交完整源码。以下 Git 命令由你自行执行；本模板不会创建或推送远程仓库：

```bash
git init
git add .
git commit -m "Add reproducible curriculum method"
```

在自己的 GitHub 账号下准备公开仓库，上传这个项目并保留该完整 commit。然后运行：

```bash
python tools/prepare_submission.py \
  --repository https://github.com/YOUR_ACCOUNT/YOUR_METHOD_REPO \
  --policy var/task-policy.json \
  --commit HEAD \
  --output var/submission
```

`--commit` 可以输入本地 ref，但最终清单固定为完整 40 位 commit。工具只读取已提交 Git 对象，不根据有缓存或本地文件的工作目录猜测源码摘要。源码树摘要与平台 `shared.artifacts.tree_manifest` 使用相同文件记录、路径排序和规范 JSON 算法；依赖摘要来自解析后的 `dependencies.json` 的规范 JSON，**不是直接对这个文件的排版字节做 SHA256**。

输出：

- `methods.json`：`{真实task_id: MethodDescriptor}`，可直接作为 `miner.method_file`。
- `method.json`：单个 `MethodDescriptor`，字段包含 repository、commit、tree_sha256、dependencies_sha256、method_license_id、entrypoint、sources。
- `snapshot.json`：固定 commit 和两个摘要，可用于有需要的历史投稿工具。
- `source-manifest.json`：完整文件摘要清单与源码树摘要。
- `source/`：从该 commit 导出的可人工审核源树，不含 `.git` 和未提交文件。

默认方法代码许可为 MIT，必须是任务允许的许可并与实际 `LICENSE` 相符。来源许可如 Apache-2.0 独立保留。工具要求干净工作区，检查任务是否批准标准库依赖声明；拒绝源码中的符号链接、模型序列化、凭据、Git LFS 指针、子模块及 `.gitattributes`，避免归档规则改变下载内容。生成物仅可写到仓库的 `var/` 或仓库外的新目录，防止把描述符纳入自身摘要。

清单生成不联网，不证明 GitHub 可访问。必须保证填写的公开仓库**确实包含清单中的 commit**，再提交。不要修改 `source/` 或手改摘要；修改代码后重新 commit 并输出到新的目录，如 `var/submission-v2`。不要将 methods.json 再提交到它描述的那个源码版本中。

## 6. 通过矿工客户端提交

在已经配置真实身份的 CapabilityForge 矿工环境中，将生成的 `methods.json` 复制到配置的 `miner.method_file` 路径，或显式传文件。以下路径需要替换为自己的实际值：

```bash
python -m capabilityforge.miner \
  --config /path/to/capabilityforge/configs/miner.local.toml \
  submit-method REAL_TASK_ID \
  --method-file /path/to/my-miner-method/var/submission/methods.json

python -m capabilityforge.miner \
  --config /path/to/capabilityforge/configs/miner.local.toml \
  method-status REAL_TASK_ID
```

用任务真实 `task_id` 替换 `REAL_TASK_ID`。客户端读取已有钱包，签名后发送到配置的公共 API；如需指定现有 API，可在子命令后传 `--api-url`。矿工钱包、节点配置和密钥保留在原有节点目录，不进入本 GitHub 项目。新协作投稿使用 `submit-method`，历史 V5 文件签名投稿有独立流程。

`RECEIVED` 表示已收到，`VERIFIED` 才表示来源与源码完成核验；是否进入训练和是否有贡献由后续准入、训练及独立复核决定。仅换 URL、commit 或注释不能证明新的方法贡献；应在 `curriculum.py` 中实现自己的课程策略，并接受任务去重规则。

## 手工检查与限制

本模板适配当前数学及五门学科的受限 schema，不是开放域任意语料生成平台。新题型、外部语料或额外依赖需要对应任务政策与可信执行侧支持。标准库依赖声明不包含可选的主机开发工具依赖；沙箱入口不会导入公共包。

使用时人工检查：各样例的题量和顺序；clarification 的 scale 是否为空；导出的答案、教学语言和图表引用；独立 GitHub 仓库是否包含固定 commit；methods.json 中任务 ID、来源、许可和摘要是否对应真实政策。正式训练的隐藏题族隔离、token/像素预算及评分仍由验证者审核，本地导出不提供通过证明。

本次仅创建代码与文档，未启动、重启或停止服务，未执行生成器、训练、测试、构建、lint、类型检查、浏览器或网络验证。以上命令全部供你后续按需执行。
