import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ComparePicker } from "@/components/ComparePicker";
import { ConstituentToolkit } from "@/components/ConstituentToolkit";
import { JsonLd } from "@/components/JsonLd";
import { MemberContactCard } from "@/components/MemberContactCard";
import { MemberVotePieChart } from "@/components/MemberVotePieChart";
import { MemberVoteStats } from "@/components/MemberVoteStats";
import { PolicyLegend } from "@/components/PolicyLegend";
import { PrintButton } from "@/components/PrintButton";
import { SaveMemberButton } from "@/components/account/SaveMemberButton";
import { ShareButton } from "@/components/ShareButton";
import { VoteTable } from "@/components/VoteTable";
import { PartyBadge } from "@/components/PartyBadge";
import {
  formatDisplayName,
  summarizeMemberVotes,
} from "@/lib/format";
import { getReportPageUrl } from "@/lib/share";
import { getReportCard } from "@/lib/api";
import { hasUserSessionCookie, getUserProfile } from "@/lib/user-api";
import { cookies, headers } from "next/headers";
import { apiErrorStatus, friendlyErrorMessage } from "@/lib/errors";
import { getStateCode } from "@/lib/states";
import { memberJsonLd } from "@/lib/structured-data";

interface MemberPageProps {
  params: Promise<{ id: string }>;
}

const BIOGUIDE_PATTERN = /^[A-Za-z][0-9]{5,7}$/;

export async function generateMetadata({
  params,
}: MemberPageProps): Promise<Metadata> {
  const { id } = await params;
  try {
    const card = await getReportCard(id);
    const displayName = formatDisplayName(card.name);
    const title = `${displayName}: How They Voted`;
    const description = `See how ${displayName} (${card.party}, ${card.state}) voted on tracked child safety bills.`;
    return {
      title,
      description,
      openGraph: {
        title: `${displayName}: How They Voted | Operation Child Shield`,
        description,
        url: `/member/${id}`,
      },
      twitter: {
        card: "summary_large_image",
        title: `${displayName}: How They Voted | Operation Child Shield`,
        description,
      },
    };
  } catch {
    return {
      title: "How They Voted",
      description: "Child safety voting record from Operation Child Shield.",
    };
  }
}

