const W = 720;
const H = 240;
const PAD_L = 34;
const PAD_R = 12;
const PAD_T = 16;
const PAD_B = 26;

const plotW = W - PAD_L - PAD_R;
const plotH = H - PAD_T - PAD_B;

// innings 1 is overs 0-19 on the x axis, innings 2 just continues at 20-39
function xFor(innings, over) {
  const slot = innings === 1 ? over : over + 20;
  return PAD_L + (slot / 39) * plotW;
}

function yFor(pct) {
  return PAD_T + (1 - pct / 100) * plotH;
}

export default function ProbChart({ overs, team1, team2, team1Color, team2Color, live }) {
  if (overs.length === 0) {
    return <div className="chart-empty">waiting for first over...</div>;
  }

  const points = overs.map((o) => {
    const team1Pct = o.innings === 1
      ? o.win_prob_batting_team * 100
      : (1 - o.win_prob_batting_team) * 100;
    return { innings: o.innings, over: o.over, team1Pct };
  });

  const linePath = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${xFor(p.innings, p.over)} ${yFor(p.team1Pct)}`)
    .join(" ");

  const fillPath =
    `${linePath} L ${xFor(points.at(-1).innings, points.at(-1).over)} ${yFor(50)} ` +
    points
      .slice()
      .reverse()
      .map((p) => `L ${xFor(p.innings, p.over)} ${yFor(50)}`)
      .join(" ") +
    " Z";

  const last = points.at(-1);
  const leaderTeam = last.team1Pct >= 50 ? team1 : team2;
  const leaderPct = last.team1Pct >= 50 ? last.team1Pct : 100 - last.team1Pct;

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="prob-chart" preserveAspectRatio="none">
        {/* gridlines */}
        {[0, 25, 50, 75, 100].map((p) => (
          <line
            key={p}
            x1={PAD_L} x2={W - PAD_R}
            y1={yFor(p)} y2={yFor(p)}
            className={p === 50 ? "grid-mid" : "grid-line"}
          />
        ))}

        {/* innings divider */}
        <line x1={xFor(2, 0)} x2={xFor(2, 0)} y1={PAD_T} y2={H - PAD_B} className="innings-divider" />

        <path d={fillPath} className="chart-fill" fill={last.team1Pct >= 50 ? team1Color : team2Color} />
        <path d={linePath} className="chart-line" />

        {/* pulses while playing */}
        {live && (
          <circle
            cx={xFor(last.innings, last.over)}
            cy={yFor(last.team1Pct)}
            r="4.5"
            className="chart-dot-pulse"
          />
        )}
        <circle
          cx={xFor(last.innings, last.over)}
          cy={yFor(last.team1Pct)}
          r="4.5"
          className="chart-dot"
        />

        {/* axis labels */}
        <text x={PAD_L} y={H - 6} className="axis-label">Powerplay</text>
        <text x={xFor(1, 19)} y={H - 6} className="axis-label" textAnchor="end">Inn 1</text>
        <text x={xFor(2, 0)} y={H - 6} className="axis-label" textAnchor="middle">Inn 2</text>
        <text x={W - PAD_R} y={H - 6} className="axis-label" textAnchor="end">Death</text>

        <text x={PAD_L - 6} y={yFor(100) + 4} className="axis-label" textAnchor="end">100</text>
        <text x={PAD_L - 6} y={yFor(50) + 4} className="axis-label" textAnchor="end">50</text>
        <text x={PAD_L - 6} y={yFor(0) + 4} className="axis-label" textAnchor="end">0</text>
      </svg>

      <div className="chart-readout">
        <span className="chart-readout-team">{leaderTeam}</span>
        <span className="chart-readout-pct">{leaderPct.toFixed(1)}%</span>
        <span className="chart-readout-tail">to win</span>
      </div>
    </div>
  );
}
