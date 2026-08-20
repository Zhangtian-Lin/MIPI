export type SourceGrade = "S1" | "S2" | "S3" | "S4" | "S5" | "S6";
export type FactLevel = "F0" | "F1" | "F2" | "F3" | "F4";

export const factLevelLabels: Record<FactLevel, string> = {
  F0: "线索",
  F1: "单一来源报道",
  F2: "第一方正式宣布",
  F3: "多个独立来源一致",
  F4: "权威记录确认",
};

export function formatOriginalMoney(amount: number | null, currency: string | null): string {
  if (amount === null || currency === null) return "来源未披露";
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount);
}

