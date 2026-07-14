#!/usr/bin/env python3
"""
Critical SkillGovern — Batch Skill Review Script

Usage:
    python batch-review.py --path ./skills [--format hermes|claude-code|codex] [--csv report.csv]
    python batch-review.py --path ~/.hermes/skills --format hermes --fix

Scans skills directory, checks routing health, outputs diagnostic cards.
"""

import os
import sys
import csv
import yaml
import argparse
from datetime import datetime
from pathlib import Path


REQUIRED_SECTIONS = ['【触发场景】', '【输入特征】', '【输出目标】', '【不适用场景】']
TEMPLATE_RESIDUALS = ['.join', 'kw[:', '+ ,', "', '", "\n.join"]


def check_skill_routing(fm, desc):
    """Check a single skill's routing health."""
    issues = []
    
    has_4layer = all(s in desc for s in REQUIRED_SECTIONS)
    if not has_4layer:
        missing = [s for s in REQUIRED_SECTIONS if s not in desc]
        issues.append(('🔴', '缺少路由层', f'缺失: {", ".join(missing)}'))
    
    # Check template residuals
    for residual in TEMPLATE_RESIDUALS:
        if residual in desc:
            issues.append(('🔴', '模板残余', f'含 Python 字面量: "{residual}"'))
            break
    
    # Check Chinese ratio
    chinese_chars = sum(1 for c in desc if '\u4e00' <= c <= '\u9fff')
    if chinese_chars == 0 and len(desc.strip()) > 10:
        issues.append(('🔴', '全英触发', '描述中没有中文字符'))
    elif chinese_chars < 10 and len(desc.strip()) > 20:
        issues.append(('🟡', '中英混合', '中文字符过少'))
    
    # Check negative samples
    if '【不适用场景】' in desc:
        neg_section = desc.split('【不适用场景】')[-1].split('\n')[0]
        if len(neg_section.strip()) < 10:
            issues.append(('🟡', '弱负样本', f'负样本过短: "{neg_section.strip()[:30]}"'))
    
    # Check tags
    tags = fm.get('tags', [])
    if not tags:
        issues.append(('🟡', '缺少 tags', 'tags 为空'))
    elif isinstance(tags, list) and len(tags) == 1:
        issues.append(('🟢', '单层 tag', f'tags 只有一层: {tags}'))
    
    # Check related_skills
    rel = fm.get('related_skills', [])
    if not rel:
        issues.append(('🟢', '缺关联', 'related_skills 为空'))
    
    return issues


def scan_hermes_skills(base_path):
    """Scan Hermes Agent SKILL.md files."""
    results = []
    for root, dirs, files in os.walk(base_path):
        if 'SKILL.md' not in files:
            continue
        rel = os.path.relpath(root, base_path).replace(os.sep, '/')
        # Skip system dirs
        if any(p.startswith('.') for p in rel.split('/')):
            continue
        
        try:
            with open(os.path.join(root, 'SKILL.md')) as f:
                content = f.read()
            parts = content.split('---', 2)
            if len(parts) < 3:
                continue
            fm = yaml.safe_load(parts[1])
            desc = fm.get('description', '')
            name = fm.get('name', os.path.basename(root))
            
            issues = check_skill_routing(fm, desc)
            score = sum(1 for sev, _, _ in issues if sev == '🔴') * 3
            score += sum(1 for sev, _, _ in issues if sev == '🟡') * 2
            score += sum(1 for sev, _, _ in issues if sev == '🟢') * 1
            
            results.append({
                'name': name,
                'path': rel,
                'issues': issues,
                'score': score,
                'healthy': len([i for i in issues if '🔴' in i]) == 0
            })
            
        except Exception as e:
            results.append({
                'name': os.path.basename(root),
                'path': rel,
                'issues': [('🔴', '读取失败', str(e))],
                'score': 999,
                'healthy': False
            })
    
    return results


def print_report(results, auto_fix=False):
    """Print audit report."""
    total = len(results)
    healthy = sum(1 for r in results if r['healthy'])
    critical = sum(1 for r in results 
                   if any('🔴' in i[0] for i in r['issues']))
    
    print(f"""
=== Critical SkillGovern Report ===
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Total skills: {total}
Healthy: {healthy}/{total} ({healthy/total*100:.0f}%)
Critical issues: {critical}
===================================
""")
    
    # Print unhealthy skills
    for r in sorted(results, key=lambda x: -x['score']):
        if not r['issues']:
            continue
        sevs = [i[0] for i in r['issues']]
        max_sev = '🔴' if '🔴' in sevs else ('🟡' if '🟡' in sevs else '🟢')
        
        print(f"\n### {r['name']} [{max_sev}]")
        print(f"   Path: {r['path']}")
        for sev, issue, detail in r['issues']:
            print(f"   {sev} {issue}: {detail}")
        print()


def main():
    parser = argparse.ArgumentParser(description='Batch review skills routing health')
    parser.add_argument('--path', required=True, help='Path to skills directory')
    parser.add_argument('--format', default='hermes', choices=['hermes', 'claude-code', 'codex'])
    parser.add_argument('--fix', action='store_true', help='Auto-fix template residuals')
    parser.add_argument('--csv', help='Export report to CSV file')
    
    args = parser.parse_args()
    
    if args.format == 'hermes':
        results = scan_hermes_skills(args.path)
    else:
        print(f"Format '{args.format}' support coming soon")
        sys.exit(1)
    
    print_report(results)
    
    if args.csv:
        with open(args.csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Path', 'Severity', 'Issue', 'Detail'])
            for r in results:
                for sev, issue, detail in r['issues']:
                    writer.writerow([r['name'], r['path'], sev, issue, detail])
        print(f"Report exported to {args.csv}")


if __name__ == '__main__':
    main()
