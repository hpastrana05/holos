import type { ReactNode } from "react";

export const today = () => new Date().toISOString().slice(0, 10);
export const monthValue = () => today().slice(0, 7);
export const euros = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "EUR",
});
export const shortDate = (value?: string) =>
  value
    ? new Intl.DateTimeFormat("es-ES", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(`${value}T00:00:00`))
    : "—";
export const api = async (path: string, token: string, options: RequestInit = {}) => {
  const response = await fetch("/api" + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
  if (!response.ok)
    throw new Error(
      (await response.json().catch(() => ({}))).detail ||
        "No se pudo completar la operación",
    );
  return response.status === 204 ? null : response.json();
};
export type Notice = { text: string; error?: boolean } | null;
export const Field = ({
  label,
  help,
  children,
}: {
  label: string;
  help?: string;
  children: ReactNode;
}) => (
  <label className="field">
    <span>{label}</span>
    {children}
    {help && <small>{help}</small>}
  </label>
);
