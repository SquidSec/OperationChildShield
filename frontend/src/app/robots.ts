import type { MetadataRoute } from "next";

// Admin pages are private and also carry noindex metadata.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/admin", "/admin/", "/api/"],
      },
    ],
  };
}
