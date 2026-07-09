import { useEffect, useState } from "react";
import { getLive } from "../api";
import ProbChart from "./ProbChart";
import LoadingMark from "./LoadingMark";

// how often the frontend asks our backend - the backend only hits
// cricketdata.org once every 150s no matter what, so this just controls
// how quickly fresh data shows up once it lands
const REFRESH_MS = 30000;

// clay vs moss, kept separate from the ochre used for buttons/focus/playhead
const TEAM1_COLOR = "#c1652f";
const TEAM2_COLOR = "#7c8a52";

function inningsSummary(rows) {
  if (rows.length === 0) return null;
  const last = rows.at(-1);
  return {
    runs: last.cum_runs,
    wickets: last.wickets_fallen,
    oversBowled: last.over + 1,
  };
}

export default function Live({ matchId, onBack }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setData(null);
    setErr(null);

    let stopped = false;
    const load = () =>
      getLive(matchId)
        .then((d) => { if (!stopped) { setData(d); setErr(null); } })
        .catch((e) => { if (!stopped) setErr(e.message); });

    load();
    const id = setInterval(load, REFRESH_MS);
    return () => { stopped = true; clearInterval(id); };
  }, [matchId]);

  if (err && !data) {
    return (
      <div className="replay-error">
        couldn't reach the live tracker ({err})
        <button className="link-btn" onClick={onBack}>go back</button>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="replay-loading">
        <LoadingMark />
        tuning in…
      </div>
    );
  }

  const overs = data.overs;
  const current = overs.at(-1);
  const inn1 = inningsSummary(overs.filter((o) => o.innings === 1));
  const inn2 = inningsSummary(overs.filter((o) => o.innings === 2));
  const battingTeam = current
    ? (current.innings === 1 ? data.team1 : data.team2)
    : data.team1;

  return (
    <div className="replay">
      <div className="replay-header">
        <button className="link-btn" onClick={onBack}>← other matches</button>
        <div className="replay-venue">{data.info.venue}</div>
      </div>

      <div className="live-banner">
        {!data.done && <span className="live-dot" />}
        <span className="live-banner-status">
          {data.done ? data.info.status : `${data.info.status || "in progress"} · updates every couple of minutes`}
        </span>
      </div>

      <div className="scoreboard">
        <div className={`scoreboard-team ${!data.done && battingTeam === data.team1 ? "batting" : ""}`}>
          <span className="team-swatch" style={{ background: TEAM1_COLOR }} />
          <span className="team-name">{data.team1}</span>
          {inn1 ? (
            <span className="team-score">
              {`${inn1.runs}/${inn1.wickets}`}
              <small>{` (${inn1.oversBowled})`}</small>
            </span>
          ) : (
            <span className="team-score-pending">yet to bat</span>
          )}
        </div>

        <div className={`scoreboard-team ${!data.done && battingTeam === data.team2 ? "batting" : ""}`}>
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
        overs={overs}
        team1={data.team1}
        team2={data.team2}
        team1Color={TEAM1_COLOR}
        team2Color={TEAM2_COLOR}
        live={!data.done}
        totalOvers={data.total_overs}
      />

      {current && (
        <div className="over-strip">
          <div className="over-strip-meta">
            <span>innings {current.innings} · over {current.over + 1}</span>
            <span>CRR {current.crr}</span>
            {current.rrr != null && <span>RRR {current.rrr}</span>}
          </div>
        </div>
      )}

      {data.done && (
        <div className="result-banner">{data.info.status}</div>
      )}
    </div>
  );
}
