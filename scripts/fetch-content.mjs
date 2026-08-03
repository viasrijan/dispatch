#!/usr/bin/env node
/* ============================================================
   THE DISPATCH — auto content engine
   Fetches football headlines from credible RSS sources,
   curates (dedupes, edits, categorises) and posts them as
   data/content.json + live scores as data/scores.json.
   Designed to run on a 30-minute GitHub Actions cron.
   ============================================================ */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const DATA_DIR = path.join(__dirname, '..', 'data')
const CONTENT_FILE = path.join(DATA_DIR, 'content.json')
const SCORES_FILE = path.join(DATA_DIR, 'scores.json')

const SOURCES = [
  { id: 'bbc', name: 'BBC Sport', url: 'https://feeds.bbci.co.uk/sport/football/rss.xml' },
  { id: 'guardian', name: 'The Guardian', url: 'https://www.theguardian.com/football/rss' },
  { id: 'independent', name: 'The Independent', url: 'https://www.independent.co.uk/sport/football/rss', headers: { 'user-agent': 'Mozilla/5.0' } },
  { id: 'espn', name: 'ESPN FC', url: 'https://www.espn.com/espn/rss/soccer/news' },
]

const MAX_ARTICLES = 40
const KEEP_OLD_HOURS = 72

/* ---------------- RSS parsing ---------------- */

const decodeEntities = (s) =>
  String(s ?? '')
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
    .replace(/&#0?39;/g, "'").replace(/&apos;/g, "'")
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&')
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(+n))

const stripHtml = (s) => decodeEntities(s).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()

function parseRss(xml) {
  const items = []
  const itemRe = /<item[\s>]([\s\S]*?)<\/item>/gi
  let m
  while ((m = itemRe.exec(xml)) !== null) {
    const body = m[1]
    const grab = (tag) => {
      const r = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i').exec(body)
      return r ? stripHtml(r[1]) : ''
    }
    const title = grab('title')
    if (!title) continue
    items.push({
      title,
      link: grab('link'),
      description: grab('description'),
      published: parseDate(grab('pubDate')),
    })
  }
  return items
}

const parseDate = (s) => {
  if (!s) return null
  const t = Date.parse(s)
  return Number.isNaN(t) ? null : new Date(t).toISOString()
}

/* ---------------- curation ---------------- */

const normalizeTitle = (t) =>
  t.toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\b(the|a|an|to|of|in|for|on|at|by|and|is|as)\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

const editTitle = (t) => {
  const clean = decodeEntities(t).replace(/\s+/g, ' ').trim()
  if (clean.length <= 110) return clean
  const cut = clean.slice(0, 110)
  return cut.slice(0, cut.lastIndexOf(' ')) + '…'
}

const excerptOf = (a) => {
  const d = stripHtml(a.description || '')
  if (!d) return ''
  if (d.length <= 170) return d
  const cut = d.slice(0, 170)
  return cut.slice(0, cut.lastIndexOf(' ')) + '…'
}

const CATEGORY_RULES = [
  ['Transfers & Rumours', ['transfer', 'move to', 'signs', 'signing', 'loan', 'contract', 'release clause', 'bid for', 'switch to', 'joins', 'departure', 'extends ', 'extension', 'talisman', 'price tag', 'wanted by', 'targeted by']],
  ['Match Reports', ['beat ', 'defeat', ' won ', 'wins', ' victory', 'thrash', 'hammer', 'comeback', 'hat-trick', 'strikes', 'net', 'draw ', 'scored', 'stunner', 'battles', 'progress']],
  ['Injuries', ['injured', 'injury', 'blow', 'ruled out', 'out for', 'fitness', 'doubt', 'side-lined', 'sidelined']],
  ['Tactics & Analysis', ['analysis', 'tactics', 'explain', 'verdict', 'talking points', 'how ', 'why ', 'positional', 'formation', 'press conference', 'in numbers', 'data']],
  ['Previews', ['preview', 'team news', 'predicted', 'ahead of', 'line-up', 'lineup', 'odds']],
  ['News', ['confirms', 'announces', 'announced', 'appointed', 'sacked', 'fined', 'banned', 'award', 'wins award', 'calls up', 'recalled', 'retires', 'retirement']],
]

