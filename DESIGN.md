# Design System — Thesica

> Single source of truth for visual decisions. Read this before any UI work.
> Created by `/design-consultation` on 2026-06-21. Direction: **Scholarly Press**.
> **Living component + infographic library:** [`thesica-brandbook.html`](thesica-brandbook.html) — open in a browser to see every token, element, and data-viz pattern rendered (light + dark). DESIGN.md is the spec; the brandbook is the proof.

## Brand Name & Logo
- **Name:** **Thesica** (was working name "TesiGo"). Latin/academic feel; `-ica` suffix reads as a discipline (*logica, musica, etica*) across IT/ES/CZ/EN; root "thes-" carries *thesis*. Chosen for universality + clean domain/trademark runway (the literal "Thes-" tools like Thesify/ThesisAI are all taken; abstract picks like Laude/Accredo had conflicts).
- **Domain:** primary **thesica.ai** (free, registered); defensive **getthesica.com** (free). `thesica.com` is taken.
- **Wordmark:** "Thesica" set in **Literata 600** (the brand display serif). Optional `θ`-initial variant (theta = θέσις) kept as a backup motif.
- **Mark:** **bookmark ribbon** — a notched ribbon = a marked / finished / distinguished document. Distinctive silhouette, holds down to 16px.
- **Assets:** SVG files in `~/.gstack/projects/topdjedw1n-debug-ai-tesi/designs/design-system-20260621/brand/` — `thesica-mark.svg` (app icon), `thesica-mark-on-dark.svg`, `thesica-mark-mono.svg` (currentColor), `favicon.svg`, `thesica-lockup.svg` (mark + wordmark).
- **Mark geometry (green tile + cream ribbon):** `<rect rx=20 fill=#0f6e56/>` + `<path d="M36 24 Q36 19 41 19 L51 19 Q56 19 56 24 L56 71 L46 61 L36 71 Z" fill=#fffdf9/>`.
- **Propagated (2026-06-21):** renamed TesiGo → Thesica and swapped the placeholder logo for the ribbon mark across `apps/web` (Header/Footer/Dashboard, metadata, manifest, favicon), README/QUICK_START, and the brandbook. Test fixtures, `.env*`, eval data, and historical logs left untouched on purpose.

## Product Context
- **What this is:** Thesica — AI-генерація академічних робіт (дипломні/магістерські), де ядро цінності не «дешевше», а «дешево **і реально приймається** університетом» (плагіат + AI-детектор + наукрук).
- **Who it's for:** (1) **редактор/менеджер агенції** у внутрішній консолі — пріоритетна поверхня; (2) студент, який інакше заплатив би агенції ~€100 за готову роботу, якій критично пройти універ-гейт.
- **Space/industry:** AI-academic-writing / scholarly tools. Peers: Jenni AI, Paperpal, Scribbr, Consensus.
- **Project type:** internal tool (консоль редактора) + web product (лендінг + кабінет). Stack: FastAPI + Next.js 14 + Tailwind.

## The One Memorable Thing
**«Це справжня наукова робота, їй можна довіряти».**
Легітимність — це і є моат (проходить там, де сирий ChatGPT валиться). Кожне дизайн-рішення служить цій одній речі. Якщо вибір додає «AI-іграшковості» замість «друкованої легітимності» — він неправильний.

