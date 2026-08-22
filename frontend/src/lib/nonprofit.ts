export const NONPROFIT = {
  legalName: "Operation Child Shield",
  mailingAddressLines: ["PO Box 82", "Manson, WA 98831"],
  mailingAddress: "PO Box 82, Manson, WA 98831",
  ircSection: "501(c)(3)",
  publicCharityStatus: "170(b)(1)(A)(vi)",
  effectiveDateLabel: "July 1, 2026",
  contributionDeductible: true,
} as const;

export function nonprofitStatusSummary(): string {
  return `${NONPROFIT.legalName} is a ${NONPROFIT.ircSection} public charity. Contributions are tax-deductible to the extent allowed by law.`;
}
