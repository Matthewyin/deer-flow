import type { Message } from "@langchain/langgraph-sdk";
import { ExternalLinkIcon, FileIcon, LinkIcon } from "lucide-react";
import { useParams } from "next/navigation";
import { memo, useMemo } from "react";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";

import {
  InlineCitationCard,
  InlineCitationCardBody,
  InlineCitationSource,
} from "@/components/ai-elements/inline-citation";
import {
  Message as AIElementMessage,
  MessageContent as AIElementMessageContent,
  MessageResponse as AIElementMessageResponse,
  MessageToolbar,
} from "@/components/ai-elements/message";
import { Badge } from "@/components/ui/badge";
import { HoverCardTrigger } from "@/components/ui/hover-card";
import { resolveArtifactURL } from "@/core/artifacts/utils";
import {
  type Citation,
  buildCitationMap,
  extractDomainFromUrl,
  parseCitations,
} from "@/core/citations";
import {
  extractContentFromMessage,
  extractReasoningContentFromMessage,
  parseUploadedFiles,
  type UploadedFile,
} from "@/core/messages/utils";
import { useRehypeSplitWordsIntoSpans } from "@/core/rehype";
import { cn } from "@/lib/utils";

import { CopyButton } from "../copy-button";

export function MessageListItem({
  className,
  message,
  isLoading,
}: {
  className?: string;
  message: Message;
  isLoading?: boolean;
}) {
  return (
    <AIElementMessage
      className={cn("group/conversation-message relative w-full", className)}
      from={message.type === "human" ? "user" : "assistant"}
    >
      <MessageContent
        className={message.type === "human" ? "w-fit" : "w-full"}
        message={message}
        isLoading={isLoading}
      />
      <MessageToolbar
        className={cn(
          message.type === "human" && "justify-end",
          message.type === "human" ? "-bottom-9" : "-bottom-8",
          "absolute right-0 left-0 z-20 opacity-0 transition-opacity delay-200 duration-300 group-hover/conversation-message:opacity-100",
        )}
      >
        <div className="flex gap-1">
          <CopyButton
            clipboardData={
              extractContentFromMessage(message)
                ? extractContentFromMessage(message)
                : (extractReasoningContentFromMessage(message) ?? "")
            }
          />
        </div>
      </MessageToolbar>
    </AIElementMessage>
  );
}

