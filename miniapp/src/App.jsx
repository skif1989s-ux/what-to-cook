import { useState, useEffect, useRef } from 'react'
import { useTelegram } from './hooks/useTelegram'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const { tg, user } = useTelegram()
  const [screen, setScreen] = useState('home') // home | list | recipe | create
  const [categories, setCategories] = useState([])
  const [tags, setTags] = useState([])
  const [cuisines, setCuisines] = useState([])
  const [activeCat, setActiveCat] = useState(null)
  const [activeTag, setActiveTag] = useState(null)
  const [activeCuisine, setActiveCuisine] = useState(null)
  const [customTitle, setCustomTitle] = useState(null)
  const [search, setSearch] = useState('')
  const [recipes, setRecipes] = useState([])
  const [recipe, setRecipe] = useState(null)
  const [showVideo, setShowVideo] = useState(false)
  const [stepIdx, setStepIdx] = useState(0)
  const [loading, setLoading] = useState(false)
  // Избранное
  const [favorites, setFavorites] = useState([])
  const [favIds, setFavIds] = useState([])
  // Создание рецепта
  const [createText, setCreateText] = useState('')
  const [createIngredients, setCreateIngredients] = useState([])
  const fileRef = useRef(null)

  useEffect(() => {
    if (tg) { tg.ready(); tg.expand() }
    fetch(`${API}/api/categories`).then(r => r.json()).then(d => {
      setCategories(d.categories); setTags(d.tags)
    }).catch(console.error)
    fetch(`${API}/api/cuisines`).then(r => r.json()).then(d => {
      setCuisines(d.cuisines)
    }).catch(console.error)

    if (user) {
      fetch(`${API}/api/users/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: user.id, username: user.username || '' })
      }).catch(console.error)
      loadFavorites()
    }
  }, [])

  const loadFavorites = async () => {
    if (!user) return
    try {
      const d = await (await fetch(`${API}/api/favorites/list?user_id=${user.id}`)).json()
      setFavorites(d.recipes)
      setFavIds(d.recipes.map(r => r.id))
    } catch (e) { console.error(e) }
  }

  const toggleFavorite = async (r) => {
    if (!user) { alert('Откройте приложение в Telegram, чтобы сохранять рецепты ❤️'); return }
    const isFav = favIds.includes(r.id)
    await fetch(`${API}/api/favorites/${isFav ? 'remove' : 'add'}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: user.id, recipe_id: r.id })
    })
    setFavIds(prev => isFav ? prev.filter(id => id !== r.id) : [...prev, r.id])
    loadFavorites()
  }

  const openList = async ({ cat = null, tag = null, cuisine = null, q = '' } = {}) => {
    setActiveCat(cat); setActiveTag(tag); setActiveCuisine(cuisine); setCustomTitle(null)
    const params = new URLSearchParams()
    if (cat) params.set('category', cat)
    if (tag) params.set('tag', tag)
    if (cuisine) params.set('cuisine', cuisine)
    if (q) params.set('search', q)
    try {
      const d = await (await fetch(`${API}/api/recipes?${params}`)).json()
      setRecipes(d.recipes)
    } catch (e) { console.error(e); setRecipes([]) }
    setScreen('list')
  }

  const openFavorites = () => {
    setRecipes(favorites)
    setActiveCat(null); setActiveTag(null); setActiveCuisine(null)
    setCustomTitle('❤️ Избранное')
    setScreen('list')
  }

  const openRecipe = (r) => { setRecipe(r); setStepIdx(0); setShowVideo(false); setScreen('recipe') }

  const handleFiles = async (files) => {
    setLoading(true)
    for (const file of Array.from(files)) {
      const formData = new FormData()
      formData.append('file', file)
      try {
        const d = await (await fetch(`${API}/api/parse/image`, { method: 'POST', body: formData })).json()
        setCreateIngredients(prev => [...new Set([...prev, ...d.ingredients])])
      } catch (e) { console.error(e) }
    }
    setLoading(false)
  }

  const smartSearch = async () => {
    setLoading(true)
    try {
      let ingredients = [...createIngredients]
      if (createText.trim()) {
        const d = await (await fetch(`${API}/api/parse/text`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: createText })
        })).json()
        ingredients = [...new Set([...ingredients, ...d.ingredients])]
      }
      const d = await (await fetch(`${API}/api/recipes/smart-search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ingredients, user_id: user?.id, max_time: 90 })
      })).json()
      setRecipes(d.recipes)
      setActiveCat(null); setActiveTag(null); setActiveCuisine(null)
      setCustomTitle('🔍 Результаты')
      setScreen('list')
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  const listTitle = () => {
    if (customTitle) return customTitle
    if (activeTag) return `#${activeTag}`
    if (activeCuisine) return `${(cuisines.find(c => c.id === activeCuisine) || {}).flag || '🌍'} ${activeCuisine}`
    return (categories.find(c => c.id === activeCat) || {}).name || 'Поиск'
  }

  // ───────── ГЛАВНАЯ ─────────
  if (screen === 'home') return (
    <div style={S.page}>
      <h1 style={S.h1}>🍳 Что приготовить?</h1>
      <input placeholder="🔍 Поиск блюд..." value={search}
        onChange={e => setSearch(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && openList({ q: search })}
        style={S.input} />

      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <button onClick={() => { setCreateText(''); setCreateIngredients([]); setScreen('create') }} style={S.btnOrange}>
          📷✨ Что в холодильнике?
        </button>
        <button onClick={openFavorites} style={S.btnRed}>
          ❤️ ({favorites.length})
        </button>
      </div>

      <h2 style={S.h2}>Категории</h2>
      <div style={S.catGrid}>
        {categories.map(c => (
          <div key={c.id} onClick={() => openList({ cat: c.id })} style={S.catCard}>
            <div style={{ fontSize: 28 }}>{c.emoji}</div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{c.name}</div>
          </div>
        ))}
      </div>

      <h2 style={S.h2}>🌍 Кухни мира</h2>
      <div style={S.tagRow}>
        {cuisines.map(c => (
          <span key={c.id} onClick={() => openList({ cuisine: c.id })} style={S.tag}>
            {c.flag} {c.name}
          </span>
        ))}
      </div>

      <h2 style={S.h2}>Теги</h2>
      <div style={S.tagRow}>
        {tags.map(t => (
          <span key={t} onClick={() => openList({ tag: t })} style={S.tag}>#{t}</span>
        ))}
      </div>
    </div>
  )

  // ───────── СОЗДАТЬ РЕЦЕПТ ─────────
  if (screen === 'create') return (
    <div style={S.page}>
      <div style={S.topbar}>
        <button onClick={() => setScreen('home')} style={S.back}>←</button>
        <strong>✨ Подбор рецепта</strong>
      </div>

      <p style={{ color: '#666', fontSize: 14 }}>
        Прикрепите фото продуктов (можно несколько) или напишите, что у вас есть — я найду или придумаю рецепт!
      </p>

      <input type="file" accept="image/*" multiple ref={fileRef}
        onChange={e => handleFiles(e.target.files)} style={{ display: 'none' }} />
      <button onClick={() => fileRef.current?.click()} style={S.btnPhoto}>
        📷 Загрузить фото продуктов
      </button>

      <textarea
        placeholder="Например: у меня есть курица, рис, помидоры и лук..."
        value={createText}
        onChange={e => setCreateText(e.target.value)}
        style={S.textarea}
      />

      {createIngredients.length > 0 && (
        <>
          <h2 style={S.h2}>Распознано:</h2>
          <div style={S.tagRow}>
            {createIngredients.map((ing, i) => (
              <span key={i} onClick={() => setCreateIngredients(createIngredients.filter((_, idx) => idx !== i))} style={S.tag}>
                {ing} ✕
              </span>
            ))}
          </div>
        </>
      )}

      <button onClick={smartSearch}
        disabled={loading || (!createIngredients.length && !createText.trim())}
        style={{ ...S.btnGreen, background: (createIngredients.length || createText.trim()) ? '#4caf50' : '#ccc', marginTop: 16 }}>
        {loading ? '⏳ Распознаём...' : '🔍 Найти или создать рецепт'}
      </button>
    </div>
  )

  // ───────── СПИСОК ─────────
  if (screen === 'list') return (
    <div style={S.page}>
      <div style={S.topbar}>
        <button onClick={() => setScreen('home')} style={S.back}>←</button>
        <strong>{listTitle()}</strong>
      </div>
      {recipes.map(r => (
        <div key={r.id} onClick={() => openRecipe(r)} style={S.card}>
          <div style={{ position: 'relative' }}>
            {r.image_url
              ? <img src={r.image_url} style={S.img} alt="" />
              : <div style={{ ...S.img, background: 'linear-gradient(135deg,#ffe0b2,#ffcc80)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 48 }}>🍽️</div>}
            {r.video_url && <span style={S.videoBadge}>▶ видео</span>}
          </div>
          <div style={{ padding: 12 }}>
            <strong>{r.title}</strong>
            <div style={S.meta}>⏱ {r.time_min} мин • 🔥 {r.calories} ккал • 🌍 {r.cuisine}</div>
            {r.match_percent !== undefined && (
              <div style={{ color: r.match_percent === 100 ? '#4caf50' : '#ff9800', fontSize: 13, fontWeight: 'bold' }}>
                {r.match_percent}% совпадение
                {r.missing?.length > 0 && <span style={{ color: '#f44336', fontWeight: 'normal' }}> • не хватает: {r.missing.join(', ')}</span>}
              </div>
            )}
            <div>{(r.tags || []).map(t => <span key={t} style={S.tagMini}>#{t}</span>)}</div>
          </div>
        </div>
      ))}
      {!recipes.length && <p style={{ textAlign: 'center', color: '#888' }}>Ничего не найдено 😕</p>}
    </div>
  )

  // ───────── РЕЦЕПТ ─────────
  return (
    <div style={S.page}>
      <div style={S.topbar}>
        <button onClick={() => setScreen('list')} style={S.back}>←</button>
        <strong style={{ flex: 1 }}>{recipe.title}</strong>
        <button onClick={() => toggleFavorite(recipe)} style={S.heart}>
          {favIds.includes(recipe.id) ? '❤️' : '🤍'}
        </button>
      </div>

      {recipe.video_url ? (
        <>
          <div style={{ display: 'flex', gap: 8, margin: '8px 0' }}>
            <button onClick={() => setShowVideo(false)} style={!showVideo ? S.btnActive : S.btn}>📷 Фото</button>
            <button onClick={() => setShowVideo(true)} style={showVideo ? S.btnActive : S.btn}>▶ Видео</button>
          </div>
          {showVideo ? (
            <div style={{ position: 'relative' }}>
              <video src={recipe.video_url} autoPlay muted loop playsInline style={S.img} />
              <div style={S.subtitle}>{stepIdx + 1}. {recipe.steps[stepIdx]}</div>
              <div style={S.subControls}>
                <button onClick={() => setStepIdx(Math.max(0, stepIdx - 1))} style={S.btn}>←</button>
                <span style={{ fontSize: 13, color: '#fff' }}>{stepIdx + 1}/{recipe.steps.length}</span>
                <button onClick={() => setStepIdx(Math.min(recipe.steps.length - 1, stepIdx + 1))} style={S.btn}>→</button>
              </div>
            </div>
          ) : (
            recipe.image_url ? <img src={recipe.image_url} style={S.img} alt="" /> : <div style={{ ...S.img, background: '#eee' }} />
          )}
        </>
      ) : (
        recipe.image_url ? <img src={recipe.image_url} style={S.img} alt="" /> : <div style={{ ...S.img, background: 'linear-gradient(135deg,#ffe0b2,#ffcc80)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 64 }}>🍽️</div>
      )}

      <div style={S.meta}>⏱ {recipe.time_min} мин • 🔥 {recipe.calories} ккал • 🌍 {recipe.cuisine} кухня</div>

      <h2 style={S.h2}>Ингредиенты</h2>
      {recipe.ingredients.map((i, n) => <div key={n} style={S.li}>• {i}</div>)}

      <h2 style={S.h2}>Приготовление</h2>
      {recipe.steps.map((s, n) => (
        <div key={n} onClick={() => { setStepIdx(n); if (recipe.video_url) setShowVideo(true) }} style={S.step}>
          <b>{n + 1}.</b> {s}
        </div>
      ))}
    </div>
  )
}

const S = {
  page: { padding: 16, fontFamily: 'system-ui', maxWidth: 600, margin: '0 auto', paddingBottom: 40 },
  h1: { fontSize: 22, marginTop: 8 },
  h2: { fontSize: 16, margin: '16px 0 8px' },
  input: { width: '100%', padding: 12, borderRadius: 10, border: '1px solid #ddd', boxSizing: 'border-box', fontSize: 15 },
  textarea: { width: '100%', padding: 12, borderRadius: 10, border: '1px solid #ddd', boxSizing: 'border-box', fontSize: 15, minHeight: 80, marginTop: 12 },
  catGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 },
  catCard: { background: '#f5f5f5', borderRadius: 14, padding: 14, textAlign: 'center', cursor: 'pointer' },
  tagRow: { display: 'flex', flexWrap: 'wrap', gap: 8 },
  tag: { background: '#e3f2fd', padding: '6px 12px', borderRadius: 16, cursor: 'pointer', fontSize: 14 },
  tagMini: { background: '#e3f2fd', padding: '2px 8px', borderRadius: 10, fontSize: 11, marginRight: 4, display: 'inline-block' },
  topbar: { display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 },
  back: { fontSize: 22, background: 'none', border: 'none', cursor: 'pointer' },
  heart: { fontSize: 22, background: 'none', border: 'none', cursor: 'pointer' },
  card: { border: '1px solid #eee', borderRadius: 14, marginBottom: 14, overflow: 'hidden', cursor: 'pointer' },
  img: { width: '100%', height: 200, objectFit: 'cover', display: 'block' },
  videoBadge: { position: 'absolute', top: 8, right: 8, background: 'rgba(0,0,0,.6)', color: '#fff', padding: '4px 10px', borderRadius: 12, fontSize: 12 },
  meta: { color: '#666', fontSize: 13, margin: '6px 0' },
  btn: { padding: '8px 14px', borderRadius: 10, border: '1px solid #ddd', background: '#fff', cursor: 'pointer' },
  btnActive: { padding: '8px 14px', borderRadius: 10, border: 'none', background: '#2481cc', color: '#fff', cursor: 'pointer' },
  btnOrange: { flex: 1, padding: 14, borderRadius: 12, background: '#ff9800', color: '#fff', border: 'none', fontSize: 15, fontWeight: 'bold', cursor: 'pointer' },
  btnRed: { padding: '14px 16px', borderRadius: 12, background: '#ffebee', color: '#f44336', border: 'none', fontSize: 15, fontWeight: 'bold', cursor: 'pointer' },
  btnGreen: { width: '100%', padding: 14, borderRadius: 12, color: '#fff', border: 'none', fontSize: 16, fontWeight: 'bold', cursor: 'pointer' },
  btnPhoto: { width: '100%', padding: 14, borderRadius: 10, background: '#f0f0f0', border: '2px dashed #ccc', cursor: 'pointer', fontSize: 15 },
  subtitle: { position: 'absolute', bottom: 44, left: 8, right: 8, background: 'rgba(0,0,0,.7)', color: '#fff', padding: '8px 12px', borderRadius: 10, fontSize: 14, textAlign: 'center' },
  subControls: { position: 'absolute', bottom: 6, left: 0, right: 0, display: 'flex', justifyContent: 'center', gap: 16, alignItems: 'center' },
  li: { fontSize: 14, margin: '4px 0' },
  step: { fontSize: 14, margin: '8px 0', padding: 10, background: '#f9f9f9', borderRadius: 10, cursor: 'pointer' },
}