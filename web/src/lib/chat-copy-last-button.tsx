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
        // In the flow below the image controls with a 44px tap target, so
        // it never covers the last terminal rows on a phone.
        "z-10 self-end mt-2 min-h-11 min-w-11 px-2 py-1 text-xs",
        "normal-case tracking-normal font-normal",
        "rounded border border-current/30",
        "bg-black/20",
        "opacity-70 hover:opacity-100 hover:border-current/60",
        "transition-opacity duration-150",
      )}
      style={{ color }}
    >
      <span className="inline-flex items-center gap-1.5">
        <Copy className="h-3 w-3 shrink-0" />
        <span className="hidden min-[400px]:inline tracking-wide">
          {copied ? "copied" : "copy last response"}
        </span>
      </span>
    </Button>
  );
}
