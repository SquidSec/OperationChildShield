/**
 * Role-based action guidance.
 *
 * Content only — the page that renders it lives at /take-action. Keeping the
 * copy in one module makes it easy to review the guidance without touching
 * markup. Every action is lawful and nonpartisan; nothing here asks a reader to
 * approach a suspect or to expose a victim.
 */

export type RoleId =
  | "parent"
  | "teacher"
  | "leo"
  | "medical"
  | "child"
  | "teen"
  | "faith"
  | "business"
  | "volunteer";

export interface ActionStep {
  title: string;
  body: string;
  /** Optional link the step points to. Internal paths or absolute URLs. */
  href?: string;
  linkLabel?: string;
  external?: boolean;
}

export interface Role {
  id: RoleId;
  label: string;
  /** One line shown under the label in the picker. */
  tagline: string;
  /** Short emoji-free glyph key used for the icon. */
  icon: "shield" | "book" | "badge" | "heart" | "child" | "spark" | "cross" | "briefcase" | "hands";
  intro: string;
  steps: ActionStep[];
  /** A closing line that names the limit of the role's authority. */
  guardrail: string;
}

const CYBERTIP = {
  href: "https://report.cybertip.org/",
  linkLabel: "Report to the CyberTipline",
  external: true,
} as const;

const HOTLINE = {
  href: "tel:18008435678",
  linkLabel: "Call 1-800-THE-LOST",
} as const;

const FIND_LAWMAKERS = {
  href: "/",
  linkLabel: "Find your lawmakers",
} as const;

const BILLS = {
  href: "/bills",
  linkLabel: "See the tracked bills",
} as const;

const NEWS = {
  href: "/news",
  linkLabel: "Read the Daily Brief",
} as const;

