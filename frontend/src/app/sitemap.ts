import type { MetadataRoute } from "next";
import { getMembersPage } from "@/lib/api";
import { STATIC_PUBLIC_ROUTES, siteUrl } from "@/lib/site";
import { US_STATE_OPTIONS } from "@/lib/states";

/** Hard cap so a directory growth spurt cannot blow up the sitemap response. */
const MAX_MEMBERS = 600;
const PAGE_SIZE = 250;

/** Public Congress.gov cover sheet pages we always list. */
const SITEMAP_ENTRY_LIMIT = 5000;

function staticEntries(now: Date): MetadataRoute.Sitemap {
  const entries: MetadataRoute.Sitemap = STATIC_PUBLIC_ROUTES.map((route) => ({
    url: siteUrl(route.path),
    lastModified: now,
    changeFrequency: route.changeFrequency,
    priority: route.priority,
  }));

  for (const { code } of US_STATE_OPTIONS) {
    entries.push({
      url: siteUrl(`/states/${code.toLowerCase()}`),
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.6,
    });
  }

  return entries;
}

async function memberEntries(now: Date): Promise<MetadataRoute.Sitemap> {
  const entries: MetadataRoute.Sitemap = [];
  let offset = 0;

  try {
    while (offset < MAX_MEMBERS) {
      const page = await getMembersPage(offset, PAGE_SIZE);
      for (const member of page.members) {
        if (!member.bioguideId) continue;
        entries.push({
          url: siteUrl(`/member/${member.bioguideId}`),
          lastModified: now,
          changeFrequency: "weekly",
          priority: 0.7,
        });
      }

      offset += PAGE_SIZE;
      if (page.members.length < PAGE_SIZE || offset >= page.total) break;
    }
  } catch {
    // Fail soft: the sitemap still lists every static route when the API is down.
    return entries;
  }

  return entries;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const entries = [...staticEntries(now), ...(await memberEntries(now))];
  return entries.slice(0, SITEMAP_ENTRY_LIMIT);
}

export const revalidate = 3600;
