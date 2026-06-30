const fs = require('fs');

function parseNumber(v) {
  return parseFloat(v.replace(/,/g, "")) || 0;
}

function parseTransactionCSV(raw) {
  const lines = raw
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  if (lines.length < 2) return [];

  const headers = lines[0].split(",").map((h) => h.trim());

  return lines.slice(1).map((line) => {
    return { tx_id: "test" };
  });
}

const raw = fs.readFileSync('L2_transaction_monitor/data/transactions.csv', 'utf8');
const rows = parseTransactionCSV(raw);
console.log(`Parsed ${rows.length} rows`);