export default async function MemberPage({ params }: MemberPageProps) {
  const { id } = await params;

  // Account state is optional here: the page must render for anonymous visitors.
  const cookieStore = await cookies();
  const cookieHeader = (await headers()).get("cookie") ?? "";
  const signedIn =
    Boolean(cookieStore.get("ocs_user_session")?.value) && hasUserSessionCookie(cookieHeader);
  const profile = signedIn ? await getUserProfile(cookieHeader) : null;
  const initiallySaved = Boolean(
    profile?.savedMembers?.some((m) => m.bioguideId === id.toUpperCase())
  );

  // Malformed ids are never a real member; render the 404 rather than an error.
  if (!BIOGUIDE_PATTERN.test(id)) {
    notFound();
  }

  let card: Awaited<ReturnType<typeof getReportCard>> | null = null;
  let error: unknown = null;

  try {
    card = await getReportCard(id);
  } catch (e) {
    error = e;
  }

  if (card === null) {
    const status = apiErrorStatus(error);
    if (status === 400 || status === 404) {
      notFound();
    }

    return (
      <div className="page-container py-16 text-center">
        <h1 className="text-2xl font-bold text-blue">We couldn&apos;t load this record</h1>
        <p className="mx-auto mt-2 max-w-xl text-muted">
          {friendlyErrorMessage(
            error,
            "This voting record is unavailable right now. Please try again in a moment."
          )}
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-4">
          <Link href="/" className="text-red font-bold hover:underline">
            ← Back to lawmakers
          </Link>
          <Link href="/search" className="text-blue font-bold hover:underline">
            Search bills and lawmakers →
          </Link>
        </div>
      </div>
    );
  }

  const displayName = formatDisplayName(card.name);
  const prefix = card.chamber === "Senate" ? "Sen." : "Rep.";
  const subtitle = `${prefix} ${card.state}${card.district ? `-${card.district}` : ""}`;
  const voteSummary = summarizeMemberVotes(card.key_votes);
  const stateCode = card.state ? getStateCode(card.state) : "";

  return (
    <div className="page-container py-8">
      <JsonLd
        data={memberJsonLd({
          name: displayName,
          bioguideId: card.bioguide_id,
          party: card.party,
          state: card.state,
          chamber: card.chamber,
          imageUrl: card.image_url,
          congressProfileUrl: card.congress_profile_url,
        })}
      />
      <Link
        href="/"
        className="text-sm text-muted hover:text-blue transition-colors print:hidden"
      >
        ← Back to lawmakers
      </Link>

      <header className="mt-6 overflow-hidden rounded-[10px] border border-card-border bg-surface shadow-[0_6px_12px_-2px_rgb(0_0_0_/_0.1)]">
        <div className="flex flex-col gap-4 bg-gradient-to-r from-blue to-blue-light p-5 text-white sm:flex-row sm:items-center sm:gap-5 sm:px-6">
          <div className="h-20 w-20 shrink-0 overflow-hidden rounded-full border-[3px] border-white bg-white sm:h-[88px] sm:w-[88px]">
            {card.image_url ? (
              <Image
                src={card.image_url}
                alt={displayName}
                width={88}
                height={88}
                className="h-full w-full object-cover"
              />
            ) : (
              <span className="flex h-full w-full items-center justify-center text-3xl">
                🇺🇸
              </span>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className="m-0 text-xs font-bold uppercase tracking-wider text-blue-100">
              Child safety voting record
            </p>
            <h1 className="m-0 mt-1 text-2xl font-bold sm:text-3xl">{displayName}</h1>
            <p className="m-0 mt-1 text-sm text-[#cbd5e1]">{subtitle}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <PartyBadge party={card.party} variant="header" />
              {stateCode ? (
                <Link
                  href={`/states/${stateCode.toLowerCase()}`}
                  className="text-xs font-semibold text-blue-100 underline hover:text-white"
                >
                  {card.state} overview
                </Link>
              ) : null}
              <a
                href={card.congress_profile_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-semibold text-blue-100 underline hover:text-white"
              >
                Congress.gov
              </a>
            </div>
          </div>
        </div>
      </header>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(16rem,0.8fr)]">
        <section className="rounded-[10px] border border-card-border bg-surface p-5 shadow-sm sm:p-6">
          <h2 className="m-0 text-lg font-bold text-blue">Record at a glance</h2>
          <p className="mt-2 mb-0 text-sm leading-relaxed text-muted">
            Recorded House roll-call votes on tracked child safety bills, compared
            to Operation Child Shield policy. Not voting is counted as not voting.
          </p>
          <MemberVoteStats summary={voteSummary} />
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {voteSummary.recorded > 0 ? (
              <MemberVotePieChart votes={card.key_votes} compact={false} />
            ) : (
              <div className="rounded-md border border-card-border bg-surface-muted px-3 py-6 text-center text-sm text-muted">
                {card.chamber === "Senate"
                  ? "Senate floor votes are not yet available via the Congress.gov API."
                  : "No Yes/No roll-call votes on tracked bills yet."}
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-card-border bg-surface-muted p-4 text-center">
                <p className="m-0 text-2xl font-bold text-blue">{card.votes_tracked}</p>
                <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-muted">
                  Bills tracked
                </p>
              </div>
              <div className="rounded-lg border border-card-border bg-surface-muted p-4 text-center">
                <p className="m-0 text-2xl font-bold text-blue">{voteSummary.notVoting}</p>
                <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-muted">
                  Not voting
                </p>
              </div>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap items-center gap-3 print:hidden">
            <ShareButton
              variant="report"
              bioguideId={card.bioguide_id}
              name={card.name}
              party={card.party}
              votesTracked={card.votes_tracked}
              keyVotes={card.key_votes}
              chamber={card.chamber}
            />
            <SaveMemberButton
              bioguideId={card.bioguide_id}
              name={card.name}
              state={card.state ?? ""}
              signedIn={signedIn}
              initiallySaved={initiallySaved}
            />
            <PrintButton />
            <Link
              href={`/compare?ids=${card.bioguide_id}`}
              className="inline-flex items-center justify-center rounded-md border border-card-border bg-surface px-4 py-2.5 text-sm font-bold text-blue transition-colors hover:bg-surface-muted"
            >
              Compare with another member
            </Link>
          </div>
        </section>

        <aside className="min-w-0 space-y-4">
          {card.contact ? (
            <MemberContactCard
              contact={card.contact}
              actionPath={`/member/${card.bioguide_id}`}
            />
          ) : null}
          <div className="print:hidden">
            <ComparePicker bioguideId={card.bioguide_id} displayName={displayName} />
          </div>
        </aside>
      </div>

      {/* Letter writing sits between the summary metrics and the full vote table:
          read the numbers, act, then audit every vote. */}
      <ConstituentToolkit
        className="mt-8 print:hidden"
        officialName={`${prefix} ${displayName}`}
        reportUrl={getReportPageUrl(card.bioguide_id)}
      />

      <section className="mt-8">
        <h2 className="mb-2 text-xl font-bold text-blue">Every vote we track</h2>
        <PolicyLegend className="mb-4 justify-start" />
        <div className="rounded-[10px] border border-card-border bg-surface p-4 shadow-[0_6px_12px_-2px_rgb(0_0_0_/_0.1)] sm:p-5">
          <VoteTable votes={card.key_votes} />
        </div>
      </section>

    </div>
  );
}
