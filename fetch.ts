// Scrape PIB (pib.gov.in) press releases and their official Indian-language
// translations into a parallel corpus.
//
//   bun fetch.ts 40                        the English feed, first 40 releases
//   bun fetch.ts 40 --reg 6 --lang 11      the Chennai office's Tamil feed
//   bun fetch.ts --month 2025-09           every PRID PIB Delhi published that month
//   bun fetch.ts --month 2025-09 --columns hi,ta
//
// Discovery is PIB's own RSS feed (latest 20 per office+language) or the
// Allrel.aspx month list, driven by ASP.NET postback, for anything older. A
// release body lives on PressReleaseIframePage.aspx?PRID=N; its "Read this
// release in:" block links the translations, each with its own PRID, so the
// corpus is n-way parallel by construction. The block lists every language of
// the release except the page's own, so a page's language comes from its text.
//
// Polite by default: one request at a time, PIB_DELAY ms apart (1500), 429/503
// backed off and retried, and every page cached under data/html/ so a
// rerun and a crash both cost nothing. PIB_DELAY=0 only for a cached rerun.
// PIB_UA overrides the User-Agent, which names this project and its URL. PIB's
// edge answers 403 to the RFC bot form "(+https://...)", so the contact goes
// after a semicolon instead.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'

const DIR = process.env.PIB_DIR ?? 'data'
const HTML = `${DIR}/html`
const DELAY = Number(process.env.PIB_DELAY ?? 1500)
const SITE = 'https://www.pib.gov.in'
const UA = process.env.PIB_UA ?? 'pib-parallel/1.0; github.com/micahchoo/pib-parallel'
// 403 joins the list because PIB's edge uses it to refuse a request outright;
// without a retry, one refused page ends the whole run.
const RETRYABLE = new Set([403, 429, 500, 502, 503, 504])

/** PIB names each translation in its own script; map a label to the app's language code. */
const LANGS: Record<string, string> = {
  English: 'en', Hindi: 'hi', हिन्दी: 'hi', Urdu: 'ur', Marathi: 'mr', Bengali: 'bn', Assamese: 'as',
  Manipuri: 'mni', Punjabi: 'pa', Gujarati: 'gu', Odia: 'or', Oriya: 'or', Tamil: 'ta', Telugu: 'te',
  Kannada: 'kn', Malayalam: 'ml', Konkani: 'gom', Dogri: 'doi', Bodo: 'brx', Sanskrit: 'sa',
  Maithili: 'mai', Nepali: 'ne', Sindhi: 'sd', Mizo: 'lus', Khasi: 'kha', Tenyidei: 'njm',
}

// Each language's script. The danda and double danda (U+0964-5) sit in the
// Devanagari block but end sentences in Punjabi, Bengali, Odia and Assamese
// too, so they are left out: with them, 117 Punjabi pairs were labelled Hindi.
const SCRIPTS: Array<[string, RegExp]> = [
  ['hi', /[\u0900-\u0963\u0966-\u097F]/g], ['ur', /[\u0600-\u06FF]/g], ['bn', /[\u0980-\u09FF]/g], ['pa', /[\u0A00-\u0A7F]/g],
  ['gu', /[\u0A80-\u0AFF]/g], ['or', /[\u0B00-\u0B7F]/g], ['ta', /[\u0B80-\u0BFF]/g], ['te', /[\u0C00-\u0C7F]/g],
  ['kn', /[\u0C80-\u0CFF]/g], ['ml', /[\u0D00-\u0D7F]/g], ['mni', /[\uABC0-\uABFF]/g], ['en', /[A-Za-z]/g],
]
// Languages that share a script: a Devanagari page could be any of them, so a
// hint naming one of them wins.
const SHARED_SCRIPT: Record<string, string> = {
  mr: 'hi', ne: 'hi', sa: 'hi', gom: 'hi', as: 'bn', mni: 'bn', sd: 'ur',
  // Latin-script languages of the north-east offices: Mizo, Khasi, Tenyidei.
  lus: 'en', kha: 'en', njm: 'en',
}

