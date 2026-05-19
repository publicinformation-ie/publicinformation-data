#!/usr/bin/env node
import { createInterface } from 'readline';
import { readFile, writeFile } from 'fs/promises';
import { existsSync, readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..');

function loadEnv(filePath) {
  if (!existsSync(filePath)) return {};
  const env = {};
  for (const line of readFileSync(filePath, 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx === -1) continue;
    env[trimmed.slice(0, eqIdx).trim()] = trimmed.slice(eqIdx + 1).trim();
  }
  return env;
}

const env = loadEnv(resolve(REPO_ROOT, '.env.admin'));
const { CORRECTIONS_URL, ADMIN_API_KEY, SIGN_KARMA_URL } = env;

if (!CORRECTIONS_URL || !ADMIN_API_KEY || !SIGN_KARMA_URL) {
  console.error('Missing required env vars. Copy .env.admin.example to .env.admin and fill in values.');
  process.exit(1);
}

const FIELD_STEP_MAP = {
  website_url:      'validate_websites',
  foi_page:         'find_foi_pages',
  foi_email:        'get_foi_emails',
  disclosures_page: 'find_disclosure_pages',
};

const STEPS_DIR = resolve(REPO_ROOT, 'foi_pipeline', 'steps');

async function readStepOutput(stepName) {
  const p = resolve(STEPS_DIR, stepName, 'output.json');
  if (!existsSync(p)) return null;
  return JSON.parse(await readFile(p, 'utf8'));
}

async function readOverride(step) {
  const p = resolve(STEPS_DIR, step, 'override.json');
  if (!existsSync(p)) return [];
  return JSON.parse(await readFile(p, 'utf8'));
}

async function writeOverride(step, records) {
  await writeFile(resolve(STEPS_DIR, step, 'override.json'), JSON.stringify(records, null, 2));
}

async function fetchPending() {
  const res = await fetch(`${CORRECTIONS_URL}/pending`, {
    headers: { 'x-api-key': ADMIN_API_KEY },
  });
  if (!res.ok) throw new Error(`Fetch failed: ${res.status} ${res.statusText}`);
  return res.json();
}

async function apiAccept(correctionId, pendingKarmaRecord) {
  const res = await fetch(`${CORRECTIONS_URL}/accept`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-api-key': ADMIN_API_KEY },
    body: JSON.stringify({ correctionId, pendingKarmaRecord }),
  });
  if (!res.ok) throw new Error(`Accept failed: ${res.status} ${res.statusText}`);
}

async function apiReject(correctionId, reason) {
  const body = { correctionId };
  if (reason) body.reason = reason;
  const res = await fetch(`${CORRECTIONS_URL}/reject`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-api-key': ADMIN_API_KEY },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Reject failed: ${res.status} ${res.statusText}`);
}

async function signKarma(did) {
  const res = await fetch(SIGN_KARMA_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ did, value: 10, reason: 'correction-accepted' }),
  });
  if (!res.ok) throw new Error(`Karma signing failed: ${res.status} ${res.statusText}`);
  const { record } = await res.json();
  return record;
}

function buildOverrideRecord(correction, publicBodiesResults, foiPagesResults, foiPageUrlOverride, officialWebsiteUrlOverride) {
  const { bodyId, bodyName, field, suggestedValue } = correction;
  const now = new Date().toISOString();

  if (field === 'website_url') {
    return {
      public_body_id: bodyId,
      name: bodyName,
      official_website_url: suggestedValue,
      is_reachable: true,
      http_status: 200,
      checked_at: now,
      overridden: true,
    };
  }
  if (field === 'foi_page') {
    const body = publicBodiesResults?.find(b => b.public_body_id === bodyId);
    return {
      public_body_id: bodyId,
      name: bodyName,
      official_website_url: officialWebsiteUrlOverride ?? body?.official_website_url ?? null,
      foi_page_url: suggestedValue,
      source_method: 'manual',
      overridden: true,
    };
  }
  if (field === 'foi_email') {
    const foiPage = foiPagesResults?.find(r => r.public_body_id === bodyId);
    return {
      public_body_id: bodyId,
      name: bodyName,
      foi_page_url: foiPageUrlOverride ?? foiPage?.foi_page_url ?? null,
      foi_email: suggestedValue,
      email_status: 'found',
      overridden: true,
    };
  }
  if (field === 'disclosures_page') {
    const foiPage = foiPagesResults?.find(r => r.public_body_id === bodyId);
    return {
      public_body_id: bodyId,
      name: bodyName,
      foi_page_url: foiPageUrlOverride ?? foiPage?.foi_page_url ?? null,
      disclosure_page_url: suggestedValue,
      source_method: 'manual',
      overridden: true,
    };
  }
  throw new Error(`Unknown field: ${field}`);
}

function prompt(rl, question) {
  return new Promise(resolve => rl.question(question, resolve));
}

