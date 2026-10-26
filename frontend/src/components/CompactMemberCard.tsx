"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { PartyBadge } from "@/components/PartyBadge";
import { PolicyBadge } from "@/components/PolicyBadge";
import {
  formatDisplayName,
  formatMemberSubtitle,
  resolvePolicyConsistent,
  summarizeMemberVotes,
  voteToLabel,
} from "@/lib/format";
import { reportCardQueue } from "@/lib/fetch-queue";
import { resolveParty } from "@/lib/party";
import type { MemberSummary, ReportCard } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface CompactMemberCardProps {
  member: MemberSummary;
}

/**
 * Small directory card for state pages: same footprint as the simple member
 * list, plus a short voting-record summary from the full member card data.
 */
export function CompactMemberCard({ member }: CompactMemberCardProps) {
  const cardRef = useRef<HTMLAnchorElement>(null);
  const [report, setReport] = useState<ReportCard | null>(null);
  const [visible, setVisible] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  // Derived instead of set synchronously in the effect below (which would
  // trigger a cascading render on every visibility change).
  const loading = visible && !report && !loadFailed;

  const displayName = formatDisplayName(member.name);
  const subtitle = formatMemberSubtitle(member);
  const party = resolveParty(member.party, report?.party);

  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;

    let cancelled = false;
    const markVisible = () => {
      if (!cancelled) setVisible(true);
    };

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          markVisible();
          observer.disconnect();
        }
      },
      { rootMargin: "150px", threshold: 0 }
    );
    observer.observe(el);

    const rect = el.getBoundingClientRect();
    if (rect.top < window.innerHeight + 150 && rect.bottom > -150) {
      markVisible();
      observer.disconnect();
    }

    return () => {
      cancelled = true;
      observer.disconnect();
    };
  }, [member.bioguideId]);

  useEffect(() => {
    if (!visible) return;

    let cancelled = false;

    reportCardQueue
      .enqueue(async () => {
        const res = await fetch(
          `${API_URL}/api/members/${member.bioguideId}/report-card`
        );
        if (!res.ok) throw new Error(`Failed to load voting record: ${res.status}`);
        return res.json() as Promise<ReportCard>;
      })
      .then((data) => {
        if (!cancelled) {
          setReport(data);
          setLoadFailed(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoadFailed(true);
      });

    return () => {
      cancelled = true;
    };
  }, [visible, member.bioguideId]);

  const voteSummary = summarizeMemberVotes(report?.key_votes ?? []);
  const topVote = (report?.key_votes ?? []).find(
    (v) =>
      v.vote_cast !== "Unknown" &&
      resolvePolicyConsistent(v.policy_consistent, v.score_impact) !== null
  );

  return (
    <Link
      ref={cardRef}
      href={`/member/${member.bioguideId}`}
      className="flex min-h-[5.75rem] items-stretch gap-3 rounded-[10px] border border-card-border bg-surface p-3 shadow-sm no-underline transition-colors hover:border-blue/40 sm:p-4"
    >
      <div className="h-12 w-12 shrink-0 self-center overflow-hidden rounded-full border border-card-border bg-surface-muted">
        {member.imageUrl ? (
          <Image
            src={member.imageUrl}
            alt=""
            width={48}
            height={48}
            className="h-full w-full object-cover"
          />
        ) : (
          <span className="flex h-full w-full items-center justify-center text-lg">
            🇺🇸
          </span>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-start justify-between gap-x-2 gap-y-1">
          <div className="min-w-0">
            <p className="m-0 truncate text-sm font-semibold text-foreground sm:text-base">
              {displayName}
            </p>
            <p className="m-0 mt-0.5 text-xs text-muted">
              {subtitle}
              <span className="text-muted/80"> · {member.chamber}</span>
            </p>
          </div>
          <PartyBadge party={party} variant="light" size="sm" />
        </div>

        <div className="mt-2 min-h-[1.75rem]">
          {loading && !report && (
            <p className="m-0 text-[0.7rem] text-muted animate-pulse">
              Loading votes...
            </p>
          )}

          {loadFailed && !report && (
            <p className="m-0 text-[0.7rem] text-muted">Record unavailable</p>
          )}

          {report && voteSummary.recorded === 0 && (
            <p className="m-0 text-[0.7rem] text-muted">
              {member.chamber === "Senate"
                ? "Senate floor votes not available yet"
                : "No recorded votes yet"}
            </p>
          )}

          {report && voteSummary.recorded > 0 && (
            <div className="flex flex-col gap-1.5">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[0.7rem] sm:text-xs">
                <span className="font-semibold text-blue">
                  {voteSummary.recorded} vote
                  {voteSummary.recorded === 1 ? "" : "s"}
                </span>
                <span className="inline-flex items-center gap-1 text-foreground">
                  <PolicyBadge consistent size="sm" />
                  <span className="font-semibold">{voteSummary.consistent}</span>
                </span>
                <span className="inline-flex items-center gap-1 text-foreground">
                  <PolicyBadge consistent={false} size="sm" />
                  <span className="font-semibold">{voteSummary.notConsistent}</span>
                </span>
                {voteSummary.notVoting > 0 && (
                  <span className="text-muted">
                    {voteSummary.notVoting} not voting
                  </span>
                )}
              </div>

              {topVote && (
                <p className="m-0 flex min-w-0 items-center gap-1.5 text-[0.65rem] leading-snug text-muted sm:text-[0.7rem]">
                  <span className="min-w-0 truncate">
                    {topVote.bill_number || topVote.bill_title}
                  </span>
                  <span
                    className={`shrink-0 rounded-full px-1.5 py-px text-[0.65rem] font-bold ${
                      voteToLabel(topVote.vote_cast).className
                    }`}
                  >
                    {voteToLabel(topVote.vote_cast).label}
                  </span>
                  <PolicyBadge
                    consistent={resolvePolicyConsistent(
                      topVote.policy_consistent,
                      topVote.score_impact
                    )}
                    size="sm"
                  />
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}
