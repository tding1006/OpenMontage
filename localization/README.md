# localization / coze-vefaas

OpenMontage 在 **无 API key、单核 1.9G 内存、FUSE 云盘、容器不持久** 环境下的本地化补丁层。

这一层**只新增文件，不改动仓库原有任何内容** —— `.agents/skills/`、`skills/`、`lib/`、`tools/`、`pipeline_defs/` 全部保持上游原样，因此不会和后续同步冲突。

```
localization/coze-vefaas/
├── bin/
│   ├── openmontage.py    原生安装 + fork 绑定同步（install / status / check / apply / reload）
│   ├── openmontage.sh    上面那个的包装脚本
│   └── openclaw.sh       项目内 OpenClaw CLI 包装（家目录不可写时的绕法）
├── asr/
│   ├── transcribe.py     本地 ASR CLI（faster-whisper，CPU，零 key）
│   ├── asr.sh            包装脚本：按需还原运行时后转写
│   └── build-runtime.sh  重新构建 asr/runtime.tar（换机器时用）
├── docs/
│   └── SETUP.md          完整安装记录 + 能力摸底 + 环境限制（原始记录，未删改）
└── examples/
    └── blackhole-explainer/   一次 animated-explainer 管线的完整 artifact 示例
```

---

## 一、目标环境的三条硬约束

这三条决定了下面所有设计：

1. **家目录不持久** —— `/root`、`/tmp` 每次 bash 调用都可能重置，只有网络盘持久。
2. **网络盘极慢** —— FUSE 挂载，顺序读写约 40MB/s，但**几万个小文件会卡死**（`pip install numpy` 400s 装不完）。
3. **外网受限** —— `pypi.org`、`huggingface.co` 直连不通；可用的是 `mirrors.ivolces.com`、阿里/腾讯 pypi 镜像、`hf-mirror.com`。

对策：**能在本地盘做的都在本地盘做，产物打成单个文件放网络盘，用时还原。**

---

## 二、快速开始

```bash
# 0. 准备目录（项目根 = 下面命令的当前目录）
mkdir -p skills-src skills knowledge .openmontage reports

# 1. 检出 fork（唯一同步源）
git clone https://github.com/tding1006/OpenMontage.git skills-src/OpenMontage

# 2. 原生安装（把 92 个 SKILL.md + 158 个 Layer-2 知识文件铺到项目里）
OPENMONTAGE_ROOT=$PWD python3 localization/coze-vefaas/bin/openmontage.py install

# 3. 本地 ASR（可选，解锁转写/字幕）
bash localization/coze-vefaas/asr/build-runtime.sh     # 首次构建，约 10 分钟
./asr/asr.sh 素材.mp4                                   # 之后每次直接用
```

同步语义（`openmontage.py` 的核心约定）：

| 命令 | 行为 |
| --- | --- |
| `status` | 已安装提交 vs fork head；digest 比对列出被手改的技能 |
| `check` | **只** fetch fork，diff 写进 `reports/`，安装区零改动 |
| `apply --yes` | 人工确认后才执行：更新检出 → 重装变更技能 → 重建索引 |
| `reload` | 仅重建 `INDEX.md` / `registry.json` |

`origin` 会被硬校验成 fork 地址，不一致直接拒绝；**不 fetch 任何其他 remote**；被替换/移除的技能移进 `.openmontage/trash/`，不硬删除。

---

## 三、能力摸底：164 个工具 → 35 可用 / 2 降级 / 127 不可用

**可用（纯本地，零 key）**

| 能力 | 工具 |
| --- | --- |
| 视频后期 | `video_compose` `video_stitch` `video_trimmer` `silence_cutter` `auto_reframe` `green_screen_processor` `green_screen_composite` `showcase_card` |
| 音频 | `audio_mixer` `audio_enhance` `audio_probe` `audio_energy` |
| 分析质检 | `scene_detect` `frame_sampler` `video_analyzer` `visual_qa` `composition_validator` |
| 字幕 | `subtitle_gen` `remotion_caption_burn`（需先跑 `npm install`） |
| 图形 / 3D | `threejs_world` `threejs_asset_catalog` `character_spec_generator` `svg_rig_builder` `pose_library_builder` `character_rig_renderer` `action_timeline_compiler` `character_animation_reviewer` |
| 录屏 | `cap_recorder` `screen_recorder` `screen_capture_selector` |
| 音乐检索 | `pixabay_music` |
| 导出 | `export_bundle` |

**不可用（127 个）**：全部 TTS（ElevenLabs / Azure / 豆包 / Fish / Cartesia / MiniMax）、全部 AI 生图（FAL / BFL / Bria / Atlas / Replicate / Gemini）、全部 AI 生视频（Kling / Sora / Veo / CogVideo）、音乐生成、`clip_search`（缺 torch）、`face_restore` / `bg_remove`（缺 gfpgan / rembg）、`diagram_gen` 降级（缺 mermaid-cli）。共 4 个环境变量能解锁一部分：`HEYGEN_API_KEY`（5 个技能）、`ELEVENLABS_API_KEY`（4）、`AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION`（2）。

