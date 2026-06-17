import type { Transaction } from "../types/pipeline";

function parseNumber(v: string): number {
  return parseFloat(v.replace(/,/g, "")) || 0;
}

/**
 * Parse a CSV string into Transaction objects.
 * Handles Windows line-endings and quoted fields.
 */
export function parseTransactionCSV(raw: string): Transaction[] {
  const lines = raw
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  if (lines.length < 2) return [];

  const headers = lines[0].split(",").map((h) => h.trim());

  return lines.slice(1).map((line) => {
    const values = line.split(",").map((v) => v.trim().replace(/^"|"$/g, ""));
    const row: Record<string, string> = {};
    headers.forEach((h, i) => (row[h] = values[i] ?? ""));

    return {
      tx_id: row.tx_id,
      timestamp: row.timestamp,
      channel: (row.channel as Transaction["channel"]) ?? "UPI",
      amount_inr: parseNumber(row.amount_inr),
      sender_account_id: row.sender_account_id,
      sender_name: row.sender_name,
      sender_pan: row.sender_pan,
      sender_dob: row.sender_dob,
      sender_bank: row.sender_bank,
      sender_ifsc: row.sender_ifsc,
      sender_vpa: row.sender_vpa,
      receiver_name: row.receiver_name,
      receiver_account_external: row.receiver_account_id,
      receiver_pan: row.receiver_pan,
      receiver_dob: row.receiver_dob,
      receiver_bank: row.receiver_bank,
      receiver_vpa: row.receiver_vpa,
      receiver_state: row.receiver_state,
      receiver_city: row.receiver_city,
      tx_location_state: row.tx_location_state,
      tx_location_city: row.tx_location_city,
      tx_location_country: row.tx_location_country,
      tx_location_lat: row.tx_location_lat,
      tx_location_lon: row.tx_location_lon,
      purpose_code: row.purpose_code,
      device_id: row.device_id,
      is_cross_border: row.is_cross_border,
      usd_equiv: row.usd_equiv,
      fx_usd_inr: row.fx_usd_inr,
      beneficiary_id: row.beneficiary_id,
      tx_status: row.tx_status,
    };
  });
}

/** Format a number as ₹ with Indian grouping */
export function formatINR(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}
