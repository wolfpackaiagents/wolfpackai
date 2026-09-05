import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  createMeshDefinition,
  createMeshEnvironment,
  createMeshRegistration,
  deleteMeshEnvironment,
  deleteMeshRegistration,
  fetchMeshCatalog,
  fetchMeshGraph,
  fetchMeshInteractions,
  updateMeshEnvironment,
  updateMeshRegistration,
} from "../lib/api";
import type {
  MeshCatalog,
  MeshDefinition,
  MeshEnvironment,
  MeshGraph,
  MeshInteraction,
  MeshKind,
} from "../lib/types";
import ContextCombobox from "../components/ContextCombobox";
import ConfirmationDialog from "../components/ConfirmationDialog";

const emptyCatalog: MeshCatalog = {
  summary: { environments: 0, registrations: 0, active_registrations: 0 },
  environments: [],
  definitions: [],
};
const emptyGraph: MeshGraph = { nodes: [], edges: [] };

export default function Mesh() {
  const { t } = useTranslation();
  const [catalog, setCatalog] = useState<MeshCatalog>(emptyCatalog);
  const [graph, setGraph] = useState<MeshGraph>(emptyGraph);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [graphLoading, setGraphLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showEnvironment, setShowEnvironment] = useState(false);
  const [showDefinition, setShowDefinition] = useState(false);
  const [editingEnvironment, setEditingEnvironment] = useState<MeshEnvironment | null>(null);
  const [confirmation, setConfirmation] = useState<{ description: string; onConfirm: () => void } | null>(null);
  const [graphView, setGraphView] = useState<"ledger" | "flow">("ledger");
  const [selectedEdge, setSelectedEdge] = useState<MeshGraph["edges"][number] | null>(null);
  const [selectedInteractions, setSelectedInteractions] = useState<MeshInteraction[]>([]);
  const [interactionLoading, setInteractionLoading] = useState(false);

  async function refresh() {
    setCatalogLoading(true);
    setGraphLoading(true);
    setError(null);

    const catalogRequest = fetchMeshCatalog()
      .then(setCatalog)
      .catch((reason) => {
        setError(t("mesh.loadInventoryFailed", { error: String(reason) }));
      })
      .finally(() => setCatalogLoading(false));
    const graphRequest = fetchMeshGraph()
      .then(setGraph)
      .catch((reason) => {
        setError((current) =>
          current
            ? `${current} ${t("mesh.loadGraphFailed", { error: String(reason) })}`
            : t("mesh.loadGraphFailed", { error: String(reason) }),
        );
      })
      .finally(() => setGraphLoading(false));

    await Promise.allSettled([catalogRequest, graphRequest]);
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function register(
    environment: MeshEnvironment,
    definition: MeshDefinition,
  ) {
    try {
      await createMeshRegistration({
        environment_id: environment.id,
        definition_id: definition.id,
      });
      setNotice(t("mesh.registeredIn", { definition: definition.name, environment: environment.name }));
      await refresh();
    } catch (reason) {
      setError(String(reason));
    }
  }

  async function setRegistrationEnabled(registrationId: string, enabled: boolean) {
    try {
      await updateMeshRegistration(registrationId, { enabled });
      setNotice(t(enabled ? "mesh.registrationEnabled" : "mesh.registrationDisabled"));
      await refresh();
    } catch (reason) { setError(String(reason)); }
  }

  async function removeRegistration(registrationId: string) {
    try {
      await deleteMeshRegistration(registrationId);
      setNotice(t("mesh.registrationDeleted"));
      await refresh();
    } catch (reason) { setError(String(reason)); }
  }

  async function removeEnvironment(environment: MeshEnvironment) {
    try {
      await deleteMeshEnvironment(environment.id);
      setNotice(t("mesh.environmentDeleted"));
      await refresh();
    } catch (reason) { setError(String(reason)); }
  }

  async function selectEdge(edge: MeshGraph["edges"][number]) {
    setSelectedEdge(edge);
    setSelectedInteractions([]);
    setInteractionLoading(true);
    try {
      const interactions = await fetchMeshInteractions();
      setSelectedInteractions(interactions.filter((interaction) =>
        interaction.source === edge.source &&
        interaction.target === edge.target &&
        interaction.interaction_type === edge.interaction_type &&
        interaction.operation === edge.operation &&
        interaction.tool_name === edge.tool_name,
      ));
    } catch (reason) {
      setSelectedInteractions([]);
      setError(t("meshFlow.loadInteractionsFailed", { error: String(reason) }));
    } finally {
      setInteractionLoading(false);
    }
  }

  return (
    <div className="mesh-console">
      <section className="mesh-hero">
        <div className="mesh-hero-grid" />
        <div className="relative z-[1] max-w-3xl">
          <div className="mesh-eyebrow">
            <span className="mesh-pulse" /> {t("mesh.eyebrow").toUpperCase()}
          </div>
          <h1>
            {t("mesh.title")}
            <br />
            <span>{t("mesh.titleAccent")}</span>
          </h1>
          <p>
            {t("mesh.subtitle")}
          </p>
        </div>
        <div className="mesh-hero-actions relative z-[1]">
          <button
            className="mesh-primary"
            onClick={() => setShowDefinition(true)}
          >
            {t("mesh.registerArtifact")} <span>+</span>
          </button>
          <button
            className="mesh-secondary"
            onClick={() => setShowEnvironment(true)}
          >
            {t("mesh.newEnvironment")}
          </button>
        </div>
        <div className="mesh-kpis relative z-[1]">
          <Kpi
            label={t("mesh.controlledEnvironments")}
            value={catalog.summary.environments}
            hint={t("mesh.isolatedReleaseContexts")}
          />
          <Kpi
            label={t("mesh.liveRegistrations")}
            value={catalog.summary.active_registrations}
            hint={t("mesh.versionBindings", { count: catalog.summary.registrations })}
          />
          <Kpi
            label={t("mesh.inventoryArtifacts")}
            value={catalog.definitions.length}
            hint={t("mesh.artifactHint")}
          />
        </div>
      </section>

      {error && <div className="mesh-feedback is-error">{error}</div>}
      {notice && <div className="mesh-feedback">{notice}</div>}

      <section className="mesh-section-heading">
        <div>
          <div className="mesh-section-index">{t("mesh.environmentsIndex").toUpperCase()}</div><h2>{t("mesh.releaseTopology")}</h2>
        </div>
        <button
          className="mesh-text-button"
          onClick={() => setShowEnvironment(true)}
        >
          {t("mesh.manageEnvironments")}
        </button>
      </section>
      <section className="mesh-environments">
        {catalogLoading ? (
          <Loading />
        ) : catalog.environments.length === 0 ? (
          <Empty
            label={t("mesh.noEnvironments")} action={t("mesh.createFirstEnvironment")}
            onClick={() => setShowEnvironment(true)}
          />
        ) : (
          catalog.environments.map((environment) => (
            <article className="mesh-environment-card" key={environment.id}>
              <div className="mesh-card-top">
                <div className="mesh-env-icon">
                  {environment.slug.slice(0, 1).toUpperCase()}
                </div>
                <span
                  className={`mesh-status ${environment.status === "active" ? "" : "is-muted"}`}
                >
                  {environment.status}
                </span>
              </div>
              <h3>{environment.name}</h3>
              <p>
                {environment.description ||
                  t("mesh.defaultEnvironmentDescription")}
              </p>
              <div className="mesh-env-stats">
                <span>
                  <b>{environment.registrations.length}</b> {t("mesh.registrations")}
                </span>
                <span>
                  <b>
                    {
                      environment.registrations.filter(
                        (registration) =>
                          registration.definition_kind === "agent",
                      ).length
                    }
                  </b>{" "}
                  {t("mesh.agents")}
                </span>
              </div>
              <div className="mesh-card-footer">
                <code>{environment.slug}</code>
                <div className="mesh-card-actions">
                  <button type="button" onClick={() => setEditingEnvironment(environment)}>{t("mesh.edit")}</button>
                  <button type="button" className="is-danger" onClick={() => setConfirmation({ description: t("mesh.confirmDeleteEnvironment", { environment: environment.name }), onConfirm: () => void removeEnvironment(environment) })}>{t("mesh.delete")}</button>
                </div>
              </div>
              {environment.registrations.length > 0 && <div className="mesh-registration-list">
                {environment.registrations.map((registration) => <div key={registration.id} className="mesh-registration">
                  <span>{registration.definition_name} <i className={`health-badge health-${registration.health_status}`}>{t(`mesh.health.${registration.health_status}`)} · {t("mesh.replicaCount", { count: registration.online_replicas })}</i></span>
                  <div>
                    <button type="button" onClick={() => void setRegistrationEnabled(registration.id, !registration.enabled)}>{t(registration.enabled ? "mesh.disable" : "mesh.enable")}</button>
                    <button type="button" className="is-danger" onClick={() => setConfirmation({ description: t("mesh.confirmDeleteRegistration"), onConfirm: () => void removeRegistration(registration.id) })}>{t("mesh.delete")}</button>
                  </div>
                </div>)}
              </div>}
            </article>
          ))
        )}
      </section>

      <section className="mesh-section-heading mesh-artifacts-heading">
        <div>
          <div className="mesh-section-index">{t("mesh.communicationIndex").toUpperCase()}</div><h2>{t("mesh.interactionGraph")}</h2>
        </div>
        <div className="mesh-graph-summary">
          <span>{graph.nodes.length} {t("mesh.nodes")}</span><span>{graph.edges.length} {t("mesh.edges")}</span>
        </div>
      </section>
      <section className="mesh-graph">
        {graphLoading ? (
          <Loading />
        ) : graph.nodes.length === 0 ? (
          <div className="mesh-empty">
            <strong>{t("mesh.noCommunication")}</strong>
          </div>
        ) : (
          <>
            <div className="mesh-graph-toolbar" role="tablist" aria-label={t("meshFlow.graphViews")}>
              <button type="button" role="tab" aria-selected={graphView === "ledger"} className={graphView === "ledger" ? "is-active" : ""} onClick={() => setGraphView("ledger")}>{t("meshFlow.ledgerView")}</button>
              <button type="button" role="tab" aria-selected={graphView === "flow"} className={graphView === "flow" ? "is-active" : ""} onClick={() => setGraphView("flow")}>{t("meshFlow.flowView")}</button>
            </div>
            {graphView === "ledger" ? (
              <div className="mesh-graph-ledger">
                <div className="mesh-graph-nodes">{graph.nodes.map((node) => <code key={node.id}>{node.label}</code>)}</div>
                <div className="mesh-graph-edges">{graph.edges.map((edge) => <button type="button" className={`mesh-graph-edge ${edgeKey(edge) === edgeKey(selectedEdge) ? "is-selected" : ""}`} key={edgeKey(edge)} onClick={() => void selectEdge(edge)}><code>{edge.source_display_name || edge.source}</code><b>→</b><code>{edge.target_display_name || edge.target}</code><span>{interactionLabel(edge)}</span><small>{edge.count} {t("mesh.observed")}</small></button>)}</div>
              </div>
            ) : <FlowGraph graph={graph} selectedEdge={selectedEdge} onSelect={selectEdge} />}
            {selectedEdge && <EdgeDetails edge={selectedEdge} interactions={selectedInteractions} loading={interactionLoading} />}
          </>
        )}
      </section>

      <section className="mesh-section-heading mesh-artifacts-heading">
        <div>
          <div className="mesh-section-index">{t("mesh.registryIndex").toUpperCase()}</div><h2>{t("mesh.runtimeInventory")}</h2>
        </div>
        <div className="mesh-legend">
          <span>
            <i className="agent" />
            {t("mesh.agent")}
          </span>
          <span>
            <i className="team" />
            {t("mesh.team")}
          </span>
          <span>
            <i className="workflow" />
            {t("mesh.workflow")}
          </span>
        </div>
      </section>
      <section className="mesh-inventory">
        <div className="mesh-inventory-header">
          <span>{t("mesh.artifact")}</span><span>{t("mesh.type")}</span><span>{t("mesh.version")}</span><span>{t("mesh.deploymentCoverage")}</span>
          <span />
        </div>
        {catalogLoading ? (
          <Loading />
        ) : catalog.definitions.length === 0 ? (
          <Empty
            label={t("mesh.noEnvironments")}
            action={t("mesh.registerArtifact")}
            onClick={() => setShowDefinition(true)}
          />
        ) : (
          catalog.definitions.map((definition) => {
            const targets = catalog.environments.filter((environment) =>
              environment.registrations.some(
                (registration) => registration.definition_id === definition.id,
              ),
            );
            return (
              <div className="mesh-inventory-row" key={definition.id}>
                <div>
                  <div className="mesh-artifact-name">
                    <span className={`mesh-kind ${definition.kind}`}>
                      {kindGlyph(definition.kind)}
                    </span>
                    <strong>{definition.name}</strong>
                  </div>
                  <code>{definition.key}</code>
                  {typeof definition.summary.memory_profile === "string" && (
                    <span className="mesh-memory-profile">
                      memory: {definition.summary.memory_profile}
                    </span>
                  )}
                </div>
                <span className={`mesh-type ${definition.kind}`}>
                  {definition.kind}
                </span>
                <code className="mesh-version">v{definition.version}</code>
                <div className="mesh-coverage">
                  {targets.length ? (
                    targets.map((target) => {
                      const registration = target.registrations.find((item) => item.definition_id === definition.id)!;
                      return <span key={target.id} className={`health-${registration.health_status}`}>{target.slug} <i className="health-badge">{t(`mesh.health.${registration.health_status}`)} · {t("mesh.replicaCount", { count: registration.online_replicas })}</i></span>;
                    })
                  ) : (
                    <em>{t("mesh.unassigned")}</em>
                  )}
                </div>
                <div className="mesh-row-actions">
                  {catalog.environments
                    .filter(
                      (environment) =>
                        !targets.some((target) => target.id === environment.id),
                    )
                    .slice(0, 1)
                    .map((environment) => (
                      <button
                        key={environment.id}
                        onClick={() => register(environment, definition)}
                      >
                        {t("mesh.registerTo", { environment: environment.slug })}
                      </button>
                    ))}
                </div>
              </div>
            );
          })
        )}
      </section>

      {showEnvironment && (
        <EnvironmentDialog
          onClose={() => setShowEnvironment(false)}
          onCreated={async () => {
            setShowEnvironment(false);
            setNotice(t("mesh.environmentCreated"));
            await refresh();
          }}
        />
      )}
      {showDefinition && (
        <DefinitionDialog
          onClose={() => setShowDefinition(false)}
          onCreated={async () => {
            setShowDefinition(false);
            setNotice(t("mesh.artifactRegistered"));
            await refresh();
          }}
        />
      )}
      {editingEnvironment && <EnvironmentDialog environment={editingEnvironment} onClose={() => setEditingEnvironment(null)} onCreated={async () => { setEditingEnvironment(null); setNotice(t("mesh.environmentUpdated")); await refresh(); }} />}
      {confirmation && <ConfirmationDialog title={t("meta.confirmDestructiveAction")} description={confirmation.description} cancelLabel={t("meta.cancel")} confirmLabel={t("mesh.delete")} onCancel={() => setConfirmation(null)} onConfirm={() => { const action = confirmation.onConfirm; setConfirmation(null); action(); }} />}
    </div>
  );
}

function edgeKey(edge: MeshGraph["edges"][number] | null) {
  return edge ? `${edge.source}-${edge.target}-${edge.interaction_type}-${edge.operation || ""}-${edge.tool_name || ""}` : "";
}

function interactionLabel(edge: Pick<MeshGraph["edges"][number], "interaction_type" | "operation" | "tool_name">) {
  return [edge.interaction_type, edge.operation, edge.tool_name && `tool: ${edge.tool_name}`].filter(Boolean).join(" · ");
}

function FlowGraph({ graph, selectedEdge, onSelect }: { graph: MeshGraph; selectedEdge: MeshGraph["edges"][number] | null; onSelect: (edge: MeshGraph["edges"][number]) => void }) {
  const { t } = useTranslation();
  const layout = flowLayout(graph);
  return <div className="mesh-flow-scroll"><svg className="mesh-flow" viewBox={`0 0 ${layout.width} ${layout.height}`} role="list" aria-label={t("meshFlow.flowView")}>
    <defs><marker id="mesh-flow-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M 0 0 L 8 4 L 0 8 z" /></marker></defs>
    {layout.lanes.map((lane, index) => <text className="mesh-flow-lane" key={index} x={lane.x} y="24">{t("meshFlow.lane", { count: index + 1 })}</text>)}
    {graph.edges.map((edge) => {
      const source = layout.nodes.get(edge.source)!;
      const target = layout.nodes.get(edge.target)!;
      const midX = (source.x + target.x + 138) / 2;
      const selected = edgeKey(edge) === edgeKey(selectedEdge);
      const path = `M ${source.x + 138} ${source.y + 26} C ${midX} ${source.y + 26}, ${midX} ${target.y + 26}, ${target.x} ${target.y + 26}`;
      return <g key={edgeKey(edge)} role="button" tabIndex={0} aria-pressed={selected} aria-label={`${edge.source_display_name || edge.source} to ${edge.target_display_name || edge.target}, ${edge.count} ${interactionLabel(edge)}`} className={`mesh-flow-connector ${selected ? "is-selected" : ""}`} onClick={() => onSelect(edge)} onKeyDown={(event) => (event.key === "Enter" || event.key === " ") && onSelect(edge)}><path className="mesh-flow-hit" d={path} /><path className="mesh-flow-path" markerEnd="url(#mesh-flow-arrow)" d={path} /><text className="mesh-flow-edge-label" x={midX} y={(source.y + target.y) / 2 + 18}>{edge.count} · {interactionLabel(edge)}</text></g>;
    })}
    {[...layout.nodes.entries()].map(([id, node]) => <g key={id} className="mesh-flow-node" transform={`translate(${node.x} ${node.y})`}><rect width="138" height="52" rx="7" /><text x="12" y="22">{node.label}</text><text className="mesh-flow-node-id" x="12" y="39">{id}</text></g>)}
  </svg></div>;
}

function EdgeDetails({ edge, interactions, loading }: { edge: MeshGraph["edges"][number]; interactions: MeshInteraction[]; loading: boolean }) {
  const { t } = useTranslation();
  const traces = [...new Set(interactions.map((interaction) => interaction.trace_id).filter((traceId): traceId is string => Boolean(traceId)))];
  return <div className="mesh-edge-details"><div><span>{t("meshFlow.selectedFlow")}</span><strong>{edge.source_display_name || edge.source} <b>→</b> {edge.target_display_name || edge.target}</strong><small>{edge.count} {t("mesh.observed")} · {interactionLabel(edge)}</small></div><div className="mesh-edge-traces"><span>{t("meshFlow.traceEvidence")}</span>{loading ? <small>{t("meshFlow.loadingInteractions")}</small> : traces.length ? traces.map((traceId) => <Link key={traceId} to={`/traces/${traceId}`}>{traceId.slice(0, 12)}...</Link>) : <small>{t("meshFlow.noTraceEvidence")}</small>}</div></div>;
}

function flowLayout(graph: MeshGraph) {
  const pending = new Set(graph.nodes.map((node) => node.id));
  const levelByNode = new Map<string, number>();
  const predecessors = new Map(graph.nodes.map((node) => [node.id, graph.edges.filter((edge) => edge.target === node.id).map((edge) => edge.source)]));
  let level = 0;
  while (pending.size) {
    let ready = [...pending].filter((id) => (predecessors.get(id) ?? []).every((source) => !pending.has(source)));
    if (!ready.length) ready = [[...pending].sort()[0]];
    ready.sort().forEach((id) => { levelByNode.set(id, level); pending.delete(id); });
    level += 1;
  }
  const laneCount = Math.max(...levelByNode.values(), 0) + 1;
  const lanes = Array.from({ length: laneCount }, (_, index) => ({ x: 30 + index * 210 }));
  const nodes = new Map<string, { x: number; y: number; label: string }>();
  lanes.forEach((lane, index) => graph.nodes.filter((node) => levelByNode.get(node.id) === index).sort((a, b) => a.label.localeCompare(b.label)).forEach((node, row) => nodes.set(node.id, { x: lane.x, y: 48 + row * 82, label: node.label })));
  return { lanes, nodes, width: Math.max(720, laneCount * 210 + 30), height: Math.max(170, ...[...nodes.values()].map((node) => node.y + 82)) };
}

function Kpi({
  label,
  value,
  hint,
}: {
  label: string;
  value: number;
  hint: string;
}) {
  return (
    <div>
      <span>{label}</span>
      <strong>{String(value).padStart(2, "0")}</strong>
      <small>{hint}</small>
    </div>
  );
}
function Loading() {
  return (
    <div className="mesh-loading">
      Synchronizing Mesh inventory<span>.</span>
      <span>.</span>
      <span>.</span>
    </div>
  );
}
function Empty({
  label,
  action,
  onClick,
}: {
  label: string;
  action: string;
  onClick: () => void;
}) {
  return (
    <div className="mesh-empty">
      <strong>{label}</strong>
      <button onClick={onClick}>
        {action} <b>+</b>
      </button>
    </div>
  );
}
function kindGlyph(kind: MeshKind) {
  return kind === "agent" ? "A" : kind === "team" ? "T" : "W";
}

function EnvironmentDialog({
  onClose,
  onCreated,
  environment,
}: {
  onClose: () => void;
  onCreated: () => Promise<void>;
  environment?: MeshEnvironment;
}) {
  const [status, setStatus] = useState(environment?.status ?? "active");
  const { t } = useTranslation();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (environment) {
      await updateMeshEnvironment(environment.id, { name: String(data.get("name")), description: String(data.get("description") || ""), status: String(data.get("status")) as "active" | "inactive" });
    } else {
      await createMeshEnvironment({ name: String(data.get("name")), slug: String(data.get("slug")), description: String(data.get("description") || "") });
    }
    await onCreated();
  }
  return (
    <div className="mesh-dialog-backdrop">
      <form className="mesh-dialog" onSubmit={submit}>
        <button type="button" className="mesh-close" onClick={onClose}>
          ×
        </button>
        <div className="mesh-section-index">{t(environment ? "mesh.editEnvironmentIndex" : "mesh.newEnvironmentIndex").toUpperCase()}</div>
        <h2>{t(environment ? "mesh.editEnvironment" : "mesh.createEnvironment")}</h2>
        <p>{t("mesh.environmentHint")}</p>
        <label>
          {t("mesh.name")}
          <input name="name" placeholder={t("mesh.namePlaceholder")} defaultValue={environment?.name} required />
        </label>
        {!environment && <label>
          {t("mesh.slug")}
          <input
            name="slug"
            placeholder={t("mesh.slugPlaceholder")}
            pattern="[a-z0-9][a-z0-9-]{0,62}"
            required
          />
        </label>}
        {environment && <label>{t("mesh.status")}<ContextCombobox name="status" label={t("mesh.status")} value={status} onChange={setStatus} options={[{ value: "active", label: t("mesh.active") }, { value: "inactive", label: t("mesh.inactive") }]} /></label>}
        <label>
          {t("mesh.description")}
          <textarea
            name="description"
            placeholder={t("mesh.environmentDescriptionPlaceholder")}
            defaultValue={environment?.description ?? ""}
          />
        </label>
        <button className="mesh-primary" type="submit">
          {t(environment ? "mesh.saveEnvironment" : "mesh.createEnvironmentAction")} <span>+</span>
        </button>
      </form>
    </div>
  );
}

function DefinitionDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => Promise<void>;
}) {
  const [kind, setKind] = useState<MeshKind>("agent");
  const [memoryProfile, setMemoryProfile] = useState("none");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await createMeshDefinition({
      name: String(data.get("name")),
      key: String(data.get("key")),
      kind,
      version: String(data.get("version")),
      description: String(data.get("description") || ""),
      summary: { memory_profile: memoryProfile },
    });
    await onCreated();
  }
  return (
    <div className="mesh-dialog-backdrop">
      <form className="mesh-dialog" onSubmit={submit}>
        <button type="button" className="mesh-close" onClick={onClose}>
          ×
        </button>
        <div className="mesh-section-index">REGISTER ARTIFACT</div>
        <h2>Publish a runtime identity</h2>
        <p>
          The registry stores an immutable version declaration, not executable
          source or secrets.
        </p>
        <div className="mesh-form-grid">
          <label>
            Name
            <input name="name" placeholder="Support triage" required />
          </label>
          <label>
            Type
            <ContextCombobox name="kind" label="Type" value={kind} onChange={(value) => setKind(value as MeshKind)} options={[{ value: "agent", label: "Agent" }, { value: "team", label: "Team" }, { value: "workflow", label: "Workflow" }]} />
          </label>
        </div>
        <div className="mesh-form-grid">
          <label>
            Stable key
            <input
              name="key"
              placeholder="support-triage"
              pattern="[a-z0-9][a-z0-9-]{0,126}"
              required
            />
          </label>
          <label>
            Version
            <input name="version" placeholder="1.0.0" required />
          </label>
        </div>
        <label>
          Memory profile
          <ContextCombobox name="memory_profile" label="Memory profile" value={memoryProfile} onChange={setMemoryProfile} options={[{ value: "none", label: "No retained memory" }, { value: "session", label: "Session memory" }]} />
        </label>
        <label>
          Description
          <textarea
            name="description"
            placeholder="What operational responsibility does this artifact own?"
          />
        </label>
        <button className="mesh-primary" type="submit">
          Register version <span>+</span>
        </button>
      </form>
    </div>
  );
}
