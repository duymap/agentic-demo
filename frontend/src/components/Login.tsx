import { useState, type FormEvent } from "react";
import { api, setToken } from "../api/client";

export default function Login({ onSuccess }: { onSuccess: () => void }) {
  const [username, setUsername] = useState("alice");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const { token } = await api.login(username, password);
      setToken(token);
      onSuccess();
    } catch {
      setError("Invalid username or password");
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-gray-50">
      <form onSubmit={submit} className="w-80 space-y-3 rounded-xl bg-white p-6 shadow">
        <h1 className="text-lg font-semibold">Agentic Support Demo</h1>
        <input className="w-full rounded border p-2" value={username}
          onChange={(e) => setUsername(e.target.value)} placeholder="Username" />
        <input className="w-full rounded border p-2" type="password" value={password}
          onChange={(e) => setPassword(e.target.value)} placeholder="Password" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button className="w-full rounded bg-blue-600 p-2 text-white">Log in</button>
      </form>
    </div>
  );
}
