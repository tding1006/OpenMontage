#!/usr/bin/env python3
"""
OpenMontage native skill installer / fork-bound sync tool.

Layout
------
skills-src/OpenMontage/   git clone of the FORK (sync source, never edited by hand)
skills/<slug>/            native installed skills (each with SKILL.md)
knowledge/                Layer-2 project conventions copied from repo skills/
.openmontage/state.json   installed commit + per-skill digests
reports/                  generated change reports (diff before reload)

Commands
--------
install           fresh native install from the checked-out commit
status            installed commit vs fork head, local drift
check             fetch ONLY the fork, diff against installed commit, write report
apply --yes       apply the last checked report (recopy changed skills + knowledge)
reload            rebuild INDEX.md / registry.json from what is installed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Resolve the project root from $OPENMONTAGE_ROOT, else the current directory.
# (The original copy lived at <root>/scripts/, this one lives outside the project.)
PROJECT_ROOT = Path(os.environ.get("OPENMONTAGE_ROOT") or Path.cwd()).resolve()
SRC_ROOT = PROJECT_ROOT / "skills-src" / "OpenMontage"
SKILLS_DIR = PROJECT_ROOT / "skills"
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
STATE_DIR = PROJECT_ROOT / ".openmontage"
STATE_FILE = STATE_DIR / "state.json"
REPORTS_DIR = PROJECT_ROOT / "reports"
TRASH_DIR = STATE_DIR / "trash"

FORK_URL = "https://github.com/tding1006/OpenMontage.git"
BRANCH = "main"

SRC_SKILLS = Path(".agents/skills")
SRC_KNOWLEDGE = Path("skills")


# ---------------------------------------------------------------- helpers
def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-C", str(SRC_ROOT), *args],
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{proc.stderr.strip()}")
    return proc.stdout.strip()


def normalize_remote(url: str) -> str:
    url = url.strip()
    if url.endswith("/"):
        url = url[:-1]
    if url.endswith(".git"):
        url = url[:-4]
    return url.lower()


def assert_fork_only() -> None:
    """Hard guard: the only remote we ever talk to is the user's fork."""
    remotes = git("remote").split()
    if "origin" not in remotes:
        raise SystemExit("origin remote is missing in skills-src/OpenMontage")
    url = git("remote", "get-url", "origin")
    if normalize_remote(url) != normalize_remote(FORK_URL):
        raise SystemExit(
            f"origin points to {url}\nrefusing: sync source must be the fork {FORK_URL}"
        )
    extra = [r for r in remotes if r != "origin"]
    if extra:
        print(f"[warn] extra remotes present and ignored: {', '.join(extra)}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dir_digest(path: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(path.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(path).as_posix().encode())
            h.update(b"\0")
            h.update(sha256_file(p).encode())
    return h.hexdigest()


ENV_JSON = re.compile(r'"env"\s*:\s*\[([^\]]*)\]')
ENV_LIST = re.compile(r"env:\s*\[([^\]]*)\]")
ENV_BLOCK = re.compile(r"env:\s*\n((?:\s*-\s*[A-Za-z0-9_]+\s*\n?)+)")


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}
    data: dict[str, str] = {}
    key = None
    buf: list[str] = []
    for line in lines[1:end]:
        if key is not None and (line.startswith((" ", "\t")) or not line.strip()):
            buf.append(line.strip())
            continue
        if key is not None:
            data[key] = " ".join(x for x in buf if x).strip()
            key, buf = None, []
        if ":" in line:
            k, v = line.split(":", 1)
            v = v.strip()
            if v in ("|", ">", "|-", ">-", ""):
                key = k.strip()
                buf = []
            else:
                data[k.strip()] = v
    if key is not None:
        data[key] = " ".join(x for x in buf if x).strip()
    return data