function formatDate(iso) {
  return iso.replace('T', ' ').slice(0, 16);
}

async function main() {
  const rl = createInterface({ input: process.stdin, output: process.stdout });

  console.log('Fetching pending corrections...');
  let corrections;
  try {
    corrections = await fetchPending();
  } catch (err) {
    console.error(`Error: ${err.message}`);
    rl.close();
    process.exit(1);
  }

  if (corrections.length === 0) {
    console.log('No pending corrections.');
    rl.close();
    return;
  }

  console.log(`Found ${corrections.length} pending correction${corrections.length === 1 ? '' : 's'}.\n`);

  const publicBodiesData = await readStepOutput('find_public_bodies');
  const foiPagesData = await readStepOutput('find_foi_pages');
  const publicBodiesResults = publicBodiesData?.public_bodies ?? null;
  const foiPagesResults = foiPagesData?.results ?? null;

  let accepted = 0, rejected = 0, skipped = 0;
  const acceptedSteps = [];

  for (let i = 0; i < corrections.length; i++) {
    const correction = corrections[i];
    const { correctionId, bodyId, bodyName, field, currentValue, suggestedValue, submitterDid, submitterIp, submittedAt } = correction;

    console.log('─'.repeat(45));
    console.log(`[${i + 1}/${corrections.length}] ${bodyName}`);
    console.log(`      Field:     ${field}`);
    console.log(`      Current:   ${currentValue ?? '(none)'}`);
    console.log(`      Suggested: ${suggestedValue}`);
    console.log(`      By (DID):  ${submitterDid}`);
    console.log(`      By (IP):   ${submitterIp}`);
    console.log(`      At:        ${formatDate(submittedAt)}`);
    console.log('');

    const answer = (await prompt(rl, 'Accept (a) / Reject (r) / Skip (s)? ')).trim().toLowerCase();

    if (answer === 'a') {
      try {
        let foiPageUrlOverride = null;
        let officialWebsiteUrlOverride = null;

        if (field === 'foi_email' || field === 'disclosures_page') {
          const existing = foiPagesResults?.find(r => r.public_body_id === bodyId);
          if (!existing?.foi_page_url) {
            const entered = (await prompt(rl, '      foi_page_url not in output — enter (required): ')).trim();
            if (!entered) {
              console.error('✗ foi_page_url is required — correction skipped.');
              skipped++;
              continue;
            }
            foiPageUrlOverride = entered;
          }
        }

        if (field === 'foi_page') {
          const body = publicBodiesResults?.find(b => b.public_body_id === bodyId);
          if (!body?.official_website_url) {
            const entered = (await prompt(rl, '      official_website_url not in output — enter (required): ')).trim();
            if (!entered) {
              console.error('✗ official_website_url is required — correction skipped.');
              skipped++;
              continue;
            }
            officialWebsiteUrlOverride = entered;
          }
        }

        const step = FIELD_STEP_MAP[field];
        const newRecord = buildOverrideRecord(correction, publicBodiesResults, foiPagesResults, foiPageUrlOverride, officialWebsiteUrlOverride);

        const records = await readOverride(step);
        const idx = records.findIndex(r => r.public_body_id === bodyId);
        if (idx !== -1) {
          records[idx] = newRecord;
        } else {
          records.push(newRecord);
        }
        await writeOverride(step, records);
        console.log(`✓ Override written:  foi_pipeline/steps/${step}/override.json`);

        const pendingKarmaRecord = await signKarma(submitterDid);
        console.log(`✓ Karma signed:      +10 for ${submitterDid} (stored as pending in KV)`);

        await apiAccept(correctionId, pendingKarmaRecord);
        console.log(`✓ Correction marked: accepted`);

        accepted++;
        if (!acceptedSteps.includes(step)) acceptedSteps.push(step);
      } catch (err) {
        console.error(`✗ Error: ${err.message}`);
      }
    } else if (answer === 'r') {
      const reason = (await prompt(rl, 'Reason (optional, press Enter to skip): ')).trim();
      try {
        await apiReject(correctionId, reason || undefined);
        console.log('✓ Correction marked: rejected');
        rejected++;
      } catch (err) {
        console.error(`✗ Error: ${err.message}`);
      }
    } else {
      skipped++;
    }

    console.log('');
  }

  console.log('─'.repeat(45));
  console.log(`Done. ${accepted} accepted, ${rejected} rejected, ${skipped} skipped.`);

  if (acceptedSteps.length > 0) {
    console.log('\nNext steps:');
    for (const step of acceptedSteps) {
      console.log(`  git add foi_pipeline/steps/${step}/override.json`);
    }
    console.log('  git commit -m "feat: accept correction for <field> (body <id>)"');
    console.log('  git push');
    console.log('  [re-run export_status step and redeploy pipeline data to CDN]');
  }

  rl.close();
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
