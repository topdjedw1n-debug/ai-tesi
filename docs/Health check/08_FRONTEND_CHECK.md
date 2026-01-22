# 8️⃣ ПЕРЕВІРКА FRONTEND (Next.js)

> **Категорія:** Frontend Application
> **Час виконання:** ~10-15 хвилин
> **Залежності:** Backend running + Node.js
> **Критичність:** 🟡 СЕРЕДНЯ - User Interface

---

## 🎯 МЕТА ПЕРЕВІРКИ

Переконатися що Next.js frontend коректно збирається, запускається, та інтегрується з backend API.

**Що перевіряємо:**
- ✅ Node.js залежності встановлені
- ✅ Development build працює
- ✅ Production build компілюється
- ✅ Pages рендеряться без помилок
- ✅ API integration з backend
- ✅ Authentication flow працює
- ✅ Static assets завантажуються

---

## ✅ ПЕРЕДУМОВИ

- [ ] Node.js 18+ встановлено
- [ ] Backend running на `localhost:8000`
- [ ] `.env.local` налаштовано

---

## 📋 ПОКРОКОВА ІНСТРУКЦІЯ

### Крок 1: Встановлення залежностей

**Команда:**
```bash
cd /Users/maxmaxvel/.claude-worktrees/AI\ TESI/stupefied-fermat/apps/web

# Встановлення
npm install

# Або з очищенням кешу якщо проблеми
npm ci
```

**Очікуваний результат:**
```
added 543 packages in 45s
```

**Перевірка критичних пакетів:**
```bash
npm list next react typescript @tanstack/react-query axios
```

---

### Крок 2: Development Build

**Команда:**
```bash
npm run dev
```

**Очікуваний результат в консолі:**
```
▲ Next.js 14.0.3
- Local:        http://localhost:3000
- Ready in 2.5s
```

**Перевірка доступності:**
```bash
# В іншому терміналі
curl -s http://localhost:3000 | head -n 20
```

**Очікується HTML:**
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>TesiGo</title>
    ...
```

---

### Крок 3: Production Build

**Команда:**
```bash
# Зупинити dev server (Ctrl+C)

# Production build
npm run build
```

**Очікуваний результат:**
```
Route (app)                              Size     First Load JS
┌ ○ /                                    142 B          87.2 kB
├ ○ /_not-found                          142 B          87.2 kB
├ ○ /auth/login                          5.43 kB        92.6 kB
├ ○ /dashboard                           8.12 kB        95.3 kB
└ ○ /admin                               6.24 kB        93.4 kB

○  (Static)  automatically rendered as static HTML

✓ Compiled successfully
```

**Критерії:**
- ✅ Build завершився без помилок
- ✅ Всі pages компілюються
- ✅ Bundle size адекватний (First Load < 200 kB)

---

### Крок 4: Production Start

**Команда:**
```bash
npm run start
```

**Очікуваний результат:**
```
▲ Next.js 14.0.3
- Local:        http://localhost:3000
- Production mode
```

**Перевірка:**
```bash
curl -s http://localhost:3000 | grep "<title>"
# Очікується: <title>TesiGo</title>
```

---

### Крок 5: Page Routes Test

**Landing Page (`/`):**
```bash
curl -s http://localhost:3000/ | grep -o "<h1[^>]*>.*</h1>" | head -1
# Очікується: <h1>Generate High-Quality Academic Papers</h1>
```

**Auth Page (`/auth/login`):**
```bash
curl -s http://localhost:3000/auth/login | grep "magic link"
# Має бути форма з email input
```

**Dashboard (`/dashboard` - потребує auth):**
```bash
curl -s http://localhost:3000/dashboard
# Redirect на /auth/login або показує login форму
```

**Admin Panel (`/admin`):**
```bash
curl -s http://localhost:3000/admin
# Redirect на /admin/login
```

---

### Крок 6: API Integration Test

**Створити тестовий скрипт:**
```bash
cat > test_frontend_api.js << 'EOF'
const axios = require('axios');

async function testAPI() {
  try {
    // Test health endpoint через frontend proxy
    const health = await axios.get('http://localhost:3000/api/health');
    console.log('✅ Frontend API proxy:', health.data);

    // Test backend direct
    const backend = await axios.get('http://localhost:8000/health');
    console.log('✅ Backend health:', backend.data);

  } catch (error) {
    console.log('❌ Error:', error.message);
  }
}

testAPI();
EOF

node test_frontend_api.js
```

---

### Крок 7: Static Assets Test

**Команда:**
```bash
# Перевірка favicon
curl -I http://localhost:3000/favicon.ico | grep "200 OK"

# Перевірка public assets
curl -I http://localhost:3000/logo.png | grep "200"

# Перевірка Next.js assets
curl -I http://localhost:3000/_next/static/ | grep "200\|301\|302"
```

---

### Крок 8: TypeScript Compilation

**Команда:**
```bash
cd /Users/maxmaxvel/.claude-worktrees/AI\ TESI/stupefied-fermat/apps/web

# Type check без компіляції
npx tsc --noEmit
```

**Очікуваний результат:**
```
✓ No type errors found
```

**Якщо є помилки:**
```
app/components/DocumentList.tsx(23,15): error TS2339: ...
```

**Критерій:** 0 type errors для production готовності

---

### Крок 9: ESLint Check

**Команда:**
```bash
npm run lint
```

**Очікуваний результат:**
```
✔ No ESLint warnings or errors
```

---

### Крок 10: Authentication Flow (E2E Manual)

**Через браузер (якщо є GUI):**
```bash
# macOS
open http://localhost:3000