export type Release = {
  prid: string
  lang: string
  title: string
  subtitle: string
  ministry: string
  date: string
  body: string
  translations: Record<string, string>
}

// Removed before anything is read: an embedded tweet or post is third-party
// material, and on translated pages most were left in English (578 of 1,028
// on Urdu pages in the November 2025 pilot), so they would pair English with
// English. Contact details become placeholders, the same on every side of a
// release, so the sentence and its pair survive. All 93 addresses and 68 phone
// numbers in the pilot were institutional; none of it is text a translation
// corpus needs.
// A post is known by its class or, where an editor dropped the class (35 pilot
// pages), by its link; a plain quotation stays.
const QUOTES = /<blockquote\b[^>]*>[\s\S]*?<\/blockquote>/gi
const POST = /class="(?:twitter-tweet|instagram-media)|(?:twitter|x)\.com\/\w+\/status\/|instagram\.com\/(?:p|reel)\//i
// The local part may end in a stray dot and take [dot]; the domain is lower
// case, so a following sentence ("...gov.in. Next") is not taken with it, and
// may have a space after a dot or round [at] and [dot] ("trai. gov.in",
// "csm-upsc [at] nic [dot] in"): all forms found in the November 2025 data.
const EMAIL = /[\w+-]+(?:(?:\.|\s?\[dot\]\s?)[\w+-]+)*\.?\s?(?:@|\[at\])\s?[a-z0-9-]+(?:(?:\.\s?|\s?\[dot\]\s?)[a-z0-9-]+)+/g
const ZERO = '[0०০੦૦୦௦౦೦൦۰٠]'
// A mobile's first digit, 6 to 9, in every script that writes its own digits:
// a Bengali page wrote a WhatsApp number in Bengali digits, which [6-9] missed.
const MOBILE_FIRST = `[6-9${[0x0966, 0x09e6, 0x0a66, 0x0ae6, 0x0b66, 0x0be6, 0x0c66, 0x0ce6, 0x0d66, 0x0660, 0x06f0]
  .map((zero) => `${String.fromCodePoint(zero + 6)}-${String.fromCodePoint(zero + 9)}`)
  .join('')}]`
const D = '\\p{Nd}'
const SEP = '[\\s-]?'
// A number after +91, which drops the trunk 0 ("+91-33-22361401", "+ 91-11-..."),
// or kept in right-to-left order on an Urdu page ("-23000761 +91-40"); a
// landline with its STD code; a mobile; a toll-free number, Indian or "1-800".
// Never digits that touch a letter (an app id, a file name) or run on into more.
const PHONE = new RegExp(
  `(?<![\\p{L}\\p{M}\\p{Nd}])(?:${[
    `\\+\\s?91${SEP}${D}{2,4}${SEP}${D}{3,4}${SEP}${D}{3,4}`,
    `-?${D}{6,8}\\s?\\+\\s?91${SEP}${D}{2,4}`,
    `(?:\\+\\s?91${SEP})?${ZERO}${D}{2,4}${SEP}${D}{3,4}${SEP}${D}{3,4}`,
    `(?:\\+\\s?91${SEP})?${MOBILE_FIRST}${D}{4}${SEP}${D}{5}`,
    `1${SEP}800${SEP}${D}{2,3}${SEP}${D}{3,4}`,
  ].join('|')})(?![\\p{L}\\p{M}\\p{Nd}])`,
  'gu',
)

export function redact(text: string) {
  return text.replace(EMAIL, '<email>').replace(PHONE, '<phone>')
}

