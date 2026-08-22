import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ENABLE_BOARD_PAGE } from "@/lib/feature-flags";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Leadership",
  description:
    "Meet the Operation Child Shield board of directors guiding our mission of nonpartisan congressional accountability on child protection legislation.",
};

type BoardMember = {
  name: string;
  role: string;
  membership: string;
  organization?: string;
  organizationLabel?: string;
  href?: string;
  linkedin?: string;
  photo?: string;
  photoWidth?: number;
  photoHeight?: number;
};

function LinkedInIcon() {
  return (
    <svg
      aria-hidden
      className="h-5 w-5"
      viewBox="0 0 24 24"
      fill="currentColor"
    >
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 4.126 0 2.065 2.065 0 0 1-2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  );
}

function memberInitials(name: string): string {
  return name
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

const officers: BoardMember[] = [
  {
    name: "Joanna Wiggum",
    role: "President",
    membership: "Founding Voting Member",
    organization: "Countervail Intelligence",
    organizationLabel: "Founder of Countervail",
    href: "https://countervailintelligence.com/",
    linkedin: "https://www.linkedin.com/in/joanna-wiggum",
    photo: "/images/jo.png",
    photoWidth: 517,
    photoHeight: 521,
  },
  {
    name: "Hailey Allen",
    role: "Vice President",
    membership: "Founding Voting Member",
    photo: "/images/hailey.png",
    photoWidth: 1122,
    photoHeight: 1402,
  },
  {
    name: "Pam James",
    role: "Secretary",
    membership: "Founding Voting Member",
    photo: "/images/pam.jpg",
    photoWidth: 1536,
    photoHeight: 2048,
  },
  {
    name: "Sara Bowthorpe",
    role: "Treasurer",
    membership: "Founding Voting Member",
    photo: "/images/sara.png",
    photoWidth: 1086,
    photoHeight: 1448,
  },
];

const boardDirectors: BoardMember[] = [
  {
    name: "Todd Thompson",
    role: "Board Director",
    membership: "Founding Voting Member",
    linkedin: "https://www.linkedin.com/in/todd-thompson-a538064",
    photo: "/images/todd.png",
    photoWidth: 1402,
    photoHeight: 1122,
  },
  {
    name: "Anthony Russell",
    role: "Board Director and Chief Technology Officer (CTO)",
    membership: "Founding Voting Member",
    organization: "SquidSec",
    organizationLabel: "Founder of SquidSec",
    href: "https://squidoffense.com/",
    linkedin: "https://www.linkedin.com/in/dotnetrussell",
    photo: "/images/anthony.jpg",
    photoWidth: 864,
    photoHeight: 1152,
  },
];

function MemberPhoto({ member }: { member: BoardMember }) {
  const frameClass =
    "w-40 h-40 sm:w-44 sm:h-44 rounded-full overflow-hidden border-4 border-blue/20 shadow-md bg-surface-subtle";

  if (member.photo && member.photoWidth && member.photoHeight) {
    return (
      <div className={frameClass}>
        <Image
          src={member.photo}
          alt={member.name}
          width={member.photoWidth}
          height={member.photoHeight}
          className="object-cover w-full h-full"
          priority
        />
      </div>
    );
  }

  return (
    <div
      className={`${frameClass} flex items-center justify-center bg-gradient-to-br from-blue/15 to-blue/5`}
      aria-hidden
    >
      <span className="text-3xl sm:text-4xl font-bold text-blue/70 tracking-wide">
        {memberInitials(member.name)}
      </span>
    </div>
  );
}

export default function BoardPage() {
  if (!ENABLE_BOARD_PAGE) notFound();

  return (
    <div className="page-container py-10">
      <Link href="/" className="text-sm text-muted hover:text-blue">
        ← Back to lawmakers
      </Link>

      <h1 className="text-3xl font-bold text-blue mt-4">The People Behind the Mission</h1>
      <p className="mt-3 text-muted leading-relaxed max-w-2xl">
        Operation Child Shield is guided by leaders committed to protecting children,
        advancing transparency, and holding elected officials accountable through
        public data.{" "}
        <Link href="/organization" className="text-red font-semibold hover:underline">
          About the organization
        </Link>
        .
      </p>

      {[
        { title: "Officers", members: officers },
        { title: "Board Directors", members: boardDirectors },
      ].map(({ title, members }) => (
        <section key={title} className="mt-10">
          <h2 className="text-xl font-bold text-blue m-0">{title}</h2>
          <div className="mt-6 grid gap-8">
            {members.map((member) => (
              <article
                key={member.name}
                className="flex flex-col sm:flex-row items-center gap-6 bg-surface rounded-[10px] p-8 border border-card-border shadow-[0_6px_12px_-2px_rgb(0_0_0_/_0.1)]"
              >
                <div className="shrink-0">
                  <MemberPhoto member={member} />
                </div>
                <div className="flex-1 text-center sm:text-left">
                  <p className="text-xs font-bold uppercase tracking-wider text-red m-0">
                    {member.role}
                  </p>
                  <p className="mt-1 text-[0.7rem] font-semibold uppercase tracking-wide text-blue/80 m-0">
                    {member.membership}
                  </p>
                  <div className="mt-1 flex items-center gap-2 justify-center sm:justify-start">
                    <h3 className="text-2xl font-bold text-blue m-0">{member.name}</h3>
                    {member.linkedin && (
                      <a
                        href={member.linkedin}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#0A66C2] hover:text-[#004182] transition-colors"
                        aria-label={`${member.name} on LinkedIn`}
                      >
                        <LinkedInIcon />
                      </a>
                    )}
                  </div>
                  {member.organizationLabel && (
                    <p className="mt-2 text-muted text-sm leading-relaxed m-0">
                      {member.organizationLabel}
                    </p>
                  )}
                  {member.href && member.organization && (
                    <a
                      href={member.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-block mt-4 text-sm font-bold text-red hover:underline"
                    >
                      {member.organization} →
                    </a>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}