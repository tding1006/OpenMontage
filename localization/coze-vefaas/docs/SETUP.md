# OpenMontage · 原生安装与 fork 同步说明

## 一、来源

| 项 | 值 |
| --- | --- |
| 同步源（唯一） | `https://github.com/tding1006/OpenMontage.git`（你的 fork） |
| 上游 | `OpenMontageInc/OpenMontage`（**不拉取、不合并**） |
| 分支 | `main` |
| 已安装提交 | `fecb9a1e3c`（2026-11-08 22:23:54 -0800） |
| 安装方式 | 原生安装（SKILL.md 直读，非 ClawHub 镜像） |

## 二、目录结构

```
Video_Maker/
├── skills-src/OpenMontage/     git 检出（origin = 你的 fork，只读，不手改）
│   ├── .agents/skills/         92 个 SKILL.md 技能（Layer 3 技术知识）
│   └── skills/                 158 个 md（Layer 2 项目约定：core/creative/meta/pipelines）
├── skills/                     原生安装区（94 项 = 92 技能 + INDEX.md + registry.json）
│   ├── <slug>/SKILL.md
│   ├── INDEX.md                人读索引（技能 / 说明 / 依赖环境变量 / 文件数）
│   └── registry.json           机读注册表（含每个技能的 digest）
├── knowledge/                  Layer 2 知识文件的安装副本（158 个）
├── .openmontage/
│   ├── state.json              已安装提交 + 每技能 digest + 知识文件哈希
│   ├── pending.json            待确认的检查结果（apply 前存在）
│   └── trash/                  同步时被替换/移除的旧版本（不硬删除）
├── reports/                    每次 check 生成的变更报告（latest.md 为最新）
├── scripts/openmontage.py      安装 / 检查 / 应用 / 重载
├── tools/node24/               OpenClaw 所需 Node 24.22.3（系统 Node 22 不满足 engines）
├── tools/openclaw/             OpenClaw CLI 2026.11.3（项目内安装）
├── .openclaw/                  OpenClaw 状态目录（state/plugin-skills，项目内隔离）
├── openclaw.sh                 OpenClaw CLI 包装脚本（已注入 PATH / 状态目录 / workspace）
└── openmontage.sh              技能安装与同步脚本
```

## 三、日常操作

```bash
./openmontage.sh status     # 已安装提交 vs fork 最新提交，本地是否有改动
./openmontage.sh check      # 只 fetch fork，生成变更报告到 reports/，不动安装区
./openmontage.sh apply --yes  # 人工确认后才执行：更新检出 → 重装变更技能 → 重建索引
./openmontage.sh reload     # 仅重建索引（不改代码）
```

同步语义（与你的要求一致）：

1. **只拉 fork**：`origin` 硬校验为 `tding1006/OpenMontage`，不一致直接拒绝；不 fetch 任何其他 remote。
2. **先报后改**：`check` 只 fetch + 生成 diff 报告，安装区零改动。
3. **确认后重载**：`apply` 必须带 `--yes`；执行后重建 `skills/INDEX.md`、`skills/registry.json`，并打印需要重读的 SKILL.md 列表。
4. **不硬删除**：被移除或被替换的技能目录移入 `.openmontage/trash/<时间戳>/`。
5. **本地改动可查**：`status` 会用 digest 比对，列出被手改过的技能。

## 四、变更报告包含什么

- 待合入提交列表（`base..fork/main`）
- 技能级变更：新增 / 移除 / 修改（修改标注文件数与是否动了 `SKILL.md`）
- Layer 2 知识文件变更清单
- 仓库其他改动（tools / pipeline_defs / docs 等，**不安装**，仅提示）

## 五、使用技能

需要某项能力时读取对应 `skills/<slug>/SKILL.md`，按其步骤执行；管线级约定（资产映射、质量清单、增强链顺序）读 `knowledge/`，入口 `knowledge/INDEX.md`。

需要环境变量的技能（共 4 个变量）：

| 变量 | 涉及技能数 |
| --- | --- |
| `HEYGEN_API_KEY` | 5 |
| `ELEVENLABS_API_KEY` | 4 |
| `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION` | 2 |

## 六、OpenClaw CLI（真实安装）

| 项 | 值 |
| --- | --- |
| 版本 | OpenClaw 2026.11.3 (847611d) |
| 位置 | `tools/openclaw/`（项目内安装，非全局） |
| 运行时 | `tools/node24/`（v24.22.3，OpenClaw 要求 >=24.16.0 <25 或 >=26.1.0） |
| 状态目录 | `.openclaw/`（`OPENCLAW_STATE_DIR`，不写 `~/.openclaw`） |
| 工作区 | 项目根目录（`OPENCLAW_WORKSPACE_DIR`） |

为什么不是全局装：本机 `~/.local/node/lib/node_modules`、`~/.openclaw`、`~/Library` 等目录对当前执行环境均不可写（EPERM），只有项目目录可写。因此采用项目内安装 + 包装脚本，功能等价。

```bash
./openclaw.sh --version
./openclaw.sh skills list          # 147 项，其中 92 项来源 openclaw-workspace
./openclaw.sh skills info ffmpeg
```

验证结果：`skills list` 识别到 `openclaw-workspace` 来源技能 **92 个**，与 `skills/` 原生安装数量一致；49 个 `openclaw-bundled`、4 个 `openclaw-custodian`、2 个 `openclaw-extra` 为 CLI 自带。

注意：

