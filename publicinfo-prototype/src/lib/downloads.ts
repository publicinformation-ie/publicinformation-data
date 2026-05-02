export type BodyRecord = {
  public_body_id: number;
  public_body_name: string;
  public_body_short_name: string;
  public_body_url: string;
  public_body_category: string;
};

export type DatasetName = 'all' | 'government-department' | 'public-service-body' | 'local-authority';

const SLUG_TO_CATEGORY: Record<string, string> = {
  'government-department': 'government department',
  'public-service-body': 'public service body',
  'local-authority': 'local authority',
};

export function getDataset(name: DatasetName, records: BodyRecord[]): BodyRecord[] {
  if (name === 'all') return records;
  const category = SLUG_TO_CATEGORY[name];
  return records.filter((r) => r.public_body_category === category);
}

export function toCSV(records: BodyRecord[]): string {
  if (records.length === 0) return '';
  const keys = Object.keys(records[0]) as (keyof BodyRecord)[];
  const header = keys.join(',');
  const rows = records.map((r) =>
    keys
      .map((k) => {
        const raw = String(r[k]);
        const escaped = raw.replace(/"/g, '""');
        return raw.includes(',') || raw.includes('"') || raw.includes('\n')
          ? `"${escaped}"`
          : raw;
      })
      .join(',')
  );
  return [header, ...rows].join('\n') + '\n';
}

export function toJSON(records: BodyRecord[]): string {
  return JSON.stringify(records, null, 2);
}
