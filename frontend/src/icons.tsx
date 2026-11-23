const paths = {
  dashboard: "M3 10 12 3l9 7v10H3z M9 20v-6h6v6",
  health: "M20.8 8.5c0 5-8.8 11-8.8 11s-8.8-6-8.8-11A4.5 4.5 0 0 1 12 7a4.5 4.5 0 0 1 8.8 1.5Z M4 12h4l2-3 3 6 2-3h5",
  finance: "M3 6h18v13H3z M3 9h18 M17 14h1",
  nutrition: "M4 3v6a2 2 0 0 0 4 0V3 M6 3v18 M18 21V3c-3 2-4 5-4 9h4",
  calendar: "M3 6h18v14H3z M7 3v6 M17 3v6 M3 11h18 M8 15h2 M14 15h2",
  house: "M3 10 12 3l9 7v10H3z M11 17l3-4h-4l3-4",
  chat: "M21 4H3v13h5v4l5-4h8z M7 9h10 M7 13h6",
  logout: "M10 4H4v16h6 M9 12h12 M17 8l4 4-4 4",
  screen: "M3 4h18v13H3z M12 17v4 M8 21h8",
};

export type IconName = keyof typeof paths;

export function Icon({ name }: { name: IconName }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" width="24" height="24"
      fill="none" stroke="currentColor" strokeWidth="1.7"
      strokeLinecap="round" strokeLinejoin="round">
      <path d={paths[name]} />
    </svg>
  );
}
