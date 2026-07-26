export function isValidPlayerIdentifier(value: string): boolean {
  const normalized = value.trim();
  return normalized.length >= 1
    && normalized.length <= 64
    && !Array.from(normalized).some((character) => character.charCodeAt(0) < 32);
}
