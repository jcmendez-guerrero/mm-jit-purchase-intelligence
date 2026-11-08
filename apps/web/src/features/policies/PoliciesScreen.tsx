import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, PolicyConsole } from "../../api/client";
import { DemandSection } from "./DemandSection";
import { ForecastSection } from "./ForecastSection";
import { PurchasingSection } from "./PurchasingSection";
import { SafetyStockSection } from "./SafetyStockSection";
import { Button } from "../../ui/Button";
import { ScreenState } from "../../ui/ScreenState";
import { Card } from "../../ui/Card";

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
      <Card as="div">
        <h2 id="policies-title">{t("policies.title")}</h2>
        <p className="mmi-muted">{t("policies.subtitle")}</p>
        {error && <ScreenState state="error" errorHint={error} onRetry={() => void load()} />}
        <div className="mmi-split mmi-split--nav">
        <div className="mmi-split__aside">
        <div role="tablist" aria-label={t("policies.title")} className="mmi-tablist">
          {TABS.map((id) => (
            <Button key={id} role="tab" aria-selected={tab === id} variant={tab === id ? "primary" : "secondary"} onClick={() => setTab(id)}>
              {t(`policies.section.${id}`)}
            </Button>
          ))}
        </div>
        </div>
        <div className="mmi-split__main">
        {data === null ? (
          <ScreenState state="loading" skeletonLines={4} />
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
        </div>
      </Card>
    </section>
  );
};
