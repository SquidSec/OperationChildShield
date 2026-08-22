const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://operationchildshield.org";

export function buildConstituentMessage(input?: {
  officialName?: string;
  reportUrl?: string;
}): string {
  const greeting = input?.officialName?.trim()
    ? `Dear ${input.officialName.trim()},`
    : "Dear Representative or Senator,";

  const lines = [
    greeting,
    "",
    "I am a constituent writing about child safety, anti-abuse, and anti-trafficking legislation.",
    "",
    "I follow which bills protecting children from exploitation and trafficking are moving through Congress, and how members voted or abstained, at Operation Child Shield.",
    "",
    SITE_URL,
    "",
    "Please support stronger child safety and anti-exploitation protections, and vote on the record so the public can see where you stand.",
  ];

  if (input?.reportUrl?.trim()) {
    lines.push("", `Your recorded votes: ${input.reportUrl.trim()}`);
  }

  lines.push("", "Thank you.");
  return lines.join("\n");
}

export function buildConstituentMailto(input?: {
  officialName?: string;
  reportUrl?: string;
}): string {
  const params = new URLSearchParams({
    subject: "Child safety and anti-trafficking legislation",
    body: buildConstituentMessage(input),
  });
  return `mailto:?${params.toString()}`;
}
