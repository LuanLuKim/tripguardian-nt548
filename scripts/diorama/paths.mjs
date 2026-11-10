import { realpathSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const CODE = dirname(realpathSync(fileURLToPath(import.meta.url)));
export const REPO = resolve(CODE, '../..');
export const DATA = resolve(process.env.DIORAMA_DATA ?? resolve(REPO, '../tripguardian-store/splat/diorama'));
