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
import { StateBadge } from "@/components/StateBadge";
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

  return (
    <div className="page-container py-8">
      <Link href="/" className="text-sm text-muted hover:text-blue transition-colors">
        ← Back to lawmakers
      </Link>

      <div className="mt-6 overflow-visible rounded-[10px] border border-card-border bg-surface shadow-[0_6px_12px_-2px_rgb(0_0_0_/_0.1)]">
        <div className="flex items-center gap-4 overflow-hidden rounded-t-[10px] bg-gradient-to-r from-blue to-blue-light p-5 px-6 text-white">
          <div className="w-[72px] h-[72px] rounded-full bg-white shrink-0 flex items-center justify-center text-3xl border-[3px] border-white overflow-hidden">
            {card.image_url ? (
              <Image
                src={card.image_url}
                alt={displayName}
                width={72}
                height={72}
                className="object-cover w-full h-full"
              />
            ) : (
              <span>🇺🇸</span>
            )}
          </div>
          <div className="flex-1">
            <p className="text-xs font-bold uppercase tracking-wider text-blue-100 m-0">
              How They Voted on Child Safety
            </p>
            <h1 className="text-2xl font-bold m-0 mt-1">{displayName}</h1>
            <p className="text-[#cbd5e1] m-0 mt-0.5">{subtitle}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <PartyBadge party={card.party} variant="header" />
              {card.state ? (
                <Link
                  href={`/states/${getStateCode(card.state).toLowerCase()}`}
                  className="text-xs font-semibold text-blue-100 underline hover:text-white"
                >
                  View {card.state} overview
                </Link>
              ) : null}
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-b border-card-border flex flex-wrap items-center justify-between gap-3">
          <StateBadge stateName={card.state} variant="light" />
          <PartyBadge party={card.party} variant="light" />
        </div>

        <div className="p-6">
          <p className="text-muted text-sm leading-relaxed m-0">
            This page reports how this official voted on tracked child safety
            legislation, with each recorded floor vote compared to Operation Child
            Shield&apos;s board-adopted policy positions.
          </p>

          <MemberVoteStats summary={voteSummary} />

          {voteSummary.recorded > 0 && (
            <div className="mt-4 max-w-sm">
              <MemberVotePieChart votes={card.key_votes} compact={false} />
            </div>
          )}

          <div className="mt-4 grid grid-cols-2 gap-4 text-center">
            <div className="bg-surface-muted rounded-lg p-4 border border-card-border">
              <p className="text-2xl font-bold text-blue m-0">{card.votes_tracked}</p>
              <p className="text-xs text-muted mt-1 uppercase tracking-wide">
                Bills Tracked
              </p>
            </div>
            <div className="bg-surface-muted rounded-lg p-4 border border-card-border">
              <p className="text-2xl font-bold text-blue m-0">{voteSummary.notVoting}</p>
              <p className="text-xs text-muted mt-1 uppercase tracking-wide">
                Not Voting
              </p>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <ShareButton
              variant="report"
              bioguideId={card.bioguide_id}
              name={card.name}
              party={card.party}
              votesTracked={card.votes_tracked}
              keyVotes={card.key_votes}
              chamber={card.chamber}
            />
            <a
              href={card.congress_profile_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-bold text-red hover:underline"
            >
              Official Profile on Congress.gov →
            </a>
          </div>

          {card.contact && (
            <MemberContactCard
              contact={card.contact}
              actionPath={`/member/${card.bioguide_id}`}
            />
          )}
          <ConstituentToolkit
            className="mt-6"
            officialName={`${prefix} ${displayName}`}
            reportUrl={getReportPageUrl(card.bioguide_id)}
          />
        </div>
      </div>

      <div className="mt-8">
        <h2 className="text-xl font-bold text-blue mb-2">Every Vote We Track</h2>
        <PolicyLegend className="mb-4 justify-start" />
        <div className="bg-surface rounded-[10px] p-5 shadow-[0_6px_12px_-2px_rgb(0_0_0_/_0.1)] border border-card-border">
          <VoteTable votes={card.key_votes} />
        </div>
      </div>
    </div>
  );
}