export function parseRelease(prid: string, page: string, hint = ''): Release {
  const html = page.replace(QUOTES, (quote) => (POST.test(quote) ? '' : quote))
  const field = (id: string) => {
    const m = html.match(new RegExp(`<[a-z0-9]+ id="${id}"[^>]*>([\\s\\S]*?)</[a-z0-9]+>`, 'i'))
    return m ? redact(text(m[1])) : ''
  }
  // The body is everything the release container holds past the dateline; the
  // header blocks above it go by id rather than by tag nesting. Cut at the
  // modal's opening tag, not its id, or its "<div" is left in the text.
  //
  // The class name is matched as an attribute: it first appears in a style sheet.
  const open = html.indexOf('class="innner-page-main-about-us-content-right-part"')
  const close = html.indexOf('<div id="P_CategoryManagement"')
  // No container is no release: PIB's error page arrives with status 200.
  const container = open < 0 ? '' : html.slice(open, close < 0 ? html.length : close)
  const title = field('Titleh2')
  // A release opens after its dateline. The event layout (IFFI) has none, so
  // its prose opens after the subtitle, or failing that the title.
  const dateline = container.indexOf('<div id="PrDateTime"')
  const heading = ['<h3 id="Subtitleh3"', '<h1 id="Titleh2"'].map((m) => container.indexOf(m)).find((i) => i >= 0) ?? -1
  const start =
    dateline >= 0 ? container.indexOf('</div>', dateline) + 6 : heading >= 0 ? container.indexOf('</h', heading + 4) : 0
  // Past the prose come the release id, the view counter, the language block and
  // the attachment list; the body ends at whichever of them comes first. The
  // event layout adds a festival paragraph, the same on every release.
  const ends = [
    '<span id="ReleaseId"', '<span id="lblViews"', '<div class="ReleaseLang"', '<div id="RelLink"',
    '<div id="FooterEventText"', '<span id="ReleaseIdEvent"', '<span id="lblViewsEvent"',
  ]
    .map((marker) => container.indexOf(marker, start))
    .filter((i) => i >= 0)
  // An editor sometimes pastes another release's footer into the prose; no
  // sentence of a release says "Visitor Counter".
  const body = text(container.slice(start, ends.length ? Math.min(...ends) : container.length).replace(/<input[^>]*>/gi, ''))
    .split('\n')
    .filter((line) => !line.includes('Visitor Counter'))
    .join('\n')
    .trim()
  const block = html.match(/<div class="ReleaseLang">([\s\S]*?)<\/div>/i)
  const translations: Record<string, string> = {}
  // An office's own version is labelled "Hindi_Cg", "Bengali-TR": it names its
  // language, but fills that language only if the release has no national one.
  const links = block ? [...block[1].matchAll(/PRID=(\d+)'[^>]*>\s*([^<]+?)\s*<\/a>/g)].map((m) => [m[2].trim(), m[1]]) : []
  for (const [label, id] of links) if (LANGS[label]) translations[LANGS[label]] = id
  for (const [label, id] of links) {
    const code = LANGS[label] ? '' : (LANGS[label.split(/[-_]/)[0]] ?? label)
    if (code && !(code in translations)) translations[code] = id
  }
  return {
    prid,
    lang: pageLang(title || body, hint),
    title,
    subtitle: field('Subtitleh3'),
    ministry: field('MinistryName'),
    date: field('PrDateTime').replace(/\s+/g, ' ').replace(/^[^:]*:\s*/, ''),
    body: redact(body),
    translations,
  }
}

/**
 * The page carries no lang attribute, so the language is the script with the
 * most letters in its headline (an English acronym in a Hindi headline does
 * not make it English), disambiguated by the feed that found it.
 */
export function pageLang(headline: string, hint: string) {
  let seen = ''
  let most = 0
  for (const [code, re] of SCRIPTS) {
    const n = headline.match(re)?.length ?? 0
    if (n > most) (seen = code), (most = n)
  }
  return hint && (hint === seen || SHARED_SCRIPT[hint] === seen) ? hint : seen || hint
}

// PIB writes its body paragraphs with HTML entities, including the typographic
// set, so the text is not usable until they are decoded. Decoding runs after
// the tags are stripped, or an escaped "<b>" would be stripped as a tag.
const ENTITIES: Record<string, string> = {
  amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', zwj: '\u200d', zwnj: '\u200c',
  lsquo: '\u2018', rsquo: '\u2019', ldquo: '\u201c', rdquo: '\u201d',
  mdash: '\u2014', ndash: '\u2013', hellip: '\u2026', middot: '\u00b7', bull: '\u2022',
  deg: '\u00b0', times: '\u00d7', laquo: '\u00ab', raquo: '\u00bb', copy: '\u00a9', reg: '\u00ae', trade: '\u2122', rupee: '\u20b9',
}

/** Named, decimal and hex entities, in one pass each. Two passes are needed: some PIB text is escaped twice. */
function decode(html: string) {
  return html
    .replace(/&#x([0-9a-f]+);/gi, (match, hex: string) => (parseInt(hex, 16) <= 0x10ffff ? String.fromCodePoint(parseInt(hex, 16)) : match))
    .replace(/&#(\d+);/g, (match, dec: string) => (Number(dec) <= 0x10ffff ? String.fromCodePoint(Number(dec)) : match))
    .replace(/&([a-z]+);/gi, (match, name: string) => ENTITIES[name.toLowerCase()] ?? match)
}

function text(html: string) {
  return decode(
    decode(
      html
        .replace(/\r/g, '')
        .replace(/<br\s*\/?>|<\/p>|<\/div>|<\/li>|<\/h\d>/gi, '\n')
        .replace(/<[^>]+>/g, ' '),
    ),
  )
    .replace(/\n[ \t]+/g, '\n')
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

// A request that never answers is retried like any other failure. On 2026-10-04
// a VPN dropped mid-request and the crawl, with no timeout, waited forever.
const TIMEOUT = 60_000

let lastRequest = 0
let requests = 0

/** Wait out whichever is longer: the politeness gap, or the CDN's own answer. */
async function pause(ms: number) {
  const { promise, resolve } = Promise.withResolvers<void>()
  setTimeout(resolve, ms)
  return promise
}

/** One GET for the whole run, held PIB_DELAY apart from the last. */
async function get(url: string): Promise<string> {
  for (let attempt = 0; ; attempt++) {
    const gap = DELAY - (Date.now() - lastRequest)
    if (gap > 0) await pause(gap)
    lastRequest = Date.now()
    requests++
    let res: Response
    try {
      res = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9' }, signal: AbortSignal.timeout(TIMEOUT) })
    } catch (error) {
      if (attempt >= 5) throw error
      const backoff = Math.min(60_000, 2 ** attempt * 2000)
      console.error(`  ${(error as Error).message}; waiting ${(backoff / 1000).toFixed(0)}s`)
      await pause(backoff)
      continue
    }
    if (res.ok) return res.text()
    const backoff = Number(res.headers.get('retry-after') ?? 0) * 1000 || Math.min(60_000, 2 ** attempt * 2000)
    if (!RETRYABLE.has(res.status) || attempt >= 5) throw new Error(`${res.status} ${url}`)
    console.error(`  ${res.status}; waiting ${(backoff / 1000).toFixed(0)}s`)
    await pause(backoff)
  }
}

const MONTHS: Record<string, number> = { JAN: 0, FEB: 1, MAR: 2, APR: 3, MAY: 4, JUN: 5, JUL: 6, AUG: 7, SEP: 8, OCT: 9, NOV: 10, DEC: 11 }
const SETTLE_DAYS = 7

/**
 * Whether a cached page can be trusted: its release is a week old. Translations
 * are added in the days after posting (on 2026-10-04 the newest English release
 * linked none), so a page cached sooner would keep an empty language block for
 * good. A page with no readable date is trusted rather than refetched forever.
 */
export function settled(html: string, now = new Date()): boolean {
  const m = html.match(/id="PrDateTime"[^>]*>[^<]*?(\d{1,2}) ([A-Z]{3}) (\d{4})/)
  if (!m || !(m[2] in MONTHS)) return true
  const posted = Date.UTC(Number(m[3]), MONTHS[m[2]], Number(m[1]))
  return now.getTime() - posted >= SETTLE_DAYS * 86_400_000
}

const fetchedThisRun = new Set<string>()

/**
 * A release page's address. The bare `?PRID=N` answers 302 to this form, which
 * cost a quarter of each page's time (2026-10-04). Any reg and lang give the
 * same release; 15 of 16 sampled pages parsed identically, and the 16th only
 * differed in the footer's label, which the parser drops.
 */
export function releaseUrl(prid: string) {
  return `${SITE}/PressReleaseIframePage.aspx?PRID=${prid}&reg=3&lang=1`
}

/** A release page, cached by PRID, and fetched again until its release has settled. */
async function page(prid: string): Promise<string> {
  const file = `${HTML}/${prid}.html`
  if (existsSync(file)) {
    const cached = readFileSync(file, 'utf8')
    if (fetchedThisRun.has(prid) || settled(cached)) return cached
  }
  const html = await get(releaseUrl(prid))
  writeFileSync(file, html)
  fetchedThisRun.add(prid)
  return html
}

/** The latest 20 releases PIB offers for one office and language. `Regid` AND `reg` are both needed, or PIB silently answers with National/Hindi. */
async function feed(lang: number, reg: number) {
  const xml = await get(`${SITE}/RssMain.aspx?ModId=6&Lang=${lang}&Regid=${reg}&reg=${reg}`)
  return [...xml.matchAll(/<item>[\s\S]*?<title>([\s\S]*?)<\/title>[\s\S]*?PRID=(\d+)/g)].map((m) => ({ title: text(m[1]), prid: m[2] }))
}

/** Every PRID one office published in one month. The date filter is POSTback, so the form's own state goes back with it. */
async function monthPrerids(reg: number, lang: number, year: number, month: number) {
  const url = `${SITE}/Allrel.aspx?reg=${reg}&lang=${lang}`
  const form = new URLSearchParams()
  for (const m of (await get(url)).matchAll(/<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"/g)) form.set(m[1], m[2])
  form.set('ctl00$Bar1$ddlregion', String(reg))
  form.set('ctl00$Bar1$ddlLang', String(lang))
  form.set('ctl00$ContentPlaceHolder1$ddlMinistry', '0')
  form.set('ctl00$ContentPlaceHolder1$ddlday', '0')
  form.set('ctl00$ContentPlaceHolder1$ddlMonth', String(month))
  form.set('ctl00$ContentPlaceHolder1$ddlYear', String(year))
  form.set('__EVENTTARGET', 'ctl00$ContentPlaceHolder1$ddlYear')
  form.set('__EVENTARGUMENT', '')
  await pause(Math.max(0, DELAY - (Date.now() - lastRequest)))
  lastRequest = Date.now()
  requests++
  const res = await fetch(url, { method: 'POST', headers: { 'User-Agent': UA, 'Content-Type': 'application/x-www-form-urlencoded' }, body: form.toString(), signal: AbortSignal.timeout(TIMEOUT) })
  if (!res.ok) throw new Error(`${res.status} ${url}`)
  const html = await res.text()
  console.error(`  ${(html.match(/Displaying\s+([\d,]+)\s+Press Releases[^<]*/)?.[0] ?? 'no list').trim()}`)
  return [...new Set([...html.matchAll(/PressReleaseDetail\.aspx\?PRID=(\d+)/g)].map((m) => m[1]))]
}

/** One release and its translations as a parallel row. A blank page is no side; a blank source is no row. */
export function groupOf(row: Release, translated: Release[]) {
  if (!row.body) return null
  const byLang: Record<string, { prid: string; title: string; body: string }> = { [row.lang]: { prid: row.prid, title: row.title, body: row.body } }
  for (const t of translated) if (t.body) byLang[t.lang] = { prid: t.prid, title: t.title, body: t.body }
  return { prid: row.prid, date: row.date, ministry: row.ministry, byLang }
}

/**
 * How many releases this method could pair: PIB links a translation on the
 * release page, or nothing does. In November 2018 Chandigarh's Punjabi and
 * Bhubaneswar's Odia releases linked none, so a run there finds no pairs.
 */
export function linkReport(rows: Release[]) {
  const english = rows.every((r) => r.lang === 'en')
  const linked = rows.filter((r) => (english ? Object.keys(r.translations).length > 0 : 'en' in r.translations)).length
  return `${linked} of ${rows.length} releases link ${english ? 'a' : 'an English'} translation`
}

// The feed number is the only statement of the discovered pages' language. Read
// from each office's own language list on Allrel.aspx (2026-10-04; the table is
// in offices.tsv). Offices publishing their own Hindi, Urdu, Telugu or
// Bengali use their own numbers for it.
const FEED_LANGS: Record<string, string> = {
  1: 'en', 2: 'hi', 3: 'ur', 4: 'bn', 6: 'pa', 8: 'kn', 9: 'mr', 10: 'as', 11: 'ta', 13: 'gu', 14: 'mni', 15: 'ml',
  16: 'te', 18: 'or', 29: 'ne', 30: 'kha', 31: 'njm', 32: 'lus', 37: 'bn', 42: 'gom', 44: 'ur', 46: 'te',
  33: 'hi', 34: 'hi', 35: 'hi', 36: 'hi', 38: 'hi', 39: 'hi', 40: 'hi', 41: 'hi', 43: 'hi', 45: 'hi',
}

if (import.meta.main) {
  mkdirSync(HTML, { recursive: true })

  const args = process.argv.slice(2)
  const flag = (name: string, fallback: string) => {
    const i = args.indexOf(`--${name}`)
    return i >= 0 ? args[i + 1] : fallback
  }
  const reg = Number(flag('reg', '3'))
  const lang = Number(flag('lang', '1'))
  const columns = flag('columns', 'en').split(',').map((s) => s.trim()).filter(Boolean)
  const month = flag('month', '')
  const sourceLang = flag('source-lang', FEED_LANGS[String(lang)] ?? '')
  const bare = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')))
  const limit = bare[0] ? Number(bare[0]) : month ? Infinity : 20

  console.error(`PIB: reg=${reg} lang=${lang} delay=${DELAY}ms -> ${DIR}`)
  const prids = month
    ? (await monthPrerids(reg, lang, ...(month.split('-').map(Number) as [number, number]))).slice(0, limit)
    : (await feed(lang, reg)).slice(0, limit).map((i) => i.prid)
  console.error(`  ${prids.length} releases to fetch`)

  const rows: Release[] = []
  for (const prid of prids) rows.push(parseRelease(prid, await page(prid), sourceLang))
  writeFileSync(`${DIR}/releases.jsonl`, rows.map((r) => JSON.stringify(r)).join('\n') + '\n')

  // One parallel row per release group: the source page plus the translations asked for.
  const groups: string[] = []
  for (const row of rows) {
    const translated: Release[] = []
    for (const col of columns) {
      const prid = col === row.lang ? undefined : row.translations[col]
      // Keyed by the column asked for, not the script seen: a Tamil page with an English headline is still Tamil.
      if (prid) translated.push({ ...parseRelease(prid, await page(prid), col), lang: col })
    }
    const group = groupOf(row, translated)
    if (group) groups.push(JSON.stringify(group))
  }
  writeFileSync(`${DIR}/pairs.jsonl`, groups.map((g) => g + '\n').join(''))

  console.error(`  ${linkReport(rows)}`)
  console.error(`wrote ${rows.length} releases and ${groups.length} groups (${requests} requests)`)
}
