"""Closed manager-facing vocabulary shared by execution and status projections."""

from datetime import UTC, datetime

STOP_CODES = frozenset(
    {"provider_access", "provider_unusable_response", "storage_or_db"}
)
DEFECT_CODE = "internal_error"
WARNING_CODES = {
    "source_coverage_gap": (
        "warning",
        "Для частини теми знайдено недостатньо джерел із доступним текстом.",
    ),
    "source_no_readable_text": (
        "info",
        "Джерело підтверджено, але його текст недоступний для написання.",
    ),
    "source_full_text_unavailable": ("info", "Частину повних текстів не отримано."),
    "source_full_text_off_topic": (
        "info",
        "Повний текст визнано не про тему роботи: використано лише анотацію.",
    ),
    "section_without_documents": ("warning", "Розділ без повнотекстових документів."),
    "catalogue_unavailable": ("warning", "Каталог джерел не відповідав."),
    "standard_reference_used": ("info", "Джерело зі стандартної бібліотеки."),
    "plan_material_gap": ("warning", "У пакеті бракує матеріалу для розділу."),
    "frame_rewritten": ("info", "Рамковий розділ переписано без переказу глав."),
    "outline_scope_unmapped": ("warning", "План не охоплює частину завдання."),
    "output_truncated_retried": (
        "info",
        "Обрізану відповідь моделі відновлено додатковим зверненням.",
    ),
    "output_truncated_kept": (
        "warning",
        "Розділ двічі обірвано; збережено текст до останнього повного речення.",
    ),
    "citation_unresolved": (
        "warning",
        "Невідоме позначення джерела прибрано з тексту.",
    ),
    "length_off_target": ("warning", "Обсяг розділу відрізняється від запланованого."),
    "reference_replaced": (
        "warning",
        "Посилання, яке не вдалося підтвердити, прибрано з тексту.",
    ),
    "review_negative": ("warning", "Академічний огляд виявив недоліки готової роботи."),
    "review_note": ("info", "Академічний огляд залишив зауваження до готової роботи."),
    "page_out_of_range": ("warning", "Сторінка поза межами документа."),
    "decision_year_mismatch": (
        "warning",
        "Рік рішення в тексті не збігається з джерелом.",
    ),
    "quote_share_high": ("warning", "Забагато цитат у лапках (понад 15 %)."),
    "quote_without_page": (
        "info",
        "Частина дослівних цитат не має номера сторінки в посиланні.",
    ),
    "bibliography_suspect": (
        "info",
        "Частина бібліографічних записів має сумнівні дані (рік, автори, назва); перевірте перед видачею.",
    ),
    "detector_unchecked": ("info", "Зовнішній детектор зараз недоступний."),
    "placeholder_text": ("warning", "У розділі залишилися редакторські заглушки."),
}
STAGE_LABELS = {
    "sources": "Пошук джерел",
    "outline": "Побудова плану",
    "writing": "Написання розділів",
    "references": "Упорядкування посилань",
    "assembling": "Збірка DOCX та огляд",
}
STATUS_LABELS = {
    "queued": "У черзі",
    "running": "Виконується",
    "generating": "Виконується",
    "completed": "Написання завершено",
    "failed": "Технічна зупинка",
    "cancelled": "Скасовано",
}
ACTION_LABELS = {
    "retry_now": "Нова спроба",
    "retry_after_owner": "Звернутися до власника",
    "contact_owner": "Звернутися до власника",
}


class ExecutionStop(Exception):
    def __init__(self, code, message, *, stage=None, section_index=None, budget=False):
        if code not in STOP_CODES | {DEFECT_CODE}:
            raise ValueError(code)
        action = {
            "provider_access": "retry_after_owner",
            DEFECT_CODE: "contact_owner",
        }.get(code, "retry_now")
        self.budget = budget
        self.stop = {
            "code": code,
            "message_uk": message,
            "next_action": action,
            "next_action_label": ACTION_LABELS[action],
            "retryable": action == "retry_now",
            "stage": stage,
            "section_index": section_index,
        }
        super().__init__(message)


def unusable(message, **fields):
    return ExecutionStop("provider_unusable_response", message, **fields)


def warning(code, stage, *, section_index=None, detail=""):
    severity, message = WARNING_CODES[code]
    return {
        "code": code,
        "severity": severity,
        "stage": stage,
        "section_index": section_index,
        "message_uk": message,
        "detail": str(detail)[:1000],
        "created_at": datetime.now(UTC).isoformat(),
    }


def is_v2(job):
    return (job.request_payload or {}).get("executor_version") == 2


def status_fields(job):
    if not is_v2(job):
        return {
            "status_label": {
                **STATUS_LABELS,
                "running": "Генерується…",
                "failed": "Не вдалося",
                "failed_quality": "Якість не підтверджена",
            }.get(job.status, "Стара робота")
        }
    state = (job.request_payload or {}).get("execution", {})
    return {
        "executor_version": 2,
        "status_label": STATUS_LABELS[job.status],
        "stage": state.get("stage"),
        "stage_label": STAGE_LABELS.get(state.get("stage")),
        "sections_done": state.get("sections_done", 0),
        "sections_total": state.get("sections_total", 0),
        "last_signal": state.get("last_signal", "Роботу поставлено в чергу.")[:120],
        "cost_cents_so_far": int(job.cost_cents or 0),
        "tokens_so_far": int(job.total_tokens or 0),
        "warnings_count": state.get("warnings_count", 0),
        "stop": state.get("stop"),
        "result": state.get("result"),
    }
