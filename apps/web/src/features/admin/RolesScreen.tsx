import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, RoleMirrorStatus, RolesListing } from "../../api/client";
import { ASSIGNABLE_ROLES, mirrorState, needsSecondApprover, oldestPendingMinutes, toggleRole } from "./rolesModel";
import { ScreenState } from "../../ui/ScreenState";
import { useActionNotice } from "../../ui/NoticeProvider";
import { ConfirmDialog } from "../../ui/ConfirmDialog";
import { Card } from "../../ui/Card";
import { Button } from "../../ui/Button";
import { DataTable } from "../../ui/DataTable";

export const RolesScreen: React.FC = () => {
  const { t } = useTranslation();
  const [listing, setListing] = useState<RolesListing | null>(null);
  const [mirror, setMirror] = useState<RoleMirrorStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useActionNotice();
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState<{ userId: string; roles: string[]; active: boolean } | null>(null);

  const load = useCallback(async () => {
    try {
      const [l, m] = await Promise.all([api.getRoles(), api.getRoleMirror()]);
      setListing(l);
      setMirror(m);
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async (userId: string, roles: string[], active: boolean) => {
    setError(null);
    setNotice(null);
    try {
      await api.updateRoles(userId, roles, active);
      setNotice(t("admin.roles.saved"));
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
    await load();
  };

  const retry = async () => {
    setError(null);
    try {
      await api.retryRoleMirror();
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
    await load();
  };

  const state = mirror ? mirrorState(mirror) : "ok";

  return (
    <section aria-labelledby="roles-title">
      <ConfirmDialog
        open={pending !== null}
        title={t("admin.roles.confirm.title")}
        objectLabel={pending ? t("admin.roles.confirm.object", { user: pending.userId }) : ""}
        effect={t("admin.roles.confirm.effect")}
        confirmLabel={t("admin.roles.confirm.apply")}
        onCancel={() => setPending(null)}
        onConfirm={() => {
          const change = pending;
          setPending(null);
          if (change) void save(change.userId, change.roles, change.active);
        }}
      />
      <Card as="div">
        <h2 className="mmi-title-lg mmi-mb-2" id="roles-title">
          {t("admin.roles.title")}
        </h2>
        <p className="mmi-muted mmi-text-sm mmi-mt-0">{t("admin.roles.subtitle")}</p>

        {loading && <ScreenState state="loading" skeletonLines={3} />}
        {error && (
          <p className="mmi-error" role="alert">
            {error}
          </p>
        )}
        {notice && <p role="status">{notice}</p>}

        {listing && (
          <>
            <p>{t("admin.roles.approvers", { count: listing.eligible_approvers_count })}</p>
            {needsSecondApprover(listing.eligible_approvers_count) && <p role="alert">{t("admin.roles.need_two")}</p>}

            {listing.users.length === 0 ? (
              <p>{t("admin.roles.empty")}</p>
            ) : (
              <DataTable
                ariaLabel={t("a11y.roles_table")}
                rows={listing.users}
                rowKey={(u) => u.user_id}
                columns={[
                  { id: "user", header: t("admin.roles.user"), cell: (u) => <strong>{u.user_id}</strong>, sortValue: (u) => u.user_id },
                  {
                    id: "roles",
                    header: t("admin.roles.roles"),
                    cell: (u) => (
                      <>
                        {ASSIGNABLE_ROLES.map((r) => (
                          <label className="mmi-mr-3" key={r}>
                            <input
                              type="checkbox"
                              checked={u.roles.includes(r)}
                              aria-label={`${u.user_id} ${t(`roles.${r}`)}`}
                              onChange={() => setPending({ userId: u.user_id, roles: toggleRole(u.roles, r), active: u.active })}
                            />{" "}
                            {t(`roles.${r}`)}
                          </label>
                        ))}
                      </>
                    ),
                  },
                  {
                    id: "active",
                    header: t("admin.roles.active"),
                    cell: (u) => (
                      <input
                        type="checkbox"
                        checked={u.active}
                        aria-label={`${u.user_id} ${t("admin.roles.active")}`}
                        onChange={() => setPending({ userId: u.user_id, roles: u.roles, active: !u.active })}
                      />
                    ),
                  },
                ]}
              />
            )}
          </>
        )}

        {mirror && (
          <div className="mmi-mt-5" aria-label={t("a11y.mirror_status")}>
            <h3 className="mmi-title-md">{t("admin.roles.mirror_title")}</h3>
            {state === "ok" && <p>{t("admin.roles.mirror_ok")}</p>}
            {state !== "ok" && (
              <>
                <p>{t("admin.roles.mirror_pending", { count: mirror.pending })}</p>
                <p>{t("admin.roles.mirror_oldest", { minutes: oldestPendingMinutes(mirror) })}</p>
              </>
            )}
            {state === "failed" && (
              <>
                <p role="alert">{t("admin.roles.mirror_failed", { count: mirror.failed })}</p>
                <Button onClick={() => void retry()}>
                  {t("admin.roles.retry")}
                </Button>
              </>
            )}
          </div>
        )}
      </Card>
    </section>
  );
};
