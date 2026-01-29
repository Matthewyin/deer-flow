import {
  Code2Icon,
  CopyIcon,
  DownloadIcon,
  ExternalLinkIcon,
  EyeIcon,
  SquareArrowOutUpRightIcon,
  XIcon,
} from "lucide-react";
import * as React from "react";
import { useEffect, useMemo, useState } from "react";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";
import { toast } from "sonner";
import { Streamdown } from "streamdown";

import {
  Artifact,
  ArtifactAction,
  ArtifactActions,
  ArtifactContent,
  ArtifactHeader,
  ArtifactTitle,
} from "@/components/ai-elements/artifact";
import {
  InlineCitationCard,
  InlineCitationCardBody,
  InlineCitationSource,
} from "@/components/ai-elements/inline-citation";
import { Badge } from "@/components/ui/badge";
import { HoverCardTrigger } from "@/components/ui/hover-card";
import {
  buildCitationMap,
  extractDomainFromUrl,
  parseCitations,
  type Citation,
} from "@/core/citations";
import { Select, SelectItem } from "@/components/ui/select";
import {
  SelectContent,
  SelectGroup,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { CodeEditor } from "@/components/workspace/code-editor";
import { useArtifactContent } from "@/core/artifacts/hooks";
import { urlOfArtifact } from "@/core/artifacts/utils";
import { useI18n } from "@/core/i18n/hooks";
import { checkCodeFile, getFileName } from "@/core/utils/files";
import { cn } from "@/lib/utils";

import { useArtifacts } from "./context";

export function ArtifactFileDetail({
  className,
  filepath: filepathFromProps,
  threadId,
}: {
  className?: string;
  filepath: string;
  threadId: string;
}) {
  const { t } = useI18n();
  const { artifacts, setOpen, select } = useArtifacts();
  const isWriteFile = useMemo(() => {
    return filepathFromProps.startsWith("write-file:");
  }, [filepathFromProps]);
  const filepath = useMemo(() => {
    if (isWriteFile) {
      const url = new URL(filepathFromProps);
      return decodeURIComponent(url.pathname);
    }
    return filepathFromProps;
  }, [filepathFromProps, isWriteFile]);
  const { isCodeFile, language } = useMemo(() => {
    if (isWriteFile) {
      let language = checkCodeFile(filepath).language;
      language ??= "text";
      return { isCodeFile: true, language };
    }
    return checkCodeFile(filepath);
  }, [filepath, isWriteFile]);
  const previewable = useMemo(() => {
    return (language === "html" && !isWriteFile) || language === "markdown";
  }, [isWriteFile, language]);
  const { content } = useArtifactContent({
    threadId,
    filepath: filepathFromProps,
    enabled: isCodeFile && !isWriteFile,
  });
  
  // Parse citations and get clean content for code editor
  const cleanContent = useMemo(() => {
    if (language === "markdown" && content) {
      return parseCitations(content).cleanContent;
    }
    return content;
  }, [content, language]);
  
  const [viewMode, setViewMode] = useState<"code" | "preview">("code");
  useEffect(() => {
    if (previewable) {
      setViewMode("preview");
    } else {
      setViewMode("code");
    }
  }, [previewable]);
  return (
    <Artifact className={cn(className)}>
      <ArtifactHeader className="px-2">
        <div className="flex items-center gap-2">
          <ArtifactTitle>
            {isWriteFile ? (
              <div className="px-2">{getFileName(filepath)}</div>
            ) : (
              <Select value={filepath} onValueChange={select}>
                <SelectTrigger className="border-none bg-transparent! shadow-none select-none focus:outline-0 active:outline-0">
                  <SelectValue placeholder="Select a file" />
                </SelectTrigger>
                <SelectContent className="select-none">
                  <SelectGroup>
                    {(artifacts ?? []).map((filepath) => (
                      <SelectItem key={filepath} value={filepath}>
                        {getFileName(filepath)}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            )}
          </ArtifactTitle>
        </div>
        <div className="flex min-w-0 grow items-center justify-center">
          {previewable && (
            <ToggleGroup
              className="mx-auto"
              type="single"
              variant="outline"
              size="sm"
              value={viewMode}
              onValueChange={(value) =>
                setViewMode(value as "code" | "preview")
              }
            >
              <ToggleGroupItem value="code">
                <Code2Icon />
              </ToggleGroupItem>
              <ToggleGroupItem value="preview">
                <EyeIcon />
              </ToggleGroupItem>
            </ToggleGroup>
          )}
        </div>
        <div className="flex items-center gap-2">
          <ArtifactActions>
            {!isWriteFile && (
              <a href={urlOfArtifact({ filepath, threadId })} target="_blank">
                <ArtifactAction
                  icon={SquareArrowOutUpRightIcon}
                  label={t.common.openInNewWindow}
                  tooltip={t.common.openInNewWindow}
                />
              </a>
            )}
            {isCodeFile && (
              <ArtifactAction
                icon={CopyIcon}
                label={t.clipboard.copyToClipboard}
                disabled={!content}
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(content ?? "");
                    toast.success(t.clipboard.copiedToClipboard);
                  } catch (error) {
                    toast.error("Failed to copy to clipboard");
                    console.error(error);
                  }
                }}
                tooltip={t.clipboard.copyToClipboard}
              />
            )}
            {!isWriteFile && (
              <a
                href={urlOfArtifact({ filepath, threadId, download: true })}
                target="_blank"
              >
                <ArtifactAction
                  icon={DownloadIcon}
                  label={t.common.download}
                  tooltip={t.common.download}
                />
              </a>
            )}
            <ArtifactAction
              icon={XIcon}
              label={t.common.close}
              onClick={() => setOpen(false)}
              tooltip={t.common.close}
            />
          </ArtifactActions>
        </div>
      </ArtifactHeader>
      <ArtifactContent className="p-0">
        {previewable && viewMode === "preview" && (
          <ArtifactFilePreview
            filepath={filepath}
            threadId={threadId}
            content={content}
            language={language ?? "text"}
          />
        )}
        {isCodeFile && viewMode === "code" && (
          <CodeEditor
            className="size-full resize-none rounded-none border-none"
            value={cleanContent ?? ""}
            readonly
          />
        )}
        {!isCodeFile && (
          <iframe
            className="size-full"
            src={urlOfArtifact({ filepath, threadId })}
          />
        )}
      </ArtifactContent>
    </Artifact>
  );
}

export function ArtifactFilePreview({
  filepath,
  threadId,
  content,
  language,
}: {
  filepath: string;
  threadId: string;
  content: string;
  language: string;
}) {
  const { citations, cleanContent, citationMap } = React.useMemo(() => {
    const parsed = parseCitations(content ?? "");
    const map = buildCitationMap(parsed.citations);
    return {
      citations: parsed.citations,
      cleanContent: parsed.cleanContent,
      citationMap: map,
    };
  }, [content]);

  if (language === "markdown") {
    return (
      <div className="size-full px-4">
        <Streamdown
          className="size-full"
          remarkPlugins={[[remarkMath, { singleDollarTextMath: true }]]}
          rehypePlugins={[[rehypeKatex, { output: "html" }]]}
          components={{
            a: ({
              href,
              children,
            }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => {
              if (!href) {
                return <span>{children}</span>;
              }

              // Check if it's a citation link
              const citation = citationMap.get(href);
              if (citation) {
                return (
                  <ArtifactCitationLink citation={citation} href={href}>
                    {children}
                  </ArtifactCitationLink>
                );
              }

              // Check if it's an external link (http/https)
              const isExternalLink =
                href.startsWith("http://") || href.startsWith("https://");

              if (isExternalLink) {
                return (
                  <ExternalLinkBadge href={href}>{children}</ExternalLinkBadge>
                );
              }

              // Internal/anchor link
              return (
                <a href={href} className="text-primary hover:underline">
                  {children}
                </a>
              );
            },
          }}
        >
          {cleanContent ?? ""}
        </Streamdown>
      </div>
    );
  }
  if (language === "html") {
    return (
      <iframe
        className="size-full"
        src={urlOfArtifact({ filepath, threadId })}
      />
    );
  }
  return null;
}

/**
 * Citation link component for artifact preview (with full citation data)
 */
function ArtifactCitationLink({
  citation,
  href,
  children,
}: {
  citation: Citation;
  href: string;
  children: React.ReactNode;
}) {
  const domain = extractDomainFromUrl(href);

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
            className="mx-0.5 cursor-pointer gap-1 rounded-full px-2 py-0.5 text-xs font-normal hover:bg-secondary/80"
          >
            {children ?? domain}
            <ExternalLinkIcon className="size-3" />
          </Badge>
        </a>
      </HoverCardTrigger>
      <InlineCitationCardBody>
        <div className="p-3">
          <InlineCitationSource
            title={citation.title}
            url={href}
            description={citation.snippet}
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
}

/**
 * External link badge component for artifact preview
 */
function ExternalLinkBadge({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  const domain = extractDomainFromUrl(href);

  return (
    <InlineCitationCard>
      <HoverCardTrigger asChild>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center"
        >
          <Badge
            variant="secondary"
            className="mx-0.5 cursor-pointer gap-1 rounded-full px-2 py-0.5 text-xs font-normal hover:bg-secondary/80"
          >
            {children ?? domain}
            <ExternalLinkIcon className="size-3" />
          </Badge>
        </a>
      </HoverCardTrigger>
      <InlineCitationCardBody>
        <div className="p-3">
          <InlineCitationSource title={domain} url={href} />
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
}
