import type { APIRoute, GetStaticPaths } from 'astro';
import bodies from '../../data/public_bodies.json';
import { getDataset, toCSV } from '../../lib/downloads';
import type { DatasetName } from '../../lib/downloads';

export const getStaticPaths: GetStaticPaths = () => [
  { params: { dataset: 'all' } },
  { params: { dataset: 'government-department' } },
  { params: { dataset: 'public-service-body' } },
  { params: { dataset: 'local-authority' } },
];

export const GET: APIRoute = ({ params }) => {
  const name = params.dataset as DatasetName;
  const records = getDataset(name, bodies as any);
  const csv = toCSV(records);
  return new Response(csv, {
    headers: {
      'Content-Type': 'text/csv',
      'Content-Disposition': `attachment; filename="public-bodies-${name}.csv"`,
    },
  });
};
