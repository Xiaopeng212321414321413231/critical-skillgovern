import { readFile, readdir } from 'node:fs/promises'
import { join, extname } from 'node:path'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'dsh-skillgovern'
export const inject = ['tools']

const SKIP_DIRS = new Set([
  '.git', '.hermes', 'node_modules', '.venv', '__pycache__',
  'dist', 'build', '.archive', '.hub', 'scripts', 'logs', 'input'
])

function hasChinese(text) {
  return /[\u4e00-\u9fff]/.test(text)
}

function countChinese(text) {
  return (text.match(/[\u4e00-\u9fff]/g) || []).length
}

function extractFrontmatter(content) {
  const match = content.match(/^---\n([\s\S]*?)\n---/)
  if (!match) return null
  const fm = {}
  for (const line of match[1].split('\n')) {
    const idx = line.indexOf(':')
    if (idx === -1) continue
    const key = line.slice(0, idx).trim()
    let val = line.slice(idx + 1).trim()
    if (val.startsWith('|')) val = val.slice(1).trim()
    if (val.startsWith('[') && val.endsWith(']')) {
      val = val.slice(1, -1).split(',').map(s => s.trim().replace(/^['"]|['"]$/g, ''))
    }
    fm[key] = val
  }
  return fm
}

function detectFormat(content) {
  if (content.match(/^---\n[\s\S]*?\n---/) && /name:/.test(content)) return 'hermes'
  if (/When the user/i.test(content)) return 'claude-code'
  if (/You are/i.test(content) && /Instructions/i.test(content)) return 'codex'
  return 'generic'
}

function diagnoseSkill(content, filename) {
  const issues = []
  const format = detectFormat(content)
  const fm = extractFrontmatter(content)
  const desc = fm?.description || content.split('\n').slice(0, 5).join('\n')

  const layers = ['\u3010\u89e6\u53d1\u573a\u666f\u3011', '\u3010\u8f93\u5165\u7279\u5f81\u3011', '\u3010\u8f93\u51fa\u76ee\u6807\u3011', '\u3010\u4e0d\u9002\u7528\u573a\u666f\u3011']
  for (const layer of layers) {
    if (!desc.includes(layer)) {
      issues.push({ severity: 'critical', issue: `\u7f3a\u5c11\u8def\u7531\u5c42: ${layer}`, suggestion: `\u5728 description \u4e2d\u6dfb\u52a0 ${layer} \u6bb5\u843d` })
    }
  }

  if (/\.\w+\(|kw\[:|\.join\(|\.strip\(\)/.test(desc)) {
    issues.push({ severity: 'critical', issue: '\u6a21\u677f\u6b8b\u4f59: \u68c0\u6d4b\u5230 Python \u5b57\u9762\u91cf', suggestion: '\u5220\u9664 .join()\u3001kw[: \u7b49\u4ee3\u7801\u7247\u6bb5\uff0c\u7528\u81ea\u7136\u8bed\u8a00\u66ff\u4ee3' })
  }

  if (desc.length > 10 && !hasChinese(desc)) {
    issues.push({ severity: 'critical', issue: '\u5168\u82f1\u89e6\u53d1: \u63cf\u8ff0\u4e2d\u65e0\u4e2d\u6587\u5b57\u7b26', suggestion: '\u5c06\u89e6\u53d1\u573a\u666f\u548c\u5173\u952e\u8bcd\u7ffb\u8bd1\u4e3a\u7528\u6237\u8bed\u8a00' })
  } else if (hasChinese(desc) && countChinese(desc) < desc.length * 0.1) {
    issues.push({ severity: 'warning', issue: '\u4e2d\u82f1\u6df7\u5408: \u4e2d\u6587\u5b57\u7b26\u5360\u6bd4\u8fc7\u4f4e', suggestion: '\u7edf\u4e00\u63cf\u8ff0\u8bed\u8a00\uff0c\u51cf\u5c11\u4e0d\u5fc5\u8981\u7684\u82f1\u6587\u6bb5\u843d' })
  }

  const negMatch = desc.match(/\u3010\u4e0d\u9002\u7528\u573a\u666f\u3011([\s\S]*?)(\u3010|$)/)
  if (negMatch) {
    const neg = negMatch[1].trim()
    if (neg.length < 15) {
      issues.push({ severity: 'warning', issue: '\u5f31\u8d1f\u6837\u672c: \u4e0d\u9002\u7528\u573a\u666f\u63cf\u8ff0\u8fc7\u77ed', suggestion: '\u5217\u51fa 2+ \u79cd\u8bef\u89e6\u60c5\u51b5\uff0c\u5e76\u6307\u5411\u5177\u4f53\u66ff\u4ee3\u6280\u80fd' })
    }
    if (!neg.includes('\u2192') && !neg.includes('\u4f7f\u7528') && !neg.includes('\u5e94') && neg.length >= 15) {
      issues.push({ severity: 'warning', issue: '\u8d1f\u6837\u672c\u65e0\u66ff\u4ee3\u6307\u5411', suggestion: '\u5728\u4e0d\u9002\u7528\u7684\u573a\u666f\u540e\uff0c\u7528 \u2192 \u6307\u5411\u66ff\u4ee3\u6280\u80fd' })
    }
  }

  if (fm) {
    const tags = fm.tags
    if (!tags || (Array.isArray(tags) && tags.length === 0)) {
      issues.push({ severity: 'warning', issue: '\u7f3a\u5c11 tags', suggestion: '\u6dfb\u52a0\u53cc\u5c42\u6807\u7b7e tags: [\u5927\u7c7b, \u5c0f\u7c7b]' })
    } else if (Array.isArray(tags) && tags.length === 1) {
      issues.push({ severity: 'info', issue: '\u5355\u5c42 tag', suggestion: '\u6269\u5c55\u4e3a\u53cc\u5c42: tags: [\u5927\u7c7b, \u5c0f\u7c7b]' })
    }
    if (!fm.related_skills || (Array.isArray(fm.related_skills) && fm.related_skills.length === 0)) {
      issues.push({ severity: 'info', issue: '\u7f3a\u5c11 related_skills', suggestion: '\u5173\u8054\u4e0a\u4e0b\u6e38\u6216\u540c\u7ea7\u522b\u6280\u80fd' })
    }
  }

  const critical = issues.filter(i => i.severity === 'critical').length
  const warnings = issues.filter(i => i.severity === 'warning').length
  const infos = issues.filter(i => i.severity === 'info').length
  const health = critical === 0 ? (warnings === 0 ? 'healthy' : 'needs-attention') : 'unhealthy'

  return { file: filename, format, health, summary: { critical, warnings, infos }, issues }
}

async function walkSkillsDir(dir) {
  const results = []
  const entries = await readdir(dir, { withFileTypes: true })
  for (const entry of entries) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name) || entry.name.startsWith('.')) continue
      results.push(...await walkSkillsDir(full))
    } else if (extname(entry.name) === '.md') {
      const content = await readFile(full, 'utf-8')
      results.push({ path: full, name: entry.name, content })
    }
  }
  return results
}

function formatDiagnosticCard(result) {
  const icon = { critical: '\ud83d\udd34', warning: '\ud83d\udfe1', info: '\ud83d\udfe2' }
  const healthIcon = { healthy: '\u2705', 'needs-attention': '\u26a0\ufe0f', unhealthy: '\u274c' }
  let out = `## ${result.file} \u8bca\u65ad\u5361\n`
  out += `**\u683c\u5f0f**: ${result.format} | **\u5065\u5eb7\u5ea6**: ${healthIcon[result.health]} ${result.health}\n\n`
  if (result.issues.length === 0) {
    out += '\u8def\u7531\u5065\u5eb7\uff0c\u65e0\u9700\u4fee\u590d\u3002\n'
    return out
  }
  out += '| \u4e25\u91cd\u5ea6 | \u95ee\u9898 | \u5efa\u8bae |\n|--------|------|------|\n'
  for (const i of result.issues) {
    out += `| ${icon[i.severity]} ${i.severity} | ${i.issue} | ${i.suggestion} |\n`
  }
  out += `\n**\u7edf\u8ba1**: \ud83d\udd34 ${result.summary.critical} | \ud83d\udfe1 ${result.summary.warnings} | \ud83d\udfe2 ${result.summary.infos}\n`
  return out
}

export function apply(ctx) {
  ctx.tools.register(defineTool({
    name: 'skill-diagnose',
    description: '\u8bca\u65ad\u5355\u4e2a\u6280\u80fd\u6587\u4ef6\u7684\u8def\u7531\u5065\u5eb7\u5ea6\u3002\u68c0\u67e5\u56db\u5c42\u8def\u7531\u7ed3\u6784\u3001\u6a21\u677f\u6b8b\u4f59\u3001\u4e2d\u82f1\u6df7\u5408\u3001\u5f31\u8d1f\u6837\u672c\u3001tags \u5b8c\u6574\u6027\u7b49\u95ee\u9898\uff0c\u8f93\u51fa\u8bca\u65ad\u5361\u3002',
    parameters: {
      path: { type: 'string', required: true, description: '\u6280\u80fd\u6587\u4ef6\u7684\u7edd\u5bf9\u8def\u5f84\uff08\u5982 SKILL.md\uff09' }
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }]
    },
    async execute(args) {
      const content = await readFile(args.path, 'utf-8')
      const filename = args.path.split(/[/\\]/).pop()
      return formatDiagnosticCard(diagnoseSkill(content, filename))
    }
  }))

  ctx.tools.register(defineTool({
    name: 'skill-audit',
    description: '\u6279\u91cf\u5ba1\u8ba1\u6574\u4e2a\u6280\u80fd\u76ee\u5f55\u4e2d\u6240\u6709 .md \u6587\u4ef6\u7684\u8def\u7531\u5065\u5eb7\u5ea6\u3002\u8df3\u8fc7 node_modules\u3001.git \u7b49\u65e0\u5173\u76ee\u5f55\uff0c\u8f93\u51fa\u6c47\u603b\u62a5\u544a\u3002',
    parameters: {
      path: { type: 'string', required: true, description: '\u6280\u80fd\u76ee\u5f55\u7684\u7edd\u5bf9\u8def\u5f84' },
      strict: { type: 'boolean', description: '\u4e25\u683c\u6a21\u5f0f\uff1awarning \u4e5f\u8ba1\u4e3a\u5931\u8d25\uff08\u9ed8\u8ba4 false\uff09' }
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }]
    },
    async execute(args) {
      const files = await walkSkillsDir(args.path)
      if (files.length === 0) return `\u76ee\u5f55 ${args.path} \u4e2d\u672a\u627e\u5230 .md \u6587\u4ef6\u3002`
      const results = files.map(f => diagnoseSkill(f.content, f.name))
      const healthy = results.filter(r => r.health === 'healthy').length
      const attention = results.filter(r => r.health === 'needs-attention').length
      const unhealthy = results.filter(r => r.health === 'unhealthy').length
      const totalCritical = results.reduce((s, r) => s + r.summary.critical, 0)
      const totalWarnings = results.reduce((s, r) => s + r.summary.warnings, 0)
      let out = `# \u6280\u80fd\u8def\u7531\u5ba1\u8ba1\u62a5\u544a\n\n`
      out += `**\u626b\u63cf\u8def\u5f84**: ${args.path}\n**\u626b\u63cf\u6587\u4ef6**: ${files.length} \u4e2a\n\n`
      out += `## \u6982\u89c8\n\n| \u72b6\u6001 | \u6570\u91cf | \u5360\u6bd4 |\n|------|------|------|\n`
      out += `| \u2705 \u5065\u5eb7 | ${healthy} | ${(healthy / results.length * 100).toFixed(0)}% |\n`
      out += `| \u26a0\ufe0f \u9700\u5173\u6ce8 | ${attention} | ${(attention / results.length * 100).toFixed(0)}% |\n`
      out += `| \u274c \u4e0d\u5065\u5eb7 | ${unhealthy} | ${(unhealthy / results.length * 100).toFixed(0)}% |\n\n`
      out += `**\u95ee\u9898\u603b\u8ba1**: \ud83d\udd34 ${totalCritical} | \ud83d\udfe1 ${totalWarnings}\n\n`
      const problemSkills = results.filter(r => r.health !== 'healthy')
      if (problemSkills.length > 0) {
        out += `## \u95ee\u9898\u6e05\u5355\n\n`
        for (const r of problemSkills) {
          out += `### ${r.file}\n`
          for (const i of r.issues) {
            const icon = { critical: '\ud83d\udd34', warning: '\ud83d\udfe1', info: '\ud83d\udfe2' }
            out += `- ${icon[i.severity]} ${i.issue}: ${i.suggestion}\n`
          }
          out += '\n'
        }
      }
      return out
    }
  }))

  ctx.tools.register(defineTool({
    name: 'skill-classify',
    description: '\u8bfb\u53d6\u76ee\u5f55\u4e2d\u6240\u6709\u6280\u80fd\u6587\u4ef6\uff0c\u751f\u6210\u5206\u7c7b\u63d0\u793a\u8bcd\u3002\u6a21\u578b\u6839\u636e 7 \u5927\u7c7b 19 \u5b50\u7c7b\u7684\u5206\u7c7b\u6807\u51c6\uff0c\u5c06\u6bcf\u4e2a\u6280\u80fd\u5f52\u7c7b\u5e76\u8f93\u51fa\u7ed3\u6784\u5316\u7ed3\u679c\u3002',
    parameters: {
      path: { type: 'string', required: true, description: '\u6280\u80fd\u76ee\u5f55\u7684\u7edd\u5bf9\u8def\u5f84' }
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }]
    },
    async execute(args) {
      const files = await walkSkillsDir(args.path)
      if (files.length === 0) return `\u76ee\u5f55 ${args.path} \u4e2d\u672a\u627e\u5230 .md \u6587\u4ef6\u3002`
      const promptPath = join(import.meta.dirname || new URL('.', import.meta.url).pathname, 'prompts', 'classify-v2.txt')
      let classifyPrompt = ''
      try { classifyPrompt = await readFile(promptPath, 'utf-8') } catch {
        classifyPrompt = '\u5c06\u4ee5\u4e0b\u6280\u80fd\u6309\u529f\u80fd\u5f52\u7c7b\u5230 7 \u5927\u7c7b 19 \u5b50\u7c7b\u4e2d\uff0c\u8f93\u51fa\u683c\u5f0f: \u6280\u80fd\u540d: \u5927\u7c7b \u2192 \u5b50\u7c7b'
      }
      const skillDescriptions = files.map(f => {
        const fm = extractFrontmatter(f.content)
        const desc = fm?.description || f.content.split('\n').filter(l => l.trim()).slice(0, 3).join(' ')
        return `- ${f.name.replace(/\.md$/, '')}: ${desc.slice(0, 200)}`
      })
      let out = `# \u6280\u80fd\u5206\u7c7b\u4efb\u52a1\n\n## \u5206\u7c7b\u6807\u51c6\n\n${classifyPrompt}\n\n`
      out += `## \u5f85\u5206\u7c7b\u6280\u80fd\uff08${files.length} \u4e2a\uff09\n\n`
      out += skillDescriptions.join('\n') + '\n\n'
      out += `\u8bf7\u6309\u4e0a\u8ff0\u5206\u7c7b\u6807\u51c6\uff0c\u5bf9\u6bcf\u4e2a\u6280\u80fd\u7ed9\u51fa\u5206\u7c7b\u7ed3\u679c\u3002\u8f93\u51fa\u683c\u5f0f: \`\u6280\u80fd\u540d: \u5927\u7c7b \u2192 \u5b50\u7c7b\`\n`
      return out
    }
  }))
}
