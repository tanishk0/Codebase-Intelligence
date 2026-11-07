import React from "react";
import { cn } from "@/lib/utils";

/**
 * ArclineIcon
 * Precision vector representation of the signature Arcline logo mark:
 * - 4 corner focus brackets (with top-right brilliant blue accent #60A5FA / #3B82F6)
 * - 1 central upward chevron in crisp white #FFFFFF
 */
export function ArclineIcon({
  className = "h-7 w-7",
  variant = "signature", // "signature" | "monochrome"
  ...props
}) {
  const idPrefix = React.useId().replace(/:/g, "");

  return (
    <svg
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("shrink-0 select-none", className)}
      aria-label="Arcline Logo"
      role="img"
      {...props}
    >
      <defs>
        {/* Top-Right: Vibrant Electric Azure Accent */}
        <linearGradient
          id={`${idPrefix}-tr`}
          x1="0%"
          y1="0%"
          x2="100%"
          y2="100%"
        >
          <stop offset="0%" stopColor="#70A6FF" />
          <stop offset="100%" stopColor="#3B82F6" />
        </linearGradient>

        {/* Top-Left: Frosted White Ice */}
        <linearGradient
          id={`${idPrefix}-tl`}
          x1="0%"
          y1="0%"
          x2="100%"
          y2="100%"
        >
          <stop offset="0%" stopColor="#FFFFFF" />
          <stop offset="100%" stopColor="#DCE4F0" />
        </linearGradient>

        {/* Bottom-Left: Slate Ice Steel */}
        <linearGradient
          id={`${idPrefix}-bl`}
          x1="0%"
          y1="100%"
          x2="100%"
          y2="0%"
        >
          <stop offset="0%" stopColor="#8EA2C4" />
          <stop offset="100%" stopColor="#B2C2DC" />
        </linearGradient>

        {/* Bottom-Right: Soft Slate Blue */}
        <linearGradient
          id={`${idPrefix}-br`}
          x1="100%"
          y1="100%"
          x2="0%"
          y2="0%"
        >
          <stop offset="0%" stopColor="#839BC0" />
          <stop offset="100%" stopColor="#A5B7D4" />
        </linearGradient>
      </defs>

      {/* Top-Left Corner Bracket */}
      <path
        d="M 37 10 H 22 A 12 12 0 0 0 10 22 V 37"
        fill="none"
        stroke={variant === "monochrome" ? "currentColor" : `url(#${idPrefix}-tl)`}
        strokeWidth="13.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Top-Right Corner Bracket (Signature Blue) */}
      <path
        d="M 63 10 H 78 A 12 12 0 0 1 90 22 V 37"
        fill="none"
        stroke={variant === "monochrome" ? "currentColor" : `url(#${idPrefix}-tr)`}
        strokeWidth="13.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Bottom-Left Corner Bracket */}
      <path
        d="M 10 63 V 78 A 12 12 0 0 0 22 90 H 37"
        fill="none"
        stroke={variant === "monochrome" ? "currentColor" : `url(#${idPrefix}-bl)`}
        strokeWidth="13.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Bottom-Right Corner Bracket */}
      <path
        d="M 90 63 V 78 A 12 12 0 0 1 78 90 H 63"
        fill="none"
        stroke={variant === "monochrome" ? "currentColor" : `url(#${idPrefix}-br)`}
        strokeWidth="13.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Center Upward Chevron */}
      <path
        d="M 34 62 L 50 39 L 66 62"
        fill="none"
        stroke={variant === "monochrome" ? "currentColor" : "#FFFFFF"}
        strokeWidth="13"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/**
 * ArclineLogo
 * Full brand lockup combining the ArclineIcon and modern typography wordmark.
 */
export default function ArclineLogo({
  className,
  iconClassName = "h-7 w-7",
  textClassName = "text-[16px] font-semibold tracking-[-0.015em] text-white",
  showText = true,
  variant = "signature",
  ...props
}) {
  return (
    <div
      className={cn("inline-flex items-center gap-2.5", className)}
      {...props}
    >
      <ArclineIcon className={iconClassName} variant={variant} />
      {showText && (
        <span className={cn("font-inter leading-none", textClassName)}>
          Arcline
        </span>
      )}
    </div>
  );
}
