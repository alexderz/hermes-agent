import { Button } from "@nous-research/ui/ui/components/button";
import { Copy } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Floating "copy last response" overlay on the chat terminal: sends `/copy` over
 * the PTY (see chat-copy-last.ts) and shows "copied" for the 1.5s reset window.
 */
export function CopyLastButton({
  onClick,
  copied,
  color,
}: {
  onClick: () => void;
  copied: boolean;
  color: string;
}) {
  return (
    <Button
      ghost
      onClick={onClick}
      title="Copy last assistant response as raw markdown"
      aria-label="Copy last assistant response"
      className={cn(
        // Lives in the floating chat toolbar (top-right), never in the
        // layout flow, so the terminal keeps its full height when the phone
        // keyboard opens.
        "h-9 min-w-9 px-2 text-xs inline-flex items-center justify-center",
        "normal-case tracking-normal font-normal",
        "rounded border border-current/30",
        "bg-black/60",
        "opacity-80 hover:opacity-100 hover:border-current/60",
        "transition-opacity duration-150",
      )}
      style={{ color }}
    >
      <span className="inline-flex items-center gap-1.5">
        <Copy className="h-3 w-3 shrink-0" />
        <span className="hidden sm:inline tracking-wide">
          {copied ? "copied" : "copy last response"}
        </span>
      </span>
    </Button>
  );
}
