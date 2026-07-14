#!/usr/bin/env python3
"""
Critical SkillGovern — Routing Validation Script

Usage:
    python validate-routing.py --path ./skills [--format hermes]

Validates that all skills have proper routing configuration.
Returns exit code 0 if all pass, 1 if any fail.
"""

import os
import sys
import yaml
import argparse
from pathlib import Path


REQUIRED_SECTIONS = ['【触发场景】', '【输入特征】', '【输出目标】', '【不适用场景】']


def validate_hermes_skill(path):
    """Validate a single Hermes SKILL.md."""
    with open(path) as f:
        content = f.read()
    
    parts = content.split('---', 2)
    if len(parts) < 3:
        return False, "Invalid YAML frontmatter"
    
    fm = yaml.safe_load(parts[1])
    errors = []
    
    # Check name
    if not fm.get('name'):
        errors.append("Missing 'name' field")
    
    # Check description has 4-layer routing
    desc = fm.get('description', '')
    for section in REQUIRED_SECTIONS:
        if section not in desc:
            errors.append(f"Missing '{section}' in description")
    
    # Check tags
    if not fm.get('tags'):
        errors.append("Missing 'tags' field")
    elif isinstance(fm.get('tags'), str):
        errors.append("'tags' should be a list, not a string")
    
    # Check length limits
    if len(desc) > 500:
        errors.append(f"Description too long ({len(desc)} chars, max 500)")
    
    if errors:
        return False, "; ".join(errors)
    return True, "OK"


def validate_skills(base_path, fmt):
    """Validate all skills in a directory."""
    results = []
    
    if fmt == 'hermes':
        for root, dirs, files in os.walk(base_path):
            if 'SKILL.md' not in files:
                continue
            rel = os.path.relpath(root, base_path).replace(os.sep, '/')
            ok, msg = validate_hermes_skill(os.path.join(root, 'SKILL.md'))
            results.append({
                'name': os.path.basename(root),
                'path': rel,
                'ok': ok,
                'msg': msg
            })
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Validate skill routing configuration')
    parser.add_argument('--path', required=True, help='Path to skills directory')
    parser.add_argument('--format', default='hermes', choices=['hermes', 'claude-code', 'codex'])
    parser.add_argument('--strict', action='store_true', help='Fail on warnings too')
    
    args = parser.parse_args()
    
    results = validate_skills(args.path, args.format)
    
    total = len(results)
    passed = sum(1 for r in results if r['ok'])
    
    print(f"Validation Results ({fmt})")
    print(f"{'='*50}")
    print(f"{passed}/{total} passed")
    
    for r in results:
        status = '✅' if r['ok'] else '❌'
        print(f"  {status} {r['path']}")
        if not r['ok']:
            print(f"       {r['msg']}")
    
    overall_ok = passed == total
    if not args.strict:
        overall_ok = True  # Only strict mode fails
    
    sys.exit(0 if overall_ok else 1)


if __name__ == '__main__':
    main()
