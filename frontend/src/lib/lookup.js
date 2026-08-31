export function digitsOnly(value) {
  return String(value || "").replace(/\D/g, "");
}

/**
 * Open a household when the query uniquely identifies it (ID number or household number).
 * Returns the lookup payload. Caller should navigate to search results when match !== "unique".
 */
export async function lookupHousehold(api, q) {
  const res = await api.get("/households/lookup/", { params: { q } });
  return res.data;
}

export function uniqueHousehold(payload) {
  if (payload?.match === "unique" && payload.households?.length === 1) {
    return payload.households[0];
  }
  return null;
}
