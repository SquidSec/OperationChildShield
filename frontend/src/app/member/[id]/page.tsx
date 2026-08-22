import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { ConstituentToolkit } from "@/components/ConstituentToolkit";
import { MemberContactCard } from "@/components/MemberContactCard";
import { MemberVotePieChart } from "@/components/MemberVotePieChart";
import { MemberVoteStats } from "@/components/MemberVoteStats";
import { PolicyLegend } from "@/components/PolicyLegend";
import { ShareButton } from "@/components/ShareButton";
import { VoteTable } from "@/components/VoteTable";
import { PartyBadge } from "@/components/PartyBadge";
import {
  formatDisplayName,
  summarizeMemberVotes,
} from "@/lib/format";
import { getReportPageUrl } from "@/lib/share";
import { getReportCard } from "@/lib/api";
import { getStateCode } from "@/lib/states";

interface MemberPageProps {
  params: Promise<{ id: string }>;
}

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

  let card: Awaited<ReturnType<typeof getReportCard>> | null = null;
  let error: string | null = null;

  try {
    card = await getReportCard(id);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load voting record";
  }

  if (error || !card) {
    return (
      <div className="page-container py-16 text-center">
        <h1 className="text-2xl font-bold text-blue">Member Not Found</h1>
        <p className="mt-2 text-muted">{error}</p>
        <Link href="/" className="mt-6 inline-block text-red font-bold hover:underline">
          ← Back to lawmakers
        </Link>
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
      <Link href="/" className="text-sm text-muted hover:text-blue transition-colors">
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
                No Yes/No roll-call votes on tracked bills yet.
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
          <div className="mt-5">
            <ShareButton
              variant="report"
              bioguideId={card.bioguide_id}
              name={card.name}
              party={card.party}
              votesTracked={card.votes_tracked}
              keyVotes={card.key_votes}
              chamber={card.chamber}
            />
          </div>
        </section>

        <aside className="min-w-0 space-y-4">
          {card.contact ? (
            <MemberContactCard
              contact={card.contact}
              actionPath={`/member/${card.bioguide_id}`}
            />
          ) : null}
        </aside>
      </div>

      <section className="mt-8">
        <h2 className="mb-2 text-xl font-bold text-blue">Every vote we track</h2>
        <PolicyLegend className="mb-4 justify-start" />
        <div className="rounded-[10px] border border-card-border bg-surface p-4 shadow-[0_6px_12px_-2px_rgb(0_0_0_/_0.1)] sm:p-5">
          <VoteTable votes={card.key_votes} />
        </div>
      </section>

      <ConstituentToolkit
        className="mt-8"
        officialName={`${prefix} ${displayName}`}
        reportUrl={getReportPageUrl(card.bioguide_id)}
      />
    </div>
  );
}
