export interface UserProfile {
  id: number;
  email: string;
  displayName: string;
  emailVerified: boolean;
  createdAt?: string;
  lastLoginAt?: string | null;
}

export interface SavedMember {
  bioguideId: string;
  name: string;
  state: string;
}

export interface AlertSubscription {
  kind: "member_vote" | "bill_floor_vote" | "weekly_digest";
  bioguideId: string;
  active: boolean;
}

export const ALERT_LABELS: Record<AlertSubscription["kind"], string> = {
  member_vote: "Votes by a lawmaker I follow",
  bill_floor_vote: "New floor votes on tracked bills",
  weekly_digest: "Weekly digest",
};
