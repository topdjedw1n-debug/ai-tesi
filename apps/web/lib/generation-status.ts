export function generationStopGuidance(error: string): string {
  if (/cancelled|canceled/i.test(error)) {
    return 'Запуск скасовано. Нова спроба потребує повторного перегляду умов.';
  }
  if (
    /unavailable|timeout|timed out|connection|temporar|rate limit|429/i.test(
      error
    )
  ) {
    return 'Сервіс тимчасово недоступний. Дочекайтеся відновлення доступу перед новою спробою.';
  }
  if (/too few|source preflight|source_pack_insufficient/i.test(error)) {
    return 'Не вистачило перевірених джерел. Потрібно виправити автоматичний добір для цієї теми; PDF необов’язкові.';
  }
  if (/citation|grounding|claim|quality|source pack|source-pack/i.test(error)) {
    return 'Перевірка якості або джерел зупинила роботу. Передайте причину помилки відповідальному за систему; повторюйте після виправлення.';
  }
  return 'Роботу зупинено. Передайте номер роботи й причину помилки відповідальному за систему. Нова спроба має сенс після усунення причини.';
}
