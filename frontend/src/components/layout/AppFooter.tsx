import { cn } from "@/lib/utils";

const CONTACT = {
  address: "A.J. Momoh Street / Tower Hill, P.M.B. 595, Freetown, Sierra Leone",
  email: "info@statistics.sl",
  phone: "+232-78-208595 / 30-593333",
  website: "https://www.statistics.sl",
};

const TONES = {
  light: { text: "text-slate-500", strong: "text-slate-700", link: "text-brand-600", divider: "bg-slate-300" },
  dark: { text: "text-slate-400", strong: "text-slate-200", link: "text-brand-300", divider: "bg-slate-600" },
};

export function AppFooter({
  tone = "light",
  className,
}: {
  tone?: keyof typeof TONES;
  className?: string;
}) {
  const t = TONES[tone];
  const year = new Date().getFullYear();

  return (
    <footer className={cn("px-4 py-3 text-center text-xs print:hidden", t.text, className)}>
      <p>
        <span className={cn("font-semibold", t.strong)}>Developed by Statistics Sierra Leone</span>
        <span className={cn("mx-2 inline-block h-3 w-px align-middle", t.divider)} aria-hidden="true" />
        &copy; {year} Statistics Sierra Leone. All rights reserved.
      </p>
      <p className="mt-0.5">
        SLPHC 2026 Logistics Management System
        <span className="hidden sm:inline">
          {" "}&middot; {CONTACT.address}
        </span>
      </p>
      <p className="mt-0.5">
        <a href={`mailto:${CONTACT.email}`} className={cn("hover:underline", t.link)}>
          {CONTACT.email}
        </a>
        {" "}&middot; {CONTACT.phone} &middot;{" "}
        <a href={CONTACT.website} target="_blank" rel="noreferrer" className={cn("hover:underline", t.link)}>
          www.statistics.sl
        </a>
      </p>
    </footer>
  );
}