**结论**：能产「组装型」视频（素材自备 → 剪辑/转场/字幕/混音/重构图/质检/导出），不能产「生成型」。

---

## 四、无 key 环境下的分工原则

这是跑通管线的关键取舍，不是绕路：

- **生成类**（AI 画面、配音、配乐）→ 交给宿主平台的原生生成工具，OpenMontage 侧只声明 `source_tool` 记录来源。
- **组装 / 质检类** → **必须**走 OpenMontage 原生：`video_compose` 的 render、ASS 字幕烧制、`audio_mixer`、`final_review`。
- **artifact 契约不变** —— `asset_manifest` / `edit_decisions` / `render_report` / `final_review` 仍按 `schemas/artifacts/*.schema.json` 写，管线结构、质量门、返工机制一个不少。

也就是说：**只有"谁来生成素材"被替换，"怎么组装和验收"完全是原生的。**

---

## 五、本地 ASR

`asr/transcribe.py` 基于 faster-whisper（1.2.1 / ctranslate2 4.8.1），int8 量化，纯 CPU：

```bash
./asr/asr.sh 素材.mp4                                  # 自动识别语言 → .srt + .json
./asr/asr.sh 录音.wav --language zh --format srt,txt,json
./asr/asr.sh 视频.mp4 --out out/ --compute-type int8_float32
```

- 直接吃 mp4/mov，内部走 ffmpeg 抽音轨
- 默认模型 `Systran/faster-whisper-small`（int8 下 464MB）
- **性能**：1 核 ≈ 1.6x 实时（10 分钟音频约 16 分钟）。要快换 `base`（中文精度下降），要准换 `medium`（1.5G，1.9G 内存会吃紧）。`large` 系列别想。
- 实测：7.4s 英文语音 → 12s 出结果，语言判定 en 0.99；冷启动（含解包）38s

**它补的是哪条链**：`talking-head` / `podcast-repurpose` / `localization-dub` 三条管线都依赖转写，之前完全空缺。

---

## 六、踩过的坑（都是实测）

1. **`subtitles.style` 必须是对象**。传字符串会让 `video_compose` 抛 `'str' object has no attribute 'items'` —— 源码里是 `.get("style", {}).items()`。
2. **不传 `profile` 就是横屏**。要竖屏必须显式 `profile: "youtube_shorts"`（`lib/media_profiles.py` 里还有 `instagram_reels` / `tiktok` / `cinematic` 等）。
3. **`force_style` 的 FontSize 会被 libass 按 PlayRes 放大**。SRT 默认 `PlayResY=288`，实测放大 **≈2.81 倍**（58 → 163px，字幕糊满屏）。要精确控字号，自己生成带 `PlayResX: 1080 / PlayResY: 1920` 的 ASS 再烧。
4. **别在已经烧过字幕的成片上再烧一遍**。看起来"没变化"，实际是两层叠着。改字幕要从原始分镜重渲染。
5. **`ffmpeg -ss` 放在 `-i` 前会把时间戳归零**，导致第一条字幕 cue（0.4s 起）抽帧时看不到。验证烧字幕请加 `-copyts`。
6. **`tar` 打绝对路径会吃掉前导 `/`**。`tar -cf x.tar /root/v` 成员是 `root/v`；解包必须 `-C /`，用 `-C /root` 会得到 `/root/root/v`。
7. **别在网络盘上建 venv**。见第一节第 2 条。

---

## 七、示例：`examples/blackhole-explainer/`

一次完整的 `animated-explainer` 八阶段产物（20 秒竖屏科普短片，**不含** 9.1MB 成片本身）：

| 文件 | 说明 |
| --- | --- |
| `PROJECT.md` | 全流程记录：文案、时间轴、资产清单、八阶段执行表、自检结果、偏离说明 |
| `asset_manifest.json` | 6 个资产：3 段 AI 画面 + 旁白 + 铺底音乐 + 字幕 |
| `edit_decisions.json` | 3 个 cut（7.04 + 7.04 + 6.73 = 20.81s）、音频 ducking、ASS 字幕样式 |
| `zh.srt` | ASR 对齐 + 人工校错后的字幕（8 条） |

最终成片：1080×1920 / 20.87s / 30fps / H.264+AAC，`final_review.status = pass`，时长漂移 0.3%，字幕覆盖 100%，音频峰值 −2.3dB 无削波。

---

## 八、边界

- 这一层**不提供**任何 API key，也不绕过任何 provider 的鉴权。
- `openclaw.sh` 依赖项目内自装的 `tools/node24` + `tools/openclaw`（体积约 846MB，不随仓库分发），没有就先跑安装步骤。
- `asr/runtime.tar` 是构建产物（881MB），**不进仓库**；用 `asr/build-runtime.sh` 重建。
