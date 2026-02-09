"use client";

import type { ImgHTMLAttributes } from "react";
import type { ReactNode } from "react";

import {
  MessageResponse,
  type MessageResponseProps,
} from "@/components/ai-elements/message";
import { streamdownPlugins } from "@/core/streamdown";

export type MarkdownContentProps = {
  content: string;
  isLoading: boolean;
  rehypePlugins: MessageResponseProps["rehypePlugins"];
  className?: string;
  remarkPlugins?: MessageResponseProps["remarkPlugins"];
  isHuman?: boolean;
  img?: (props: ImgHTMLAttributes<HTMLImageElement> & { threadId?: string; maxWidth?: string }) => ReactNode;
};

/** Renders markdown content. */
export function MarkdownContent({
  content,
  rehypePlugins,
  className,
  remarkPlugins = streamdownPlugins.remarkPlugins,
  img,
}: MarkdownContentProps) {
  if (!content) return null;
  const components = img ? { img } : undefined;
  return (
    <MessageResponse
      className={className}
      remarkPlugins={remarkPlugins}
      rehypePlugins={rehypePlugins}
      components={components}
    >
      {content}
    </MessageResponse>
  );
}
