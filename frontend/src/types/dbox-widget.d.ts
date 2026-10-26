import type { DetailedHTMLProps, HTMLAttributes } from "react";

/** Donorbox web component (loaded from donorbox.org/widgets.js on /donate). */
declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "dbox-widget": DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement> & {
        campaign?: string;
        type?: string;
        "enable-auto-scroll"?: string;
      };
    }
  }
}