const LEAGUE_RULES = [
  ['Premier League', ['premier league', 'epl', 'arsenal', 'chelsea', 'liverpool', 'manchester', 'man utd', 'man city', 'tottenham', 'newcastle', 'aston villa', 'everton', 'west ham', 'brighton', 'crystal palace', 'fulham', 'brentford', 'wolves', 'nottingham', 'leicester', 'southampton', 'leeds', 'burnley', 'bournemouth', 'birmingham']],
  ['Champions League', ['champions league', 'ucl', 'final in']],
  ['La Liga', ['la liga', 'real madrid', 'barcelona', 'atletico', 'sevilla', 'valencia', 'real betis', 'villarreal', 'real sociedad', 'athletic']],
  ['Serie A', ['serie a', 'juventus', 'inter ', 'ac milan', 'napoli', 'roma', 'lazio', 'atalanta']],
  ['Bundesliga', ['bundesliga', 'bayern', 'dortmund', 'leipzig', 'leverkusen']],
  ['Ligue 1', ['ligue 1', 'psg', 'paris saint', 'marseille', 'lyon', 'monaco']],
  ['Europa League', ['europa league']],
  ['International', ['world cup', 'england', 'scotland', 'wales', 'international']],
]

const NON_FOOTBALL_RULES = [
  'formula 1', 'f1 ', 'verstappen', 'hamilton', 'cricket', 'tennis', 'golf',
  'nascar', 'boxing', 'ufc', 'sailing', 'darts', 'snooker', 'cycling', 'athletics',
  'basketball', 'nba', 'nfl', 'rugby', 'motogp', 'indian wells', 'wimbledon',
  'pegula', 'eala', 'sabalenka', 'swiatek', 'rybakina', 'gaffe', 'djokovic', 'alcaraz',
  'jockey', 'racecourse', 'racing', 'nap of the day', 'race meeting', 'flat racing',
  'darts player', 'pool player', 'ice hockey', 'super league', 'boxing ring',
]

const matchAny = (text, rules) => {
  const t = ' ' + text.toLowerCase() + ' '
  for (const [label, words] of rules) {
    if (words.some((w) => t.includes(w))) return label
  }
  return null
}

const isFootball = (text) => !NON_FOOTBALL_RULES.some((w) => (' ' + text.toLowerCase() + ' ').includes(w))

const curate = (items, source) =>
  items
    .filter((i) => i.link && i.title.length > 8)
    .filter((i) => isFootball(i.title + ' ' + i.description))
    .map((i) => {
      const category = matchAny(i.title + ' ' + i.description, CATEGORY_RULES) || 'News'
      const league = matchAny(i.title, LEAGUE_RULES) || 'Football'
      return {
        id: source.id + '-' + normalizeTitle(i.title).replace(/\s+/g, '-').slice(0, 48),
        title: editTitle(i.title),
        link: i.link,
        excerpt: excerptOf(i),
        body: stripHtml(i.description),
        source: source.id,
        sourceName: source.name,
        category,
        league,
        published: i.published || new Date().toISOString(),
        fetched_at: new Date().toISOString(),
      }
    })

/* ---------------- scores ---------------- */

const ESPN_LEAGUES = [
  ['eng.1', 'Premier League'], ['esp.1', 'La Liga'], ['ger.1', 'Bundesliga'],
  ['ita.1', 'Serie A'], ['fra.1', 'Ligue 1'],
]