- `openclaw skills update` 只跟踪 ClawHub 安装，**不跟踪**这种 git/本地来源；同步仍走本文档第三节的 `openmontage.sh`。
- 技能里声明了 `HEYGEN_API_KEY` / `ELEVENLABS_API_KEY` / `AZURE_SPEECH_KEY` 等的会显示 `needs setup`，属正常。
- **模型 provider 暂未接入**（2026-11-15 托托决定先不接）。CLI 与 92 个技能识别已就绪；`.openclaw/.env` 保留空位，需要时填 key 再 onboard 即可。
- Python 侧运行时依赖（`requirements.txt`）尚未安装，`tools.tool_registry` 直接导入会缺 `requests`；实际跑管线前需建 venv 并装依赖。`ffmpeg` 已在 `~/.local/bin/ffmpeg` 可用。
- 体积：`tools/` 约 846MB（Node 202MB + openclaw 依赖 644MB），项目合计约 1.0GB，会随项目目录同步。

## 七、环境限制说明

该仓库根目录没有 `SKILL.md`（技能在 `.agents/skills/*/SKILL.md`），因此 `openclaw skills install git:owner/repo` 这类仓库级安装会失败，只能逐技能安装；本次直接采用原生目录安装，OpenClaw 已能识别。


## 八、本机能力摸底（2026-11-15）

Python 运行时：`.venv`（3.9.6，按 `requirements.txt` 装齐，`pip check` 无冲突；`cryptography` 留在 48.0.1，49.x 需 Rust 编译故跳过）。`ffmpeg`/`ffprobe` 在 `~/.local/bin` 可用。

工具注册表实扫结果：**164 个工具 → 35 可用 / 2 降级 / 127 不可用**。

**可用（纯本地，无需 key）**

| 能力 | 工具 |
| --- | --- |
| 视频后期 | `video_compose` `video_stitch` `video_trimmer` `silence_cutter` `auto_reframe` `green_screen_processor` `green_screen_composite` `showcase_card` |
| 音频 | `audio_mixer` `audio_enhance` `audio_probe` `audio_energy` |
| 分析质检 | `scene_detect` `frame_sampler` `video_analyzer` `visual_qa` `composition_validator` |
| 字幕 | `subtitle_gen` `remotion_caption_burn`（后者需先在 `remotion-composer/` 跑 `npm install`） |
| 图形 / 3D | `threejs_world` `threejs_asset_catalog` `character_spec_generator` `svg_rig_builder` `pose_library_builder` `character_rig_renderer` `action_timeline_compiler` `character_animation_reviewer` |
| 录屏 | `cap_recorder` `screen_recorder` `screen_capture_selector` |
| 音乐检索 | `pixabay_music`（免版权曲库搜索） |
| 导出 | `export_bundle` |

**不可用（127 个，主因）**

- 全部 TTS：ElevenLabs / Azure / 豆包 / Fish / Cartesia / MiniMax 等 —— 缺 `*_API_KEY`
- 全部 AI 生图：FAL / BFL / Bria / Atlas / Replicate / Gemini 等 —— 缺 key
- 全部 AI 生视频：Kling / Sora / Veo / CogVideo 等 —— 缺 key
- 音乐生成：`fal_elevenlabs_music` 等 —— 缺 key（检索类 `pixabay_music` 可用）
- 语义检索切片：`clip_search` / `corpus_builder` —— 缺 `torch` + `transformers`
- 人脸/抠像增强：`face_restore` `bg_remove` —— 缺 `gfpgan` / `rembg`
- `diagram_gen` 降级：缺 `@mermaid-js/mermaid-cli`

**结论**：现在能产"组装型"视频（素材自备 → 剪辑/转场/字幕/混音/重构图/质检/导出），不能产"生成型"（AI 配音、AI 画面、AI 切片）。转写（ASR）当前也没有本地实现，`talking-head` / `podcast-repurpose` / `localization-dub` 需要先补 whisper 一类 ASR。

**冒烟验证**：`video_stitch` 实测通过 —— 两段 2s 测试片段 + 0.5s crossfade → 输出 3.52s 成片（`sandbox/smoke/stitched.mp4`）。

## 九、本地 ASR（faster-whisper，2026-11-15）

**为什么不用 pip 直接装**：当前执行容器是 VEFAAS Linux 沙箱，`/root`、`/tmp` 不跨调用持久，而云盘 `/Coze/Drive` 是 FUSE 挂载，写 venv 那种几万个小文件极慢（实测 400s 都装不完 numpy）。因此改成「本地盘装完 → 打成一个 tar 存云盘 → 用时还原」。

**结构**
```
asr/
  runtime.tar     881M   Python3.13 venv（faster-whisper 1.2.1 / ctranslate2 4.8.1）+ whisper-small 模型
  asr.sh          包装脚本：检测 /root/v 不存在则解包，再调 transcribe.py
  transcribe.py   转写 CLI，输出 srt / json / txt
```

**用法**
```bash
./asr/asr.sh 素材.mp4                          # 自动识别语言，输出 .srt + .json
./asr/asr.sh 录音.wav --language zh --format srt,txt,json
./asr/asr.sh 视频.mp4 --out out/ --compute-type int8_float32
```
- 首次调用解包 881M（约 26s），同容器内后续调用直接复用
- 模型 `Systran/faster-whisper-small`，int8 量化，来源 hf-mirror（HuggingFace 直连不通）
- 支持直接喂 mp4/mov，内部走 ffmpeg 抽音轨

**实测**：7.4s 英文语音（ffmpeg flite 合成）→ 12s 出结果，1 段，语言判定 en 0.99，文本准确。冷启动（含解包）总耗时 38s。

**性能参考**：1 核 CPU，`small` + int8 ≈ 1.6x 实时（10 分钟音频约 16 分钟）。要更快可换 `base`（体积约减 300M，中文精度下降）；要更准可换 `medium`（约 1.5G，1.9G 内存会吃紧）。

**降级说明**：容器内存 1.9G / 1 核，不适合 `large` 系列。GPU 不可用，纯 CPU 推理。
