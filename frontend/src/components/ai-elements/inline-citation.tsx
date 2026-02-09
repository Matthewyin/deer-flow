"use client";

import { Badge } from "@/components/ui/badge";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";
import {
  cn,
  externalLinkClass,
  externalLinkClassNoUnderline,
} from "@/lib/utils";
import { ExternalLinkIcon } from "lucide-react";
import { type ComponentProps, Children } from "react";
import type { Citation } from "@/core/citations";
import {
  extractDomainFromUrl,
  isExternalUrl,
  syntheticCitationFromLink,
} from "@/core/citations";
import { Shimmer } from "./shimmer";
import { useI18n } from "@/core/i18n/hooks";

export type InlineCitationCardProps = ComponentProps<typeof HoverCard>;

export const InlineCitationCard = (props: InlineCitationCardProps) => (
  <HoverCard closeDelay={0} openDelay={0} {...props} />
);

export type InlineCitationCardBodyProps = ComponentProps<"div">;

export const InlineCitationCardBody = ({
  className,
  ...props
}: InlineCitationCardBodyProps) => (
  <HoverCardContent className={cn("relative w-80 p-0", className)} {...props} />
);

export type InlineCitationSourceProps = ComponentProps<"div"> & {
  title?: string;
  url?: string;
  description?: string;
};

export const InlineCitationSource = ({
  title,
  url,
  description,
  className,
  children,
  ...props
}: InlineCitationSourceProps) => (
  <div className={cn("space-y-1", className)} {...props}>
    {title && (
      <h4 className="truncate font-medium text-sm leading-tight">{title}</h4>
    )}
    {url && (
      <p className="truncate break-all text-muted-foreground text-xs">{url}</p>
    )}
    {description && (
      <p className="line-clamp-3 text-muted-foreground text-sm leading-relaxed">
        {description}
      </p>
    )}
    {children}
  </div>
);

/**
 * Shared CitationLink component that renders a citation as a hover card badge
 * Used across message-list-item, artifact-file-detail, and message-group
 * 
 * When citation is provided, displays title and snippet from the citation.
 * When citation is omitted, falls back to displaying the domain name extracted from href.
 */
export type CitationLinkProps = {
  citation?: Citation;
  href: string;
  children: React.ReactNode;
};

export const CitationLink = ({
  citation,
  href,
  children,
}: CitationLinkProps) => {
  const domain = extractDomainFromUrl(href);
  
  // Priority: citation.title > children (if meaningful) > domain
  // - citation.title: from parsed <citations> block, most accurate
  // - children: from markdown link text [Text](url), used when no citation data
  // - domain: fallback when both above are unavailable
  // Skip children if it's a generic placeholder like "Source"
  const childrenText = typeof children === "string" ? children : null;
  const isGenericText = childrenText === "Source" || childrenText === "来源";
  const displayText = citation?.title || (!isGenericText && childrenText) || domain;

  return (
    <InlineCitationCard>
      <HoverCardTrigger asChild>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center"
          onClick={(e) => e.stopPropagation()}
        >
          <Badge
            variant="secondary"
            className="hover:bg-secondary/80 mx-0.5 cursor-pointer gap-1 rounded-full px-2 py-0.5 text-xs font-normal"
          >
            {displayText}
            <ExternalLinkIcon className="size-3" />
          </Badge>
        </a>
      </HoverCardTrigger>
      <InlineCitationCardBody>
        <div className="p-3">
          <InlineCitationSource
            title={citation?.title || domain}
            url={href}
            description={citation?.snippet}
          />
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary mt-2 inline-flex items-center gap-1 text-xs hover:underline"
          >
            Visit source
            <ExternalLinkIcon className="size-3" />
          </a>
        </div>
      </InlineCitationCardBody>
    </InlineCitationCard>
  );
};

/**
 * Renders a link with optional citation badge. Use in markdown components (message + artifact).
 * - citationMap: URL -> Citation; links in map render as CitationLink.
 * - isHuman: when true, never render as CitationLink (plain link).
 * - isLoadingCitations: when true and not human, non-citation links use no-underline style.
 * - syntheticExternal: when true, external URLs not in citationMap render as CitationLink with synthetic citation.
 */
export type CitationAwareLinkProps = ComponentProps<"a"> & {
  citationMap: Map<string, Citation>;
  isHuman?: boolean;
  isLoadingCitations?: boolean;
  syntheticExternal?: boolean;
};

export const CitationAwareLink = ({
  href,
  children,
  citationMap,
  isHuman = false,
  isLoadingCitations = false,
  syntheticExternal = false,
  className,
  ...rest
}: CitationAwareLinkProps) => {
  if (!href) return <span>{children}</span>;

  const citation = citationMap.get(href);

  if (citation && !isHuman) {
    return (
      <CitationLink citation={citation} href={href}>
        {children}
      </CitationLink>
    );
  }

  if (syntheticExternal && isExternalUrl(href)) {
    const linkText =
      typeof children === "string"
        ? children
        : String(Children.toArray(children).join("")).trim() || href;
    return (
      <CitationLink
        citation={syntheticCitationFromLink(href, linkText)}
        href={href}
      >
        {children}
      </CitationLink>
    );
  }

  const noUnderline = !isHuman && isLoadingCitations;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(noUnderline ? externalLinkClassNoUnderline : externalLinkClass, className)}
      {...rest}
    >
      {children}
    </a>
  );
};

/**
 * Shared CitationsLoadingIndicator component
 * Used across message-list-item and message-group to show loading citations
 */
export type CitationsLoadingIndicatorProps = {
  citations: Citation[];
  className?: string;
};

export const CitationsLoadingIndicator = ({
  citations,
  className,
}: CitationsLoadingIndicatorProps) => {
  const { t } = useI18n();

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <Shimmer duration={2.5} className="text-sm">
        {citations.length > 0
          ? t.citations.loadingCitationsWithCount(citations.length)
          : t.citations.loadingCitations}
      </Shimmer>
      {citations.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {citations.map((citation) => (
            <Badge
              key={citation.id}
              variant="secondary"
              className="animate-fade-in gap-1 rounded-full px-2.5 py-1 text-xs font-normal"
            >
              <Shimmer duration={2} as="span">
                {citation.title || extractDomainFromUrl(citation.url)}
              </Shimmer>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
};
