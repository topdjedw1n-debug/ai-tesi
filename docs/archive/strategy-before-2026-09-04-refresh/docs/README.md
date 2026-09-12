# Thesica Documentation

Рішення живуть у чотирьох документах. Все інше — операційні інструкції, докази прогонів або архів.

## Джерела правди (читати в цьому порядку)

1. [AGENT_SYNC.md](./AGENT_SYNC.md) — бриф фаундера: pass-критерії, що можна і що не можна, черга. Якщо будь-який інший документ з ним розходиться — перемагає AGENT_SYNC.
2. [../THESICA-PLAN.md](../THESICA-PLAN.md) — архітектура фаз і exit-критерії.
3. [../DESIGN.md](../DESIGN.md) — дизайн (Scholarly Press); обов'язково перед будь-яким UI.
4. [PRE-RUN-001-TASKS.md](./PRE-RUN-001-TASKS.md) — актуальний покроковий список задач до RUN-001.

## Операційні документи (не рішення)

| Навіщо | Файл |
|---|---|
| Локальний запуск | [QUICK_START.md](./QUICK_START.md) |
| Деплой на прод | [setup/PRODUCTION_DEPLOYMENT_PLAN.md](./setup/PRODUCTION_DEPLOYMENT_PLAN.md) |
| Пошта | [Email/EMAIL_SETUP.md](./Email/EMAIL_SETUP.md) |
| Шаблон звіту прогону | [PHASE1_RUN_REPORT_TEMPLATE.md](./PHASE1_RUN_REPORT_TEMPLATE.md) |
| Докази прогонів Фази 1 | [phase1-runs/](./phase1-runs/) |
| Артефакт контуру Фази 0 | [PHASE0_READINESS_RECORD.md](./PHASE0_READINESS_RECORD.md) — **пише адмінка**, руками не редагувати |

## Архів

Застарілі й поглинуті документи — у [archive/](./archive/README.md). Вони не є джерелом правди; README архіву пояснює, куди перенесено кожне ще чинне рішення.

## Правило підтримки

Нових документів з рішеннями не заводити: рішення фіксуються в AGENT_SYNC (або THESICA-PLAN для фаз, DESIGN для дизайну). Одноразові звіти й виконані плани — в archive/, не в активну навігацію.
