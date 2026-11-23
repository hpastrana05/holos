export const avatars = {
  initial: "Inicial",
  sun: "☀",
  moon: "☾",
  star: "★",
  heart: "♥",
};

export type Profile = { id: number; name: string; color: string; avatar: keyof typeof avatars };
export type Account = Profile & { email: string; role: "admin" | "member"; is_active: boolean; has_pin: boolean };

export function AccountAvatar({ profile }: { profile: Profile }) {
  return <span className="account-avatar" style={{ color: profile.color }} aria-hidden="true">
    {profile.avatar === "initial" ? Array.from(profile.name)[0]?.toLocaleUpperCase("es") : avatars[profile.avatar]}
  </span>;
}
