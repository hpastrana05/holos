import { useState } from "react";
import { api, Field } from "./shared";

export default function Login({ onLogin }: { onLogin: (value: string) => void }) {
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [error, setError] = useState("");
  return (
    <main className="login">
      <h1>Holos</h1>
      <p>Tu hogar, de un vistazo.</p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            onLogin(
              (
                await api("/auth/login", "", {
                  method: "POST",
                  body: JSON.stringify({ email, password }),
                })
              ).access_token,
            );
          } catch {
            setError("Correo o contraseña incorrectos");
          }
        }}
      >
        <Field label="Correo">
          <input
            type="email"
            placeholder="tu@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </Field>
        <Field label="Contraseña">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
        <button>Entrar</button>
        {error && <p className="error">{error}</p>}
      </form>
    </main>
  );
}

