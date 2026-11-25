// @ts-nocheck
import React, { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, euros, Field, monthValue, shortDate, today, type Notice } from "./shared";

const weightNumber = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 2 });
const formatWeight = (value: number | null | undefined) =>
  value == null ? "—" : weightNumber.format(value);

const State = ({
  loading,
  error,
  empty,
  children,
}: {
  loading?: boolean;
  error?: string;
  empty?: boolean;
  children: React.ReactNode;
}) =>
  error ? (
    <p className="state error">{error}</p>
  ) : loading ? (
    <p className="state">Cargando…</p>
  ) : empty ? (
    <p className="state">Aún no hay datos.</p>
  ) : (
    <>{children}</>
  );
function useLoad(token: string, path: string) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState("");
  const load = () => {
    setError("");
    return api(path, token)
      .then(setData)
      .catch((e) => setError(e.message));
  };
  useEffect(() => {
    load();
  }, [path]);
  return { data, error, load };
}

export function Dashboard({ token }: { token: string }) {
  const health = useLoad(token, "/health/summary"),
    series = useLoad(token, "/finance/summary/monthly-series?months=6"),
    recent = useLoad(token, "/finance/transactions?limit=5"),
    nutrition = useLoad(token, "/nutrition/summary"),
    calendar = useLoad(token, "/calendar/events/upcoming?days=7");
  return (
    <>
      <h2>Resumen</h2>
      <State
        loading={!health.data || !series.data || !recent.data}
        error={health.error || series.error || recent.error}
      >
        <div className="cards">
          <article>
            <label>Peso actual</label>
            <b>{formatWeight(health.data?.current_weight_kg)} kg</b>
            <small>
              Objetivo: {formatWeight(health.data?.target_weight_kg)} kg · Restan{" "}
              {formatWeight(health.data?.remaining_kg)} kg
            </small>
          </article>
          <article>
            <label>Próximo evento</label>
            <b>{calendar.data?.[0]?.title ?? "—"}</b>
            <small>{calendar.data?.[0]?.start ? new Intl.DateTimeFormat("es-ES", { dateStyle: "short", timeStyle: "short", timeZone: "Europe/Madrid" }).format(new Date(calendar.data[0].start)) : "Conecta Google Calendar"}</small>
          </article>
          <article>
            <label>Objetivo diario</label>
            <b>{health.data?.target_kcal ?? "—"} kcal</b>
            <small>Estimación basada en tu perfil y objetivo.</small>
          </article>
          <article>
            <label>Nutrición de hoy</label>
            <b>{Math.round(nutrition.data?.totals?.kcal ?? 0)} kcal</b>
            <small>{nutrition.data?.target_kcal ? `Objetivo: ${nutrition.data.target_kcal} kcal` : "Completa tu perfil de salud para calcular el objetivo."}</small>
          </article>
        </div>
        <div className="chart-grid">
          <ChartCard title="Evolución del peso" empty={!health.data?.entries?.length}>
            <LineChart data={health.data?.entries || []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tickFormatter={shortDate} />
              <YAxis domain={["auto", "auto"]} unit=" kg" tickFormatter={formatWeight} />
              <Tooltip labelFormatter={shortDate} formatter={(value: number) => formatWeight(value)} />
              <Line
              isAnimationActive={false}
                type="monotone"
                dataKey="weight_kg"
                name="Peso"
                stroke="var(--chart-primary)"
                strokeWidth={3}
                dot
              />
              <Line
              isAnimationActive={false}
                data={health.data?.entries?.map((entry: any) => ({
                  ...entry,
                  target: health.data.target_weight_kg,
                }))}
                dataKey="target"
                name="Objetivo"
                stroke="var(--chart-secondary)"
                strokeDasharray="5 5"
                dot={false}
              />
            </LineChart>
          </ChartCard>
          <ChartCard title="Ingresos y gastos · últimos 6 meses" empty={emptySeries(series.data)}>
            <BarChart data={series.data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" />
              <YAxis />
              <Tooltip formatter={(value: number) => euros.format(value)} />
              <Legend />
              <Bar isAnimationActive={false} dataKey="income" name="Ingresos" fill="var(--chart-primary)" />
              <Bar isAnimationActive={false} dataKey="expense" name="Gastos" fill="var(--chart-secondary)" />
            </BarChart>
          </ChartCard>
        </div>
        <section>
          <h3>Últimos movimientos</h3>
          <TransactionList transactions={recent.data} />
        </section>
      </State>
    </>
  );
}
const emptySeries = (rows: { income: number; expense: number }[] | null) =>
  !rows?.some(({ income, expense }) => income !== 0 || expense !== 0);

const ChartCard = ({
  title,
  empty,
  children,
}: {
  title: string;
  empty: boolean;
  children: React.ReactElement;
}) => (
  <section className="chart">
    <h3>{title}</h3>
    <div className="chart-body">
      {empty ? (
        <p className="state chart-empty">Sin datos</p>
      ) : (
        <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={280}>
          {children}
        </ResponsiveContainer>
      )}
    </div>
  </section>
);
const TransactionList = ({
  transactions,
  onEdit,
  onDelete,
}: {
  transactions: any[];
  onEdit?: (item: any) => void;
  onDelete?: (id: number) => void;
}) =>
  !transactions.length ? (
    <p className="state">Aún no hay movimientos.</p>
  ) : (
    <ul className="list">
      {transactions.map((item) => (
        <li key={item.id}>
          <span>
            <b>
              {item.kind === "income" ? "+" : "−"}
              {euros.format(item.amount)}
            </b>
            <small>
              {shortDate(item.date)} ·{" "}
              {item.visibility === "shared" ? "Compartido" : "Personal"}
              {item.note ? ` · ${item.note}` : ""}
            </small>
          </span>
          {onEdit && (
            <span className="actions">
              <button onClick={() => onEdit(item)}>Editar</button>
              <button className="danger" onClick={() => onDelete?.(item.id)}>
                Borrar
              </button>
            </span>
          )}
        </li>
      ))}
    </ul>
  );

export function Health({ token }: { token: string }) {
  const summary = useLoad(token, "/health/summary"),
    weights = useLoad(token, "/health/weights"),
    goals = useLoad(token, "/health/goals"),
    profile = useLoad(token, "/health/profile");
  const [notice, setNotice] = useState<Notice>(null),
    [editing, setEditing] = useState<any>(null);
  const reload = () =>
    Promise.all([summary.load(), weights.load(), goals.load(), profile.load()]);
  if (!summary.data) summary.data = {};
  if (!Array.isArray(weights.data)) weights.data = [];
  if (!Array.isArray(goals.data)) goals.data = [];
  const activeGoal = goals.data.find((goal: any) => goal.active);
  const saveWeight = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = {
      date: f.get("date"),
      weight_kg: +f.get("weight_kg")!,
      source: "manual",
      notes: f.get("notes") || null,
    };
    try {
      await api(
        editing ? `/health/weights/${editing.id}` : "/health/weights",
        token,
        { method: editing ? "PUT" : "POST", body: JSON.stringify(body) },
      );
      setEditing(null);
      e.currentTarget.reset();
      setNotice({ text: "Peso guardado." });
      reload();
    } catch (error: any) {
      setNotice({ text: error.message, error: true });
    }
  };
  const remove = async (id: number) => {
    if (!confirm("¿Borrar esta medición de peso?")) return;
    await api(`/health/weights/${id}`, token, { method: "DELETE" });
    setNotice({ text: "Medición eliminada." });
    reload();
  };
  return (
    <>
      <h2>Salud</h2>
      <State
        loading={!summary.data || !weights.data || !goals.data}
        error={summary.error || weights.error || goals.error}
      >
        <NoticeBox notice={notice} />
        <div className="cards">
          <article>
            <label>Kcal objetivo/día</label>
            <b>{summary.data.target_kcal ?? "—"}</b>
          </article>
          <article>
            <label>Progreso</label>
            <b>{summary.data.progress_pct ?? "—"}%</b>
            <small>
              {formatWeight(summary.data.remaining_kg)} kg hasta el objetivo
            </small>
          </article>
          <article>
            <label>Tendencia</label>
            <b>{formatWeight(summary.data.trend_kg)} kg</b>
            <small>
              Llegada estimada: {shortDate(summary.data.estimated_goal_date)}
            </small>
          </article>
        </div>
        <ChartCard title="Peso y objetivo" empty={!weights.data?.length}>
          <LineChart
            data={(weights.data || []).map((weight: any) => ({
              ...weight,
              target: summary.data?.target_weight_kg,
            }))}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tickFormatter={shortDate} />
            <YAxis domain={["auto", "auto"]} unit=" kg" tickFormatter={formatWeight} />
            <Tooltip labelFormatter={shortDate} formatter={(value: number) => formatWeight(value)} />
            <Legend />
            <Line
              isAnimationActive={false}
              dataKey="weight_kg"
              name="Peso"
              stroke="var(--chart-primary)"
              strokeWidth={3}
            />
            <Line
              isAnimationActive={false}
              dataKey="target"
              name="Objetivo"
              stroke="var(--chart-secondary)"
              strokeDasharray="5 5"
              dot={false}
            />
          </LineChart>
        </ChartCard>
        <div className="health-forms">
          <section>
            <h3>{editing ? "Editar peso" : "Registrar peso"}</h3>
            <form onSubmit={saveWeight}>
              <Field label="Fecha">
                <input
                  name="date"
                  type="date"
                  defaultValue={editing?.date || today()}
                  required
                />
              </Field>
              <Field label="Peso (kg)">
                <input
                  name="weight_kg"
                  type="number"
                  step="0.1"
                  min="20"
                  max="500"
                  defaultValue={editing?.weight_kg}
                  placeholder="Ej.: 74.2"
                  required
                />
              </Field>
              <Field label="Nota (opcional)">
                <input
                  name="notes"
                  defaultValue={editing?.notes || ""}
                  placeholder="Ej.: en ayunas"
                />
              </Field>
              <button>{editing ? "Guardar cambios" : "Añadir peso"}</button>
              {editing && (
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setEditing(null)}
                >
                  Cancelar
                </button>
              )}
            </form>
          </section>
          {(["profile", "goal"] as const).map((mode) => (
            <ProfileForm
              key={mode}
              mode={mode}
              token={token}
              profile={profile.data}
              goal={activeGoal}
              done={() => {
                setNotice({ text: "Perfil u objetivo actualizado." });
                reload();
              }}
            />
          ))}
        </div>
        <section>
          <h3>Historial de pesos</h3>
          <State empty={!weights.data?.length}>
            <ul className="list">
              {weights.data
                .slice()
                .reverse()
                .map((weight: any) => (
                  <li key={weight.id}>
                    <span>
                      <b>{formatWeight(weight.weight_kg)} kg</b>
                      <small>
                        {shortDate(weight.date)}
                        {weight.notes ? ` · ${weight.notes}` : ""}
                      </small>
                    </span>
                    <span className="actions">
                      <button onClick={() => setEditing(weight)}>Editar</button>
                      <button
                        className="danger"
                        onClick={() => remove(weight.id)}
                      >
                        Borrar
                      </button>
                    </span>
                  </li>
                ))}
            </ul>
          </State>
        </section>
      </State>
    </>
  );
}
function ProfileForm({ mode, token, profile, goal, done }: any) {
  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body =
      mode === "profile"
        ? {
            height_cm: +f.get("height_cm")!,
            birth_date: f.get("birth_date"),
            sex: f.get("sex"),
            activity_level: f.get("activity_level"),
          }
        : {
            start_weight_kg: +f.get("start")!,
            target_weight_kg: +f.get("target")!,
            start_date: f.get("start_date"),
            target_date: f.get("target_date") || null,
            weekly_rate_kg: +f.get("rate")!,
            mode: "lose",
            active: true,
          };
    await api(
      mode === "profile"
        ? "/health/profile"
        : goal
          ? `/health/goals/${goal.id}`
          : "/health/goals",
      token,
      {
        method: mode === "profile" || goal ? "PUT" : "POST",
        body: JSON.stringify(body),
      },
    );
    done();
  };
  return (
    <section>
      <h3>{mode === "profile" ? "Perfil" : "Objetivo de peso"}</h3>
      <form onSubmit={submit}>
        {mode === "profile" ? (
          <>
            <Field label="Altura (cm)">
              <input
                name="height_cm"
                type="number"
                step="0.1"
                defaultValue={profile?.height_cm}
                required
              />
            </Field>
            <Field label="Nacimiento">
              <input
                name="birth_date"
                type="date"
                defaultValue={profile?.birth_date}
                required
              />
            </Field>
            <Field label="Sexo">
              <select name="sex" defaultValue={profile?.sex || "female"}>
                <option value="female">Mujer</option>
                <option value="male">Hombre</option>
              </select>
            </Field>
            <Field label="Actividad">
              <select
                name="activity_level"
                defaultValue={profile?.activity_level || "sedentary"}
              >
                <option value="sedentary">Sedentario</option>
                <option value="light">Ligero</option>
                <option value="moderate">Moderado</option>
                <option value="active">Activo</option>
              </select>
            </Field>
          </>
        ) : (
          <>
            <Field label="Peso inicial (kg)">
              <input
                name="start"
                type="number"
                step="0.1"
                defaultValue={goal?.start_weight_kg}
                required
              />
            </Field>
            <Field label="Peso objetivo (kg)">
              <input
                name="target"
                type="number"
                step="0.1"
                defaultValue={goal?.target_weight_kg}
                required
              />
            </Field>
            <Field label="Fecha de inicio">
              <input
                name="start_date"
                type="date"
                defaultValue={goal?.start_date || today()}
                required
              />
            </Field>
            <Field label="Fecha objetivo (opcional)">
              <input
                name="target_date"
                type="date"
                defaultValue={goal?.target_date}
              />
            </Field>
            <Field label="Ritmo semanal (kg)">
              <input
                name="rate"
                type="number"
                min="0.1"
                max="1"
                step="0.1"
                defaultValue={goal?.weekly_rate_kg || 0.5}
                required
              />
            </Field>
          </>
        )}
        <button>Guardar {mode === "profile" ? "perfil" : "objetivo"}</button>
      </form>
    </section>
  );
}

