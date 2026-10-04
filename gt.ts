// Google Cloud Translation (Basic, v2), for the copy check only.
// Every answer is cached in data/gt-cache.json, so nothing is paid for twice;
// a run that would send more than its budget of new characters is refused
// before the first request. The key comes from GOOGLE_TRANSLATE_API_KEY, which
// bun reads from the git-ignored .env.local.
import { existsSync, readFileSync, writeFileSync } from 'node:fs'

const CACHE = 'data/gt-cache.json'
const URL = 'https://translation.googleapis.com/language/translate/v2'
const BATCH = 50

const cache: Record<string, string> = existsSync(CACHE) ? JSON.parse(readFileSync(CACHE, 'utf8')) : {}
const keyOf = (from: string, to: string, text: string) => `${from}>${to}\u0000${text}`

export interface Job {
  from: string
  to: string
  text: string
}

/** Characters these jobs would send that the cache does not already hold. */
export function uncached(jobs: Job[]): number {
  const seen = new Set<string>()
  let n = 0
  for (const j of jobs) {
    const k = keyOf(j.from, j.to, j.text)
    if (!(k in cache) && !seen.has(k)) seen.add(k), (n += j.text.length)
  }
  return n
}

/** Fills the cache for every job, refusing outright above `budget` new characters. */
export async function translateAll(jobs: Job[], budget: number): Promise<void> {
  const cost = uncached(jobs)
  if (cost > budget) throw new Error(`${cost} new characters exceeds the budget of ${budget}; raise it to go on`)
  const key = process.env.GOOGLE_TRANSLATE_API_KEY
  if (!key) throw new Error('GOOGLE_TRANSLATE_API_KEY is not set; put it in .env.local')

  const todo = new Map<string, Job[]>()
  for (const j of jobs) {
    if (keyOf(j.from, j.to, j.text) in cache) continue
    const pair = `${j.from}>${j.to}`
    const list = todo.get(pair) ?? []
    if (!list.some((x) => x.text === j.text)) list.push(j)
    todo.set(pair, list)
  }
  for (const list of todo.values())
    for (let i = 0; i < list.length; i += BATCH) {
      const batch = list.slice(i, i + BATCH)
      const res = await fetch(`${URL}?key=${key}`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ q: batch.map((j) => j.text), source: batch[0].from, target: batch[0].to, format: 'text' }),
      })
      if (!res.ok) throw new Error(`Translation API ${res.status}: ${(await res.text()).slice(0, 300)}`)
      const { data } = (await res.json()) as { data: { translations: { translatedText: string }[] } }
      batch.forEach((j, k) => (cache[keyOf(j.from, j.to, j.text)] = data.translations[k].translatedText))
      writeFileSync(CACHE, JSON.stringify(cache))
    }
}

/** A cached answer; call `translateAll` first. */
export function gt(from: string, to: string, text: string): string {
  const v = cache[keyOf(from, to, text)]
  if (v === undefined) throw new Error(`not translated: ${from}>${to} ${text.slice(0, 40)}`)
  return v
}
