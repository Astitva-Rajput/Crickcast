import { useEffect, useState } from "react";
import { getReplay } from "../api";
import ProbChart from "./ProbChart";

const SPEEDS = [
  { label: "1x", ms: 850 },
  { label: "2x", ms: 420 },
  { label: "4x", ms: 200 },
];

// clay vs moss, kept separate from the ochre used for buttons/focus/playhead
const TEAM1_COLOR = "#c1652f";
const TEAM2_COLOR = "#7c8a52";

function inningsSummary(rows) {
  if (rows.length === 0) return null;
  const last = rows.at(-1);
  return {
    team: last.batting_team,
    runs: last.cum_runs,
    wickets: last.wickets_fallen,
    oversBowled: last.over + 1,
  };
}

export default function Replay({ matchId, onBack }) {
  const [data, setData] = useState(null);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speedMs, setSpeedMs] = useState(SPEEDS[0].ms);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setData(null);
    setIndex(0);
    setPlaying(false);
    setErr(null);

    getReplay(matchId)
      .then(setData)
      .catch((e) => setErr(e.message));
  }, [matchId]);

  // using a timeout chain instead of setInterval so changing speed
  // mid-playback doesnt fight a stale timer
  useEffect(() => {
    if (!playing || !data) return;
    if (index >= data.overs.length - 1) {
      setPlaying(false);
      return;
    }
    const id = setTimeout(() => setIndex((i) => i + 1), speedMs);
    return () => clearTimeout(id);
  }, [playing, index, speedMs, data]);

  if (err) {
    return (
      <div className="replay-error">
        couldn't load that match ({err}) — the API might be waking up, try again in a moment.
        <button className="link-btn" onClick={onBack}>go back</button>
      </div>
    );
  }

  if (!data) {
    return <div className="replay-loading">loading replay…</div>;
  }

  const visible = data.overs.slice(0, index + 1);
  const current = visible.at(-1);
  const inn1 = inningsSummary(visible.filter((o) => o.innings === 1));
  const inn2 = inningsSummary(visible.filter((o) => o.innings === 2));
  const atEnd = index >= data.overs.length - 1;

  return (
    <div className="replay">
      <div className="replay-header">
        <button className="link-btn" onClick={onBack}>← other matches</button>
        <div className="replay-venue">{data.venue} · {data.season}</div>
      </div>

      <div className="scoreboard">
        <div className={`scoreboard-team ${current.batting_team === data.team1 ? "batting" : ""}`}>
          <span className="team-swatch" style={{ background: TEAM1_COLOR }} />
          <span className="team-name">{data.team1}</span>
          <span className="team-score">
            {inn1 ? `${inn1.runs}/${inn1.wickets}` : "-"}
            <small>{inn1 ? ` (${inn1.oversBowled})` : ""}</small>
          </span>
        </div>

        <div className={`scoreboard-team ${current.batting_team === data.team2 ? "batting" : ""}`}>
          <span className="team-swatch" style={{ background: TEAM2_COLOR }} />
          <span className="team-name">{data.team2}</span>
          {inn2 ? (
            <span className="team-score">
              {`${inn2.runs}/${inn2.wickets}`}
              <small>{` (${inn2.oversBowled})`}</small>
            </span>
          ) : (
            <span className="team-score-pending">yet to bat</span>
          )}
        </div>
      </div>

      <ProbChart
        overs={visible}
        team1={data.team1}
        team2={data.team2}
        team1Color={TEAM1_COLOR}
        team2Color={TEAM2_COLOR}
        live={playing}
      />

      <div className="over-strip">
        <div className="over-strip-meta">
          <span className={`phase-badge phase-${current.phase}`}>{current.phase}</span>
          <span>innings {current.innings} · over {current.over + 1}</span>
          <span>CRR {current.crr}</span>
          {current.rrr != null && <span>RRR {current.rrr}</span>}
        </div>
        <div className="ball-ticker">
          {current.balls.map((b, i) => (
            <span key={i} className={`ball ball-${b === "W" ? "wicket" : /^[46]$/.test(b) ? "boundary" : "plain"}`}>
              {b}
            </span>
          ))}
        </div>
      </div>

      <div className="controls">
        <button
          className="play-btn"
          onClick={() => {
            if (atEnd) {
              setIndex(0);
              setPlaying(true);
            } else {
              setPlaying((p) => !p);
            }
          }}
        >
          {playing ? "pause" : atEnd ? "replay" : "play"}
        </button>

        <input
          type="range"
          min={0}
          max={data.overs.length - 1}
          value={index}
          onChange={(e) => {
            setPlaying(false);
            setIndex(Number(e.target.value));
          }}
          className="scrub"
        />

        <div className="speed-group">
          {SPEEDS.map((s) => (
            <button
              key={s.label}
              className={`speed-btn ${speedMs === s.ms ? "active" : ""}`}
              onClick={() => setSpeedMs(s.ms)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {atEnd && (
        <div className="result-banner">{data.winner} won the match</div>
      )}
    </div>
  );
}
