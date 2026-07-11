import { useEffect, useState } from "react";
import { getMatches, getLiveMatches } from "./api";
import MatchPicker from "./components/MatchPicker";
import Replay from "./components/Replay";
import Live from "./components/Live";
import LoadingMark from "./components/LoadingMark";

// "2026-07-11T13:30:00" from the api is gmt without the marker
function startsLabel(iso) {
  if (!iso) return "starting soon";
  const d = new Date(iso + "Z");
  return `starts ${d.toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" })}`;
}

export default function App() {
  const [matches, setMatches] = useState(null);
  const [liveMatches, setLiveMatches] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [matchId, setMatchId] = useState(null);
  const [liveId, setLiveId] = useState(null);

  useEffect(() => {
    getMatches().then(setMatches).catch((e) => setLoadError(e.message));
    // live section just doesn't show if the tracker isn't reachable -
    // the replay side of the app shouldn't care
    getLiveMatches().then(setLiveMatches).catch(() => setLiveMatches([]));
  }, []);

  const goHome = () => { setMatchId(null); setLiveId(null); };
  const picking = matchId === null && liveId === null;

  return (
    <div className="app">
      <header className="app-header">
        <button className="brand" onClick={goHome}>
          <svg className="brand-mark" width="20" height="16" viewBox="0 0 20 16">
            <rect className="bar" x="0" y="6" width="4" height="10" rx="1" fill="var(--signal)" />
            <rect className="bar" x="8" y="2" width="4" height="14" rx="1" fill="var(--signal)" />
            <rect className="bar" x="16" y="9" width="4" height="7" rx="1" fill="var(--signal)" />
          </svg>
          <h1>Crick<span>Cast</span></h1>
        </button>
        <p>live/simulated win probability</p>
      </header>

      {loadError && (
        <div className="replay-error">
          can't reach the API ({loadError}) — it might be waking up, try refreshing in a moment.
        </div>
      )}

      {!loadError && matches === null && picking && (
        <div className="replay-loading">
          <LoadingMark />
          loading..please wait this can take a bit.
        </div>
      )}

      {picking && [
        ["live", "live now"],
        ["upcoming", "starting soon"],
        ["finished", "recently finished"],
      ].map(([state, label]) => {
        const group = liveMatches.filter((m) => (m.state || "live") === state);
        if (group.length === 0) return null;
        return (
          <div className={`live-strip strip-${state}`} key={state}>
            <div className="live-strip-label">
              {state === "live" && <span className="live-dot" />}
              {label}
            </div>
            <ul className="live-list">
              {group.map((m) => (
                <li key={m.id}>
                  <button className="picker-row live-row" onClick={() => setLiveId(m.id)}>
                    <span className="picker-teams">{m.teams.join(" v ")}</span>
                    <span className="picker-meta">{m.format} · {m.venue}</span>
                    <span className="picker-winner">
                      {state === "upcoming" ? startsLabel(m.starts) : m.status}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        );
      })}

      {!loadError && matches !== null && picking && (
        <MatchPicker matches={matches} onPick={setMatchId} />
      )}

      {matchId !== null && (
        <Replay matchId={matchId} onBack={goHome} />
      )}

      {liveId !== null && (
        <Live matchId={liveId} onBack={goHome} />
      )}

      <footer className="app-footer">
        <span>
          win probability from a custom ML model · ball-by-ball data via{" "}
          <a href="https://cricsheet.org" target="_blank" rel="noopener">cricsheet.org</a>
        </span>
        <span className="footer-credit">
          built by <a href="https://github.com/Astitva-Rajput" target="_blank" rel="noopener">Astitva</a>
        </span>
      </footer>
    </div>
  );
}
