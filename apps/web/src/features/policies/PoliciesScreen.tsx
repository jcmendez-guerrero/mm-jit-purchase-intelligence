import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, PolicyConsole } from "../../api/client";
import { DemandSection } from "./DemandSection";
import { ForecastSection } from "./ForecastSection";
import { PurchasingSection } from "./PurchasingSection";
import { SafetyStockSection } from "./SafetyStockSection";

interface Props {
  userRoles: string[];
}

type Tab = "purchasing" | "safety" | "demand" | "forecast";
const TABS: Tab[] = ["purchasing", "safety", "demand", "forecast"];

export const PoliciesScreen: React.FC<Props> = ({ userRoles }) => {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("purchasing");
  const [data, setData] = useState<PolicyConsole | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      setData(await api.getPolicyConsole());
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const unavailable = <p role="alert">{t("policies.section_unavailable")}</p>;

  return (
    <section aria-labelledby="policies-title">
      <div className="mmi-card">
        <h2 id="policies-title">{t("policies.title")}</h2>
        <p className="mmi-muted">{t("policies.subtitle")}</p>
        {error && <p role="alert">{error}</p>}
        <div role="tablist" aria-label={t("policies.title")}>
          {TABS.map((id) => (
            <button key={id} type="button" role="tab" aria-selected={tab === id} className={`mmi-btn ${tab === id ? "mmi-btn-primary" : "mmi-btn-secondary"}`} onClick={() => setTab(id)}>
              {t(`policies.section.${id}`)}
            </button>
          ))}
        </div>

        {data === null ? (
          <p>{t("common.loading")}</p>
        ) : (
          <div role="tabpanel">
            {tab === "purchasing" &&
              (data.purchasing.ok && data.purchasing.data ? (
                <PurchasingSection roles={userRoles} policies={data.purchasing.data.policies} weeklyBudget={data.purchasing.data.weekly_budget} onChanged={() => void load()} />
              ) : (
                unavailable
              ))}
            {tab === "safety" && <SafetyStockSection roles={userRoles} />}
            {tab === "demand" &&
              (data.demand.ok && data.demand.data ? (
                <DemandSection roles={userRoles} exclusions={data.demand.data.exclusions} rules={data.demand.data.rules} onChanged={() => void load()} />
              ) : (
                unavailable
              ))}
            {tab === "forecast" &&
              (data.forecast.ok && data.forecast.data ? <ForecastSection roles={userRoles} parameters={data.forecast.data.parameters} onChanged={() => void load()} /> : unavailable)}
          </div>
        )}
      </div>
    </section>
  );
};
