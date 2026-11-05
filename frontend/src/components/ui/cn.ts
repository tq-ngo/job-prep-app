/**
 * Join class names, skipping falsy parts.
 *
 * Deliberately not tailwind-merge: classes are concatenated, not
 * de-conflicted. Primitives take `className` for layout (width, margin,
 * flex) only; to change a look, add a variant instead of overriding one.
 */
export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}
