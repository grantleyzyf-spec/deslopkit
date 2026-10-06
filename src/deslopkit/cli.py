"""命令行入口：`deslopkit audit|rewrite|rules|registers|version`。

设计目标：**可进 CI**——`audit --exit-code` 在有 high 严重度命中时返回非 0，
`rewrite --exit-code` 在闸门未通过时返回非 0，方便挂在 pre-commit / CI 上。
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from . import __version__
from .engine import audit, rewrite
from .fidelity import keep_terms_from
from .register import REGISTERS
from .report import audit_json, audit_markdown, rewrite_json, rewrite_markdown, write
from .rules import category_counts, load_rules

EXIT_OK = 0
EXIT_GATE_FAILED = 1
EXIT_USAGE = 2


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _collect_keep(args) -> List[str]:
    terms: List[str] = []
    if getattr(args, "keep", None):
        terms.extend(t.strip() for t in args.keep.split(",") if t.strip())
    for f in getattr(args, "keep_from", None) or []:
        terms.extend(keep_terms_from(_read(f)))
    seen = set()
    out = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def cmd_audit(args) -> int:
    keep = _collect_keep(args)
    md_parts, jsons, worst = [], [], []
    for path in args.files:
        text = _read(path)
        res = audit(text, register=args.register, keep=keep, include_quoted=args.include_quoted)
        worst.append(len(res.high_severity))
        md_parts.append(f"<!-- file: {path} -->\n" + audit_markdown(res, keep))
        jsons.append({"file": path, "audit": audit_json(res, keep)})
        if not args.quiet:
            print(f"{path}: {res.summary()}")
            for h in res.high_severity[:8]:
                print(f"  L{h.line} [{h.rule.id}] {h.rule.message} → {h.text[:50]}")
            if len(res.high_severity) > 8:
                print(f"  … 其余 {len(res.high_severity) - 8} 处 high 见报告")
    write(args.md, "\n\n".join(md_parts))
    if args.json:
        write(args.json, "[" + ",".join(x["audit"] for x in jsons) + "]")
    if args.md:
        print(f"[报告] {args.md}")
    if args.exit_code and sum(worst) > 0:
        return EXIT_GATE_FAILED
    return EXIT_OK


def cmd_rewrite(args) -> int:
    keep = _collect_keep(args)
    md_parts, jsons = [], []
    failed = False
    for path in args.files:
        text = _read(path)
        res = rewrite(text, register=args.register, keep=keep, passes=args.passes,
                      include_quoted=args.include_quoted)
        failed = failed or not res.gate.passed
        if args.out_dir:
            os.makedirs(args.out_dir, exist_ok=True)
            base = os.path.basename(path)
            stem, ext = os.path.splitext(base)
            out = os.path.join(args.out_dir, f"{stem}{args.suffix}{ext}")
            write(out, res.text)
            print(f"{path} → {out}")
        elif args.in_place:
            write(path, res.text)
            print(f"{path}（就地覆盖）")
        else:
            sys.stdout.write(res.text)
            if not res.text.endswith("\n"):
                sys.stdout.write("\n")
        print(f"  {res.summary()}")
        md_parts.append(f"<!-- file: {path} -->\n" + rewrite_markdown(res, keep))
        jsons.append(rewrite_json(res, keep))
        if not res.gate.passed:
            for c in res.gate.failures():
                print(f"  ❌ 闸门未过：{c.name}（{c.detail}）")
    if args.md:
        write(args.md, "\n\n".join(md_parts))
        print(f"[报告] {args.md}")
    if args.json:
        write(args.json, "[" + ",".join(jsons) + "]")
    if args.exit_code and failed:
        return EXIT_GATE_FAILED
    return EXIT_OK


def cmd_rules(args) -> int:
    rules = load_rules(lang=args.lang)
    if args.category:
        rules = [r for r in rules if r.category == args.category]
    counts = category_counts([])  # 占位，保持接口一致
    print(f"规则 {len(rules)} 条（lang={args.lang or 'all'}）")
    for r in rules:
        if args.verbose:
            print(f"  {r.id:14s} {r.lang} {r.category:16s} {r.severity:6s} {r.action:8s} {r.registers}")
        else:
            print(f"  {r.id:14s} {r.category:16s} {r.severity:6s} {r.message[:48]}")
    if args.json:
        import json as _json

        write(
            args.json,
            _json.dumps(
                [
                    {
                        "id": r.id, "lang": r.lang, "registers": list(r.registers),
                        "category": r.category, "severity": r.severity, "action": r.action,
                        "strategy": r.strategy, "pattern": r.pattern,
                        "replacement": r.replacement, "message": r.message, "fix_hint": r.fix_hint,
                    }
                    for r in rules
                ],
                ensure_ascii=False, indent=2,
            ),
        )
    _ = counts
    return EXIT_OK


def cmd_registers(args) -> int:
    for key, p in REGISTERS.items():
        print(f"{key:12s} {p.label}")
        print(f"             句长CV≥{p.sent_cv_min} 段长CV≥{p.para_cv_min} 短句占比≥{p.short_sent_ratio_min}")
        print(f"             自动改写={'/'.join(p.auto_fix) or '无'}｜仅提示={'/'.join(p.review_only) or '无'}｜闸门={'/'.join(p.gate)}")
        if p.notes:
            print(f"             备注：{p.notes}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="deslopkit",
        description="语域感知 + 保真护栏的中英文本去 AI 化工具（审计 / 改写 / 报告）",
    )
    ap.add_argument("--version", action="version", version=f"deslopkit {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    common = dict(files=None)

    a = sub.add_parser("audit", help="只读审计：指标 + 命中清单 + 参照带比对")
    a.add_argument("files", nargs="+")
    a.add_argument("--register", default="auto", choices=list(REGISTERS) + ["auto"])
    a.add_argument("--keep", help="逗号分隔的必保词")
    a.add_argument("--keep-from", action="append", help="从文件抽取必保词（可多次）")
    a.add_argument("--include-quoted", action="store_true", help="连引号/书名号内的命中一起报")
    a.add_argument("--md")
    a.add_argument("--json")
    a.add_argument("--quiet", action="store_true")
    a.add_argument("--exit-code", action="store_true", help="有 high 严重度命中时返回 1")
    a.set_defaults(fn=cmd_audit, **common)

    r = sub.add_parser("rewrite", help="确定性改写 + 保真护栏 + 交付闸门")
    r.add_argument("files", nargs="+")
    r.add_argument("-o", "--out-dir", help="输出目录（保留原文件名）")
    r.add_argument("--suffix", default=".deslop", help="输出文件名后缀，默认 .deslop")
    r.add_argument("--in-place", action="store_true")
    r.add_argument("--register", default="auto", choices=list(REGISTERS) + ["auto"])
    r.add_argument("--passes", type=int, default=3)
    r.add_argument("--keep")
    r.add_argument("--keep-from", action="append")
    r.add_argument("--include-quoted", action="store_true")
    r.add_argument("--md")
    r.add_argument("--json")
    r.add_argument("--exit-code", action="store_true", help="闸门未通过时返回 1")
    r.set_defaults(fn=cmd_rewrite, **common)

    rl = sub.add_parser("rules", help="列出规则库")
    rl.add_argument("--lang", choices=["zh", "en"])
    rl.add_argument("--category")
    rl.add_argument("--json")
    rl.add_argument("--verbose", action="store_true")
    rl.set_defaults(fn=cmd_rules)

    rg = sub.add_parser("registers", help="列出语域画像")
    rg.set_defaults(fn=cmd_registers)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.fn(args))
    except FileNotFoundError as exc:
        print(f"文件不存在：{exc}", file=sys.stderr)
        return EXIT_USAGE
    except BrokenPipeError:
        return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
