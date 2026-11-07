import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, RoleMirrorStatus, RolesListing } from "../../api/client";
import { ASSIGNABLE_ROLES, mirrorState, needsSecondApprover, oldestPendingMinutes, toggleRole } from "./rolesModel";

export const RolesScreen: React.FC = () => {
  const { t } = useTranslation();
  const [listing, setListing] = useState<RolesListing | null>(null);
  const [mirror, setMirror] = useState<RoleMirrorStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
      <div className="mmi-card">
        <h2 id="roles-title" style={{ fontSize: "1.3rem", marginBottom: "0.5rem" }}>
          {t("admin.roles.title")}
        </h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "0.9rem", marginTop: 0 }}>{t("admin.roles.subtitle")}</p>

        {loading && <p>{t("common.loading")}</p>}
        {error && (
          <p role="alert" style={{ color: "var(--color-danger)" }}>
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
              <div className="mmi-table-wrapper">
                <table className="mmi-table" aria-label={t("a11y.roles_table")}>
                  <thead>
                    <tr>
                      <th scope="col">{t("admin.roles.user")}</th>
                      <th scope="col">{t("admin.roles.roles")}</th>
                      <th scope="col">{t("admin.roles.active")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {listing.users.map((u) => (
                      <tr key={u.user_id}>
                        <th scope="row" style={{ fontWeight: 600 }}>
                          {u.user_id}
                        </th>
                        <td>
                          {ASSIGNABLE_ROLES.map((r) => (
                            <label key={r} style={{ marginRight: "0.75rem" }}>
                              <input
                                type="checkbox"
                                checked={u.roles.includes(r)}
                                aria-label={`${u.user_id} ${t(`roles.${r}`)}`}
                                onChange={() => void save(u.user_id, toggleRole(u.roles, r), u.active)}
                              />{" "}
                              {t(`roles.${r}`)}
                            </label>
                          ))}
                        </td>
                        <td>
                          <input
                            type="checkbox"
                            checked={u.active}
                            aria-label={`${u.user_id} ${t("admin.roles.active")}`}
                            onChange={() => void save(u.user_id, u.roles, !u.active)}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {mirror && (
          <div aria-label={t("a11y.mirror_status")} style={{ marginTop: "1.25rem" }}>
            <h3 style={{ fontSize: "1.05rem" }}>{t("admin.roles.mirror_title")}</h3>
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
                <button type="button" className="mmi-btn mmi-btn-primary" onClick={() => void retry()}>
                  {t("admin.roles.retry")}
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
};
