/* ============ EXTRA TIME — app logic ============ */
(() => {
  'use strict'

  const $ = (s, el = document) => el.querySelector(s)
  const $$ = (s, el = document) => [...el.querySelectorAll(s)]

  const COVERAGE = {
    bbc: { name: 'BBC Sport', color: '#bd1f3c', abbr: 'BBC' },
    guardian: { name: 'The Guardian', color: '#052962', abbr: 'GUARD' },
    independent: { name: 'The Independent', color: '#c8102e', abbr: 'IND' },
    espn: { name: 'ESPN FC', color: '#a6171d', abbr: 'ESPN' },
  }

  const state = { content: null, scores: null, tickerDup: false }

  const timeAgo = (iso) => {
    if (!iso) return ''
    const diff = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
    if (diff < 90) return 'just now'
    const m = Math.floor(diff / 60)
    if (m < 60) return `${m}m ago`
    const h = Math.floor(m / 60)
    if (h < 24) return `${h}h ago`
    return `${Math.floor(h / 24)}d ago`
  }

  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

  const kickerOf = (a) => (a.league && a.league !== 'Football' ? `${a.category} · ${a.league}` : a.category || 'Football')

  const img = (a, cls = 'aspect-16-9') => {
    const wrap = document.createElement('div')
    wrap.className = `img-wrap ${cls}`
    if (a.image) {
      const im = document.createElement('img')
      im.loading = 'lazy'
      im.decoding = 'async'
      im.alt = a.imageAlt || `${a.title} — image`
      im.src = a.image
      im.addEventListener('load', () => im.classList.add('loaded'), { once: true })
      wrap.appendChild(im)
    } else {
      wrap.style.background = 'linear-gradient(135deg, var(--paper-3), var(--paper-2))'
      wrap.appendChild(Object.assign(document.createElement('span'), { textContent: '⚽', style: 'position:absolute;inset:0;display:grid;place-items:center;font-size:34px;opacity:.5' }))
    }
    return wrap
  }

  function storyMeta(a, withSource = true) {
    const src = COVERAGE[a.source]
    const el = document.createElement('div')
    el.className = 'story-meta'
    el.innerHTML =
      (withSource && src ? `<span class="source-badge">${esc(src.abbr)}</span>` : '') +
      `<span>${withSource ? esc(src ? src.name : a.sourceName) : esc(a.category)}</span>` +
      `<span class="time-ago">${esc(timeAgo(a.published))}</span>`
    return el
  }

  /* ---------- ticker ---------- */
  function renderTicker() {
    const track = $('#tickerTrack')
    if (!track) return
    const matches = state.scores && state.scores.matches ? state.scores.matches : []
    if (!matches.length) { track.innerHTML = '<span class="ticker-empty">No live matches right now — the ticker refreshes automatically.</span>'; return }
    const mk = (m) => {
      const d = m.status === 'live' ? `<span class="t-live">${esc(m.clock || 'LIVE')}</span>`
        : m.status === 'final' ? `<span class="t-pre">FT</span>`
        : `<span class="t-pre">${esc(m.clock || m.time || 'Today')}</span>`
      return `<span class="ticker-item"><span class="t-team">${esc(m.home)}</span><span class="score">${m.status === 'pre' ? 'v' : `${m.homeScore ?? 0}–${m.awayScore ?? 0}`}</span><span class="t-team">${esc(m.away)}</span>${d}</span>`
    }
    let html = matches.map(mk).join('')
    if (!state.tickerDup && matches.length > 3) { html += html; state.tickerDup = true }
    track.innerHTML = html || '<span class="ticker-empty">No matches today.</span>'
    $('#tickerClock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  /* ---------- home ---------- */
  function renderHero() {
    const a = state.content.articles
    const lead = state.content.hero_id ? a.find((x) => x.id === state.content.hero_id) || a[0] : a[0]
    const side = a.slice(1, 3)

    const leadEl = $('#heroLead')
    leadEl.innerHTML = ''
    leadEl.appendChild(img(lead))
    const body = document.createElement('div')
    body.className = 'hero-lead-body'
    body.innerHTML =
      `<span class="hero-kicker">${esc(kickerOf(lead))}</span>` +
      `<h2>${esc(lead.title)}</h2>` +
      `<p>${esc(lead.dek)}</p>`
    body.appendChild(storyMeta(lead))
    body.querySelector('.story-meta')?.appendChild(Object.assign(document.createElement('span'), { className: 'arrow', innerHTML: '→' }))
    leadEl.appendChild(body)
    leadEl.addEventListener('click', () => location.hash = `#/story/${lead.slug}`)

    const sideEl = $('#heroSide')
    sideEl.innerHTML = ''
    side.forEach((s) => {
      const art = document.createElement('article')
      art.appendChild(img(s, 'aspect-16-10'))
      const inner = document.createElement('div')
      inner.innerHTML =
        `<span class="hero-kicker">${esc(kickerOf(s))}</span>` +
        `<h3>${esc(s.title)}</h3>` +
        `<p>${esc(s.dek)}</p>`
      inner.appendChild(storyMeta(s))
      art.appendChild(inner)
      art.addEventListener('click', () => location.hash = `#/story/${s.slug}`)
      sideEl.appendChild(art)
    })
  }

  function renderNews() {
    const grid = $('#newsGrid')
    grid.innerHTML = ''
    state.content.articles.slice(3, 19).forEach((a, i) => {
      const card = document.createElement('article')
      card.className = `story-card reveal ${i < 6 ? '' : ''}`
      card.appendChild(img(a, 'aspect-16-10'))
      const inner = document.createElement('div')
      inner.className = 'story-card-body'
      inner.innerHTML =
        `<span class="hero-kicker">${esc(kickerOf(a))}</span>` +
        `<h3>${esc(a.title)}</h3>` +
        `<p>${esc(a.dek)}</p>`
      inner.appendChild(storyMeta(a))
      card.appendChild(inner)
      card.addEventListener('click', () => location.hash = `#/story/${a.slug}`)
      grid.appendChild(card)
    })
    observeReveals()
  }

  function renderTransfers() {
    const list = $('#transferList')
    list.innerHTML = ''
    const rows = state.content.articles.filter((a) => a.category === 'Transfers & Rumours').slice(0, 8)
    if (!rows.length) { list.innerHTML = '<p class="fixture-empty">No transfer stories in the current cycle — check back soon.</p>'; return }
    rows.forEach((a) => {
      const row = document.createElement('div')
      row.className = 'transfer-row reveal'
      row.appendChild(img(a, 'transfer-thumb'))
      const mid = document.createElement('div')
      mid.innerHTML = `<span class="transfer-tag">Transfers</span><h3>${esc(a.title)}</h3>`
      mid.appendChild(storyMeta(a, false))
      row.appendChild(mid)
      const t = document.createElement('span')
      t.className = 'time-ago'
      t.textContent = timeAgo(a.published)
      row.appendChild(t)
      row.addEventListener('click', () => location.hash = `#/story/${a.slug}`)
      list.appendChild(row)
    })
    observeReveals()
  }

  function renderFixtures() {
    const grid = $('#fixturesGrid')
    grid.innerHTML = ''
    const ms = state.scores && state.scores.matches ? state.scores.matches : []
    if (!ms.length) { grid.innerHTML = '<p class="fixture-empty">Fixtures are synced on the next auto-update cycle.</p>'; return }
    const order = { live: 0, pre: 1, final: 2 }
    const sorted = ms.slice().sort((a, b) => (order[a.status] ?? 3) - (order[b.status] ?? 3))
    const today = new Date().toDateString()
    const todayMs = sorted.filter((m) => new Date(m.date).toDateString() === today)
    const list = (todayMs.length ? todayMs : sorted).slice(0, 12)

    list.forEach((m) => {
      const st = m.status === 'live' ? `<span class="f-status live">${esc(m.clock || 'LIVE')}</span>`
        : m.status === 'final' ? `<span class="f-status final">Full time</span>`
        : `<span class="f-status pre">${esc(m.clock || m.time || 'Upcoming')}</span>`
      const logo = (u, name) => u ? `<img class="f-logo" src="${esc(u)}" alt="" loading="lazy">` : `<span class="f-logo" style="background:var(--paper-3);border-radius:50%"></span>`
      const card = document.createElement('div')
      card.className = 'fixture-card reveal'
      card.innerHTML =
        `<span class="fixture-league">${esc(m.league)}</span>` +
        `<div class="fixture-status">${st}<span class="f-score">${m.status === 'pre' ? '' : `${m.homeScore ?? 0} – ${m.awayScore ?? 0}`}</span></div>` +
        `<div class="fixture-teams">` +
        `<div class="f-row"><span class="f-left">${logo(m.homeLogo, m.home)}<span class="t">${esc(m.home)}</span></span><span class="s">${m.status === 'pre' ? '' : (m.homeScore ?? 0)}</span></div>` +
        `<div class="f-row"><span class="f-left">${logo(m.awayLogo, m.away)}<span class="t">${esc(m.away)}</span></span><span class="s">${m.status === 'pre' ? '' : (m.awayScore ?? 0)}</span></div>` +
        `</div>`
      grid.appendChild(card)
    })
    observeReveals()
    $('#fixturesNote').textContent = `synced ${timeAgo(state.scores.generated_at)} · auto-refreshes`
  }

  function renderSources() {
    const grid = $('#sourcesGrid')
    grid.innerHTML = ''
    Object.values(COVERAGE).forEach((s) => {
      const card = document.createElement('div')
      card.className = 'source-card reveal'
      card.innerHTML =
        `<span class="source-logo" style="background:${s.color}">${esc(s.abbr)}</span>` +
        `<div><h3>${esc(s.name)}</h3><p>Reporting aggregated &amp; edited in-house</p></div>`
      grid.appendChild(card)
    })
    observeReveals()
  }

  /* ---------- story page (hosted on our site) ---------- */
  function renderStory(slug) {
    const main = $('#main')
    const view = $('#storyView')
    const a = state.content && state.content.articles.find((x) => x.slug === slug)
    if (!a) { location.hash = '#/'; return }
    main.hidden = true
    view.hidden = false
    document.title = `${a.title} — Extra Time`

    view.innerHTML = ''
    const wrap = document.createElement('div')
    wrap.className = 'story-wrap'
    wrap.innerHTML =
      `<a class="story-back" href="#/">← Back to home</a>` +
      `<div class="story-hero">${img(a).outerHTML}${a.imageCredit ? `<p class="img-caption">Photo: ${esc(a.imageCredit)}</p>` : ''}</div>` +
      `<span class="hero-kicker">${esc(kickerOf(a))}</span>` +
      `<h1 class="story-title">${esc(a.title)}</h1>` +
      `<p class="story-dek">${esc(a.dek)}</p>` +
      `<div class="story-meta"></div>` +
      `<hr class="story-divider">` +
      `<div class="story-body"></div>` +
      `<div class="story-note"><strong>Extra Time editor's note:</strong> this story was compiled and edited in-house from reporting published by ${esc(a.sourceName)}. All content on this page is hosted by us; no external links required.</div>`
    wrap.querySelector('.story-meta').appendChild(storyMeta(a))
    const body = wrap.querySelector('.story-body')
    ;(a.body && a.body.length ? a.body : [a.dek]).forEach((p) => {
      const el = document.createElement('p')
      el.textContent = p
      body.appendChild(el)
    })
    const related = state.content.articles.filter((x) => x.slug !== slug).slice(0, 2)
    const more = document.createElement('div')
    more.className = 'story-more'
    more.innerHTML = '<h3>More from today\'s edition</h3>'
    const grid = document.createElement('div')
    grid.className = 'story-more-grid'
    related.forEach((r) => {
      const card = document.createElement('div')
      card.className = 'story-more-card'
      const im = img(r, 'aspect-16-10')
      card.appendChild(im)
      const right = document.createElement('div')
      right.innerHTML = `<h4>${esc(r.title)}</h4>`
      right.appendChild(storyMeta(r))
      card.appendChild(right)
      card.addEventListener('click', () => location.hash = `#/story/${r.slug}`)
      grid.appendChild(card)
    })
    more.appendChild(grid)
    wrap.appendChild(more)
    view.appendChild(wrap)
    window.scrollTo({ top: 0, behavior: 'instant' in window ? 'instant' : 'auto' })
  }

  function renderHome() {
    const main = $('#main')
    const view = $('#storyView')
    main.hidden = false
    view.hidden = true
    document.title = 'Extra Time — Football, Every Day'
    if (!state.content || !state.content.articles || !state.content.articles.length) {
      $('#heroLead').innerHTML = '<div class="hero-skeleton">The desk is warming up — the first edition lands on the next auto-update cycle (within 30 minutes).</div>'
      $('#newsGrid').innerHTML = '<div class="grid-skeleton">Stories are being curated from BBC, Guardian, Independent &amp; ESPN…</div>'
      $('#tickerTrack').innerHTML = '<span class="ticker-empty">Fetching live scores…</span>'
      return
    }
    renderHero(); renderNews(); renderTransfers(); renderSources()
    $('#footerUpdated').textContent = `Updated: ${new Date(state.content.generated_at).toLocaleString()}`
  }

  /* ---------- router ---------- */
  function route() {
    const h = location.hash || '#/'
    if (h.startsWith('#/story/')) {
      if (!state.content) return
      renderStory(h.replace('#/story/', '').split('?')[0])
      closeMenu()
    } else {
      const sections = ['news', 'transfers', 'fixtures', 'sources']
      renderHome()
      const anchor = h.replace('#/', '')
      if (anchor && sections.includes(anchor)) {
        requestAnimationFrame(() => {
          const el = $('#' + anchor)
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
        })
      } else if (h !== '#/') {
        window.scrollTo({ top: 0, behavior: 'auto' })
      }
      closeMenu()
    }
  }
  window.addEventListener('hashchange', route)

  /* ---------- reveal on scroll ---------- */
  let io = null
  function observeReveals() {
    if (!('IntersectionObserver' in window)) { $$('.reveal').forEach((el) => el.classList.add('in')); return }
    if (!io) {
      io = new IntersectionObserver((ents) => {
        ents.forEach((en) => { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target) } })
      }, { threshold: 0.08, rootMargin: '0px 0px -24px' })
    }
    $$('.reveal').forEach((el) => io.observe(el))
  }

  /* ---------- toast ---------- */
  let toastTimer = null
  function toast(msg) {
    const t = $('#toast')
    t.textContent = msg
    t.classList.add('show')
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => t.classList.remove('show'), 2400)
  }

  /* ---------- header date / clock ---------- */
  function setMastheadDate() {
    $('#mastheadDate').textContent = new Date().toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
  }
  setInterval(() => { $('#tickerClock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }, 30000)

  /* ---------- live refresh (client-side ESPN) ---------- */
  const ESPN_LEAGUES = [
    ['eng.1', 'Premier League'], ['esp.1', 'La Liga'], ['ger.1', 'Bundesliga'],
    ['ita.1', 'Serie A'], ['fra.1', 'Ligue 1'],
  ]
  async function fetchLiveScores() {
    try {
      const all = []
      await Promise.all(ESPN_LEAGUES.map(async ([slug, name]) => {
        const r = await fetch(`https://site.api.espn.com/apis/site/v2/sports/soccer/${slug}/scoreboard`)
        if (!r.ok) return
        const j = await r.json()
        j.events.forEach((ev) => {
          const c = ev.competitions[0]
          const st = c.status || {}
          const isLive = st.type && st.type.state === 'in'
          const isFinal = st.type && st.type.state === 'post'
          const home = c.competitors.find((x) => x.homeAway === 'home')
          const away = c.competitors.find((x) => x.homeAway === 'away')
          if (!home || !away) return
          all.push({
            league: name, home: home.team.displayName, away: away.team.displayName,
            homeLogo: home.team.logo || '', awayLogo: away.team.logo || '',
            homeScore: home.score != null ? parseInt(home.score, 10) : 0,
            awayScore: away.score != null ? parseInt(away.score, 10) : 0,
            status: isLive ? 'live' : isFinal ? 'final' : 'pre',
            clock: isLive ? (st.displayClock ? `${st.displayClock}'` : 'LIVE') : '',
            time: st.type.detail || '', date: ev.date,
          })
        })
      }))
      if (all.length) {
        state.scores = { generated_at: new Date().toISOString(), matches: all }
        state.tickerDup = false
        renderTicker()
        renderFixtures()
      }
    } catch (e) { /* keep cached scores */ }
  }

  /* ---------- boot ---------- */
  async function loadData() {
    try {
      const r = await fetch('data/content.json', { cache: 'no-cache' })
      if (r.ok) state.content = await r.json()
    } catch (e) { /* offline */ }
    try {
      const r2 = await fetch('data/scores.json', { cache: 'no-cache' })
      if (r2.ok) state.scores = await r2.json()
    } catch (e) { /* ignore */ }
    route()
    renderTicker()
    renderFixtures()
    setMastheadDate()
    $('#footerYear').textContent = new Date().getFullYear()
  }

  /* ---------- nav / header interactions ---------- */
  const navToggle = $('#navToggle')
  const navList = $('#navList')
  const navBackdrop = $('#navBackdrop')
  function setMenu(open) {
    navList.classList.toggle('open', open)
    navToggle.setAttribute('aria-expanded', String(open))
    if (navBackdrop) navBackdrop.hidden = !open
  }
  function closeMenu() { setMenu(false) }
  navToggle.addEventListener('click', () => {
    const open = !navList.classList.contains('open')
    setMenu(open)
    if (open) navList.querySelector('a')?.focus()
  })
  $$('#navList a').forEach((a) => a.addEventListener('click', closeMenu))
  if (navBackdrop) navBackdrop.addEventListener('click', closeMenu)
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMenu() })

  const navLinks = $$('#navList a')
  const spyEls = ['news', 'transfers', 'fixtures', 'sources'].map((id) => $('#' + id))
  const spy = new IntersectionObserver((ents) => {
    ents.forEach((en) => {
      if (!en.isIntersecting) return
      navLinks.forEach((a) => a.classList.toggle('active', a.getAttribute('href') === '#/' + en.target.id))
    })
  }, { rootMargin: '-40% 0px -55% 0px' })
  spyEls.forEach((s) => s && spy.observe(s))

  $('#refreshBtn').addEventListener('click', async (e) => {
    const btn = e.currentTarget
    btn.classList.add('spinning')
    await Promise.all([loadData(), fetchLiveScores()])
    btn.classList.remove('spinning')
    toast('Content refreshed')
  })

  loadData()
  fetchLiveScores()
  setInterval(fetchLiveScores, 120000)
})()
