// falls back to the local FastAPI process when no build-time API URL is set
const API_BASE = `${import.meta.env.VITE_API_BASE || "http://127.0.0.1:8756"}/api`;

async function get(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`${path} -> ${res.status}`);
  }
  return res.json();
}

export function getMatches() {
  return get("/matches");
}

export function getReplay(matchId) {
  return get(`/matches/${matchId}/replay`);
}