def extract_env(text: str) -> list[str]:
    found: list[str] = []
    for rx in (ENV_JSON, ENV_LIST):
        for m in rx.finditer(text):
            found += [x.strip().strip('"\'') for x in m.group(1).split(",") if x.strip()]
    for m in ENV_BLOCK.finditer(text):
        found += [x.strip("- \t") for x in m.group(1).splitlines() if x.strip()]
    seen, out = set(), []
    for item in found:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def first_sentence(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    if not text:
        return ""
    m = re.match(r"(.+?[.!?。])\s", text + " ")
    out = m.group(1) if m else text
    return out if len(out) <= limit else out[: limit - 1].rstrip() + "…"


def skill_entry(skill_dir: Path) -> dict:
    md = skill_dir / "SKILL.md"
    text = md.read_text(encoding="utf-8", errors="replace")
    fm = parse_frontmatter(text)
    return {
        "slug": skill_dir.name,
        "name": fm.get("name") or skill_dir.name,
        "description": " ".join((fm.get("description") or "").split()),
        "summary": first_sentence(fm.get("description") or ""),
        "requires_env": extract_env(text),
        "files": sum(1 for p in skill_dir.rglob("*") if p.is_file()),
        "digest": dir_digest(skill_dir),
        "source_path": f"{SRC_SKILLS.as_posix()}/{skill_dir.name}",
    }


def safe_remove(path: Path) -> None:
    """Never hard-delete: move aside so the previous version stays recoverable."""
    if not path.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = TRASH_DIR / stamp / path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dest))
    print(f"[trash] {path.name} -> {dest.relative_to(PROJECT_ROOT)}")


def copy_skill(slug: str) -> None:
    src = SRC_ROOT / SRC_SKILLS / slug
    dst = SKILLS_DIR / slug
    safe_remove(dst)
    shutil.copytree(src, dst)


def copy_knowledge(rel: str) -> None:
    src = SRC_ROOT / SRC_KNOWLEDGE / rel
    dst = KNOWLEDGE_DIR / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


# ---------------------------------------------------------------- state
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def snapshot_knowledge() -> dict[str, str]:
    out: dict[str, str] = {}
    src = SRC_ROOT / SRC_KNOWLEDGE
    for p in sorted(src.rglob("*.md")):
        out[p.relative_to(src).as_posix()] = sha256_file(p)
    return out