# Linux
xdg-open http://localhost:3000
```

**Кроки:**
1. Відкрити `/auth/login`
2. Ввести email
3. Перевірити що форма сабмітиться
4. Перевірити redirect/повідомлення

**Через curl (симуляція):**
```bash
# Відправити форму
curl -X POST http://localhost:3000/api/auth/magic-link \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

---

### Крок 11: Frontend Logs Check

**Під час роботи dev server переглянути консоль:**
- ✅ Немає errors (червоні)
- ⚠️ Warnings допустимі (жовті)
- ✅ Compilation successful

**Типові warnings (допустимі):**
```
⚠ Fast Refresh had to perform a full reload
⚠ Image with src "..." has either width or height modified
```

**Критичні errors (не допустимі):**
```
❌ Error: Cannot find module 'next'
❌ TypeError: Cannot read property 'map' of undefined
❌ Hydration error
```

---

### Крок 12: Mobile Responsive Test

**Команда (через curl headers):**
```bash
# Симуляція mobile user agent
curl -s http://localhost:3000 \
  -H "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)" \
  | grep "viewport"

# Очікується: <meta name="viewport" content="width=device-width...">
```

**Manual test (якщо є браузер):**
1. Відкрити DevTools (F12)
2. Toggle device toolbar (Ctrl+Shift+M)
3. Вибрати iPhone/iPad
4. Перевірити responsive layout

---

### Krок 13: Performance Metrics

**Lighthouse (якщо встановлено):**
```bash
# Встановити lighthouse
npm install -g lighthouse

# Запустити аудит
lighthouse http://localhost:3000 \
  --only-categories=performance,accessibility \
  --chrome-flags="--headless"
```

**Очікувані метрики:**
- Performance: >= 70
- Accessibility: >= 90
- First Contentful Paint: < 1.5s
- Time to Interactive: < 3.0s

---

### Крок 14: Bundle Size Analysis

**Команда:**
```bash
# Аналіз bundle
npm run build 2>&1 | grep "First Load JS"

# Або використати webpack-bundle-analyzer (якщо налаштовано)
ANALYZE=true npm run build
```

**Критерії:**
- ✅ Main bundle < 100 kB (gzip)
- ✅ First Load < 200 kB
- ⚠️ 200-300 kB - Можна оптимізувати
- ❌ > 300 kB - Потребує оптимізації

---

### Крок 15: Hot Reload Test

**В dev mode:**
1. Запустити `npm run dev`
2. Відкрити `app/page.tsx`
3. Змінити текст (наприклад, заголовок)
4. Зберегти файл
5. Перевірити що зміни відразу з'являються в браузері

**Очікується:**
```
✓ Compiled /___ in 234ms
✓ Fast Refresh
```

---

## 🔍 ПЕРЕВІРКА РЕЗУЛЬТАТІВ

### Чеклист успішного проходження:

**Build:**
- [ ] `npm install` успішно
- [ ] `npm run dev` запускається
- [ ] `npm run build` компілюється без помилок
- [ ] `npm run start` запускається в production mode

**Pages:**
- [ ] Landing page (`/`) рендериться
- [ ] Auth pages доступні
- [ ] Dashboard accessible (з auth)
- [ ] Admin panel accessible (з admin auth)

**Integration:**
- [ ] API calls до backend працюють
- [ ] Authentication flow працює
- [ ] Static assets завантажуються

**Quality:**
- [ ] TypeScript: 0 errors
- [ ] ESLint: 0 errors
- [ ] Hot reload працює

---

## ⚠️ ТИПОВІ ПОМИЛКИ ТА РІШЕННЯ

| Помилка | Причина | Рішення |
|---------|---------|---------|
| `Module not found: Can't resolve 'next'` | Залежності не встановлені | `npm install` |
| `Port 3000 already in use` | Інший процес використовує порт | `lsof -i :3000` → kill |
| `ECONNREFUSED localhost:8000` | Backend не запущено | Запустити backend |
| `Hydration error` | SSR/CSR mismatch | Перевірити async data loading |
| `Module parse failed` | Webpack config issue | Перевірити `next.config.js` |

---

## 📊 КРИТЕРІЇ УСПІШНОСТІ

### ✅ ТЕСТ ПРОЙДЕНО ЯКЩО:

- Development server запускається
- Production build компілюється
- Всі pages accessible
- API integration працює
- TypeScript без errors
- ESLint passed
- Hot reload працює

### ❌ ТЕСТ ПРОВАЛЕНО ЯКЩО:

- Build fails (compilation errors)
- TypeScript має > 0 errors
- Pages не рендеряться (white screen)
- API calls не працюють
- Hot reload broken

---

## 🔗 ЗВ'ЯЗОК З ІНШИМИ ПЕРЕВІРКАМИ

**⬆️ Залежить від:**
- `03_BACKEND_CHECK.md` - Backend API
- `02_CONFIGURATION_CHECK.md` - .env.local

**⬇️ Впливає на:**
- `09_E2E_TESTS_CHECK.md` - Full user flows

**Критичність:** 🟡 СЕРЕДНЯ - UI layer

---

## 🚀 ШВИДКИЙ СТАРТ

```bash
# Quick frontend check
cd apps/web && \
npm install && \
npm run build && \
npm run start &
sleep 5 && \
curl -s http://localhost:3000 | grep "<title>" && \
echo "✅ Frontend check PASSED"
```

---

**Дата створення:** 2025-12-03
**Версія:** 1.0
**Автор:** AI Assistant
**Попередня перевірка:** `07_API_ENDPOINTS_CHECK.md`
**Наступна перевірка:** `09_E2E_TESTS_CHECK.md`
