import Link from "next/link";

const LINKS = [
  { href: "/admin", label: "Traffic" },
  { href: "/admin/applications", label: "Applications" },
  { href: "/admin/audit", label: "Audit" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/account", label: "Account" },
] as const;

/** Tab-style nav shared by the admin pages. */
export function AdminNav({ current }: { current: string }) {
  return (
    <nav aria-label="Admin sections" className="flex flex-wrap gap-2">
      {LINKS.map((link) => {
        const active = link.href === current;
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={
              active
                ? "rounded-full bg-blue px-4 py-2 text-sm font-semibold text-white no-underline"
                : "rounded-full border border-card-border bg-surface px-4 py-2 text-sm font-semibold text-muted no-underline hover:text-blue"
            }
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