## Aesthetic Direction
- **Direction:** Scholarly Press — університетський прес, чорнило на теплому папері.
- **Decoration level:** intentional — субтильна паперова теплота (тепла нейтраль, тонкі лінії, м'які тіні), без патернів і градієнтів.
- **Mood:** серйозно, але по-людськи. Спокійна впевненість друкованого журналу, а не флеш AI-SaaS.
- **Anti-direction (заборонено):** корпоративний синій як акцент (Jenni/Paperpal/старий дефолт сюди й конвергують); фіолетові градієнти; 3-колонкова сітка фіч з іконками в кружечках; centered-everything; system-ui/Inter як дисплейний шрифт; градієнтні CTA.

## Typography
Усі шрифти **мають повну кирилицю** (UI українською — жорстка вимога; саме тому Fraunces/Spectral/Bricolage відхилені як Latin-only).
- **Display/Hero:** **Literata** (600/700) — літературний серіф Google, теплий і книжковий. Заголовки, назви робіт, бренд.
- **Body / UI:** **Source Sans 3** (400/500/600) — чистий гуманістичний санс для інтерфейсу, форм, таблиць, кнопок.
- **Reading (текст самої роботи):** **Literata** (400/500) — для прев'ю та читання згенерованої прози, line-height 1.72.
- **Data / Numbers / Code:** **JetBrains Mono** (400/500) — метрики гейту, ID робіт, відсотки, лічильник хвилин (tabular).
- **Loading (Google Fonts, один CDN, з кирилицею):**
  ```html
  <link href="https://fonts.googleapis.com/css2?family=Literata:opsz,wght@7..72,400;7..72,500;7..72,600;7..72,700&family=Source+Sans+3:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap&subset=cyrillic,cyrillic-ext,latin,latin-ext" rel="stylesheet">
  ```
- **Scale (base 16px, ~1.25 major third):**
  | token | px | rem | використання |
  |-------|----|-----|--------------|
  | xs | 12 | 0.75 | мета, mono-підписи, tiny |
  | sm | 14 | 0.875 | вторинний текст, лейбли |
  | base | 16 | 1.0 | body / UI default |
  | md | 18 | 1.125 | прев'ю прози роботи |
  | lg | 20 | 1.25 | назва роботи в картці |
  | xl | 24 | 1.5 | підзаголовки секцій |
  | 2xl | 30 | 1.875 | заголовки сторінок |
  | 3xl | 38 | 2.375 | hero (лендінг) |
  | 4xl | 48 | 3.0 | великий hero |
- **Line-height:** body 1.6 · reading-prose 1.72 · headings 1.12–1.25 · mono 1.5.

## Color
- **Approach:** restrained — один акцент (зелений) + тепла нейтраль; колір рідкісний і значущий. Семантика тільки для статусів гейту.

| роль | hex | використання |
|------|-----|--------------|
| bg | `#f7f5f0` | загальний теплий папір-фон |
| paper | `#fffdf9` | картки, поверхні, консоль |
| stage | `#efeadf` | глибший фон під картками |
| bar | `#faf7f1` | хедери таблиць/панелей |
| **ink** | `#1c1b19` | основний текст |
| ink-soft | `#4a4843` | вторинний текст |
| ink-faint | `#8a877f` | мета, плейсхолдери |
| line | `#e6e1d6` | бордюри, роздільники |
| line-strong | `#d6d0c2` | бордюри secondary-кнопок |
| **accent** | `#0f6e56` | primary CTA, акцент бренду, прогрес |
| accent-deep | `#0a4d3c` | hover/active, темний текст-акцент |
| accent-soft | `#e4f1ea` | фон ok-pill, виділення |

- **Semantic (статуси гейту):**
  - success (пройшов поріг): `#0f6e56` / soft `#e4f1ea`
  - warning (потребує перевірки, напр. цитати 18/20): `#a05a00` / soft `#fbeed9`
  - error (завалив поріг): `#9a2b22` / soft `#fae6e2`
  - info: `#1c5a93` / soft `#e6eff8` — **тільки** службова інформація, ніколи не бренд-акцент (інакше зісковзуємо в синій SaaS)
- **Dark mode (консоль редактора часто = довгі сесії):** редизайн поверхонь, не інверсія. bg `#16150f`, paper `#1e1c17`, ink `#e8e4db`, line `#2c2a23`, accent підняти до `#2f9e7e` (насиченість -10–15% від денного), accent-soft `rgba(47,158,126,.12)`. Зберегти теплий тон (не холодний #0e слейт).

## Spacing
- **Base unit:** 4px.
- **Density:** comfortable — консоль щільна по даних, але дихає (gate-рядки 12px вертикалі, картки 20–24px падінг).
- **Scale:** 2xs(2) xs(4) sm(8) md(12) base(16) lg(24) xl(32) 2xl(48) 3xl(64) 4xl(96).

## Layout
- **Approach:** hybrid — grid-disciplined для консолі/кабінету (передбачуване вирівнювання, дані), editorial-теплота для лендінгу.
- **Internal console (пріоритет):** двоколонковий робочий простір; картка роботи з gate-панеллю (AND: цитати + плагіат + AI-детектор) і лічильником хвилин редактора (31/45) як першокласним елементом — це операційне ядро з office-hours.
- **Grid:** 12-кол, gutter 24px. Mobile 4-кол.
- **Max content width:** app 1180px · reading-прев'ю прози 720px (оптимальна довжина рядка) · marketing 1240px.
- **Border radius (ієрархічний):** sm 6px (pill-теги, інпути) · md 10px (кнопки, дрібні картки) · lg 14px (картки, консоль, панелі) · xl 18px (великі секції) · full 999px (статус-pills, аватари).
- **Shadow:** `0 1px 2px rgba(28,27,25,.04), 0 14px 34px rgba(28,27,25,.10)` — м'яко, паперово, без неонового glow.

## Motion
- **Approach:** minimal-functional. Серйозний інструмент → стриманість. Рух лише там, де допомагає зрозуміти стан (зміна статусу гейту, заповнення лічильника, тости). Жодних scroll-хореографій у консолі.
- **Easing:** enter `ease-out` · exit `ease-in` · move `ease-in-out`.
- **Duration:** micro 80ms (hover) · short 180ms (стейти) · medium 280ms (входи панелей) · long 450ms (рідко, переходи виду).
- Бібліотека framer-motion уже в проекті — використовувати ощадливо.

## Implementation Mapping (Tailwind / Next.js)
Поточний `apps/web/tailwind.config.js` має дефолтний синій `primary` (#3b82f6) і Inter скрізь — **це і є generic-вигляд, який відстроюємось; його треба замінити.**
- `primary` → зелена шкала навколо `#0f6e56` (500), `#0a4d3c` (700), `#e4f1ea` (50).
- `secondary` (slate) → тепла нейтраль навколо `#1c1b19`/`#8a877f`/`#e6e1d6`.
- `fontFamily.sans` → `['Source Sans 3', ...]`; додати `display: ['Literata', 'serif']`, `read: ['Literata','serif']`; `mono: ['JetBrains Mono', ...]` (вже є).
- `globals.css`: замінити `@import Inter` на Literata+Source Sans 3+JetBrains Mono (URL вище); `body` → `bg-[#f7f5f0] text-[#1c1b19]`.
- Кнопки `.btn-primary` → `bg-[#0f6e56] hover:bg-[#0a4d3c]`.
- Reference: `tesigo-concierge-design.html` (попередник цього напряму) і дошка `~/.gstack/projects/topdjedw1n-debug-ai-tesi/designs/design-system-20260621/directions-board.html`.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-21 | Створено дизайн-систему, напрям **Scholarly Press** (A з 3) | Конкуренти + старий застосунок конвергують на синьому = generic. Відстройка через науково-друкарську мову прямо обслуговує моат «легітимність» |
| 2026-06-21 | Акцент — академічний зелений `#0f6e56`, не синій | Синій = «AI-тул»; теплий зелений+папір = «справжня наукова робота». Підтверджено трендами neo-earth 2026 |
| 2026-06-21 | Шрифти: Literata + Source Sans 3 + JetBrains Mono | UI українською → потрібна повна кирилиця; Fraunces/Spectral/Bricolage відхилені як Latin-only |
| 2026-06-21 | Пріоритет поверхні — внутрішня консоль редактора | Обраний клин з office-hours (concierge-модель); self-serve лендінг — після доведення моату |
| 2026-06-21 | Дефолтний Tailwind `primary` синій позначено deprecated | Замінити на зелену шкалу (див. Implementation Mapping) |
| 2026-06-21 | Систему вживлено в `apps/web` | `tailwind.config.js` (primary→зелений, gray→тепла нейтраль, шрифти), `globals.css` (Literata+Source Sans 3+JetBrains Mono, serif-заголовки), `layout.tsx` (lang=uk, теплі тости). Зметено 238 жорстких `blue/indigo/purple` класів → `primary` у 46 файлах; видалено pink→indigo slop-градієнт у Hero. Перевірено живим рендером лендінга + auth |
