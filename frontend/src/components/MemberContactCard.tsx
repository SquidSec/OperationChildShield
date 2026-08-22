"use client";

import { trackAction } from "@/lib/api";
import type { MemberContact } from "@/lib/types";

function formatLocation(city: string | null, zipCode: string | number | null): string | null {
  const parts = [city, zipCode != null ? String(zipCode) : null].filter(Boolean);
  return parts.length ? parts.join(", ") : null;
}

export function MemberContactCard({
  contact,
  actionPath,
  className = "",
}: {
  contact: MemberContact;
  actionPath?: string;
  className?: string;
}) {
  const location = formatLocation(contact.city, contact.zip_code);
  const hasContent = Boolean(
    contact.office_address || contact.phone || contact.website_url
  );

  if (!hasContent) return null;

  function markContact() {
    void trackAction("contact_congress", actionPath || "/");
  }

  return (
    <section
      className={`rounded-[10px] border border-card-border bg-surface p-5 shadow-sm ${className}`}
    >
      <h2 className="text-sm font-bold uppercase tracking-wide text-blue m-0">
        Contact Your Representative
      </h2>
      <p className="mt-1 text-xs text-muted m-0">
        Official contact information from Congress.gov
      </p>

      <dl className="mt-4 space-y-3 text-sm m-0">
        {contact.office_address && (
          <div>
            <dt className="font-semibold text-foreground">Office</dt>
            <dd className="mt-0.5 text-muted m-0 whitespace-pre-line">
              {contact.office_address}
              {location ? `\n${location}` : ""}
            </dd>
          </div>
        )}
        {contact.phone && (
          <div>
            <dt className="font-semibold text-foreground">Phone</dt>
            <dd className="mt-0.5 m-0">
              <a
                href={`tel:${contact.phone.replace(/[^\d+]/g, "")}`}
                className="text-red font-semibold hover:underline"
                onClick={markContact}
              >
                {contact.phone}
              </a>
            </dd>
          </div>
        )}
        {contact.website_url && (
          <div>
            <dt className="font-semibold text-foreground">Website</dt>
            <dd className="mt-0.5 m-0">
              <a
                href={contact.website_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-red font-semibold hover:underline break-all"
                onClick={markContact}
              >
                {contact.website_url.replace(/^https?:\/\//, "")}
              </a>
            </dd>
          </div>
        )}
      </dl>
    </section>
  );
}
