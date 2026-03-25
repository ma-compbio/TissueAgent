/** Content-parsing utilities ported from the Python backend. */

/**
 * Split a ROUTE: header from the message body.
 * Returns [routeCaption, body].
 */
export function splitRouteAndBody(
  content: string
): [string | null, string] {
  const lines = content
    .trim()
    .split("\n")
    .filter((l) => l.trim());
  if (lines.length > 0 && lines[0].toUpperCase().startsWith("ROUTE:")) {
    const route = lines[0].split(":").slice(1).join(":").trim() || null;
    const body = lines.slice(1).join("\n").trim();
    return [route, body];
  }
  return [null, content.trim()];
}

const ALLOWED_TAGS = ["execute", "response", "scratchpad", "plan"];

/**
 * Extract <execute>, <response>, <scratchpad>, <plan> tags from content.
 * Returns a map of tag name → content, or null if none found.
 */
export function extractHtmlTags(
  content: string
): Record<string, string> | null {
  const tagPattern = ALLOWED_TAGS.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  const regex = new RegExp(
    `<(${tagPattern})>(.*?)(?:<\\/\\1>|$)`,
    "gis"
  );

  const result: Record<string, string> = {};
  let match: RegExpExecArray | null;
  let found = false;

  while ((match = regex.exec(content)) !== null) {
    found = true;
    result[match[1].toLowerCase()] = match[2].trim();
  }

  return found ? result : null;
}
