import { headers } from "next/headers";

/**
 * Donorbox donation form custom element.
 * The module script needs the per-request CSP nonce so `script-src` can stay
 * strict-dynamic; donorbox.org is allowlisted for the /donate route in proxy.ts.
 */
export async function DonorboxEmbed() {
  const nonce = (await headers()).get("x-nonce") ?? undefined;

  return (
    <div className="w-full overflow-hidden rounded-[10px] border border-card-border bg-surface p-4 shadow-[0_6px_12px_-2px_rgb(0_0_0_/_0.1)]">
      <script
        type="module"
        src="https://donorbox.org/widgets.js"
        async
        nonce={nonce}
        suppressHydrationWarning
      />
      <dbox-widget
        campaign="operation-child-shield"
        type="donation_form"
        enable-auto-scroll="true"
        suppressHydrationWarning
      />
    </div>
  );
}
