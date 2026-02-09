/**
 * Citation data structure representing a source reference
 */
export interface Citation {
  id: string;
  title: string;
  url: string;
  snippet: string;
}

/**
 * Result of parsing citations from content
 */
export interface ParseCitationsResult {
  citations: Citation[];
  cleanContent: string;
}

/**
 * Parse citations block from message content.
 *
 * The citations block format:
 * <citations>
 * {"id": "cite-1", "title": "Page Title", "url": "https://example.com", "snippet": "Description"}
 * {"id": "cite-2", "title": "Another Page", "url": "https://example2.com", "snippet": "Description"}
 * </citations>
 *
 * @param content - The raw message content that may contain a citations block
 * @returns Object containing parsed citations array and content with citations block removed
 */
export function parseCitations(content: string): ParseCitationsResult {
  if (!content) {
    return { citations: [], cleanContent: content };
  }

  // Match ALL citations blocks anywhere in content (not just at the start)
  const citationsRegex = /<citations>([\s\S]*?)<\/citations>/g;
  const citations: Citation[] = [];
  const seenUrls = new Set<string>(); // Deduplicate by URL
  let cleanContent = content;

  let match;
  while ((match = citationsRegex.exec(content)) !== null) {
    const citationsBlock = match[1] ?? "";

    // Parse each line as JSON
    const lines = citationsBlock.split("\n");
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed?.startsWith("{")) {
        try {
          const citation = JSON.parse(trimmed) as Citation;
          // Validate required fields and deduplicate
          if (citation.id && citation.url && !seenUrls.has(citation.url)) {
            seenUrls.add(citation.url);
            citations.push({
              id: citation.id,
              title: citation.title || "",
              url: citation.url,
              snippet: citation.snippet || "",
            });
          }
        } catch {
          // Skip invalid JSON lines - this can happen during streaming
        }
      }
    }
  }

  cleanContent = removeCitationsBlocks(content);

  // Convert [cite-N] references to markdown links
  // Example: [cite-1] -> [Title](url)
  if (citations.length > 0) {
    // Build a map from citation id to citation object
    const idMap = new Map<string, Citation>();
    for (const citation of citations) {
      idMap.set(citation.id, citation);
    }

    // Replace all [cite-N] patterns with markdown links
    cleanContent = cleanContent.replace(/\[cite-(\d+)\]/g, (match, num) => {
      const citeId = `cite-${num}`;
      const citation = idMap.get(citeId);
      if (citation) {
        // Use title if available, otherwise use domain
        const linkText = citation.title || extractDomainFromUrl(citation.url);
        return `[${linkText}](${citation.url})`;
      }
      // If citation not found, keep the original text
      return match;
    });
  }

  return { citations, cleanContent };
}

/**
 * Return content with citations block removed and [cite-N] replaced by markdown links.
 */
export function getCleanContent(content: string): string {
  return parseCitations(content ?? "").cleanContent;
}

/**
 * Build a map from URL to Citation for quick lookup
 *
 * @param citations - Array of citations
 * @returns Map with URL as key and Citation as value
 */
export function buildCitationMap(
  citations: Citation[],
): Map<string, Citation> {
  const map = new Map<string, Citation>();
  for (const citation of citations) {
    map.set(citation.url, citation);
  }
  return map;
}

/**
 * Whether the URL is external (http/https).
 */
export function isExternalUrl(url: string): boolean {
  return url.startsWith("http://") || url.startsWith("https://");
}

/**
 * Build a synthetic Citation from a link (e.g. in artifact markdown without <citations> block).
 */
export function syntheticCitationFromLink(href: string, title: string): Citation {
  return {
    id: `artifact-cite-${href}`,
    title: title || href,
    url: href,
    snippet: "",
  };
}

/**
 * Extract the domain name from a URL for display
 *
 * @param url - Full URL string
 * @returns Domain name or the original URL if parsing fails
 */
export function extractDomainFromUrl(url: string): string {
  try {
    const urlObj = new URL(url);
    // Remove 'www.' prefix if present
    return urlObj.hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/**
 * Remove all <citations> blocks from content (complete and incomplete).
 * Does not remove [cite-N] or markdown links; use removeAllCitations for that.
 */
export function removeCitationsBlocks(content: string): string {
  if (!content) return content;
  let result = content.replace(/<citations>[\s\S]*?<\/citations>/g, "").trim();
  if (result.includes("<citations>")) {
    result = result.replace(/<citations>[\s\S]*$/g, "").trim();
  }
  return result;
}

/**
 * Whether content contains a <citations> block (open tag).
 */
export function hasCitationsBlock(content: string): boolean {
  return Boolean(content?.includes("<citations>"));
}

/**
 * Check if content is still receiving the citations block (streaming)
 * This helps determine if we should wait before parsing
 *
 * @param content - The current content being streamed
 * @returns true if citations block appears to be incomplete
 */
export function isCitationsBlockIncomplete(content: string): boolean {
  return hasCitationsBlock(content) && !content.includes("</citations>");
}

/**
 * Strip citation markdown links from already-cleaned content (from parseCitations).
 * Use when you already have ParseCitationsResult to avoid parsing twice.
 */
export function contentWithoutCitationsFromParsed(
  parsed: ParseCitationsResult,
): string {
  const citationUrls = new Set(parsed.citations.map((c) => c.url));
  const withoutLinks = parsed.cleanContent.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    (fullMatch, _text, url) => (citationUrls.has(url) ? "" : fullMatch),
  );
  return withoutLinks.replace(/\n{3,}/g, "\n\n").trim();
}

/**
 * Remove ALL citations from content (blocks, [cite-N], and citation links).
 * Used for copy/download. For display you typically use parseCitations/useParsedCitations.
 */
export function removeAllCitations(content: string): string {
  if (!content) return content;
  return contentWithoutCitationsFromParsed(parseCitations(content));
}
