import { readdir, readFile } from 'node:fs/promises'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../src/panwatch/', import.meta.url))
const checked = []

async function walk(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) {
      await walk(path)
      continue
    }
    if (!/\.(ts|tsx)$/.test(entry.name)) continue
    if (entry.name === 'i18n.ts' || entry.name.endsWith('.test.ts')) continue
    const source = await readFile(path, 'utf8')
    const lines = source.split('\n')
    lines.forEach((line, index) => {
      if (/[\u4e00-\u9fff]/.test(line)) {
        checked.push(`${relative(process.cwd(), path)}:${index + 1}: ${line.trim()}`)
      }
    })
  }
}

await walk(root)
if (checked.length) {
  console.error('Visible copy must live in i18n.ts:\n' + checked.join('\n'))
  process.exit(1)
}
console.log('i18n literal check passed')

