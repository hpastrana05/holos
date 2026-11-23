import { Bar, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export type Forecast = {
  location: string;
  time: string;
  temperature: number | null;
  apparent_temperature: number | null;
  weather_code: number | null;
  wind: number | null;
  uv: number | null;
  maximum: number | null;
  minimum: number | null;
  sunrise: string | null;
  sunset: string | null;
  summary: string;
  stale: boolean;
  hourly: { time: string; temperature: number | null; precipitation_probability: number | null }[];
};

function weatherIcon(code: number | null) {
  if (code === null) return "—";
  if (code === 0) return "☀";
  if (code <= 2) return "⛅";
  if (code <= 3) return "☁";
  if (code === 45 || code === 48) return "🌫";
  if ([71, 73, 75, 77, 85, 86].includes(code)) return "❄";
  if (code >= 95) return "⛈";
  return "🌧";
}

const number = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 });
const value = (amount: number | null, unit = "") => amount === null ? "—" : `${number.format(amount)}${unit}`;
const time = (date: string | null) => date?.slice(11, 16) || "—";

export default function WeatherScreen({ forecast, error }: { forecast: Forecast | null; error: string }) {
  if (!forecast) return <section className="screen-weather section-weather">
    <h2>Tiempo de hoy</h2>
    <p className="state" role="status">{error || "Cargando el tiempo…"}</p>
  </section>;
  const { location, temperature, maximum, minimum, apparent_temperature, weather_code,
    hourly, wind, uv, sunrise, sunset, summary, stale } = forecast;
  return <section className="screen-weather section-weather" aria-label="Tiempo de hoy">
    <div className="weather-current">
      <h2>Tiempo en {location}</h2>
      <p className="weather-temperature"><span aria-hidden="true">{weatherIcon(weather_code)}</span> {value(temperature, " °C")}</p>
      <p>Máx. {value(maximum, "°")} · Mín. {value(minimum, "°")} · Sensación {value(apparent_temperature, "°")}</p>
      <p className="state">{summary}</p>
      <dl className="weather-details">
        <div><dt>Amanecer</dt><dd>{time(sunrise)}</dd></div>
        <div><dt>Atardecer</dt><dd>{time(sunset)}</dd></div>
        <div><dt>Viento</dt><dd>{value(wind, " km/h")}</dd></div>
        <div><dt>UV</dt><dd>{value(uv)}</dd></div>
      </dl>
    </div>
    <div className="weather-hourly">
      <h3>Previsión por horas</h3>
      {hourly.length ? <div className="weather-chart" aria-label="Temperatura y probabilidad de precipitación por hora">
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <ComposedChart data={hourly} margin={{ left: 0, right: 0, top: 5, bottom: 0 }}>
            <XAxis dataKey="time" tickFormatter={time} minTickGap={19} tick={{ fontSize: 10 }} height={20} />
            <YAxis yAxisId="temperature" unit="°" domain={["auto", "auto"]} width={31} tick={{ fontSize: 10 }} />
            <YAxis yAxisId="rain" orientation="right" unit="%" domain={[0, 100]} width={33} tick={{ fontSize: 10 }} />
            <Tooltip labelFormatter={label => time(typeof label === "string" ? label : null)} />
            <Bar yAxisId="rain" dataKey="precipitation_probability" name="Precipitación (%)" fill="var(--weather-rain)" isAnimationActive={false} />
            <Line yAxisId="temperature" dataKey="temperature" name="Temperatura (°C)" stroke="var(--weather-temperature)" strokeWidth={2} dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div> : <p className="state">Sin previsión horaria.</p>}
      <p className="weather-legend"><span>Temperatura</span><span>Probabilidad de precipitación</span></p>
    </div>
    <footer>
      <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Datos meteorológicos de Open-Meteo.com</a>
      {(stale || error) && <p className="error" role="status">Sin actualización. Datos de {forecast.time.slice(8, 10)}/{forecast.time.slice(5, 7)} a las {time(forecast.time)}.</p>}
    </footer>
  </section>;
}