export function Finance({ token }: { token: string }) {
  const [month, setMonth] = useState(monthValue()),
    [tab, setTab] = useState<"general" | "categories">("general"),
    [filters, setFilters] = useState({ kind: "", category: "" }),
    [notice, setNotice] = useState<Notice>(null),
    [editing, setEditing] = useState<any>(null);
  const [refresh, setRefresh] = useState(0);
  const [year, mon] = month.split("-").map(Number);
  const monthStart = `${month}-01`;
  const monthEnd = `${month}-${String(new Date(year, mon, 0).getDate()).padStart(2, "0")}`;
  const [start, setStart] = useState(monthStart);
  const [end, setEnd] = useState(monthEnd);
  const selectMonth = (value: string) => {
    const [nextYear, nextMonth] = value.split("-").map(Number);
    setMonth(value);
    setStart(`${value}-01`);
    setEnd(`${value}-${String(new Date(nextYear, nextMonth, 0).getDate()).padStart(2, "0")}`);
  };
  const categories = useLoad(token, "/finance/categories"),
    monthly = useLoad(
      token,
      `/finance/summary/monthly?year=${year}&month=${mon}`,
    ),
    series = useLoad(
      token,
      `/finance/summary/monthly-series?year=${year}&month=${mon}&months=6`,
    ),
    breakdown = useLoad(
      token,
      `/finance/summary/categories?start=${start}&end=${end}`,
    ),
    budgets = useLoad(
      token,
      `/finance/budgets/progress?year=${year}&month=${mon}`,
    ),
    transactions = useLoad(
      token,
      `/finance/transactions?start=${start}&end=${end}${filters.kind ? `&kind=${filters.kind}` : ""}${filters.category ? `&category_id=${filters.category}` : ""}`,
    );
  if (!Array.isArray(categories.data)) categories.data = [];
  if (!monthly.data) monthly.data = { income: 0, expense: 0, balance: 0 };
  if (!Array.isArray(series.data)) series.data = [];
  if (!Array.isArray(breakdown.data)) breakdown.data = [];
  if (!Array.isArray(budgets.data)) budgets.data = [];
  if (!Array.isArray(transactions.data)) transactions.data = [];
  const reload = () => {
    [monthly, series, breakdown, budgets, transactions].forEach((item) =>
      item.load(),
    );
    setRefresh(refresh + 1);
  };
  const expenses = breakdown.data.filter(
    (item: any) => item.kind === "expense",
  );
  const saveTransaction = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = {
      kind: f.get("kind"),
      amount: +f.get("amount")!,
      category_id: f.get("category") ? +f.get("category")! : null,
      date: f.get("date"),
      note: f.get("note") || null,
      visibility: f.get("visibility"),
    };
    try {
      await api(
        editing
          ? `/finance/transactions/${editing.id}`
          : "/finance/transactions",
        token,
        { method: editing ? "PUT" : "POST", body: JSON.stringify(body) },
      );
      setEditing(null);
      e.currentTarget.reset();
      setNotice({ text: "Movimiento guardado." });
      reload();
    } catch (error: any) {
      setNotice({ text: error.message, error: true });
    }
  };
  return (
    <>
      <h2>Finanzas</h2>
      <NoticeBox notice={notice} />
      <div className="filters">
        <Field label="Mes">
          <input
            type="month"
            value={month}
            onChange={(e) => selectMonth(e.target.value)}
          />
        </Field>
        <Field label="Desde">
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </Field>
        <Field label="Hasta">
          <input type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} />
        </Field>
        <div className="tabs">
          <button
            className={tab === "general" ? "active" : ""}
            onClick={() => setTab("general")}
          >
            General
          </button>
          <button
            className={tab === "categories" ? "active" : ""}
            onClick={() => setTab("categories")}
          >
            Categorías
          </button>
        </div>
      </div>
      <State
        loading={!monthly.data || !series.data || !transactions.data}
        error={monthly.error || series.error || transactions.error}
      >
        {tab === "general" && (
          <div className="cards">
            <article>
              <label>Ingresos</label>
              <b>{euros.format(monthly.data.income)}</b>
            </article>
            <article>
              <label>Gastos</label>
              <b>{euros.format(monthly.data.expense)}</b>
            </article>
            <article>
              <label>Balance</label>
              <b>{euros.format(monthly.data.balance)}</b>
            </article>
          </div>
        )}
        <div className="finance-grid">
          {tab === "general" ? (
            <ChartCard title="Ingresos y gastos" empty={emptySeries(series.data)}>
              <BarChart data={series.data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip formatter={(value: number) => euros.format(value)} />
                <Legend />
                <Bar isAnimationActive={false} dataKey="income" name="Ingresos" fill="var(--chart-primary)" />
                <Bar isAnimationActive={false} dataKey="expense" name="Gastos" fill="var(--chart-secondary)" />
              </BarChart>
            </ChartCard>
          ) : (
            <>
              <ChartCard title="Gastos por categoría" empty={!expenses.length}>
                <PieChart>
                  <Pie
                    isAnimationActive={false}
                    data={expenses}
                    dataKey="amount"
                    nameKey="category"
                    fill="var(--chart-primary)"
                    label={({ category, percent }) =>
                      `${category} ${(percent * 100).toFixed(0)}%`
                    }
                  />
                  <Tooltip
                    formatter={(value: number) => euros.format(value)}
                  />
                </PieChart>
              </ChartCard>
              <section>
                <h3>Top categorías</h3>
                {!expenses.length && <p className="state">Sin datos</p>}
                <ul className="list">
                  {expenses
                    .sort((a: any, b: any) => b.amount - a.amount)
                    .slice(0, 5)
                    .map((item: any) => (
                      <li key={item.category}>
                        <span>{item.category}</span>
                        <b>{euros.format(item.amount)}</b>
                      </li>
                    ))}
                </ul>
              </section>
              <BudgetPanel
                token={token}
                year={year}
                month={mon}
                categories={categories.data || []}
                budgets={budgets.data || []}
                done={reload}
              />
            </>
          )}
          <section>
            <h3>{editing ? "Editar movimiento" : "Nuevo movimiento"}</h3>
            <form className="transaction-form" onSubmit={saveTransaction}>
              <Field label="Tipo">
                <select name="kind" defaultValue={editing?.kind || "expense"}>
                  <option value="expense">Gasto</option>
                  <option value="income">Ingreso</option>
                </select>
              </Field>
              <Field label="Importe (€)">
                <input
                  name="amount"
                  type="number"
                  min="0.01"
                  step="0.01"
                  defaultValue={editing?.amount}
                  required
                />
              </Field>
              <Field label="Categoría">
                <select name="category" defaultValue={editing?.category_id || ""}>
                  <option value="">Sin categoría</option>
                  {(categories.data || []).map((c: any) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Fecha">
                <input
                  name="date"
                  type="date"
                  defaultValue={editing?.date || today()}
                  required
                />
              </Field>
              <Field label="Nota">
                <input name="note" defaultValue={editing?.note || ""} />
              </Field>
              <Field label="Visibilidad">
                <select
                  name="visibility"
                  defaultValue={editing?.visibility || "personal"}
                >
                  <option value="personal">Personal</option>
                  <option value="shared">Compartido</option>
                </select>
              </Field>
              <button>
                {editing ? "Guardar cambios" : "Guardar movimiento"}
              </button>
            </form>
          </section>
        </div>
        <section>
          <h3>Movimientos</h3>
          <div className="filters compact">
            <Field label="Tipo">
              <select
                value={filters.kind}
                onChange={(e) =>
                  setFilters({ ...filters, kind: e.target.value })
                }
              >
                <option value="">Todos</option>
                <option value="income">Ingresos</option>
                <option value="expense">Gastos</option>
              </select>
            </Field>
            <Field label="Categoría">
              <select
                value={filters.category}
                onChange={(e) =>
                  setFilters({ ...filters, category: e.target.value })
                }
              >
                <option value="">Todas</option>
                {(categories.data || []).map((c: any) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <TransactionList
            transactions={transactions.data}
            onEdit={setEditing}
            onDelete={async (id) => {
              if (confirm("¿Borrar este movimiento?")) {
                await api(`/finance/transactions/${id}`, token, {
                  method: "DELETE",
                });
                setNotice({ text: "Movimiento eliminado." });
                reload();
              }
            }}
          />
        </section>
      </State>
    </>
  );
}
function BudgetPanel({ token, year, month, categories, budgets, done }: any) {
  const [category, setCategory] = useState(""),
    [amount, setAmount] = useState("");
  return (
    <section>
      <h3>Presupuestos mensuales</h3>
      <form
        className="budget-form"
        onSubmit={async (e) => {
          e.preventDefault();
          await api("/finance/budgets", token, {
            method: "PUT",
            body: JSON.stringify({
              category_id: +category,
              year,
              month,
              amount: +amount,
            }),
          });
          setCategory("");
          setAmount("");
          done();
        }}
      >
        <Field label="Categoría">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            required
          >
            <option value="">Selecciona</option>
            {categories
              .filter((c: any) => c.kind === "expense")
              .map((c: any) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
          </select>
        </Field>
        <Field label="Límite (€)">
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
          />
        </Field>
        <button>Guardar presupuesto</button>
      </form>
      <div className="budget-list">
        {budgets.length ? (
          budgets.map((budget: any) => (
            <div key={budget.id}>
              <span>
                {budget.category}: {euros.format(budget.spent)} de{" "}
                {euros.format(budget.amount)}
              </span>
              <progress max="100" value={Math.min(budget.progress_pct, 100)} />
              <small>{budget.progress_pct}% usado</small>
            </div>
          ))
        ) : (
          <p className="state">Aún no hay presupuestos para este mes.</p>
        )}
      </div>
    </section>
  );
}
const NoticeBox = ({ notice }: { notice: Notice }) =>
  notice ? (
    <p className={`notice ${notice.error ? "error" : ""}`}>{notice.text}</p>
  ) : null;
