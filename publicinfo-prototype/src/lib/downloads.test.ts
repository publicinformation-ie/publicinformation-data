import { describe, it, expect } from 'vitest';
import { getDataset, toCSV, toJSON } from './downloads';

const SAMPLE_BODIES = [
  {
    public_body_id: 1,
    public_body_name: 'Dept of Testing',
    public_body_short_name: 'DoT',
    public_body_url: 'https://example.com',
    public_body_category: 'government department',
  },
  {
    public_body_id: 2,
    public_body_name: 'Public Test Service',
    public_body_short_name: 'PTS',
    public_body_url: 'https://pts.example.com',
    public_body_category: 'public service body',
  },
  {
    public_body_id: 3,
    public_body_name: 'Test Council',
    public_body_short_name: 'TC',
    public_body_url: 'https://tc.example.com',
    public_body_category: 'local authority',
  },
];

describe('getDataset', () => {
  it('returns all records for dataset "all"', () => {
    const result = getDataset('all', SAMPLE_BODIES);
    expect(result).toHaveLength(3);
  });

  it('returns only government departments for "government-department"', () => {
    const result = getDataset('government-department', SAMPLE_BODIES);
    expect(result).toHaveLength(1);
    expect(result[0].public_body_category).toBe('government department');
  });

  it('returns only public service bodies for "public-service-body"', () => {
    const result = getDataset('public-service-body', SAMPLE_BODIES);
    expect(result).toHaveLength(1);
    expect(result[0].public_body_category).toBe('public service body');
  });

  it('returns only local authorities for "local-authority"', () => {
    const result = getDataset('local-authority', SAMPLE_BODIES);
    expect(result).toHaveLength(1);
    expect(result[0].public_body_category).toBe('local authority');
  });
});

describe('toCSV', () => {
  it('produces a header row from object keys', () => {
    const csv = toCSV(SAMPLE_BODIES.slice(0, 1));
    const lines = csv.trim().split('\n');
    expect(lines[0]).toBe(
      'public_body_id,public_body_name,public_body_short_name,public_body_url,public_body_category'
    );
  });

  it('produces one data row per record', () => {
    const csv = toCSV(SAMPLE_BODIES);
    const lines = csv.trim().split('\n');
    expect(lines).toHaveLength(4); // 1 header + 3 rows
  });

  it('quotes values that contain commas', () => {
    const record = {
      public_body_id: 99,
      public_body_name: 'Dept, of Commas',
      public_body_short_name: 'DC',
      public_body_url: 'https://example.com',
      public_body_category: 'government department',
    };
    const csv = toCSV([record]);
    expect(csv).toContain('"Dept, of Commas"');
  });

  it('quotes and escapes values that contain double quotes', () => {
    const record = {
      public_body_id: 100,
      public_body_name: 'He said "hello"',
      public_body_short_name: 'HS',
      public_body_url: 'https://example.com',
      public_body_category: 'government department',
    };
    const csv = toCSV([record]);
    expect(csv).toContain('"He said ""hello"""');
  });
});

describe('toJSON', () => {
  it('returns valid JSON', () => {
    const json = toJSON(SAMPLE_BODIES);
    expect(() => JSON.parse(json)).not.toThrow();
  });

  it('is pretty-printed (contains newlines)', () => {
    const json = toJSON(SAMPLE_BODIES);
    expect(json).toContain('\n');
  });

  it('contains all records', () => {
    const json = toJSON(SAMPLE_BODIES);
    const parsed = JSON.parse(json);
    expect(parsed).toHaveLength(3);
  });
});
