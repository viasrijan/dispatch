#!/usr/bin/env node
/* ============================================================
   EXTRA TIME — auto content engine
   Fetches football headlines from credible RSS sources, curates
   and EDITS them into our own editorial style, sources free
   images from Wikimedia Commons, and posts the result as
   data/content.json + live scores as data/scores.json.
   Runs on a 30-minute GitHub Actions cron.
   ============================================================ */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const DATA_DIR = path.join(__dirname, '..', 'data')
const CONTENT_FILE = path.join(DATA_DIR, 'content.json')
const SCORES_FILE = path.join(DATA_DIR, 'scores.json')

const UA = { 'user-agent': 'ExtraTime-bot/1.0 (https://github.com/viasrijan/dispatch)' }

const SOURCES = [
  { id: 'bbc', name: 'BBC Sport', url: 'https://feeds.bbci.co.uk/sport/football/rss.xml' },
  { id: 'guardian', name: 'The Guardian', url: 'https://www.theguardian.com/football/rss' },
  { id: 'independent', name: 'The Independent', url: 'https://www.independent.co.uk/sport/football/rss', headers: { ...UA, 'user-agent': 'Mozilla/5.0' } },
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
    items.push({ title, link: grab('link'), description: grab('description'), published: parseDate(grab('pubDate')) })
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
    .replace(/\b(the|a|an|to|of|in|for|on|at|by|and|is|as|with|from)\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

const editTitle = (t) => {
  let clean = decodeEntities(t).replace(/\s+/g, ' ').trim()
  clean = clean.replace(/^(football|soccer|transfer|report)[:\s]+/i, '')
  if (clean.length <= 110) return clean
  const cut = clean.slice(0, 110)
  return cut.slice(0, cut.lastIndexOf(' ')) + '…'
}

const slugOf = (id, title) => {
  const s = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60)
  return `${s || 'story'}-${id.slice(-5)}`
}

const excerptOf = (d) => {
  const t = stripHtml(d || '')
  if (!t) return ''
  if (t.length <= 170) return t
  return t.slice(0, t.lastIndexOf(' ', 170)) + '…'
}

const CATEGORY_RULES = [
  ['Transfers & Rumours', ['transfer', 'move to', 'signs', 'signing', 'loan', 'contract', 'release clause', 'bid for', 'switch to', 'joins', 'departure', 'extends ', 'extension', 'price tag', 'wanted by', 'targeted by']],
  ['Match Reports', ['beat ', 'defeat', ' won ', 'wins', ' victory', 'thrash', 'hammer', 'comeback', 'hat-trick', 'strikes', 'net', 'draw ', 'scored', 'stunner', 'battles', 'progress']],
  ['Injuries', ['injured', 'injury', 'blow', 'ruled out', 'out for', 'fitness', 'doubt', 'side-lined', 'sidelined']],
  ['Tactics & Analysis', ['analysis', 'tactics', 'explain', 'verdict', 'talking points', 'how ', 'why ', 'positional', 'formation', 'press conference', 'in numbers', 'data']],
  ['Previews', ['preview', 'team news', 'predicted', 'ahead of', 'line-up', 'lineup', 'odds']],
  ['News', ['confirms', 'announces', 'announced', 'appointed', 'sacked', 'fined', 'banned', 'award', 'wins award', 'calls up', 'recalled', 'retires', 'retirement']],
]

const LEAGUE_RULES = [
  ['Premier League', ['premier league', 'epl', 'arsenal', 'chelsea', 'liverpool', 'manchester', 'man utd', 'man city', 'tottenham', 'newcastle', 'aston villa', 'everton', 'west ham', 'brighton', 'crystal palace', 'fulham', 'brentford', 'wolves', 'nottingham', 'leicester', 'southampton', 'leeds', 'burnley', 'bournemouth', 'birmingham']],
  ['Champions League', ['champions league', 'ucl']],
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
  'pegula', 'eala', 'sabalenka', 'swiatek', 'rybakina', 'djokovic', 'alcaraz',
  'jockey', 'racecourse', 'racing', 'nap of the day', 'race meeting', 'flat racing',
  'ice hockey', 'super league', 'boxing ring',
]

const TEAM_SEARCH = [
  ['arsenal', 'Arsenal'], ['chelsea', 'Chelsea'], ['liverpool', 'Liverpool'], ['man utd', 'Manchester United'], ['manchester united', 'Manchester United'],
  ['man city', 'Manchester City'], ['tottenham', 'Tottenham Hotspur'], ['newcastle', 'Newcastle United'], ['aston villa', 'Aston Villa'],
  ['everton', 'Everton'], ['west ham', 'West Ham United'], ['brighton', 'Brighton & Hove Albion'], ['crystal palace', 'Crystal Palace'],
  ['fulham', 'Fulham'], ['brentford', 'Brentford'], ['wolves', 'Wolverhampton Wanderers'], ['nottingham', 'Nottingham Forest'],
  ['leicester', 'Leicester City'], ['southampton', 'Southampton'], ['leeds', 'Leeds United'], ['bournemouth', 'Bournemouth'],
  ['birmingham', 'Birmingham City'], ['real madrid', 'Real Madrid'], ['barcelona', 'FC Barcelona'], ['atletico', 'Atlético Madrid'],
  ['sevilla', 'Sevilla'], ['valencia', 'Valencia CF'], ['villarreal', 'Villarreal'], ['real sociedad', 'Real Sociedad'],
  ['juventus', 'Juventus'], ['ac milan', 'AC Milan'], ['inter ', 'Inter Milan'], ['napoli', 'Napoli'], ['roma', 'AS Roma'],
  ['lazio', 'Lazio'], ['atalanta', 'Atalanta'], ['bayern', 'Bayern Munich'], ['dortmund', 'Borussia Dortmund'],
  ['leipzig', 'RB Leipzig'],   ['leverkusen', 'Bayer Leverkusen'], ['psg', 'Paris Saint-Germain'], ['paris saint', 'Paris Saint-Germain'],
  ['marseille', 'Olympique Marseille'], ['lyon', 'Olympique Lyonnais'], ['monaco', 'AS Monaco'],
  ['celtic', 'Celtic FC'], ['rangers', 'Rangers FC'], ['galaxy', 'LA Galaxy'], ['lask', 'LASK'],
  ['como', 'Como 1907'], ['fenerbahce', 'Fenerbahçe'], ['fenerbahçe', 'Fenerbahçe'], ['galatasaray', 'Galatasaray'],
  ['psv', 'PSV Eindhoven'], ['club brugge', 'Club Brugge'], ['red star', 'Red Star Belgrade'],
  ['slovan', 'Slovan Bratislava'], ['young boys', 'Young Boys'], ['sparta prague', 'Sparta Prague'],
  ['shakhtar', 'Shakhtar Donetsk'], ['feyenoord', 'Feyenoord'], ['porto', 'FC Porto'],
  ['benfica', 'Benfica'], ['sporting lisbon', 'Sporting CP'], ['milan', 'AC Milan'],
  ['usmnt', 'USMNT'], ['united states men', 'USMNT'], ['usa women', 'USWNT'],
]

const CATEGORY_IMAGE = {
  'Transfers & Rumours': 'soccer player',
  'Match Reports': 'soccer match',
  'Injuries': 'soccer injury',
  'Tactics & Analysis': 'soccer stadium',
  'Previews': 'soccer team',
  'News': 'soccer stadium crowd',
}

const isFootball = (text) => !NON_FOOTBALL_RULES.some((w) => (' ' + text.toLowerCase() + ' ').includes(w))
const matchAny = (text, rules) => {
  const t = ' ' + text.toLowerCase() + ' '
  for (const [label, words] of rules) {
    if (words.some((w) => t.includes(w))) return label
  }
  return null
}

const CLOSERS = {
  'Transfers & Rumours': "Details and medical terms are still subject to confirmation. We'll keep tracking this story and bring you developments as they land.",
  'Match Reports': "The result continues to shape the season picture — we'll have more reaction, statistics and analysis in the coming hours.",
  'Injuries': "Recovery timelines in football are rarely fixed. We'll monitor the situation and update this story as club statements arrive.",
  'Tactics & Analysis': "The broader tactical picture will sharpen as more data comes in — this story will be updated with fresh numbers and context.",
  'Previews': "Team news can change right up to kick-off. Bookmark this story for the final line-ups and confirmed sides.",
  'News': "Developments in this story are expected over the coming hours — check back for our next edition, which auto-publishes within 30 minutes.",
}

/* ---------------- editorial body (our own style) ---------------- */

const sentences = (text) => text.match(/[^.!?]+[.!?]+/g) || []

function buildBody(article) {
  const pars = []
  const lead = article.dek
  if (lead) pars.push(`Our briefing: ${lead}`)
  const sents = sentences(article.description)
  let chunk = []
  for (const s of sents) {
    chunk.push(s.trim())
    if (chunk.length === 3) { pars.push(chunk.join(' ')); chunk = [] }
  }
  if (chunk.length) pars.push(chunk.join(' '))
  if (!pars.length) pars.push(`Details are still coming in on this story. We'll expand this report in our next auto-published edition.`)
  pars.push(CLOSERS[article.category] || CLOSERS.News)
  pars.push(`This summary was compiled from reporting published by ${article.sourceName}.`)
  return pars
}

/* ---------------- images (Wikimedia Commons, free & attribution-safe, hotlinkable) ----------------
   Copyright strategy: prefer Public Domain / CC0 images (no attribution needed).
   Accept CC BY / CC BY-SA / CC BY-ND (attribution kept in data, shown as a small
   caption below the hero image — never overlaid on the photo). Reject CC BY-NC
   and anything non-free. Relevance: for team stories the photo file must mention
   the club name; logos/crests/badges/maps etc. are excluded. */

const photoCache = new Map()
const usedImages = new Set()

const BAD_FILE_WORDS = /(logo|crest|badge|emblem|wappen|coat of arms|shield|kit |jersey|t-shirt|scarf|certificate|programme|program |ticket|stamp|poster|screenshot|map |flag of|roundel|match ball|american football|gridiron|super bowl|\bnfl\b|guide|novel|fortune|archive\.org)/i

const RELEVANT_WORDS = ['soccer', 'stadium', 'match', 'player', 'crowd', 'derby', 'cup', 'league', 'training', 'goal', 'pitch', 'fans', 'coach', 'final', 'champion', 'striker', 'goalkeeper']

const stripTags = (s) => String(s || '').replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&#0?39;/g, "'").replace(/&quot;/g, '"').replace(/\s+/g, ' ').trim()

const licenseKind = (lic) => {
  const l = (lic || '').toLowerCase()
  if (/(public domain|cc[- ]?0|cc-zero|no restrictions)/.test(l)) return 'free'
  if (/^(cc( |[-]?by| by|by-)(sa|nd)?)/.test(l) && !/nc/.test(l)) return 'attrib'
  if (/\bgfdl\b/.test(l)) return 'attrib'
  return null
}

async function commonsPhoto(query, opts = {}) {
  const key = query + '|' + (opts.require ? opts.require.join(',') : '') + '|' + (opts.any ? 1 : 0)
  if (photoCache.has(key)) return photoCache.get(key)
  const url = 'https://commons.wikimedia.org/w/api.php?' + new URLSearchParams({
    action: 'query', format: 'json', generator: 'search',
    gsrsearch: query, gsrnamespace: '6', gsrlimit: '6',
    prop: 'imageinfo', iiprop: 'url|size|extmetadata', iiurlwidth: '900',
  })
  const out = []
  try {
    const r = await fetch(url, { headers: UA, signal: AbortSignal.timeout(8000) })
    const j = await r.json()
    const pages = j.query && j.query.pages
    if (pages) {
      const vals = Object.values(pages).sort((a, b) => (a.index || 99) - (b.index || 99))
      for (const v of vals) {
        const ii = v.imageinfo && v.imageinfo[0]
        if (!ii || !ii.thumburl) continue
        if (!/\.(jpe?g|png)(\?|$)/i.test(ii.thumburl)) continue
        if (ii.width && ii.width < (opts.minWidth || 800)) continue
        const fileTitle = v.title.replace(/^File:/, '')
        if (BAD_FILE_WORDS.test(fileTitle)) continue
        if (opts.require && !opts.require.some((r) => fileTitle.toLowerCase().includes(r))) continue
        if (opts.any && !RELEVANT_WORDS.some((w) => fileTitle.toLowerCase().includes(w))) continue
        const meta = ii.extmetadata || {}
        const lic = (meta.LicenseShortName && meta.LicenseShortName.value) || ''
        const kind = licenseKind(lic)
        if (!kind) continue
        const artist = stripTags(meta.Artist && meta.Artist.value)
        if (kind === 'attrib' && (!artist || /\.(jpe?g|png)$/i.test(artist))) continue
        out.push({
          url: ii.thumburl,
          credit: kind === 'attrib' && artist ? `${artist} — ${lic}` : null,
        })
      }
    }
  } catch (e) { /* no image */ }
  photoCache.set(key, out)
  return out
}

const CATEGORY_KEYWORD = {
  'Transfers & Rumours': 'transfer',
  'Match Reports': 'match',
  'Injuries': 'injury',
  'Tactics & Analysis': 'stadium',
  'Previews': 'match',
  'News': 'stadium',
}

function queriesFor(article) {
  const t = article.title.toLowerCase()
  let team = ''
  let teamKey = ''
  for (const [k, name] of TEAM_SEARCH) if (t.includes(k)) { team = name; teamKey = k.trim(); break }
  const kw = CATEGORY_KEYWORD[article.category] || 'football'
  const qs = []
  if (team) {
    const req = [team.toLowerCase(), teamKey].filter(Boolean)
    qs.push({ q: `${team} ${kw}`, require: req })
    qs.push({ q: `${team} soccer`, require: req })
    qs.push({ q: `${team} stadium`, require: req })
    qs.push({ q: `${team} football`, require: req })
  }
  qs.push({ q: CATEGORY_IMAGE[article.category] || 'soccer stadium crowd', any: true })
  qs.push({ q: 'soccer match', any: true })
  qs.push({ q: 'soccer stadium', any: true })
  qs.push({ q: 'soccer fans', any: true })
  return qs
}

async function attachImage(article) {
  try {
    for (const { q, require, any } of queriesFor(article)) {
      const photos = await commonsPhoto(q, { require, any })
      const pick = photos.find((p) => !usedImages.has(p.url))
      if (pick) {
        usedImages.add(pick.url)
        article.image = pick.url
        article.imageCredit = pick.credit
        break
      }
    }
  } catch (e) { /* keep no image */ }
}

/* ---------------- scores ---------------- */

const ESPN_LEAGUES = [
  ['eng.1', 'Premier League'], ['esp.1', 'La Liga'], ['ger.1', 'Bundesliga'],
  ['ita.1', 'Serie A'], ['fra.1', 'Ligue 1'],
]

async function fetchScores() {
  const matches = []
  await Promise.all(ESPN_LEAGUES.map(async ([slug, name]) => {
    try {
      const r = await fetch(`https://site.api.espn.com/apis/site/v2/sports/soccer/${slug}/scoreboard`, { headers: UA })
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
          homeLogo: (home.team.logo || '').replace('/60.png', '/120.png'),
          awayLogo: (away.team.logo || '').replace('/60.png', '/120.png'),
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
  console.log('EXTRA TIME — auto content run', new Date().toISOString())
  const start = Date.now()

  const all = []
  for (const src of SOURCES) {
    try {
      const r = await fetch(src.url, { headers: src.headers || UA })
      if (!r.ok) { console.error(`  ! ${src.id}: HTTP ${r.status}`); continue }
      const xml = await r.text()
      const items = parseRss(xml)
      const curated = items
        .filter((i) => i.link && i.title.length > 8 && isFootball(i.title + ' ' + i.description))
        .map((i) => {
          const category = matchAny(i.title + ' ' + i.description, CATEGORY_RULES) || 'News'
          const league = matchAny(i.title, LEAGUE_RULES) || 'Football'
          const norm = normalizeTitle(i.title)
          const id = src.id + '-' + norm.replace(/\s+/g, '-').slice(0, 48)
          const title = editTitle(i.title)
          const dek = excerptOf(i.description)
          return {
            id,
            slug: slugOf(id, title),
            title,
            dek,
            description: stripHtml(i.description),
            category,
            league,
            source: src.id,
            sourceName: src.name,
            published: i.published || new Date().toISOString(),
            fetched_at: new Date().toISOString(),
          }
        })
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

  /* merge with previous run (keep window, keep images/body of carried stories) */
  let prev = []
  try { prev = JSON.parse(fs.readFileSync(CONTENT_FILE, 'utf8')).articles || [] } catch (e) { /* first run */ }
  const prevById = new Map(prev.map((a) => [a.id, a]))
  const cutoff = Date.now() - KEEP_OLD_HOURS * 3600 * 1000
  const old = prev.filter((a) => {
    const t = Date.parse(a.published || '')
    return t && t > cutoff && !seen.has(normalizeTitle(a.title)) && isFootball(a.title)
  })

  /* editorial authoring + images */
  for (const a of fresh) {
    a.dek = a.dek || excerptOf(a.description)
    a.body = buildBody(a)
  }
  for (const a of old) {
    const p = prevById.get(a.id)
    a.body = p && p.body ? p.body : buildBody(a)
    a.image = p && p.image ? p.image : undefined
    a.imageCredit = p && p.imageCredit ? p.imageCredit : undefined
  }

  const merged = [...fresh, ...old].sort((a, b) => (b.published || '').localeCompare(a.published || '')).slice(0, MAX_ARTICLES)

  /* images only for the stories that will actually ship */
  for (const a of merged) {
    if (!a.image) await attachImage(a)
  }

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
  const withImg = merged.filter((a) => a.image).length
  console.log(`  ✓ content: ${merged.length} stories (${fresh.length} new), ${withImg} with images, hero: ${hero ? hero.title.slice(0, 60) : 'none'}`)

  const scores = { generated_at: new Date().toISOString(), matches: await fetchScores() }
  fs.writeFileSync(SCORES_FILE, JSON.stringify(scores, null, 1))
  const live = scores.matches.filter((m) => m.status === 'live')
  console.log(`  ✓ scores: ${scores.matches.length} matches (${live.length} live)`)

  console.log(`done in ${((Date.now() - start) / 1000).toFixed(1)}s`)
}

main().catch((e) => { console.error('fatal:', e); process.exit(1) })
