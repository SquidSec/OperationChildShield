import { CONTACT_EMAIL, SITE_DESCRIPTION, SITE_NAME, siteUrl } from "./site";

/** Sitewide Organization + WebSite graph for the public layout. */
export function siteJsonLd(): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": siteUrl("/#organization"),
        name: SITE_NAME,
        url: siteUrl("/"),
        logo: siteUrl("/images/ocs-v2-icon-inverted.png"),
        description:
          "A 501(c)(3) nonprofit publishing a public record of congressional votes on tracked child-protection bills.",
        email: CONTACT_EMAIL,
        nonprofitStatus: "Nonprofit501c3",
        address: {
          "@type": "PostalAddress",
          postOfficeBoxNumber: "82",
          addressLocality: "Manson",
          addressRegion: "WA",
          postalCode: "98831",
          addressCountry: "US",
        },
      },
      {
        "@type": "WebSite",
        "@id": siteUrl("/#website"),
        name: SITE_NAME,
        url: siteUrl("/"),
        description: SITE_DESCRIPTION,
        publisher: { "@id": siteUrl("/#organization") },
        potentialAction: {
          "@type": "SearchAction",
          target: {
            "@type": "EntryPoint",
            urlTemplate: `${siteUrl("/search")}?q={search_term_string}`,
          },
          "query-input": "required name=search_term_string",
        },
      },
    ],
  };
}

export interface PersonJsonLdInput {
  name: string;
  bioguideId: string;
  party: string;
  state: string;
  chamber: string;
  imageUrl?: string | null;
  congressProfileUrl?: string;
}

export function memberJsonLd(member: PersonJsonLdInput): Record<string, unknown> {
  const data: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "Person",
    name: member.name,
    url: siteUrl(`/member/${member.bioguideId}`),
    identifier: member.bioguideId,
    jobTitle: member.chamber === "Senate" ? "U.S. Senator" : "U.S. Representative",
    memberOf: {
      "@type": "Organization",
      name: member.chamber === "Senate" ? "United States Senate" : "United States House of Representatives",
    },
    affiliation: { "@type": "Organization", name: member.party },
    workLocation: { "@type": "Place", name: member.state },
    mainEntityOfPage: siteUrl(`/member/${member.bioguideId}`),
  };
  if (member.imageUrl) data.image = member.imageUrl;
  if (member.congressProfileUrl) data.sameAs = [member.congressProfileUrl];
  return data;
}

export interface DatasetJsonLdInput {
  name: string;
  description: string;
  congress: number;
  lastUpdated: string;
  recordCount: number;
}

export function metricsJsonLd(dataset: DatasetJsonLdInput): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "Dataset",
    name: dataset.name,
    description: dataset.description,
    url: siteUrl("/metrics"),
    creator: { "@id": siteUrl("/#organization") },
    publisher: { "@id": siteUrl("/#organization") },
    isAccessibleForFree: true,
    dateModified: dataset.lastUpdated,
    license: "https://www.congress.gov/about/terms-of-use",
    spatialCoverage: { "@type": "Country", name: "United States" },
    variableMeasured: [
      "Recorded House roll-call votes",
      "Policy-consistent votes",
      "Not-voting instances",
    ],
    size: `${dataset.recordCount} recorded floor votes`,
    citation: `Congress.gov, ${dataset.congress}th Congress`,
  };
}