export const ROLES: Role[] = [
  {
    id: "parent",
    label: "Parent or caregiver",
    tagline: "I raise children and run a household.",
    icon: "heart",
    intro:
      "Most exploitation begins with access, not abduction. The highest-value work you can do is shrink the access your child's devices and social accounts give strangers, and make sure your child knows you will not punish them for telling you something went wrong.",
    steps: [
      {
        title: "Turn on the settings that block strangers",
        body:
          "On every app your child uses, set the account to private, turn off location sharing, and disable contact from people who are not friends. Do this together, on the actual device, so your child sees where the switches are.",
      },
      {
        title: "Agree on a no-questions safety rule",
        body:
          "Tell your child, in plain words, that if anyone asks for a photo, asks them to keep a secret from you, or says they will get in trouble if they tell, they can come to you and you will handle it without blaming them. Secrecy is the tool abusers rely on most.",
      },
      {
        title: "Know the reporting path before you need it",
        body:
          "If your child discloses something, preserve the messages, do not delete or forward the images, and report to the CyberTipline and your local police. NCMEC's analysts route reports to the right agency.",
        ...CYBERTIP,
      },
      {
        title: "Ask your school what its policy actually says",
        body:
          "Request the district's child-safety, device-use, and visitor policies in writing. Districts with a named trafficking-response protocol and staff training report incidents faster than those without one.",
      },
      {
        title: "Push your representatives",
        body:
          "Tracked child-protection bills move or stall on committee schedules. A short call to a district office asking where a bill sits does more than a social media post.",
        ...FIND_LAWMAKERS,
      },
    ],
    guardrail:
      "You are not an investigator. Preserve evidence and hand it to law enforcement rather than questioning a suspect or searching a device yourself.",
  },
  {
    id: "teacher",
    label: "Teacher or school staff",
    tagline: "I work with students every day.",
    icon: "book",
    intro:
      "School staff are the most common adults to hear a disclosure first. You already have a legal duty to report suspected abuse in every state; the gap is usually knowing which behaviors to notice and having a calm script ready.",
    steps: [
      {
        title: "Learn the four behavioral signals",
        body:
          "Watch for a student who suddenly has unexplained money or a new phone, who is chronically absent or exhausted, who mentions an older \"boyfriend\" or \"sponsor,\" or who is secretive about a device. None proves trafficking; each warrants a report.",
      },
      {
        title: "Use a script, not an interview",
        body:
          "Ask only what you need to report: \"Are you safe right now?\" and \"Can you tell me who this person is?\" Do not press for details or ask leading questions — a child's first account matters in court, and repeated questioning can hurt a case.",
      },
      {
        title: "Report through the channel, then document",
        body:
          "Follow your state's mandated-reporter procedure the same day, then write down what the student said in their own words, the time, and to whom you reported. Keep it factual.",
        ...CYBERTIP,
      },
      {
        title: "Ask for the training, in writing",
        body:
          "Request documented trafficking and exploitation training for all staff, not only counselors. Ask whether the district has a named point of contact and a written response protocol.",
      },
      {
        title: "Teach the prevention unit",
        body:
          "Age-appropriate material on grooming, online strangers, and \"if something feels wrong, tell a trusted adult\" is the intervention that reaches students before a recruiter does.",
      },
    ],
    guardrail:
      "You are a mandated reporter, not a caseworker. Report and support; do not investigate, and do not contact a suspected trafficker or their family on your own.",
  },
  {
    id: "leo",
    label: "Law enforcement",
    tagline: "I wear a badge or work in public safety.",
    icon: "badge",
    intro:
      "Trafficking cases are rarely made by a single interview. They are made by documentation that survives a defense motion, by victim-centered interviews, and by referral to the task force that can follow the money and the network.",
    steps: [
      {
        title: "Know your state's statutory elements cold",
        body:
          "Trafficking statutes vary on the force, fraud, or coercion element for minors, on whether a commercial-sex act alone suffices, and on the available enhancements. Charge the elements your statute actually requires.",
      },
      {
        title: "Route to the task force early",
        body:
          "Notify your local human trafficking task force and the FBI field office or HSI special agent covering your area at the point of first disclosure, not after the case is built.",
      },
      {
        title: "Use a victim-centered, trauma-informed interview",
        body:
          "A forensic interviewer or child advocacy center should conduct the interview. Your job at the scene is safety, evidence preservation, and not re-interviewing the child.",
      },
      {
        title: "Preserve the digital record correctly",
        body:
          "Messages, account identifiers, and device data disappear fast. Document the chain of custody, capture with a forensic tool where available, and do not open or forward suspected abuse material outside your agency's evidence system.",
        ...CYBERTIP,
      },
      {
        title: "Track what your legislature is doing",
        body:
          "Statutory gaps are the reason cases fail. See which tracked bills change the elements you have to prove, and tell your association's lobbyist where the code is falling short.",
        ...BILLS,
      },
    ],
    guardrail:
      "Handle child sexual abuse material only inside an approved evidence system. Never store, forward, or view it outside the case workflow.",
  },
  {
    id: "medical",
    label: "Nurse, doctor, or clinician",
    tagline: "I provide care in a clinic or hospital.",
    icon: "cross",
    intro:
      "A trafficked patient often presents for something else: a sexually transmitted infection, a fracture, a pregnancy, or a \"friend\" who answers every question. Your exam may be the only private contact the patient gets.",
    steps: [
      {
        title: "Create ten minutes alone with the patient",
        body:
          "Use a routine pretext to separate the patient from the accompanying adult — a required lab, a scan, a form that must be completed alone. This is the single highest-yield step in a clinical setting.",
      },
      {
        title: "Screen with a validated tool",
        body:
          "Use a short validated screen rather than an improvised question. Document the result in the chart in neutral language.",
      },
      {
        title: "Document injuries and identifiers precisely",
        body:
          "Record injury patterns, tattoos or branding, and the patient's own words verbatim. Describe the accompanying adult's relationship and behavior. Chart what you observe, not conclusions you cannot support.",
      },
      {
        title: "Report and connect to advocacy",
        body:
          "Follow your state's mandated-reporter rule and involve a hospital social worker or a trafficking-specific advocacy program in the same visit.",
        ...CYBERTIP,
      },
      {
        title: "Know the community resources without referring",
        body:
          "Have the local child advocacy center, SANE program, and youth shelter on a laminated card at the desk. A referral the patient cannot safely carry is not a referral.",
        ...HOTLINE,
      },
    ],
    guardrail:
      "Meet the patient where they are. A patient who leaves against advice is still a patient who may return; keep the door open and do not confront the accompanying adult.",
  },
  {
    id: "child",
    label: "I'm under 18",
    tagline: "I'm a kid or teenager.",
    icon: "child",
    intro:
      "You do not have to be sure something is wrong to tell an adult. If someone older is asking you for photos, money, or secrets, or is offering you things that feel too good, that is enough reason to get help.",
    steps: [
      {
        title: "Tell one adult you trust",
        body:
          "A parent, a teacher, a coach, a school counselor, a nurse, or a friend's parent. Say it in your own words. You do not need proof and you are not in trouble.",
      },
      {
        title: "Never send a photo, even if they already have one",
        body:
          "If someone has a photo and is threatening to share it, that is a crime against you, not something you did wrong. Stop responding, save the messages, and tell an adult immediately.",
      },
      {
        title: "You can report it yourself",
        body:
          "The CyberTipline takes reports from anyone, including teenagers, and you can ask them not to contact your parents if that is not safe for you. Calling 1-800-THE-LOST works too.",
        ...CYBERTIP,
      },
      {
        title: "Check your account privacy tonight",
        body:
          "Turn your accounts private, turn off location sharing, and remove anyone you do not know in real life. You do not owe a stranger access to you.",
      },
      {
        title: "Help a friend without taking over",
        body:
          "If a friend is in this situation, do not promise to keep it secret. Go with them to tell an adult, or tell an adult yourself. Staying silent to protect a friendship can put them in more danger.",
      },
    ],
    guardrail:
      "Nothing that happened is your fault, and nothing you did makes you a criminal. Adults are responsible for getting you help.",
  },
  {
    id: "teen",
    label: "Young adult or student",
    tagline: "I'm in college or just starting out.",
    icon: "spark",
    intro:
      "Recruiters target young people who are new to a city, short on money, or isolated — which describes a lot of first-year students. You are also the peer most likely to notice when a friend's situation changes.",
    steps: [
      {
        title: "Learn the recruitment patterns",
        body:
          "Offers of a \"modeling gig,\" a place to stay, or fast cash from someone who will not meet in public are the standard opening. So is a much older partner who isolates a young person from friends and family.",
      },
      {
        title: "Watch for the money and the isolation",
        body:
          "A new phone, unexplained cash, a hotel stay, or a friend who suddenly cannot be reached alone are the signals peers notice first.",
        ...CYBERTIP,
      },
      {
        title: "Ask campus for a real protocol",
        body:
          "Request that your university's Title IX office, campus police, and health center have a written trafficking response protocol and staff training. Many do not.",
      },
      {
        title: "Volunteer where the need actually is",
        body:
          "Court-appointed special advocate programs, child advocacy centers, and youth shelters take trained volunteers. One consistent adult changes outcomes more than a one-day event.",
        href: "/get-involved",
        linkLabel: "Sign up to volunteer",
      },
      {
        title: "Vote and call on the record",
        body:
          "Tracked bills live or die in committee. Read the voting records, then call your representative's district office and ask where the bill sits.",
        ...FIND_LAWMAKERS,
      },
    ],
    guardrail:
      "Do not confront a suspected trafficker or try to extract a friend yourself. Report and stay present — safety planning with a professional is what works.",
  },
  {
    id: "faith",
    label: "Faith or community leader",
    tagline: "I lead a congregation or community group.",
    icon: "hands",
    intro:
      "Congregations and community groups reach families that will never walk into a police station. That trust is the asset — and it comes with the responsibility to report rather than to counsel privately and hope.",
    steps: [
      {
        title: "Train the people who greet families",
        body:
          "Volunteers and staff should be able to recognize a disclosure and know the exact reporting path. A one-hour training with a local child advocacy center is enough to start.",
      },
      {
        title: "Never promise confidentiality for abuse",
        body:
          "Say plainly that you will help and that you must report suspected abuse to the authorities. A promise of secrecy can leave a child in an unsafe home.",
        ...CYBERTIP,
      },
      {
        title: "Host the prevention conversation",
        body:
          "Bring in a trained presenter for parents on device settings, grooming, and reporting. Provide childcare so the parents who most need it can attend.",
      },
      {
        title: "Make your building available",
        body:
          "Offer space for a child advocacy center, a support group, or a youth shelter's evening program. Physical space is often the binding constraint for local services.",
      },
      {
        title: "Speak about it without a political frame",
        body:
          "Child exploitation is not a partisan issue. Naming it from the pulpit or the meeting hall without assigning blame to a party keeps the room open to everyone.",
        ...NEWS,
      },
    ],
    guardrail:
      "You are not a counselor for abuse cases. Refer to a licensed clinician and report to the authorities; do not attempt to mediate between a child and a suspected abuser.",
  },
  {
    id: "business",
    label: "Employer or business owner",
    tagline: "I hire people and run a workplace.",
    icon: "briefcase",
    intro:
      "Trafficking operations rely on legitimate businesses — hotels, short-term rentals, truck stops, cleaning and agricultural contractors — either as venues or as a cover for labor. Your staff see it first, and your policies decide whether they act.",
    steps: [
      {
        title: "Put a written protocol in the handbook",
        body:
          "Name the signal behaviors, the person to notify, and the expectation that staff report to law enforcement. A protocol nobody can point to is not a protocol.",
      },
      {
        title: "Adopt the anti-trafficking signage and training",
        body:
          "The standard hotel and hospitality training packages are free. Post the hotline where staff and guests can see it.",
        ...HOTLINE,
      },
      {
        title: "Audit your own supply chain",
        body:
          "Ask staffing agencies and subcontractors for their labor-recruitment policy, and check that workers keep their own identity documents and are paid directly.",
      },
      {
        title: "Screen your own hiring",
        body:
          "Use consistent background checks for roles with access to children, and never place a new hire alone with minors before checks clear.",
      },
      {
        title: "Fund the local response",
        body:
          "Child advocacy centers and task forces are chronically underfunded. A local grant or in-kind donation has a direct, visible effect.",
        href: "/donate",
        linkLabel: "Support the work",
      },
    ],
    guardrail:
      "Document and report; do not detain a guest or employee based on suspicion. Confronting an operation can put staff and victims at risk.",
  },
  {
    id: "volunteer",
    label: "Retired, between jobs, or ready to help",
    tagline: "I have time to give.",
    icon: "shield",
    intro:
      "The organizations doing this work are usually short on trained, consistent adults — not on good intentions. The most useful offer is a recurring block of hours and a background check you are willing to pass.",
    steps: [
      {
        title: "Pick a role with training attached",
        body:
          "Court-appointed special advocates, child advocacy center support staff, and youth shelter volunteers all provide training and supervision. Start there rather than with an unpaid solo project.",
        href: "/get-involved",
        linkLabel: "Sign up with us",
      },
      {
        title: "Commit to a recurring shift",
        body:
          "One adult who shows up every week outperforms a large one-day volunteer event. Organizations plan around reliability.",
      },
      {
        title: "Use your actual profession",
        body:
          "Bookkeeping, translation, legal research, IT, and grant writing are the needs nonprofits cannot fill. Offer the skill you already have.",
      },
      {
        title: "Learn before you speak publicly",
        body:
          "Read the sources behind the headlines so you are not repeating a claim that turns out to be wrong. Every Daily Brief lists its sources.",
        ...NEWS,
      },
      {
        title: "Hold your representatives to the record",
        body:
          "Read how your members voted on tracked child-protection bills, then ask them in writing where the current bill sits.",
        ...FIND_LAWMAKERS,
      },
    ],
    guardrail:
      "Never conduct your own investigation, approach a suspected trafficker, or post details about a case online. Report to the professionals and let them work.",
  },
];

export function getRole(id: string): Role | undefined {
  return ROLES.find((role) => role.id === id);
}

export function roleDefaultId(): RoleId {
  return "parent";
}
