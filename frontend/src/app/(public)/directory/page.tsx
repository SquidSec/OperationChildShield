import { redirect } from "next/navigation";

interface DirectoryPageProps {
  searchParams: Promise<Record<string, string | undefined>>;
}

export default async function DirectoryPage({ searchParams }: DirectoryPageProps) {
  const params = await searchParams;
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) qs.set(key, value);
  });
  const query = qs.toString();
  redirect(query ? `/?${query}` : "/");
}