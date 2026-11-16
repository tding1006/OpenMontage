# 黑洞 20 秒科普短片 — OpenMontage 制作记录

**成片**：`render/blackhole_20s.mp4` · 1080×1920 (9:16) · 20.87s · 30fps · H.264 + AAC 48k 立体声
**管线**：`animated-explainer` v2.0（OpenMontage，EP 模式）
**Playbook**：clean-professional
**制作日期**：2026-11-15

---

## 一、文案（script）

> 黑洞不是洞，是被压塌的时空。
> 一颗大质量恒星烧完燃料，核心在瞬间向内崩塌。
> 引力强到连光都拐弯，越过那条边界，什么都逃不出来。
> 靠近它，时间会变慢。
> 我们看不见黑洞，只能看见它照亮的光。

85 字，旁白实测 20.808s，语速约 4.1 字/秒。

## 二、时间轴（edit_decisions）

| 段落 | 时间 | 画面 | 字幕 |
| --- | --- | --- | --- |
| 1 | 0.0–7.04 | 蓝色巨恒星脉动 → 向内坍缩 | 黑洞不是洞，是被压塌的时空 |
| 2 | 7.04–14.08 | 吸积盘高速旋转 + 光子环 + 引力透镜 | 一颗大质量恒星烧完燃料／核心在瞬间向内崩塌／引力强到连光都拐弯 |
| 3 | 14.08–20.81 | 贴近视界，光线被拉成丝带吞没 | 越过那条边界什么都逃不出来／靠近它时间会变慢／我们看不见黑洞／只能看见它照亮的光 |

硬切保证时长精确（三段 7.04 + 7.04 + 6.73 = 20.81s），与旁白 20.808s 对齐，漂移 0.3%。

## 三、资产清单（asset_manifest）

| ID | 类型 | 来源 | 说明 |
| --- | --- | --- | --- |
| vid-1/2/3 | 视频 | `generate_video` · seedance2.0_pro | 3×7.04s，720×1280 原生，9:16 |
| narration-main | 旁白 | `generate_audio` | 中文男声纪录片腔，20.808s |
| music-bg | 音乐 | `generate_music` | 低频环境铺底，121.9s 裁到 20.8s，音量 0.12 + 侧链压低 |
| subs-zh | 字幕 | ASR 对齐 + 人工校正 | faster-whisper 出时间戳，「使空」→「时空」修正 |

## 四、执行记录（EP 八阶段）

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| research | 通过 | 检索中科院高能所/NASA/GSFC 等来源，确认：大质量恒星（≥8–10 M☉）燃料耗尽 → 核心坍缩 → 超新星 → 残核 >3 M☉ 则无简并压支撑 → 形成黑洞；视界处逃逸速度 = 光速；外部观测者看到的时间无限变慢 |
| proposal | 通过 | 单概念执行（用户已指定选题与时长），目标 20s / 9:16 / 中文旁白 |
| script | 通过 | 85 字 / 5 句，约 20.8s，符合 ±10% |
| scene_plan | 通过 | 3 个视觉场景，无连续同类型 |
| assets | 通过（有替代） | 见「五、偏离说明」 |
| edit | 通过 | 3 段硬切 + 音频分层 + 字幕 8 条 |
| compose | 通过 | `video_compose` render → final_review status=pass |
| publish | 通过 | 封面 `render/cover.jpg`，SRT/ASS 字幕，本记录 |

**compose 自检结果**：容器有效 ✓ · 时长漂移 0.3% ✓ · 黑帧无 ✓ · 旁白+音乐均在 ✓ · 无削波（峰值 -2.3 dB）✓ · 字幕覆盖率 100% ✓ · 运行时未偷换 ✓

## 五、偏离说明（重要）

OpenMontage 原生的 `tts_selector` / `image_selector` / `video_selector` 在本机不可用 —— 缺各家 API key（ElevenLabs / FAL / Kling 等）。因此：

- **生成类资产**改由平台工具产出：`generate_video`（seedance2.0_pro）、`generate_audio`、`generate_music`
- **组装类环节**全部走 OpenMontage 原生工具：`video_compose`（render）、字幕 ASS 烧制、`final_review` 质检
- 管线结构、artifact schema、EP 质检门全部保留

## 六、可复现命令

```bash
# 组装（需先装 OpenMontage 依赖）
cd skills-src/OpenMontage && python3 -m venv /root/om && /root/om/bin/pip install -r requirements.txt
/root/om/bin/python -c "
import sys,json; sys.path.insert(0,'.')
from tools.tool_registry import ToolRegistry
r=ToolRegistry(); r.discover()
b='/Coze/Drive/Video_Maker/projects/blackhole-explainer'
print(r._tools['video_compose'].execute({'operation':'render',
  'edit_decisions':json.load(open(f'{b}/artifacts/edit_decisions.json')),
  'asset_manifest':json.load(open(f'{b}/artifacts/asset_manifest.json')),
  'profile':'youtube_shorts','output_path':f'{b}/render/blackhole_20s.mp4'}))
"
```

## 七、已知可改进点

1. 首段 7 秒是「蓝色恒星」，视觉上更像行星，黑洞形象出现偏晚 —— 若重做可把首段缩到 4s，让吸积盘更早出现
2. 字幕字号 68（PlayRes 1080×1920），如需更大可调到 76
3. 音乐 121.9s 只用了前 20.8s，若换更短的环境音可省生成开销
4. 旁白 20.808s 与画面 20.81s 对齐良好，但第 8 条字幕结束在 20.60s，末尾留 0.2s 余量
