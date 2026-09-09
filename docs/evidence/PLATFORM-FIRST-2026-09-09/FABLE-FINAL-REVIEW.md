**DIRECTION_APPROVED. LOCAL_IMPLEMENTATION_READY.**

**Перевірено в коді.**
- Must-fix закрито: `convert_pack_markers(render_unresolved=…)` (`citation_keys.py:111, 158–176`) рендерить нерозв'язаний ключ лише з наявного лейбла/року, лишає його в `unresolved_keys`, не додає до бібліографії; змішані групи зливаються в одні дужки; strict-дефолт `False` незмінний. Увімкнено для warning-jobs у генераторі (`generator.py:315`) і в усіх трьох конверсіях воркера (`background_jobs.py:2704, 2729, 2857`).
- Фільтр `outline_for_available_sources` (`prompt_builder.py:180–204`) чіпає лише `evidence_keys` у копії; тест підтверджує незмінний оригінал і всі інші поля; воркер пише `discarded_outline_keys` + нерозв'язані цитати в одне попередження (`background_jobs.py:2493–2514`).
- Схема `ProductionCaseResponse.generation_warnings` додана (`schemas/production.py:128`); квитанція «до» з реальним падінням і «після» 83 passed є.
- Профіль хешує `generation_policy.py` і `standard_references.py` (`generation_profile.py:60–61`).
- Тест старого реального запису явно ставить `allow_request_changes=True` і перевіряє рендер, а не новий prompt — чесно.

**Реальний доказ v2 (термінальний).** `spend-report.json`: 1 виклик, `received`, $0.21, 29282 токени, replay без SDK; у `section.md` жодного `[Key]`, `[STD:]` чи JSON-блоку. Це доказ етапу «писар → рендер → replay», не повного job, не академічного приймання і не приймання Танею. Сумарно етапні витрати $0.42 у межах $5.

**Незавершене (не блокує).** Повний API-прогін у `platform-api-final.txt` ще без підсумку (зібрано 1469, попередній повний — 1442 passed, 0 failed); фокусні квитанції 46/83 passed. Косметика в тексті v2, того ж класу, що відкладена: інституційний автор рендериться як «(Organization, 2022)» (`section.md:11`) — прізвищева логіка `format_intext` для «World Health Organization»; додати до відкладеного пункту разом із multi-author s.d.

Живий/платний запуск, сервер і приймання — окремі дозволи, як і раніше.
