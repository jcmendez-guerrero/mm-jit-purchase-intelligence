import React, { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, errorMessage, LocalLoadDifference, LocalLoadKind, LocalLoadResult, LocalLoadReviewItem } from "../../api/client";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { DataTable, type Column } from "../../ui/DataTable";
import { EmptyState } from "../../ui/EmptyState";
import { useActionNotice } from "../../ui/NoticeProvider";
import { canLoad, canUse, fileProblem, KINDS, newIdempotencyKey } from "./localLoadModel";

interface Props {
  userRoles: string[];
}

interface KindState {
  file: File | null;
  checked: LocalLoadResult | null;
  loaded: LocalLoadResult | null;
  acknowledged: boolean;
  busy: boolean;
  error: string | null;
}

const EMPTY: KindState = { file: null, checked: null, loaded: null, acknowledged: false, busy: false, error: null };

const Counts: React.FC<{ result: LocalLoadResult }> = ({ result }) => {
  const { t } = useTranslation();
  const items: Array<[string, number]> = [
    ["rows", result.rows], ["loaded", result.loaded], ["updated", result.updated], ["unchanged", result.unchanged],
    ["quarantined", result.quarantined], ["excluded", result.excluded], ["services", result.services], ["differences", result.differences ?? 0],
  ];
  return (
    <dl className="mmi-counts">
      {items.map(([key, value]) => (
        <div key={key} className="mmi-counts__item">
          <dt>{t(`localLoad.counts.${key}`)}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
};

export const LocalLoadScreen: React.FC<Props> = ({ userRoles }) => {
  const { t } = useTranslation();
  const allowed = canUse(userRoles);
  const [state, setState] = useState<Record<LocalLoadKind, KindState>>({ suppliers: EMPTY, inventory: EMPTY, movements: EMPTY });
  const [review, setReview] = useState<LocalLoadReviewItem[]>([]);
  const [diffs, setDiffs] = useState<LocalLoadDifference[]>([]);
  const [notice, setNotice] = useActionNotice();
  const keys = useRef<Record<string, string>>({});

  const patch = useCallback((kind: LocalLoadKind, p: Partial<KindState>) => setState((s) => ({ ...s, [kind]: { ...s[kind], ...p } })), []);

  const refresh = useCallback(async () => {
    try {
      const [r, d] = await Promise.all([api.getLocalLoadReview(), api.getLocalLoadDifferences()]);
      setReview(r);
      setDiffs(d.filter((x) => x.status === "open"));
    } catch {
      /* the lists are secondary; a failure shows nothing rather than blocking the screen */
    }
  }, []);
  useEffect(() => {
    if (allowed) void refresh();
  }, [allowed, refresh]);

  const message = (err: unknown): string => {
    if (err instanceof ApiError && err.missing?.length) return `${errorMessage(err, t("common.error"))} ${err.missing.join(", ")}`;
    return errorMessage(err, t("common.error"));
  };

  const pick = (kind: LocalLoadKind, file: File | null) => {
    keys.current[kind] = newIdempotencyKey();
    if (file === null) return patch(kind, { ...EMPTY });
    const problem = fileProblem(file);
    patch(kind, { ...EMPTY, file: problem ? null : file, error: problem ? t(problem) : null });
  };

  const check = async (kind: LocalLoadKind) => {
    const file = state[kind].file;
    if (!file) return;
    patch(kind, { busy: true, error: null, checked: null, loaded: null, acknowledged: false });
    try {
      patch(kind, { checked: await api.checkLocalLoad(kind, file) });
    } catch (err) {
      patch(kind, { error: message(err) });
    } finally {
      patch(kind, { busy: false });
    }
  };

  const load = async (kind: LocalLoadKind) => {
    const { file, checked, acknowledged } = state[kind];
    if (!file || !canLoad(kind, checked, acknowledged)) return;
    patch(kind, { busy: true, error: null });
    try {
      const result = await api.runLocalLoad(kind, file, acknowledged, keys.current[kind] ?? newIdempotencyKey());
      patch(kind, { loaded: result, checked: null });
      setNotice(t("localLoad.done", { kind: t(`localLoad.kind.${kind}`) }));
      await refresh();
    } catch (err) {
      patch(kind, { error: message(err) });
    } finally {
      patch(kind, { busy: false });
    }
  };

  const decide = async (id: string, decision: "accept" | "ignore") => {
    try {
      await api.decideLocalLoadDifference(id, decision);
      await refresh();
    } catch (err) {
      setNotice(errorMessage(err, t("common.error")), "error");
    }
  };

  const reviewColumns: Column<LocalLoadReviewItem>[] = [
    { id: "kind", header: t("localLoad.review.kind"), cell: (r) => (r.kind ? t(`localLoad.kind.${r.kind}`) : "—") },
    { id: "row", header: t("localLoad.review.row"), cell: (r) => r.row, sortValue: (r) => r.row },
    { id: "code", header: t("localLoad.review.code"), cell: (r) => (t(`localLoad.code.${r.code}`, { defaultValue: r.code })) },
    { id: "source", header: t("localLoad.review.source"), cell: (r) => t(`localLoad.source.${r.source ?? "loader"}`) },
  ];
  const diffColumns: Column<LocalLoadDifference>[] = [
    { id: "sku", header: t("common.sku"), cell: (d) => <strong>{d.sku}</strong> },
    { id: "field", header: t("localLoad.diff.field"), cell: (d) => t(`localLoad.field.${d.field}`, { defaultValue: d.field }) },
    { id: "app", header: t("localLoad.diff.app"), cell: (d) => d.app_value },
    { id: "file", header: t("localLoad.diff.file"), cell: (d) => d.file_value },
    {
      id: "actions", header: t("common.actions"),
      cell: (d) => (
        <div className="mmi-actions">
          <Button small onClick={() => void decide(d.id, "accept")}>{t("localLoad.diff.accept")}</Button>
          <Button small variant="secondary" onClick={() => void decide(d.id, "ignore")}>{t("localLoad.diff.ignore")}</Button>
        </div>
      ),
    },
  ];

  if (!allowed) return <EmptyState title={t("localLoad.no_access")} hint="" />;

  return (
    <section aria-labelledby="local-load-title" className="mmi-stack">
      <Card as="div">
        <h2 id="local-load-title" className="mmi-title-lg">{t("localLoad.title")}</h2>
        <p className="mmi-muted">{t("localLoad.intro")}</p>
        <p className="mmi-muted">{t("localLoad.order")}</p>
        {notice && <p role="status" className="mmi-notice">{notice}</p>}
      </Card>

      {KINDS.map((kind) => {
        const s = state[kind];
        const fileId = `local-load-file-${kind}`;
        return (
          <Card key={kind} as="div">
            <h3>{t(`localLoad.kind.${kind}`)}</h3>
            <label htmlFor={fileId}>{t(`localLoad.file.${kind}`)}</label>
            <input id={fileId} type="file" accept=".csv,.xlsx" disabled={s.busy} onChange={(e) => pick(kind, e.target.files?.[0] ?? null)} />
            <div className="mmi-actions">
              <Button disabled={!s.file || s.busy} onClick={() => void check(kind)}>{t("localLoad.check")}</Button>
            </div>
            {s.error && <p role="alert" className="mmi-error">{s.error}</p>}
            {s.checked && (
              <div>
                <h4>{t("localLoad.check_result")}</h4>
                <Counts result={s.checked} />
                {kind === "inventory" && s.checked.interpretations && (
                  <>
                    <p>{t("localLoad.interpretation", { included: s.checked.interpretations.tax_included_rows ?? 0, excluded: s.checked.interpretations.tax_excluded_rows ?? 0, zone: s.checked.interpretations.timezone ?? "" })}</p>
                    <label className="mmi-check">
                      <input type="checkbox" checked={s.acknowledged} onChange={(e) => patch(kind, { acknowledged: e.target.checked })} />
                      {t("localLoad.acknowledge")}
                    </label>
                  </>
                )}
                <div className="mmi-actions">
                  <Button disabled={!canLoad(kind, s.checked, s.acknowledged) || s.busy} onClick={() => void load(kind)}>{t("localLoad.load")}</Button>
                </div>
              </div>
            )}
            {s.loaded && (
              <div>
                <h4>{t("localLoad.load_result")}</h4>
                <Counts result={s.loaded} />
              </div>
            )}
          </Card>
        );
      })}

      <Card as="div">
        <h3>{t("localLoad.differences")}</h3>
        {diffs.length === 0 ? <EmptyState title={t("localLoad.differences_empty")} hint="" /> : <DataTable ariaLabel={t("localLoad.differences")} columns={diffColumns} rows={diffs} rowKey={(d) => d.id} />}
      </Card>

      <Card as="div">
        <h3>{t("localLoad.review.title")}</h3>
        {review.length === 0 ? <EmptyState title={t("localLoad.review.empty")} hint="" /> : (
          <DataTable ariaLabel={t("localLoad.review.title")} columns={reviewColumns} rows={review} rowKey={(r) => `${r.kind}-${r.row}-${r.code}`} />
        )}
      </Card>
    </section>
  );
};
