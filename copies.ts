// How much of PIB's translation is Google Translate's. For a sample of sentence
// pairs from align.py, Google translates the English, and a pair
// whose PIB text is within chrF 90 of Google's is a copy. Two independent
// translations almost never come that close: in the November 2025 pilot,
// sarvam-30b and Google did on 2 of 200 Assamese sentences, Google and IN22's
// human text on 0 of 89, while Google and PIB's Assamese did on 45 of 200.
//
// It finds only text kept as Google wrote it or lightly edited. Heavier
// editing, or another engine such as the Bhashini plugin PIB loads, passes as
// "not a copy": the rate is a lower bound on machine text, not a measure of
// human text. Google today also writes differently from Google in an older
// year, so an old month's rate is a lower bound twice over.
//
//   bun copies.ts <sentences.jsonl> [n per office and language = 100]
//
// Writes copies.jsonl beside the input, one line per sampled pair with its
// chrF and `google_copy`, and never Google's text, whose terms forbid
// passing it on. GT_BUDGET caps the new characters sent (default 300,000).
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { gt, translateAll } from './gt'

/** Sentence chrF as sacrebleu computes it (CHRF() defaults: character 1- to 6-grams, whitespace ignored, beta 2). */
export function chrf(hypothesis: string, reference: string): number {
  const grams = (s: string, n: number) => {
    const chars = Array.from(s.replace(/\s+/g, ''))
    const counts = new Map<string, number>()
    for (let i = 0; i + n <= chars.length; i++) {
      const g = chars.slice(i, i + n).join('')
      counts.set(g, (counts.get(g) ?? 0) + 1)
    }
    return { counts, total: Math.max(chars.length - n + 1, 0) }
  }
  const beta2 = 4
  let precision = 0
  let recall = 0
  let orders = 0
  for (let n = 1; n <= 6; n++) {
    const h = grams(hypothesis, n)
    const r = grams(reference, n)
    let match = 0
    for (const [g, c] of h.counts) match += Math.min(c, r.counts.get(g) ?? 0)
    // Only orders both sides are long enough for count, as in sacrebleu.
    if (h.total > 0 && r.total > 0) {
      orders++
      precision += match / h.total
      recall += match / r.total
    }
  }
  if (!orders) return 0
  const p = precision / orders
  const r = recall / orders
  return p + r ? (100 * (1 + beta2) * p * r) / (beta2 * p + r) : 0
}

export const COPY = 90

/** Whether a reference is Google's output kept as it was, or nearly. */
export function isCopy(google: string, reference: string): boolean {
  return chrf(google, reference) >= COPY
}

/** A 95% Wilson interval for k of n, in per cent: honest for small samples and for rates near 0. */
function wilson(k: number, n: number): [number, number] {
  if (!n) return [0, 0]
  const z = 1.96
  const p = k / n
  const mid = (p + (z * z) / (2 * n)) / (1 + (z * z) / n)
  const half = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / (1 + (z * z) / n)
  return [Math.max(0, mid - half) * 100, Math.min(1, mid + half) * 100]
}

type Pair = { lang: string; en: string; text: string; sim: number; prid: string; office: string }

// Google writes Manipuri in Meetei Mayek; PIB writes it in Bengali script.
const NO_GT = new Set(['mni'])
// Only well-aligned pairs: a misaligned pair scores low and would hide a copy.
const MIN_SIM = 0.85

if (import.meta.main) {
  const [file, nArg] = process.argv.slice(2)
  if (!file) throw new Error('usage: bun copies.ts <sentences.jsonl> [n per office and language]')
  const n = Number(nArg ?? 100)
  const pairs: Pair[] = readFileSync(file, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))

  // Up to n per office and language, a round at a time across releases so no release dominates.
  const cells = new Map<string, Map<string, Pair[]>>()
  for (const p of pairs) {
    if (p.sim < MIN_SIM || NO_GT.has(p.lang) || p.en.length < 40) continue
    const key = `${p.office}\t${p.lang}`
    const byRelease = cells.get(key) ?? new Map<string, Pair[]>()
    byRelease.set(p.prid, [...(byRelease.get(p.prid) ?? []), p])
    cells.set(key, byRelease)
  }
  const sample = new Map<string, Pair[]>()
  for (const [key, byRelease] of cells) {
    const out: Pair[] = []
    for (let round = 0; out.length < n && [...byRelease.values()].some((l) => l[round]); round++)
      for (const list of byRelease.values()) if (list[round] && out.length < n) out.push(list[round])
    sample.set(key, out)
  }

  const all = [...sample.values()].flat()
  await translateAll(all.map((p) => ({ from: 'en', to: p.lang, text: p.en })), Number(process.env.GT_BUDGET ?? 300_000))

  const rows = all.map((p) => {
    const score = chrf(gt('en', p.lang, p.en), p.text)
    return { prid: p.prid, office: p.office, lang: p.lang, en: p.en, text: p.text, chrf: Math.round(score * 10) / 10, google_copy: score >= COPY }
  })
  const out = `${dirname(file)}/copies.jsonl`
  writeFileSync(out, rows.map((r) => JSON.stringify(r)).join('\n') + '\n')

  console.log(`${'office'.padEnd(24)} ${'lang'.padEnd(5)} ${'copies'.padStart(9)} ${'rate'.padStart(6)}  95% interval`)
  for (const [key, list] of [...sample].sort()) {
    const [office, lang] = key.split('\t')
    const k = rows.filter((r) => r.office === office && r.lang === lang && r.google_copy).length
    const [lo, hi] = wilson(k, list.length)
    console.log(`${office.padEnd(24)} ${lang.padEnd(5)} ${`${k}/${list.length}`.padStart(9)} ${((100 * k) / list.length).toFixed(0).padStart(5)}%  ${lo.toFixed(0)}-${hi.toFixed(0)}%`)
  }
  console.log(`\nwrote ${out}: ${rows.length} pairs, ${rows.filter((r) => r.google_copy).length} copies`)
}
