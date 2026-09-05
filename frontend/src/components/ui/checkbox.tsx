import { InputHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/utils";

export const Checkbox = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      type="checkbox"
      className={cn(
        "h-4 w-4 rounded border-slate-300 text-brand-700 focus:ring-2 focus:ring-brand-500",
        className,
      )}
      {...props}
    />
  ),
);
Checkbox.displayName = "Checkbox";
