"use client";

import { useMemo } from "react";

import { buildCitationMap, parseCitations } from "./utils";
import type { Citation } from "./utils";

export interface UseParsedCitationsResult {
  citations: Citation[];
  cleanContent: string;
  citationMap: Map<string, Citation>;
}

/**
 * Parse content for citations and build citation map. Memoized by content.
 * Use in message and artifact components to avoid repeating parseCitations + buildCitationMap.
 */
export function useParsedCitations(content: string): UseParsedCitationsResult {
  return useMemo(() => {
    const parsed = parseCitations(content ?? "");
    const citationMap = buildCitationMap(parsed.citations);
    return {
      citations: parsed.citations,
      cleanContent: parsed.cleanContent,
      citationMap,
    };
  }, [content]);
}
