import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { formatNumber, formatTime } from "../i18n/format";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, fetchScores } from "../lib/api";
import type { Score } from "../lib/types";
import { useScopeStore } from "../stores/context";

type Overview = {
  scored_count: number;
  numeric_count: number;
  average: number | null;
  metrics: Array<{ name: string; average: number; count: number }>;
  trend: Array<{ timestamp: string; name: string; value: number }>;
  distribution: Array<{ name: string; count: number }>;
};
const empty: Overview = {
  scored_count: 0,
  numeric_count: 0,
  average: null,
  metrics: [],
  trend: [],
  distribution: [],
};

export default function Scores() {
  const { t } = useTranslation();
  const environmentId = useScopeStore((state) => state.environmentId);
  const registrationId = useScopeStore((state) => state.registrationId);
  const [overview, setOverview] = useState<Overview>(empty);
  const [scores, setScores] = useState<Score[]>([]);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [scoresLoading, setScoresLoading] = useState(true);
  const loading = overviewLoading || scoresLoading;
  useEffect(() => {
    let active = true;
    const params = {
      environment_id: environmentId || undefined,
      registration_id: registrationId || undefined,
    };

    setOverviewLoading(true);
    setScoresLoading(true);
    void api
      .get<Overview>("/public/quality/overview", { params })
      .then((quality) => {
        if (active) setOverview(quality.data);
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) setOverviewLoading(false);
      });
    void fetchScores(params)
      .then((evidence) => {
        if (active) setScores(evidence);
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) setScoresLoading(false);
      });

    return () => {
      active = false;
    };
  }, [environmentId, registrationId]);
  const trend = overview.trend.map((point) => ({
    ...point,
    label: formatTime(point.timestamp),
  }));
  return (
    <section className="quality-console">
      <header className="quality-header">
        <div>
          <p>{t("scores.eyebrow")}</p><h1>{t("scores.title")}</h1><span>{t("scores.subtitle")}</span>
        </div>
        <div className="quality-scope">
          {registrationId
            ? t("scores.verifiedAgentScope").toUpperCase() : t("scores.projectQualityView").toUpperCase()}
        </div>
      </header>
      <div className="quality-kpis">
        <Kpi
          label={t("scores.scoredEvidence")}
          value={overview.scored_count}
          note={t("scores.traceLinkedAnnotations")}
        />
        <Kpi
          label={t("scores.numericCoverage")}
          value={overview.numeric_count}
          note={t("scores.validQuantitativeSamples")}
        />
        <Kpi
          label={t("scores.meanQuality")}
          value={
            overview.average === null ? t("meta.notAvailable") : overview.average.toFixed(2)
          }
          note={t("scores.unweightedAverage")}
        />
        <Kpi
          label={t("scores.metricDefinitions")}
          value={overview.metrics.length}
          note={t("scores.activeObservedDimensions")}
        />
      </div>
      <div className="quality-grid">
        <Panel
          title={t("scores.qualityTrend")} subtitle={t("scores.qualityTrendHint")}
        >
          {trend.length ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={trend}>
                <CartesianGrid stroke="#294038" vertical={false} />
                <XAxis dataKey="label" stroke="#789087" fontSize={10} />
                <YAxis stroke="#789087" fontSize={10} />
                <Tooltip
                  contentStyle={{
                    background: "#10201c",
                    border: "1px solid #365047",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#c7f36b"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "#ff6b35" }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <NoData
              loading={loading}
              label={t("scores.trendEmpty")}
            />
          )}
        </Panel>
        <Panel
          title={t("scores.coverageByMetric")} subtitle={t("scores.coverageHint")}
        >
          {overview.distribution.length ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={overview.distribution}>
                <CartesianGrid stroke="#294038" vertical={false} />
                <XAxis dataKey="name" stroke="#789087" fontSize={10} />
                <YAxis stroke="#789087" fontSize={10} />
                <Tooltip
                  contentStyle={{
                    background: "#10201c",
                    border: "1px solid #365047",
                  }}
                />
                <Bar dataKey="count" fill="#ff6b35" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <NoData
              loading={loading}
              label={t("scores.coverageEmpty")}
            />
          )}
        </Panel>
      </div>
      <section className="quality-table">
        <div className="quality-table-heading">
          <div>
            <p>{t("scores.recentEvidence").toUpperCase()}</p><h2>{t("scores.recentEvidenceHint")}</h2>
          </div>
          <span>{formatNumber(scores.length)}</span>
        </div>
        {scores.length ? (
          <table>
            <thead>
              <tr>
                <th>{t("scores.name")}</th><th>{t("scores.value")}</th><th>{t("scores.source")}</th><th>{t("scores.trace")}</th><th>{t("scores.comment")}</th>
              </tr>
            </thead>
            <tbody>
              {scores.slice(0, 20).map((score) => (
                <tr key={score.id}>
                  <td>
                    <b>{score.name}</b>
                    <small>{score.data_type}</small>
                  </td>
                  <td className="quality-value">
                    {score.string_value ?? score.value ?? t("meta.notAvailable")}
                  </td>
                  <td>
                    <span className="quality-source">{score.source}</span>
                  </td>
                  <td>
                    <a href={`/traces/${score.trace_id}`}>
                      {score.trace_id?.slice(0, 14)}...
                    </a>
                  </td>
                  <td>{score.comment || t("meta.notAvailable")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <NoData
            loading={loading}
            label={t("scores.noScores")}
          />
        )}
      </section>
    </section>
  );
}

function Kpi({
  label,
  value,
  note,
}: {
  label: string;
  value: string | number;
  note: string;
}) {
  return (
    <article>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}
function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <section className="quality-panel">
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
      {children}
    </section>
  );
}
function NoData({ loading, label }: { loading: boolean; label: string }) {
  return (
    <div className="quality-empty">
      {loading ? useTranslation().t("scores.loading") : label}
    </div>
  );
}
