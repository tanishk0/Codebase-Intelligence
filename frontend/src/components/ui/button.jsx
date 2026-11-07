import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva } from "class-variance-authority";
import { ArrowRight, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 cursor-pointer select-none",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline:
          "border border-input bg-background shadow-xs hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground shadow-xs hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
        // Design System Variants (Dark Mode Standard)
        brandPrimary:
          "rounded-[10px] bg-[#EAECEF] text-[#0B0F16] shadow-sm hover:bg-white active:scale-[0.98] border border-transparent font-medium",
        brandSecondary:
          "rounded-[10px] border border-[#243041] bg-[#111622]/90 text-[#E5E7EB] hover:bg-[#1A2232] hover:border-[#374558] active:scale-[0.98] font-medium",
      },
      size: {
        default: "h-9 px-4 py-2 text-[13.5px]",
        sm: "h-9 rounded-[9px] px-4 text-[13px]",
        md: "h-10 rounded-[10px] px-4 py-2.5 text-[14px]",
        lg: "h-11 rounded-[10px] px-5 py-2.5 text-[14px]",
        icon: "h-9 w-9 rounded-[9px]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

const Button = React.forwardRef(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

/**
 * PrimaryButton — Solid White (#FFFFFF) button with dark Ink (#0B0F16) text,
 * optional trailing arrow, loading spinner, and full Radix Slot (`asChild`) support.
 */
const PrimaryButton = React.forwardRef(
  (
    {
      children,
      className,
      size = "md",
      withArrow = false,
      isLoading = false,
      disabled,
      asChild = false,
      icon: Icon,
      ...props
    },
    ref
  ) => {
    const classes = cn(
      buttonVariants({ variant: "brandPrimary", size }),
      "group font-inter tracking-tight",
      className
    );

    const renderInner = (labelContent) => (
      <>
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin text-[#0B0F16]" />
        ) : Icon ? (
          <Icon className="h-4 w-4" />
        ) : null}
        <span>{labelContent}</span>
        {withArrow && !isLoading && (
          <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
        )}
      </>
    );

    if (asChild && React.isValidElement(children)) {
      return (
        <Slot ref={ref} className={classes} {...props}>
          {React.cloneElement(
            children,
            undefined,
            renderInner(children.props.children)
          )}
        </Slot>
      );
    }

    const Comp = props.href ? "a" : "button";
    return (
      <Comp
        ref={ref}
        type={Comp === "button" ? props.type || "button" : undefined}
        disabled={Comp === "button" ? disabled || isLoading : undefined}
        className={classes}
        {...props}
      >
        {renderInner(children)}
      </Comp>
    );
  }
);
PrimaryButton.displayName = "PrimaryButton";

/**
 * SecondaryButton — Dark surface button with #243041 border, #E5E7EB typography,
 * optional leading icon, and full Radix Slot (`asChild`) support.
 */
const SecondaryButton = React.forwardRef(
  (
    {
      children,
      className,
      size = "md",
      isLoading = false,
      disabled,
      asChild = false,
      icon: Icon,
      ...props
    },
    ref
  ) => {
    const classes = cn(
      buttonVariants({ variant: "brandSecondary", size }),
      "font-inter font-medium tracking-tight",
      className
    );

    const renderInner = (labelContent) => (
      <>
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin text-[#E5E7EB]" />
        ) : Icon ? (
          <Icon className="h-4 w-4 text-[#E5E7EB]" />
        ) : null}
        <span>{labelContent}</span>
      </>
    );

    if (asChild && React.isValidElement(children)) {
      return (
        <Slot ref={ref} className={classes} {...props}>
          {React.cloneElement(
            children,
            undefined,
            renderInner(children.props.children)
          )}
        </Slot>
      );
    }

    const Comp = props.href ? "a" : "button";
    return (
      <Comp
        ref={ref}
        type={Comp === "button" ? props.type || "button" : undefined}
        disabled={Comp === "button" ? disabled || isLoading : undefined}
        className={classes}
        {...props}
      >
        {renderInner(children)}
      </Comp>
    );
  }
);
SecondaryButton.displayName = "SecondaryButton";

export { Button, buttonVariants, PrimaryButton, SecondaryButton };