def write_registry(state: dict) -> None:
    skills = state.get("skills", {})
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    registry = {
        "source": state.get("fork_url"),
        "branch": state.get("branch"),
        "installed_commit": state.get("installed_commit"),
        "installed_at": state.get("installed_at"),
        "count": len(skills),
        "skills": skills,
    }
    (SKILLS_DIR / "registry.json").write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n"
    )

    lines = [
        "# OpenMontage · 已安装技能索引",
        "",
        f"- 同步源（fork）：{state.get('fork_url')}",
        f"- 分支：{state.get('branch')} · 已安装提交：`{str(state.get('installed_commit'))[:10]}`",
        f"- 安装时间：{state.get('installed_at')}",
        f"- 技能数：{len(skills)}（原生安装，SKILL.md 直读）",
        "",
        "| 技能 | 说明 | 依赖环境变量 | 文件数 |",
        "| --- | --- | --- | --- |",
    ]
    for slug in sorted(skills):
        s = skills[slug]
        desc = (s.get("summary") or "").replace("|", "\\|")
        envs = ", ".join(s.get("requires_env") or []) or "—"
        lines.append(f"| `{slug}` | {desc} | {envs} | {s.get('files', 0)} |")
    lines += [
        "",
        "---",
        "",
        "使用方式：需要某项能力时，直接读取 `skills/<slug>/SKILL.md`，按其步骤执行。",
        "Layer-2 项目约定（管线集成、质量清单）在 `knowledge/` 下，入口 `knowledge/INDEX.md`。",
        "",
    ]
    (SKILLS_DIR / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- commands
def cmd_install(_args) -> None:
    assert_fork_only()
    commit = git("rev-parse", "HEAD")
    skills_src = SRC_ROOT / SRC_SKILLS
    slugs = sorted(d.name for d in skills_src.iterdir() if (d / "SKILL.md").exists())

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

    for slug in slugs:
        copy_skill(slug)

    knowledge = snapshot_knowledge()
    for rel in knowledge:
        copy_knowledge(rel)

    state = {
        "fork_url": FORK_URL,
        "branch": BRANCH,
        "installed_commit": commit,
        "installed_at": now_iso(),
        "install_mode": "native-git",
        "skills": {slug: skill_entry(SKILLS_DIR / slug) for slug in slugs},
        "knowledge": knowledge,
    }
    save_state(state)
    write_registry(state)

    skipped = [
        d.name
        for d in skills_src.iterdir()
        if d.is_dir() and not (d / "SKILL.md").exists()
    ]
    print(f"installed {len(slugs)} skills + {len(knowledge)} knowledge files")
    print(f"commit {commit[:10]}  ({state['installed_at']})")
    if skipped:
        print(f"skipped (no SKILL.md): {', '.join(sorted(skipped))}")


def cmd_status(_args) -> None:
    assert_fork_only()
    state = load_state()
    if not state:
        print("not installed")
        return
    installed = state["installed_commit"]
    head = git("rev-parse", f"origin/{BRANCH}", check=False) or git("rev-parse", "HEAD")
    print(f"fork      : {FORK_URL}")
    print(f"installed : {installed[:10]}  ({state.get('installed_at')})")
    print(f"fork head : {head[:10]}")
    behind = git("rev-list", "--count", f"{installed}..{head}", check=False) or "?"
    print(f"pending   : {behind} commit(s) on {BRANCH}")

    drift = []
    for slug, meta in state.get("skills", {}).items():
        path = SKILLS_DIR / slug
        if not path.exists():
            drift.append(f"{slug} (missing)")
        elif dir_digest(path) != meta.get("digest"):
            drift.append(f"{slug} (local edits)")
    if drift:
        print(f"local drift: {len(drift)} skill(s) — {', '.join(drift[:10])}")
    else:
        print("local drift: none")


def _skill_slugs_at(commit: str) -> set[str]:
    out = git("ls-tree", "-r", "--name-only", commit, SRC_SKILLS.as_posix())
    slugs = set()
    for line in out.splitlines():
        parts = line.split("/")
        if len(parts) >= 4:
            slugs.add(parts[2])
    return slugs


def cmd_check(args) -> None:
    assert_fork_only()
    state = load_state()
    if not state:
        raise SystemExit("not installed yet — run: install")
    base = args.from_commit or state["installed_commit"]

    print(f"[fetch] origin {BRANCH} (fork only)")
    git("fetch", "--quiet", "origin", BRANCH)
    target = git("rev-parse", f"origin/{BRANCH}")

    if normalize_remote(git("remote", "get-url", "origin")) != normalize_remote(FORK_URL):
        raise SystemExit("remote mismatch")

    diff = git("diff", "--name-status", f"{base}..{target}")
    commits = git("log", "--oneline", "--no-decorate", f"{base}..{target}")

    changed_skills: dict[str, set[str]] = {}
    changed_knowledge: set[str] = set()
    other: list[str] = []

    for line in diff.splitlines():
        if not line.strip():
            continue
        status, path = (line.split("\t") + [""])[:2]
        parts = path.split("/")
        if path.startswith(f"{SRC_SKILLS.as_posix()}/") and len(parts) >= 4:
            changed_skills.setdefault(parts[2], set()).add(status[0])
        elif path.startswith(f"{SRC_KNOWLEDGE.as_posix()}/"):
            changed_knowledge.add(path[len(SRC_KNOWLEDGE.as_posix()) + 1 :])
        else:
            other.append(f"{status}\t{path}")

    old_slugs = _skill_slugs_at(base)
    new_slugs = _skill_slugs_at(target)
    added = sorted(new_slugs - old_slugs)
    removed = sorted(old_slugs - new_slugs)
    modified = sorted(s for s in changed_skills if s in new_slugs and s in old_slugs)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = REPORTS_DIR / f"sync-{stamp}.md"

    lines = [
        f"# OpenMontage 同步检查 · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"- 同步源：`{FORK_URL}`（仅 fork，未拉取 upstream）",
        f"- 已安装提交：`{base[:10]}`",
        f"- fork 最新：`{target[:10]}`",
        f"- 待合入提交：{len(commits.splitlines())}",
        "",
    ]
    if commits:
        lines += ["## 提交", "", "```", commits, "```", ""]

    if not (added or removed or modified or changed_knowledge):
        lines += ["## 结论", "", "无技能改动，已是最新。", ""]
    else:
        lines += ["## 技能变更", ""]
        for slug in added:
            lines.append(f"- 新增 `{slug}`")
        for slug in removed:
            lines.append(f"- 移除 `{slug}`（将移入回收目录，不硬删除）")
        for slug in modified:
            flags = sorted(changed_skills[slug])
            touched = sorted(
                p.split("/", 3)[-1]
                for p in diff.splitlines()
                if p.split("\t")[-1].startswith(f"{SRC_SKILLS.as_posix()}/{slug}/")
            )
            md_changed = "SKILL.md" in touched
            note = "（SKILL.md 有改动，需重读）" if md_changed else ""
            lines.append(
                f"- 修改 `{slug}`：{len(touched)} 个文件，{''.join(flags)} {note}"
            )
        if changed_knowledge:
            lines += ["", "## Layer-2 知识文件变更", ""]
            lines += [f"- `{p}`" for p in sorted(changed_knowledge)]
        if other:
            lines += ["", "## 其他仓库改动（不安装，仅供参考）", ""]
            lines += [f"- `{p}`" for p in other[:40]]
            if len(other) > 40:
                lines.append(f"- …共 {len(other)} 项")

    lines += [
        "",
        "---",
        "",
        "确认后执行：`python3 scripts/openmontage.py apply --yes`（重载索引）",
        "",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")
    (REPORTS_DIR / "latest.md").write_text("\n".join(lines), encoding="utf-8")

    summary = {
        "base": base[:10],
        "target": target[:10],
        "commits": len(commits.splitlines()),
        "added": added,
        "removed": removed,
        "modified": modified,
        "knowledge": sorted(changed_knowledge),
        "other": len(other),
        "report": str(report.relative_to(PROJECT_ROOT)),
    }
    (STATE_DIR / "pending.json").write_text(
        json.dumps({"target": target, "base": base, "summary": summary}, indent=2)
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def cmd_apply(args) -> None:
    assert_fork_only()
    state = load_state()
    pending_file = STATE_DIR / "pending.json"
    if not pending_file.exists():
        raise SystemExit("no pending check — run: check")
    pending = json.loads(pending_file.read_text())
    if not args.yes:
        print("refusing without --yes: show the report to the user first")
        print(json.dumps(pending["summary"], indent=2, ensure_ascii=False))
        return

    base, target = pending["base"], pending["target"]
    print(f"[apply] {base[:10]} -> {target[:10]} (fork only)")
    git("checkout", "--quiet", BRANCH)
    git("reset", "--hard", "--quiet", target)

    diff = git("diff", "--name-status", f"{base}..{target}")
    old_slugs = _skill_slugs_at(base)
    new_slugs = _skill_slugs_at(target)

    touched_slugs = {
        line.split("/")[2]
        for line in diff.splitlines()
        if line.split("\t")[-1].startswith(f"{SRC_SKILLS.as_posix()}/")
        and len(line.split("/")) > 2
    }

    for slug in sorted(touched_slugs | (old_slugs - new_slugs)):
        if slug in new_slugs and (SRC_ROOT / SRC_SKILLS / slug / "SKILL.md").exists():
            copy_skill(slug)
        elif slug not in new_slugs:
            safe_remove(SKILLS_DIR / slug)

    knowledge = snapshot_knowledge()
    for rel in sorted(knowledge):
        if state.get("knowledge", {}).get(rel) != knowledge[rel]:
            copy_knowledge(rel)
    for rel in sorted(set(state.get("knowledge", {})) - set(knowledge)):
        safe_remove(KNOWLEDGE_DIR / rel)

    state["skills"] = {
        d.name: skill_entry(d)
        for d in sorted(SKILLS_DIR.iterdir())
        if d.is_dir() and (d / "SKILL.md").exists()
    }
    state["knowledge"] = knowledge
    state["installed_commit"] = target
    state["installed_at"] = now_iso()
    save_state(state)
    write_registry(state)

    reloaded = sorted(s for s in touched_slugs if s in new_slugs)
    pending_file.unlink(missing_ok=True)
    print(f"[apply] done at {target[:10]}")
    print(f"[reload] {len(reloaded)} skill(s) updated: {', '.join(reloaded) or '—'}")
    print("[reload] 索引已重建：skills/INDEX.md · skills/registry.json")


def cmd_reload(_args) -> None:
    state = load_state()
    if not state:
        raise SystemExit("not installed yet — run: install")
    state["skills"] = {
        d.name: skill_entry(d)
        for d in sorted(SKILLS_DIR.iterdir())
        if d.is_dir() and (d / "SKILL.md").exists()
    }
    save_state(state)
    write_registry(state)
    print(f"[reload] index rebuilt · {len(state['skills'])} skills")


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenMontage native installer / sync")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("install").set_defaults(func=cmd_install)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("reload").set_defaults(func=cmd_reload)

    p_check = sub.add_parser("check")
    p_check.add_argument("--from-commit", help="diff from this commit (default: installed)")
    p_check.set_defaults(func=cmd_check)

    p_apply = sub.add_parser("apply")
    p_apply.add_argument("--yes", action="store_true")
    p_apply.set_defaults(func=cmd_apply)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
