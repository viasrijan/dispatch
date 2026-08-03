/* ============ THE DISPATCH — app logic ============ */
(() => {
  'use strict'

  const $ = (s, el = document) => el.querySelector(s)
  const $$ = (s, el = document) => [...el.querySelectorAll(s)]

  const SOURCES = {
    bbc: { name: 'BBC Sport', home: 'https://www.bbc.com/sport/football', color: '#bd1f3c', abbr: 'BBC' },
    guardian: { name: 'The Guardian', home: 'https://www.theguardian.com/football', color: '#052962', abbr: 'GUARD' },
    independent: { name: 'The Independent', home: 'https://www.independent.co.uk/sport/football', color: '#c8102e', abbr: 'IND' },
    espn: { name: 'ESPN FC', home: 'https://www.espn.com/soccer', color: '#a6171d', abbr: 'ESPN' },
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

  const kickerOf = (a) => a.league ? `${a.category} · ${a.league}` : (a.category || 'Football')

  function storyMeta(a) {
    const src = SOURCES[a.source] || SOURCES.espn
    const el = document.createElement('div')
    el.className = 'story-meta'
    el.innerHTML =
      `<span class="source-badge ${esc(a.source)}">${esc(src.abbr)}</span>` +
      `<span>${esc(src.name)}</span>` +
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
        : m.status === 'final' ? `<span class="score" style="color:${m.homeScore > m.awayScore ? '#ffb347' : m.homeScore < m.awayScore ? '#ffb347' : ''}">${m.homeScore}–${m.awayScore} FT</span>`
        : `<span class="t-pre">${esc(m.clock || m.time || 'Today')}</span>`
      return `<span class="ticker-item"><span class="t-team">${esc(m.home)}</span><span class="score">${m.status === 'pre' ? 'v' : `${m.homeScore ?? 0}–${m.awayScore ?? 0}`}</span><span class="t-team">${esc(m.away)}</span>${d}</span>`
    }
    let html = matches.map(mk).join('')
    if (!state.tickerDup && matches.length > 3) { html += html; state.tickerDup = true }
    track.innerHTML = html || '<span class="ticker-empty">No matches today.</span>'
    $('#tickerClock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  /* ---------- hero ---------- */
  function renderHero() {
    const a = state.content.articles
    const lead = state.content.hero || a[0]
    const side = a.slice(1, 3)

    const leadEl = $('#heroLead')
    leadEl.innerHTML = ''
    const body = document.createElement('div')
    body.className = 'hero-lead-body'
    body.innerHTML =
      `<span class="hero-kicker">${esc(kickerOf(lead))}</span>` +
      `<h2>${esc(lead.title)}</h2>` +
      `<p>${esc(lead.excerpt)}</p>`
    body.appendChild(storyMeta(lead))
    body.querySelector('.story-meta')?.appendChild(Object.assign(document.createElement('span'), { className: 'arrow', innerHTML: '→' }))
    leadEl.appendChild(body)
    leadEl.addEventListener('click', () => openArticle(lead))

    const sideEl = $('#heroSide')
    sideEl.innerHTML = ''
    side.forEach((s, i) => {
      const art = document.createElement('article')
      art.innerHTML =
        `<span class="hero-kicker">${esc(kickerOf(s))}</span>` +
        `<h3>${esc(s.title)}</h3>` +
        `<p>${esc(s.excerpt)}</p>`
      art.appendChild(storyMeta(s))
      art.addEventListener('click', () => openArticle(s))
      sideEl.appendChild(art)
    })
  }

  /* ---------- news grid ---------- */
  function renderNews() {
    const grid = $('#newsGrid')
    grid.innerHTML = ''
    state.content.articles.slice(3, 19).forEach((a, i) => {
      const card = document.createElement('article')
      card.className = `story-card reveal ${i < 6 ? '' : 'reveal-late'}`
      card.innerHTML =
        `<span class="hero-kicker">${esc(kickerOf(a))}</span>` +
        `<h3>${esc(a.title)}</h3>` +
        `<p>${esc(a.excerpt)}</p>`
      card.appendChild(storyMeta(a))
      card.addEventListener('click', () => openArticle(a))
      grid.appendChild(card)
    })
    observeReveals()
  }

  /* ---------- transfers ---------- */
  function renderTransfers() {
    const list = $('#transferList')
    list.innerHTML = ''
    const rows = state.content.articles.filter((a) => a.category === 'Transfers & Rumours').slice(0, 8)
    if (!rows.length) { list.innerHTML = '<p class="fixture-empty">No transfer stories in the current cycle — check back soon.</p>'; return }
    rows.forEach((a) => {
      const row = document.createElement('div')
      row.className = 'transfer-row reveal'
      row.innerHTML =
        `<span class="transfer-tag">Transfers</span>` +
        `<div><h3>${esc(a.title)}</h3><p style="font-size:12.5px;color:var(--muted)">${esc(a.excerpt.slice(0, 130))}</p></div>`
      const meta = storyMeta(a)
      const t = meta.querySelector('.time-ago')
      if (t) { t.parentElement.removeChild(t) }
      row.appendChild(meta)
      row.addEventListener('click', () => openArticle(a))
      list.appendChild(row)
    })
    observeReveals()
  }

  /* ---------- fixtures ---------- */
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
      const card = document.createElement('div')
      card.className = 'fixture-card reveal'
      card.innerHTML =
        `<span class="fixture-league">${esc(m.league)}</span>` +
        `<div class="fixture-status">${st}<span class="f-score">${m.status === 'pre' ? '' : `${m.homeScore ?? 0} – ${m.awayScore ?? 0}`}</span></div>` +
        `<div class="fixture-teams">` +
        `<div class="f-row"><span class="t">${esc(m.home)}</span><span class="s">${m.status === 'pre' ? '' : (m.homeScore ?? 0)}</span></div>` +
        `<div class="f-row"><span class="t">${esc(m.away)}</span><span class="s">${m.status === 'pre' ? '' : (m.awayScore ?? 0)}</span></div>` +
        `</div>`
      grid.appendChild(card)
    })
    observeReveals()
    $('#fixturesNote').textContent = `synced ${timeAgo(state.scores.generated_at)} · auto-refreshes`
  }

  /* ---------- sources ---------- */
  function renderSources() {
    const grid = $('#sourcesGrid')
    grid.innerHTML = ''
    Object.values(SOURCES).forEach((s, i) => {
      const card = document.createElement('a')
      card.className = 'source-card reveal'
      card.href = s.home
      card.target = '_blank'
      card.rel = 'noreferrer'
      card.innerHTML =
        `<span class="source-logo" style="background:${s.color}">${esc(s.abbr)}</span>` +
        `<div><h3>${esc(s.name)}</h3><p>Football desk — live feed</p></div>`
      grid.appendChild(card)
    })
    observeReveals()
  }

  /* ---------- article modal ---------- */
  const modal = $('#articleModal')
  let lastFocus = null

  function openArticle(a) {
    if (!a) return
    lastFocus = document.activeElement
    const src = SOURCES[a.source] || SOURCES.espn
    $('#modalArticle').innerHTML =
      `<span class="hero-kicker">${esc(kickerOf(a))}</span>` +
      `<h2 id="modalTitle">${esc(a.title)}</h2>` +
      `<div class="story-meta"><span class="source-badge ${esc(a.source)}">${esc(src.abbr)}</span><span>${esc(src.name)}</span><span class="time-ago">${esc(timeAgo(a.published))}</span></div>` +
      `<div class="modal-body">${esc(a.body || a.excerpt || '')}</div>` +
      `<a class="modal-original" href="${esc(a.link)}" target="_blank" rel="noreferrer">Read original at ${esc(src.name)} →</a>`
    modal.classList.add('open')
    modal.setAttribute('aria-hidden', 'false')
    document.body.style.overflow = 'hidden'
    const close = $('.modal-close', modal)
    close.focus()
    close.scrollIntoView({ block: 'nearest' })
  }
  function closeModal() {
    modal.classList.remove('open')
    modal.setAttribute('aria-hidden', 'true')
    document.body.style.overflow = ''
    if (lastFocus) lastFocus.focus()
  }
  $$('[data-close]', modal).forEach((b) => b.addEventListener('click', closeModal))
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('open')) closeModal()
  })

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
    const d = new Date()
    $('#mastheadDate').textContent = d.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
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
            homeScore: home.score != null ? parseInt(home.score, 10) : 0,
            awayScore: away.score != null ? parseInt(away.score, 10) : 0,
            status: isLive ? 'live' : isFinal ? 'final' : 'pre',
            clock: isLive ? (st.displayClock ? `${st.displayClock}'` : 'LIVE') : '',
            time: st.type.detail || '',
            date: ev.date,
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
    const headers = document.querySelector('html')
    let contentOk = false
    try {
      const r = await fetch('data/content.json', { cache: 'no-cache' })
      if (r.ok) { state.content = await r.json(); contentOk = true }
    } catch (e) { /* offline */ }
    try {
      const r2 = await fetch('data/scores.json', { cache: 'no-cache' })
      if (r2.ok) state.scores = await r2.json()
    } catch (e) { /* ignore */ }

    if (!state.content || !state.content.articles || !state.content.articles.length) {
      $('#heroLead').innerHTML = '<div class="hero-skeleton">The dispatch desk is warming up — first edition lands on the next auto-update cycle (within 30 minutes).</div>'
      $('#newsGrid').innerHTML = '<div class="grid-skeleton">Stories are being aggregated from BBC, Guardian, Sky &amp; ESPN…</div>'
      $('#tickerTrack').innerHTML = '<span class="ticker-empty">Fetching live scores…</span>'
    } else {
      renderHero(); renderNews(); renderTransfers(); renderSources()
      $('#updatedAt').textContent = `updated ${timeAgo(state.content.generated_at)}`
      $('#footerUpdated').textContent = `Updated: ${new Date(state.content.generated_at).toLocaleString()}`
    }
    renderTicker()
    renderFixtures()
    setMastheadDate()
    $('#footerYear').textContent = new Date().getFullYear()
  }

  /* ---------- nav / header interactions ---------- */
  const navToggle = $('#navToggle')
  const navList = $('#navList')
  navToggle.addEventListener('click', () => {
    const open = navList.classList.toggle('open')
    navToggle.setAttribute('aria-expanded', String(open))
    if (open) navList.querySelector('a')?.focus()
  })
  $$('#navList a').forEach((a) => a.addEventListener('click', () => { navList.classList.remove('open'); navToggle.setAttribute('aria-expanded', 'false') }))

  const navLinks = $$('#navList a')
  const sectionEls = ['news', 'transfers', 'fixtures', 'sources'].map((id) => $('#' + id))
  const spy = new IntersectionObserver((ents) => {
    ents.forEach((en) => {
      if (!en.isIntersecting) return
      const id = en.target.id
      navLinks.forEach((a) => a.classList.toggle('active', a.getAttribute('href') === '#' + id))
    })
  }, { rootMargin: '-40% 0px -55% 0px' })
  sectionEls.forEach((s) => s && spy.observe(s))

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

  if ('serviceWorker' in navigator) { /* reserved for future PWA */ }
})()
