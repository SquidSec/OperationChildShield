/**
 * Renders structured data as an inert JSON-LD data block. The CSP in proxy.ts
 * deliberately omits nonces here: application/ld+json scripts are never
 * executed, so script-src does not apply to them.
 */
export function JsonLd({ data }: { data: Record<string, unknown> }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        // Escape "<" so a value can never close the script tag early.
        __html: JSON.stringify(data).replace(/</g, "\\u003c"),
      }}
    />
  );
}