async function fetchScores() {
  const matches = []
  await Promise.all(ESPN_LEAGUES.map(async ([slug, name]) => {
    try {
      const r = await fetch(`https://site.api.espn.com/apis/site/v2/sports/soccer/${slug}/scoreboard`, { headers: { 'user-agent': 'dispatch-bot/1.0' } })
      if (!r.ok) return
      const j = await r.json()
      for (const ev of (j.events || [])) {
        const c = ev.competitions && ev.competitions[0]
        if (!c) continue
        const st = c.status || {}
        const state = st.type ? st.type.state : ''
        const home = c.competitors.find((x) => x.homeAway === 'home')
        const away = c.competitors.find((x) => x.homeAway === 'away')
        if (!home || !away) continue
        matches.push({
          league: name,
          home: home.team.displayName,
          away: away.team.displayName,
          homeScore: home.score != null ? parseInt(home.score, 10) : 0,
          awayScore: away.score != null ? parseInt(away.score, 10) : 0,
          status: state === 'in' ? 'live' : state === 'post' ? 'final' : 'pre',
          clock: state === 'in' ? (st.displayClock ? st.displayClock : 'LIVE') : '',
          time: st.type ? st.type.detail : '',
          date: ev.date || new Date().toISOString(),
        })
      }
    } catch (e) { console.error(`  ! espn ${slug}: ${e.message}`) }
  }))
  return matches
}

/* ---------------- main ---------------- */

async function main() {
  console.log('THE DISPATCH — auto content run', new Date().toISOString())
  const start = Date.now()

  const all = []
  for (const src of SOURCES) {
    try {
      const r = await fetch(src.url, { headers: src.headers || { 'user-agent': 'dispatch-bot/1.0' } })
      if (!r.ok) { console.error(`  ! ${src.id}: HTTP ${r.status}`); continue }
      const xml = await r.text()
      const items = parseRss(xml)
      const curated = curate(items, src)
      all.push(...curated)
      console.log(`  ✓ ${src.name}: ${curated.length} stories`)
    } catch (e) {
      console.error(`  ! ${src.id}: ${e.message}`)
    }
  }

  /* dedupe */
  const seen = new Set()
  const fresh = all.filter((a) => {
    const key = normalizeTitle(a.title)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
  fresh.sort((a, b) => (b.published || '').localeCompare(a.published || ''))

  /* merge with previous run (keep window) */
  let prev = []
  try { prev = JSON.parse(fs.readFileSync(CONTENT_FILE, 'utf8')).articles || [] } catch (e) { /* first run */ }
  const cutoff = Date.now() - KEEP_OLD_HOURS * 3600 * 1000
  const old = prev.filter((a) => {
    const t = Date.parse(a.published || '')
    return t && t > cutoff && !seen.has(normalizeTitle(a.title)) && isFootball(a.title)
  })
  const merged = [...fresh, ...old].sort((a, b) => (b.published || '').localeCompare(a.published || '')).slice(0, MAX_ARTICLES)

  /* rotating hero so the edition changes every cycle */
  const runCount = Math.floor(Date.now() / 60000)
  const hero = merged[runCount % Math.max(1, Math.min(6, merged.length))] || merged[0] || null

  const content = {
    generated_at: new Date().toISOString(),
    updated_utc: new Date().toISOString().slice(0, 16) + 'Z',
    cycle: runCount,
    sources_used: SOURCES.filter((s) => all.some((a) => a.source === s.id)).map((s) => ({ id: s.id, name: s.name })),
    hero_id: hero ? hero.id : null,
    articles: merged,
  }
  fs.mkdirSync(DATA_DIR, { recursive: true })
  fs.writeFileSync(CONTENT_FILE, JSON.stringify(content, null, 1))
  console.log(`  ✓ content: ${merged.length} stories (${fresh.length} new, ${merged.length - fresh.length} carried), hero: ${hero ? hero.title.slice(0, 60) : 'none'}`)

  /* scores */
  const scores = { generated_at: new Date().toISOString(), matches: await fetchScores() }
  fs.writeFileSync(SCORES_FILE, JSON.stringify(scores, null, 1))
  const live = scores.matches.filter((m) => m.status === 'live')
  console.log(`  ✓ scores: ${scores.matches.length} matches (${live.length} live)`)

  console.log(`done in ${((Date.now() - start) / 1000).toFixed(1)}s`)
}

main().catch((e) => { console.error('fatal:', e); process.exit(1) })