function MessageContent_({
  className,
  message,
  isLoading = false,
}: {
  className?: string;
  message: Message;
  isLoading?: boolean;
}) {
  const rehypePlugins = useRehypeSplitWordsIntoSpans(isLoading);
  const isHuman = message.type === "human";

  // Extract and parse citations and uploaded files from message content
  const { citations, cleanContent, uploadedFiles } = useMemo(() => {
    const reasoningContent = extractReasoningContentFromMessage(message);
    const rawContent = extractContentFromMessage(message);
    if (!isLoading && reasoningContent && !rawContent) {
      return { citations: [], cleanContent: reasoningContent, uploadedFiles: [] };
    }

    // For human messages, first parse uploaded files
    if (isHuman && rawContent) {
      const { files, cleanContent: contentWithoutFiles } = parseUploadedFiles(rawContent);
      const { citations, cleanContent: finalContent } = parseCitations(contentWithoutFiles);
      return { citations, cleanContent: finalContent, uploadedFiles: files };
    }

    const { citations, cleanContent } = parseCitations(rawContent ?? "");
    return { citations, cleanContent, uploadedFiles: [] };
  }, [isLoading, message, isHuman]);

  // Build citation map for quick URL lookup
  const citationMap = useMemo(
    () => buildCitationMap(citations),
    [citations],
  );

  const { thread_id } = useParams<{ thread_id: string }>();

  // For human messages with uploaded files, render files outside the bubble
  if (isHuman && uploadedFiles.length > 0) {
    return (
      <div className={cn("ml-auto flex flex-col gap-2", className)}>
        {/* Uploaded files outside the message bubble */}
        <UploadedFilesList files={uploadedFiles} threadId={thread_id} />
        
        {/* Message content inside the bubble (only if there's text) */}
        {cleanContent && (
          <AIElementMessageContent className="w-fit">
            <AIElementMessageResponse
              remarkPlugins={[[remarkMath, { singleDollarTextMath: true }]]}
              rehypePlugins={[...rehypePlugins, [rehypeKatex, { output: "html" }]]}
              components={{
                a: ({
                  href,
                  children,
                }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => {
                  if (!href) {
                    return <span>{children}</span>;
                  }

                  // Check if this link matches a citation
                  const citation = citationMap.get(href);
                  if (citation) {
                    return (
                      <CitationLink citation={citation} href={href}>
                        {children}
                      </CitationLink>
                    );
                  }

                  // Regular external link
                  return (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary underline underline-offset-2 hover:no-underline"
                    >
                      {children}
                    </a>
                  );
                },
                img: ({ src, alt }: React.ImgHTMLAttributes<HTMLImageElement>) => {
                  if (!src) return null;
                  if (typeof src !== "string") {
                    return (
                      <img
                        className="max-w-full overflow-hidden rounded-lg"
                        src={src}
                        alt={alt}
                      />
                    );
                  }
                  let url = src;
                  if (src.startsWith("/mnt/")) {
                    url = resolveArtifactURL(src, thread_id);
                  }
                  return (
                    <a href={url} target="_blank" rel="noopener noreferrer">
                      <img
                        className="max-w-full overflow-hidden rounded-lg"
                        src={url}
                        alt={alt}
                      />
                    </a>
                  );
                },
              }}
            >
              {cleanContent}
            </AIElementMessageResponse>
          </AIElementMessageContent>
        )}
      </div>
    );
  }

  // Default rendering for non-human messages or human messages without files
  return (
    <AIElementMessageContent className={className}>
      {/* Uploaded files for human messages - show first */}
      {uploadedFiles.length > 0 && thread_id && (
        <UploadedFilesList files={uploadedFiles} threadId={thread_id} />
      )}

      {/* Message content - always show if present */}
      {cleanContent && (
        <AIElementMessageResponse
          remarkPlugins={[[remarkMath, { singleDollarTextMath: true }]]}
          rehypePlugins={[...rehypePlugins, [rehypeKatex, { output: "html" }]]}
          components={{
            a: ({
              href,
              children,
            }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => {
              if (!href) {
                return <span>{children}</span>;
              }

              // Check if this link matches a citation
              const citation = citationMap.get(href);
              if (citation) {
                return (
                  <CitationLink citation={citation} href={href}>
                    {children}
                  </CitationLink>
                );
              }

              // Regular external link
              return (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline underline-offset-2 hover:no-underline"
                >
                  {children}
                </a>
              );
            },
            img: ({ src, alt }: React.ImgHTMLAttributes<HTMLImageElement>) => {
              if (!src) return null;
              if (typeof src !== "string") {
                return (
                  <img
                    className="max-w-full overflow-hidden rounded-lg"
                    src={src}
                    alt={alt}
                  />
                );
              }
              let url = src;
              if (src.startsWith("/mnt/")) {
                url = resolveArtifactURL(src, thread_id);
              }
              return (
                <a href={url} target="_blank" rel="noopener noreferrer">
                  <img
                    className="max-w-full overflow-hidden rounded-lg"
                    src={url}
                    alt={alt}
                  />
                </a>
              );
            },
          }}
        >
          {cleanContent}
        </AIElementMessageResponse>
      )}
    </AIElementMessageContent>
  );
}

/**
 * Get file type label from filename extension
 */
function getFileTypeLabel(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  const typeMap: Record<string, string> = {
    json: "JSON",
    csv: "CSV",
    txt: "TXT",
    md: "Markdown",
    py: "Python",
    js: "JavaScript",
    ts: "TypeScript",
    tsx: "TSX",
    jsx: "JSX",
    html: "HTML",
    css: "CSS",
    xml: "XML",
    yaml: "YAML",
    yml: "YAML",
    pdf: "PDF",
    png: "PNG",
    jpg: "JPG",
    jpeg: "JPEG",
    gif: "GIF",
    svg: "SVG",
    zip: "ZIP",
    tar: "TAR",
    gz: "GZ",
  };
  return typeMap[ext] || ext.toUpperCase() || "FILE";
}

/**
 * Check if a file is an image based on extension
 */
function isImageFile(filename: string): boolean {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"].includes(ext);
}

/**
 * Uploaded files list component that displays files as cards or image thumbnails (Claude-style)
 */
function UploadedFilesList({
  files,
  threadId,
}: {
  files: UploadedFile[];
  threadId: string;
}) {
  if (files.length === 0) return null;

  return (
    <div className="mb-2 flex flex-wrap gap-2">
      {files.map((file, index) => (
        <UploadedFileCard
          key={`${file.path}-${index}`}
          file={file}
          threadId={threadId}
        />
      ))}
    </div>
  );
}

/**
 * Single uploaded file card component (Claude-style)
 * Shows image thumbnail for image files, file card for others
 */
function UploadedFileCard({
  file,
  threadId,
}: {
  file: UploadedFile;
  threadId: string;
}) {
  const typeLabel = getFileTypeLabel(file.filename);
  const isImage = isImageFile(file.filename);

  // Don't render if threadId is invalid
  if (!threadId) {
    return null;
  }

  // Build URL - browser will handle encoding automatically
  const imageUrl = resolveArtifactURL(file.path, threadId);

  // For image files, show thumbnail
  if (isImage) {
    return (
      <a
        href={imageUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="group relative block overflow-hidden rounded-lg border border-border/40"
      >
        <img
          src={imageUrl}
          alt={file.filename}
          className="h-32 w-auto max-w-[240px] object-cover transition-transform group-hover:scale-105"
        />
      </a>
    );
  }

  // For non-image files, show file card
  return (
    <div className="bg-background flex min-w-[120px] max-w-[200px] flex-col gap-1 rounded-lg border border-border/40 p-3 shadow-sm">
      <div className="flex items-start gap-2">
        <FileIcon className="text-muted-foreground mt-0.5 size-4 shrink-0" />
        <span
          className="text-foreground truncate text-sm font-medium"
          title={file.filename}
        >
          {file.filename}
        </span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <Badge
          variant="secondary"
          className="rounded px-1.5 py-0.5 text-[10px] font-normal"
        >
          {typeLabel}
        </Badge>
        <span className="text-muted-foreground text-[10px]">{file.size}</span>
      </div>
    </div>
  );
}

/**
 * Citations list component that displays all sources at the top
 */
function CitationsList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;

  return (
    <div className="mb-4 rounded-lg border bg-muted/30 p-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <LinkIcon className="size-4" />
        <span>Sources ({citations.length})</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {citations.map((citation) => (
          <CitationBadge key={citation.id} citation={citation} />
        ))}
      </div>
    </div>
  );
}

/**
 * Single citation badge in the citations list
 */
function CitationBadge({ citation }: { citation: Citation }) {
  const domain = extractDomainFromUrl(citation.url);

  return (
    <InlineCitationCard>
      <HoverCardTrigger asChild>
        <a
          href={citation.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex"
        >
          <Badge
            variant="secondary"
            className="cursor-pointer gap-1 rounded-full px-2.5 py-1 text-xs font-normal hover:bg-secondary/80"
          >
            {domain}
            <ExternalLinkIcon className="size-3" />
          </Badge>
        </a>
      </HoverCardTrigger>
      <InlineCitationCardBody>
        <div className="p-3">
          <InlineCitationSource
            title={citation.title}
            url={citation.url}
            description={citation.snippet}
          />
          <a
            href={citation.url}
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
 * Citation link component that renders as a hover card badge
 */
function CitationLink({
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
const MessageContent = memo(MessageContent_);
